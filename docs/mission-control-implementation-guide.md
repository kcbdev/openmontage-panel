# OpenMontage Mission Control — Implementation Guide
### UI layouts, components, data schema, and exact mapping to the current OpenMontage repo

This guide is grounded in the current `calesthio/OpenMontage` structure: 12 pipelines, 48-52 tools across 7 categories, YAML pipeline manifests, Markdown skills, JSON-schema-validated checkpoints, a 7-dimension provider scorer, and the existing local Backlot board. Mission Control wraps this — a pinned engine — and does not modify any of it. Every entity below either mirrors a file OpenMontage already writes, or is genuinely new surface area Mission Control adds on top.

---

## 1. Engine mapping — what's pinned, what's wrapped

| OpenMontage (engine, pinned, unmodified) | Mission Control (wrapper) |
|---|---|
| `pipeline_defs/*.yaml` (12 pipelines: Animated Explainer, Animation, Avatar Spokesperson, Cinematic, Clip Factory, Documentary Montage, Hybrid, Localization & Dub, Podcast Repurpose, Screen Demo, Talking Head, Character Animation) | Launch Console pipeline picker — one tile per manifest, description pulled from the manifest itself |
| Stage sequence `research → proposal → script → scene_plan → assets → edit → compose` | Command Deck stage tracker — 7 nodes, exact order preserved |
| 5 enforced gates: proposal, script, scene plan, generated assets, publish | Command Deck GO/NO-GO prompts — one UI pattern, 5 instantiations |
| `tools/` (video/, audio/, graphics/, enhancement/, analysis/, avatar/, subtitle/) | Ground Systems provider directory + Studio-mode per-capability pinning |
| `skills/pipelines/`, `skills/creative/`, `skills/core/`, `skills/meta/` | Not surfaced directly — these drive the Driver's behavior inside the engine container, invisible to the UI by design |
| `schemas/` (15 JSON Schemas) | Mission Control validates its own mirrored copies against the same schemas — no duplicate schema authoring |
| `styles/*.yaml` (Clean Professional, Flat Motion Graphics, Minimalist Diagram) | Ground Systems → Mission Profiles, plus any tenant-cloned custom playbooks |
| Checkpoint JSON (`lib/` checkpoint writer, resumable, decision log + cost snapshot per stage) | `stage_checkpoints` table — direct mirror, one row per checkpoint file |
| `registry.support_envelope()` / `registry.provider_menu()` (7-dimension scorer: task fit 30%, output quality 20%, control 15%, reliability 15%, cost efficiency 10%, latency 5%, continuity 5%) | Decision trail panel on Command Deck, provider picker in Studio mode — reads the registry's own output, doesn't re-score anything |
| Budget governance (estimate → reserve → reconcile; modes observe/warn/cap; default per-action threshold $0.50, default total cap $10) | Ground Systems → Budget console; `budget_ledger` table mirrors the engine's own reserve/reconcile events |
| `backlot/` (existing local board: `python -m backlot open`, `open <project-id>`, `backlot_simulate_run.py`) | Backlot's data model is the proof this bridge works today, single-user/local — Mission Control's filesystem bridge (§4) is Backlot's mirroring logic, made multi-project and multi-tenant |
| Platform output profiles (YouTube Landscape/4K/Shorts, Reels, Feed, TikTok, LinkedIn, Cinematic 21:9) | Launch Console platform-profile dropdown, values taken verbatim from the engine's own profile table |
| `render_runtime` (Remotion vs HyperFrames, locked at proposal via `edit_decisions`) | Studio-mode render runtime lock/auto toggle; Command Deck displays which was chosen and why (decision log entry) |
| (not applicable — OpenRouter routing) | Studio → Model routing: per-stage model override (OpenRouter), written into Driver config at provision as `MODEL_ROUTING` env var |

---

## 2. Database schema (Postgres)

Every table either mirrors an artifact the engine already writes (marked **[mirror]**) or is new to Mission Control (marked **[new]**).

