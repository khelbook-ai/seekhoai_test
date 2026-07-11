"""MCP server skeleton (spec 05 §2/§3).

Exposes the stubbed extractor catalog over MCP so agents call tools the same way
now (stubs) and later (real). Run standalone:  python -m app.mcp.server

Phase 0: registers each tool with its stub. Phase 2 swaps the stub bodies in
app/mcp/tools.py for real extraction — no change needed here.
"""
from __future__ import annotations

from app.mcp.tools import TOOLS


def build_server():
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("seekhai-tools")
    for name, fn in TOOLS.items():
        server.tool(name=name)(fn)
    return server


if __name__ == "__main__":
    build_server().run()
