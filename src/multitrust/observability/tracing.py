"""OpenTelemetry tracing support for MultiTrust.

Provides span instrumentation for trust operations using the ``gen_ai.*``
semantic conventions namespace.  When the OpenTelemetry SDK is installed
(``pip install multitrust[otel]``), real spans are emitted.  Otherwise all
helpers degrade to no-ops so the rest of the codebase never needs to
guard imports.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import Any

# ---------------------------------------------------------------------------
# Lazy, optional OTel import
# ---------------------------------------------------------------------------

try:
    from opentelemetry import trace

    _tracer: trace.Tracer = trace.get_tracer(
        "multitrust",
        schema_url="https://opentelemetry.io/schemas/1.24.0",
    )
    _HAS_OTEL = True
except ImportError:  # pragma: no cover – tested via mock
    _HAS_OTEL = False
    _tracer = None  # type: ignore[assignment,unused-ignore]


# ---------------------------------------------------------------------------
# Span names – centralised so tests can assert on them.
# ---------------------------------------------------------------------------

SPAN_SUBMIT_EVIDENCE = "gen_ai.trust.submit_evidence"
SPAN_GET_TRUST = "gen_ai.trust.evaluate"
SPAN_IS_TRUSTED = "gen_ai.trust.is_trusted"
SPAN_RANK_AGENTS = "gen_ai.trust.rank_agents"
SPAN_EXPLAIN_TRUST = "gen_ai.trust.explain"
SPAN_MERGE_AUTHORITIES = "gen_ai.trust.merge_authorities"
SPAN_APPLY_DECAY = "gen_ai.trust.apply_decay"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_tracer() -> Any:
    """Return the package-level OTel tracer (or *None* if OTel is absent)."""
    return _tracer


def otel_available() -> bool:
    """Return *True* when the OpenTelemetry SDK is importable."""
    return _HAS_OTEL


@contextlib.contextmanager
def trust_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Context manager that opens an OTel span for a trust operation.

    *attributes* are set on the span immediately.  The yielded object is the
    live ``Span`` (or a no-op ``None`` when OTel is absent) so callers can
    add extra attributes or record exceptions as the operation proceeds.

    Usage::

        with trust_span(SPAN_SUBMIT_EVIDENCE, {"gen_ai.trust.agent_id": "a1"}) as span:
            ...
            if span is not None:
                span.set_attribute("gen_ai.trust.new_score", 0.85)
    """
    if not _HAS_OTEL or _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(name, attributes=attributes or {}) as span:
        yield span
