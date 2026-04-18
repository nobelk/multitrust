"""MCP tool definitions and dispatcher for MultiTrust.

This module exposes the :class:`TrustManager` API as a set of MCP tools
without taking a hard dependency on the ``mcp`` SDK. Each tool is described
by a JSON-schema-shaped dict (``name``, ``description``, ``inputSchema``),
and :class:`TrustMCPWrapper` dispatches incoming ``(tool_name, arguments)``
calls to the underlying manager.

Why the indirection? The MCP SDK (``mcp.server.Server``) only needs a way to
list tool definitions and call a handler — both of which are pure-Python
data. Keeping that core importable without the SDK means tests run anywhere
and the integration follows the same pattern used by the existing
``anthropic`` and ``openai_agents`` integrations.
"""

from __future__ import annotations

from typing import Any

from multitrust.core.errors import AgentNotFoundError
from multitrust.core.evidence import Evidence


class MCPToolError(Exception):
    """Raised when an MCP tool call cannot be dispatched or executed.

    The dispatcher converts unknown tool names, invalid arguments, and
    underlying ``MultiTrustError`` instances into this single error type so
    MCP clients see a consistent failure shape.
    """


def get_mcp_tool_definitions() -> list[dict[str, Any]]:
    """Return MCP tool descriptors for the trust manager surface.

    The shape matches the MCP spec's ``Tool`` object: each entry has a
    ``name``, ``description``, and ``inputSchema`` (a JSON Schema describing
    the call arguments).
    """
    return [
        {
            "name": "register_agent",
            "description": (
                "Register a new agent with a vacuous (maximum-uncertainty) trust opinion. "
                "If the agent already exists, returns the existing record unchanged."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The unique identifier for the agent.",
                    },
                },
                "required": ["agent_id"],
            },
        },
        {
            "name": "get_trust",
            "description": (
                "Return the projected trust score in [0, 1] for an agent. "
                "Raises if the agent is unknown."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The agent to query.",
                    },
                },
                "required": ["agent_id"],
            },
        },
        {
            "name": "is_trusted",
            "description": (
                "Check whether an agent's trust score meets a threshold. "
                "Unknown agents return false rather than raising."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "threshold": {
                        "type": "number",
                        "description": (
                            "Optional minimum trust threshold in [0, 1]. "
                            "Defaults to the manager's configured trust_threshold."
                        ),
                    },
                },
                "required": ["agent_id"],
            },
        },
        {
            "name": "submit_evidence",
            "description": (
                "Submit positive/negative observation counts about an agent from an authority. "
                "The manager fuses this evidence into the agent's current opinion."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "authority_id": {
                        "type": "string",
                        "description": "The source attesting to these observations.",
                    },
                    "positive": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Count of positive observations.",
                    },
                    "negative": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Count of negative observations.",
                    },
                    "rule_name": {
                        "type": "string",
                        "description": "Optional name of the rule that produced this evidence.",
                    },
                },
                "required": ["agent_id", "authority_id"],
            },
        },
        {
            "name": "rank_agents",
            "description": (
                "Return all agents (or a provided subset) ranked by trust score, descending."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "agent_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional list of agent IDs to rank. "
                            "If omitted, all known agents are ranked."
                        ),
                    },
                },
            },
        },
        {
            "name": "explain_trust",
            "description": (
                "Return a structured explanation of an agent's current trust state, "
                "including opinion, top contributors, decay info, and projected trust."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string"},
                    "threshold": {
                        "type": "number",
                        "description": "Optional threshold to include a decision verdict.",
                    },
                    "top_k_contributors": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "How many top evidence contributors to include.",
                    },
                },
                "required": ["agent_id"],
            },
        },
    ]


