"""TIAGo House-Errand Bot – Webots state bridge service.

Communicates with the Webots TIAGo controller via HTTP on localhost:8001,
with fallback to Smart Home Hub on localhost:8000 when running in standalone mode.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

TIAGO_API_BASE = "http://127.0.0.1:8001"
SMART_HOME_API_BASE = os.getenv("SMART_HOME_HUB_URL", "http://127.0.0.1:8000")
_TIMEOUT = 15.0


def _get(path: str) -> dict[str, Any]:
    try:
        resp = httpx.get(f"{TIAGO_API_BASE}{path}", timeout=_TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "status": "simulation_unavailable"}


def _post(path: str, payload: dict[str, Any] | None = None, timeout: float = _TIMEOUT) -> dict[str, Any]:
    try:
        resp = httpx.post(f"{TIAGO_API_BASE}{path}", json=payload or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "status": "simulation_unavailable"}


# ── Telemetry ──────────────────────────────────────────────────────────────────

def get_tiago_telemetry() -> dict[str, Any]:
    """Return full TIAGo telemetry: pose, battery, gripper state, current task, held object, patrol logs."""
    res = _get("/telemetry")
    if res.get("status") == "simulation_unavailable":
        try:
            robots = httpx.get(f"{SMART_HOME_API_BASE}/api/robots", timeout=3.0).json()
            if robots:
                return robots[0]
        except Exception:
            pass
    return res


# ── Navigation ─────────────────────────────────────────────────────────────────

def navigate_to_room(room: str) -> dict[str, Any]:
    """Command TIAGo to navigate to a named room in the house."""
    res = _post("/navigate/room", {"room": room})
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={"action": "navigate", "destination": room},
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


def navigate_to_pose(x: float, y: float, theta: float) -> dict[str, Any]:
    """Command TIAGo to navigate to an absolute (x, y, θ) pose."""
    return _post("/navigate/pose", {"x": x, "y": y, "theta": theta})


def stop_tiago() -> dict[str, Any]:
    """Immediately halt TIAGo's current navigation or manipulation task."""
    res = _post("/stop")
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={"action": "stop"},
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


def get_route_plan(destination: str) -> dict[str, Any]:
    """Compute and return the topological waypoint path to *destination*, including any blocking doors."""
    return _post("/route/plan", {"destination": destination})


# ── Manipulation (Supervisor-Assisted Magnetic Grasp) ─────────────────────────

def pick_object(object_name: str) -> dict[str, Any]:
    """Command TIAGo to magnetically grasp a named object at its current position."""
    res = _post("/manipulate/pick", {"object": object_name})
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={"action": "pick", "object": object_name},
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


def place_object(location: str) -> dict[str, Any]:
    """Command TIAGo to place the held object onto the target room surface."""
    res = _post("/manipulate/place", {"location": location})
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={"action": "place", "location": location},
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


def set_gripper(state: str) -> dict[str, Any]:
    """Open or close TIAGo's gripper. *state* must be 'open' or 'closed'."""
    res = _post("/gripper/set", {"state": state})
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={"action": "gripper", "gripper_state": state},
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


def set_arm_pose(pose_name: str) -> dict[str, Any]:
    """Move TIAGo's arm to a named preset pose (e.g. 'home', 'carry', 'reach_table', 'reach_floor', 'handover')."""
    res = _post("/arm/pose", {"pose": pose_name})
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={"action": "arm", "pose": pose_name},
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


# ── Head / Multimodal Perception & Visual Inspector ────────────────────────────

def look_at(target: str) -> dict[str, Any]:
    """Point TIAGo's head camera toward a named target or direction ('forward', 'left', 'right', 'up', 'down')."""
    return _post("/head/look_at", {"target": target})


def get_camera_image() -> dict[str, Any]:
    """Capture a snapshot from TIAGo's head camera and return its metadata and nearby detections."""
    res = _get("/camera/snapshot")
    if "base64_jpeg" in res:
        res = {k: v for k, v in res.items() if k != "base64_jpeg"}
    return res


