"""Unit tests for the explain_trust() API and explanation data types."""

from __future__ import annotations

import json
import time

import pytest

from multitrust.config.settings import MultiTrustConfig
from multitrust.core.errors import AgentNotFoundError
from multitrust.core.evidence import Evidence
from multitrust.core.explanation import (
    DecayInfo,
    DecisionExplanation,
    EvidenceContribution,
    EvidenceSummary,
    TrustProjection,
)
from multitrust.core.opinion import Opinion
from multitrust.core.types import TrustLevel
from multitrust.manager.trust_manager import TrustManager
from multitrust.operators.decay import time_decay
from multitrust.storage.memory_ledger import InMemoryEvidenceLedger


@pytest.fixture
def ledger() -> InMemoryEvidenceLedger:
    return InMemoryEvidenceLedger()


@pytest.fixture
async def manager_with_ledger(ledger: InMemoryEvidenceLedger) -> TrustManager:
    return TrustManager(evidence_ledger=ledger)


@pytest.fixture
async def manager_no_ledger() -> TrustManager:
    return TrustManager()


class TestExplainVacuousAgent:
    @pytest.mark.asyncio
    async def test_explain_vacuous_agent(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("fresh-agent")

        explanation = await mgr.explain_trust("fresh-agent")

        assert explanation.agent_id == "fresh-agent"
        assert explanation.trust_score == pytest.approx(0.5, abs=0.01)
        assert explanation.trust_level == TrustLevel.LOW
        assert explanation.opinion.uncertainty == pytest.approx(1.0, abs=0.01)
        assert explanation.completeness == "full"
        assert explanation.top_contributors == []
        assert explanation.evidence_summary.total_evidence_count == 0

    @pytest.mark.asyncio
    async def test_explain_nonexistent_agent(self, manager_with_ledger: TrustManager) -> None:
        with pytest.raises(AgentNotFoundError):
            await manager_with_ledger.explain_trust("no-such-agent")


class TestExplainAfterEvidence:
    @pytest.mark.asyncio
    async def test_explain_after_evidence(
        self, manager_with_ledger: TrustManager, ledger: InMemoryEvidenceLedger
    ) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(
                agent_id="agent-1",
                authority_id="validator",
                positive=5.0,
                negative=1.0,
                rule_name="ConsensusRule",
            )
        )
        await mgr.submit_evidence(
            Evidence(
                agent_id="agent-1",
                authority_id="monitor",
                positive=3.0,
                negative=2.0,
                rule_name="LatencyRule",
            )
        )

        explanation = await mgr.explain_trust("agent-1")

        assert explanation.trust_score > 0.5
        assert explanation.evidence_summary.total_evidence_count == 2
        assert explanation.evidence_summary.total_positive == 8.0
        assert explanation.evidence_summary.total_negative == 3.0
        assert explanation.evidence_summary.distinct_authorities == 2
        assert explanation.completeness == "full"

    @pytest.mark.asyncio
    async def test_current_opinion_matches_record(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="auth", positive=3.0, negative=0.5)
        )

        record = await mgr.get_agent("agent-1")
        explanation = await mgr.explain_trust("agent-1")

        assert record is not None
        assert explanation.opinion == record.opinion
        assert explanation.trust_score == pytest.approx(record.trustworthiness)


