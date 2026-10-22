"""Strict ID/wbt_name device state, command, scene, and robot endpoints."""

from __future__ import annotations

import asyncio
import base64
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, Response, StreamingResponse

from ..broker import get_broker
from ..database.connection import get_db
from ..database.models import CommandRequest

router = APIRouter(tags=["devices"])

KNOWN_OBJECTS: list[str] = [
    "cup",
    "bottle",
    "plate",
    "book",
    "remote_control",
    "medicine_box",
    "glasses",
    "phone",
    "keys",
    "tray",
]


def strict_not_found_payload(identifier: str, domain: str | None = None) -> dict[str, Any]:
    domain_arg = f"domain='{domain}'" if domain else ""
    return {
        "success": False,
        "error_code": "DEVICE_NOT_FOUND_STRICT",
        "message": (
            f"No device matched exact id or wbt_name '{identifier}'. "
            f"Fuzzy matching is disabled. Call get_devices({domain_arg}) first "
            "to retrieve exact 'id' or 'wbt_name' values."
        ),
    }


async def _dispatch_device_command(
    dev: dict[str, Any], action: str, params: dict[str, Any]
) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"

    db.update_desired_state(dev["id"], params)
    cmd_payload = {
        "command_id": cmd_id,
        "device_id": dev["id"],
        "wbt_name": dev["wbt_name"],
        "wbt_def": dev.get("wbt_def"),
        "domain": dev["domain"],
        "action": action,
        "params": params,
    }
    topic = f"device.command.{dev['domain']}.{dev['id']}"
    db.log_event(topic, cmd_payload)
    await broker.publish(topic, cmd_payload)

    # Give VirtualPhysicsWorker or Webots bridge a brief yield to update reported_state
    await asyncio.sleep(0.02)
    refreshed = db.strict_lookup(dev["id"])
    return refreshed or dev


# ═══════════════════════════════════════════════════════════════════════════════
# V2 Unified Strict Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/v2/devices")
async def list_v2_devices(
    domain: str | None = Query(None),
    room_id: str | None = Query(None),
) -> list[dict[str, Any]]:
    db = get_db()
    return db.list_devices(domain=domain, room_id=room_id)


@router.get("/api/v2/devices/{identifier}")
async def get_v2_device(identifier: str) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier)
    if not dev:
        return JSONResponse(status_code=404, content=strict_not_found_payload(identifier))
    return dev


