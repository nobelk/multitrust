"""Tests for explain_trust() — Phase 2 / Task 2.3 deltas + JSON shape snapshot."""

from __future__ import annotations

import time

import pytest

from multitrust.core.evidence import Evidence
from multitrust.core.explanation import (
    ContributorChange,
    OpinionDelta,
    TrustExplanation,
)
from multitrust.manager.trust_manager import (
    DEFAULT_EXPLAIN_LOOKBACK_SECONDS,
    TrustManager,
)
from multitrust.storage.memory_ledger import InMemoryEvidenceLedger

# ---------------------------------------------------------------------------
# delta_over_time / contributor_diff: present-when-ledger semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delta_fields_none_without_ledger() -> None:
    """No ledger configured → both delta fields stay None and a limitation is set."""
    mgr = TrustManager()
    await mgr.register_agent("a")
    await mgr.submit_evidence(
        Evidence(agent_id="a", authority_id="auth", positive=2.0, negative=0.0)
    )
    explanation = await mgr.explain_trust("a")
    assert explanation.delta_over_time is None
    assert explanation.contributor_diff is None
    assert explanation.completeness == "partial"
    assert any("ledger" in lim.lower() for lim in explanation.limitations)


@pytest.mark.asyncio
async def test_delta_populated_with_ledger() -> None:
    """Ledger present → delta_over_time and contributor_diff are populated."""
    ledger = InMemoryEvidenceLedger()
    mgr = TrustManager(evidence_ledger=ledger)
    await mgr.register_agent("a")
    await mgr.submit_evidence(
        Evidence(
            agent_id="a",
            authority_id="orchestrator",
            positive=4.0,
            negative=1.0,
            rule_name="ConsensusRule",
        )
    )
    await mgr.submit_evidence(
        Evidence(
            agent_id="a",
            authority_id="monitor",
            positive=2.0,
            negative=0.0,
            rule_name="LatencyRule",
        )
    )

    explanation = await mgr.explain_trust("a")

    assert explanation.delta_over_time is not None
    assert isinstance(explanation.delta_over_time, OpinionDelta)
    assert explanation.delta_over_time.evidence_count_delta == 2
    assert explanation.delta_over_time.lookback_seconds == DEFAULT_EXPLAIN_LOOKBACK_SECONDS
    # Trust moved up because the agent received mostly-positive evidence
    # within the window from a vacuous start.
    assert explanation.delta_over_time.trust_delta > 0

    assert explanation.contributor_diff is not None
    assert len(explanation.contributor_diff) == 2
    keys = {(c.authority_id, c.rule_name) for c in explanation.contributor_diff}
    assert keys == {("orchestrator", "ConsensusRule"), ("monitor", "LatencyRule")}
    # Sorted by total movement, descending.
    totals = [c.positive_delta + c.negative_delta for c in explanation.contributor_diff]
    assert totals == sorted(totals, reverse=True)


@pytest.mark.asyncio
async def test_lookback_splits_pre_window_evidence() -> None:
    """Evidence older than the lookback window is anchored as `from_opinion`."""
    ledger = InMemoryEvidenceLedger()
    mgr = TrustManager(evidence_ledger=ledger)
    await mgr.register_agent("a")

    # Two batches of evidence — one "old" (1 hour ago), one "now".
    now = time.time()
    await mgr.submit_evidence(
        Evidence(
            agent_id="a",
            authority_id="auth",
            positive=10.0,
            negative=0.0,
            timestamp=now - 3600,
        )
    )
    await mgr.submit_evidence(
        Evidence(
            agent_id="a",
            authority_id="auth",
            positive=0.0,
            negative=5.0,
            timestamp=now,
        )
    )

    # 30-minute window: only the "now" entry falls inside.
    explanation = await mgr.explain_trust("a", lookback=1800.0)
    assert explanation.delta_over_time is not None
    assert explanation.delta_over_time.evidence_count_delta == 1
    # `from_opinion` should reflect the 10/0 pre-window evidence (high trust);
    # `to_opinion` reflects the fused 10/5 (lower trust). So trust dropped.
    assert explanation.delta_over_time.trust_delta < 0


