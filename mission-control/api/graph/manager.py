import logging
import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.session import async_session
from api.graph.graph import SupervisorState, build_supervisor_graph
from api.models import ApprovalGate, Asset, Project, ProviderCredential, Run, StageCheckpoint, Tenant
from api.notifications import notify_anomaly, notify_done, notify_gate_created, notify_gate_resolved
from api.routers.ws import anomaly_event, checkpoint_event, done_event, gate_event, publish_run_event, state_update

logger = logging.getLogger(__name__)

_instances: dict[str, "RunInstance"] = {}


class RunInstance:
    def __init__(self, run_id: str, initial_state: SupervisorState):
        self.run_id = run_id
        self.state = initial_state
        self.graph = build_supervisor_graph()
        self._pending_node: str | None = None

    async def step(self):
        async for event in self.graph.astream(self.state):
            for node_name, output in event.items():
                self.state.update(output)
                self._pending_node = node_name
            break

        if self.state.get("status") == "awaiting_approval":
            await self._persist_gate()

        await self._persist_state()

    async def resume(self, decision: str, revision_notes: str | None = None, scope: dict | None = None):
        self.state["decision"] = decision
        self.state["revision_notes"] = revision_notes
        self.state["scope"] = scope
        if decision == "approve":
            await self._resolve_gate("approved", revision_notes)
            await self.step()
        elif decision == "revise":
            await self._resolve_gate("revision_requested", revision_notes)
            self.state["decision"] = "approve"
            self.state["revision_notes"] = revision_notes
            await self.step()
        elif decision == "reject":
            await self._resolve_gate("rejected", revision_notes)
            self.state["status"] = "done"
            await self._persist_state()

    async def _persist_state(self):
        async with async_session() as db:
            result = await db.execute(select(Run).where(Run.id == self.run_id))
            run = result.scalar_one_or_none()
            if not run:
                return

            run.status = self.state.get("status", run.status)
            run.current_stage = self.state.get("current_stage", run.current_stage)
            if self.state.get("status") == "done":
                run.finished_at = datetime.now(timezone.utc)
            if self.state.get("status") == "anomaly":
                err = self.state.get("error")
                if err:
                    run.anomaly_reason = err
            if self.state.get("engine_container_id"):
                run.engine_container_id = self.state["engine_container_id"]

            # Mirror filesystem checkpoint into DB
            cp = self.state.get("last_checkpoint")
            if cp and cp.get("stage"):
                existing = await db.execute(
                    select(StageCheckpoint)
                    .where(StageCheckpoint.run_id == self.run_id)
                    .where(StageCheckpoint.stage == cp["stage"])
                )
                checkpoint_created = False
                if not existing.scalar_one_or_none():
                    db.add(StageCheckpoint(
                        run_id=self.run_id,
                        stage=cp["stage"],
                        checkpoint_json=cp,
                        cost_snapshot_json=cp.get("cost_snapshot"),
                    ))
                    checkpoint_created = True

                # Count total checkpoints for this run
                count_result = await db.execute(
                    select(StageCheckpoint.id).where(StageCheckpoint.run_id == self.run_id)
                )
                stage_count = len(count_result.scalars().all())

                artifacts = cp.get("artifacts", [])

                if checkpoint_created:
                    try:
                        await publish_run_event(self.run_id, checkpoint_event(
                            self.run_id, cp["stage"],
                            has_artifacts=bool(artifacts),
                            stage_count=stage_count,
                        ))
                    except Exception:
                        pass

            # Mirror scene artifacts from checkpoints into Asset table
            artifacts = cp.get("artifacts", []) if cp else []
            for a in artifacts:
                existing_asset = await db.execute(
                    select(Asset).where(
                        Asset.run_id == self.run_id,
                        Asset.storage_path == a.get("thumbnail_url"),
                    )
                )
                if not existing_asset.scalar_one_or_none():
                    db.add(Asset(
                        run_id=self.run_id,
                        stage=cp["stage"],
                        type="scene",
                        storage_path=a.get("thumbnail_url"),
                        provider_used=a.get("provider_used"),
                        cost=a.get("cost", 0),
                        is_locked=a.get("is_locked", False),
                    ))

            await db.commit()

            # Publish live event for WebSocket consumers
            try:
                if self.state.get("status") == "anomaly":
                    evt = anomaly_event(self.run_id, run.anomaly_reason or "unknown",
                                        run.current_stage)
                    await notify_anomaly(self.run_id, run.anomaly_reason or "unknown",
                                         run.current_stage)
                elif self.state.get("status") == "done":
                    evt = done_event(self.run_id,
                                     run.finished_at.isoformat() if run.finished_at else None)
                    await notify_done(self.run_id,
                                      run.finished_at.isoformat() if run.finished_at else None)
                else:
                    evt = state_update(self.run_id, run.status, run.current_stage,
                                       anomaly_reason=run.anomaly_reason,
                                       stage=cp.get("stage") if cp else None)
                await publish_run_event(self.run_id, evt)
            except Exception:
                pass

    async def _persist_gate(self):
        gate = self.state.get("pending_gate")
        if not gate:
            return
        async with async_session() as db:
            existing = await db.execute(
                select(ApprovalGate)
                .where(ApprovalGate.run_id == self.run_id)
                .where(ApprovalGate.stage == gate.get("stage"))
                .where(ApprovalGate.status == "pending")
            )
            if not existing.scalar_one_or_none():
                gate_type = gate.get("gate_type", "approval")
                db.add(ApprovalGate(
                    run_id=self.run_id,
                    stage=gate.get("stage", "?"),
                    gate_type=gate_type,
                    payload_json=gate,
                ))
                await db.commit()

                # Set required_role from tenant config
                tenant_cfg = await db.execute(
                    select(Tenant.gate_role_requirements)
                    .join(Project, Tenant.id == Project.tenant_id)
                    .join(Run, Project.id == Run.project_id)
                    .where(Run.id == self.run_id)
                )
                role_reqs = tenant_cfg.scalar_one_or_none()
                req_role = "owner"
                if role_reqs:
                    req_role = role_reqs.get(gate_type, "owner")
                    gate_row = await db.execute(
                        select(ApprovalGate)
                        .where(ApprovalGate.run_id == self.run_id)
                        .where(ApprovalGate.stage == gate.get("stage"))
                        .where(ApprovalGate.status == "pending")
                    )
                    g = gate_row.scalar_one_or_none()
                    if g:
                        g.required_role = req_role
                        await db.commit()

                try:
                    await publish_run_event(self.run_id, gate_event(
                        self.run_id, gate.get("stage", "?"), gate_type,
                        "created", required_role=req_role,
                    ))
                except Exception:
                    pass

                try:
                    await notify_gate_created(self.run_id, gate.get("stage", "?"), gate_type, req_role)
                except Exception:
                    pass

    async def _resolve_gate(self, status: str, notes: str | None):
        async with async_session() as db:
            result = await db.execute(
                select(ApprovalGate)
                .where(ApprovalGate.run_id == self.run_id)
                .where(ApprovalGate.status == "pending")
                .order_by(ApprovalGate.created_at.desc())
                .limit(1)
            )
            gate = result.scalar_one_or_none()
            if gate:
                gate.status = status
                gate.revision_notes = notes
                gate.resolved_at = datetime.now(timezone.utc)
                await db.commit()

                try:
                    await publish_run_event(self.run_id, gate_event(
                        self.run_id, gate.stage, gate.gate_type,
                        status, required_role=gate.required_role,
                    ))
                except Exception:
                    pass

                try:
                    await notify_gate_resolved(self.run_id, gate.stage, status)
                except Exception:
                    pass

    @property
    def last_node(self) -> str | None:
        return self._pending_node


