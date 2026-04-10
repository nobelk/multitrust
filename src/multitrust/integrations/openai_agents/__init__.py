"""OpenAI Agents integration for MultiTrust.

Requires: pip install openai-agents
"""

from multitrust.integrations.openai_agents.guardrails import TrustGuardrail
from multitrust.integrations.openai_agents.tools import (
    get_trust_tool_definition,
    handle_trust_tool_call,
)

__all__ = ["TrustGuardrail", "get_trust_tool_definition", "handle_trust_tool_call"]
