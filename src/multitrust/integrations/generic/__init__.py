"""Generic framework-agnostic integrations."""

from multitrust.integrations.generic.context import TrustContext
from multitrust.integrations.generic.decorators import collect_evidence, trust_aware

__all__ = ["trust_aware", "collect_evidence", "TrustContext"]
