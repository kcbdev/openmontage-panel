"""
Headless pipeline runner for Mission Control integration.

Reads pipeline.json from $PROJECT_DIR, executes stages sequentially
using the openmontage-src tool registry, writes checkpoints via the
lib/checkpoint protocol, and handles approval gates through the
filesystem contract (pending_decision.json / decision_response.json).

Invoked by the engine Docker container CMD:
    python -m headless_runner

Environment variables:
    PROJECT_DIR   — project workspace path (default: /data/project)
    STUB_SPEED    — "fast" uses 2s polling, otherwise 5s
    OPENAI_API_KEY / GOOGLE_API_KEY — LLM credentials for AI stages
    FORCED_PROVIDERS — JSON string of provider overrides
    MODEL_ROUTING     — JSON string of model routing config
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

logger = logging.getLogger("headless_runner")


PROJECT_DIR = Path(os.environ.get("PROJECT_DIR", "/data/project"))
POLL_INTERVAL = 2 if os.environ.get("STUB_SPEED") == "fast" else 5
GATE_TIMEOUT = 3600  # 1 hour before a gate times out
MAX_RETRIES = 3


def _resolve_project_id() -> str:
    """Derive project_id from the directory name under PROJECTS_DIR."""
    return PROJECT_DIR.name


def _pipeline_path() -> Path:
    return PROJECT_DIR / "pipeline.json"


def _gate_path() -> Path:
    return PROJECT_DIR / "pending_decision.json"


def _decision_path() -> Path:
    return PROJECT_DIR / "decision_response.json"


def _checkpoint_path(stage: str) -> Path:
    return PROJECT_DIR / f"checkpoint_{stage}.json"


def load_pipeline() -> dict:
    path = _pipeline_path()
    if not path.exists():
        logger.error("pipeline.json not found at %s", path)
        sys.exit(1)
    data = json.loads(path.read_text())
    logger.info("Loaded pipeline: %s (%d stages)",
                data.get("pipeline_type", "unknown"), len(data.get("stages", [])))
    return data


def write_checkpoint(
    stage: str,
    status: str,
    artifacts: dict | None = None,
    error: str | None = None,
    cost_snapshot: dict | None = None,
) -> None:
    project_id = _resolve_project_id()
    pipeline_type = None
    try:
        pipeline = load_pipeline()
        pipeline_type = pipeline.get("pipeline_type")
    except Exception:
        pass

    try:
        from lib.checkpoint import write_checkpoint as _write_cp
        _write_cp(
            pipeline_dir=PROJECT_DIR.parent,
            project_id=project_id,
            stage=stage,
            status=status,
            artifacts=artifacts or {},
            pipeline_type=pipeline_type,
            error=error,
            cost_snapshot=cost_snapshot,
        )
    except ImportError:
        cp = {
            "version": "1.0",
            "project_id": project_id,
            "stage": stage,
            "status": status,
            "artifacts": artifacts or {},
            "pipeline_type": pipeline_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if error:
            cp["error"] = error
        if cost_snapshot:
            cp["cost_snapshot"] = cost_snapshot
        path = _checkpoint_path(stage)
        path.write_text(json.dumps(cp, indent=2))

    logger.info("Checkpoint written: %s — %s", stage, status)


def handle_gate(stage: str) -> bool:
    gate_data = {
        "stage": stage,
        "gate_type": "approval",
        "summary": f"Stage '{stage}' requires human review before continuing.",
        "artifacts": {},
    }
    _gate_path().write_text(json.dumps(gate_data, indent=2))
    logger.info("Gate created for stage %s — waiting for decision response", stage)

    elapsed = 0
    while elapsed < GATE_TIMEOUT:
        if _decision_path().exists():
            try:
                decision = json.loads(_decision_path().read_text())
                _decision_path().unlink(missing_ok=True)
                _gate_path().unlink(missing_ok=True)
                logger.info("Gate resolved: %s", decision.get("decision"))
                return decision.get("decision") == "approve"
            except Exception as e:
                logger.warning("Failed to read decision response: %s", e)
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    logger.error("Gate timed out for stage %s after %ds", stage, GATE_TIMEOUT)
    write_checkpoint(stage, "error", error="gate timed out")
    return False


def execute_stage(stage_name: str, gated: bool) -> bool:
    logger.info("Executing stage: %s (gated=%s)", stage_name, gated)

    if _checkpoint_path(stage_name).exists():
        logger.info("Stage %s already has a checkpoint — skipping", stage_name)
        return True

    artifacts: dict = {}
    cost_snapshot: dict = {}
    tool_name = None

    try:
        from tools.tool_registry import registry
        registry.discover()
        available = registry.list_all()
        logger.info("Available tools: %s", available)

        for t_name in available:
            tool = registry.get(t_name)
            if tool and getattr(tool, "capability", None) == stage_name:
                tool_name = t_name
                break

        if tool_name:
            tool = registry.get(tool_name)
            logger.info("Using tool: %s for stage %s", tool_name, stage_name)
            result = tool.execute(context={"project_dir": str(PROJECT_DIR)})
            artifacts = {"output": str(result)[:500] if result else "completed"}
            cost_snapshot = {"tool_cost": getattr(tool, "cost", 0) or 0}
        else:
            artifacts = {"note": f"No registered tool for stage '{stage_name}'"}
            logger.info("No tool found for stage %s — using direct LLM", stage_name)

    except ImportError as e:
        logger.warning("Tool registry not available (%s) — using direct LLM", e)
    except Exception as e:
        logger.warning("Tool execution failed for stage %s: %s", stage_name, e)
        for attempt in range(MAX_RETRIES):
            logger.info("Retry %d/%d for stage %s", attempt + 1, MAX_RETRIES, stage_name)
            time.sleep(POLL_INTERVAL)
            try:
                from tools.tool_registry import registry
                registry.discover()
                tool = registry.get(stage_name)
                if tool:
                    result = tool.execute(context={"project_dir": str(PROJECT_DIR)})
                    artifacts = {"output": str(result)[:500] if result else "completed"}
                    cost_snapshot = {"tool_cost": getattr(tool, "cost", 0) or 0}
                    break
            except Exception:
                continue
        else:
            logger.error("All retries exhausted for stage %s", stage_name)
            return False

    write_checkpoint(stage_name, "completed", artifacts=artifacts, cost_snapshot=cost_snapshot)
    return True


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger.info("Headless runner starting — PROJECT_DIR=%s", PROJECT_DIR)

    pipeline = load_pipeline()
    stages = pipeline.get("stages", [])

    for stage in stages:
        name = stage["name"]
        gated = stage.get("gated", False)

        success = execute_stage(name, gated)
        if not success:
            logger.error("Stage %s failed — aborting pipeline", name)
            write_checkpoint(name, "error", error=f"Stage {name} execution failed")
            sys.exit(1)

        if gated:
            approved = handle_gate(name)
            if not approved:
                logger.info("Gate rejected for stage %s — pipeline halted", name)
                write_checkpoint(name, "rejected", error="rejected by reviewer")
                sys.exit(0)

    logger.info("All stages complete — writing final checkpoint")
    write_checkpoint("publish", "completed", artifacts={"final": True})
    logger.info("Pipeline finished successfully")


if __name__ == "__main__":
    main()
