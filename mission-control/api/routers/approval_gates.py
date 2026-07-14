from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import get_current_tenant
from api.db.session import get_db
from api.models import ApprovalGate, Project, Run, Tenant

router = APIRouter(prefix="/runs/{run_id}/gates", tags=["approval_gates"])


@router.get("/pending")
async def pending_gates(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    # Verify the run belongs to this tenant
    run_result = await db.execute(
        select(Run)
        .join(Project)
        .where(Run.id == run_id)
        .where(Project.tenant_id == tenant.id)
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(404, "run not found")

    result = await db.execute(
        select(ApprovalGate)
        .where(ApprovalGate.run_id == run_id)
        .where(ApprovalGate.status == "pending")
        .order_by(ApprovalGate.created_at)
    )
    gates = result.scalars().all()
    return [
        {
            "id": str(g.id),
            "stage": g.stage,
            "gate_type": g.gate_type,
            "payload": g.payload_json,
            "required_role": g.required_role,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        }
        for g in gates
    ]
