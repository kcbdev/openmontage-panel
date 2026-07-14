from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import (
    create_access_token,
    get_password_hash,
    require_user,
    validate_password,
    verify_password,
)
from api.bridge.minio import ensure_tenant_bucket
from api.db.session import get_db
from api.models import Tenant, User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    tenant_id: str


@router.post("/register", status_code=201)
async def register(body: RegisterBody, db: AsyncSession = Depends(get_db)):
    err = validate_password(body.password)
    if err:
        raise HTTPException(422, err)

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "email already registered")

    result = await db.execute(select(Tenant).limit(1))
    existing_tenant = result.scalar_one_or_none()

    if existing_tenant:
        raise HTTPException(403, "registration is invite-only — ask an owner to invite you")

    tenant = Tenant(name="default")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)

    await ensure_tenant_bucket(tenant.id)

    user = User(
        tenant_id=tenant.id,
        email=body.email,
        hashed_password=get_password_hash(body.password),
        role="owner",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "tenant_id": str(user.tenant_id),
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "email": user.email, "role": user.role, "tenant_id": str(user.tenant_id)},
    }


@router.post("/login")
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "invalid email or password")

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role,
        "tenant_id": str(user.tenant_id),
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user.id), "email": user.email, "role": user.role, "tenant_id": str(user.tenant_id)},
    }


@router.get("/me")
async def me(user: User = Depends(require_user)):
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "tenant_id": str(user.tenant_id),
    }