class TrustMCPWrapper:
    """Dispatches MCP tool calls to a :class:`TrustManager`.

    Parameters
    ----------
    manager:
        The trust manager instance. Typed as ``Any`` so the wrapper has no
        import-time dependency on the manager module's transitive imports.

    The wrapper is intentionally stateless beyond the manager handle —
    constructing it per server is cheap and keeps lifetimes explicit.
    """

    def __init__(self, manager: Any) -> None:
        self._manager = manager

    @staticmethod
    def list_tools() -> list[dict[str, Any]]:
        """Return the tool descriptors this wrapper handles."""
        return get_mcp_tool_definitions()

    @property
    def tool_names(self) -> list[str]:
        """Names of tools this wrapper can dispatch."""
        return [tool["name"] for tool in get_mcp_tool_definitions()]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Dispatch ``name`` to the matching handler with ``arguments``.

        Returns a JSON-serializable dict. Errors are normalized to
        :class:`MCPToolError` so callers don't have to special-case
        framework-specific exception types.
        """
        args: dict[str, Any] = arguments or {}
        try:
            handler = self._handlers().get(name)
            if handler is None:
                raise MCPToolError(f"Unknown MCP tool: {name!r}")
            return await handler(args)
        except MCPToolError:
            raise
        except KeyError as exc:
            # A required argument was missing from the args dict.
            raise MCPToolError(f"Missing required argument for {name!r}: {exc}") from exc
        except AgentNotFoundError as exc:
            raise MCPToolError(str(exc)) from exc

    def _handlers(self) -> dict[str, Any]:
        return {
            "register_agent": self._register_agent,
            "get_trust": self._get_trust,
            "is_trusted": self._is_trusted,
            "submit_evidence": self._submit_evidence,
            "rank_agents": self._rank_agents,
            "explain_trust": self._explain_trust,
        }

    async def _register_agent(self, args: dict[str, Any]) -> dict[str, Any]:
        agent_id = _require_str(args, "agent_id")
        record = await self._manager.register_agent(agent_id)
        return {
            "agent_id": record.agent_id,
            "trust_score": record.trustworthiness,
            "opinion": record.opinion.to_dict(),
        }

    async def _get_trust(self, args: dict[str, Any]) -> dict[str, Any]:
        agent_id = _require_str(args, "agent_id")
        trust = await self._manager.get_trust(agent_id)
        return {"agent_id": agent_id, "trust_score": trust}

    async def _is_trusted(self, args: dict[str, Any]) -> dict[str, Any]:
        agent_id = _require_str(args, "agent_id")
        threshold = args.get("threshold")
        if threshold is None:
            trusted = await self._manager.is_trusted(agent_id)
        else:
            trusted = await self._manager.is_trusted(agent_id, threshold=float(threshold))
        return {
            "agent_id": agent_id,
            "is_trusted": bool(trusted),
            "threshold": float(threshold) if threshold is not None else None,
        }

    async def _submit_evidence(self, args: dict[str, Any]) -> dict[str, Any]:
        evidence = Evidence(
            agent_id=_require_str(args, "agent_id"),
            authority_id=_require_str(args, "authority_id"),
            positive=float(args.get("positive", 0.0)),
            negative=float(args.get("negative", 0.0)),
            rule_name=args.get("rule_name"),
        )
        record = await self._manager.submit_evidence(evidence)
        return {
            "agent_id": record.agent_id,
            "trust_score": record.trustworthiness,
            "evidence_count": record.evidence_count,
            "positive_total": record.positive_total,
            "negative_total": record.negative_total,
        }

    async def _rank_agents(self, args: dict[str, Any]) -> dict[str, Any]:
        agent_ids = args.get("agent_ids")
        ranked = await self._manager.rank_agents(agent_ids)
        return {
            "ranking": [
                {"agent_id": agent_id, "trust_score": score} for agent_id, score in ranked
            ],
        }

    async def _explain_trust(self, args: dict[str, Any]) -> dict[str, Any]:
        agent_id = _require_str(args, "agent_id")
        kwargs: dict[str, Any] = {}
        if "threshold" in args and args["threshold"] is not None:
            kwargs["threshold"] = float(args["threshold"])
        if "top_k_contributors" in args and args["top_k_contributors"] is not None:
            kwargs["top_k_contributors"] = int(args["top_k_contributors"])
        explanation = await self._manager.explain_trust(agent_id, **kwargs)
        return explanation.to_dict()


def _require_str(args: dict[str, Any], key: str) -> str:
    """Pull a required string argument out of ``args`` or raise MCPToolError.

    The MCP spec lets clients send anything; we coerce defensively at the
    boundary so the manager only sees clean inputs.
    """
    if key not in args:
        raise MCPToolError(f"Missing required argument: {key!r}")
    value = args[key]
    if not isinstance(value, str) or not value:
        raise MCPToolError(f"Argument {key!r} must be a non-empty string, got {value!r}")
    return value
