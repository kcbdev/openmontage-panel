import asyncio
import io
import os
from functools import lru_cache

from minio import Minio
from minio.error import S3Error


@lru_cache(maxsize=1)
def _get_client() -> Minio | None:
    endpoint = os.environ.get("MINIO_ENDPOINT", "")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    if not endpoint:
        return None
    return Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
    )


def _tenant_bucket(tenant_id: str) -> str:
    return f"tenant-{tenant_id}"


async def ensure_tenant_bucket(tenant_id: str) -> str:
    """Create the tenant bucket if it doesn't exist. Returns the bucket name."""
    client = _get_client()
    if not client:
        return ""
    bucket = _tenant_bucket(tenant_id)
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, client.make_bucket, bucket)
    except S3Error as e:
        if e.code != "BucketAlreadyOwnedByYou":
            raise
    return bucket


async def object_path(tenant_id: str, project_id: str, run_id: str, key: str) -> str | None:
    """Get a presigned URL for an object in the tenant's bucket."""
    client = _get_client()
    if not client:
        return None
    bucket = _tenant_bucket(tenant_id)
    obj = f"projects/{project_id}/runs/{run_id}/{key}"
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: client.presigned_get_object(bucket, obj),
        )
    except S3Error:
        return None


async def put_object(
    tenant_id: str, project_id: str, run_id: str, key: str, data: bytes,
    content_type: str = "application/octet-stream",
) -> str | None:
    client = _get_client()
    if not client:
        return None
    bucket = _tenant_bucket(tenant_id)
    obj = f"projects/{project_id}/runs/{run_id}/{key}"
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(
            None,
            lambda: client.put_object(bucket, obj, io.BytesIO(data), len(data), content_type=content_type),
        )
        return obj
    except S3Error:
        return None
