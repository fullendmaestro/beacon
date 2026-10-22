"""TIAGo House-Errand Bot – Beacon Core Hub & Webots state bridge service.

Communicates with the Beacon Core Hub (localhost:8000) which owns the SQLite navigation
graph, Event Broker, and Dual-Mode Virtual Physics Engine.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

HUB_API_BASE = os.getenv("SMART_HOME_HUB_URL", "http://127.0.0.1:8000").rstrip("/")
_TIMEOUT = 5.0


def _get_hub(path: str) -> Any:
    try:
        resp = httpx.get(f"{HUB_API_BASE}{path}", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "status": "hub_unavailable"}


def _post_hub(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        resp = httpx.post(f"{HUB_API_BASE}{path}", json=payload or {}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "status": "hub_unavailable"}


# ── Telemetry ──────────────────────────────────────────────────────────────────

def get_tiago_telemetry() -> dict[str, Any]:
    """Return full TIAGo telemetry: pose, battery, gripper state, current task."""
    robots = _get_hub("/api/robots")
    if isinstance(robots, list) and robots:
        r = robots[0]
        return {
            "pose": r.get("pose", {"x": -3.10, "y": -7.62, "theta": 1.5708}),
            "battery": r.get("battery_pct", 92),
            "status": r.get("status", "Docked"),
            "current_room": r.get("current_room", "Foyer"),
            "gripper": r.get("gripper", "open"),
            "arm_pose": r.get("arm_pose", "home"),
            "task": r.get("task_description", "idle"),
            "held_object": r.get("held_object", ""),
            "active_route": r.get("active_route", []),
        }
    return robots if isinstance(robots, dict) else {"error": "No robot found"}


# ── Navigation ─────────────────────────────────────────────────────────────────

def navigate_to_room(room: str) -> dict[str, Any]:
    """Command TIAGo to navigate to a named room in the house."""
    return _post_hub("/api/robots", {"action": "navigate", "destination": room})


def navigate_to_pose(x: float, y: float, theta: float) -> dict[str, Any]:
    """Command TIAGo to navigate to an absolute (x, y, θ) pose."""
    return _post_hub("/api/robots", {"action": "navigate", "x": x, "y": y, "theta": theta})


def stop_tiago() -> dict[str, Any]:
    """Immediately halt TIAGo's current navigation or manipulation task."""
    return _post_hub("/api/robots", {"action": "stop"})


def get_route_plan(destination: str) -> dict[str, Any]:
    """Compute and return the topological waypoint path to *destination*, including any blocking doors."""
    return _post_hub("/api/v2/robots/tiago/route", {"destination": destination})


# ── Manipulation ───────────────────────────────────────────────────────────────

def pick_object(object_name: str) -> dict[str, Any]:
    """Command TIAGo to pick up a named object at its current position."""
    return _post_hub("/api/robots", {"action": "pick", "object": object_name})


def place_object(location: str) -> dict[str, Any]:
    """Command TIAGo to place the held object at a named location or surface."""
    return _post_hub("/api/robots", {"action": "place", "location": location})


def set_gripper(state: str) -> dict[str, Any]:
    """Open or close TIAGo's gripper. *state* must be 'open' or 'closed'."""
    return _post_hub("/api/robots", {"action": "gripper", "gripper_state": state})


def set_arm_pose(pose_name: str) -> dict[str, Any]:
    """Move TIAGo's arm to a named preset pose (e.g. 'home', 'carry', 'reach_table', 'reach_floor')."""
    return _post_hub("/api/robots", {"action": "arm", "pose": pose_name})


# ── Head / Perception ──────────────────────────────────────────────────────────

def look_at(target: str) -> dict[str, Any]:
    """Point TIAGo's head camera toward a named target or direction ('forward', 'left', 'right', 'up', 'down')."""
    return _post_hub("/api/robots", {"action": "head", "target": target})


def get_camera_image() -> dict[str, Any]:
    """Capture a snapshot from TIAGo's head camera and return its live stream URL and status."""
    meta = _get_hub("/api/cameras/TIAGo%20Camera/frame?format=base64")
    return {
        "status": "ok",
        "camera_name": "TIAGo Camera",
        "source": meta.get("source", "live") if isinstance(meta, dict) else "live",
        "stream_url": f"{HUB_API_BASE}/api/cameras/TIAGo%20Camera/stream",
        "frame_url": f"{HUB_API_BASE}/api/cameras/TIAGo%20Camera/frame",
        "width": 640,
        "height": 480,
    }


# ── Errand helpers ─────────────────────────────────────────────────────────────

def deliver_item(item: str, from_location: str, to_location: str) -> dict[str, Any]:
    """High-level errand: navigate → pick *item* at *from_location* → deliver to *to_location*."""
    return _post_hub("/api/v2/robots/tiago/errand", {
        "errand_type": "deliver",
        "item": item,
        "from_location": from_location,
        "to_location": to_location,
    })


def fetch_item(item: str, from_location: str) -> dict[str, Any]:
    """High-level errand: navigate to *from_location*, pick *item*, return to home position."""
    return _post_hub("/api/v2/robots/tiago/errand", {
        "errand_type": "fetch",
        "item": item,
        "from_location": from_location,
        "to_location": "foyer",
    })


def get_errand_status() -> dict[str, Any]:
    """Return the status and progress of the currently running high-level errand."""
    return _get_hub("/api/v2/robots/tiago/errand")


def list_known_rooms() -> dict[str, Any]:
    """Return the list of named rooms TIAGo knows how to navigate to."""
    return _get_hub("/api/v2/robots/tiago/rooms")


def list_known_objects() -> dict[str, Any]:
    """Return a catalogue of objects TIAGo can recognise and interact with."""
    return _get_hub("/api/v2/robots/tiago/objects")

