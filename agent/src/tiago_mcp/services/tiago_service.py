"""TIAGo House-Errand Bot – Webots state bridge service.

Communicates with the Webots TIAGo controller via HTTP on localhost:8001.
Falls back gracefully when the simulation is not running.
"""

from __future__ import annotations

from typing import Any

import httpx

TIAGO_API_BASE = "http://127.0.0.1:8001"
_TIMEOUT = 5.0


def _get(path: str) -> dict[str, Any]:
    try:
        resp = httpx.get(f"{TIAGO_API_BASE}{path}", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "status": "simulation_unavailable"}


def _post(path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        resp = httpx.post(f"{TIAGO_API_BASE}{path}", json=payload or {}, timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "status": "simulation_unavailable"}


# ── Telemetry ──────────────────────────────────────────────────────────────────

def get_tiago_telemetry() -> dict[str, Any]:
    """Return full TIAGo telemetry: pose, battery, gripper state, current task."""
    return _get("/telemetry")


# ── Navigation ─────────────────────────────────────────────────────────────────

def navigate_to_room(room: str) -> dict[str, Any]:
    """Command TIAGo to navigate to a named room in the house."""
    return _post("/navigate/room", {"room": room})


def navigate_to_pose(x: float, y: float, theta: float) -> dict[str, Any]:
    """Command TIAGo to navigate to an absolute (x, y, θ) pose."""
    return _post("/navigate/pose", {"x": x, "y": y, "theta": theta})


def stop_tiago() -> dict[str, Any]:
    """Immediately halt TIAGo's current navigation or manipulation task."""
    return _post("/stop")


def get_route_plan(destination: str) -> dict[str, Any]:
    """Compute and return the topological waypoint path to *destination*, including any blocking doors."""
    return _post("/route/plan", {"destination": destination})


# ── Manipulation ───────────────────────────────────────────────────────────────

def pick_object(object_name: str) -> dict[str, Any]:
    """Command TIAGo to pick up a named object at its current position."""
    return _post("/manipulate/pick", {"object": object_name})


def place_object(location: str) -> dict[str, Any]:
    """Command TIAGo to place the held object at a named location or surface."""
    return _post("/manipulate/place", {"location": location})


def set_gripper(state: str) -> dict[str, Any]:
    """Open or close TIAGo's gripper. *state* must be 'open' or 'closed'."""
    return _post("/gripper/set", {"state": state})


def set_arm_pose(pose_name: str) -> dict[str, Any]:
    """Move TIAGo's arm to a named preset pose (e.g. 'home', 'carry', 'reach_table', 'reach_floor')."""
    return _post("/arm/pose", {"pose": pose_name})


# ── Head / Perception ──────────────────────────────────────────────────────────

def look_at(target: str) -> dict[str, Any]:
    """Point TIAGo's head camera toward a named target or direction ('forward', 'left', 'right', 'up', 'down')."""
    return _post("/head/look_at", {"target": target})


def get_camera_image() -> dict[str, Any]:
    """Capture a snapshot from TIAGo's head camera and return its metadata/path."""
    return _get("/camera/snapshot")


# ── Errand helpers ─────────────────────────────────────────────────────────────

def deliver_item(item: str, from_location: str, to_location: str) -> dict[str, Any]:
    """High-level errand: navigate → pick *item* at *from_location* → deliver to *to_location*."""
    return _post("/errand/deliver", {
        "item": item,
        "from_location": from_location,
        "to_location": to_location,
    })


def fetch_item(item: str, from_location: str) -> dict[str, Any]:
    """High-level errand: navigate to *from_location*, pick *item*, return to home position."""
    return _post("/errand/fetch", {"item": item, "from_location": from_location})


def get_errand_status() -> dict[str, Any]:
    """Return the status and progress of the currently running high-level errand."""
    return _get("/errand/status")


def list_known_rooms() -> dict[str, Any]:
    """Return the list of named rooms TIAGo knows how to navigate to."""
    return _get("/rooms")


def list_known_objects() -> dict[str, Any]:
    """Return a catalogue of objects TIAGo can recognise and interact with."""
    return _get("/objects")
