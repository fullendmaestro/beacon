"""Beacon Agent graph for deployment with Smart Home MCP tools."""

from __future__ import annotations

import ast
import asyncio
import operator
import os
from datetime import datetime, timezone

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

_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_ast(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPERATORS:
        return _SAFE_OPERATORS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPERATORS:
        return _SAFE_OPERATORS[type(node.op)](_eval_ast(node.operand))
    raise ValueError(f"Unsupported arithmetic expression: {ast.dump(node)}")


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical arithmetic expression safely (e.g., '2 + 3 * 4')."""
    try:
        parsed = ast.parse(expression, mode="eval")
        result = _eval_ast(parsed)
        if isinstance(result, float) and result.is_integer():
            return str(int(result))
        return str(result)
    except Exception as e:  # noqa: BLE001
        return f"Error evaluating expression: {e}"


@tool
def utc_now() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


model = ChatGoogleGenerativeAI(
    model=os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash"),
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "master-inn-505014-t1"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    temperature=0.2,
)


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
        import nest_asyncio

        nest_asyncio.apply()
        return asyncio.run(_load_mcp_tools())
    return asyncio.run(_load_mcp_tools())


# Load tools from MCP server
smarthome_tools = get_smarthome_tools()

# Core toolset combines local helper tools and Smart Home MCP tools
tools = [calculator, utc_now, *smarthome_tools]

BEACON_SYSTEM_PROMPT = (
    "You are Beacon, an intelligent smart home orchestrator and assistant for a connected Webots 3D estate. "
    "You have real-time control and telemetry across the entire property via your Smart Home MCP tools:\n"
    "- **Overview, Scenes & Sky**: `get_home_summary`, `trigger_scene` ('morning', 'movie', 'away', 'night'), "
    "`set_environment` ('day', 'sunset', 'night').\n"
    "- **Smart Lighting**: `get_lights`, `get_light_state`, `set_power_state`, `set_brightness`, `set_color`.\n"
    "- **Doors, Locks, Garage & Driveway Gate**: `get_doors`, `set_door_state`, `set_door_lock`.\n"
    "- **Motorized Window Blinds**: `get_blinds`, `set_blind_position` (0-100%).\n"
    "- **HVAC / Climate Zones**: `get_climate_zones`, `set_climate_state` (15-30°C, 'heat', 'cool', 'eco', 'off').\n"
    "- **Smart Appliances & Plugs**: `get_appliances`, `set_appliance_state` (TV, Fridge, Oven, Microwave, Cooktop, Washer, Grill, Plugs).\n"
    "- **Security Cameras & Sensors**: `get_cameras`, `get_sensors` (Motion sensors & roof daylight sensor).\n\n"
    "Always invoke the appropriate tools to inspect state or actuate devices when answering user requests, "
    "and respond clearly and concisely."
)

graph = create_agent(
    model=model,
    tools=tools,
    system_prompt=BEACON_SYSTEM_PROMPT,
    name="beacon_agent",
)