@router.post("/api/v2/devices/{identifier}/command")
async def command_v2_device(identifier: str, req: CommandRequest) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier)
    if not dev:
        return JSONResponse(status_code=404, content=strict_not_found_payload(identifier))
    updated = await _dispatch_device_command(dev, req.action, req.params)
    return {
        "success": True,
        "device": updated,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Home Summary, Scenes & Environment
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/home/summary")
async def get_home_summary() -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    return db.get_summary(sim_mode=broker.sim_mode)


@router.post("/api/home/environment")
async def update_environment(req: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    tod = str(req.get("time_of_day", "day")).lower()
    env = db.set_environment(tod)
    await broker.publish("environment.updated", env)
    return env


@router.post("/api/home/scene")
async def trigger_scene(req: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    scene = str(req.get("scene", "morning")).lower()

    if scene == "morning":
        env = db.set_environment("day")
        await broker.publish("environment.updated", env)
        for b in db.list_devices("blind"):
            await _dispatch_device_command(b, "set_state", {"position": 100})
        for l_dev in db.list_devices("light"):
            is_ext = "Bollard" in l_dev["wbt_name"] or "Patio" in l_dev["wbt_name"]
            await _dispatch_device_command(
                l_dev,
                "set_state",
                {"power_state": "off" if is_ext else "on", "brightness": 0 if is_ext else 80},
            )
    elif scene == "away":
        for l_dev in db.list_devices("light"):
            await _dispatch_device_command(l_dev, "set_state", {"power_state": "off"})
        for b in db.list_devices("blind"):
            await _dispatch_device_command(b, "set_state", {"position": 0})
        for d in db.list_devices("door"):
            await _dispatch_device_command(
                d, "set_state", {"open_state": "closed", "locked": True, "position": 0}
            )
    elif scene == "movie":
        env = db.set_environment("sunset")
        await broker.publish("environment.updated", env)
        for b in db.list_devices("blind"):
            await _dispatch_device_command(b, "set_state", {"position": 0})
        for l_dev in db.list_devices("light"):
            in_living = l_dev["room_id"] == "living_room"
            await _dispatch_device_command(
                l_dev,
                "set_state",
                {
                    "power_state": "on" if in_living else "off",
                    "brightness": 25 if in_living else 0,
                    "color": "warm white",
                },
            )
        tv = db.strict_lookup("Living Room Smart TV", domain="appliance")
        if tv:
            await _dispatch_device_command(
                tv, "set_state", {"power_state": "on", "mode": "Cinema 4K HDR"}
            )
    elif scene == "night":
        env = db.set_environment("night")
        await broker.publish("environment.updated", env)
        for b in db.list_devices("blind"):
            await _dispatch_device_command(b, "set_state", {"position": 0})
        for d in db.list_devices("door"):
            await _dispatch_device_command(
                d, "set_state", {"open_state": "closed", "locked": True, "position": 0}
            )
        for l_dev in db.list_devices("light"):
            is_ext = "Bollard" in l_dev["wbt_name"] or "Porch" in l_dev["wbt_name"]
            await _dispatch_device_command(
                l_dev,
                "set_state",
                {"power_state": "on" if is_ext else "off", "brightness": 60 if is_ext else 0},
            )

    await broker.publish("scene.triggered", {"scene": scene})
    return {"success": True, "scene": scene}


# ═══════════════════════════════════════════════════════════════════════════════
# Domain Endpoints (Strict ID/wbt_name matching)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/lights")
async def get_lights() -> list[dict[str, Any]]:
    db = get_db()
    return [db.format_light(d) for d in db.list_devices("light")]


@router.get("/api/lights/{identifier}")
async def get_light_by_id(identifier: str) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier, domain="light")
    if not dev:
        return JSONResponse(status_code=404, content=strict_not_found_payload(identifier, "light"))
    return db.format_light(dev)


@router.post("/api/lights/{identifier}/toggle")
async def toggle_light(identifier: str) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier, domain="light")
    if not dev:
        return JSONResponse(status_code=404, content=strict_not_found_payload(identifier, "light"))
    updated = await _dispatch_device_command(dev, "toggle", {})
    return {"success": True, **db.format_light(updated)}


@router.post("/api/lights/{identifier}/state")
async def set_light_state_endpoint(identifier: str, req: dict[str, Any]) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier, domain="light")
    if not dev:
        return JSONResponse(status_code=404, content=strict_not_found_payload(identifier, "light"))
    updated = await _dispatch_device_command(dev, "set_state", req)
    return {"success": True, **db.format_light(updated)}


@router.get("/api/doors")
async def get_doors() -> list[dict[str, Any]]:
    db = get_db()
    return [db.format_door(d) for d in db.list_devices("door")]


@router.post("/api/doors/{identifier}/state")
async def update_door_state(identifier: str, req: dict[str, Any]) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier, domain="door")
    if not dev:
        return JSONResponse(status_code=404, content=strict_not_found_payload(identifier, "door"))
    updated = await _dispatch_device_command(dev, "set_state", req)
    return {"success": True, **db.format_door(updated)}


@router.get("/api/blinds")
async def get_blinds() -> list[dict[str, Any]]:
    db = get_db()
    return [db.format_blind(d) for d in db.list_devices("blind")]


