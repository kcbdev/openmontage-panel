"""
Rate limiting via slowapi with Redis backend (falls back to in-memory).
"""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


def configure_rate_limiter(app: FastAPI) -> Limiter:
    redis_url = os.environ.get("REDIS_URL", None)
    storage_uri = f"{redis_url}/1" if redis_url else None

    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=storage_uri,
        default_limits=["60/minute"],
    )

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "rate limit exceeded — try again later"},
        )

    return limiter
