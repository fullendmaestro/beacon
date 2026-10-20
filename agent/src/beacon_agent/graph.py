"""Beacon Agent graph – TIAGo House-Errand Bot edition."""

from __future__ import annotations

import ast
import asyncio
import atexit
from contextlib import AsyncExitStack
import operator
import os
import socket
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
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
from tiago_mcp.server import tiago_mcp as tiago_mcp_server

load_dotenv()


def _ensure_smart_home_hub_running(host: str = "127.0.0.1", port: int = 8000) -> None:
    """
    Ensure the Smart Home Hub API server is listening on `host:port`.
    If Webots is not currently running the controller on port 8000, start the
    standalone hub controller in a background daemon thread so the frontend
    and MCP tools never get ERR_CONNECTION_REFUSED.
    """
    if os.getenv("DISABLE_AUTO_SMART_HOME_HUB") == "1":
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        if sock.connect_ex((host, port)) == 0:
            return

    ctrl_dir = Path(__file__).resolve().parents[1] / "simulation" / "controllers" / "smart_home_controller"
    if not ctrl_dir.exists():
        return

    def _serve() -> None:
        if str(ctrl_dir) not in sys.path:
            sys.path.insert(0, str(ctrl_dir))
        try:
            import uvicorn
            from api import create_app
            from controller_service import SmartHomeController
            from standalone_supervisor import StandaloneSupervisor

            controller = SmartHomeController(supervisor=StandaloneSupervisor())
            controller.init_devices()
            app = create_app(controller)

            def _sim_loop() -> None:
                while controller.supervisor.step(controller.time_step) != -1:
                    controller.step_simulation()

            threading.Thread(target=_sim_loop, daemon=True).start()
            uvicorn.run(app, host=host, port=port, log_level="warning")
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=_serve, daemon=True, name="beacon-standalone-hub").start()


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


def _create_chat_model(temperature: float = 0.2) -> Any:
    """
    Create the primary chat model for Beacon.
    Supports Amazon Bedrock (e.g. Amazon Nova Pro / Claude for Amazon App Dev 2026 Alexa+ Track)
    as well as Google Gemini (API Key or Vertex AI without hardcoded project IDs).
    """
    provider = os.getenv("BEACON_LLM_PROVIDER", "").strip().lower()
    if provider in ("bedrock", "aws", "alexa+") or os.getenv("BEDROCK_MODEL_ID"):
        try:
            from langchain_aws import ChatBedrockConverse  # type: ignore[import-not-found]

            return ChatBedrockConverse(
                model=os.getenv("BEDROCK_MODEL_ID", os.getenv("BEACON_AGENT_MODEL", "us.amazon.nova-pro-v1:0")),
                region_name=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
                temperature=temperature,
            )
        except ImportError:
            pass

    model_name = os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash")
    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if gcp_project:
        return ChatGoogleGenerativeAI(
            model=model_name,
            vertexai=True,
            project=gcp_project,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=temperature,
        )
    if api_key:
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature,
        )
    return ChatGoogleGenerativeAI(
        model=model_name,
        vertexai=True,
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        temperature=temperature,
    )


model = _create_chat_model(temperature=0.2)

_LOOP_MCP_SESSIONS: dict[tuple[int, int], tuple[AsyncExitStack, dict[str, BaseTool]]] = {}


async def _get_live_tool_for_loop(server: Any, tool_name: str) -> BaseTool:
    """Maintain an active MCPAdapter session bound to the current event loop so transport never closes prematurely."""
    loop = asyncio.get_running_loop()
    key = (id(loop), id(server))
    entry = _LOOP_MCP_SESSIONS.get(key)
    if entry is None:
        stack = AsyncExitStack()
        adapter = await stack.enter_async_context(MCPAdapter(server))
        live_tools = await adapter.list_tools()
        tool_map = {t.name: t for t in live_tools}
        _LOOP_MCP_SESSIONS[key] = (stack, tool_map)
        entry = (stack, tool_map)
    return entry[1][tool_name]


