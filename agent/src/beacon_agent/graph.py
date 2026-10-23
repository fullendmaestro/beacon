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
from beacon_agent.model import get_model
from beacon_agent.prompt import BEACON_SYSTEM_PROMPT, SENTINEL_SYSTEM_PROMPT

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


model = get_model()


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

graph = create_agent(
    model=model,
    tools=tools,
    system_prompt=BEACON_SYSTEM_PROMPT,
    name="beacon_agent",
)

sentinel_graph = create_agent(
    model=model,
    tools=tools,
    system_prompt=SENTINEL_SYSTEM_PROMPT,
    name="beacon_sentinel_agent",
)