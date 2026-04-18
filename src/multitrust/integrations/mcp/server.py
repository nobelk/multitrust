"""Optional MCP stdio server for MultiTrust.

Importing this module requires the ``mcp`` package. The core wrapper in
:mod:`multitrust.integrations.mcp.tools` does not.

Typical usage::

    from multitrust import TrustManager
    from multitrust.integrations.mcp.server import build_server, run_stdio

    async def main() -> None:
        async with TrustManager() as mgr:
            await run_stdio(mgr)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from multitrust.integrations.mcp.tools import MCPToolError, TrustMCPWrapper

if TYPE_CHECKING:
    from mcp.server import Server


def _import_mcp() -> Any:
    """Import the optional ``mcp`` SDK and raise a clear error if missing."""
    try:
        import mcp  # noqa: F401
        from mcp import types as mcp_types
        from mcp.server import Server
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise ImportError(
            "The 'mcp' package is required to run the MCP server. Install it with: pip install mcp"
        ) from exc
    return Server, mcp_types


def build_server(manager: Any, *, name: str = "multitrust") -> Server:
    """Build an MCP :class:`mcp.server.Server` wired to ``manager``.

    The returned server registers list-tools and call-tool handlers that
    delegate to :class:`TrustMCPWrapper`. Tool results are returned as a
    single text content block containing JSON, which is the MCP-idiomatic
    way to ship structured payloads.
    """
    Server, mcp_types = _import_mcp()
    wrapper = TrustMCPWrapper(manager)
    server = Server(name)

    @server.list_tools()  # type: ignore[no-untyped-call,misc]
    async def _list_tools() -> list[Any]:
        return [
            mcp_types.Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in wrapper.list_tools()
        ]

    @server.call_tool()  # type: ignore[no-untyped-call,misc]
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> list[Any]:
        try:
            result = await wrapper.call_tool(name, arguments)
            return [mcp_types.TextContent(type="text", text=json.dumps(result, default=str))]
        except MCPToolError as exc:
            return [mcp_types.TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    return server


async def run_stdio(manager: Any, *, name: str = "multitrust") -> None:
    """Run the MultiTrust MCP server over stdio until the client disconnects."""
    _, _ = _import_mcp()
    from mcp.server.stdio import stdio_server

    server = build_server(manager, name=name)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
