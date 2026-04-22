"""OpenAI Agents integration for MultiTrust.

Support tier: **tier-1** (supported).

Tier-1 integrations have contract tests in CI and a stable public surface.
Breaking changes go through a deprecation cycle. See ``COMPATIBILITY.md``
in the repo root for the full policy.

Requires: ``pip install openai-agents``
"""

from multitrust.integrations.openai_agents.guardrails import TrustGuardrail
from multitrust.integrations.openai_agents.tools import (
    get_trust_tool_definition,
    handle_trust_tool_call,
)

__all__ = ["TrustGuardrail", "get_trust_tool_definition", "handle_trust_tool_call"]
