"""
WebSocket endpoint for live run events via Redis pub/sub.
"""
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from api.auth.session import decode_jwt
from api.db.session import async_session
from api.models import Project, Run

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
router = APIRouter()

_redis = None


async def _get_redis():
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(REDIS_URL)
    return _redis


async def publish_run_event(run_id: str, event: dict) -> None:
    try:
        r = await _get_redis()
        channel = f"run:{run_id}:events"
        await r.publish(channel, json.dumps(event))
    except Exception as e:
        logger.warning("failed to publish event for run %s: %s", run_id, e)


def _typed_event(event_type: str, data: dict) -> dict:
    return {"type": event_type, "data": data}


def state_update(run_id: str, status: str, current_stage: str | None,
                 anomaly_reason: str | None = None, **extra) -> dict:
    return _typed_event("state_update", {
        "run_id": run_id,
        "status": status,
        "current_stage": current_stage,
        "anomaly_reason": anomaly_reason,
        **extra,
    })


def gate_event(run_id: str, stage: str, gate_type: str, action: str,
               required_role: str | None = None) -> dict:
    return _typed_event("gate", {
        "run_id": run_id,
        "stage": stage,
        "gate_type": gate_type,
        "action": action,
        "required_role": required_role,
    })


def checkpoint_event(run_id: str, stage: str, has_artifacts: bool = False,
                     stage_count: int = 0) -> dict:
    return _typed_event("checkpoint", {
        "run_id": run_id,
        "stage": stage,
        "has_artifacts": has_artifacts,
        "stage_count": stage_count,
    })


def anomaly_event(run_id: str, reason: str, stage: str | None = None) -> dict:
    return _typed_event("anomaly", {
        "run_id": run_id,
        "reason": reason,
        "stage": stage,
    })


def done_event(run_id: str, finished_at: str | None = None) -> dict:
    return _typed_event("done", {
        "run_id": run_id,
        "finished_at": finished_at,
    })


async def _verify_ws_token(token: str, run_id: str) -> bool:
    try:
        payload = decode_jwt(token)
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return False
        async with async_session() as db:
            result = await db.execute(
                select(Run.id)
                .join(Project, Run.project_id == Project.id)
                .where(Run.id == run_id, Project.tenant_id == tenant_id)
            )
            return result.scalar_one_or_none() is not None
    except Exception:
        return False


@router.websocket("/runs/{run_id}/stream")
async def run_stream(ws: WebSocket, run_id: str):
    token = ws.query_params.get("token", "")

    if not token or not await _verify_ws_token(token, run_id):
        await ws.close(code=4001, reason="unauthorized")
        return

    await ws.accept()
    logger.info("WS connected for run %s", run_id)

    try:
        r = await _get_redis()
        pubsub = r.pubsub()
        channel = f"run:{run_id}:events"

        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                await ws.send_text(message["data"])
            except WebSocketDisconnect:
                break
            except Exception:
                break

        await pubsub.unsubscribe(channel)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WS error for run %s: %s", run_id, e)