@pytest.mark.asyncio
async def test_lookback_validation() -> None:
    """`lookback <= 0` raises ValueError before any ledger work."""
    mgr = TrustManager()
    await mgr.register_agent("a")
    with pytest.raises(ValueError, match="lookback must be > 0"):
        await mgr.explain_trust("a", lookback=0)
    with pytest.raises(ValueError, match="lookback must be > 0"):
        await mgr.explain_trust("a", lookback=-5)


@pytest.mark.asyncio
async def test_empty_ledger_yields_zero_deltas() -> None:
    """Registered agent + zero evidence → from_opinion is vacuous, all deltas 0."""
    ledger = InMemoryEvidenceLedger()
    mgr = TrustManager(evidence_ledger=ledger)
    await mgr.register_agent("a")

    explanation = await mgr.explain_trust("a")
    assert explanation.delta_over_time is not None
    assert explanation.delta_over_time.evidence_count_delta == 0
    assert explanation.delta_over_time.belief_delta == 0.0
    assert explanation.delta_over_time.disbelief_delta == 0.0
    assert explanation.delta_over_time.uncertainty_delta == 0.0
    assert explanation.delta_over_time.trust_delta == 0.0
    assert explanation.contributor_diff == []


@pytest.mark.asyncio
async def test_all_evidence_pre_window_is_quiet_window() -> None:
    """All evidence older than the lookback → from_opinion ≈ to_opinion, no movers."""
    ledger = InMemoryEvidenceLedger()
    mgr = TrustManager(evidence_ledger=ledger)
    await mgr.register_agent("a")

    now = time.time()
    await mgr.submit_evidence(
        Evidence(
            agent_id="a",
            authority_id="auth",
            positive=4.0,
            negative=1.0,
            timestamp=now - 7200,
        )
    )

    # 30-minute window: nothing falls inside.
    explanation = await mgr.explain_trust("a", lookback=1800.0)
    assert explanation.delta_over_time is not None
    assert explanation.delta_over_time.evidence_count_delta == 0
    # `from_opinion` reconstructs from the pre-window 4/1; `to_opinion`
    # is the live opinion (also driven by the same 4/1) — equal up to
    # floating-point.
    assert explanation.delta_over_time.trust_delta == pytest.approx(0.0, abs=1e-9)
    assert explanation.contributor_diff == []


@pytest.mark.asyncio
async def test_lookback_longer_than_history() -> None:
    """Lookback > age of oldest entry → all evidence falls inside the window."""
    ledger = InMemoryEvidenceLedger()
    mgr = TrustManager(evidence_ledger=ledger)
    await mgr.register_agent("a")
    await mgr.submit_evidence(
        Evidence(agent_id="a", authority_id="auth", positive=8.0, negative=0.0)
    )

    explanation = await mgr.explain_trust("a", lookback=10 * 86400.0)
    assert explanation.delta_over_time is not None
    assert explanation.delta_over_time.evidence_count_delta == 1
    # `from_opinion` is the configured-base-rate vacuous opinion (no
    # pre-window evidence to reconstruct from).
    assert explanation.delta_over_time.from_opinion.belief == 0.0
    assert explanation.delta_over_time.from_opinion.uncertainty == 1.0


@pytest.mark.asyncio
async def test_discounted_opinion_in_window_records_limitation() -> None:
    """`submit_discounted_opinion` writes a ledger entry not reflected in from_opinion."""
    from multitrust.core.opinion import Opinion

    ledger = InMemoryEvidenceLedger()
    mgr = TrustManager(evidence_ledger=ledger)
    await mgr.register_agent("a")
    discounted = Opinion(belief=0.7, disbelief=0.1, uncertainty=0.2, base_rate=0.5)
    await mgr.submit_discounted_opinion("a", discounted, positive=3.0, negative=1.0)

    explanation = await mgr.explain_trust("a")
    assert any("discounted" in lim.lower() for lim in explanation.limitations)


