"""MultiTrust: A Trust Framework SDK for Multi-Agent Systems."""

__version__ = "0.1.0"

from multitrust.core.errors import (
    AgentNotFoundError,
    AuthorityNotFoundError,
    ConcurrencyError,
    InvalidEvidenceError,
    InvalidOpinionError,
    MultiTrustError,
    StoreError,
    TrustThresholdError,
)
from multitrust.core.evidence import Evidence, EvidenceResult
from multitrust.core.explanation import (
    DecayInfo,
    DecisionExplanation,
    EvidenceContribution,
    EvidenceSummary,
    TrustExplanation,
    TrustProjection,
)
from multitrust.core.opinion import Opinion
from multitrust.core.trust_record import TrustRecord
from multitrust.core.types import AgentId, AuthorityId, TrustLevel
from multitrust.evidence.collector import CallbackCollector, EvidenceCollector, RuleBasedCollector
from multitrust.evidence.rules import EvidenceRule, RuleEngine
from multitrust.integrations.generic.context import TrustContext
from multitrust.integrations.generic.decorators import collect_evidence, trust_aware
from multitrust.manager.admin import ADMIN_AGENT_ID, AdminAction, TrustSnapshot
from multitrust.manager.policy import DecisionPolicy, ThresholdPolicy, TrustPolicy
from multitrust.manager.sync import SyncTrustManager
from multitrust.manager.timeline import TimelinePoint, TrustTimeline, generate_trust_timeline
from multitrust.manager.trust_authority import DistributedAuthority, TrustAuthority
from multitrust.manager.trust_manager import AUTHORITY_METADATA_FLAG, TrustManager
from multitrust.observability.events import (
    AgentRegisteredEvent,
    EventBus,
    EvidenceSubmittedEvent,
    TrustEvent,
    TrustExplainedEvent,
    TrustThresholdCrossedEvent,
    TrustUpdatedEvent,
)
from multitrust.observability.tracing import get_tracer, otel_available, trust_span
from multitrust.operators.decay import evidence_decay, time_decay
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
from multitrust.storage.base import TrustStore, VersionedTrustStore
from multitrust.storage.evidence_ledger import EvidenceLedger, EvidenceLedgerEntry
from multitrust.storage.memory import InMemoryTrustStore
from multitrust.storage.memory_ledger import InMemoryEvidenceLedger
from multitrust.storage.redis_store import RedisTrustStore
from multitrust.storage.sqlite import SQLiteTrustStore
from multitrust.storage.sqlite_ledger import SQLiteEvidenceLedger

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
    # Explanation types
    "TrustExplanation",
    "TrustProjection",
    "EvidenceContribution",
    "EvidenceSummary",
    "DecayInfo",
    "DecisionExplanation",
    # Errors
    "MultiTrustError",
    "InvalidOpinionError",
    "InvalidEvidenceError",
    "AgentNotFoundError",
    "StoreError",
    "ConcurrencyError",
    "TrustThresholdError",
    "AuthorityNotFoundError",
    # Operators
    "evidence_decay",
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
    # Timeline
    "TrustTimeline",
    "TimelinePoint",
    "generate_trust_timeline",
    # Manager
    "SyncTrustManager",
    "TrustManager",
    "TrustAuthority",
    "DistributedAuthority",
    "TrustPolicy",
    "DecisionPolicy",
    "ThresholdPolicy",
    # Admin / bulk ops
    "AdminAction",
    "TrustSnapshot",
    "ADMIN_AGENT_ID",
    "AUTHORITY_METADATA_FLAG",
    # Storage
    "TrustStore",
    "VersionedTrustStore",
    "InMemoryTrustStore",
    "SQLiteTrustStore",
    "RedisTrustStore",
    "EvidenceLedger",
    "EvidenceLedgerEntry",
    "InMemoryEvidenceLedger",
    "SQLiteEvidenceLedger",
    # Evidence
    "CallbackCollector",
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
    "TrustThresholdCrossedEvent",
    "TrustExplainedEvent",
    # Tracing
    "get_tracer",
    "otel_available",
    "trust_span",
]
