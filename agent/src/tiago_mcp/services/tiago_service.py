"""TIAGo House-Errand Bot – Webots state bridge service.

Communicates with the Webots TIAGo controller via HTTP on localhost:8001,
with fallback to Smart Home Hub on localhost:8000 when running in standalone mode.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

TIAGO_API_BASE = os.getenv("TIAGO_API_URL", "http://127.0.0.1:8001").rstrip("/")
SMART_HOME_API_BASE = os.getenv("SMART_HOME_HUB_URL", "http://127.0.0.1:8000").rstrip("/")
_TIMEOUT = 15.0


async def _get(path: str, timeout: float = _TIMEOUT) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{TIAGO_API_BASE}{path}")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "status": "simulation_unavailable"}


async def _post(path: str, payload: dict[str, Any] | None = None, timeout: float = _TIMEOUT) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{TIAGO_API_BASE}{path}", json=payload or {})
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "status": "simulation_unavailable"}


async def _hub_get(path: str, timeout: float = 3.0) -> Any:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(f"{SMART_HOME_API_BASE}{path}")
        resp.raise_for_status()
        return resp.json()


async def _hub_post(path: str, payload: dict[str, Any], timeout: float = 3.0) -> Any:
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{SMART_HOME_API_BASE}{path}", json=payload)
        resp.raise_for_status()
        return resp.json()


def _create_vision_model() -> Any:
    """Create a multimodal vision model supporting Amazon Bedrock (Nova Pro) or Google Gemini."""
    provider = os.getenv("BEACON_LLM_PROVIDER", "").strip().lower()
    if provider in ("bedrock", "aws", "alexa+") or os.getenv("BEDROCK_MODEL_ID"):
        try:
            from langchain_aws import ChatBedrockConverse  # type: ignore[import-not-found]

            return ChatBedrockConverse(
                model=os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
                region_name=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")),
                temperature=0.1,
            )
        except Exception:
            pass

    from langchain_google_genai import ChatGoogleGenerativeAI

    gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gcp_project:
        return ChatGoogleGenerativeAI(
            model=os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash"),
            vertexai=True,
            project=gcp_project,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            temperature=0.1,
        )
    if api_key:
        return ChatGoogleGenerativeAI(
            model=os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash"),
            google_api_key=api_key,
            temperature=0.1,
        )
    return ChatGoogleGenerativeAI(
        model=os.getenv("BEACON_AGENT_MODEL", "gemini-2.5-flash"),
        vertexai=True,
        location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        temperature=0.1,
    )


# ── Telemetry ──────────────────────────────────────────────────────────────────

async def get_tiago_telemetry() -> dict[str, Any]:
    """Return full TIAGo telemetry: pose, battery, gripper state, current task, held object, patrol logs."""
    res = await _get("/telemetry")
    if res.get("status") == "simulation_unavailable":
        try:
            robots = await _hub_get("/api/robots")
            if robots:
                return robots[0]
        except Exception:
            pass
    return res


# ── Navigation ─────────────────────────────────────────────────────────────────

async def navigate_to_room(room: str) -> dict[str, Any]:
    """Command TIAGo to navigate to a named room in the house."""
    res = await _post("/navigate/room", {"room": room})
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post("/api/robots", {"action": "navigate", "destination": room})
        except Exception:
            pass
    return res


async def navigate_to_pose(x: float, y: float, theta: float) -> dict[str, Any]:
    """Command TIAGo to navigate to an absolute (x, y, θ) pose."""
    return await _post("/navigate/pose", {"x": x, "y": y, "theta": theta})


async def stop_tiago() -> dict[str, Any]:
    """Immediately halt TIAGo's current navigation or manipulation task."""
    res = await _post("/stop")
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post("/api/robots", {"action": "stop"})
        except Exception:
            pass
    return res


async def get_route_plan(destination: str) -> dict[str, Any]:
    """Compute and return the topological waypoint path to *destination*, including any blocking doors."""
    return await _post("/route/plan", {"destination": destination})


# ── Manipulation (Supervisor-Assisted Magnetic Grasp) ─────────────────────────

async def pick_object(object_name: str) -> dict[str, Any]:
    """Command TIAGo to magnetically grasp a named object at its current position."""
    res = await _post("/manipulate/pick", {"object": object_name})
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post("/api/robots", {"action": "pick", "object": object_name})
        except Exception:
            pass
    return res


async def place_object(location: str) -> dict[str, Any]:
    """Command TIAGo to place the held object onto the target room surface."""
    res = await _post("/manipulate/place", {"location": location})
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post("/api/robots", {"action": "place", "location": location})
        except Exception:
            pass
    return res


