"""Observability module for MultiTrust — events, metrics, logging."""

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

__all__ = [
    "EventBus",
    "TrustEvent",
    "TrustUpdatedEvent",
    "EvidenceSubmittedEvent",
    "AgentRegisteredEvent",
    "TrustThresholdCrossedEvent",
    "MetricsCollector",
    "get_logger",
]
