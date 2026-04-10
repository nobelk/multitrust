"""MultiTrust: A Trust Framework SDK for Multi-Agent Systems."""

__version__ = "0.1.0"

from multitrust.core.errors import (
    AgentNotFoundError,
    AuthorityNotFoundError,
    InvalidEvidenceError,
    InvalidOpinionError,
    MultiTrustError,
    StoreError,
)
from multitrust.core.evidence import Evidence, EvidenceResult
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.core.types import AgentId, AuthorityId, TrustLevel
from multitrust.evidence.collector import EvidenceCollector, RuleBasedCollector
from multitrust.evidence.rules import EvidenceRule, RuleEngine
from multitrust.integrations.generic.context import TrustContext
from multitrust.integrations.generic.decorators import collect_evidence, trust_aware
from multitrust.manager.policy import DecisionPolicy, ThresholdPolicy, TrustPolicy
from multitrust.manager.trust_authority import DistributedAuthority, TrustAuthority
from multitrust.manager.trust_manager import TrustManager
from multitrust.observability.events import (
    AgentRegisteredEvent,
    EventBus,
    EvidenceSubmittedEvent,
    TrustEvent,
    TrustUpdatedEvent,
)
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
from multitrust.storage.base import TrustStore
from multitrust.storage.memory import InMemoryTrustStore

__all__ = [
    # Version
    "__version__",
    # Core types
    "Opinion",
    "Evidence",
    "EvidenceResult",
    "TrustRecord",
    "AgentId",
    "AuthorityId",
    "TrustLevel",
    # Errors
    "MultiTrustError",
    "InvalidOpinionError",
    "InvalidEvidenceError",
    "AgentNotFoundError",
    "StoreError",
    "AuthorityNotFoundError",
    # Operators
    "cumulative_fusion",
    "averaging_fusion",
    "multi_source_averaging_fusion",
    "multi_source_cumulative_fusion",
    "discount_opinion",
    "time_decay",
    "evidence_to_opinion",
    "opinion_to_evidence",
    "opinion_to_beta_parameters",
    "beta_to_opinion",
    # Manager
    "TrustManager",
    "TrustAuthority",
    "DistributedAuthority",
    "TrustPolicy",
    "DecisionPolicy",
    "ThresholdPolicy",
    # Storage
    "TrustStore",
    "InMemoryTrustStore",
    # Evidence
    "EvidenceCollector",
    "RuleBasedCollector",
    "EvidenceRule",
    "RuleEngine",
    # Generic integrations
    "trust_aware",
    "collect_evidence",
    "TrustContext",
    # Observability
    "EventBus",
    "TrustEvent",
    "TrustUpdatedEvent",
    "EvidenceSubmittedEvent",
    "AgentRegisteredEvent",
]
