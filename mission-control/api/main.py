import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from api.auth.router import router as auth_router
from api.db.session import Base, engine
from api.middleware.logging import configure_logging
from api.middleware.rate_limit import configure_rate_limiter
from api.routers import (
    approval_gates,
    archive,
    budget,
    credentials,
    pipelines,
    profiles,
    projects,
    providers,
    runs,
    tenant,
    ws,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="OpenMontage Mission Control", version="0.1.0", lifespan=lifespan)

configure_logging(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = configure_rate_limiter(app)

app.include_router(auth_router)
app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(approval_gates.router)
app.include_router(ws.router)
app.include_router(pipelines.router)
app.include_router(providers.router)
app.include_router(credentials.router)
app.include_router(budget.router)
app.include_router(tenant.router)
app.include_router(archive.router)
app.include_router(profiles.router)


@app.get("/health")
async def health():
    return Response(status_code=204)


@app.get("/ready")
async def ready():
    status = {"database": False, "redis": False}
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status["database"] = True
    except Exception:
        pass
    if os.environ.get("REDIS_URL"):
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(os.environ["REDIS_URL"])
            await r.ping()
            await r.aclose()
            status["redis"] = True
        except Exception:
            pass
    all_ok = all(status.values())
    status_code = 200 if all_ok else 503
    import json

    return Response(
        content=json.dumps({"status": "ok" if all_ok else "degraded", "checks": status}),
        status_code=status_code,
        media_type="application/json",
    )
