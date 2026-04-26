from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

from multitrust.core.errors import InvalidOpinionError

_OPINION_EQ_TOL = 1e-9


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
        for f in fields(self):
            val = getattr(self, f.name)
            if not 0.0 <= val <= 1.0:
                raise InvalidOpinionError(f"{f.name} must be in [0, 1], got {val}")

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
        return asdict(self)

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
            abs(self.belief - other.belief) <= _OPINION_EQ_TOL
            and abs(self.disbelief - other.disbelief) <= _OPINION_EQ_TOL
            and abs(self.uncertainty - other.uncertainty) <= _OPINION_EQ_TOL
            and abs(self.base_rate - other.base_rate) <= _OPINION_EQ_TOL
        )

    def __hash__(self) -> int:
        return hash((self.belief, self.disbelief, self.uncertainty, self.base_rate))
