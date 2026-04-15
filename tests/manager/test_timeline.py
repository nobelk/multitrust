"""Tests for trust timeline visualization."""

from __future__ import annotations

import pytest

from multitrust import (
    Evidence,
    Opinion,
    SyncTrustManager,
    TrustManager,
    TrustTimeline,
    generate_trust_timeline,
)
from multitrust.config.settings import MultiTrustConfig
from multitrust.core.errors import AgentNotFoundError

# ── generate_trust_timeline (pure function) ────────────────────────


class TestGenerateTrustTimeline:
    def test_returns_correct_number_of_points(self) -> None:
        opinion = Opinion.from_evidence(10, 2)
        tl = generate_trust_timeline(opinion, 3600.0, num_points=10)
        assert len(tl.points) == 11  # 0..10 inclusive

    def test_first_point_matches_initial_opinion(self) -> None:
        opinion = Opinion.from_evidence(8, 4)
        tl = generate_trust_timeline(opinion, 3600.0)
        first = tl.points[0]
        assert first.elapsed_seconds == 0.0
        assert first.trust_score == pytest.approx(opinion.trustworthiness)
        assert first.decay_factor == pytest.approx(1.0)

    def test_trust_decays_monotonically(self) -> None:
        opinion = Opinion(0.7, 0.1, 0.2)
        tl = generate_trust_timeline(opinion, 3600.0, num_points=20)
        trust_scores = [p.trust_score for p in tl.points]
        for i in range(1, len(trust_scores)):
            assert trust_scores[i] <= trust_scores[i - 1] + 1e-9

    def test_half_life_halves_belief_and_disbelief(self) -> None:
        opinion = Opinion(0.6, 0.2, 0.2)
        half_life = 3600.0
        tl = generate_trust_timeline(opinion, half_life, duration_seconds=half_life, num_points=1)
        # At exactly one half-life, belief and disbelief should be halved
        at_half = tl.points[-1]
        assert at_half.opinion.belief == pytest.approx(opinion.belief / 2, abs=1e-6)
        assert at_half.opinion.disbelief == pytest.approx(opinion.disbelief / 2, abs=1e-6)

    def test_default_duration_is_four_half_lives(self) -> None:
        opinion = Opinion.from_evidence(5, 5)
        half_life = 1800.0
        tl = generate_trust_timeline(opinion, half_life)
        last = tl.points[-1]
        assert last.elapsed_seconds == pytest.approx(half_life * 4)

    def test_custom_duration(self) -> None:
        opinion = Opinion.from_evidence(5, 5)
        tl = generate_trust_timeline(opinion, 3600.0, duration_seconds=7200.0, num_points=5)
        assert tl.points[-1].elapsed_seconds == pytest.approx(7200.0)

    def test_agent_id_stored(self) -> None:
        opinion = Opinion.vacuous()
        tl = generate_trust_timeline(opinion, 3600.0, agent_id="bot-7")
        assert tl.agent_id == "bot-7"

    def test_vacuous_opinion_stays_at_base_rate(self) -> None:
        """A vacuous opinion (all uncertainty) should produce constant trust = base_rate."""
        opinion = Opinion.vacuous(base_rate=0.5)
        tl = generate_trust_timeline(opinion, 3600.0, num_points=10)
        for p in tl.points:
            assert p.trust_score == pytest.approx(0.5)

    def test_decay_factor_at_known_points(self) -> None:
        opinion = Opinion.from_evidence(10, 2)
        half_life = 3600.0
        tl = generate_trust_timeline(
            opinion, half_life, duration_seconds=half_life * 2, num_points=2
        )
        # t=0: factor=1.0, t=half_life: factor=0.5, t=2*half_life: factor=0.25
        assert tl.points[0].decay_factor == pytest.approx(1.0)
        assert tl.points[1].decay_factor == pytest.approx(0.5)
        assert tl.points[2].decay_factor == pytest.approx(0.25)

    def test_high_trust_eventually_approaches_base_rate(self) -> None:
        """After many half-lives, trust should converge toward the base rate."""
        opinion = Opinion(0.9, 0.05, 0.05, base_rate=0.5)
        tl = generate_trust_timeline(opinion, 3600.0, duration_seconds=3600.0 * 20, num_points=50)
        last = tl.points[-1]
        assert last.trust_score == pytest.approx(0.5, abs=0.01)


# ── TrustTimeline.to_text() ────────────────────────────────────────