def inspect_scene(
    query: str = "Describe what is visible in the room, including any objects, appliances, or people.",
    room: str | None = None,
    sweep: bool = True,
) -> dict[str, Any]:
    """
    Multimodal Visual Search & Inspector:
    Optionally navigates TIAGo to *room*, turns on room lights if dark, sweeps the head camera,
    captures an RGB frame + 3D Supervisor scene detections, and runs multimodal analysis.
    """
    raw = _post("/vision/inspect", {"query": query, "room": room, "sweep": sweep}, timeout=60.0)
    if raw.get("status") == "simulation_unavailable":
        # Fallback to Smart Home Hub objects & humans telemetry
        try:
            objs = httpx.get(f"{SMART_HOME_API_BASE}/api/objects", timeout=3.0).json()
            humans = httpx.get(f"{SMART_HOME_API_BASE}/api/humans", timeout=3.0).json()
            target_rm = (room or "living_room").replace("_", " ").lower()
            room_objs = [
                {"object": o["name"], "room": o["room"], "position": o["position"]}
                for o in objs
                if target_rm in o.get("room", "").lower()
            ]
            room_humans = [
                {"name": h["name"], "room": h["current_room"], "status": h["status"]}
                for h in humans
                if target_rm in h.get("current_room", "").lower()
            ]
            return {
                "status": "ok",
                "room": room or "current_room",
                "query": query,
                "nearby_objects": room_objs,
                "nearby_humans": room_humans,
                "visual_summary": (
                    f"Inspected {room or 'current room'}: detected objects "
                    f"{[o['object'] for o in room_objs] or ['none']} and people "
                    f"{[h['name'] for h in room_humans] or ['none']}."
                ),
            }
        except Exception:
            return raw

    b64 = raw.pop("base64_jpeg", "")
    objs_seen = [o["object"] for o in raw.get("nearby_objects", [])]
    humans_seen = [h["name"] for h in raw.get("nearby_humans", [])]
    summary = (
        f"Visual inspection in {raw.get('room', 'room')}: "
        f"Objects in view: {', '.join(objs_seen) if objs_seen else 'none'}. "
        f"People in view: {', '.join(humans_seen) if humans_seen else 'none'}."
    )

    if b64:
        try:
            from langchain_core.messages import HumanMessage
            from langchain_google_genai import ChatGoogleGenerativeAI

            vlm = ChatGoogleGenerativeAI(
                model=os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash"),
                vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT", "master-inn-505014-t1"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
                temperature=0.1,
            )
            msg = HumanMessage(
                content=[
                    {
                        "type": "text",
                        "text": (
                            f"You are TIAGo's onboard vision system in the {raw.get('room')}. "
                            f"Scene telemetry confirms nearby objects={objs_seen} and humans={humans_seen}. "
                            f"Answer concisely: {query}"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]
            )
            vlm_resp = vlm.invoke([msg])
            if vlm_resp and vlm_resp.content:
                summary = str(vlm_resp.content)
        except Exception:
            pass

    raw["visual_summary"] = summary
    return raw


# ── Errand & Patrol helpers ────────────────────────────────────────────────────

def deliver_item(item: str, from_location: str, to_location: str) -> dict[str, Any]:
    """High-level errand: navigate → magnetic grasp *item* at *from_location* → deliver to *to_location*."""
    res = _post("/errand/deliver", {
        "item": item,
        "from_location": from_location,
        "to_location": to_location,
    })
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={
                    "action": "deliver",
                    "item": item,
                    "from_location": from_location,
                    "to_location": to_location,
                },
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


def fetch_item(item: str, from_location: str) -> dict[str, Any]:
    """High-level errand: navigate to *from_location*, magnetic grasp *item*, return to foyer dock."""
    res = _post("/errand/fetch", {"item": item, "from_location": from_location})
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={"action": "fetch", "item": item, "from_location": from_location},
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


def patrol_home(rooms: list[str] | None = None) -> dict[str, Any]:
    """High-level security patrol errand across multiple rooms with camera sweeps and object/human logging."""
    res = _post("/errand/patrol", {"rooms": rooms})
    if res.get("status") == "simulation_unavailable":
        try:
            return httpx.post(
                f"{SMART_HOME_API_BASE}/api/robots",
                json={"action": "patrol", "rooms": rooms},
                timeout=3.0,
            ).json()
        except Exception:
            pass
    return res


def get_errand_status() -> dict[str, Any]:
    """Return the status and progress of the currently running high-level errand or patrol."""
    return _get("/errand/status")


def list_known_rooms() -> dict[str, Any]:
    """Return the list of named rooms TIAGo knows how to navigate to."""
    res = _get("/rooms")
    if res.get("status") == "simulation_unavailable":
        return {
            "rooms": [
                "foyer", "living_room", "kitchen", "dining_room",
                "master_bedroom", "bathroom", "study_bedroom", "utility_room",
            ]
        }
    return res


def list_known_objects() -> dict[str, Any]:
    """Return a catalogue of objects TIAGo can recognise and interact with, including 3D coordinates."""
    res = _get("/objects")
    if res.get("status") == "simulation_unavailable":
        try:
            objs = httpx.get(f"{SMART_HOME_API_BASE}/api/objects", timeout=3.0).json()
            return {"objects": [o["name"] for o in objs], "details": objs}
        except Exception:
            pass
    return res

