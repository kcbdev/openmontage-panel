# Phase 0 — Foundation & Validation
### Detailed Implementation Guide

**Duration guide:** this phase is a spike, not a build — timebox it. If the headless Driver spike doesn't work within a reasonable timebox, stop and reassess the architecture before spending more time.

---

## 0.1 License review

**Task:** Determine AGPL-3.0 exposure for the self-hosted-first model.

**Steps:**
1. Read `LICENSE` in the OpenMontage repo verbatim (GNU AGPLv3).
2. Confirm the specific posture: Mission Control never modifies engine source, ships as a *separate* application that supervises a pinned, unmodified container image of the engine. Each customer runs their own instance — you are not operating a network service against a modified copy of the AGPL code on their behalf.
3. Get this confirmed by a lawyer or, at minimum, a direct written exchange with the maintainer (`calesthio`) about intended commercial use — GitHub Discussions or direct contact per the repo's contact section.
4. Document the conclusion in a short internal memo (`docs/legal/agpl-posture.md`) before Phase 7 packaging begins — this is a hard gate on public launch messaging, not on internal development.

**Deliverable:** one-page internal memo, sign-off before Phase 7.

---

## 0.2 Pin engine version & build image

**Steps:**
```bash
git clone https://github.com/calesthio/OpenMontage.git
cd OpenMontage
git rev-parse HEAD > ../ENGINE_PINNED_COMMIT.txt
git tag mission-control-v0-pin
```

**Dockerfile** (`engine/Dockerfile`):
```dockerfile
FROM node:18-bullseye AS base
RUN apt-get update && apt-get install -y python3.10 python3-pip python3-venv ffmpeg git

WORKDIR /app
COPY . .

RUN python3 -m pip install -r requirements.txt
RUN python3 -m pip install piper-tts
RUN cd remotion-composer && npm install

# Mission Control adds nothing here except an entrypoint script —
# no engine files are modified.
COPY engine/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

**Validation:**
```bash
docker build -t openmontage-engine:mc-v0 -f engine/Dockerfile .
docker run --rm openmontage-engine:mc-v0 make test-contracts
```

**Exit check:** contract tests pass inside the container, unmodified, with zero code changes to the cloned repo.

---

## 0.3 Headless Driver spike

This is the highest-risk item in the entire plan — build it in isolation, outside any product code.

**Goal:** prove a headless agent session can:
1. Read `AGENT_GUIDE.md` and `pipeline_defs/animated-explainer.yaml`
2. Execute the `research` stage using real tool calls
3. Detect and pause cleanly at the `proposal` gate
4. Resume from a written decision file, continue to `script`, pause again

**Spike script** (`spike/headless_driver.py`, run inside the engine container):
```python
"""
Phase 0 spike — not production code. Proves the Driver contract works
before any of Phase 1's supervisor graph is built.
"""
import json, os, time
from pathlib import Path
from openai import OpenAI

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_KEY = os.environ["OPENROUTER_API_KEY"]

PROJECT_DIR = Path("projects/spike-run-1")
PENDING_DECISION = PROJECT_DIR / "pending_decision.json"

# Per-stage model defaults — overridable per project via studio_params
MODEL_ROUTING = {
    "research":    "anthropic/claude-3.5-haiku",
    "proposal":    "anthropic/claude-sonnet-4",
    "script":      "anthropic/claude-sonnet-4",
    "scene_plan":  "openai/gpt-4o",
    "assets":      "openai/gpt-4o",
    "edit":        "anthropic/claude-3.5-haiku",
}

def run_stage_headless(
    stage_prompt: str,
    tool_definitions: list,
    stage: str = "research",
    model_override: str | None = None,
):
    """
    Invokes the agent via OpenRouter with tool-calling bound to
    tools/tool_registry — same contract as a human's agent session
    would have, but headless. Permission hook intercepts gated calls.
    """
    model = model_override or MODEL_ROUTING.get(stage, "anthropic/claude-sonnet-4")
    client = OpenAI(
        base_url=OPENROUTER_BASE,
        api_key=OPENROUTER_KEY,
        default_headers={
            "HTTP-Referer": "https://mission-control.local",
            "X-Title": "Mission Control Driver",
        },
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": stage_prompt},
        ],
        tools=tool_definitions,
    )
    # system prompt = contents of AGENT_GUIDE.md + the relevant
    # skills/pipelines/animated-explainer/<stage>.md file, read verbatim
    ...

def permission_hook(tool_call):
    if tool_call.name in GATED_ACTIONS:
        PENDING_DECISION.write_text(json.dumps({
            "gate_type": tool_call.gate_type,
            "payload": tool_call.payload,
            "model_used": tool_call.model,  # record which model generated this
            "created_at": time.time(),
        }))
        # block here — poll for a decision file, or raise/pause
        return wait_for_decision()
    return ALLOW

def wait_for_decision(timeout=3600):
    while not (PROJECT_DIR / "decision_response.json").exists():
        time.sleep(2)
    resp = json.loads((PROJECT_DIR / "decision_response.json").read_text())
    (PROJECT_DIR / "decision_response.json").unlink()
    return resp
```

**Manual test procedure:**
1. Start the spike script inside the running engine container.
2. Confirm `pending_decision.json` appears after the `proposal` stage completes, with a sensible payload (proposal text/summary).
3. From *outside* the container, write `decision_response.json` with `{"decision": "approve"}`.
4. Confirm the script resumes and proceeds to `script`, pausing again correctly.
5. Repeat through all 5 gates to a finished render in `projects/spike-run-1/renders/final.mp4`.

**Exit criteria:** one full run, zero human typing into a terminal, gate payloads are legible enough that a UI could render them directly, and resume works reliably across all 5 gate types (proposal, script, scene_plan, assets, publish).

**If this fails:** document exactly where — e.g. if the OpenRouter/OpenAI SDK's tool-calling doesn't cleanly support external blocking/resume, the fallback is to run the Driver as a fully separate process per stage (spawn, wait for checkpoint file, kill, respawn for next stage with checkpoint as context) rather than one long-lived session with an in-process pause. This is uglier but still viable — note it as Plan B before starting Phase 1.

---

## 0.4 Filesystem bridge spike

**Steps:**
1. Read `backlot/README.md` and the checkpoint writer in `lib/` end to end.
2. Run `python -m backlot open` against the spike run from §0.3, confirm Backlot's board correctly renders the run's state from files alone.
3. Extract Backlot's file-derivation logic (whatever module reads `checkpoints/*.json` and `decision_log.json` into board state) into a standalone function you can call from a sidecar process outside Backlot itself.
4. Confirm it works against the spike run without any modification.

**Exit criteria:** a small standalone script, forked from Backlot's own logic, that can read `projects/spike-run-1/` and print structured JSON matching the `stage_checkpoints` schema in the implementation guide — proving the "mirror, don't reimplement" approach is real, not aspirational.

---

## Phase 0 sign-off checklist

- [ ] AGPL posture memo written and reviewed
- [ ] Engine image builds and passes `make test-contracts` unmodified
- [ ] Headless Driver completes one full 5-gate run with no human intervention beyond writing decision files
- [ ] Filesystem bridge extraction confirmed working against real spike-run output
- [ ] Plan B documented if the Driver spike required a workaround

Do not start Phase 1 until every box above is checked.