class TestTimelineText:
    def test_text_contains_agent_id(self) -> None:
        opinion = Opinion.from_evidence(10, 2)
        tl = generate_trust_timeline(opinion, 3600.0, agent_id="agent-x")
        text = tl.to_text()
        assert "agent-x" in text

    def test_text_contains_half_life(self) -> None:
        opinion = Opinion.from_evidence(10, 2)
        tl = generate_trust_timeline(opinion, 86400.0, agent_id="a")
        text = tl.to_text()
        assert "Half-life" in text

    def test_text_contains_chart_bars(self) -> None:
        opinion = Opinion.from_evidence(10, 2)
        tl = generate_trust_timeline(opinion, 3600.0, num_points=5)
        text = tl.to_text()
        assert "\u2588" in text  # full block
        assert "|" in text

    def test_text_contains_opinion_breakdown(self) -> None:
        opinion = Opinion.from_evidence(10, 2)
        tl = generate_trust_timeline(opinion, 3600.0, num_points=5)
        text = tl.to_text()
        assert "Opinion breakdown" in text
        assert "b=" in text
        assert "d=" in text
        assert "u=" in text

    def test_custom_width(self) -> None:
        opinion = Opinion.from_evidence(10, 2)
        tl = generate_trust_timeline(opinion, 3600.0, num_points=3)
        text_narrow = tl.to_text(width=20)
        text_wide = tl.to_text(width=80)
        # Wider chart should produce longer lines
        narrow_max = max(len(line) for line in text_narrow.split("\n"))
        wide_max = max(len(line) for line in text_wide.split("\n"))
        assert wide_max > narrow_max


# ── TrustTimeline.plot() ───────────────────────────────────────────


class TestTimelinePlot:
    def test_plot_raises_without_matplotlib(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """plot() should raise ImportError when matplotlib is not installed."""
        import builtins

        original_import = builtins.__import__

        def mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "matplotlib.pyplot" or name == "matplotlib":
                raise ImportError("no matplotlib")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        opinion = Opinion.from_evidence(10, 2)
        tl = generate_trust_timeline(opinion, 3600.0, num_points=3)
        with pytest.raises(ImportError, match="matplotlib"):
            tl.plot(show=False)

    def test_plot_returns_figure(self) -> None:
        """plot() should return a matplotlib Figure when matplotlib is available."""
        pytest.importorskip("matplotlib")
        import matplotlib

        matplotlib.use("Agg")  # non-interactive backend

        opinion = Opinion.from_evidence(10, 2)
        tl = generate_trust_timeline(opinion, 3600.0, num_points=5)
        fig = tl.plot(show=False)
        from matplotlib.figure import Figure

        assert isinstance(fig, Figure)
        import matplotlib.pyplot as plt

        plt.close(fig)


# ── TrustManager.trust_timeline() (async) ──────────────────────────


class TestTrustManagerTimeline:
    async def test_timeline_for_registered_agent(self) -> None:
        config = MultiTrustConfig(enable_time_decay=True, decay_half_life_seconds=3600.0)
        async with TrustManager(config=config) as m:
            await m.register_agent("a1", initial_opinion=Opinion.from_evidence(10, 2))
            tl = await m.trust_timeline("a1")
            assert tl.agent_id == "a1"
            assert tl.half_life_seconds == 3600.0
            assert len(tl.points) == 21  # default 20 + point 0

    async def test_timeline_unknown_agent_raises(self) -> None:
        async with TrustManager() as m:
            with pytest.raises(AgentNotFoundError):
                await m.trust_timeline("nonexistent")

    async def test_timeline_custom_half_life_override(self) -> None:
        config = MultiTrustConfig(decay_half_life_seconds=3600.0)
        async with TrustManager(config=config) as m:
            await m.register_agent("a1", initial_opinion=Opinion.from_evidence(5, 5))
            tl = await m.trust_timeline("a1", half_life_seconds=7200.0)
            assert tl.half_life_seconds == 7200.0

    async def test_timeline_after_evidence(self) -> None:
        config = MultiTrustConfig(enable_time_decay=True, decay_half_life_seconds=1800.0)
        async with TrustManager(config=config) as m:
            await m.register_agent("a1")
            ev = Evidence(agent_id="a1", authority_id="auth", positive=20, negative=1)
            await m.submit_evidence(ev)
            tl = await m.trust_timeline("a1")
            # Trust should start high (lots of positive evidence)
            assert tl.initial_trust > 0.8


# ── SyncTrustManager.trust_timeline() ──────────────────────────────


class TestSyncTrustManagerTimeline:
    def test_sync_timeline(self) -> None:
        config = MultiTrustConfig(decay_half_life_seconds=3600.0)
        with SyncTrustManager(config=config) as m:
            m.register_agent("s1", initial_opinion=Opinion.from_evidence(10, 2))
            tl = m.trust_timeline("s1")
            assert isinstance(tl, TrustTimeline)
            assert tl.agent_id == "s1"
            text = tl.to_text()
            assert "s1" in text


# ── _format_duration ────────────────────────────────────────────────


class TestFormatDuration:
    def test_zero(self) -> None:
        from multitrust.manager.timeline import _format_duration

        assert _format_duration(0) == "0s"

    def test_seconds(self) -> None:
        from multitrust.manager.timeline import _format_duration

        assert _format_duration(30) == "30s"

    def test_minutes(self) -> None:
        from multitrust.manager.timeline import _format_duration

        assert _format_duration(120) == "2m"

    def test_hours(self) -> None:
        from multitrust.manager.timeline import _format_duration

        assert _format_duration(7200) == "2h"

    def test_days(self) -> None:
        from multitrust.manager.timeline import _format_duration

        assert _format_duration(172800) == "2d"

    def test_fractional_hours(self) -> None:
        from multitrust.manager.timeline import _format_duration

        result = _format_duration(5400)  # 1.5 hours
        assert "h" in result
