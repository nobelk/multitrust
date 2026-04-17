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

    def __init__(self, *args: object, explanation: object | None = None) -> None:
        super().__init__(*args)
        self.explanation = explanation


class StoreError(MultiTrustError):
    """Raised when a storage operation fails."""


class ConcurrencyError(StoreError):
    """Raised when an optimistic-concurrency check fails (version mismatch)."""

    def __init__(
        self,
        message: str,
        *,
        agent_id: str | None = None,
        expected_version: int | None = None,
        actual_version: int | None = None,
    ) -> None:
        super().__init__(message)
        self.agent_id = agent_id
        self.expected_version = expected_version
        self.actual_version = actual_version


class AuthorityNotFoundError(MultiTrustError):
    """Raised when an authority cannot be found."""