```sql
-- ============ TENANCY & IDENTITY [new] ============
tenants (
  id UUID PK, name TEXT, plan TEXT,
  budget_cap_default NUMERIC DEFAULT 10.00,   -- matches engine's own $10 default
  budget_mode_default TEXT DEFAULT 'warn',     -- observe | warn | cap
  approval_threshold_default NUMERIC DEFAULT 0.50,
  created_at TIMESTAMPTZ
)

users (
  id UUID PK, tenant_id FK, email TEXT, role TEXT, -- owner | editor | viewer
  created_at TIMESTAMPTZ
)

provider_credentials (          -- BYOK, maps 1:1 to .env keys the engine reads
  id UUID PK, tenant_id FK,
  provider_key TEXT,             -- FAL_KEY, ELEVENLABS_API_KEY, SUNO_API_KEY, etc.
  encrypted_value TEXT, scope TEXT,  -- tenant | platform
  last_verified_at TIMESTAMPTZ
)

-- ============ PROJECTS [new + mirror] ============
projects (
  id UUID PK, tenant_id FK, owner_id FK,
  name TEXT,
  pipeline_type TEXT,             -- one of the 12 pipeline_defs manifest ids
  status TEXT,                    -- draft | running | awaiting_decision | anomaly | done | archived
  render_runtime TEXT,            -- 'remotion' | 'hyperframes' — mirrors edit_decisions.render_runtime
  style_playbook TEXT,            -- references styles/*.yaml or a cloned tenant variant
  platform_profile TEXT,          -- e.g. 'youtube_shorts', 'instagram_reels'
  duration_target_seconds INT,
  parent_project_id UUID NULL,    -- set when created via Remix
  created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
)

project_params (                  -- full parameter snapshot, versioned [new]
  id UUID PK, project_id FK, version INT,
  params_json JSONB,               -- everything set in Launch Console (Guided or Studio)
  created_at TIMESTAMPTZ
)

runs (                             -- one engine container lifecycle per attempt [new]
  id UUID PK, project_id FK,
  engine_container_id TEXT,        -- Docker/Coolify container reference
  engine_version TEXT,             -- pinned OpenMontage image tag
  status TEXT,                     -- provisioning | running | paused_decision | anomaly | done | torn_down
  current_stage TEXT,              -- research | proposal | script | scene_plan | assets | edit | compose
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ
)

-- ============ MIRRORED ENGINE STATE [mirror — read replica only] ============
stage_checkpoints (                -- mirrors lib/ checkpoint JSON files verbatim
  id UUID PK, run_id FK,
  stage TEXT,
  checkpoint_json JSONB,           -- the engine's own checkpoint payload, unmodified
  decision_log_json JSONB,         -- engine's decision log entries for this checkpoint
  cost_snapshot_json JSONB,        -- engine's own cost tracking at this point
  schema_version TEXT,             -- validated against schemas/ at mirror time
  created_at TIMESTAMPTZ
)

decision_log (                     -- flattened, queryable view of provider/style/fallback choices
  id UUID PK, run_id FK, stage TEXT,
  decision_type TEXT,               -- provider_selection | style_choice | renderer_choice | fallback
  chosen TEXT, alternatives_json JSONB,   -- mirrors registry.support_envelope() scoring output
  confidence NUMERIC, reasoning TEXT,
  created_at TIMESTAMPTZ
)

assets (                           -- mirrors projects/<name>/assets/ + renders/
  id UUID PK, run_id FK, stage TEXT,
  type TEXT,                        -- image | video | audio | subtitle | render
  storage_path TEXT,                -- MinIO/S3 path, populated on archive
  provider_used TEXT, cost NUMERIC, quality_score NUMERIC,
  is_locked BOOLEAN DEFAULT FALSE,  -- Mission Control-only flag, drives scoped re-runs (§5)
  created_at TIMESTAMPTZ
)

budget_ledger (                    -- mirrors the engine's estimate/reserve/reconcile events
  id UUID PK, tenant_id FK, project_id FK, run_id FK,
  action TEXT, estimated_cost NUMERIC, actual_cost NUMERIC,
  mode TEXT,                        -- observe | warn | cap
  created_at TIMESTAMPTZ
)

-- ============ DECISION GATES [new — the Driver's I/O surface] ============
approval_gates (
  id UUID PK, run_id FK, stage TEXT,
  gate_type TEXT,                   -- proposal | script | scene_plan | assets | publish  (the 5 enforced gates)
  payload_json JSONB,                -- what's being reviewed — script text, storyboard, final render ref
  status TEXT,                       -- pending | approved | revise | rejected
  revision_notes TEXT,
  resolved_by UUID FK, resolved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ
)

-- ============ REUSE & TEMPLATES [new] ============
mission_profiles (                  -- saved parameter sets + style, named templates
  id UUID PK, tenant_id FK, name TEXT,
  params_json JSONB, style_playbook TEXT,
  created_at TIMESTAMPTZ
)
```

