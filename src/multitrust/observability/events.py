"""Trust event types and event bus for observability."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrustEvent:
    event_type: str
    agent_id: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrustUpdatedEvent(TrustEvent):
    old_trust: float = 0.0
    new_trust: float = 0.0


@dataclass
class EvidenceSubmittedEvent(TrustEvent):
    positive: float = 0.0
    negative: float = 0.0


@dataclass
class AgentRegisteredEvent(TrustEvent):
    initial_trust: float = 0.5


@dataclass
class TrustThresholdCrossedEvent(TrustEvent):
    threshold: float = 0.5
    direction: str = "below"  # "above" or "below"


@dataclass
class TrustExplainedEvent(TrustEvent):
    explanation: Any = None  # TrustExplanation (Any to avoid circular import)


Handler = Callable[[Any], Awaitable[None]]


class EventBus:
    """Async event bus for publishing and subscribing to trust events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = {}

    def on(self, event_type: str, handler: Handler) -> None:
        """Register an async handler for a given event type."""
        self._handlers.setdefault(event_type, []).append(handler)

    async def emit(self, event: TrustEvent) -> None:
        """Emit an event to all registered handlers for its event_type."""
        handlers = self._handlers.get(event.event_type, [])
        for handler in handlers:
            await handler(event)
