"""Beacon Agent graph for deployment with Smart Home MCP tools."""

from __future__ import annotations

import ast
import asyncio
import operator
import os
from datetime import UTC, datetime
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

from rover_mcp.server import rover_mcp as rover_mcp_server
from smarthome_mcp.server import mcp as smarthome_mcp_server

load_dotenv()

_SAFE_BIN_OPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_SAFE_UNARY_OPS: dict[type[ast.unaryop], Any] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_ast(node: ast.AST) -> float | int:
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BIN_OPS:
        return _SAFE_BIN_OPS[type(node.op)](_eval_ast(node.left), _eval_ast(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARY_OPS:
        return _SAFE_UNARY_OPS[type(node.op)](_eval_ast(node.operand))
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
    return datetime.now(UTC).isoformat()


model = ChatGoogleGenerativeAI(
    model=os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash"),
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "master-inn-505014-t1"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    temperature=0.2,
)


async def _load_all_mcp_tools() -> list[BaseTool]:
    """Discover tools exposed by both the Smart Home MCP Server and the Rover MCP Server."""
    async with (
        MCPAdapter(smarthome_mcp_server) as home_adapter,
        MCPAdapter(rover_mcp_server) as rover_adapter,
    ):
        home_tools = await home_adapter.list_tools()
        rover_tools = await rover_adapter.list_tools()
        return [*home_tools, *rover_tools]


def get_all_mcp_tools() -> list[BaseTool]:
    """Retrieve Smart Home and Rover MCP tools synchronously using an event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio

        nest_asyncio.apply()
        return asyncio.run(_load_all_mcp_tools())
    return asyncio.run(_load_all_mcp_tools())


mcp_tools = get_all_mcp_tools()
tools = [calculator, utc_now, *mcp_tools]

BEACON_SYSTEM_PROMPT = (
    "You are Beacon, an intelligent smart home orchestrator and robotic fleet commander for a connected Webots 3D estate.\n"
    "You have real-time control and telemetry across two MCP tool suites:\n"
    "1. **Smart Home MCP (`smarthome_mcp`)**:\n"
    "   - Overview, Scenes & Sky: `get_home_summary`, `trigger_scene`, `set_environment`.\n"
    "   - Smart Lighting: `get_lights`, `get_light_state`, `set_power_state`, `set_brightness`, `set_color`.\n"
    "   - Doors, Locks, Garage & Driveway Gate: `get_doors`, `set_door_state`, `set_door_lock`.\n"
    "   - Motorized Window Blinds: `get_blinds`, `set_blind_position`.\n"
    "   - HVAC & Appliances: `get_climate_zones`, `set_climate_state`, `get_appliances`, `set_appliance_state`.\n"
    "   - Security Cameras & Sensors: `get_cameras`, `get_sensors`.\n"
    "2. **Autonomous Rover MCP (`rover_mcp` - KUKA youBot)**:\n"
    "   - Route Planning & Telemetry: `get_rover_telemetry`, `plan_rover_route`.\n"
    "   - Autonomous Navigation: `navigate_rover_to_room`, `navigate_rover_to_pose`, `stop_rover`.\n"
    "   - Mobile Manipulation & Teleop: `set_rover_arm_pose`, `set_rover_gripper`, `drive_rover_velocity`.\n\n"
    "**CRITICAL ROVER NAVIGATION PROTOCOL**:\n"
    "Whenever asked to send the rover to a room or location:\n"
    "1. Call `plan_rover_route(destination=...)` first to compute the topological waypoint path and check `blocking_doors`.\n"
    "2. If `blocking_doors` is non-empty, explicitly unlock (`set_door_lock`) and open (`set_door_state`) each blocking door via the Smart Home MCP.\n"
    "3. Optionally turn on room lights if the target room is dark.\n"
    "4. Call `navigate_rover_to_room(destination=...)` to execute the orthogonal route trajectory."
)

graph = create_agent(
    model=model,
    tools=tools,
    system_prompt=BEACON_SYSTEM_PROMPT,
    name="beacon_agent",
)