class TestProjectionHorizons:
    @pytest.mark.asyncio
    async def test_projection_horizons(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="auth", positive=5.0, negative=1.0)
        )

        explanation = await mgr.explain_trust("agent-1")

        assert len(explanation.projected_trust) == 4
        # Trust should decrease monotonically with time due to decay
        trusts = [p.projected_trust for p in explanation.projected_trust]
        for i in range(len(trusts) - 1):
            assert trusts[i] >= trusts[i + 1]

    @pytest.mark.asyncio
    async def test_custom_horizons(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")

        explanation = await mgr.explain_trust("agent-1", projection_horizons=[1800.0, 7200.0])

        assert len(explanation.projected_trust) == 2
        assert explanation.projected_trust[0].horizon_label == "30m"
        assert explanation.projected_trust[1].horizon_label == "2h"

    @pytest.mark.asyncio
    async def test_default_horizon_labels(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")

        explanation = await mgr.explain_trust("agent-1")

        labels = [p.horizon_label for p in explanation.projected_trust]
        assert labels == ["1h", "12h", "24h", "7d"]


class TestTopContributors:
    @pytest.mark.asyncio
    async def test_top_contributors_ordering(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        # Submit evidence from different authorities with different impacts
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="big-auth", positive=10.0, negative=0.0)
        )
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="small-auth", positive=1.0, negative=0.5)
        )

        explanation = await mgr.explain_trust("agent-1")

        assert len(explanation.top_contributors) >= 2
        # Should be sorted by |impact_score| descending
        impacts = [abs(c.impact_score) for c in explanation.top_contributors]
        for i in range(len(impacts) - 1):
            assert impacts[i] >= impacts[i + 1]

    @pytest.mark.asyncio
    async def test_top_contributors_without_ledger(self, manager_no_ledger: TrustManager) -> None:
        mgr = manager_no_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="auth", positive=3.0, negative=1.0)
        )

        explanation = await mgr.explain_trust("agent-1")

        assert explanation.top_contributors == []
        assert explanation.completeness == "partial"
        assert any("attribution" in lim.lower() for lim in explanation.limitations)

    @pytest.mark.asyncio
    async def test_top_k_limit(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        for i in range(10):
            await mgr.submit_evidence(
                Evidence(agent_id="agent-1", authority_id=f"auth-{i}", positive=1.0, negative=0.0)
            )

        explanation = await mgr.explain_trust("agent-1", top_k_contributors=3)
        assert len(explanation.top_contributors) <= 3


class TestPartialExplanation:
    @pytest.mark.asyncio
    async def test_partial_explanation_without_ledger(
        self, manager_no_ledger: TrustManager
    ) -> None:
        mgr = manager_no_ledger
        await mgr.register_agent("agent-1")

        explanation = await mgr.explain_trust("agent-1")

        assert explanation.completeness == "partial"
        assert len(explanation.limitations) > 0

    @pytest.mark.asyncio
    async def test_evicted_ledger_marks_windowed_results(self) -> None:
        ledger = InMemoryEvidenceLedger(max_entries_per_agent=5)
        mgr = TrustManager(evidence_ledger=ledger)
        await mgr.register_agent("agent-1")

        for _i in range(10):
            await mgr.submit_evidence(
                Evidence(agent_id="agent-1", authority_id="auth", positive=1.0, negative=0.0)
            )

        explanation = await mgr.explain_trust("agent-1")
        assert any("windowed" in lim.lower() for lim in explanation.limitations)


class TestDecayInfo:
    @pytest.mark.asyncio
    async def test_decay_info_accuracy(self) -> None:
        config = MultiTrustConfig(enable_time_decay=True, decay_half_life_seconds=86400.0)
        mgr = TrustManager(config=config, evidence_ledger=InMemoryEvidenceLedger())
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="auth", positive=5.0, negative=1.0)
        )

        explanation = await mgr.explain_trust("agent-1")

        assert explanation.decay.enabled is True
        assert explanation.decay.half_life_seconds == 86400.0
        assert explanation.decay.current_decay_factor <= 1.0
        assert explanation.decay.current_decay_factor > 0.0

        # Verify the decayed opinion matches time_decay
        record = await mgr.get_agent("agent-1")
        assert record is not None
        elapsed = explanation.decay.seconds_since_last_update
        expected_decayed = time_decay(record.opinion, elapsed, 86400.0)
        assert explanation.decay.opinion_if_decayed_now.belief == pytest.approx(
            expected_decayed.belief, abs=0.01
        )

    @pytest.mark.asyncio
    async def test_decay_disabled(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")

        explanation = await mgr.explain_trust("agent-1")
        assert explanation.decay.enabled is False
        assert explanation.decay.current_decay_factor == 1.0


class TestDecisionExplanation:
    @pytest.mark.asyncio
    async def test_decision_allow(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="auth", positive=10.0, negative=0.0)
        )

        explanation = await mgr.explain_trust("agent-1", threshold=0.3)

        assert explanation.decision is not None
        assert explanation.decision.action == "allow"
        assert explanation.decision.margin is not None
        assert explanation.decision.margin > 0

    @pytest.mark.asyncio
    async def test_decision_block(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="auth", positive=0.0, negative=5.0)
        )

        explanation = await mgr.explain_trust("agent-1", threshold=0.8)

        assert explanation.decision is not None
        assert explanation.decision.action == "block"
        assert explanation.decision.margin is not None
        assert explanation.decision.margin < 0

    @pytest.mark.asyncio
    async def test_evidence_needed_estimation(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="auth", positive=1.0, negative=2.0)
        )

        explanation = await mgr.explain_trust("agent-1", threshold=0.7)

        assert explanation.decision is not None
        assert explanation.decision.action == "block"
        # evidence_needed should be a positive number
        if explanation.decision.evidence_needed is not None:
            assert explanation.decision.evidence_needed > 0


