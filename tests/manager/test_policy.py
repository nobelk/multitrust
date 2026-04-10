from __future__ import annotations

import pytest

from multitrust.core.types import TrustLevel
from multitrust.manager.policy import DecisionPolicy, ThresholdPolicy, TrustPolicy


class TestTrustPolicyDefaultThresholds:
    def test_classify_default_thresholds(self):
        policy = TrustPolicy()
        assert policy.classify(0.0) == TrustLevel.UNTRUSTED
        assert policy.classify(0.2) == TrustLevel.UNTRUSTED
        assert policy.classify(0.4) == TrustLevel.LOW
        assert policy.classify(0.6) == TrustLevel.MODERATE
        assert policy.classify(0.85) == TrustLevel.HIGH
        assert policy.classify(0.95) == TrustLevel.FULLY_TRUSTED

    def test_classify_edge_cases(self):
        policy = TrustPolicy()
        # Score of 0.0 is below UNTRUSTED threshold (0.2) → returns UNTRUSTED (default)
        assert policy.classify(0.0) == TrustLevel.UNTRUSTED
        # Score of 1.0 is above all thresholds → FULLY_TRUSTED
        assert policy.classify(1.0) == TrustLevel.FULLY_TRUSTED
        # Exact boundary for LOW
        assert policy.classify(0.4) == TrustLevel.LOW
        # Just below MODERATE boundary → LOW
        assert policy.classify(0.59) == TrustLevel.LOW
        # Exact boundary for MODERATE
        assert policy.classify(0.6) == TrustLevel.MODERATE


class TestTrustPolicyCustomThresholds:
    def test_classify_custom_thresholds(self):
        # Custom thresholds: shift HIGH to 0.7 instead of default 0.85
        custom = {
            TrustLevel.UNTRUSTED: 0.1,
            TrustLevel.LOW: 0.3,
            TrustLevel.MODERATE: 0.5,
            TrustLevel.HIGH: 0.7,
            TrustLevel.FULLY_TRUSTED: 0.9,
        }
        policy = TrustPolicy(thresholds=custom)
        # At 0.75, should classify as HIGH (>= 0.7) but not FULLY_TRUSTED (< 0.9)
        assert policy.classify(0.75) == TrustLevel.HIGH
        # At 0.85 with default thresholds would be HIGH, but with custom at 0.9 it's still HIGH
        assert policy.classify(0.85) == TrustLevel.HIGH
        # At 0.9 → FULLY_TRUSTED
        assert policy.classify(0.9) == TrustLevel.FULLY_TRUSTED
        # At 0.65 → MODERATE (>= 0.5, < 0.7)
        assert policy.classify(0.65) == TrustLevel.MODERATE

    def test_classify_uses_custom_not_enum_defaults(self):
        # Set HIGH threshold to 0.5 (much lower than enum value 0.85)
        custom = {
            TrustLevel.UNTRUSTED: 0.0,
            TrustLevel.LOW: 0.2,
            TrustLevel.MODERATE: 0.35,
            TrustLevel.HIGH: 0.5,
            TrustLevel.FULLY_TRUSTED: 0.8,
        }
        policy = TrustPolicy(thresholds=custom)
        # With default enum values, 0.55 would be MODERATE (0.6 threshold not met)
        # With custom, 0.55 >= 0.5 (HIGH threshold) → HIGH
        assert policy.classify(0.55) == TrustLevel.HIGH


class TestDecisionPolicy:
    def test_should_allow_above_min(self):
        policy = DecisionPolicy(min_trust=0.5)
        assert policy.should_allow(0.5) is True
        assert policy.should_allow(0.75) is True
        assert policy.should_allow(1.0) is True

    def test_should_deny_below_min(self):
        policy = DecisionPolicy(min_trust=0.5)
        assert policy.should_allow(0.49) is False
        assert policy.should_allow(0.0) is False

    def test_default_min_trust(self):
        policy = DecisionPolicy()
        assert policy.should_allow(0.5) is True
        assert policy.should_allow(0.49) is False


class TestThresholdPolicy:
    @pytest.mark.anyio
    async def test_threshold_policy_check_allows(self):
        class FakeManager:
            async def get_trust(self, agent_id: str) -> float:
                return 0.8

        policy = ThresholdPolicy(threshold=0.7)
        result = await policy.check(FakeManager(), "agent-1")
        assert result is True

    @pytest.mark.anyio
    async def test_threshold_policy_check_denies(self):
        class FakeManager:
            async def get_trust(self, agent_id: str) -> float:
                return 0.5

        policy = ThresholdPolicy(threshold=0.7)
        result = await policy.check(FakeManager(), "agent-1")
        assert result is False

    @pytest.mark.anyio
    async def test_threshold_policy_check_exact_boundary(self):
        class FakeManager:
            async def get_trust(self, agent_id: str) -> float:
                return 0.7

        policy = ThresholdPolicy(threshold=0.7)
        result = await policy.check(FakeManager(), "agent-1")
        assert result is True