---

## 3. UI layouts and components

### 3.1 Fleet View (`/projects`)

```
┌─────────────────────────────────────────────────────────┐
│ Mission Control          [Search]      [+ New Launch]     │
├─────────────────────────────────────────────────────────┤
│ Filters: [Status ▾] [Pipeline ▾] [Date ▾]                 │
├─────────────────────────────────────────────────────────┤
│ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐  │
│ │ 🟡 AWAITING│ │ 🟢 RUNNING │ │ ⚪ ARCHIVED│ │ 🔴 ANOMALY │  │
│ │ Product    │ │ Podcast    │ │ Q2 Explain-│ │ Cinematic  │  │
│ │ Launch     │ │ Repurpose  │ │ er         │ │ Trailer    │  │
│ │ script gate│ │ scene_plan │ │ $0.42      │ │ gen failed │  │
│ │ [thumbnail]│ │ [thumbnail]│ │ [thumbnail]│ │ [thumbnail]│  │
│ └───────────┘ └───────────┘ └───────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Components:** `ProjectCard` (status badge, pipeline icon, live cost, thumbnail, gate label if 🟡), `FilterBar`, `StatusLight` (🟢🟡🔴⚪ — direct read of `runs.status`), `EmptyState` (first-run CTA).

### 3.2 Launch Console (`/projects/new`)

**Guided mode (default):**
```
┌─────────────────────────────────────────────────────────┐
│  What's the video about?                                  │
│  [___________________________________]  or  [Paste a URL] │
│                                                             │
│  How long?          [====●=======]  45s                   │
│  Budget              ○ Free   ● Balanced   ○ Premium      │
│                                                             │
│  → Suggested pipeline: Animated Explainer  [change]        │
│  → Estimated cost: $0.85          [Advanced ▸]             │
│                                                             │
│                              [Launch]                      │
└─────────────────────────────────────────────────────────┘
```

**Studio mode (Advanced toggle):**
```
Pipeline          [Cinematic ▾]                     — one of 12 pipeline_defs
Duration          [30s]
Platform profile  [YouTube Shorts (1080x1920, 9:16) ▾]
Style playbook    [Flat Motion Graphics ▾]  [Clone & edit]
Render runtime    ○ Auto  ● Remotion  ○ HyperFrames
Footage mode      ○ AI-generated  ○ Real-footage only  ● Hybrid

Per-capability provider pinning:
  Video gen    [Auto (scored) ▾]  → Kling / Runway Gen-4 / Veo 3 / WAN 2.1 (local) / Pexels ...
  Image gen    [Auto (scored) ▾]  → FLUX / Imagen / GPT Image 2 / Local Diffusion ...
  Narration    [Piper (free) ▾]   → ElevenLabs / Google TTS / OpenAI TTS / Piper
  Music        [Auto (scored) ▾]  → Suno / ElevenLabs Music / none

Quality gates     Slideshow-risk strictness [Standard ▾]   Delivery-promise strictness [Standard ▾]
Model routing     Per-stage model picker (via OpenRouter) — overrides the Driver's built-in defaults
Budget cap        [$5.00]   Per-action approval above [$0.50]

                              [Launch]