def _bind_resilient_mcp_tool(mcp_tool: BaseTool, server: Any) -> BaseTool:
    """Wrap an MCPAdapter tool so invocations always execute on an active MCPAdapter session in the caller's loop."""
    tool_name = mcp_tool.name

    async def _resilient_coro(**kwargs: Any) -> Any:
        try:
            live_tool = await _get_live_tool_for_loop(server, tool_name)
            coro = getattr(live_tool, "coroutine", None)
            if coro is not None:
                return await coro(**kwargs)
            return await live_tool.ainvoke(kwargs)
        except Exception:
            # Re-open a fresh session if the cached session was invalidated
            loop = asyncio.get_running_loop()
            _LOOP_MCP_SESSIONS.pop((id(loop), id(server)), None)
            async with MCPAdapter(server) as fresh_adapter:
                fresh_tools = await fresh_adapter.list_tools()
                for ft in fresh_tools:
                    if ft.name == tool_name:
                        f_coro = getattr(ft, "coroutine", None)
                        if f_coro is not None:
                            return await f_coro(**kwargs)
                        return await ft.ainvoke(kwargs)
            raise

    def _resilient_sync(**kwargs: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            import nest_asyncio

            nest_asyncio.apply()
        return asyncio.run(_resilient_coro(**kwargs))

    if hasattr(mcp_tool, "coroutine"):
        object.__setattr__(mcp_tool, "coroutine", _resilient_coro)
    if hasattr(mcp_tool, "func"):
        object.__setattr__(mcp_tool, "func", _resilient_sync)
    return mcp_tool


def _cleanup_mcp_sessions() -> None:
    _LOOP_MCP_SESSIONS.clear()


atexit.register(_cleanup_mcp_sessions)


async def _load_all_mcp_tools() -> tuple[list[BaseTool], list[BaseTool]]:
    """Discover tools exposed by the Smart Home MCP Server and the TIAGo MCP Server and bind live session wrappers."""
    async with (
        MCPAdapter(smarthome_mcp_server) as home_adapter,
        MCPAdapter(tiago_mcp_server) as tiago_adapter,
    ):
        raw_home_tools = await home_adapter.list_tools()
        raw_tiago_tools = await tiago_adapter.list_tools()
        home_tools = [_bind_resilient_mcp_tool(t, smarthome_mcp_server) for t in raw_home_tools]
        t_tools = [_bind_resilient_mcp_tool(t, tiago_mcp_server) for t in raw_tiago_tools]
        return home_tools, t_tools


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
rover_tools = tiago_tools
mcp_tools = [*smarthome_tools, *tiago_tools]
tools = [calculator, utc_now, *mcp_tools]

BEACON_SYSTEM_PROMPT = (
    "You are Beacon, an Alexa+ Proactive Ambient Intelligence smart home orchestrator and domestic robot commander.\n"
    "You oversee a connected Webots 3D smart home staffed by a PAL Robotics TIAGo house-errand bot\n"
    "with Supervisor-Assisted Magnetic Grasp, Multimodal Visual Inspection, and Ambient + Human-in-the-Loop (HITL) AI workflows.\n"
    "You have real-time control and telemetry across two MCP tool suites:\n\n"
    "1. **Smart Home MCP (`smarthome_mcp`)**:\n"
    "   - Overview, Scenes & Sky: `get_home_summary`, `trigger_scene`, `set_environment`.\n"
    "   - Occupants, Objects & AI Tasks: `get_humans`, `get_household_objects`, `get_ai_tasks`, `propose_ai_task`, `approve_ai_task`.\n"
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
    "   - Supervisor Magnetic Grasp Manipulation: `pick_object`, `place_object`.\n"
    "   - Multimodal Vision & Head Camera: `inspect_scene_visually`, `look_at`, `get_tiago_camera_image`.\n"
    "   - High-level Errands & Security Patrol: `fetch_item`, `deliver_item`, `patrol_home`, `get_errand_status`.\n\n"
    "**CRITICAL TIAGO NAVIGATION PROTOCOL**:\n"
    "Whenever asked to send TIAGo to a room or location:\n"
    "1. Call `plan_tiago_route(destination=...)` first to compute the waypoint path and check `blocking_doors`.\n"
    "2. If `blocking_doors` is non-empty, unlock (`set_door_lock`) and open (`set_door_state`) each blocking door.\n"
    "3. Optionally turn on room lights if the target room is dark.\n"
    "4. Call `navigate_tiago_to_room(room=...)` to execute the route.\n\n"
    "**MULTIMODAL VISUAL SEARCH & MAGNETIC GRASP BEST PRACTICE**:\n"
    "- Use `inspect_scene_visually(query=..., room=...)` or `get_household_objects()` to locate misplaced items or check on human occupants.\n"
    "- For fetch/deliver tasks prefer `fetch_item` / `deliver_item`, which use Supervisor-Assisted Magnetic Grasp to attach the 3D object to TIAGo's wrist during transport.\n"
    "- For multi-room inspection use `patrol_home(rooms=...)`.\n"
    "- For sensitive or high-impact actions, queue a Human-in-the-Loop task via `propose_ai_task(..., proposed_actions=[...])`."
)

graph = create_agent(
    model=model,
    tools=tools,
    system_prompt=BEACON_SYSTEM_PROMPT,
    name="beacon_agent",
)