# Phase 1 — Supervisor Graph & Single-Project Backend
### Detailed Implementation Guide

**Prerequisite:** Phase 0 sign-off complete, Plan B documented if needed.

---

## 1.1 Repository structure

```
mission-control/
├── api/                        # FastAPI service
│   ├── main.py
│   ├── models/                 # SQLAlchemy models, 1:1 with schema doc §2
│   ├── routers/
│   │   ├── projects.py
│   │   └── runs.py
│   ├── graph/                  # LangGraph supervisor
│   │   ├── supervisor.py
│   │   └── nodes.py
│   ├── bridge/                 # filesystem mirror sidecar
│   │   └── watcher.py
│   └── db/
│       ├── session.py
│       └── migrations/         # Alembic
├── engine/                     # from Phase 0
│   └── Dockerfile
└── docker-compose.dev.yml
```

---

## 1.2 Database — Alembic migration for Phase 1 subset

Implement only the tables needed now (full schema from the implementation guide, Phase-1 subset):

```python
# api/models/core.py
import uuid
from sqlalchemy import Column, String, DateTime, Numeric, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    name = Column(String)
    budget_cap_default = Column(Numeric, default=10.00)
    budget_mode_default = Column(String, default="warn")

class Project(Base):
    __tablename__ = "projects"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))
    name = Column(String)
    pipeline_type = Column(String)
    status = Column(String, default="draft")
    render_runtime = Column(String, nullable=True)
    style_playbook = Column(String, nullable=True)
    platform_profile = Column(String, nullable=True)
    duration_target_seconds = Column(String, nullable=True)

class Run(Base):
    __tablename__ = "runs"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID, ForeignKey("projects.id"))
    engine_container_id = Column(String, nullable=True)
    engine_version = Column(String)
    status = Column(String, default="provisioning")
    current_stage = Column(String, nullable=True)

class StageCheckpoint(Base):
    __tablename__ = "stage_checkpoints"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID, ForeignKey("runs.id"))
    stage = Column(String)
    checkpoint_json = Column(JSON)
    decision_log_json = Column(JSON, nullable=True)
    cost_snapshot_json = Column(JSON, nullable=True)

class ApprovalGate(Base):
    __tablename__ = "approval_gates"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID, ForeignKey("runs.id"))
    stage = Column(String)
    gate_type = Column(String)
    payload_json = Column(JSON)
    status = Column(String, default="pending")
    revision_notes = Column(String, nullable=True)

class Asset(Base):
    __tablename__ = "assets"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID, ForeignKey("runs.id"))
    stage = Column(String)
    type = Column(String)
    storage_path = Column(String, nullable=True)
    provider_used = Column(String, nullable=True)
    cost = Column(Numeric, nullable=True)
    is_locked = Column(Boolean, default=False)

class BudgetLedger(Base):
    __tablename__ = "budget_ledger"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))
    project_id = Column(UUID, ForeignKey("projects.id"))
    run_id = Column(UUID, ForeignKey("runs.id"))
    estimated_cost = Column(Numeric, nullable=True)
    actual_cost = Column(Numeric, nullable=True)
    mode = Column(String)
```

```bash
alembic revision --autogenerate -m "phase1 core tables"
alembic upgrade head
```

---

## 1.3 Supervisor graph (LangGraph)

```python
# api/graph/supervisor.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from typing import TypedDict, Optional

class SupervisorState(TypedDict):
    run_id: str
    project_id: str
    pipeline_type: str
    container_id: Optional[str]
    current_stage: Optional[str]
    pending_gate: Optional[dict]
    status: str

def provision(state: SupervisorState) -> SupervisorState:
    container_id = spawn_engine_container(
        pipeline_type=state["pipeline_type"],
        run_id=state["run_id"],
    )
    return {**state, "container_id": container_id, "status": "running"}

def await_checkpoint(state: SupervisorState) -> SupervisorState:
    # polls the shared volume via the bridge (§1.4) — blocks until
    # a new checkpoint or pending_decision.json appears
    event = wait_for_next_event(state["container_id"])
    if event["type"] == "pending_decision":
        return {**state, "pending_gate": event["payload"], "status": "paused_decision"}
    return {**state, "current_stage": event["stage"], "status": "running"}

def surface_decision(state: SupervisorState) -> SupervisorState:
    write_approval_gate_row(state["run_id"], state["pending_gate"])
    return state  # graph interrupts here — see resume_driver

def resume_driver(state: SupervisorState) -> SupervisorState:
    decision = read_latest_gate_response(state["run_id"])
    write_decision_response_file(state["container_id"], decision)
    return {**state, "pending_gate": None, "status": "running"}

def archive(state: SupervisorState) -> SupervisorState:
    move_assets_to_object_storage(state["run_id"])
    teardown_container(state["container_id"])
    return {**state, "status": "done"}

def route(state: SupervisorState) -> str:
    if state["status"] == "paused_decision":
        return "surface_decision"
    if state["current_stage"] == "compose" and state["status"] == "done":
        return "archive"
    return "await_checkpoint"

graph = StateGraph(SupervisorState)
graph.add_node("provision", provision)
graph.add_node("await_checkpoint", await_checkpoint)
graph.add_node("surface_decision", surface_decision)
graph.add_node("resume_driver", resume_driver)
graph.add_node("archive", archive)

graph.set_entry_point("provision")
graph.add_edge("provision", "await_checkpoint")
graph.add_conditional_edges("await_checkpoint", route, {
    "surface_decision": "surface_decision",
    "await_checkpoint": "await_checkpoint",
    "archive": "archive",
})
graph.add_edge("archive", END)

checkpointer = PostgresSaver.from_conn_string(DB_URL)
compiled = graph.compile(checkpointer=checkpointer, interrupt_after=["surface_decision"])
```