```

**Components:** `PipelinePicker` (tiles, description pulled live from manifest metadata), `CostDial`, `ReferenceVideoDropzone`, `ProviderSelect` (populated from `registry.provider_menu()` mirror, grouped by capability exactly as `tools/` is grouped — video/audio/graphics), `StylePlaybookPicker`, `PlatformProfileSelect` (the 8 built-in profiles verbatim), `ModelRoutingConfig` (per-stage model picker over OpenRouter), `BudgetInputs`, `AdvancedToggle`.

### 3.3 Command Deck (`/projects/:id/run/:runId`) — the core screen

```
┌─────────────────────────────────────────────────────────────────┐
│ ● research  ● proposal  ● script  ○ scene_plan  ○ assets ○ edit ○ compose │
│                                          ^ current stage highlighted     │
├─────────────────────────────────┬─────────────────────────────────┤
│  SCRIPT — awaiting your review    │  DECISION TRAIL (live)          │
│  ┌─────────────────────────────┐ │  ✓ Provider: ElevenLabs TTS      │
│  │ SCENE 1 — INT. LAB — DAY     │ │    (task fit 0.9, cost 0.4)      │
│  │                               │ │  ✓ Style: Flat Motion Graphics   │
│  │ NARRATOR (V.O.)               │ │  ✓ Renderer: Remotion            │
│  │ "In every cell of your body.."│ │    (data-driven brief detected)  │
│  └─────────────────────────────┘ │                                   │
│                                   │  COST METER                      │
│  [Approve] [Revise: ______] [Reject]│  $0.34 / $5.00 cap  ▓▓▓░░░░░  │
├─────────────────────────────────┴─────────────────────────────────┤
│  [◀ Replay from start]                              [Scrub ─●───]  │
└─────────────────────────────────────────────────────────────────┘
```

At the `scene_plan` / `assets` gates, the main panel becomes a storyboard contact sheet:

```
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐
│ Scene1│ │ Scene2│ │ Scene3│ │ Scene4│
│ 🔒     │ │ 🔒     │ │       │ │       │
│ $0.08  │ │ $0.08  │ │ $0.11 │ │ $0.09 │
│[Lock]  │ │[Lock]  │ │[Regen]│ │[Regen]│
└───────┘ └───────┘ └───────┘ └───────┘
       [Approve storyboard] [Regenerate unlocked scenes]
