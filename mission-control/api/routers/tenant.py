from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import get_current_tenant as auth_get_current_tenant
from api.auth.session import get_password_hash, require_user, role_satisfies
from api.db.session import get_db
from api.models import Tenant, User

router = APIRouter(prefix="/tenant", tags=["tenant"])


class InviteBody(BaseModel):
    email: str


@router.get("")
async def get_current_tenant(tenant: Tenant = Depends(auth_get_current_tenant)):
    return {
        "id": tenant.id,
        "name": tenant.name,
    }


@router.post("/invite", status_code=201)
async def invite_member(
    body: InviteBody,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    tenant: Tenant = Depends(auth_get_current_tenant),
):
    if not role_satisfies(user.role, "owner"):
        raise HTTPException(403, "only owners can invite members")

    existing = await db.execute(
        select(User).where(User.email == body.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "user already exists")

    # Generate a random password — the invited user will need to reset
    import secrets
    temp_password = secrets.token_urlsafe(16)
    new_user = User(
        tenant_id=tenant.id,
        email=body.email,
        hashed_password=get_password_hash(temp_password),
        role="editor",
        invited_by=user.id,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "id": new_user.id,
        "email": new_user.email,
        "role": new_user.role,
        "temp_password": temp_password,
    }


@router.get("/members")
async def list_members(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    tenant: Tenant = Depends(auth_get_current_tenant),
):
    result = await db.execute(
        select(User).where(User.tenant_id == tenant.id)
    )
    members = result.scalars().all()
    return [
        {
            "id": m.id,
            "email": m.email,
            "role": m.role,
            "invited_by": m.invited_by,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in members
    ]


@router.delete("/members/{member_id}")
async def remove_member(
    member_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_user),
    tenant: Tenant = Depends(auth_get_current_tenant),
):
    if not role_satisfies(user.role, "owner"):
        raise HTTPException(403, "only owners can remove members")

    result = await db.execute(
        select(User).where(
            User.id == member_id,
            User.tenant_id == tenant.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(404, "member not found")
    if member.id == user.id:
        raise HTTPException(400, "cannot remove yourself")

    await db.delete(member)
    await db.commit()
    return {"status": "removed"}