class TestTrustPolicyEdgeCases:
    def test_classify_negative_score(self):
        policy = TrustPolicy()
        # Negative score is below all thresholds; best stays at initial UNTRUSTED
        assert policy.classify(-1.0) == TrustLevel.UNTRUSTED

    def test_classify_score_above_one(self):
        policy = TrustPolicy()
        # Score above 1.0 meets all thresholds → FULLY_TRUSTED
        assert policy.classify(1.5) == TrustLevel.FULLY_TRUSTED

    def test_classify_exact_boundaries_all_levels(self):
        policy = TrustPolicy()
        # Each exact threshold value should map to its own level
        assert policy.classify(0.2) == TrustLevel.UNTRUSTED
        assert policy.classify(0.4) == TrustLevel.LOW
        assert policy.classify(0.6) == TrustLevel.MODERATE
        assert policy.classify(0.85) == TrustLevel.HIGH
        assert policy.classify(0.95) == TrustLevel.FULLY_TRUSTED

    def test_classify_just_below_each_boundary(self):
        policy = TrustPolicy()
        # Just below LOW threshold → UNTRUSTED
        assert policy.classify(0.39) == TrustLevel.UNTRUSTED
        # Just below MODERATE threshold → LOW
        assert policy.classify(0.59) == TrustLevel.LOW
        # Just below HIGH threshold → MODERATE
        assert policy.classify(0.84) == TrustLevel.MODERATE
        # Just below FULLY_TRUSTED threshold → HIGH
        assert policy.classify(0.94) == TrustLevel.HIGH

    def test_classify_zero_score(self):
        policy = TrustPolicy()
        # 0.0 is below UNTRUSTED threshold (0.2) → best stays UNTRUSTED (initial value)
        assert policy.classify(0.0) == TrustLevel.UNTRUSTED

    def test_custom_thresholds_partial(self):
        # Custom thresholds with all levels at very different values
        custom = {
            TrustLevel.UNTRUSTED: 0.05,
            TrustLevel.LOW: 0.15,
            TrustLevel.MODERATE: 0.25,
            TrustLevel.HIGH: 0.5,
            TrustLevel.FULLY_TRUSTED: 0.75,
        }
        policy = TrustPolicy(thresholds=custom)
        # 0.03 is below all thresholds → UNTRUSTED (initial best)
        assert policy.classify(0.03) == TrustLevel.UNTRUSTED
        # 0.1 >= 0.05 but < 0.15 → UNTRUSTED
        assert policy.classify(0.1) == TrustLevel.UNTRUSTED
        # 0.2 >= 0.15 but < 0.25 → LOW
        assert policy.classify(0.2) == TrustLevel.LOW
        # 0.6 >= 0.5 but < 0.75 → HIGH
        assert policy.classify(0.6) == TrustLevel.HIGH
        # 0.8 >= 0.75 → FULLY_TRUSTED
        assert policy.classify(0.8) == TrustLevel.FULLY_TRUSTED


class TestDecisionPolicyEdgeCases:
    def test_should_allow_zero_threshold(self):
        policy = DecisionPolicy(min_trust=0.0)
        # 0.0 >= 0.0 → allowed
        assert policy.should_allow(0.0) is True

    def test_should_allow_one_threshold(self):
        policy = DecisionPolicy(min_trust=1.0)
        # 0.99 < 1.0 → denied
        assert policy.should_allow(0.99) is False
        # 1.0 >= 1.0 → allowed
        assert policy.should_allow(1.0) is True

    def test_should_allow_negative_score(self):
        policy = DecisionPolicy(min_trust=0.5)
        # Negative score is always below any positive threshold
        assert policy.should_allow(-0.1) is False


class TestThresholdPolicyEdgeCases:
    @pytest.mark.anyio
    async def test_threshold_policy_zero_threshold(self):
        class FakeManager:
            async def get_trust(self, agent_id: str) -> float:
                return 0.0

        policy = ThresholdPolicy(threshold=0.0)
        # 0.0 >= 0.0 → allowed
        result = await policy.check(FakeManager(), "agent-1")
        assert result is True

    @pytest.mark.anyio
    async def test_threshold_policy_high_threshold(self):
        class FakeManager:
            async def get_trust(self, agent_id: str) -> float:
                return 0.94

        policy = ThresholdPolicy(threshold=0.95)
        # 0.94 < 0.95 → denied
        result = await policy.check(FakeManager(), "agent-1")
        assert result is False

    @pytest.mark.anyio
    async def test_threshold_policy_different_agents(self):
        received_ids: list[str] = []

        class FakeManager:
            async def get_trust(self, agent_id: str) -> float:
                received_ids.append(agent_id)
                return 0.8

        policy = ThresholdPolicy(threshold=0.7)
        await policy.check(FakeManager(), "agent-alpha")
        await policy.check(FakeManager(), "agent-beta")
        # Verify the correct agent_id was passed through each time
        assert received_ids == ["agent-alpha", "agent-beta"]
