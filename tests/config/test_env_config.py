from __future__ import annotations

import pytest

from multitrust.config.defaults import (
    DEFAULT_BASE_RATE,
    DEFAULT_DECAY_HALF_LIFE,
    DEFAULT_MAX_STALE_AGE,
    DEFAULT_MIN_UNCERTAINTY,
    DEFAULT_PRIOR_WEIGHT,
    DEFAULT_TRUST_THRESHOLD,
)
from multitrust.config.settings import MultiTrustConfig


class TestFromEnvDefaults:
    def test_fallback_to_defaults_when_no_env_vars(self):
        config = MultiTrustConfig.from_env()
        assert config.enable_time_decay is False
        assert config.decay_half_life_seconds == DEFAULT_DECAY_HALF_LIFE
        assert config.default_base_rate == DEFAULT_BASE_RATE
        assert config.default_prior_weight == DEFAULT_PRIOR_WEIGHT
        assert config.min_uncertainty == DEFAULT_MIN_UNCERTAINTY
        assert config.trust_threshold == DEFAULT_TRUST_THRESHOLD
        assert config.thread_safe is False
        assert config.max_stale_age_seconds == DEFAULT_MAX_STALE_AGE


class TestFromEnvLoading:
    def test_loads_float_fields_from_env(self, monkeypatch):
        monkeypatch.setenv("MULTITRUST_DECAY_HALF_LIFE_SECONDS", "3600.0")
        monkeypatch.setenv("MULTITRUST_DEFAULT_BASE_RATE", "0.7")
        monkeypatch.setenv("MULTITRUST_DEFAULT_PRIOR_WEIGHT", "5.0")
        monkeypatch.setenv("MULTITRUST_MIN_UNCERTAINTY", "0.05")
        monkeypatch.setenv("MULTITRUST_TRUST_THRESHOLD", "0.8")
        monkeypatch.setenv("MULTITRUST_MAX_STALE_AGE_SECONDS", "1200.0")

        config = MultiTrustConfig.from_env()
        assert config.decay_half_life_seconds == 3600.0
        assert config.default_base_rate == 0.7
        assert config.default_prior_weight == 5.0
        assert config.min_uncertainty == 0.05
        assert config.trust_threshold == 0.8
        assert config.max_stale_age_seconds == 1200.0

    def test_loads_all_fields(self, monkeypatch):
        monkeypatch.setenv("MULTITRUST_ENABLE_TIME_DECAY", "true")
        monkeypatch.setenv("MULTITRUST_THREAD_SAFE", "true")
        monkeypatch.setenv("MULTITRUST_DECAY_HALF_LIFE_SECONDS", "7200.0")
        monkeypatch.setenv("MULTITRUST_DEFAULT_BASE_RATE", "0.3")
        monkeypatch.setenv("MULTITRUST_DEFAULT_PRIOR_WEIGHT", "1.5")
        monkeypatch.setenv("MULTITRUST_MIN_UNCERTAINTY", "0.02")
        monkeypatch.setenv("MULTITRUST_TRUST_THRESHOLD", "0.6")
        monkeypatch.setenv("MULTITRUST_MAX_STALE_AGE_SECONDS", "86400.0")

        config = MultiTrustConfig.from_env()
        assert config.enable_time_decay is True
        assert config.thread_safe is True
        assert config.decay_half_life_seconds == 7200.0
        assert config.default_base_rate == 0.3
        assert config.default_prior_weight == 1.5
        assert config.min_uncertainty == 0.02
        assert config.trust_threshold == 0.6
        assert config.max_stale_age_seconds == 86400.0


class TestBoolParsing:
    @pytest.mark.parametrize("value", ["true", "True", "TRUE"])
    def test_enable_time_decay_true_string(self, monkeypatch, value):
        monkeypatch.setenv("MULTITRUST_ENABLE_TIME_DECAY", value)
        config = MultiTrustConfig.from_env()
        assert config.enable_time_decay is True

    @pytest.mark.parametrize("value", ["false", "False", "FALSE"])
    def test_enable_time_decay_false_string(self, monkeypatch, value):
        monkeypatch.setenv("MULTITRUST_ENABLE_TIME_DECAY", value)
        config = MultiTrustConfig.from_env()
        assert config.enable_time_decay is False

    def test_enable_time_decay_one(self, monkeypatch):
        monkeypatch.setenv("MULTITRUST_ENABLE_TIME_DECAY", "1")
        config = MultiTrustConfig.from_env()
        assert config.enable_time_decay is True

    def test_enable_time_decay_zero(self, monkeypatch):
        monkeypatch.setenv("MULTITRUST_ENABLE_TIME_DECAY", "0")
        config = MultiTrustConfig.from_env()
        assert config.enable_time_decay is False

    @pytest.mark.parametrize("value", ["true", "1"])
    def test_thread_safe_true(self, monkeypatch, value):
        monkeypatch.setenv("MULTITRUST_THREAD_SAFE", value)
        config = MultiTrustConfig.from_env()
        assert config.thread_safe is True

    @pytest.mark.parametrize("value", ["false", "0"])
    def test_thread_safe_false(self, monkeypatch, value):
        monkeypatch.setenv("MULTITRUST_THREAD_SAFE", value)
        config = MultiTrustConfig.from_env()
        assert config.thread_safe is False


class TestInvalidValues:
    def test_invalid_float_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("MULTITRUST_DEFAULT_BASE_RATE", "not-a-number")
        with pytest.raises(ValueError):
            MultiTrustConfig.from_env()

    def test_invalid_bool_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("MULTITRUST_ENABLE_TIME_DECAY", "yes")
        with pytest.raises(ValueError):
            MultiTrustConfig.from_env()

    def test_invalid_decay_half_life_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("MULTITRUST_DECAY_HALF_LIFE_SECONDS", "abc")
        with pytest.raises(ValueError):
            MultiTrustConfig.from_env()

    def test_invalid_trust_threshold_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("MULTITRUST_TRUST_THRESHOLD", "")
        with pytest.raises(ValueError):
            MultiTrustConfig.from_env()


class TestBackwardCompatibility:
    def test_default_constructor_unchanged(self):
        config = MultiTrustConfig()
        assert config.enable_time_decay is False
        assert config.decay_half_life_seconds == DEFAULT_DECAY_HALF_LIFE
        assert config.default_base_rate == DEFAULT_BASE_RATE
        assert config.default_prior_weight == DEFAULT_PRIOR_WEIGHT
        assert config.min_uncertainty == DEFAULT_MIN_UNCERTAINTY
        assert config.trust_threshold == DEFAULT_TRUST_THRESHOLD
        assert config.thread_safe is False
        assert config.max_stale_age_seconds == DEFAULT_MAX_STALE_AGE

    def test_constructor_with_kwargs_unchanged(self):
        config = MultiTrustConfig(enable_time_decay=True, trust_threshold=0.9)
        assert config.enable_time_decay is True
        assert config.trust_threshold == 0.9
