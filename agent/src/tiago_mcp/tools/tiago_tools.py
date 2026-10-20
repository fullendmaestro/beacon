"""TIAGo house-errand bot MCP tools.

All tools bridge to the Webots TIAGo simulation via the `tiago_service` module.
"""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from tiago_mcp.services import tiago_service as svc

# Shared MCP server – imported by the graph.py
tiago_mcp = FastMCP("tiago_mcp")


# ═══════════════════════════════════════════════════════════
# Telemetry
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
async def get_tiago_telemetry() -> dict:
    """
    Return TIAGo's current telemetry snapshot including:
    - `pose`    : {x, y, theta} in the world frame (metres / radians)
    - `battery` : charge percentage 0-100
    - `gripper` : 'open' | 'closed'
    - `arm_pose`: current named arm pose
    - `task`    : description of the active task (or 'idle')
    """
    return await svc.get_tiago_telemetry()


# ═══════════════════════════════════════════════════════════
# Navigation
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
async def plan_tiago_route(
    destination: Annotated[str, "Target room or location name"],
) -> dict:
    """
    Compute the topological waypoint path from TIAGo's current position to
    *destination* and return:
    - `waypoints`      : ordered list of intermediate waypoints
    - `distance_m`     : estimated path length in metres
    - `blocking_doors` : list of door names that must be opened before navigation
    """
    return await svc.get_route_plan(destination)


@tiago_mcp.tool()
async def navigate_tiago_to_room(
    room: Annotated[str, "Named room (e.g. 'kitchen', 'living_room', 'bedroom')"],
) -> dict:
    """
    Command TIAGo to autonomously navigate to a named room.
    Returns the navigation status and final pose once the robot arrives.
    """
    return await svc.navigate_to_room(room)


@tiago_mcp.tool()
async def navigate_tiago_to_pose(
    x: Annotated[float, "Target X position in metres"],
    y: Annotated[float, "Target Y position in metres"],
    theta: Annotated[float, "Target heading in radians"],
) -> dict:
    """
    Command TIAGo to navigate to an exact (x, y, θ) world-frame pose.
    """
    return await svc.navigate_to_pose(x, y, theta)


@tiago_mcp.tool()
async def stop_tiago() -> dict:
    """
    Immediately stop TIAGo – halts both navigation and any active manipulation task.
    """
    return await svc.stop_tiago()


@tiago_mcp.tool()
async def list_tiago_rooms() -> dict:
    """
    Return the catalogue of named rooms TIAGo knows how to navigate to.
    """
    return await svc.list_known_rooms()


# ═══════════════════════════════════════════════════════════
# Manipulation & Gripper
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
async def set_tiago_arm_pose(
    pose_name: Annotated[str, "Preset arm pose: 'home' | 'carry' | 'reach_table' | 'reach_floor' | 'handover'"],
) -> dict:
    """
    Move TIAGo's 7-DoF arm to a named preset configuration.
    Preset poses available: 'home', 'carry', 'reach_table', 'reach_floor', 'handover'.
    """
    return await svc.set_arm_pose(pose_name)


@tiago_mcp.tool()
async def set_tiago_gripper(
    state: Annotated[str, "'open' to release, 'closed' to grasp"],
) -> dict:
    """
    Open or close TIAGo's parallel gripper.
    """
    return await svc.set_gripper(state)


@tiago_mcp.tool()
async def pick_object(
    object_name: Annotated[str, "Name of the object to grasp"],
) -> dict:
    """
    Command TIAGo to grasp a named object at its detected location.
    The robot will align its arm, lower the gripper, close it, and lift the object.
    """
    return await svc.pick_object(object_name)


@tiago_mcp.tool()
async def place_object(
    location: Annotated[str, "Named surface or location to place the object on"],
) -> dict:
    """
    Command TIAGo to place the currently held object onto a named surface or location.
    """
    return await svc.place_object(location)


# ═══════════════════════════════════════════════════════════
# Head / Perception
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
async def look_at(
    target: Annotated[str, "Named target or direction: 'forward' | 'left' | 'right' | 'up' | 'down' | object name"],
) -> dict:
    """
    Point TIAGo's head camera toward a named target or direction.
    """
    return await svc.look_at(target)


@tiago_mcp.tool()
async def get_tiago_camera_image() -> dict:
    """
    Capture a snapshot from TIAGo's head-mounted Orbbec Astra RGB camera.
    Returns image metadata, nearby 3D household objects, and nearby humans.
    """
    return await svc.get_camera_image()


@tiago_mcp.tool()
async def inspect_scene_visually(
    query: Annotated[
        str,
        "Visual question or search target (e.g. 'Where are my keys?', 'Who is in the living room?')",
    ] = "Describe what is visible in the room, including any objects, appliances, or people.",
    room: Annotated[
        str | None,
        "Optional room to navigate to before inspecting (e.g. 'kitchen', 'living_room', 'dining_room')",
    ] = None,
    sweep: Annotated[
        bool,
        "Whether to sweep the head camera (left, right, down, forward) during inspection",
    ] = True,
) -> dict:
    """
    Multimodal Visual Search & Inspector:
    Optionally navigates TIAGo to *room*, automatically turns on room lights if dark,
    sweeps TIAGo's pan/tilt head camera, captures an RGB frame + 3D Supervisor detections
    (nearby graspable objects and human actors), and returns a multimodal visual summary.
    """
    return await svc.inspect_scene(query=query, room=room, sweep=sweep)


@tiago_mcp.tool()
async def list_tiago_objects() -> dict:
    """
    Return the catalogue of 10 graspable household objects TIAGo can pick up with
    Supervisor-Assisted Magnetic Grasp, along with their live 3D coordinates.
    """
    return await svc.list_known_objects()


# ═══════════════════════════════════════════════════════════
# High-level Errands & Security Patrol
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
async def deliver_item(
    item: Annotated[str, "Name of the item to deliver (e.g. 'cup', 'bottle', 'medicine_box', 'keys')"],
    from_location: Annotated[str, "Room where the item is currently located (e.g. 'kitchen')"],
    to_location: Annotated[str, "Destination room (e.g. 'living_room', 'master_bedroom')"],
) -> dict:
    """
    High-level errand: navigate to *from_location*, pick *item* using Supervisor Magnetic Grasp,
    navigate to *to_location*, and place the item onto the room surface.
    Returns task ID and live status for tracking.
    """
    return await svc.deliver_item(item, from_location, to_location)


@tiago_mcp.tool()
async def fetch_item(
    item: Annotated[str, "Name of the item to fetch"],
    from_location: Annotated[str, "Room where the item currently is"],
) -> dict:
    """
    High-level errand: navigate to *from_location*, pick *item* using Supervisor Magnetic Grasp,
    then return to TIAGo's foyer docking position holding the item.
    """
    return await svc.fetch_item(item, from_location)


@tiago_mcp.tool()
async def patrol_home(
    rooms: Annotated[
        list[str] | None,
        "Optional list of rooms to patrol (defaults to ['living_room', 'dining_room', 'kitchen', 'master_bedroom', 'study_bedroom'])",
    ] = None,
) -> dict:
    """
    High-level security patrol errand: autonomously visits each room in sequence,
    ensures lighting is on, sweeps the head camera, logs all detected objects and humans,
    and returns to the foyer dock.
    """
    return await svc.patrol_home(rooms=rooms)


@tiago_mcp.tool()
async def get_errand_status() -> dict:
    """
    Return the status and step-by-step progress of TIAGo's currently running
    high-level errand (deliver/fetch/patrol), including held_object and patrol_logs.
    """
    return await svc.get_errand_status()
