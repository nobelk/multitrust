"""Property tests for `ThresholdPolicy(min_trust=, max_uncertainty=)` (Task 2.1).

The contract under test:

1. **Vacuous-opinion rejection.** Whenever `max_uncertainty < 1.0` is set, an
   opinion at maximum uncertainty (`u == 1.0`) MUST be rejected, even if the
   scalar projection happens to clear `min_trust`.
2. **Scalar-only equivalence.** With `max_uncertainty=None`, behavior must
   match the pre-Phase-2 `ThresholdPolicy(threshold=...)` contract bit-for-bit.
3. **Threshold composition.** When both gates are set, the policy allows iff
   *both* `trust >= min_trust` AND `uncertainty <= max_uncertainty`.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from multitrust import (
    Evidence,
    Opinion,
    PolicyDecision,
    ThresholdPolicy,
    TrustManager,
)
from multitrust.manager.policy import (
    REJECTION_AGENT_NOT_FOUND,
    REJECTION_TRUST_BELOW_MIN,
    REJECTION_UNCERTAINTY_ABOVE_MAX,
)


def _opinion_strategy() -> st.SearchStrategy[Opinion]:
    """Generate any valid opinion (the simplex `b + d + u == 1`)."""
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False).flatmap(
        lambda b: st.floats(min_value=0.0, max_value=1.0 - b, allow_nan=False).map(
            lambda d: Opinion(b, d, 1.0 - b - d, 0.5)
        )
    )


# ── 1. Construction equivalence ───────────────────────────────────────────────


def test_legacy_threshold_keyword_still_works():
    """Existing call sites pass `threshold=`; that contract must keep holding."""
    legacy = ThresholdPolicy(threshold=0.6)
    canonical = ThresholdPolicy(min_trust=0.6)
    positional = ThresholdPolicy(0.6)
    assert legacy == canonical == positional
    assert legacy.min_trust == legacy.threshold == 0.6
    assert legacy.max_uncertainty is None


def test_min_trust_and_threshold_together_raises():
    with pytest.raises(TypeError):
        ThresholdPolicy(min_trust=0.5, threshold=0.5)


def test_no_min_trust_raises():
    with pytest.raises(TypeError):
        ThresholdPolicy()


def test_invalid_max_uncertainty_raises():
    with pytest.raises(ValueError):
        ThresholdPolicy(min_trust=0.5, max_uncertainty=1.5)
    with pytest.raises(ValueError):
        ThresholdPolicy(min_trust=0.5, max_uncertainty=-0.1)


def test_repr_surfaces_max_uncertainty_for_explanations():
    assert "max_uncertainty" not in repr(ThresholdPolicy(0.5))
    repr_with_u = repr(ThresholdPolicy(min_trust=0.5, max_uncertainty=0.3))
    assert "min_trust=0.5" in repr_with_u
    assert "max_uncertainty=0.3" in repr_with_u


# ── 2. Vacuous-opinion rejection ──────────────────────────────────────────────


@pytest.mark.asyncio
@given(min_trust=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
@settings(max_examples=50, deadline=None)
async def test_vacuous_opinion_rejected_when_max_uncertainty_set(min_trust: float):
    """A vacuous opinion's scalar trust equals base_rate; if `min_trust <= base_rate`,
    the scalar gate would allow it. The uncertainty gate must still block.
    """
    manager = TrustManager()
    await manager.register_agent("vacuous-agent")  # default vacuous, base_rate=0.5
    policy = ThresholdPolicy(min_trust=min_trust, max_uncertainty=0.99)

    decision = await policy.evaluate(manager, "vacuous-agent")

    assert decision.allowed is False
    # If trust gate fires first (min_trust > 0.5), reason is trust; otherwise
    # uncertainty. Either way the rejection is structured, never an allow.
    assert decision.reason in (
        REJECTION_TRUST_BELOW_MIN,
        REJECTION_UNCERTAINTY_ABOVE_MAX,
    )


@pytest.mark.asyncio
async def test_vacuous_blocked_even_when_trust_clears_floor():
    """The headline guarantee: belief alone clears the floor, but we still
    refuse because we 'don't know enough'.
    """
    manager = TrustManager()
    await manager.register_agent("vacuous-agent")
    # min_trust=0.4 < base_rate=0.5, so vacuous opinion's trust=0.5 clears it.
    policy = ThresholdPolicy(min_trust=0.4, max_uncertainty=0.5)

    decision = await policy.evaluate(manager, "vacuous-agent")

    assert decision.allowed is False
    assert decision.reason == REJECTION_UNCERTAINTY_ABOVE_MAX
    assert decision.uncertainty == pytest.approx(1.0)


# ── 3. Scalar-only equivalence (Phase 1 callers see no change) ────────────────


@pytest.mark.asyncio
@given(opinion=_opinion_strategy(), min_trust=st.floats(0.0, 1.0, allow_nan=False))
@settings(max_examples=100, deadline=None)
async def test_scalar_only_matches_pre_phase_2_behavior(opinion: Opinion, min_trust: float):
    """`ThresholdPolicy(min_trust=...)` (no uncertainty gate) MUST agree with
    the bare `trust >= min_trust` check that pre-Phase-2 callers relied on.
    """
    manager = TrustManager()
    await manager.register_agent("agent-1", initial_opinion=opinion)
    policy = ThresholdPolicy(min_trust=min_trust)

    decision = await policy.evaluate(manager, "agent-1")
    expected_allow = opinion.trustworthiness >= min_trust

    assert decision.allowed is expected_allow
    if not expected_allow:
        assert decision.reason == REJECTION_TRUST_BELOW_MIN


@pytest.mark.asyncio
@given(opinion=_opinion_strategy(), min_trust=st.floats(0.0, 1.0, allow_nan=False))
@settings(max_examples=100, deadline=None)
async def test_check_returns_same_bool_as_evaluate(opinion: Opinion, min_trust: float):
    manager = TrustManager()
    await manager.register_agent("agent-1", initial_opinion=opinion)
    policy = ThresholdPolicy(min_trust=min_trust)

    bool_result = await policy.check(manager, "agent-1")
    decision = await policy.evaluate(manager, "agent-1")

    assert bool_result is decision.allowed


# ── 4. Threshold composition (both gates ↔ AND) ───────────────────────────────


@pytest.mark.asyncio
@given(
    opinion=_opinion_strategy(),
    min_trust=st.floats(0.0, 1.0, allow_nan=False),
    max_uncertainty=st.floats(0.0, 1.0, allow_nan=False),
)
@settings(max_examples=200, deadline=None)
async def test_both_thresholds_compose_as_and(
    opinion: Opinion, min_trust: float, max_uncertainty: float
):
    """Allow iff trust>=min_trust AND uncertainty<=max_uncertainty."""
    manager = TrustManager()
    await manager.register_agent("agent-1", initial_opinion=opinion)
    policy = ThresholdPolicy(min_trust=min_trust, max_uncertainty=max_uncertainty)

    decision = await policy.evaluate(manager, "agent-1")
    expected_allow = (
        opinion.trustworthiness >= min_trust and opinion.uncertainty <= max_uncertainty
    )

    assert decision.allowed is expected_allow
    if expected_allow:
        assert decision.reason is None
    else:
        # Trust check is consulted first; reason names the gate that fired.
        if opinion.trustworthiness < min_trust:
            assert decision.reason == REJECTION_TRUST_BELOW_MIN
        else:
            assert decision.reason == REJECTION_UNCERTAINTY_ABOVE_MAX


@pytest.mark.asyncio
async def test_both_thresholds_pass_returns_allowed_decision():
    manager = TrustManager()
    high_trust_low_u = Opinion(0.85, 0.05, 0.10, 0.5)
    await manager.register_agent("good-agent", initial_opinion=high_trust_low_u)
    policy = ThresholdPolicy(min_trust=0.7, max_uncertainty=0.2)

    decision = await policy.evaluate(manager, "good-agent")

    assert decision.allowed is True
    assert decision.reason is None
    assert decision.trust_score == pytest.approx(high_trust_low_u.trustworthiness)
    assert decision.uncertainty == pytest.approx(0.10)


# ── 5. is_trusted parity ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_is_trusted_with_max_uncertainty_blocks_vacuous():
    """`TrustManager.is_trusted(..., max_uncertainty=...)` mirrors the policy."""
    manager = TrustManager()
    await manager.register_agent("vacuous-agent")
    # min_trust default (0.5) clears for a vacuous opinion at base_rate=0.5,
    # but the uncertainty gate must override.
    assert await manager.is_trusted("vacuous-agent", max_uncertainty=0.5) is False
    # Without the uncertainty gate, the legacy contract holds.
    assert await manager.is_trusted("vacuous-agent", threshold=0.4) is True


@pytest.mark.asyncio
async def test_is_trusted_max_uncertainty_validation():
    manager = TrustManager()
    await manager.register_agent("agent-1")
    with pytest.raises(ValueError):
        await manager.is_trusted("agent-1", max_uncertainty=1.5)


@pytest.mark.asyncio
async def test_evaluate_unknown_agent_returns_structured_block():
    manager = TrustManager()
    policy = ThresholdPolicy(min_trust=0.5)

    decision = await policy.evaluate(manager, "no-such-agent")

    assert decision.allowed is False
    assert decision.reason == REJECTION_AGENT_NOT_FOUND
    assert decision.trust_score is None
    assert decision.uncertainty is None


@pytest.mark.asyncio
async def test_evidence_can_lift_an_agent_through_both_gates():
    """End-to-end: enough positive evidence drives uncertainty down and trust up."""
    manager = TrustManager()
    await manager.register_agent("learner")
    policy = ThresholdPolicy(min_trust=0.6, max_uncertainty=0.3)

    # Vacuous start — both gates would block.
    decision_pre = await policy.evaluate(manager, "learner")
    assert decision_pre.allowed is False

    # Submit a substantial run of positive evidence.
    for _ in range(20):
        await manager.submit_evidence(
            Evidence(agent_id="learner", authority_id="auth", positive=5.0)
        )

    decision_post = await policy.evaluate(manager, "learner")
    assert decision_post.allowed is True
    assert isinstance(decision_post, PolicyDecision)
