from __future__ import annotations


class MultiTrustError(Exception):
    """Base exception for all MultiTrust errors."""


class InvalidOpinionError(MultiTrustError):
    """Raised when an opinion has invalid values."""


class InvalidEvidenceError(MultiTrustError):
    """Raised when evidence has invalid values."""


class AgentNotFoundError(MultiTrustError):
    """Raised when an agent cannot be found."""


class TrustThresholdError(MultiTrustError):
    """Raised when an agent's trust is below the required threshold for an action."""


class StoreError(MultiTrustError):
    """Raised when a storage operation fails."""


class AuthorityNotFoundError(MultiTrustError):
    """Raised when an authority cannot be found."""
