
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import get_current_tenant
from api.db.session import get_db
from api.graph.manager import GraphManager
from api.models import Project, Run, Tenant
from api.pricing import estimate as compute_estimate

router = APIRouter(prefix="/projects", tags=["projects"])


class StudioParams(BaseModel):
    render_runtime: str | None = None
    footage_mode: str | None = None
    providers: dict[str, str] | None = None
    model_routing: dict[str, str] | None = None
    style_playbook: str | None = None
    budget_cap: float | None = None


class ProjectCreate(BaseModel):
    name: str
    pipeline_type: str = "animated-explainer"
    duration_target_seconds: int = 45
    render_runtime: str | None = None
    style_playbook: str | None = None
    platform_profile: str | None = None
    studio_params: StudioParams | None = None


class EstimateBody(BaseModel):
    brief: str
    duration: int = 45
    pipeline_type: str = "animated-explainer"
    cost_tier: str = "balanced"


class ProjectOut(BaseModel):
    id: str
    name: str
    pipeline_type: str
    status: str
    render_runtime: str | None
    style_playbook: str | None
    platform_profile: str | None
    duration_target_seconds: int | None
    created_at: str


@router.post("/estimate")
async def estimate_project(body: EstimateBody):
    return compute_estimate(body)


@router.post("", status_code=201)
async def create_project(
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    # Concurrency check: count active runs for this tenant
    active_count = await db.execute(
        select(func.count(Run.id))
        .join(Project, Run.project_id == Project.id)
        .where(Project.tenant_id == tenant.id)
        .where(Run.status.notin_(["done", "anomaly"]))
    )
    active = active_count.scalar() or 0
    max_runs = tenant.max_concurrent_runs or 3
    if active >= max_runs:
        raise HTTPException(429, f"max concurrent runs reached ({active}/{max_runs})")

    project = Project(
        tenant_id=tenant.id,
        name=body.name,
        pipeline_type=body.pipeline_type,
        render_runtime=body.render_runtime,
        style_playbook=body.style_playbook,
        platform_profile=body.platform_profile,
        duration_target_seconds=body.duration_target_seconds,
        status="provisioning",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    run = Run(
        project_id=project.id,
        engine_version="mc-v0",
        status="provisioning",
        studio_params=body.studio_params.model_dump() if body.studio_params else None,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    manager = GraphManager()
    await manager.start_run(db, project, run)

    return {"project_id": project.id, "run_id": run.id, "status": "provisioning"}


@router.get("")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    latest_run_subq = (
        select(Run.id)
        .where(Run.project_id == Project.id)
        .order_by(Run.started_at.desc())
        .limit(1)
        .correlate(Project)
        .scalar_subquery()
    )
    result = await db.execute(
        select(Project, latest_run_subq)
        .where(Project.tenant_id == tenant.id)
        .order_by(Project.created_at.desc())
    )
    rows = result.all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "pipeline_type": p.pipeline_type,
            "status": p.status,
            "run_id": str(run_id) if run_id else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p, run_id in rows
    ]


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(Project)
        .where(Project.id == project_id)
        .where(Project.tenant_id == tenant.id)
    )
    p = result.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "project not found")
    return {
        "id": str(p.id),
        "name": p.name,
        "pipeline_type": p.pipeline_type,
        "status": p.status,
        "render_runtime": p.render_runtime,
        "style_playbook": p.style_playbook,
        "platform_profile": p.platform_profile,
        "duration_target_seconds": p.duration_target_seconds,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    }
