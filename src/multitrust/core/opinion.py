from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from multitrust.core.errors import InvalidOpinionError


@dataclass(frozen=True, slots=True)
class Opinion:
    belief: float
    disbelief: float
    uncertainty: float
    base_rate: float = 0.5

    def __post_init__(self) -> None:
        total = self.belief + self.disbelief + self.uncertainty
        if abs(total - 1.0) > 1e-9:
            raise InvalidOpinionError(
                f"belief + disbelief + uncertainty must equal 1.0, got {total}"
            )
        for name, val in [
            ("belief", self.belief),
            ("disbelief", self.disbelief),
            ("uncertainty", self.uncertainty),
            ("base_rate", self.base_rate),
        ]:
            if val < 0.0 or val > 1.0:
                raise InvalidOpinionError(f"{name} must be in [0, 1], got {val}")

    @property
    def trustworthiness(self) -> float:
        return self.belief + self.uncertainty * self.base_rate

    @classmethod
    def vacuous(cls, base_rate: float = 0.5) -> Opinion:
        return cls(0.0, 0.0, 1.0, base_rate)

    @classmethod
    def dogmatic_trust(cls) -> Opinion:
        return cls(1.0, 0.0, 0.0, 0.5)

    @classmethod
    def dogmatic_distrust(cls) -> Opinion:
        return cls(0.0, 1.0, 0.0, 0.5)

    @classmethod
    def from_evidence(
        cls,
        positive: float,
        negative: float,
        prior_weight: float = 2.0,
        base_rate: float = 0.5,
    ) -> Opinion:
        W = prior_weight
        r = positive
        s = negative
        denom = r + s + W
        b = r / denom
        d = s / denom
        u = W / denom
        return cls(b, d, u, base_rate)

    def to_dict(self) -> dict[str, Any]:
        return {
            "belief": self.belief,
            "disbelief": self.disbelief,
            "uncertainty": self.uncertainty,
            "base_rate": self.base_rate,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Opinion:
        return cls(
            belief=float(d["belief"]),
            disbelief=float(d["disbelief"]),
            uncertainty=float(d["uncertainty"]),
            base_rate=float(d["base_rate"]),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Opinion):
            return NotImplemented
        return (
            abs(self.belief - other.belief) <= 1e-9
            and abs(self.disbelief - other.disbelief) <= 1e-9
            and abs(self.uncertainty - other.uncertainty) <= 1e-9
            and abs(self.base_rate - other.base_rate) <= 1e-9
        )

    def __hash__(self) -> int:
        return hash((self.belief, self.disbelief, self.uncertainty, self.base_rate))
