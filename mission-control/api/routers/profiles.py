from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import get_current_tenant
from api.db.session import get_db
from api.models import MissionProfile, Tenant, TenantStylePlaybook

router = APIRouter(tags=["profiles"])


class ProfileCreate(BaseModel):
    name: str
    pipeline_type: str = "animated-explainer"
    params: dict | None = None


class StyleCloneBody(BaseModel):
    name: str
    source_playbook_id: str
    yaml_content: str | None = None


@router.get("/mission-profiles")
async def list_profiles(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(MissionProfile)
        .where(MissionProfile.tenant_id == tenant.id)
        .order_by(MissionProfile.created_at.desc())
    )
    profiles = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "pipeline_type": p.pipeline_type,
            "params": p.params,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in profiles
    ]


@router.post("/mission-profiles", status_code=201)
async def create_profile(
    body: ProfileCreate,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    profile = MissionProfile(
        tenant_id=tenant.id,
        name=body.name,
        pipeline_type=body.pipeline_type,
        params=body.params,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return {
        "id": str(profile.id),
        "name": profile.name,
        "pipeline_type": profile.pipeline_type,
    }


@router.delete("/mission-profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(MissionProfile).where(
            MissionProfile.id == profile_id,
            MissionProfile.tenant_id == tenant.id,
        )
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "profile not found")
    await db.delete(profile)
    await db.commit()
    return {"status": "deleted"}


@router.post("/styles/clone", status_code=201)
async def clone_style(
    body: StyleCloneBody,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    playbook = TenantStylePlaybook(
        tenant_id=tenant.id,
        name=body.name,
        source_playbook_id=body.source_playbook_id,
        yaml_content=body.yaml_content,
    )
    db.add(playbook)
    await db.commit()
    await db.refresh(playbook)
    return {
        "id": str(playbook.id),
        "name": playbook.name,
        "source_playbook_id": playbook.source_playbook_id,
    }
