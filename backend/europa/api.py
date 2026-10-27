"""FastAPI application: /api/health, /api/scenarios, POST /api/assess (NDJSON stream)."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError
from starlette.background import BackgroundTask

from . import __version__
from .config import Settings
from .llm import LangChainStructuredLLM, StructuredLLM
from .ratelimit import SlidingWindowLimiter
from .scenarios import SCENARIOS
from .schemas import MAX_DESCRIPTION_CHARS, AssessmentRequest
from .service import stream_assessment

logger = logging.getLogger("europa.api")

MAX_BODY_BYTES = 6 * MAX_DESCRIPTION_CHARS + 2048  # worst case UTF-8 plus JSON envelope

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def _error(
    status: int, code: str, message: str, *, retry_after: int | None = None, extra: Any = None
) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if retry_after is not None:
        body["error"]["retry_after_seconds"] = retry_after
    if extra is not None:
        body["error"]["details"] = extra
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
    return JSONResponse(body, status_code=status, headers=headers)


def client_key(request: Request) -> str:
    """Vercel overwrites x-vercel-forwarded-for, so clients cannot spoof it there."""
    forwarded = request.headers.get("x-vercel-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


async def read_limited_body(request: Request, limit: int) -> bytes | None:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        return None
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def create_app(settings: Settings | None = None, llm: StructuredLLM | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="EUROPA AI GOVERNANCE API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    limiter = SlidingWindowLimiter(
        settings.rate_limit_requests,
        settings.global_rate_limit_requests,
        settings.rate_limit_window_s,
    )
    active = {"runs": 0}
    resolved_llm: dict[str, StructuredLLM | None] = {"llm": llm}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        max_age=600,
    )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        return response

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error: %s", type(exc).__name__)
        return _error(500, "internal_error", "Something went wrong. Please try again.")

    def get_llm() -> StructuredLLM | None:
        if resolved_llm["llm"] is None and settings.llm_configured:
            resolved_llm["llm"] = LangChainStructuredLLM(settings)
        return resolved_llm["llm"]

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": __version__,
            "model": settings.model,
            "llm_configured": settings.llm_configured or resolved_llm["llm"] is not None,
            "max_reassessment_rounds": settings.max_reassessment_rounds,
        }

    @app.get("/api/scenarios")
    async def scenarios() -> dict[str, Any]:
        return {"scenarios": [s.model_dump() for s in SCENARIOS]}

    @app.post("/api/assess")
    async def assess(request: Request):
        ctype = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            return _error(415, "unsupported_media_type", "Send the request as application/json.")
        body = await read_limited_body(request, MAX_BODY_BYTES)
        if body is None:
            return _error(413, "payload_too_large", "The request is too large.")
        try:
            payload = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            return _error(400, "invalid_json", "The request body is not valid JSON.")
        try:
            req = AssessmentRequest.model_validate(payload)
        except ValidationError as exc:
            details = [
                {"field": ".".join(str(p) for p in e["loc"]), "issue": e["msg"]}
                for e in exc.errors(include_input=False, include_url=False)
            ]
            return _error(
                422,
                "validation_error",
                "The description must be between 30 and 6000 characters.",
                extra=details,
            )
        model = get_llm()
        if model is None:
            return _error(
                503, "not_configured", "The assessment service is not configured on this server."
            )
        retry = limiter.check(client_key(request))
        if retry is not None:
            return _error(
                429,
                "rate_limited",
                "Too many assessments. Please wait before trying again.",
                retry_after=retry,
            )
        if active["runs"] >= settings.max_concurrent_runs:
            return _error(
                503, "busy", "The service is busy. Please try again shortly.", retry_after=10
            )

        # Reserve the slot synchronously so concurrent requests cannot both pass the check.
        active["runs"] += 1
        released = False

        def release() -> None:
            nonlocal released
            if not released:
                released = True
                active["runs"] -= 1

        async def body_stream() -> AsyncIterator[bytes]:
            try:
                async for event in stream_assessment(req, settings, model):
                    yield (json.dumps(event, ensure_ascii=False) + "\n").encode()
            finally:
                release()

        return StreamingResponse(
            body_stream(),
            media_type="application/x-ndjson",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store, no-transform"},
            background=BackgroundTask(release),
        )

    return app