class TestSerialization:
    @pytest.mark.asyncio
    async def test_to_dict_roundtrip(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(agent_id="agent-1", authority_id="auth", positive=3.0, negative=1.0)
        )

        explanation = await mgr.explain_trust("agent-1")
        d = explanation.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["agent_id"] == "agent-1"
        assert "opinion" in parsed
        assert "trust_score" in parsed
        assert "projected_trust" in parsed
        assert isinstance(parsed["projected_trust"], list)
        assert "evidence_summary" in parsed
        assert "decay" in parsed

    @pytest.mark.asyncio
    async def test_summary_format(self, manager_with_ledger: TrustManager) -> None:
        mgr = manager_with_ledger
        await mgr.register_agent("agent-1")
        await mgr.submit_evidence(
            Evidence(
                agent_id="agent-1",
                authority_id="validator",
                positive=5.0,
                negative=1.0,
                rule_name="ConsensusRule",
            )
        )

        explanation = await mgr.explain_trust("agent-1")
        summary = explanation.summary()

        assert isinstance(summary, str)
        assert "agent-1" in summary
        assert "trust:" in summary.lower() or "trust" in summary.lower()
        assert len(summary) > 0


class TestExplanationDataclasses:
    def test_trust_projection_to_dict(self) -> None:
        proj = TrustProjection(
            horizon_label="1h",
            elapsed_seconds=3600.0,
            projected_opinion=Opinion.vacuous(),
            projected_trust=0.5,
        )
        d = proj.to_dict()
        assert d["horizon_label"] == "1h"
        assert d["elapsed_seconds"] == 3600.0

    def test_evidence_contribution_to_dict(self) -> None:
        ec = EvidenceContribution(
            authority_id="auth",
            rule_name="TestRule",
            positive_total=5.0,
            negative_total=1.0,
            evidence_count=3,
            last_submitted=time.time(),
            impact_score=0.3,
            impact_method="heuristic",
        )
        d = ec.to_dict()
        assert d["authority_id"] == "auth"
        assert d["impact_method"] == "heuristic"

    def test_evidence_summary_to_dict(self) -> None:
        es = EvidenceSummary(
            total_evidence_count=10,
            total_positive=8.0,
            total_negative=2.0,
            distinct_authorities=3,
            distinct_rules=2,
            earliest_evidence=1000.0,
            latest_evidence=2000.0,
        )
        d = es.to_dict()
        assert d["total_evidence_count"] == 10
        assert d["distinct_authorities"] == 3

    def test_decay_info_to_dict(self) -> None:
        di = DecayInfo(
            enabled=True,
            half_life_seconds=86400.0,
            seconds_since_last_update=3600.0,
            current_decay_factor=0.97,
            opinion_if_decayed_now=Opinion.vacuous(),
            trust_if_decayed_now=0.5,
        )
        d = di.to_dict()
        assert d["enabled"] is True
        assert d["half_life_seconds"] == 86400.0

    def test_decision_explanation_to_dict(self) -> None:
        de = DecisionExplanation(
            action="allow",
            basis="threshold",
            threshold=0.5,
            trust_score=0.7,
            margin=0.2,
            policy_name="TrustManager.is_trusted",
        )
        d = de.to_dict()
        assert d["action"] == "allow"
        assert d["margin"] == 0.2
