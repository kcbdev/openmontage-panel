import logging
import os
import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


def configure_logging(app: FastAPI) -> None:
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        force=True,
    )
    logger = logging.getLogger("uvicorn.access")
    logger.handlers.clear()

    app.add_middleware(LoggingMiddleware)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        logger = logging.getLogger("api")
        path = request.url.path
        method = request.method

        logger.info("request_id=%s method=%s path=%s", request_id, method, path)

        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_id=%s unhandled exception", request_id)
            raise

        elapsed = time.monotonic() - start
        logger.info(
            "request_id=%s method=%s path=%s status=%d elapsed_ms=%.0f",
            request_id,
            method,
            path,
            response.status_code,
            elapsed * 1000,
        )
        response.headers["X-Request-ID"] = request_id
        return response
