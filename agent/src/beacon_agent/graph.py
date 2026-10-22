"""Beacon Agent graph – TIAGo House-Errand Bot edition."""

from __future__ import annotations

import ast
import asyncio
import operator
import os
import socket
import sys
import threading
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
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
from tiago_mcp.server import tiago_mcp as tiago_mcp_server

load_dotenv()


def _ensure_smart_home_hub_running(host: str = "127.0.0.1", port: int = 8000) -> None:
    """
    Ensure the standalone Beacon Core Hub Service (`beacon_hub`) is listening on `host:port`.
    The Hub owns the SQLite WAL database, Async Event Broker, and Dual-Mode Virtual Physics Engine.
    """
    if os.getenv("DISABLE_AUTO_SMART_HOME_HUB") == "1":
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        if sock.connect_ex((host, port)) == 0:
            return

    src_dir = Path(__file__).resolve().parents[1]

    def _serve() -> None:
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        try:
            import uvicorn
            from beacon_hub.main import app as hub_app

            uvicorn.run(hub_app, host=host, port=port, log_level="warning")
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_serve, daemon=True, name="beacon-core-hub").start()


_ensure_smart_home_hub_running()

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


HUB_BASE_URL = os.getenv("SMART_HOME_HUB_URL", "http://127.0.0.1:8000").rstrip("/")


