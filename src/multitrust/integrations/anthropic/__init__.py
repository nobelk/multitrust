"""Anthropic Claude integration for MultiTrust.

Requires: pip install anthropic
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
