from multitrust.operators.decay import time_decay
from multitrust.operators.discount import discount_opinion
from multitrust.operators.fusion import (
    averaging_fusion,
    cumulative_fusion,
    multi_source_averaging_fusion,
    multi_source_cumulative_fusion,
)
from multitrust.operators.mapping import (
    beta_to_opinion,
    evidence_to_opinion,
    opinion_to_beta_parameters,
    opinion_to_evidence,
)

__all__ = [
    "averaging_fusion",
    "beta_to_opinion",
    "cumulative_fusion",
    "discount_opinion",
    "evidence_to_opinion",
    "multi_source_averaging_fusion",
    "multi_source_cumulative_fusion",
    "opinion_to_beta_parameters",
    "opinion_to_evidence",
    "time_decay",
]
