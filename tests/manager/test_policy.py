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