```

**Components:** `StageTracker` (7-node, mirrors engine stage sequence exactly), `ScreenplayView` (script gate), `StoryboardContactSheet` (scene_plan/assets gates — per-card `SceneCard` with `LockToggle` and `RegenerateButton`, driving `assets.is_locked`), `DecisionTrailPanel` (live feed from `decision_log`), `CostMeter` (reads `budget_ledger` running total against `projects.budget_cap`), `GateActionBar` (Approve / Revise-with-notes / Reject — writes to `approval_gates`), `ReplayScrubber` (scrubs `stage_checkpoints` history).

### 3.4 Mission Archive (`/projects/:id`)

```
┌─────────────────────────────────────────────────────────┐
│ Product Launch Explainer          [Remix] [Download]      │
├─────────────────────────────────────────────────────────┤
│ Versions: [v3 (current)] [v2] [v1]                        │
│ Total cost: $1.12   Pipeline: Animated Explainer           │
├─────────────────────────────────────────────────────────┤
│ Asset Library                                              │
│  research/ (3)  script/ (1)  scenes/ (8)  renders/ (1)     │
│  [grid of thumbnails, filterable by stage/type]            │
├─────────────────────────────────────────────────────────┤
│ Decision Audit Trail                     [Export]          │
│  Provider, style, and renderer choices, full reasoning     │
└─────────────────────────────────────────────────────────┘
```

**Components:** `VersionSelector`, `AssetGrid` (filterable by `assets.stage`/`assets.type`), `DecisionAuditTable`, `RemixButton` (creates a new `project` with `parent_project_id` set, pre-fills Launch Console from `project_params`).

### 3.5 Ground Systems (`/settings`)

Tabs: **Credentials** (`provider_credentials` CRUD, test-connection per key, grouped exactly as the engine's `.env.example` groups them — image/video gateway, free stock, music, voice, more video providers), **Budget** (tenant defaults, mirrors engine's observe/warn/cap + threshold model), **Mission Profiles** (`mission_profiles` CRUD, clone-from-built-in-playbook), **Team** (`users` + role assignment), **Engine** (pinned OpenMontage version currently deployed, upgrade action).

---

## 4. The filesystem bridge (concrete)

Each `run` gets an ephemeral engine container with a shared volume mounted at the same path OpenMontage already uses: `projects/<project-name>/`. A sidecar process (reused logic from `backlot/`, since Backlot already implements exactly this file-derivation pattern for the local single-user case) watches:

```
projects/<name>/
├── checkpoints/*.json        → mirrored into stage_checkpoints
├── decision_log.json         → mirrored into decision_log (flattened)
├── cost_tracking.json        → mirrored into budget_ledger
├── research/                 → assets (stage='research')
├── script/                   → assets (stage='script')
├── scenes/                   → assets (stage='scene_plan' / 'assets')
├── renders/final.mp4         → assets (stage='compose', type='render')
└── pending_decision.json     → written by the Driver's permission hook, read by supervisor graph
```

On new/changed file: sidecar POSTs a diff to `mission-control-api`, which validates against `schemas/*.json` (the engine's own schemas — no parallel schema maintained), writes the mirror row, and pushes a WebSocket event to any open Command Deck for that run.

---

## 5. Scoped regeneration — mapping to the engine's actual gate contract

The engine enforces the `assets` gate as a single pass/fail decision (per the governance model: "generated assets ... pause for your sign-off"). Mission Control's per-scene lock/regenerate (§3.3) is implemented as a **scoped resume instruction** passed back through `pending_decision.json`:

```json
{
  "gate_type": "assets",
  "decision": "revise",
  "scope": {
    "locked_scene_ids": ["scene_1", "scene_2"],
    "regenerate_scene_ids": ["scene_3", "scene_4"],
    "provider_override": { "scene_4": "kling" }
  }
}
```

The Driver reads this on resume and re-executes only the listed scenes — this is expressible entirely within the engine's existing tool-calling contract (call the video/image gen tool again for specific scene IDs), no engine modification required, just a richer payload than a plain approve/reject.

---

## 6. API surface (FastAPI, `mission-control-api`)

```
POST   /projects                          create (Launch Console submit)
GET    /projects                          Fleet View list, filterable
GET    /projects/:id                      Mission Archive detail
POST   /projects/:id/remix                fork with parent_project_id set

POST   /runs/:id/resume                   respond to a pending gate (approve/revise/reject + scope)
GET    /runs/:id/checkpoints              Command Deck stage history
WS     /runs/:id/stream                   live decision log + cost + stage updates

GET    /ground-systems/credentials        list (values redacted)
POST   /ground-systems/credentials        upsert + test-connection
GET    /ground-systems/budget
PUT    /ground-systems/budget
GET    /mission-profiles
POST   /mission-profiles                  save current project params as template
```

---

## 7. Deployment — grounded in the actual repo's own setup path

The engine image is built directly from the repo's own documented install path, so the Dockerfile is close to a literal translation of `make setup`:

```dockerfile
FROM python:3.10-slim AS base
RUN apt-get update && apt-get install -y nodejs npm ffmpeg git
WORKDIR /app
COPY openmontage-src/ .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pytest
RUN cd remotion-composer && npm install
COPY engine/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
# GPU variant (optional): RUN pip install -r requirements-gpu.txt, set VIDEO_GEN_LOCAL_ENABLED=true
```

Pin the image to a specific commit/tag at build time — this tag is what `runs.engine_version` records, and what the Ground Systems "Engine" tab shows as the current deployed version, with an explicit upgrade action rather than silent drift.

Coolify stack (unchanged from the prior architecture doc, restated with the corrected container list):

| Container | Role |
|---|---|
| `mission-control-web` | Next.js frontend — all screens in §3 |
| `mission-control-api` | FastAPI — API surface (§6) + supervisor graph host |
| `postgres` | schema in §2 |
| `redis` | supervisor graph pub/sub, sidecar diff queue |
| `minio` | archived assets on project completion |
| `openmontage-engine:{pinned-tag}` | spun up per active run, torn down on archive/anomaly-resolved |

---

## 8. Build checklist

1. Pin an OpenMontage commit, build and publish the engine image, confirm `make test-contracts` passes inside it unmodified.
2. Implement the sidecar (fork Backlot's file-derivation logic — it already solves this exact problem for the single-user case).
3. Build the Driver: headless agent invocation via OpenRouter (OpenAI SDK) + permission hook writing/reading `pending_decision.json` + per-stage model routing (default IDs: `anthropic/claude-haiku-4.5`, `anthropic/claude-sonnet-4.5`, `openai/gpt-4o`).
4. Stand up the supervisor graph (provision → await → surface → resume → archive) against a single pipeline first (Animated Explainer — zero-API-key path, fastest to validate end to end).
5. Build Fleet View + Launch Console (Guided only) + Command Deck against that one pipeline.
6. Add remaining 11 pipelines (manifest-driven — Launch Console picker should need no new code per pipeline, only new tiles).
7. Add Studio mode, Mission Archive, Ground Systems, Mission Profiles, Team roles.
8. Package the Coolify one-click template.