async def set_gripper(state: str) -> dict[str, Any]:
    """Open or close TIAGo's gripper. *state* must be 'open' or 'closed'."""
    res = await _post("/gripper/set", {"state": state})
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post("/api/robots", {"action": "gripper", "gripper_state": state})
        except Exception:
            pass
    return res


async def set_arm_pose(pose_name: str) -> dict[str, Any]:
    """Move TIAGo's arm to a named preset pose (e.g. 'home', 'carry', 'reach_table', 'reach_floor', 'handover')."""
    res = await _post("/arm/pose", {"pose": pose_name})
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post("/api/robots", {"action": "arm", "pose": pose_name})
        except Exception:
            pass
    return res


# ── Head / Multimodal Perception & Visual Inspector ────────────────────────────

async def look_at(target: str) -> dict[str, Any]:
    """Point TIAGo's head camera toward a named target or direction ('forward', 'left', 'right', 'up', 'down')."""
    return await _post("/head/look_at", {"target": target})


async def get_camera_image() -> dict[str, Any]:
    """Capture a snapshot from TIAGo's head camera and return its metadata and nearby detections."""
    res = await _get("/camera/snapshot")
    if "base64_jpeg" in res:
        res = {k: v for k, v in res.items() if k != "base64_jpeg"}
    return res


async def inspect_scene(
    query: str = "Describe what is visible in the room, including any objects, appliances, or people.",
    room: str | None = None,
    sweep: bool = True,
) -> dict[str, Any]:
    """
    Multimodal Visual Search & Inspector:
    Optionally navigates TIAGo to *room*, turns on room lights if dark, sweeps the head camera,
    captures an RGB frame + 3D Supervisor scene detections, and runs multimodal analysis.
    """
    raw = await _post("/vision/inspect", {"query": query, "room": room, "sweep": sweep}, timeout=60.0)
    if raw.get("status") == "simulation_unavailable":
        # Fallback to Smart Home Hub objects & humans telemetry
        try:
            objs = await _hub_get("/api/objects")
            humans = await _hub_get("/api/humans")
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

            vlm = _create_vision_model()
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
            vlm_resp = await vlm.ainvoke([msg])
            if vlm_resp and vlm_resp.content:
                summary = str(vlm_resp.content)
        except Exception:
            pass

    raw["visual_summary"] = summary
    return raw


# ── Errand & Patrol helpers ────────────────────────────────────────────────────

async def deliver_item(item: str, from_location: str, to_location: str) -> dict[str, Any]:
    """High-level errand: navigate → magnetic grasp *item* at *from_location* → deliver to *to_location*."""
    res = await _post("/errand/deliver", {
        "item": item,
        "from_location": from_location,
        "to_location": to_location,
    })
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post(
                "/api/robots",
                {
                    "action": "deliver",
                    "item": item,
                    "from_location": from_location,
                    "to_location": to_location,
                },
            )
        except Exception:
            pass
    return res


async def fetch_item(item: str, from_location: str) -> dict[str, Any]:
    """High-level errand: navigate to *from_location*, magnetic grasp *item*, return to foyer dock."""
    res = await _post("/errand/fetch", {"item": item, "from_location": from_location})
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post(
                "/api/robots",
                {"action": "fetch", "item": item, "from_location": from_location},
            )
        except Exception:
            pass
    return res


async def patrol_home(rooms: list[str] | None = None) -> dict[str, Any]:
    """High-level security patrol errand across multiple rooms with camera sweeps and object/human logging."""
    res = await _post("/errand/patrol", {"rooms": rooms})
    if res.get("status") == "simulation_unavailable":
        try:
            return await _hub_post("/api/robots", {"action": "patrol", "rooms": rooms})
        except Exception:
            pass
    return res


async def get_errand_status() -> dict[str, Any]:
    """Return the status and progress of the currently running high-level errand or patrol."""
    return await _get("/errand/status")


async def list_known_rooms() -> dict[str, Any]:
    """Return the list of named rooms TIAGo knows how to navigate to."""
    res = await _get("/rooms")
    if res.get("status") == "simulation_unavailable":
        return {
            "rooms": [
                "foyer", "front_door", "living_room", "kitchen", "dining_room",
                "master_bedroom", "bathroom", "study_bedroom", "utility_room",
            ]
        }
    return res


async def list_known_objects() -> dict[str, Any]:
    """Return a catalogue of objects TIAGo can recognise and interact with, including 3D coordinates."""
    res = await _get("/objects")
    if res.get("status") == "simulation_unavailable":
        try:
            objs = await _hub_get("/api/objects")
            return {"objects": [o["name"] for o in objs], "details": objs}
        except Exception:
            pass
    return res