@tool
def inspect_camera_feed(camera_name: str, question: str = "Describe what you see in this room.") -> list[dict[str, Any]]:
    """
    Capture a live frame from any smart home security camera or TIAGo's head camera
    and visually inspect the scene using multimodal vision.

    Valid `camera_name` values:
    - 'Kitchen Camera'
    - 'Living Room Camera'
    - 'Bedroom Camera'
    - 'Front Door Camera'
    - 'Driveway Camera'
    - 'Backyard Patio Camera'
    - 'TIAGo Camera'
    """
    encoded = urllib.parse.quote(camera_name.strip(), safe="")
    try:
        resp = httpx.get(f"{HUB_BASE_URL}/api/cameras/{encoded}/frame?format=base64", timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        b64 = data["jpeg_base64"]
        source = data.get("source", "live")
        return [
            {
                "type": "text",
                "text": (
                    f"Captured live frame from '{camera_name}' (source={source}). "
                    f"Stream URL: {HUB_BASE_URL}/api/cameras/{encoded}/stream. "
                    f"User visual focus: {question}"
                ),
            },
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
        ]
    except Exception as exc:  # noqa: BLE001
        return [{"type": "text", "text": f"Failed to capture frame from '{camera_name}': {exc}"}]


@tool
def get_recent_home_events(limit: int = 20) -> list[dict[str, Any]]:
    """
    Retrieve the latest real-time events from the Beacon Event Broker
    (sensor triggers, device commands, robot telemetry, and autonomous rule alerts).
    """
    resp = httpx.get(f"{HUB_BASE_URL}/api/v2/events/recent?limit={limit}", timeout=5.0)
    resp.raise_for_status()
    return resp.json()


@tool
def list_automation_rules() -> list[dict[str, Any]]:
    """List all active event-driven automation rules registered in the Beacon Event Broker."""
    resp = httpx.get(f"{HUB_BASE_URL}/api/v2/events/rules", timeout=5.0)
    resp.raise_for_status()
    return resp.json()


@tool
def create_automation_rule(
    name: str,
    trigger_topic: str,
    condition: dict[str, Any],
    actions: list[dict[str, Any]],
    agent_prompt: str | None = None,
    cooldown_sec: float = 15.0,
) -> dict[str, Any]:
    """
    Create a real-time event-driven automation rule on the Beacon Event Broker.

    Example `trigger_topic`:
    - 'sensor.telemetry.front_porch_motion_sensor'
    - 'sensor.telemetry.living_room_motion_sensor'
    - 'sensor.telemetry.exterior_daylight_sensor'
    - 'device.state.door.dev_door_front_entrance'

    Example `condition`:
    - {'triggered': True} or {'state': 'Open'}

    Example `actions` list items:
    - {'type': 'device_command', 'device_id': 'dev_light_03', 'action': 'set_state', 'params': {'power_state': 'on', 'brightness': 100}}
    - {'type': 'robot_navigate', 'destination': 'kitchen'}
    - {'type': 'camera_alert', 'camera_name': 'Front Door Camera', 'message': 'Motion at front door!'}
    """
    resp = httpx.post(
        f"{HUB_BASE_URL}/api/v2/events/rules",
        json={
            "name": name,
            "trigger_topic": trigger_topic,
            "condition": condition,
            "actions": actions,
            "agent_prompt": agent_prompt,
            "cooldown_sec": cooldown_sec,
        },
        timeout=5.0,
    )
    resp.raise_for_status()
    return resp.json()


@tool
def delete_automation_rule(rule_id: str) -> dict[str, Any]:
    """Delete an event-driven automation rule by its `rule_id`."""
    resp = httpx.delete(f"{HUB_BASE_URL}/api/v2/events/rules/{rule_id}", timeout=5.0)
    resp.raise_for_status()
    return resp.json()


model = ChatGoogleGenerativeAI(
    model=os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash"),
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "master-inn-505014-t1"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
    temperature=0.2,
)


async def _load_all_mcp_tools() -> tuple[list[BaseTool], list[BaseTool]]:
    """Discover tools exposed by the Smart Home MCP Server and the TIAGo MCP Server."""
    async with (
        MCPAdapter(smarthome_mcp_server) as home_adapter,
        MCPAdapter(tiago_mcp_server) as tiago_adapter,
    ):
        home_tools = await home_adapter.list_tools()
        tiago_tools = await tiago_adapter.list_tools()
        return list(home_tools), list(tiago_tools)


def _get_mcp_tool_sets() -> tuple[list[BaseTool], list[BaseTool]]:
    """Retrieve Smart Home and TIAGo MCP tool sets synchronously using an event loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import nest_asyncio

        nest_asyncio.apply()
        return asyncio.run(_load_all_mcp_tools())
    return asyncio.run(_load_all_mcp_tools())


def get_all_mcp_tools() -> list[BaseTool]:
    """Retrieve combined Smart Home and TIAGo MCP tools synchronously."""
    home_tools, t_tools = _get_mcp_tool_sets()
    return [*home_tools, *t_tools]


smarthome_tools, tiago_tools = _get_mcp_tool_sets()
mcp_tools = [*smarthome_tools, *tiago_tools]
tools = [
    calculator,
    utc_now,
    inspect_camera_feed,
    get_recent_home_events,
    list_automation_rules,
    create_automation_rule,
    delete_automation_rule,
    *mcp_tools,
]

BEACON_SYSTEM_PROMPT = (
    "You are Beacon, an intelligent smart home orchestrator and domestic robot commander.\n"
    "You oversee a connected Webots 3D smart home staffed by a PAL Robotics TIAGo house-errand bot.\n"
    "You have real-time control and telemetry across two MCP tool suites:\n\n"
    "1. **Smart Home MCP (`smarthome_mcp`)**:\n"
    "   - Unified Discovery & Provisioning: `get_devices`, `provision_device`, `remove_device`.\n"
    "   - Overview, Scenes & Sky: `get_home_summary`, `trigger_scene`, `set_environment`.\n"
    "   - Smart Lighting: `get_lights`, `get_light_state`, `set_power_state`, `set_brightness`, `set_color`.\n"
    "   - Doors, Locks, Garage & Driveway Gate: `get_doors`, `set_door_state`, `set_door_lock`.\n"
    "   - Motorized Window Blinds: `get_blinds`, `set_blind_position`.\n"
    "   - HVAC & Appliances: `get_climate_zones`, `set_climate_state`, `get_appliances`, `set_appliance_state`.\n"
    "   - Security Cameras & Sensors: `get_cameras`, `get_sensors`.\n\n"
    "2. **TIAGo House-Errand Bot MCP (`tiago_mcp`)**:\n"
    "   - Telemetry & Discovery: `get_tiago_telemetry`, `list_tiago_rooms`, `list_tiago_objects`.\n"
    "   - Route Planning: `plan_tiago_route` — always call this first to identify blocking doors.\n"
    "   - Autonomous Navigation: `navigate_tiago_to_room`, `navigate_tiago_to_pose`, `stop_tiago`.\n"
    "   - Arm & Gripper Control: `set_tiago_arm_pose`, `set_tiago_gripper`.\n"
    "   - Object Manipulation: `pick_object`, `place_object`.\n"
    "   - Head / Perception: `look_at`, `get_tiago_camera_image`.\n"
    "   - High-level Errands: `fetch_item`, `deliver_item`, `get_errand_status`.\n\n"
    "3. **Live Camera Vision & Event-Driven Automation**:\n"
    "   - Whenever the user asks what is happening in a room, or asks you to check a camera or what TIAGo sees, "
    "call `inspect_camera_feed(camera_name=...)` to capture a real-time JPEG frame and analyze it visually.\n"
    "   - Whenever the user asks to set up a reactive behavior (e.g., 'When motion is detected in the living room, "
    "turn on the lights and send TIAGo'), call `create_automation_rule(...)` so the Beacon Event Broker executes it autonomously.\n\n"
    "**CRITICAL DEVICE IDENTIFICATION PROTOCOL**:\n"
    "Fuzzy device matching is disabled. Never guess or fabricate a `device_id` or `wbt_name` "
    "(such as passing `\"living room light\"` or `\"tv\"`). Before mutating any device state, "
    "if you do not already have its exact `id` or `.wbt` `name` in the current conversation context, "
    "you MUST call the corresponding discovery tool (`get_devices`, `get_lights`, `get_doors`, "
    "`get_blinds`, `get_climate_zones`, `get_appliances`) first, inspect the returned list, "
    "and pass the exact `id` or `wbt_name`.\n\n"
    "**CRITICAL TIAGO NAVIGATION PROTOCOL**:\n"
    "Whenever asked to send TIAGo to a room or location:\n"
    "1. Call `plan_tiago_route(destination=...)` first to compute the waypoint path and check `blocking_doors`.\n"
    "2. If `blocking_doors` is non-empty, unlock (`set_door_lock`) and open (`set_door_state`) each blocking door.\n"
    "3. Optionally turn on room lights if the target room is dark.\n"
    "4. Call `navigate_tiago_to_room(room=...)` to execute the route.\n\n"
    "**ERRAND BEST PRACTICE**:\n"
    "For complex fetch/deliver tasks prefer the high-level `fetch_item` / `deliver_item` tools which\n"
    "handle the full navigate → pick → navigate → place cycle autonomously.  Use `get_errand_status`\n"
    "to poll progress and report back to the user."
)

graph = create_agent(
    model=model,
    tools=tools,
    system_prompt=BEACON_SYSTEM_PROMPT,
    name="beacon_agent",
)