@pytest.mark.asyncio
async def test_contributor_change_dataclass_frozen() -> None:
    """ContributorChange is frozen — protects against accidental mutation."""
    cc = ContributorChange(
        authority_id="auth",
        rule_name="rule",
        positive_delta=1.0,
        negative_delta=0.0,
        evidence_count_delta=1,
    )
    with pytest.raises((AttributeError, TypeError)):
        cc.positive_delta = 99.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# JSON-shape snapshot — additive change must not rename or remove fields.
# Keep the assertions on *keys*, not values, so unrelated computation
# changes do not break the snapshot.
# ---------------------------------------------------------------------------

EXPECTED_TOP_LEVEL_KEYS = {
    "agent_id",
    "timestamp",
    "completeness",
    "limitations",
    "opinion",
    "trust_score",
    "trust_level",
    "projected_trust",
    "top_contributors",
    "evidence_summary",
    "decay",
    "decision",
    "delta_over_time",
    "contributor_diff",
}


@pytest.mark.asyncio
async def test_to_dict_keys_stable() -> None:
    ledger = InMemoryEvidenceLedger()
    mgr = TrustManager(evidence_ledger=ledger)
    await mgr.register_agent("a")
    await mgr.submit_evidence(
        Evidence(agent_id="a", authority_id="auth", positive=3.0, negative=1.0)
    )

    payload = (await mgr.explain_trust("a")).to_dict()
    assert set(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS

    delta = payload["delta_over_time"]
    assert delta is not None
    assert set(delta.keys()) == {
        "from_opinion",
        "to_opinion",
        "belief_delta",
        "disbelief_delta",
        "uncertainty_delta",
        "trust_delta",
        "lookback_seconds",
        "evidence_count_delta",
    }

    diff = payload["contributor_diff"]
    assert diff is not None and len(diff) >= 1
    assert set(diff[0].keys()) == {
        "authority_id",
        "rule_name",
        "positive_delta",
        "negative_delta",
        "evidence_count_delta",
    }


@pytest.mark.asyncio
async def test_to_dict_keys_present_when_no_ledger() -> None:
    """Even without a ledger, the new keys appear (with None values)."""
    mgr = TrustManager()
    await mgr.register_agent("a")
    payload = (await mgr.explain_trust("a")).to_dict()
    assert set(payload.keys()) == EXPECTED_TOP_LEVEL_KEYS
    assert payload["delta_over_time"] is None
    assert payload["contributor_diff"] is None


# ---------------------------------------------------------------------------
# summary() surfaces deltas
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_mentions_delta_when_present() -> None:
    ledger = InMemoryEvidenceLedger()
    mgr = TrustManager(evidence_ledger=ledger)
    await mgr.register_agent("a")
    await mgr.submit_evidence(
        Evidence(agent_id="a", authority_id="auth", positive=5.0, negative=0.0, rule_name="r")
    )
    explanation = await mgr.explain_trust("a")
    text = explanation.summary()
    assert "Change over last" in text
    assert "Top movers in window" in text


@pytest.mark.asyncio
async def test_summary_no_delta_section_when_absent() -> None:
    mgr = TrustManager()
    await mgr.register_agent("a")
    text = (await mgr.explain_trust("a")).summary()
    assert "Change over last" not in text
    assert "Top movers" not in text


# ---------------------------------------------------------------------------
# Sync facade exposes lookback
# ---------------------------------------------------------------------------


def test_sync_manager_explain_trust_accepts_lookback() -> None:
    from multitrust.manager.sync import SyncTrustManager

    mgr = SyncTrustManager()
    mgr.register_agent("a")
    mgr.submit_evidence(Evidence(agent_id="a", authority_id="auth", positive=1.0, negative=0.0))
    # No ledger → fields are None but lookback validation still runs.
    explanation = mgr.explain_trust("a", lookback=60.0)
    assert isinstance(explanation, TrustExplanation)
    assert explanation.delta_over_time is None
