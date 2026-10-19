"""TIAGo House-Errand Bot – FastMCP server entry point.

Import `tiago_mcp` from this module to use it as an in-process MCP server
inside LangGraph, or run this file directly to start a standalone stdio server.
"""

from tiago_mcp.tools.tiago_tools import tiago_mcp  # noqa: F401  (re-exported)

__all__ = ["tiago_mcp"]

if __name__ == "__main__":
    tiago_mcp.run()