@router.post("/api/blinds/{identifier}/state")
async def update_blind_state(identifier: str, req: dict[str, Any]) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier, domain="blind")
    if not dev:
        return JSONResponse(status_code=404, content=strict_not_found_payload(identifier, "blind"))
    updated = await _dispatch_device_command(dev, "set_state", req)
    return {"success": True, **db.format_blind(updated)}


@router.get("/api/climate")
async def get_climate_zones() -> list[dict[str, Any]]:
    db = get_db()
    return [db.format_climate(d) for d in db.list_devices("climate")]


@router.post("/api/climate/{identifier}/state")
async def update_climate_zone(identifier: str, req: dict[str, Any]) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier, domain="climate")
    if not dev:
        return JSONResponse(
            status_code=404, content=strict_not_found_payload(identifier, "climate")
        )
    updated = await _dispatch_device_command(dev, "set_state", req)
    return {"success": True, **db.format_climate(updated)}


@router.get("/api/appliances")
async def get_appliances() -> list[dict[str, Any]]:
    db = get_db()
    return [db.format_appliance(d) for d in db.list_devices("appliance")]


@router.post("/api/appliances/{identifier}/state")
async def update_appliance_state(identifier: str, req: dict[str, Any]) -> Any:
    db = get_db()
    dev = db.strict_lookup(identifier, domain="appliance")
    if not dev:
        return JSONResponse(
            status_code=404, content=strict_not_found_payload(identifier, "appliance")
        )
    updated = await _dispatch_device_command(dev, "set_state", req)
    return {"success": True, **db.format_appliance(updated)}


@router.get("/api/sensors")
async def get_sensors() -> list[dict[str, Any]]:
    db = get_db()
    return [db.format_sensor(d) for d in db.list_devices("sensor")]


@router.get("/api/cameras")
async def get_cameras() -> list[dict[str, Any]]:
    db = get_db()
    cams = [db.format_camera(d) for d in db.list_devices("camera")]
    cams.append(
        {
            "id": "TIAGo Camera",
            "wbt_name": "TIAGo Camera",
            "name": "TIAGo Camera",
            "room_id": "foyer",
            "state": "Online",
            "metadata": "Live • 640x480 (Orbbec Astra RGB)",
            "type": "Camera",
            "translation": [-3.1, -7.62, 1.2],
        }
    )
    return cams


@router.get("/api/cameras/{name}/frame")
async def camera_single_frame(name: str, format: str = Query("jpeg")) -> Response:
    from ..main import get_fallback_worker

    broker = get_broker()
    worker = get_fallback_worker()

    live_frame = broker.get_camera_frame(name)
    if live_frame and broker.is_webots_attached:
        frame = live_frame
        source = "webots_live"
    else:
        frame = worker.render_synthetic_camera_frame(name)
        source = "synthetic_fallback"

    if format == "base64":
        return JSONResponse({
            "camera_name": name,
            "source": source,
            "mime_type": "image/jpeg",
            "jpeg_base64": base64.b64encode(frame).decode("ascii"),
            "stream_url": f"/api/cameras/{name}/stream",
        })

    return Response(content=frame, media_type="image/jpeg")


@router.get("/api/cameras/{name}/stream")
async def camera_stream(name: str) -> StreamingResponse:
    from ..main import get_fallback_worker

    broker = get_broker()
    worker = get_fallback_worker()

    async def frame_generator() -> AsyncGenerator[bytes]:
        while True:
            live_frame = broker.get_camera_frame(name)
            if live_frame and broker.is_webots_attached:
                frame = live_frame
            else:
                frame = worker.render_synthetic_camera_frame(name)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
            await asyncio.sleep(0.15)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TIAGo Robot & Route Planning Endpoints (Event Broker Backed)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/robots")
async def get_robots() -> list[dict[str, Any]]:
    db = get_db()
    return [db.get_robot("tiago")]


