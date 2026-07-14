# Mission Control — Architecture
### A control panel wrapped around a fixed, unmodified OpenMontage engine

---

## 1. The core principle

Two layers, cleanly separated, that never blur into each other:

**The Engine** — OpenMontage, pinned at a specific version/commit, packaged as a container image, never forked or modified. All 12 pipelines, all `tools/`, all `skills/`, all budget/provider-scoring logic stay exactly as authored. This is the biggest change from the previous architecture doc: instead of reimplementing pipeline stages as LangGraph nodes (Doc 1, §2), **the engine keeps running the way it was designed to** — driven by an AI agent reading its manifests and calling its tools.

**Mission Control** — a separate application that supervises many engine instances (one per project), gives every project a UI, and never touches the engine's internals. It doesn't know what a "scene plan" is; it knows "this project wrote a new checkpoint file" and "this project is waiting for a decision."

This separation is what makes the system genuinely low-risk to build: bugs in Mission Control can't corrupt a pipeline run, and upgrading OpenMontage's version later means swapping a container image, not touching your orchestration code.

---

## 2. Replacing the human — the Driver

OpenMontage is designed to be driven by a human's coding agent in a terminal. Mission Control needs something to play that role headlessly, per project, without a human present.

**Driver = OpenAI-compatible agent SDK (via OpenRouter) running headless inside the project's container**, reading the same `pipeline_defs/*.yaml` and `skills/*.md`, calling the same tools — except invoked programmatically instead of typed by a human. The Driver uses the `openai` SDK pointed at `https://openrouter.ai/api/v1`, which allows model-agnostic routing: any model OpenRouter supports (Claude, GPT, Gemini, Qwen, etc.) can drive the pipeline without code changes. This is a smaller, more faithful piece of engineering than reimplementing tool-calling in LangGraph from scratch, because it's the actual execution mode the repo was built for.

Approval gates: the Driver's tool-use is wrapped with a permission hook. When a gated action fires (script approval, scene approval, publish approval), the hook doesn't ask a terminal user — it writes a `pending_decision.json` into the project's shared volume and blocks. Mission Control's filesystem watcher (§3) sees that file, surfaces it in the UI as a decision, and once a user responds, writes the response back to the same location. The Driver's hook picks it up and resumes. No pipeline logic changes — this is purely an I/O substitution, chat-in-terminal replaced by file-in-shared-volume.

**LangGraph's job moves up one level.** It's no longer modeling "research → script → scene_plan → ..." (the engine already models that internally). It's the **supervisor graph**: one node per *project lifecycle* concern — provision container, wait for engine to reach a checkpoint or a pending decision, surface it, resume on user input, detect stall/failure, archive on completion, tear down container. This is a coarse state machine over container + filesystem events, not a re-implementation of the creative pipeline — genuinely less code, and it can't drift out of sync with OpenMontage's own logic because it never touches it.

```python
# supervisor graph — sketch, not the pipeline itself
def provision(state):        # spin up pinned OpenMontage container for this project
def await_checkpoint(state): # poll/subscribe to shared volume for new checkpoint or pending_decision.json
def surface_decision(state): # write approval_gates row, interrupt() for UI
def resume_driver(state):    # write decision back to shared volume, unblock the Driver
def archive(state):          # on completion: move assets to object storage, close out project
```

### 2.5 Multi-model routing

The Driver routes per-stage AI work to different models over OpenRouter, optimizing cost vs. quality. Model selection is baked into the Driver at deploy time with sensible defaults, and overridable per project via Studio mode.

| Stage | Default model | OpenRouter ID | Rationale |
|---|---|---|---|---|
| **research** | Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | Fast, cheap — factual gathering only |
| **proposal** | Claude Sonnet 4.5 | `anthropic/claude-sonnet-4.5` | Needs creative synthesis |
| **script** | Claude Sonnet 4.5 | `anthropic/claude-sonnet-4.5` | Highest quality writing |
| **scene_plan** | GPT-4o | `openai/gpt-4o` | Visual/structured reasoning |
| **assets** | GPT-4o | `openai/gpt-4o` | Tool-calling heavy, structured output |
| **edit** | Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | Lightweight decision-making |
| **compose** | n/a | n/a | Rendering only, no AI call |
| **publish** | Claude Haiku 4.5 | `anthropic/claude-haiku-4.5` | Metadata composition |

Per-stage model overrides are passed to the engine container as `MODEL_ROUTING` env var (JSON map of `stage → model_name`). The Driver reads this at stage entry and selects the model for the OpenAI chat completion call. If no override is set for a stage, the default table above applies.

The same OpenRouter API key (from `provider_credentials`) is used for all stages — only the model string changes, never the auth or base URL.

---

## 3. The filesystem bridge

