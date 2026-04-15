"""Observability module for MultiTrust — events, metrics, logging, tracing."""

from multitrust.observability.events import (
    AgentRegisteredEvent,
    EventBus,
    EvidenceSubmittedEvent,
    TrustEvent,
    TrustThresholdCrossedEvent,
    TrustUpdatedEvent,
)
from multitrust.observability.logging import get_logger
from multitrust.observability.metrics import MetricsCollector
from multitrust.observability.tracing import get_tracer, otel_available, trust_span

__all__ = [
    "EventBus",
    "TrustEvent",
    "TrustUpdatedEvent",
    "EvidenceSubmittedEvent",
    "AgentRegisteredEvent",
    "TrustThresholdCrossedEvent",
    "MetricsCollector",
    "get_logger",
    "get_tracer",
    "otel_available",
    "trust_span",
]
