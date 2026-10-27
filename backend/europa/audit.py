"""Audit trail: structured, user-text-free events, logged and streamed."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from .schemas import AgentName, AgentStatus, AuditEvent, AuditEventType

logger = logging.getLogger("europa.audit")


class AuditLog:
    """Append-only event list. Optionally mirrors events into an asyncio queue.

    Messages are produced by code, never from user text. Only the event type,
    agent, status, round and sequence number are written to the process log.
    """

    def __init__(self, sink: asyncio.Queue[AuditEvent | None] | None = None) -> None:
        self.events: list[AuditEvent] = []
        self._sink = sink

    def emit(
        self,
        type_: AuditEventType,
        message: str,
        *,
        agent: AgentName | None = None,
        status: AgentStatus | None = None,
        round_: int = 0,
        **data: str | int | float | bool | list[str],
    ) -> AuditEvent:
        event = AuditEvent(
            seq=len(self.events) + 1,
            ts=datetime.now(UTC),
            type=type_,
            message=message,
            agent=agent,
            status=status,
            round=round_,
            data=data,
        )
        self.events.append(event)
        logger.info(
            "audit seq=%s type=%s agent=%s status=%s round=%s",
            event.seq,
            event.type.value,
            agent.value if agent else "-",
            status.value if status else "-",
            round_,
        )
        if self._sink is not None:
            self._sink.put_nowait(event)
        return event