@router.post("/api/robots")
async def control_robot_endpoint(req: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    action = str(req.get("action", "navigate")).lower()

    if action == "navigate":
        dest = req.get("destination") or req.get("room")
        if dest:
            robot = db.get_robot("tiago")
            try:
                plan = db.compute_route(robot["pose"]["x"], robot["pose"]["y"], str(dest))
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            # Request the Hub Event Broker to open any blocking doors on the path via BarrierActuatorWorker
            for bd in plan.get("blocking_doors", []):
                door_dev = db.strict_lookup(bd["id"], domain="door")
                if door_dev:
                    await _dispatch_device_command(
                        door_dev,
                        "set_state",
                        {"open_state": "open", "locked": False, "position": 100},
                    )
            cmd = {
                "task_id": uuid.uuid4().hex[:8],
                "action": "navigate",
                "destination": plan["destination"],
                "room": plan["destination"],
                "waypoints": plan["waypoints"],
                "blocking_doors": plan["blocking_doors"],
            }
            await broker.publish("robot.command.tiago", cmd)
            return {
                "success": True,
                "status": "navigating",
                "room": plan["destination"],
                "destination_name": plan["destination_name"],
                "origin": plan["origin"],
                "origin_pose": plan["origin_pose"],
                "distance_m": plan["distance_m"],
                "eta_seconds": plan["eta_seconds"],
                "waypoints": plan["waypoints"],
                "blocking_doors": plan["blocking_doors"],
                "doors_on_path_details": plan["doors_on_path_details"],
                "target": plan["waypoints"][-1] if plan["waypoints"] else robot["pose"],
            }
        elif "x" in req and "y" in req:
            wp = {"x": float(req["x"]), "y": float(req["y"]), "theta": float(req.get("theta", 0.0))}
            await broker.publish(
                "robot.command.tiago",
                {"task_id": uuid.uuid4().hex[:8], "action": "navigate", "waypoints": [wp]},
            )
            return {"success": True, "status": "navigating", "target": wp}

    await broker.publish("robot.command.tiago", req)
    await asyncio.sleep(0.02)
    return {"success": True, "status": action, "robot": db.get_robot("tiago")}


@router.post("/api/v2/robots/tiago/route")
async def plan_tiago_route_endpoint(req: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    dest = str(req.get("destination", "foyer"))
    robot = db.get_robot("tiago")
    try:
        return db.compute_route(robot["pose"]["x"], robot["pose"]["y"], dest)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/api/v2/robots/tiago/rooms")
async def list_tiago_rooms_endpoint() -> dict[str, Any]:
    db = get_db()
    nodes = db.list_nav_nodes()
    return {
        "rooms": [n["id"] for n in nodes],
        "nodes": nodes,
    }


@router.get("/api/v2/robots/tiago/objects")
async def list_tiago_objects_endpoint() -> dict[str, Any]:
    return {"objects": KNOWN_OBJECTS}


@router.get("/api/v2/robots/tiago/errand")
async def get_tiago_errand_endpoint() -> dict[str, Any]:
    db = get_db()
    return db.get_latest_errand()


@router.post("/api/v2/robots/tiago/errand")
async def start_tiago_errand_endpoint(req: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    errand_type = str(req.get("errand_type", req.get("action", "fetch"))).lower()
    item = str(req.get("item", "cup"))
    from_loc = str(req.get("from_location", "kitchen"))
    to_loc = str(req.get("to_location", "foyer" if errand_type == "fetch" else "living_room"))
    task_id = uuid.uuid4().hex[:8]

    robot = db.get_robot("tiago")
    try:
        route_to_source = db.compute_route(robot["pose"]["x"], robot["pose"]["y"], from_loc)
        src_wp = route_to_source["waypoints"][-1] if route_to_source["waypoints"] else robot["pose"]
        route_to_dest = db.compute_route(src_wp["x"], src_wp["y"], to_loc)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    combined_wps = [*route_to_source["waypoints"], *route_to_dest["waypoints"]]
    total_dist = round(route_to_source["distance_m"] + route_to_dest["distance_m"], 2)
    blocking = [*route_to_source["blocking_doors"], *route_to_dest["blocking_doors"]]
    eta_seconds = round((total_dist / 0.6) + (len(blocking) * 2.0) + 4.0, 1)

    await broker.publish(
        "robot.command.tiago",
        {
            "task_id": task_id,
            "action": errand_type,
            "item": item,
            "from_location": from_loc,
            "to_location": to_loc,
        },
    )
    return {
        "status": "started",
        "task_id": task_id,
        "errand": errand_type,
        "item": item,
        "from_location": from_loc,
        "to_location": to_loc,
        "origin": route_to_source["origin"],
        "origin_pose": route_to_source["origin_pose"],
        "destination": route_to_dest["destination"],
        "destination_name": route_to_dest["destination_name"],
        "waypoints": combined_wps,
        "distance_m": total_dist,
        "eta_seconds": eta_seconds,
        "blocking_doors": blocking,
        "doors_on_path_details": [
            *route_to_source["doors_on_path_details"],
            *route_to_dest["doors_on_path_details"],
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Event Rules & History Endpoints
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/api/v2/events/recent")
async def get_recent_events_endpoint(limit: int = Query(25, ge=1, le=100)) -> list[dict[str, Any]]:
    return get_db().list_recent_events(limit=limit)


@router.get("/api/v2/events/rules")
async def list_event_rules_endpoint() -> list[dict[str, Any]]:
    return get_db().list_event_rules()


@router.post("/api/v2/events/rules")
async def create_event_rule_endpoint(req: dict[str, Any]) -> dict[str, Any]:
    rule = get_db().create_event_rule(
        name=str(req.get("name", "Custom Rule")),
        trigger_topic=str(req.get("trigger_topic", "sensor.telemetry.*")),
        condition=req.get("condition", {}),
        actions=req.get("actions", []),
        agent_prompt=req.get("agent_prompt"),
        cooldown_sec=float(req.get("cooldown_sec", 15.0)),
    )
    await get_broker().publish("event.rule.created", rule)
    return {"success": True, "rule": rule}


@router.delete("/api/v2/events/rules/{rule_id}")
async def delete_event_rule_endpoint(rule_id: str) -> dict[str, Any]:
    deleted = get_db().delete_event_rule(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
    await get_broker().publish("event.rule.deleted", {"rule_id": rule_id})
    return {"success": True, "rule_id": rule_id}


# ═══════════════════════════════════════════════════════════════════════════════
# Physical Simulation Stimulus Scenarios (Webots 3D Spawner & Virtual Twin)
# ═══════════════════════════════════════════════════════════════════════════════

SIM_STIMULUS_PRESETS: dict[str, dict[str, Any]] = {
    "guest_front_door": {
        "id": "guest_front_door",
        "title": "Guest Arrives at Front Door",
        "description": "Spawns a 3D guest avatar at (1.15, -7.49) directly in front of the Front Porch Motion Sensor ray and Front Door Camera.",
        "wbt_def": "STIM_GUEST_PORCH",
        "name": "Front Porch Visitor",
        "kind": "human",
        "room_id": "courtyard",
        "translation": [1.15, -7.49, 0.0],
        "color": [0.14, 0.65, 0.92],
        "sensor_id": "front_porch_motion_sensor",
        "camera_name": "Front Door Camera",
        "auto_actions": [
            {"device_id": "dev_light_11", "params": {"power_state": "on", "brightness": 100}},
        ],
        "agent_prompt": (
            "Front Porch Motion Sensor was just triggered by a visitor at the Front Entrance Door. "
            "Inspect 'Front Door Camera' to verify the guest and announce their arrival."
        ),
    },
    "resident_living_room": {
        "id": "resident_living_room",
        "title": "Resident Enters Living Room",
        "description": "Spawns a 3D resident avatar at (-4.85, -2.50) in the Living Room Motion Sensor ray and Living Room Camera FOV.",
        "wbt_def": "STIM_RESIDENT_LIVING",
        "name": "Resident in Living Room",
        "kind": "human",
        "room_id": "living_room",
        "translation": [-4.85, -2.50, 0.0],
        "color": [0.16, 0.78, 0.52],
        "sensor_id": "living_room_motion_sensor",
        "camera_name": "Living Room Camera",
        "auto_actions": [
            {"device_id": "dev_light_03", "params": {"power_state": "on", "brightness": 90}},
            {"device_id": "living_room_smart_tv", "params": {"power_state": "on", "mode": "Ambient Art"}},
        ],
        "agent_prompt": (
            "Living Room Motion Sensor detected the resident entering the Living Room. "
            "Check 'Living Room Camera' and ask if they need TIAGo to bring anything from the kitchen."
        ),
    },
    "vehicle_driveway": {
        "id": "vehicle_driveway",
        "title": "Vehicle Pulls Up to Driveway Gate",
        "description": "Spawns a 3D vehicle at (2.10, -8.10) in front of the Driveway Gate Motion Sensor ray and Driveway Camera.",
        "wbt_def": "STIM_VEHICLE_DRIVEWAY",
        "name": "Arriving SUV",
        "kind": "vehicle",
        "room_id": "courtyard",
        "translation": [2.10, -8.10, 0.45],
        "color": [0.85, 0.38, 0.18],
        "sensor_id": "driveway_gate_motion_sensor",
        "camera_name": "Driveway Camera",
        "auto_actions": [
            {"device_id": "dev_light_12", "params": {"power_state": "on", "brightness": 100}},
            {"device_id": "driveway_gate", "params": {"open_state": "open", "locked": False, "position": 100}},
        ],
        "agent_prompt": (
            "Driveway Gate Motion Sensor triggered! A vehicle just pulled into the forecourt. "
            "Inspect 'Driveway Camera' and confirm that the Driveway Gate opened safely."
        ),
    },
    "intruder_hallway": {
        "id": "intruder_hallway",
        "title": "Motion in West Corridor",
        "description": "Spawns a 3D figure at (-4.45, -7.50) across the Hallway Motion Sensor beam.",
        "wbt_def": "STIM_HALLWAY_PERSON",
        "name": "Corridor Figure",
        "kind": "human",
        "room_id": "corridor",
        "translation": [-4.45, -7.50, 0.0],
        "color": [0.92, 0.22, 0.28],
        "sensor_id": "hallway_motion_sensor",
        "camera_name": "TIAGo Camera",
        "auto_actions": [
            {"device_id": "dev_light_04", "params": {"power_state": "on", "brightness": 100}},
            {"device_id": "dev_light_05", "params": {"power_state": "on", "brightness": 100}},
        ],
        "agent_prompt": (
            "Hallway Motion Sensor detected movement in the corridor. "
            "Use 'TIAGo Camera' or 'Front Door Camera' to inspect the hallway immediately."
        ),
    },
    "sudden_nightfall": {
        "id": "sudden_nightfall",
        "title": "Sudden Dusk / Nightfall Drop",
        "description": "Drops Webots SUN_LIGHT luminosity to 0.04 so the roof Exterior Daylight Sensor trips (< 300 lux).",
        "wbt_def": "NONE",
        "name": "Nightfall",
        "kind": "environment",
        "room_id": "courtyard",
        "translation": [-3.5, -5.0, 2.6],
        "color": [0.4, 0.4, 0.9],
        "sensor_id": "exterior_daylight_sensor",
        "camera_name": "Backyard Patio Camera",
        "auto_actions": [
            {"device_id": "dev_light_11", "params": {"power_state": "on", "brightness": 85}},
            {"device_id": "dev_light_12", "params": {"power_state": "on", "brightness": 85}},
            {"device_id": "dev_light_13", "params": {"power_state": "on", "brightness": 75}},
        ],
        "agent_prompt": (
            "The Exterior Daylight Sensor detected nightfall (low ambient lux). "
            "Verify exterior bollard lights are on and offer to close the blinds and lock the perimeter."
        ),
    },
}


@router.get("/api/v2/sim/stimuli")
async def list_sim_stimuli() -> list[dict[str, Any]]:
    return list(SIM_STIMULUS_PRESETS.values())


@router.post("/api/v2/sim/stimulus")
async def trigger_sim_stimulus(req: dict[str, Any]) -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    scenario_id = str(req.get("scenario_id", ""))
    trigger_agent = bool(req.get("trigger_agent", True))

    if scenario_id == "clear_all":
        all_defs = [
            p["wbt_def"] for p in SIM_STIMULUS_PRESETS.values() if p["wbt_def"] != "NONE"
        ]
        await broker.publish("sim.stimulus.clear", {"wbt_defs": all_defs})
        # Reset motion sensors in SQLite when cleared
        for p in SIM_STIMULUS_PRESETS.values():
            if p["kind"] != "environment":
                s_dev = db.strict_lookup(p["sensor_id"])
                if s_dev:
                    rep = {"type": "MotionSensor", "state": "Clear", "value": 1000.0, "triggered": False}
                    db.update_reported_state(s_dev["id"], rep, also_sync_desired=True)
                    await broker.publish(
                        f"sensor.telemetry.{s_dev['id']}",
                        {
                            "device_id": s_dev["id"],
                            "wbt_name": s_dev["wbt_name"],
                            "triggered": False,
                            "value": 1000.0,
                            "state": "Clear",
                        },
                    )
        return {"success": True, "cleared": all_defs}

    preset = SIM_STIMULUS_PRESETS.get(scenario_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Unknown stimulus scenario '{scenario_id}'")

    # 1. If it's an environment event (nightfall), update Webots SUN_LIGHT
    if preset["kind"] == "environment":
        env = db.set_environment("night")
        await broker.publish("environment.updated", env)
    else:
        # Spawn physical 3D Human/Vehicle in Webots directly in front of the DistanceSensor ray
        await broker.publish("sim.stimulus.spawn", preset)

    # 2. If Webots is not attached (or while Webots ray-cast steps in the next 250ms),
    # ensure the sensor state & automated device reactions fire deterministically
    sensor_dev = db.strict_lookup(preset["sensor_id"])
    if sensor_dev:
        is_daylight = preset["kind"] == "environment"
        sim_val = 40.0 if is_daylight else 320.0
        sim_state = "Low Light / Night" if is_daylight else "Motion Detected"
        db.update_reported_state(
            sensor_dev["id"],
            {"triggered": True, "value": sim_val, "state": sim_state},
            also_sync_desired=True,
        )
        await broker.publish(
            f"sensor.telemetry.{sensor_dev['id']}",
            {
                "device_id": sensor_dev["id"],
                "wbt_name": sensor_dev["wbt_name"],
                "triggered": True,
                "value": sim_val,
                "state": sim_state,
                "stimulus": scenario_id,
            },
        )

    executed: list[str] = []
    for act in preset.get("auto_actions", []):
        target_dev = db.strict_lookup(act["device_id"])
        if target_dev:
            await _dispatch_device_command(target_dev, "set_state", act["params"])
            executed.append(f"{target_dev['wbt_name']} -> {act['params']}")

    alert_payload = {
        "alert_id": f"stim_{uuid.uuid4().hex[:8]}",
        "rule_id": scenario_id,
        "rule_name": preset["title"],
        "trigger_topic": f"sensor.telemetry.{preset['sensor_id']}",
        "message": preset["description"],
        "executed_actions": executed,
        "camera_name": preset["camera_name"],
        "agent_prompt": preset["agent_prompt"] if trigger_agent else None,
        "timestamp": time.time(),
    }
    db.log_event("agent.event.alert", alert_payload)
    await broker.publish("agent.event.alert", alert_payload)

    return {
        "success": True,
        "scenario": preset,
        "alert": alert_payload,
    }
