"""Google ADK integration for MultiTrust.

Support tier: **experimental**.

Experimental integrations ship without contract tests and may change or be
removed in any minor release. If you depend on this module, please open an
issue at https://github.com/nobelk/multitrust/issues so it can be
considered for promotion to tier-1. See ``COMPATIBILITY.md`` for the
full policy.

Requires: ``pip install google-adk``
"""

from multitrust.integrations.google_adk.callbacks import (
    TrustAfterAgentCallback,
    TrustBeforeAgentCallback,
)

__all__ = ["TrustBeforeAgentCallback", "TrustAfterAgentCallback"]
