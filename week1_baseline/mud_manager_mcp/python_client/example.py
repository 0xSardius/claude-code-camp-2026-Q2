# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp==1.28.1"]
# ///
"""Python MCP client example for mud_manager_mcp -- see
docs/plans/mud_manager_mcp. A single-file demo script (PEP 723 inline
dependency metadata, run via `uv run example.py`) rather than a full
uv/pyproject.toml package like the boukensha ports -- there's no
importable module here, just one script proving the round trip, so the
usual package scaffolding would be pure ceremony.

Connects to the mud_manager_mcp server (must already be running --
bin/mud_manager_mcp_server), lists the available tools, then walks through
connect -> look -> consider -> mud_status, printing each tool's real MUD
response. Deliberately does NOT wire MCP into boukensha's own
Registry/Tool classes -- that integration is a separate follow-up, not
required to prove this server works.
"""
import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError

SERVER_URL = "http://localhost:8000/"


async def call_tool(session: ClientSession, name: str, **arguments) -> str:
    # A server-side tool error (e.g. the MUD connection dropped mid-call)
    # surfaces as an MCP-protocol-level error, not a normal CallToolResult
    # -- session.call_tool() raises McpError rather than returning
    # gracefully. Without this, an uncaught McpError crashes the whole
    # script with a raw traceback instead of printing a readable message
    # and letting the demo continue. Found by code review.
    try:
        result = await session.call_tool(name, arguments)
    except McpError as e:
        return f"[mcp error] {e}"
    return "\n".join(block.text for block in result.content if hasattr(block, "text"))


async def main() -> None:
    async with streamable_http_client(SERVER_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Available tools ({len(tools.tools)}): {[t.name for t in tools.tools]}")
            print()

            print("=== mud_status ===")
            print(await call_tool(session, "mud_status"))
            print()

            print("=== look ===")
            print(await call_tool(session, "look"))
            print()

            print("=== check (score) ===")
            print(await call_tool(session, "check", kind="score"))
            print()


if __name__ == "__main__":
    asyncio.run(main())
