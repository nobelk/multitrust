"""Anthropic Claude integration for MultiTrust.

Support tier: **experimental**.

Experimental integrations ship without contract tests and may change or be
removed in any minor release. If you depend on this module, please open an
issue at https://github.com/nobelk/multitrust/issues so it can be
considered for promotion to tier-1. See ``COMPATIBILITY.md`` for the
full policy.

Requires: ``pip install anthropic``
"""

from multitrust.integrations.anthropic.hooks import TrustPostMessageHook, TrustPreMessageHook
from multitrust.integrations.anthropic.tools import (
    get_trust_tool_definition,
    handle_trust_tool_use,
)

__all__ = [
    "get_trust_tool_definition",
    "handle_trust_tool_use",
    "TrustPreMessageHook",
    "TrustPostMessageHook",
]
