from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import get_current_tenant, require_user, role_satisfies
from api.db.session import get_db
from api.graph.manager import GraphManager
from api.models import ApprovalGate, Asset, Project, Run, StageCheckpoint, Tenant, User

router = APIRouter(prefix="/runs", tags=["runs"])


class SceneOverride(BaseModel):
    scene_id: str
    provider_override: str | None = None


class SceneScope(BaseModel):
    locked_scene_ids: list[str] = []
    regenerate_scenes: list[SceneOverride] = []


class ResumeBody(BaseModel):
    decision: str  # "approve" | "revise" | "reject"
    revision_notes: str | None = None
    scope: SceneScope | None = None


class RetryBody(BaseModel):
    provider_override: str | None = None
    rollback_to_checkpoint_id: str | None = None


@router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    body: ResumeBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(Run)
        .join(Project)
        .where(Run.id == run_id)
        .where(Project.tenant_id == tenant.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "run not found")

    # Check role gate for this run's pending gate
    gate_result = await db.execute(
        select(ApprovalGate)
        .where(ApprovalGate.run_id == run_id)
        .where(ApprovalGate.status == "pending")
        .order_by(ApprovalGate.created_at.desc())
        .limit(1)
    )
    gate = gate_result.scalar_one_or_none()
    if gate and gate.required_role:
        if not role_satisfies(user.role, gate.required_role):
            raise HTTPException(403, f"requires role {gate.required_role}")

    manager = GraphManager()
    scope_dict = body.scope.model_dump() if body.scope else None
    await manager.resume_run(db, run, body.decision, body.revision_notes, scope_dict)

    # Record who resolved the gate
    if gate and body.decision in ("approve", "revise", "reject"):
        await db.execute(
            select(ApprovalGate)
            .where(ApprovalGate.id == gate.id)
        )
        gate.resolved_by = user.id
        gate.resolved_at = datetime.now(timezone.utc)
        await db.commit()

    return {"run_id": run_id, "status": run.status, "decision": body.decision}


@router.get("/{run_id}/assets")
async def list_assets(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(Asset)
        .join(Run, Asset.run_id == Run.id)
        .join(Project, Run.project_id == Project.id)
        .where(Asset.run_id == run_id)
        .where(Project.tenant_id == tenant.id)
        .where(Asset.stage.in_(["scene_plan", "assets"]))
        .order_by(Asset.created_at)
    )
    assets = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "run_id": str(a.run_id),
            "stage": a.stage,
            "type": a.type,
            "storage_path": a.storage_path,
            "provider_used": a.provider_used,
            "cost": float(a.cost) if a.cost else None,
            "is_locked": a.is_locked,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in assets
    ]


@router.post("/{run_id}/assets/{asset_id}/lock")
async def toggle_asset_lock(
    run_id: str,
    asset_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(Asset)
        .join(Run, Asset.run_id == Run.id)
        .join(Project, Run.project_id == Project.id)
        .where(Asset.id == asset_id, Asset.run_id == run_id)
        .where(Project.tenant_id == tenant.id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise HTTPException(404, "asset not found")

    asset.is_locked = not asset.is_locked
    await db.commit()

    return {
        "id": str(asset.id),
        "is_locked": asset.is_locked,
    }


@router.post("/{run_id}/retry")
async def retry_run(
    run_id: str,
    body: RetryBody,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(Run)
        .join(Project)
        .where(Run.id == run_id)
        .where(Project.tenant_id == tenant.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "run not found")

    if run.status != "anomaly":
        raise HTTPException(400, "can only retry a run in anomaly status")

    # Build scope for retry: set provider override on all regenerate scenes
    scope_dict = None
    if body.provider_override:
        scope_dict = {
            "locked_scene_ids": [],
            "regenerate_scenes": [{"scene_id": "*", "provider_override": body.provider_override}],
        }

    # Rollback: find the last good checkpoint and reset
    if body.rollback_to_checkpoint_id:
        cp_result = await db.execute(
            select(StageCheckpoint).where(
                StageCheckpoint.id == body.rollback_to_checkpoint_id,
                StageCheckpoint.run_id == run_id,
            )
        )
        cp = cp_result.scalar_one_or_none()
        if not cp:
            raise HTTPException(404, "checkpoint not found for rollback")

    # Reset run status
    run.status = "awaiting_checkpoint"
    run.anomaly_reason = None
    await db.commit()

    manager = GraphManager()
    await manager.resume_run(db, run, "approve", None, scope_dict)

    return {"run_id": run_id, "status": run.status, "provider_override": body.provider_override}


@router.get("/{run_id}/checkpoints")
async def list_checkpoints(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(StageCheckpoint)
        .join(Run, StageCheckpoint.run_id == Run.id)
        .join(Project, Run.project_id == Project.id)
        .where(StageCheckpoint.run_id == run_id)
        .where(Project.tenant_id == tenant.id)
        .order_by(StageCheckpoint.created_at)
    )
    cps = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "stage": c.stage,
            "checkpoint": c.checkpoint_json,
            "decision_log": c.decision_log_json,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cps
    ]


@router.get("/{run_id}/state")
async def run_state(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(Run)
        .join(Project)
        .where(Run.id == run_id)
        .where(Project.tenant_id == tenant.id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "run not found")

    cp_result = await db.execute(
        select(StageCheckpoint)
        .where(StageCheckpoint.run_id == run_id)
        .order_by(StageCheckpoint.created_at)
    )
    checkpoints = cp_result.scalars().all()
    last_cp = checkpoints[-1] if checkpoints else None

    from api.bridge.state import derive_board_state
    board = derive_board_state([c.checkpoint_json for c in checkpoints])

    return {
        "run_id": run_id,
        "status": run.status,
        "current_stage": run.current_stage,
        "anomaly_reason": run.anomaly_reason,
        "last_checkpoint": {
            "stage": last_cp.stage,
            "checkpoint": last_cp.checkpoint_json,
            "cost_snapshot": last_cp.cost_snapshot_json,
        } if last_cp else None,
        "board_state": board,
    }
