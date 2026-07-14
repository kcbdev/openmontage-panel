"""
Stub driver sidecar — watches for new project directories in the shared
projects volume, then simulates each run's 8-stage pipeline.

Supports scene-level data (Phase 3):
- Generates 4-8 scene artifacts at scene_plan and assets gates
- Reads scope from decision_response.json for lock/regenerate flow
- STUB_FAIL_AT env var to simulate provider crash at a specific stage
"""
import json
import os
import random
import threading
import time
import uuid
from pathlib import Path

PROJECTS_DIR = os.environ.get("PROJECTS_DIR", "/data/projects")
STUB_SPEED = os.environ.get("STUB_SPEED", "fast")
STUB_FAIL_AT = os.environ.get("STUB_FAIL_AT")

STAGES = [
    {"name": "research", "gated": False},
    {"name": "proposal", "gated": True},
    {"name": "script", "gated": True},
    {"name": "storyboard", "gated": False},
    {"name": "scene_plan", "gated": True},
    {"name": "assets", "gated": True},
    {"name": "edit", "gated": False},
    {"name": "publish", "gated": True},
]

SCENE_PROVIDERS = [
    "openai-dall-e", "midjourney", "stable-diffusion",
    "kling", "pika", "runway", "kaiber",
]

SLEEP = 2 if STUB_SPEED == "fast" else 5
_known_runs: set[str] = set()


def stage_sleep():
    time.sleep(SLEEP + random.uniform(0, 0.5))


def _generate_scene_artifacts(
    stage_name: str,
    prev_artifacts: list[dict] | None = None,
    scope: dict | None = None,
) -> list[dict]:
    locked_ids = set(scope.get("locked_scene_ids", [])) if scope else set()
    regenerate_map: dict[str, str | None] = {}
    if scope:
        for item in scope.get("regenerate_scenes", []):
            regenerate_map[item["scene_id"]] = item.get("provider_override")

    prev = prev_artifacts or []
    kept = [a for a in prev if a.get("id") in locked_ids]

    target = 8
    new_count = target - len(kept)
    new_scenes = []
    for i in range(new_count):
        sid = f"scene_{stage_name}_{uuid.uuid4().hex[:8]}"
        provider = random.choice(SCENE_PROVIDERS)
        new_scenes.append({
            "id": sid,
            "scene_number": len(kept) + i + 1,
            "stage": stage_name,
            "thumbnail_url": f"/thumbnails/{sid}.png",
            "cost": round(random.uniform(0.005, 0.05), 4),
            "provider_used": provider,
            "is_locked": False,
        })

    return kept + new_scenes


def fake_checkpoint(
    stage_name: str,
    prev_scene_artifacts: list[dict] | None = None,
    scope: dict | None = None,
) -> dict:
    if STUB_FAIL_AT and stage_name == STUB_FAIL_AT:
        return {
            "stage": stage_name,
            "summary": f"FAILED at stage: {stage_name}",
            "error": "provider_request_failed",
            "error_detail": f"Simulated provider crash at {stage_name}",
            "cost_snapshot": {
                "prompt_tokens": random.randint(100, 500),
                "completion_tokens": random.randint(50, 300),
                "total_cost": round(random.uniform(0.001, 0.05), 4),
            },
            "artifacts": [],
        }

    artifacts = []
    if stage_name in ("scene_plan", "assets"):
        artifacts = _generate_scene_artifacts(stage_name, prev_scene_artifacts, scope)

    return {
        "stage": stage_name,
        "summary": f"Stub output for stage: {stage_name}",
        "cost_snapshot": {
            "prompt_tokens": random.randint(100, 500),
            "completion_tokens": random.randint(50, 300),
            "total_cost": round(random.uniform(0.001, 0.05), 4),
        },
        "artifacts": artifacts,
    }


def wait_for_decision(pdir: Path) -> dict:
    decision_path = pdir / "decision_response.json"
    while not decision_path.exists():
        time.sleep(1)
    decision = json.loads(decision_path.read_text())
    decision_path.unlink(missing_ok=True)
    return decision


def simulate_run(pdir: Path, stages: list[dict]):
    last_scene_artifacts: list[dict] = []
    scope: dict | None = None

    for stage in stages:
        name = stage["name"]
        gated = stage.get("gated", False)

        cp = fake_checkpoint(name, last_scene_artifacts, scope)
        cp_path = pdir / f"checkpoint_{name}.json"
        cp_path.write_text(json.dumps(cp, indent=2))

        if STUB_FAIL_AT and name == STUB_FAIL_AT:
            print(f"[stub-driver] Simulated failure at stage {name} — stopping")
            return

        if name in ("scene_plan", "assets"):
            last_scene_artifacts = cp.get("artifacts", [])

        if gated:
            gate_data = {
                "stage": name,
                "type": "approval",
                "summary": cp["summary"],
                "cost_snapshot": cp["cost_snapshot"],
                "artifacts": cp.get("artifacts", []),
            }
            (pdir / "pending_decision.json").write_text(json.dumps(gate_data, indent=2))

            decision = wait_for_decision(pdir)
            if decision.get("decision") == "reject":
                return
            scope = decision.get("scope")

        stage_sleep()

    fake_asset = {
        "status": "complete",
        "output_file": "video_final.mp4",
    }
    (pdir / "final_asset.json").write_text(json.dumps(fake_asset, indent=2))


def main():
    pdir = Path(PROJECTS_DIR)
    pdir.mkdir(parents=True, exist_ok=True)

    while True:
        for child in pdir.iterdir():
            if not child.is_dir():
                continue
            run_id = child.name
            if run_id in _known_runs:
                continue
            pipeline_file = child / "pipeline.json"
            if not pipeline_file.exists():
                continue

            _known_runs.add(run_id)
            pipeline = json.loads(pipeline_file.read_text())
            stages = pipeline.get("stages", STAGES)
            t = threading.Thread(target=simulate_run, args=(child, stages), daemon=True)
            t.start()

        time.sleep(2)


if __name__ == "__main__":
    main()
