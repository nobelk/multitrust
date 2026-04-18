"""Model Context Protocol (MCP) integration for MultiTrust.

The core wrapper (``tools``) has no hard dependency on the ``mcp`` package
and can be imported anywhere. The optional :mod:`server` submodule wires the
wrapper into an actual MCP stdio server using the official ``mcp`` SDK and
must be imported explicitly.

Install the SDK with::

    pip install mcp
"""

from multitrust.integrations.mcp.tools import (
    MCPToolError,
    TrustMCPWrapper,
    get_mcp_tool_definitions,
)

__all__ = [
    "MCPToolError",
    "TrustMCPWrapper",
    "get_mcp_tool_definitions",
]
