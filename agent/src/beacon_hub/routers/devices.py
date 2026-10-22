"""Strict ID/wbt_name device state, command, scene, and robot endpoints."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

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