The `interrupt_after=["surface_decision"]` is the mechanism that pauses the graph until `resume_driver` is explicitly invoked from the `/runs/:id/resume` API endpoint — this is the direct implementation of the human-in-loop contract from the architecture doc.

---

## 1.4 Filesystem bridge / sidecar

```python
# api/bridge/watcher.py
import time, json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ProjectFileHandler(FileSystemEventHandler):
    def __init__(self, run_id, api_client):
        self.run_id = run_id
        self.api_client = api_client

    def on_created(self, event):
        path = Path(event.src_path)
        if path.name == "pending_decision.json":
            payload = json.loads(path.read_text())
            self.api_client.notify_pending_decision(self.run_id, payload)
        elif path.match("checkpoints/*.json"):
            payload = json.loads(path.read_text())
            self.api_client.mirror_checkpoint(self.run_id, payload)

def watch_run(run_id: str, project_dir: str, api_client):
    handler = ProjectFileHandler(run_id, api_client)
    observer = Observer()
    observer.schedule(handler, project_dir, recursive=True)
    observer.start()
    return observer
```

One watcher process per active run, started in `provision()`, stopped in `archive()`. This directly forks the extraction from Phase 0 §0.4.

---

## 1.5 API surface (subset)

```python
# api/routers/runs.py
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/runs")

@router.post("/{run_id}/resume")
def resume_run(run_id: str, decision: GateDecision):
    gate = get_pending_gate(run_id)
    if not gate:
        raise HTTPException(404, "no pending gate for this run")
    write_gate_response(gate.id, decision)
    supervisor_graphs[run_id].resume_from_interrupt()
    return {"status": "resumed"}

@router.get("/{run_id}/checkpoints")
def get_checkpoints(run_id: str):
    return db.query(StageCheckpoint).filter_by(run_id=run_id).order_by(StageCheckpoint.created_at).all()
```

```python
# api/routers/projects.py
@router.post("/")
def create_project(payload: ProjectCreate):
    project = Project(**payload.dict(), tenant_id=DEFAULT_TENANT_ID)
    db.add(project); db.commit()
    run = Run(project_id=project.id, engine_version=PINNED_ENGINE_TAG)
    db.add(run); db.commit()
    supervisor_graphs[str(run.id)] = compiled.astream({
        "run_id": str(run.id), "project_id": str(project.id),
        "pipeline_type": project.pipeline_type, "status": "provisioning",
    })
    return {"project_id": project.id, "run_id": run.id}
```

---

## 1.6 Dev stack

```yaml
# docker-compose.dev.yml
services:
  postgres:
    image: postgres:16
    environment: { POSTGRES_PASSWORD: dev }
  redis:
    image: redis:7
  minio:
    image: minio/minio
    command: server /data
  mission-control-api:
    build: ./api
    depends_on: [postgres, redis, minio]
    environment:
      DB_URL: postgresql://postgres:dev@postgres/mission_control
      ENGINE_IMAGE: openmontage-engine:mc-v0
```

---

## Phase 1 acceptance test

```bash
curl -X POST localhost:8000/projects -d '{
  "pipeline_type": "animated-explainer",
  "name": "test project",
  "duration_target_seconds": 45
}'
# → { "project_id": "...", "run_id": "..." }

# poll until a gate appears
curl localhost:8000/runs/<run_id>/checkpoints

# approve the proposal gate
curl -X POST localhost:8000/runs/<run_id>/resume -d '{"decision": "approve"}'

# repeat through script, scene_plan, assets, publish
# confirm final asset lands in MinIO and runs.status == 'done'
```

**Exit criteria:** the full curl sequence above completes successfully with no manual container interaction, checkpoints visible in Postgres in real time, and a finished render archived — the exact backend proof described in the Phase 1 summary.
