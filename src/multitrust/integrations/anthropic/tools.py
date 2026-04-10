"""Trust tool definitions in Anthropic tool_use format."""

from __future__ import annotations

from typing import Any


def get_trust_tool_definition() -> dict[str, Any]:
    """Return an Anthropic-compatible tool definition for querying agent trust."""
    return {
        "name": "get_agent_trust",
        "description": "Query the trust score for an agent by ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "The ID of the agent to query.",
                },
                "threshold": {
                    "type": "number",
                    "description": "Optional minimum trust threshold to check against.",
                },
            },
            "required": ["agent_id"],
        },
    }


async def handle_trust_tool_use(
    manager: Any,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """Handle an Anthropic tool_use block and return a result dict.

    Args:
        manager: TrustManager instance.
        tool_input: The input dict from the tool_use block.

    Returns:
        Dict with trust_score, is_trusted, and agent_id keys.
    """
    agent_id = tool_input["agent_id"]
    threshold = float(tool_input.get("threshold", 0.5))
    trust_score = await manager.get_trust(agent_id)
    return {
        "agent_id": agent_id,
        "trust_score": trust_score,
        "is_trusted": trust_score >= threshold,
        "threshold": threshold,
    }