class GraphManager:
    async def _load_credentials(self, db: AsyncSession, tenant_id: str) -> dict[str, str]:
        result = await db.execute(
            select(ProviderCredential).where(ProviderCredential.tenant_id == tenant_id)
        )
        creds: dict[str, str] = {}
        for c in result.scalars().all():
            try:
                from api.routers.credentials import _decrypt
                creds[c.provider_key] = _decrypt(c.encrypted_value)
            except Exception:
                continue
        return creds

    async def start_run(self, db: AsyncSession, project: Project, run: Run):
        credentials = await self._load_credentials(db, str(project.tenant_id))
        state: SupervisorState = {
            "project_id": str(project.id),
            "run_id": str(run.id),
            "project_dir": os.environ.get("PROJECTS_DIR", "/data/projects") + f"/{run.id}",
            "project_name": project.name,
            "pipeline_type": project.pipeline_type,
            "engine_container_id": None,
            "current_stage": None,
            "last_checkpoint": None,
            "pending_gate": None,
            "decision": None,
            "revision_notes": None,
            "scope": None,
            "studio_params": run.studio_params,
            "credentials": credentials,
            "status": "provisioning",
            "error": None,
        }

        instance = RunInstance(str(run.id), state)
        _instances[str(run.id)] = instance
        await instance.step()

    async def resume_run(
        self, db: AsyncSession, run: Run,
        decision: str,
        revision_notes: str | None = None,
        scope: dict | None = None,
    ):
        instance = _instances.get(str(run.id))
        if not instance:
            project_result = await db.execute(select(Project).where(Project.id == run.project_id))
            project = project_result.scalar_one_or_none()
            creds = await self._load_credentials(db, str(project.tenant_id)) if project else {}
            state: SupervisorState = {
                "project_id": str(run.project_id),
                "run_id": str(run.id),
                "project_dir": os.environ.get("PROJECTS_DIR", "/data/projects") + f"/{run.id}",
                "project_name": project.name if project else "",
                "pipeline_type": project.pipeline_type if project else "",
                "engine_container_id": run.engine_container_id,
                "current_stage": run.current_stage,
                "last_checkpoint": None,
                "pending_gate": None,
                "decision": None,
                "revision_notes": None,
                "scope": None,
                "studio_params": run.studio_params,
                "credentials": creds,
                "status": run.status,
                "error": None,
            }
            instance = RunInstance(str(run.id), state)
            _instances[str(run.id)] = instance

        await instance.resume(decision, revision_notes, scope)
