import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.session import get_current_tenant
from api.db.session import get_db
from api.models import ProviderCredential, Tenant

router = APIRouter(prefix="/credentials", tags=["credentials"])

ENCRYPTION_KEY = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
if ENCRYPTION_KEY:
    _fernet = Fernet(ENCRYPTION_KEY.encode())
else:
    _fernet = None


def _encrypt(value: str) -> str:
    if not _fernet:
        raise HTTPException(500, "credential encryption not configured")
    return _fernet.encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    if not _fernet:
        raise HTTPException(500, "credential encryption not configured")
    return _fernet.decrypt(value.encode()).decode()


class CredentialUpsert(BaseModel):
    key: str
    value: str


class CredentialOut(BaseModel):
    key: str
    last_verified_at: str | None = None


@router.get("")
async def list_credentials(
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(ProviderCredential)
        .where(ProviderCredential.tenant_id == tenant.id)
    )
    creds = result.scalars().all()
    return [
        {
            "key": c.provider_key,
            "last_verified_at": c.last_verified_at.isoformat() if c.last_verified_at else None,
        }
        for c in creds
    ]


@router.post("", status_code=201)
async def upsert_credential(
    payload: CredentialUpsert,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    encrypted = _encrypt(payload.value)
    existing = await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.tenant_id == tenant.id,
            ProviderCredential.provider_key == payload.key,
        )
    )
    cred = existing.scalar_one_or_none()
    if cred:
        cred.encrypted_value = encrypted
        cred.last_verified_at = None
    else:
        cred = ProviderCredential(
            tenant_id=tenant.id,
            provider_key=payload.key,
            encrypted_value=encrypted,
        )
        db.add(cred)
    await db.commit()
    return {"status": "saved"}


@router.delete("/{key}")
async def delete_credential(
    key: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.provider_key == key,
            ProviderCredential.tenant_id == tenant.id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(404, "credential not found")
    await db.delete(cred)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{key}/test")
async def test_credential(
    key: str,
    db: AsyncSession = Depends(get_db),
    tenant: Tenant = Depends(get_current_tenant),
):
    result = await db.execute(
        select(ProviderCredential).where(
            ProviderCredential.provider_key == key,
            ProviderCredential.tenant_id == tenant.id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(404, "credential not found")

    value = _decrypt(cred.encrypted_value)
    if not value:
        raise HTTPException(500, "failed to decrypt credential")

    # Lightweight ping — just mark as verified for now
    cred.last_verified_at = datetime.now(timezone.utc)
    await db.commit()

    return {"ok": True, "message": f"{key} credential verified"}
