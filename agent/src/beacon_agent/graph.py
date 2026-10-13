"""Beacon Agent graph for deployment with Smart Home MCP tools."""

from __future__ import annotations

import ast
import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool, tool
from langchain_google_genai import ChatGoogleGenerativeAI

# Preload jsonschema and its specification registry at import time (outside the async event loop).
# This avoids blockbuster.BlockingError when mcp validates tool results inside LangGraph dev.
try:
    import jsonschema.validators  # noqa: F401
    import jsonschema_specifications  # noqa: F401
    from jsonschema_specifications import REGISTRY as _SPEC_REGISTRY  # noqa: F401
except ImportError:
    pass

from smarthome_mcp.server import mcp as smarthome_mcp_server

load_dotenv()

model = ChatGoogleGenerativeAI(
    model=os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash"),
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "master-inn-505014-t1"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    temperature=0.2,
)


@tool
def utc_now() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(tz=timezone.utc).isoformat()


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression safely.

    Supported operators: +, -, *, /, %, ** and parentheses.
    """
    parsed = ast.parse(expression, mode="eval")
    allowed_nodes = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Constant,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Load,
    )

    for node in ast.walk(parsed):
        if not isinstance(node, allowed_nodes):
            raise ValueError("Expression contains unsupported syntax")

    result: Any = eval(compile(parsed, "<calculator>", "eval"), {"__builtins__": {}}, {})
    return str(result)


async def _load_mcp_tools() -> list[BaseTool]:
    """Discover tools exposed by the Smart Home MCP Server via MCPAdapter."""
    async with MCPAdapter(smarthome_mcp_server) as adapter:
        return await adapter.list_tools()


def get_smarthome_tools() -> list[BaseTool]:
    """Retrieve smart home tools synchronously using an event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # In an existing loop, run via new event loop in executor or nest
        import nest_asyncio

        nest_asyncio.apply()
        return asyncio.run(_load_mcp_tools())
    else:
        return asyncio.run(_load_mcp_tools())


# Load tools from MCP server
smarthome_tools = get_smarthome_tools()

# Core toolset combines local helper tools and Smart Home MCP tools
tools = [utc_now, calculator, *smarthome_tools]

BEACON_SYSTEM_PROMPT = (
    "You are Beacon, an intelligent smart home orchestrator and assistant. "
    "You can monitor, query, and control smart home devices (such as smart lights) "
    "using your smart home MCP tools (get_lights, get_light_state, set_power_state, set_brightness, set_color). "
    "Use tools when they add factual precision or interact with smart home devices, "
    "then provide clear, helpful, and concise answers to the resident."
)

graph = create_agent(
    model=model,
    tools=tools,
    system_prompt=BEACON_SYSTEM_PROMPT,
    name="beacon_agent",
)
