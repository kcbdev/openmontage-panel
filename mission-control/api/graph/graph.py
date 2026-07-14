import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

PROJECTS_DIR = os.environ.get("PROJECTS_DIR", "/data/projects")
ENGINE_IMAGE = os.environ.get("ENGINE_IMAGE", "openmontage-engine:mc-v0")


class SupervisorState(TypedDict):
    project_id: str
    run_id: str
    project_dir: str
    project_name: str
    pipeline_type: str
    engine_container_id: str | None
    current_stage: str | None
    last_checkpoint: dict[str, Any] | None
    pending_gate: dict[str, Any] | None
    decision: str | None
    revision_notes: str | None
    scope: dict | None
    studio_params: dict | None
    credentials: dict[str, str] | None
    status: str
    error: str | None


def _project_dir(state: SupervisorState) -> Path:
    return Path(state["project_dir"])


# ---- nodes ----


async def provision(state: SupervisorState) -> dict[str, Any]:
    pdir = _project_dir(state)
    pdir.mkdir(parents=True, exist_ok=True)

    # Write a minimal pipeline.json so the engine knows what to do
    pipeline = {
        "pipeline_type": state["pipeline_type"],
        "stages": [
            {"name": "research", "gated": False},
            {"name": "proposal", "gated": True},
            {"name": "script", "gated": True},
            {"name": "storyboard", "gated": False},
            {"name": "scene_plan", "gated": True},
            {"name": "assets", "gated": True},
            {"name": "edit", "gated": False},
            {"name": "publish", "gated": True},
        ],
    }
    (pdir / "pipeline.json").write_text(json.dumps(pipeline, indent=2))

    # Stub mode — no real engine; stub-driver sidecar picks up pipeline.json
    if os.environ.get("STUB_DRIVER") == "true":
        logger.info("stub mode — pipeline.json written, sidecar will simulate")
        return {"engine_container_id": "stub", "status": "awaiting_checkpoint"}

    # Run the engine container
    try:
        cmd = [
            "docker", "run", "-d",
            "--name", f"om-engine-{state['run_id'][:8]}",
            "-v", f"{pdir}:/data/project:rw",
            "-e", "PROJECT_DIR=/data/project",
        ]
        sp = state.get("studio_params") or {}
        if sp.get("providers"):
            cmd += ["-e", f"FORCED_PROVIDERS={json.dumps(sp['providers'])}"]
        if sp.get("model_routing"):
            cmd += ["-e", f"MODEL_ROUTING={json.dumps(sp['model_routing'])}"]
        creds = state.get("credentials") or {}
        for k, v in creds.items():
            cmd += ["-e", f"{k}={v}"]
        cmd.append(ENGINE_IMAGE)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        container_id = result.stdout.strip()
        logger.info("engine container started: %s", container_id)

        # Verify container stays running
        import time
        time.sleep(3)
        inspect = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Status}}", container_id],
            capture_output=True, text=True, timeout=10,
        )
        status = inspect.stdout.strip()
        if status != "running":
            logger.error("engine container exited immediately (status=%s)", status)
            subprocess.run(["docker", "rm", "-f", container_id], capture_output=True, timeout=10)
            return {
                "status": "error",
                "error": f"engine container exited (status={status})",
                "engine_container_id": None,
            }
    except Exception as e:
        logger.error("failed to start engine: %s", e)
        return {"status": "error", "error": str(e), "engine_container_id": None}

    return {"engine_container_id": container_id, "status": "awaiting_checkpoint"}


