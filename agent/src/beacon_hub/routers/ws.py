"""WebSocket Multiplexer for Next.js UI (/ws/events), Webots Spawner (/ws/sim-bridge), and Device Controllers (/ws/device/{device_id})."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..broker import get_broker
from ..database.connection import get_db

logger = logging.getLogger("beacon_hub.ws")

router = APIRouter(tags=["websockets"])


@router.websocket("/ws/events")
async def ws_ui_events(ws: WebSocket) -> None:
    """
    Zero-polling WebSocket stream for the Next.js Web UI & Assistant UI.
    Immediately sends an initial `hub.snapshot` with floorplan + summary,
    then streams all `device.state.*`, `device.lifecycle.*`, `sensor.telemetry.*`,
    `robot.telemetry.tiago`, and `environment.updated` events in real time.
    """
    await ws.accept()
    db = get_db()
    broker = get_broker()
    await broker.register_ui_socket(ws)
    try:
        snapshot = {
            "topic": "hub.snapshot",
            "payload": {
                "sim_mode": broker.sim_mode,
                "summary": db.get_summary(sim_mode=broker.sim_mode),
                "rooms": db.list_rooms(),
                "devices": db.list_devices(),
                "nav_nodes": db.list_nav_nodes(),
                "nav_edges": db.list_nav_edges(),
                "robot": db.get_robot("tiago"),
                "environment": db.get_environment(),
            },
        }
        await ws.send_text(json.dumps(snapshot))

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await ws.send_text(
                        json.dumps({"topic": "hub.pong", "sim_mode": broker.sim_mode})
                    )
            except Exception:  # noqa: BLE001
                pass
    except WebSocketDisconnect:
        pass
    finally:
        broker.unregister_ui_socket(ws)


@router.websocket("/ws/sim-bridge")
async def ws_sim_bridge(ws: WebSocket) -> None:
    """
    WebSocket bridge for Webots `world_spawner` and `tiago_home_controller`.
    On attach, sends `sim.init_manifest` containing all SQLite devices and their current
    `reported_state` + TIAGo's current `(x, y, theta)` for seamless hot-attach spawning.
    """
    await ws.accept()
    db = get_db()
    broker = get_broker()
    await broker.register_sim_bridge_socket(ws)

    try:
        manifest = {
            "topic": "sim.init_manifest",
            "payload": {
                "devices": db.list_devices(),
                "robot": db.get_robot("tiago"),
                "environment": db.get_environment(),
                "nav_nodes": db.list_nav_nodes(),
                "nav_edges": db.list_nav_edges(),
            },
        }
        await ws.send_text(json.dumps(manifest))

        while True:
            raw = await ws.receive_text()
            await _handle_incoming_sim_message(raw)
    except WebSocketDisconnect:
        pass
    finally:
        broker.unregister_sim_bridge_socket(ws)


@router.websocket("/ws/device/{device_id}")
async def ws_device_controller(ws: WebSocket, device_id: str) -> None:
    """
    Isolated per-device WebSocket channel for `iot_device_controller` instances.
    """
    await ws.accept()
    db = get_db()
    broker = get_broker()
    await broker.register_device_socket(device_id, ws)

    try:
        dev = db.strict_lookup(device_id)
        if dev:
            await ws.send_text(
                json.dumps({"topic": "device.config", "payload": dev})
            )
        while True:
            raw = await ws.receive_text()
            await _handle_incoming_sim_message(raw)
    except WebSocketDisconnect:
        pass
    finally:
        broker.unregister_device_socket(device_id, ws)


async def _handle_incoming_sim_message(raw: str) -> None:
    db = get_db()
    broker = get_broker()
    try:
        msg: dict[str, Any] = json.loads(raw)
    except Exception:  # noqa: BLE001
        return

    topic = str(msg.get("topic", ""))
    payload = msg.get("payload", {})
    if not topic:
        return

    broker.record_heartbeat(
        sim_time=float(payload.get("sim_time", 0.0)),
        fps=float(payload.get("fps", 60.0)),
    )

    if topic == "sim.bridge.heartbeat":
        await broker.publish(topic, payload)
        return

    if topic.startswith("device.state."):
        dev_id = payload.get("device_id")
        state_patch = payload.get("state", {})
        if dev_id and isinstance(state_patch, dict):
            try:
                updated = db.update_reported_state(dev_id, state_patch)
                payload["state"] = updated
            except KeyError:
                pass
        await broker.publish(topic, payload)

    elif topic.startswith("sensor.telemetry."):
        dev_id = payload.get("device_id")
        if dev_id:
            try:
                db.update_reported_state(
                    dev_id,
                    {
                        "triggered": bool(payload.get("triggered", False)),
                        "value": float(payload.get("value", 1000.0)),
                        "state": str(payload.get("state", "Clear")),
                    },
                )
            except KeyError:
                pass
        await broker.publish(topic, payload)

    elif topic == "robot.telemetry.tiago":
        pose = payload.get("pose", {})
        updates: dict[str, Any] = {"online": 1}
        if "x" in pose:
            updates["pose_x"] = float(pose["x"])
        if "y" in pose:
            updates["pose_y"] = float(pose["y"])
        if "theta" in pose:
            updates["theta"] = float(pose["theta"])
        if "battery" in payload:
            updates["battery_pct"] = float(payload["battery"])
        if "status" in payload:
            updates["status"] = str(payload["status"])
        if "task" in payload:
            updates["task_description"] = str(payload["task"])
        if "arm_pose" in payload:
            updates["arm_pose"] = str(payload["arm_pose"])
        if "gripper" in payload:
            updates["gripper"] = str(payload["gripper"])
        if "held_object" in payload:
            updates["held_object"] = str(payload["held_object"])
        if "active_route" in payload:
            updates["active_waypoints_json"] = json.dumps(payload["active_route"])

        robot_rec = db.update_robot("tiago", **updates)
        payload["current_room"] = robot_rec["current_room"]
        await broker.publish(topic, payload)

    elif topic == "pedestrian.telemetry":
        await broker.publish(topic, payload)

    elif topic == "camera.frame":
        cam_name = payload.get("camera_name")
        b64_jpeg = payload.get("jpeg_base64")
        if cam_name and b64_jpeg:
            try:
                broker.update_camera_frame(cam_name, base64.b64decode(b64_jpeg))
            except Exception:  # noqa: BLE001
                pass