OpenMontage already writes everything Mission Control needs to display — checkpoints, decision logs, cost tracking, storyboard state — it just writes them as local files in `projects/<name>/`. Mission Control doesn't re-derive any of this; it **mirrors** it:

- A lightweight sidecar process per project container tails the shared volume and pushes diffs to Mission Control's API
- API writes mirrored state into Postgres (`stage_checkpoints`, `decision_log`, `budget_ledger` — same shape as Doc 1 §1, populated by mirroring instead of by LangGraph nodes writing directly)
- WebSocket/SSE pushes live updates to the UI

This means Mission Control's data model is a **read replica of the engine's own state**, not a parallel source of truth — much lower risk of the two disagreeing with each other.

---

## 4. Mission Control UI — the control room

Leaning into the metaphor directly, because it maps cleanly onto the panels already designed in earlier rounds:

**Fleet View** (was: Library) — every active and past project as a status light: 🟢 nominal / 🟡 awaiting your decision / 🔴 anomaly / ⚪ archived. This is the front door — a glance tells you what needs attention across every project in flight.

**Launch Console** (was: New Project Wizard) — Guided mode (brief + duration + cost dial) or Studio mode (full parameter form), same as previously specced. "Launch" kicks off `provision()` in the supervisor graph.

**Telemetry / Command Deck** (was: Live Run Cockpit) — the mirrored checkpoint stream rendered live: stage tracker, screenplay view, storyboard contact sheet, decision log, running cost. Pending decisions render as **GO / NO-GO** prompts, with a revision-notes field for NO-GO-with-changes — this is the direct UI form of the approval-gate mechanism in §2, and it's where the scene-level "regenerate this take, lock that one" control from earlier rounds lives.

**Mission Archive** (was: Project Detail) — every past run, full checkpoint history scrubbable end-to-end (this is a straight read of the mirrored `stage_checkpoints` table — no extra engineering beyond what §3 already gives you), assets browsable and downloadable, fork-as-new-launch.

**Ground Systems** (was: Settings) — provider credential vault, budget caps ("fuel budget"), style playbooks ("mission profiles" — save a param set + style as a reusable template), crew/team roles.

---

## 5. Project configuration & management tooling

This is the part that turns "a wrapper" into "a product" — the pieces that don't exist in OpenMontage at all today:

- **Template library**: any launched project's parameter set + style playbook can be saved as a named template ("mission profile"), reused for future launches — the mechanism for a team to build a consistent house style over time
- **Multi-project scheduling**: the supervisor graph can cap concurrent container provisioning per tenant (compute governance), queue launches past that cap, and show queue position in Fleet View
- **Model routing**: per-stage model picker (OpenRouter) configurable per project in Studio mode, overriding the built-in defaults in §2.5
- **Credential/provider config UI**: BYOK per tenant, test-connection, scoped per project or tenant-wide default
- **Budget console**: cap mode (observe/warn/cap) set at tenant level with per-project override, real-time ledger, spend-vs-estimate reporting per completed launch — closes the trust loop from the original UX critique
- **Team roles**: owner/editor/viewer, who can approve gates vs. who can only view telemetry

---

## 6. Deployment shape (Coolify / Hetzner)

| Container | Role |
|---|---|
| `mission-control-web` | Next.js frontend |
| `mission-control-api` | FastAPI — project CRUD, auth, supervisor graph host |
| `postgres` | mirrored state, tenants, templates, budget ledger |
| `redis` | supervisor graph pub/sub, job queue |
| `minio` | archived project assets |
| `openmontage-engine:{pinned-version}` | **spun up per active project**, not a permanent service — ephemeral, torn down on archive |

Only the engine containers scale with concurrent video generation load; Mission Control's own services stay small and constant. This is a materially cheaper and simpler resource story than the full re-platform in Doc 1, since render/generation compute is fully contained inside per-project engine instances rather than shared workers you have to isolate yourself.

---

## 7. Why this beats the full re-platform (Doc 1)

- **No pipeline logic is reimplemented** — zero risk of Mission Control's graph drifting out of sync with OpenMontage's actual stage behavior as the upstream repo evolves
- **Upgrading OpenMontage = swap a pinned image version**, test against the same Driver contract, ship — not a merge conflict against your own fork
- **LangGraph's job shrinks to something it's genuinely good at** — coarse lifecycle/state supervision — instead of being asked to mirror a bespoke pipeline DSL it didn't design
- **AGPL exposure narrows**: you're not modifying OpenMontage's source at all, just running it as a pinned dependency and building genuinely separate software around it — worth confirming with a proper license read, but structurally the cleanest posture available
- **Self-hosted-first still holds** (Doc 2 §3) — Mission Control + its engine containers deploy as one Coolify stack per customer, same license-and-managed-hosting business model
