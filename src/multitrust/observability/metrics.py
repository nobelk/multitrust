"""Prometheus-compatible metrics collector (optional prometheus_client dep)."""

from __future__ import annotations

from typing import Any


class _NoOpGauge:
    def set(self, value: float) -> None:
        pass

    def labels(self, **kwargs: Any) -> _NoOpGauge:
        return self


class _NoOpCounter:
    def inc(self, amount: float = 1) -> None:
        pass

    def labels(self, **kwargs: Any) -> _NoOpCounter:
        return self


class _NoOpHistogram:
    def observe(self, value: float) -> None:
        pass

    def labels(self, **kwargs: Any) -> _NoOpHistogram:
        return self


class MetricsCollector:
    """Prometheus-compatible metrics collector.

    Uses prometheus_client if available; falls back to no-ops if not installed.
    """

    def __init__(self) -> None:
        try:
            import prometheus_client as prom  # type: ignore[import-untyped]

            self._evidence_counter = prom.Counter(
                "multitrust_evidence_submitted_total",
                "Total evidence submissions",
                ["agent_id"],
            )
            self._trust_gauge = prom.Gauge(
                "multitrust_trust_score",
                "Current trust score per agent",
                ["agent_id"],
            )
            self._agent_count = prom.Gauge(
                "multitrust_registered_agents_total",
                "Total number of registered agents",
            )
            self._prometheus_available = True
        except ImportError:
            self._evidence_counter: Any = _NoOpCounter()
            self._trust_gauge: Any = _NoOpGauge()
            self._agent_count: Any = _NoOpGauge()
            self._prometheus_available = False

    def record_evidence_submitted(self, agent_id: str) -> None:
        """Increment the evidence submission counter for an agent."""
        self._evidence_counter.labels(agent_id=agent_id).inc()

    def record_trust_update(self, agent_id: str, trust_score: float) -> None:
        """Update the trust score gauge for an agent."""
        self._trust_gauge.labels(agent_id=agent_id).set(trust_score)

    def set_agent_count(self, count: int) -> None:
        """Set the total number of registered agents."""
        self._agent_count.set(count)
