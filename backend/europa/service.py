"""Runs the graph and exposes it as an async stream of JSON-serialisable events."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from .agents import RunContext
from .audit import AuditLog
from .config import Settings
from .graph import build_graph
from .llm import StructuredLLM
from .schemas import AssessmentRequest, AuditEvent, AuditEventType, GovernanceReport

logger = logging.getLogger("europa.service")

HEARTBEAT_S = 8.0
HARD_GRACE_S = 15.0


async def run_assessment(
    request: AssessmentRequest,
    settings: Settings,
    llm: StructuredLLM,
    sink: asyncio.Queue[AuditEvent | None] | None = None,
) -> GovernanceReport:
    audit = AuditLog(sink)
    ctx = RunContext(
        settings=settings,
        llm=llm,
        audit=audit,
        deadline=time.monotonic() + settings.run_deadline_s,
    )
    try:
        audit.emit(
            AuditEventType.ASSESSMENT_STARTED,
            "Assessment started",
            description_chars=len(request.description),
            max_reassessment_rounds=settings.max_reassessment_rounds,
        )
        async with asyncio.timeout(settings.run_deadline_s + HARD_GRACE_S):
            final = await build_graph().ainvoke(
                {"description": request.description, "scenario_id": request.scenario_id},
                config={"configurable": {"ctx": ctx}},
            )
        return final["report"]
    finally:
        if sink is not None:
            sink.put_nowait(None)


def _event_line(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": kind, **payload}


async def stream_assessment(
    request: AssessmentRequest, settings: Settings, llm: StructuredLLM
) -> AsyncIterator[dict[str, Any]]:
    """Yield `audit` events as they happen, then one `report` (or `error`) event."""
    queue: asyncio.Queue[AuditEvent | None] = asyncio.Queue()
    task = asyncio.create_task(run_assessment(request, settings, llm, queue))
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_S)
            except TimeoutError:
                yield _event_line("ping", {})
                continue
            if event is None:
                break
            yield _event_line("audit", {"event": event.model_dump(mode="json")})
        try:
            report = await task
        except TimeoutError:
            logger.error("assessment exceeded hard deadline")
            yield _event_line(
                "error",
                {
                    "error": {
                        "code": "timeout",
                        "message": "The assessment took too long and "
                        "was stopped. Please try again with a shorter description.",
                    }
                },
            )
            return
        except Exception as exc:
            logger.error("assessment crashed: %s", type(exc).__name__)
            yield _event_line(
                "error",
                {
                    "error": {
                        "code": "internal_error",
                        "message": "The assessment could not be completed. Please try again.",
                    }
                },
            )
            return
        yield _event_line("report", {"report": report.model_dump(mode="json")})
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
