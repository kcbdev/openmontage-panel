from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import get_current_tenant, require_user
from api.db.session import get_db
from api.models import Asset, Project, Run, Tenant, User

router = APIRouter(prefix="/projects", tags=["archive"])


class RemixBody(BaseModel):
    name: str
    pipeline_type: str | None = None
    render_runtime: str | None = None
    style_playbook: str | None = None
    platform_profile: str | None = None
    duration_target_seconds: int | None = None
    studio_params: dict | None = None


@router.get("/{project_id}/assets")
async def list_project_assets(
    project_id: str,
    stage: str | None = Query(None),
    type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    project = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant.id,
        )
    )
    if not project.scalar_one_or_none():
        raise HTTPException(404, "project not found")

    q = select(Asset).join(Run).where(Run.project_id == project_id)
    if stage:
        q = q.where(Asset.stage == stage)
    if type:
        q = q.where(Asset.type == type)
    q = q.order_by(Asset.created_at.desc())

    result = await db.execute(q)
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
            "scene_number": a.scene_number,
            "thumbnail_url": a.thumbnail_url,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in assets
    ]


@router.get("/{project_id}/download")
async def download_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    project = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant.id,
        )
    )
    p = project.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "project not found")

    runs_result = await db.execute(
        select(Run).where(Run.project_id == project_id).order_by(Run.started_at.desc())
    )
    runs = runs_result.scalars().all()

    return {
        "project": {
            "id": str(p.id),
            "name": p.name,
            "pipeline_type": p.pipeline_type,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        },
        "runs": [
            {
                "id": str(r.id),
                "status": r.status,
                "engine_version": r.engine_version,
                "current_stage": r.current_stage,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ],
    }


@router.post("/{project_id}/remix", status_code=201)
async def remix_project(
    project_id: str,
    body: RemixBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    source = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.tenant_id == tenant.id,
        )
    )
    src = source.scalar_one_or_none()
    if not src:
        raise HTTPException(404, "project not found")

    project = Project(
        tenant_id=tenant.id,
        name=body.name,
        pipeline_type=body.pipeline_type or src.pipeline_type,
        render_runtime=body.render_runtime or src.render_runtime,
        style_playbook=body.style_playbook or src.style_playbook,
        platform_profile=body.platform_profile or src.platform_profile,
        duration_target_seconds=body.duration_target_seconds or src.duration_target_seconds,
        parent_project_id=src.id,
        status="draft",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)

    return {"project_id": project.id, "status": "draft"}