async def await_checkpoint(state: SupervisorState) -> dict[str, Any]:
    pdir = _project_dir(state)
    timeout = 120
    poll = 2 if os.environ.get("STUB_SPEED") == "fast" else 5

    for _ in range(timeout // poll):
        gate_path = pdir / "pending_decision.json"
        if gate_path.exists():
            try:
                gate_data = json.loads(gate_path.read_text())
                return {
                    "current_stage": gate_data.get("stage"),
                    "pending_gate": gate_data,
                    "status": "awaiting_approval",
                }
            except Exception:
                pass

        cps = sorted(pdir.glob("checkpoint_*.json"))
        if cps:
            last = cps[-1]
            try:
                cp_data = json.loads(last.read_text())
                if cp_data.get("error"):
                    return {
                        "status": "anomaly",
                        "error": cp_data["error"],
                        "error_detail": cp_data.get("error_detail"),
                    }
                return {
                    "current_stage": cp_data.get("stage"),
                    "last_checkpoint": cp_data,
                    "status": "awaiting_checkpoint",
                }
            except Exception:
                pass

        time.sleep(poll)

    return {"status": "anomaly", "error": "driver stalled — no checkpoint or gate within timeout"}


async def surface_decision(state: SupervisorState) -> dict[str, Any]:
    logger.info("gate paused for run %s stage %s", state["run_id"], state["current_stage"])
    return {"status": "awaiting_approval"}


async def resume_driver(state: SupervisorState) -> dict[str, Any]:
    pdir = _project_dir(state)
    decision_path = pdir / "decision_response.json"
    decision: dict[str, Any] = {
        "decision": state.get("decision", "approve"),
        "revision_notes": state.get("revision_notes"),
    }
    scope = state.get("scope")
    if scope:
        decision["scope"] = scope
    decision_path.write_text(json.dumps(decision, indent=2))

    gate_path = pdir / "pending_decision.json"
    if gate_path.exists():
        gate_path.unlink()

    logger.info("decision written for run %s: %s", state["run_id"], decision["decision"])
    return {"pending_gate": None, "status": "awaiting_checkpoint"}


async def archive(state: SupervisorState) -> dict[str, Any]:
    cid = state.get("engine_container_id")
    if cid and cid != "stub":
        try:
            subprocess.run(["docker", "stop", cid], capture_output=True, timeout=15)
            subprocess.run(["docker", "rm", cid], capture_output=True, timeout=15)
            logger.info("engine container %s stopped and removed", cid)
        except Exception as e:
            logger.warning("failed to clean up container %s: %s", cid, e)

    return {"status": "done", "engine_container_id": None}


# ---- routing ----

def route_after_provision(state: SupervisorState) -> Literal["await_checkpoint", "__error__"]:
    if state.get("status") == "error":
        return "__error__"
    return "await_checkpoint"


def route_after_checkpoint(
    state: SupervisorState,
) -> Literal["surface_decision", "await_checkpoint", "archive", "anomaly"]:
    if state.get("status") == "anomaly":
        return "anomaly"
    if state.get("status") == "awaiting_approval":
        return "surface_decision"
    if state.get("last_checkpoint") and state["last_checkpoint"].get("stage") == "publish":
        return "archive"
    return "await_checkpoint"


def route_after_resume(state: SupervisorState) -> Literal["await_checkpoint", "archive"]:
    if state.get("status") == "done":
        return "archive"
    return "await_checkpoint"


# ---- build graph ----

def build_supervisor_graph() -> StateGraph:
    builder = StateGraph(SupervisorState)

    builder.add_node("provision", provision)
    builder.add_node("await_checkpoint", await_checkpoint)
    builder.add_node("surface_decision", surface_decision)
    builder.add_node("resume_driver", resume_driver)
    builder.add_node("archive", archive)

    builder.add_edge(START, "provision")
    builder.add_conditional_edges(
        "provision", route_after_provision,
        {"await_checkpoint": "await_checkpoint", "__error__": END},
    )
    builder.add_conditional_edges("await_checkpoint", route_after_checkpoint, {
        "surface_decision": "surface_decision",
        "await_checkpoint": "await_checkpoint",
        "archive": "archive",
        "anomaly": END,
    })
    builder.add_edge("surface_decision", "resume_driver")
    builder.add_conditional_edges("resume_driver", route_after_resume, {
        "await_checkpoint": "await_checkpoint",
        "archive": "archive",
    })
    builder.add_edge("archive", END)

    graph = builder.compile()
    graph.name = "supervisor"
    return graph
