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
def get_tiago_telemetry() -> dict:
    """
    Return TIAGo's current telemetry snapshot including:
    - `pose`    : {x, y, theta} in the world frame (metres / radians)
    - `battery` : charge percentage 0-100
    - `gripper` : 'open' | 'closed'
    - `arm_pose`: current named arm pose
    - `task`    : description of the active task (or 'idle')
    """
    return svc.get_tiago_telemetry()


# ═══════════════════════════════════════════════════════════
# Navigation
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
def plan_tiago_route(
    destination: Annotated[str, "Target room or location name"],
) -> dict:
    """
    Compute the topological waypoint path from TIAGo's current position to
    *destination* and return:
    - `waypoints`      : ordered list of intermediate waypoints
    - `distance_m`     : estimated path length in metres
    - `blocking_doors` : list of door names that must be opened before navigation
    """
    return svc.get_route_plan(destination)


@tiago_mcp.tool()
def navigate_tiago_to_room(
    room: Annotated[str, "Named room (e.g. 'kitchen', 'living_room', 'bedroom')"],
) -> dict:
    """
    Command TIAGo to autonomously navigate to a named room.
    Returns the navigation status and final pose once the robot arrives.
    """
    return svc.navigate_to_room(room)


@tiago_mcp.tool()
def navigate_tiago_to_pose(
    x: Annotated[float, "Target X position in metres"],
    y: Annotated[float, "Target Y position in metres"],
    theta: Annotated[float, "Target heading in radians"],
) -> dict:
    """
    Command TIAGo to navigate to an exact (x, y, θ) world-frame pose.
    """
    return svc.navigate_to_pose(x, y, theta)


@tiago_mcp.tool()
def stop_tiago() -> dict:
    """
    Immediately stop TIAGo – halts both navigation and any active manipulation task.
    """
    return svc.stop_tiago()


@tiago_mcp.tool()
def list_tiago_rooms() -> dict:
    """
    Return the catalogue of named rooms TIAGo knows how to navigate to.
    """
    return svc.list_known_rooms()


# ═══════════════════════════════════════════════════════════
# Manipulation & Gripper
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
def set_tiago_arm_pose(
    pose_name: Annotated[str, "Preset arm pose: 'home' | 'carry' | 'reach_table' | 'reach_floor' | 'handover'"],
) -> dict:
    """
    Move TIAGo's 7-DoF arm to a named preset configuration.
    Preset poses available: 'home', 'carry', 'reach_table', 'reach_floor', 'handover'.
    """
    return svc.set_arm_pose(pose_name)


@tiago_mcp.tool()
def set_tiago_gripper(
    state: Annotated[str, "'open' to release, 'closed' to grasp"],
) -> dict:
    """
    Open or close TIAGo's parallel gripper.
    """
    return svc.set_gripper(state)


@tiago_mcp.tool()
def pick_object(
    object_name: Annotated[str, "Name of the object to grasp"],
) -> dict:
    """
    Command TIAGo to grasp a named object at its detected location.
    The robot will align its arm, lower the gripper, close it, and lift the object.
    """
    return svc.pick_object(object_name)


@tiago_mcp.tool()
def place_object(
    location: Annotated[str, "Named surface or location to place the object on"],
) -> dict:
    """
    Command TIAGo to place the currently held object onto a named surface or location.
    """
    return svc.place_object(location)


# ═══════════════════════════════════════════════════════════
# Head / Perception
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
def look_at(
    target: Annotated[str, "Named target or direction: 'forward' | 'left' | 'right' | 'up' | 'down' | object name"],
) -> dict:
    """
    Point TIAGo's head camera toward a named target or direction.
    """
    return svc.look_at(target)


@tiago_mcp.tool()
def get_tiago_camera_image() -> dict:
    """
    Capture a snapshot from TIAGo's head-mounted RGB camera.
    Returns image metadata and a filesystem path to the saved image.
    """
    return svc.get_camera_image()


@tiago_mcp.tool()
def list_tiago_objects() -> dict:
    """
    Return the catalogue of household objects TIAGo is capable of recognising and
    interacting with in the current simulation.
    """
    return svc.list_known_objects()


# ═══════════════════════════════════════════════════════════
# High-level Errands
# ═══════════════════════════════════════════════════════════

@tiago_mcp.tool()
def deliver_item(
    item: Annotated[str, "Name of the item to deliver"],
    from_location: Annotated[str, "Room or surface where the item is currently located"],
    to_location: Annotated[str, "Destination room or surface"],
) -> dict:
    """
    High-level errand: navigate to *from_location*, pick *item*, navigate to
    *to_location*, then place the item there.
    Returns task ID and live status for tracking.
    """
    return svc.deliver_item(item, from_location, to_location)


@tiago_mcp.tool()
def fetch_item(
    item: Annotated[str, "Name of the item to fetch"],
    from_location: Annotated[str, "Room or surface where the item currently is"],
) -> dict:
    """
    High-level errand: navigate to *from_location*, pick *item*, then return
    to TIAGo's home/docking position holding the item.
    """
    return svc.fetch_item(item, from_location)


@tiago_mcp.tool()
def get_errand_status() -> dict:
    """
    Return the status and step-by-step progress of TIAGo's currently running
    high-level errand (deliver/fetch/patrol).
    Fields: task_id, errand_type, current_step, total_steps, status, message.
    """
    return svc.get_errand_status()
