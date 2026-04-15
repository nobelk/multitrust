"""Tests for OpenTelemetry tracing integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from multitrust.core.evidence import Evidence
from multitrust.manager.trust_manager import TrustManager
from multitrust.observability.tracing import (
    SPAN_APPLY_DECAY,
    SPAN_EXPLAIN_TRUST,
    SPAN_GET_TRUST,
    SPAN_IS_TRUSTED,
    SPAN_MERGE_AUTHORITIES,
    SPAN_RANK_AGENTS,
    SPAN_SUBMIT_EVIDENCE,
    get_tracer,
    otel_available,
    trust_span,
)

try:
    import opentelemetry.sdk  # noqa: F401

    _has_otel = True
except ImportError:
    _has_otel = False

requires_otel = pytest.mark.skipif(not _has_otel, reason="opentelemetry-sdk not installed")


# ---------------------------------------------------------------------------
# Unit tests for the tracing module itself
# ---------------------------------------------------------------------------


class TestTracingHelpers:
    """Tests that work regardless of OTel installation."""

    def test_trust_span_yields_none_when_otel_absent(self):
        """When OTel is not available, trust_span yields None (no-op)."""
        with (
            patch("multitrust.observability.tracing._HAS_OTEL", False),
            trust_span("test.span", {"key": "value"}) as span,
        ):
            assert span is None

    def test_otel_available_returns_bool(self):
        result = otel_available()
        assert isinstance(result, bool)

    def test_get_tracer_returns_something(self):
        tracer = get_tracer()
        if otel_available():
            assert tracer is not None
        # When OTel absent, tracer is None — both valid

    def test_span_names_are_in_gen_ai_namespace(self):
        for name in [
            SPAN_SUBMIT_EVIDENCE,
            SPAN_GET_TRUST,
            SPAN_IS_TRUSTED,
            SPAN_RANK_AGENTS,
            SPAN_EXPLAIN_TRUST,
            SPAN_MERGE_AUTHORITIES,
            SPAN_APPLY_DECAY,
        ]:
            assert name.startswith("gen_ai.trust.")


# ---------------------------------------------------------------------------
# Integration tests requiring opentelemetry-sdk
# ---------------------------------------------------------------------------


@requires_otel
class TestTracingWithOtel:
    """Tests that verify real OTel spans are created."""

    @pytest.fixture()
    def exporter(self):
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        exp = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exp))

        # Patch the module-level tracer so trust_span uses our test provider
        import multitrust.observability.tracing as tracing_mod

        original_tracer = tracing_mod._tracer
        tracing_mod._tracer = provider.get_tracer("multitrust.test")
        yield exp
        tracing_mod._tracer = original_tracer
        provider.shutdown()

    def test_trust_span_creates_real_span(self, exporter):
        with trust_span("gen_ai.trust.test_op", {"gen_ai.trust.agent_id": "a1"}) as span:
            assert span is not None
            span.set_attribute("gen_ai.trust.score", 0.75)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        s = spans[0]
        assert s.name == "gen_ai.trust.test_op"
        assert s.attributes["gen_ai.trust.agent_id"] == "a1"
        assert s.attributes["gen_ai.trust.score"] == 0.75

    async def test_submit_evidence_emits_span(self, exporter):
        async with TrustManager() as m:
            await m.register_agent("agent-1")
            ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=3, negative=1)
            await m.submit_evidence(ev)

        spans = exporter.get_finished_spans()
        names = [s.name for s in spans]
        assert SPAN_SUBMIT_EVIDENCE in names

        submit_span = next(s for s in spans if s.name == SPAN_SUBMIT_EVIDENCE)
        assert submit_span.attributes["gen_ai.trust.agent_id"] == "agent-1"
        assert submit_span.attributes["gen_ai.trust.authority_id"] == "auth-1"
        assert submit_span.attributes["gen_ai.trust.evidence.positive"] == 3
        assert submit_span.attributes["gen_ai.trust.evidence.negative"] == 1
        assert "gen_ai.trust.new_score" in submit_span.attributes
        assert "gen_ai.trust.old_score" in submit_span.attributes

    async def test_get_trust_emits_span(self, exporter):
        async with TrustManager() as m:
            await m.register_agent("agent-1")
            await m.get_trust("agent-1")

        spans = exporter.get_finished_spans()
        names = [s.name for s in spans]
        assert SPAN_GET_TRUST in names

        get_span = next(s for s in spans if s.name == SPAN_GET_TRUST)
        assert get_span.attributes["gen_ai.trust.agent_id"] == "agent-1"
        assert "gen_ai.trust.score" in get_span.attributes

    async def test_is_trusted_emits_span_with_decision(self, exporter):
        async with TrustManager() as m:
            await m.register_agent("agent-1")
            await m.is_trusted("agent-1")

        spans = exporter.get_finished_spans()
        is_spans = [s for s in spans if s.name == SPAN_IS_TRUSTED]
        assert len(is_spans) == 1

        s = is_spans[0]
        assert s.attributes["gen_ai.trust.agent_id"] == "agent-1"
        assert s.attributes["gen_ai.trust.decision"] in ("allow", "block")
        assert "gen_ai.trust.threshold" in s.attributes

    async def test_is_trusted_missing_agent_emits_block(self, exporter):
        async with TrustManager() as m:
            result = await m.is_trusted("nonexistent")  # noqa: F841
            assert result is False

        spans = exporter.get_finished_spans()
        is_spans = [s for s in spans if s.name == SPAN_IS_TRUSTED]
        assert len(is_spans) == 1
        assert is_spans[0].attributes["gen_ai.trust.decision"] == "block"
        assert is_spans[0].attributes["gen_ai.trust.agent_found"] is False

    async def test_rank_agents_emits_span(self, exporter):
        async with TrustManager() as m:
            await m.register_agent("a1")
            await m.register_agent("a2")
            await m.rank_agents()

        spans = exporter.get_finished_spans()
        rank_spans = [s for s in spans if s.name == SPAN_RANK_AGENTS]
        assert len(rank_spans) == 1
        assert rank_spans[0].attributes["gen_ai.trust.agent_count"] == 2

    async def test_explain_trust_emits_span(self, exporter):
        async with TrustManager() as m:
            await m.register_agent("agent-1")
            ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=5, negative=1)
            await m.submit_evidence(ev)
            await m.explain_trust("agent-1")

        spans = exporter.get_finished_spans()
        explain_spans = [s for s in spans if s.name == SPAN_EXPLAIN_TRUST]
        assert len(explain_spans) == 1

        s = explain_spans[0]
        assert s.attributes["gen_ai.trust.agent_id"] == "agent-1"
        assert "gen_ai.trust.score" in s.attributes
        assert "gen_ai.trust.level" in s.attributes
        assert "gen_ai.trust.decision" in s.attributes
        assert "gen_ai.trust.completeness" in s.attributes

    async def test_merge_authority_opinions_emits_span(self, exporter):
        from multitrust.core.opinion import Opinion

        async with TrustManager() as m:
            await m.register_agent("agent-1")
            auth_op = Opinion(belief=0.8, disbelief=0.1, uncertainty=0.1)
            agent_op = Opinion(belief=0.7, disbelief=0.1, uncertainty=0.2)
            await m.merge_authority_opinions("agent-1", [(auth_op, agent_op)])

        spans = exporter.get_finished_spans()
        merge_spans = [s for s in spans if s.name == SPAN_MERGE_AUTHORITIES]
        assert len(merge_spans) == 1
        assert merge_spans[0].attributes["gen_ai.trust.agent_id"] == "agent-1"
        assert merge_spans[0].attributes["gen_ai.trust.authority_count"] == 1

    async def test_apply_decay_emits_span(self, exporter):
        from multitrust.config.settings import MultiTrustConfig

        cfg = MultiTrustConfig(enable_time_decay=True, decay_half_life_seconds=3600)
        async with TrustManager(config=cfg) as m:
            await m.register_agent("agent-1")
            count = await m.apply_decay()

        spans = exporter.get_finished_spans()
        decay_spans = [s for s in spans if s.name == SPAN_APPLY_DECAY]
        assert len(decay_spans) == 1
        assert decay_spans[0].attributes["gen_ai.trust.agents_decayed"] == count


# ---------------------------------------------------------------------------
# Tests that trust_span is a true no-op when OTel absent
# ---------------------------------------------------------------------------


class TestNoOpFallback:
    """Verify that the no-op path doesn't break normal TrustManager operations."""

    async def test_submit_evidence_works_without_otel(self):
        with patch("multitrust.observability.tracing._HAS_OTEL", False):
            async with TrustManager() as m:
                await m.register_agent("agent-1")
                ev = Evidence(agent_id="agent-1", authority_id="auth-1", positive=3, negative=1)
                record = await m.submit_evidence(ev)
                assert record.trustworthiness > 0

    async def test_get_trust_works_without_otel(self):
        with patch("multitrust.observability.tracing._HAS_OTEL", False):
            async with TrustManager() as m:
                await m.register_agent("agent-1")
                score = await m.get_trust("agent-1")
                assert isinstance(score, float)
