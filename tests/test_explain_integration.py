"""Integration tests for the explain_trust() API."""

from __future__ import annotations

import pytest

from multitrust.core.errors import TrustThresholdError
from multitrust.core.evidence import Evidence
from multitrust.integrations.generic.decorators import trust_aware
from multitrust.manager.trust_manager import TrustManager
from multitrust.storage.memory_ledger import InMemoryEvidenceLedger


class TestEndToEndExplanation:
    @pytest.mark.asyncio
    async def test_full_flow(self) -> None:
        """Register agent, submit evidence from multiple authorities, explain."""
        ledger = InMemoryEvidenceLedger()
        mgr = TrustManager(evidence_ledger=ledger)

        await mgr.register_agent("fact-checker")

        # Submit from multiple authorities
        await mgr.submit_evidence(
            Evidence(
                agent_id="fact-checker",
                authority_id="validator",
                positive=8.0,
                negative=1.0,
                rule_name="ConsensusRule",
            )
        )
        await mgr.submit_evidence(
            Evidence(
                agent_id="fact-checker",
                authority_id="monitor",
                positive=4.0,
                negative=3.0,
                rule_name="LatencyRule",
            )
        )
        await mgr.submit_evidence(
            Evidence(
                agent_id="fact-checker",
                authority_id="validator",
                positive=6.0,
                negative=0.0,
                rule_name="ConsensusRule",
            )
        )

        explanation = await mgr.explain_trust("fact-checker")

        # Validate all fields populated
        assert explanation.agent_id == "fact-checker"
        assert explanation.trust_score > 0.5
        assert explanation.completeness == "full"
        assert len(explanation.projected_trust) == 4
        assert len(explanation.top_contributors) >= 2
        assert explanation.evidence_summary.total_evidence_count == 3
        assert explanation.evidence_summary.distinct_authorities == 2
        assert explanation.evidence_summary.distinct_rules == 2
        assert explanation.decay is not None
        assert explanation.decision is not None
        assert explanation.decision.action == "allow"

        # Verify summary() works
        summary = explanation.summary()
        assert "fact-checker" in summary
        assert "trust:" in summary.lower() or "0." in summary

        # Verify to_dict() works
        d = explanation.to_dict()
        assert d["agent_id"] == "fact-checker"
        assert isinstance(d["projected_trust"], list)

    @pytest.mark.asyncio
    async def test_multiple_agents_independent(self) -> None:
        """Explanations for different agents are independent."""
        ledger = InMemoryEvidenceLedger()
        mgr = TrustManager(evidence_ledger=ledger)

        await mgr.register_agent("agent-a")
        await mgr.register_agent("agent-b")

        await mgr.submit_evidence(
            Evidence(agent_id="agent-a", authority_id="auth", positive=10.0, negative=0.0)
        )
        await mgr.submit_evidence(
            Evidence(agent_id="agent-b", authority_id="auth", positive=0.0, negative=10.0)
        )

        exp_a = await mgr.explain_trust("agent-a")
        exp_b = await mgr.explain_trust("agent-b")

        assert exp_a.trust_score > exp_b.trust_score
        assert exp_a.decision is not None and exp_a.decision.action == "allow"
        assert exp_b.decision is not None and exp_b.decision.action == "block"


class TestTrustAwareExplanation:
    @pytest.mark.asyncio
    async def test_trust_threshold_error_has_explanation(self) -> None:
        """@trust_aware attaches explanation to TrustThresholdError."""
        ledger = InMemoryEvidenceLedger()
        mgr = TrustManager(evidence_ledger=ledger)

        await mgr.register_agent("low-trust-agent")
        await mgr.submit_evidence(
            Evidence(agent_id="low-trust-agent", authority_id="auth", positive=0.0, negative=5.0)
        )

        @trust_aware(mgr, "low-trust-agent", threshold=0.8)
        async def protected_fn() -> str:
            return "ok"

        with pytest.raises(TrustThresholdError) as exc_info:
            await protected_fn()

        assert exc_info.value.explanation is not None
        assert exc_info.value.explanation.agent_id == "low-trust-agent"
        assert exc_info.value.explanation.decision is not None
        assert exc_info.value.explanation.decision.action == "block"


class TestSyncManagerExplanation:
    def test_sync_explain_trust(self) -> None:
        from multitrust.manager.sync import SyncTrustManager

        ledger = InMemoryEvidenceLedger()
        with SyncTrustManager(evidence_ledger=ledger) as mgr:
            mgr.register_agent("agent-1")
            mgr.submit_evidence(
                Evidence(agent_id="agent-1", authority_id="auth", positive=5.0, negative=1.0)
            )

            explanation = mgr.explain_trust("agent-1")
            assert explanation.agent_id == "agent-1"
            assert explanation.trust_score > 0.5
            assert explanation.decision is not None
