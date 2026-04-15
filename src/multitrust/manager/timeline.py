"""Trust timeline visualization for decay curve analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass

from multitrust.core.opinion import Opinion
from multitrust.operators.decay import time_decay


@dataclass(frozen=True, slots=True)
class TimelinePoint:
    """A single point on a trust decay timeline."""

    elapsed_seconds: float
    label: str
    opinion: Opinion
    trust_score: float
    decay_factor: float


@dataclass(frozen=True, slots=True)
class TrustTimeline:
    """Complete trust decay timeline for an agent."""

    agent_id: str
    initial_opinion: Opinion
    initial_trust: float
    half_life_seconds: float
    points: list[TimelinePoint]

    def to_text(self, *, width: int = 60) -> str:
        """Render the timeline as a text-based ASCII chart.

        Parameters
        ----------
        width:
            Width of the bar chart area in characters.
        """
        lines: list[str] = []
        lines.append(f"Trust Timeline: {self.agent_id}")
        lines.append(f"Half-life: {_format_duration(self.half_life_seconds)}")
        lines.append(
            f"Initial: trust={self.initial_trust:.3f}  "
            f"b={self.initial_opinion.belief:.3f}  "
            f"d={self.initial_opinion.disbelief:.3f}  "
            f"u={self.initial_opinion.uncertainty:.3f}"
        )
        lines.append("")

        # Header
        label_width = max(len(p.label) for p in self.points)
        header = f"{'Time':<{label_width}}  {'Trust':>6}  {'Decay%':>6}  Chart"
        lines.append(header)
        lines.append("-" * (label_width + 8 + 8 + width + 2))

        for p in self.points:
            bar_len = round(p.trust_score * width)
            bar = "\u2588" * bar_len + "\u2591" * (width - bar_len)
            decay_pct = (1.0 - p.decay_factor) * 100
            lines.append(
                f"{p.label:<{label_width}}  {p.trust_score:6.3f}  {decay_pct:5.1f}%  |{bar}|"
            )

        # Footer with opinion components at key points
        lines.append("")
        lines.append("Opinion breakdown (belief / disbelief / uncertainty):")
        step = max(1, len(self.points) // 5)
        for i in range(0, len(self.points), step):
            p = self.points[i]
            lines.append(
                f"  {p.label}: "
                f"b={p.opinion.belief:.3f}  "
                f"d={p.opinion.disbelief:.3f}  "
                f"u={p.opinion.uncertainty:.3f}"
            )
        # Always include the last point
        last = self.points[-1]
        if len(self.points) % step != 1:
            lines.append(
                f"  {last.label}: "
                f"b={last.opinion.belief:.3f}  "
                f"d={last.opinion.disbelief:.3f}  "
                f"u={last.opinion.uncertainty:.3f}"
            )

        return "\n".join(lines)

    def plot(self, *, show: bool = True) -> object:
        """Render the timeline as a matplotlib chart.

        Returns the matplotlib Figure object. Raises ImportError if
        matplotlib is not installed.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib is required for plot(). Install it with: pip install matplotlib"
            ) from None

        hours = [p.elapsed_seconds / 3600 for p in self.points]
        trust = [p.trust_score for p in self.points]
        belief = [p.opinion.belief for p in self.points]
        disbelief = [p.opinion.disbelief for p in self.points]
        uncertainty = [p.opinion.uncertainty for p in self.points]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)

        # Top: trust score
        ax1.plot(hours, trust, "b-", linewidth=2, label="Trust score")
        ax1.axhline(y=0.5, color="r", linestyle="--", alpha=0.5, label="Default threshold")
        hl_hours = self.half_life_seconds / 3600
        ax1.axvline(x=hl_hours, color="gray", linestyle=":", alpha=0.5, label="Half-life")
        ax1.set_ylabel("Trust Score")
        ax1.set_title(f"Trust Decay Timeline: {self.agent_id}")
        ax1.legend(loc="upper right")
        ax1.set_ylim(-0.05, 1.05)
        ax1.grid(True, alpha=0.3)

        # Bottom: opinion components
        ax2.stackplot(
            hours,
            belief,
            disbelief,
            uncertainty,
            labels=["Belief", "Disbelief", "Uncertainty"],
            colors=["#2ecc71", "#e74c3c", "#95a5a6"],
            alpha=0.7,
        )
        ax2.set_xlabel("Time (hours)")
        ax2.set_ylabel("Opinion Components")
        ax2.legend(loc="upper right")
        ax2.set_ylim(0, 1.05)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        if show:
            plt.show()
        return fig


def generate_trust_timeline(
    opinion: Opinion,
    half_life_seconds: float,
    *,
    agent_id: str = "agent",
    duration_seconds: float | None = None,
    num_points: int = 20,
) -> TrustTimeline:
    """Generate a trust decay timeline from a starting opinion.

    Parameters
    ----------
    opinion:
        The starting opinion to decay.
    half_life_seconds:
        Decay half-life in seconds.
    agent_id:
        Label for the agent.
    duration_seconds:
        Total duration to simulate. Defaults to 4x the half-life.
    num_points:
        Number of sample points along the timeline.
    """
    if duration_seconds is None:
        duration_seconds = half_life_seconds * 4.0

    initial_trust = opinion.trustworthiness

    points: list[TimelinePoint] = []
    for i in range(num_points + 1):
        elapsed = (i / num_points) * duration_seconds
        decayed = time_decay(opinion, elapsed, half_life_seconds)
        decay_factor = math.exp(-math.log(2) * elapsed / half_life_seconds)
        points.append(
            TimelinePoint(
                elapsed_seconds=elapsed,
                label=_format_duration(elapsed),
                opinion=decayed,
                trust_score=decayed.trustworthiness,
                decay_factor=decay_factor,
            )
        )

    return TrustTimeline(
        agent_id=agent_id,
        initial_opinion=opinion,
        initial_trust=initial_trust,
        half_life_seconds=half_life_seconds,
        points=points,
    )


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds == 0:
        return "0s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m" if minutes % 1 else f"{minutes:.0f}m"
    if seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.1f}h" if hours % 1 else f"{hours:.0f}h"
    days = seconds / 86400
    return f"{days:.1f}d" if days % 1 else f"{days:.0f}d"
