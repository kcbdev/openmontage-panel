from typing import Any

STAGES = [
    "research",
    "proposal",
    "script",
    "storyboard",
    "scene_plan",
    "assets",
    "edit",
    "publish",
]


GATED_STAGES = {"proposal", "script", "scene_plan", "assets", "publish"}


def derive_board_state(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    if not checkpoints:
        return {"status": "idle", "current_stage": None, "completed": []}

    completed = []
    for cp in checkpoints:
        stage = cp.get("stage", "?")
        cost = cp.get("cost_snapshot", {})
        completed.append({
            "stage": stage,
            "status": "done",
            "cost": cost.get("total", 0),
        })

    last = checkpoints[-1]
    idx = _stage_index(last.get("stage", ""))
    next_stage = STAGES[idx + 1] if idx + 1 < len(STAGES) else None

    return {
        "status": "complete" if next_stage is None else "running",
        "current_stage": last.get("stage"),
        "next_stage": next_stage,
        "next_needs_approval": next_stage in GATED_STAGES if next_stage else False,
        "completed": completed,
    }


def _stage_index(stage: str) -> int:
    try:
        return STAGES.index(stage)
    except ValueError:
        return -1
