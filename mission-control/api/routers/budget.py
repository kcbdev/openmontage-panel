from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import get_current_tenant
from api.db.session import get_db
from api.models import BudgetLedger, Project, Tenant

router = APIRouter(prefix="/tenant", tags=["budget"])


class BudgetDefaults(BaseModel):
    cap: float
    mode: str
    threshold: float | None = None


class LedgerEntryBody(BaseModel):
    project_id: str
    run_id: str
    action: str
    estimated_cost: float | None = None
    actual_cost: float | None = None
    mode: str = "warn"


@router.get("/budget")
async def get_budget(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    return {
        "tenant_id": str(tenant.id),
        "cap": float(tenant.budget_cap_default) if tenant.budget_cap_default else 10.0,
        "mode": tenant.budget_mode_default or "warn",
    }


@router.put("/budget")
async def update_budget(
    payload: BudgetDefaults,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    tenant.budget_cap_default = payload.cap
    tenant.budget_mode_default = payload.mode
    await db.commit()
    return {"status": "updated"}


@router.get("/budget/ledger")
async def get_budget_ledger(
    offset: int = 0,
    limit: int = 25,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    limit = min(limit, 100)
    count_q = select(func.count()).select_from(BudgetLedger).where(
        BudgetLedger.tenant_id == tenant.id
    )
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        select(BudgetLedger)
        .where(BudgetLedger.tenant_id == tenant.id)
        .order_by(BudgetLedger.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    entries = result.scalars().all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [
            {
                "id": str(e.id),
                "project_id": str(e.project_id),
                "run_id": str(e.run_id),
                "action": e.action,
                "estimated_cost": float(e.estimated_cost) if e.estimated_cost else None,
                "actual_cost": float(e.actual_cost) if e.actual_cost else None,
                "mode": e.mode,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }


@router.get("/budget/summary")
async def get_budget_summary(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    cap = float(tenant.budget_cap_default) if tenant.budget_cap_default else 10.0

    rows = await db.execute(
        select(
            BudgetLedger.project_id,
            func.sum(BudgetLedger.actual_cost).label("total_spent"),
            func.sum(BudgetLedger.estimated_cost).label("total_reserved"),
            func.count(BudgetLedger.id.distinct()).label("entries_count"),
        )
        .where(
            BudgetLedger.tenant_id == tenant.id,
            BudgetLedger.actual_cost.isnot(None),
        )
        .group_by(BudgetLedger.project_id)
    )

    project_totals = []
    project_ids = []
    for row in rows:
        project_ids.append(row.project_id)
        project_totals.append({
            "project_id": str(row.project_id),
            "spent": float(row.total_spent) if row.total_spent else 0,
            "reserved": float(row.total_reserved) if row.total_reserved else 0,
            "entries_count": row.entries_count,
        })

    if project_ids:
        proj_rows = await db.execute(
            select(Project.id, Project.name).where(Project.id.in_(project_ids))
        )
        name_map = {str(r.id): r.name for r in proj_rows}
        for pt in project_totals:
            pt["name"] = name_map.get(pt["project_id"], "Unknown")

    total_spent = sum(p["spent"] for p in project_totals)
    total_reserved = sum(p["reserved"] for p in project_totals)

    return {
        "cap": cap,
        "total_spent": total_spent,
        "total_reserved": total_reserved,
        "remaining": cap - total_spent,
        "projects": project_totals,
    }


@router.post("/budget/ledger/sync", status_code=201)
async def sync_budget_ledger(
    body: list[LedgerEntryBody],
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    entries = []
    for b in body:
        entry = BudgetLedger(
            tenant_id=tenant.id,
            project_id=UUID(b.project_id),
            run_id=UUID(b.run_id),
            action=b.action,
            estimated_cost=b.estimated_cost,
            actual_cost=b.actual_cost,
            mode=b.mode,
        )
        db.add(entry)
        entries.append(entry)

    await db.commit()
    return {"status": "synced", "count": len(entries)}
