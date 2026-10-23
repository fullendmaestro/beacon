"""Hot-swappable DB-driven Virtual Physics & Kinematics Worker."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import math
import time
import uuid
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageDraw

from ..broker import EventBroker
from ..database.connection import DatabaseManager
from ..database.models import ColorUtils

logger = logging.getLogger("beacon_hub.fallback")


@dataclass
class ActiveInterpolation:
    device_id: str
    wbt_name: str
    domain: str
    start_pos: float
    target_pos: float
    start_time: float
    duration: float = 1.5
    locked: bool | None = None


class VirtualPhysicsWorker:
    """
    Database-driven virtual physics engine that automatically activates when Webots is
    offline (`sim.bridge.heartbeat` > 1.5s) and yields seamlessly when Webots attaches.
    - Interpolates door/gate/blind actuation over 1.5s at 20Hz.
    - Moves TIAGo along orthogonal Manhattan segments at 0.6 m/s (or faster in errands)
      and triggers virtual MotionSensors based on Euclidean distance to sensor coordinates.
    - Renders synthetic live JPEG camera feeds annotated with real-time SQLite room states.
    """

    def __init__(self, db: DatabaseManager, broker: EventBroker) -> None:
        self.db = db
        self.broker = broker
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._interpolations: dict[str, ActiveInterpolation] = {}
        self._nav_waypoints: list[dict[str, Any]] = []
        self._nav_target_room: str | None = None
        self._robot_speed_mps: float = 1.2  # Responsive 1.2 m/s virtual speed (ETA uses 0.6 m/s baseline)
        self._errand_task: asyncio.Task[None] | None = None

        # Subscribe to device and robot commands on the Event Broker
        self.broker.subscribe("device.command.*", self._on_device_command)
        self.broker.subscribe("robot.command.tiago", self._on_robot_command)
        self._last_robot_pos: tuple[float, float] | None = None
        self._sensor_hold_until: dict[str, float] = {}
        self.broker.subscribe("sim.stimulus.spawn", self._on_sim_stimulus_spawn)

    async def _on_sim_stimulus_spawn(self, _topic: str, payload: dict[str, Any]) -> None:
        sensor_id = payload.get("sensor_id")
        if sensor_id:
            # Keep virtual motion sensor held for 8s when a stimulus is spawned
            self._sensor_hold_until[str(sensor_id)] = time.monotonic() + 8.0


    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_loop(), name="virtual-physics-worker")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _on_device_command(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle device commands when in VIRTUAL_PHYSICS_FALLBACK mode."""
        if self.broker.is_webots_attached:
            return

        parts = topic.split(".", 3)
        if len(parts) < 4:
            return
        domain, device_id = parts[2], parts[3]
        dev = self.db.strict_lookup(device_id)
        if not dev:
            return

        action = payload.get("action", "set_state")
        params = payload.get("params", {})
        rep = dict(dev["reported_state"])

        if domain == "light":
            max_int = float(dev["config"].get("maxIntensity", 3.0))
            curr_on = rep.get("state", "On") == "On"
            curr_b = int(rep.get("brightness", 100))

            if action == "toggle":
                target_on = not curr_on
                target_b = curr_b if curr_b > 0 else 100
            else:
                target_on = curr_on
                if params.get("power_state") is not None:
                    target_on = str(params["power_state"]).lower() == "on"
                target_b = curr_b if curr_b > 0 else 100
                if params.get("brightness") is not None:
                    b_val = max(0, min(100, int(params["brightness"])))
                    if b_val == 0:
                        target_on = False
                        target_b = 0
                    else:
                        target_on = True
                        target_b = b_val
                if params.get("color") is not None:
                    rgb = ColorUtils.parse(params["color"])
                    rep["color_rgb"] = rgb
                    rep["color"] = ColorUtils.to_hex(rgb)

            intensity = round((target_b / 100.0) * max_int, 2) if target_on else 0.0
            rep["state"] = "On" if target_on else "Off"
            rep["power_state"] = "on" if target_on else "off"
            rep["brightness"] = target_b if target_on else 0
            rep["intensity"] = intensity
            rep["metadata"] = f"Intensity at {intensity:.1f}"

            updated = self.db.update_reported_state(dev["id"], rep, also_sync_desired=True)
            await self.broker.publish(
                f"device.state.light.{dev['id']}",
                {
                    "device_id": dev["id"],
                    "wbt_name": dev["wbt_name"],
                    "domain": "light",
                    "state": updated,
                    "source": "virtual_physics",
                },
            )

        elif domain in ("door", "blind"):
            curr_pos = float(rep.get("position", 0))
            target_pos = curr_pos
            if params.get("open_state") is not None:
                target_pos = 100.0 if str(params["open_state"]).lower() == "open" else 0.0
            if params.get("position") is not None:
                target_pos = float(max(0, min(100, int(params["position"]))))

            locked = rep.get("locked", False)
            if params.get("locked") is not None:
                locked = bool(params["locked"])
                if locked and params.get("open_state") is None and params.get("position") is None:
                    target_pos = 0.0
            if target_pos > 0 and locked:
                locked = False

            # Update immediate lock state and start smooth 20Hz position interpolation
            if domain == "door":
                rep["locked"] = locked
                st_str = "Open" if curr_pos > 0 else "Closed"
                rep["metadata"] = f"{'Locked' if locked else 'Unlocked'} • {st_str} ({int(curr_pos)}%)"
                self.db.update_reported_state(dev["id"], rep)

            if abs(target_pos - curr_pos) < 1.0:
                rep["position"] = int(target_pos)
                rep["state"] = "Open" if target_pos > 0 else "Closed"
                if domain == "door":
                    rep["locked"] = locked
                    rep["metadata"] = (
                        f"{'Locked' if locked else 'Unlocked'} • {rep['state']} ({int(target_pos)}%)"
                    )
                else:
                    room_name = dev.get("room_name") or rep.get("room") or "Home"
                    rep["metadata"] = f"{room_name} • {int(target_pos)}% Open"
                updated = self.db.update_reported_state(dev["id"], rep, also_sync_desired=True)
                await self.broker.publish(
                    f"device.state.{domain}.{dev['id']}",
                    {
                        "device_id": dev["id"],
                        "wbt_name": dev["wbt_name"],
                        "domain": domain,
                        "state": updated,
                        "source": "virtual_physics",
                    },
                )
            else:
                self._interpolations[dev["id"]] = ActiveInterpolation(
                    device_id=dev["id"],
                    wbt_name=dev["wbt_name"],
                    domain=domain,
                    start_pos=curr_pos,
                    target_pos=target_pos,
                    start_time=time.monotonic(),
                    duration=0.45,
                    locked=locked if domain == "door" else None,
                )

        elif domain == "climate":
            if params.get("power_state") is not None:
                rep["state"] = "On" if str(params["power_state"]).lower() == "on" else "Off"
            if params.get("mode") is not None:
                rep["mode"] = str(params["mode"]).lower()
                rep["state"] = "Off" if rep["mode"] == "off" else "On"
            if params.get("target_temp") is not None:
                rep["target_temp"] = round(float(params["target_temp"]), 1)
            rep["metadata"] = f"{str(rep.get('mode', 'eco')).title()} • Target {float(rep.get('target_temp', 22.0)):.1f}°C"
            updated = self.db.update_reported_state(dev["id"], rep, also_sync_desired=True)
            await self.broker.publish(
                f"device.state.climate.{dev['id']}",
                {
                    "device_id": dev["id"],
                    "wbt_name": dev["wbt_name"],
                    "domain": "climate",
                    "state": updated,
                    "source": "virtual_physics",
                },
            )

        elif domain == "appliance":
            rated_w = float(rep.get("rated_watts", dev["config"].get("rated_watts", 100.0)))
            if params.get("power_state") is not None:
                is_on = str(params["power_state"]).lower() == "on"
                rep["state"] = "On" if is_on else "Off"
                rep["power_watts"] = rated_w if is_on else 2.5
                if not is_on:
                    rep["mode"] = "Off"
                elif rep.get("mode") in ("Off", "Standby", "Idle"):
                    rep["mode"] = "Active"
            if params.get("mode") is not None:
                rep["mode"] = str(params["mode"])
                if rep["mode"].lower() not in ("off", "standby", "idle"):
                    rep["state"] = "On"
                    rep["power_watts"] = rated_w
                else:
                    rep["state"] = "Off"
                    rep["power_watts"] = 2.5
            updated = self.db.update_reported_state(dev["id"], rep, also_sync_desired=True)
            await self.broker.publish(
                f"device.state.appliance.{dev['id']}",
                {
                    "device_id": dev["id"],
                    "wbt_name": dev["wbt_name"],
                    "domain": "appliance",
                    "state": updated,
                    "source": "virtual_physics",
                },
            )

    async def _on_robot_command(self, _topic: str, payload: dict[str, Any]) -> None:
        if self.broker.is_webots_attached:
            return

        action = payload.get("action")
        if action == "navigate":
            waypoints = payload.get("waypoints", [])
            destination = payload.get("destination") or payload.get("room")
            if not waypoints and destination:
                robot = self.db.get_robot("tiago")
                plan = self.db.compute_route(robot["pose"]["x"], robot["pose"]["y"], destination)
                waypoints = plan["waypoints"]
            self._nav_waypoints = list(waypoints)
            self._nav_target_room = destination
            if self._nav_waypoints:
                robot = self.db.update_robot(
                    "tiago",
                    status="Navigating",
                    task_description=f"navigating to {destination or 'waypoint'}",
                    target_destination=destination,
                    active_waypoints_json=json.dumps(self._nav_waypoints),
                )
                await self.broker.publish(
                    "robot.telemetry.tiago",
                    {
                        "pose": robot["pose"],
                        "status": robot["status"],
                        "battery": robot["battery_pct"],
                        "current_room": robot["current_room"],
                        "target_destination": robot["target_destination"],
                        "active_route": self._nav_waypoints,
                        "arm_pose": robot["arm_pose"],
                        "gripper": robot["gripper"],
                        "held_object": robot["held_object"],
                        "task": robot["task_description"],
                    },
                )
        elif action == "stop":
            self._nav_waypoints.clear()
            self._nav_target_room = None
            robot = self.db.update_robot(
                "tiago",
                status="Idle",
                task_description="idle",
                target_destination=None,
                active_waypoints_json="[]",
            )
            await self.broker.publish(
                "robot.telemetry.tiago",
                {
                    "pose": robot["pose"],
                    "status": "Idle",
                    "battery": robot["battery_pct"],
                    "current_room": robot["current_room"],
                    "active_route": [],
                    "task": "idle",
                },
            )
        elif action == "arm":
            pose = payload.get("pose", "home")
            robot = self.db.update_robot("tiago", arm_pose=pose)
            await self.broker.publish("robot.telemetry.tiago", robot)
        elif action == "gripper":
            state = payload.get("state") or payload.get("gripper_state") or "open"
            robot = self.db.update_robot("tiago", gripper=state)
            await self.broker.publish("robot.telemetry.tiago", robot)
        elif action == "pick":
            obj = payload.get("object", "item")
            robot = self.db.update_robot(
                "tiago",
                arm_pose="carry",
                gripper="closed",
                held_object=obj,
                status="Idle",
                task_description="idle",
            )
            await self.broker.publish("robot.telemetry.tiago", robot)
        elif action == "place":
            robot = self.db.update_robot(
                "tiago",
                arm_pose="home",
                gripper="open",
                held_object="",
                status="Idle",
                task_description="idle",
            )
            await self.broker.publish("robot.telemetry.tiago", robot)
        elif action in ("fetch", "deliver"):
            if self._errand_task and not self._errand_task.done():
                self._errand_task.cancel()
            self._errand_task = asyncio.create_task(self._execute_virtual_errand(payload))

    async def _execute_virtual_errand(self, payload: dict[str, Any]) -> None:
        action = payload.get("action")
        item = payload.get("item", "object")
        from_loc = payload.get("from_location", "kitchen")
        to_loc = payload.get("to_location", "foyer")
        task_id = payload.get("task_id") or uuid.uuid4().hex[:8]
        total_steps = 4 if action == "fetch" else 5

        self.db.upsert_errand(
            task_id=task_id,
            errand_type=str(action),
            item=item,
            from_location=from_loc,
            to_location=to_loc,
            current_step=1,
            total_steps=total_steps,
            status="running",
            message=f"Navigating to {from_loc}",
        )

        # Auto-open any blocking doors along the errand path and navigate
        await self._auto_clear_and_navigate(from_loc)

        # Step 2: Pick item
        self.db.upsert_errand(
            task_id=task_id,
            errand_type=str(action),
            item=item,
            from_location=from_loc,
            to_location=to_loc,
            current_step=2,
            total_steps=total_steps,
            status="running",
            message=f"Picking up {item}",
        )
        self.db.update_robot(
            "tiago",
            status="Picking",
            task_description=f"picking {item}",
            arm_pose="reach_table",
        )
        await asyncio.sleep(0.4)
        self.db.update_robot(
            "tiago",
            arm_pose="carry",
            gripper="closed",
            held_object=item,
        )

        # Step 3: Navigate to destination (or dock for fetch)
        dest_room = "foyer" if action == "fetch" else to_loc
        self.db.upsert_errand(
            task_id=task_id,
            errand_type=str(action),
            item=item,
            from_location=from_loc,
            to_location=to_loc,
            current_step=3,
            total_steps=total_steps,
            status="running",
            message=f"Navigating to {dest_room}",
        )
        await self._auto_clear_and_navigate(dest_room)

        if action == "deliver":
            self.db.upsert_errand(
                task_id=task_id,
                errand_type=str(action),
                item=item,
                from_location=from_loc,
                to_location=to_loc,
                current_step=4,
                total_steps=total_steps,
                status="running",
                message=f"Placing {item} at {to_loc}",
            )
            await asyncio.sleep(0.3)
            self.db.update_robot(
                "tiago",
                arm_pose="home",
                gripper="open",
                held_object="",
            )

        self.db.upsert_errand(
            task_id=task_id,
            errand_type=str(action),
            item=item,
            from_location=from_loc,
            to_location=to_loc,
            current_step=total_steps,
            total_steps=total_steps,
            status="done",
            message="Errand complete",
        )

    async def _auto_clear_and_navigate(self, destination: str) -> None:
        robot = self.db.get_robot("tiago")
        plan = self.db.compute_route(robot["pose"]["x"], robot["pose"]["y"], destination)
        for bd in plan.get("blocking_doors", []):
            await self._on_device_command(
                f"device.command.door.{bd['id']}",
                {"action": "set_state", "params": {"open_state": "open", "locked": False, "position": 100}},
            )
        await self._on_robot_command(
            "robot.command.tiago",
            {"action": "navigate", "destination": destination, "waypoints": plan["waypoints"]},
        )
        # Wait until navigation finishes
        for _ in range(150):
            if not self._nav_waypoints:
                break
            await asyncio.sleep(0.1)

    async def _run_loop(self) -> None:
        """20Hz (50ms) virtual physics and kinematics loop."""
        dt = 0.05
        last_sensor_tick = 0.0
        while self._running:
            try:
                if not self.broker.is_webots_attached:
                    now = time.monotonic()
                    await self._step_interpolations(now)
                    await self._step_robot_kinematics(dt)
                    if now - last_sensor_tick >= 0.4:
                        last_sensor_tick = now
                        await self._step_virtual_sensors()
            except Exception as exc:  # noqa: BLE001
                logger.debug("VirtualPhysicsWorker tick error: %s", exc)
            await asyncio.sleep(dt)

    async def _step_interpolations(self, now: float) -> None:
        if not self._interpolations:
            return
        finished: list[str] = []
        for dev_id, interp in list(self._interpolations.items()):
            elapsed = now - interp.start_time
            t = min(1.0, max(0.0, elapsed / max(0.05, interp.duration)))
            curr_pos = round(interp.start_pos + (interp.target_pos - interp.start_pos) * t)
            dev = self.db.strict_lookup(dev_id)
            if not dev:
                finished.append(dev_id)
                continue
            rep = dict(dev["reported_state"])
            rep["position"] = int(curr_pos)
            rep["state"] = "Open" if curr_pos > 0 else "Closed"
            if interp.domain == "door":
                locked = interp.locked if interp.locked is not None else bool(rep.get("locked", False))
                if curr_pos > 0:
                    locked = False
                rep["locked"] = locked
                rep["metadata"] = f"{'Locked' if locked else 'Unlocked'} • {rep['state']} ({int(curr_pos)}%)"
            else:
                room_name = dev.get("room_name") or rep.get("room") or "Home"
                rep["metadata"] = f"{room_name} • {int(curr_pos)}% Open"

            updated = self.db.update_reported_state(dev_id, rep, also_sync_desired=(t >= 1.0))
            await self.broker.publish(
                f"device.state.{interp.domain}.{dev_id}",
                {
                    "device_id": dev_id,
                    "wbt_name": interp.wbt_name,
                    "domain": interp.domain,
                    "state": updated,
                    "source": "virtual_physics",
                },
            )
            if t >= 1.0:
                finished.append(dev_id)

        for dev_id in finished:
            self._interpolations.pop(dev_id, None)

    async def _step_robot_kinematics(self, dt: float) -> None:
        if not self._nav_waypoints:
            return
        robot = self.db.get_robot("tiago")
        cx = float(robot["pose"]["x"])
        cy = float(robot["pose"]["y"])
        wp = self._nav_waypoints[0]
        tx, ty, ttheta = float(wp["x"]), float(wp["y"]), float(wp.get("theta", 0.0))

        dx = tx - cx
        dy = ty - cy
        dist = math.hypot(dx, dy)
        step_dist = self._robot_speed_mps * dt

        if dist <= step_dist:
            nx, ny, ntheta = tx, ty, ttheta
            self._nav_waypoints.pop(0)
        else:
            heading = math.atan2(dy, dx)
            nx = cx + math.cos(heading) * step_dist
            ny = cy + math.sin(heading) * step_dist
            ntheta = heading

        if not self._nav_waypoints:
            is_dock = math.hypot(nx - (-3.10), ny - (-7.62)) < 0.35
            new_status = "Docked" if is_dock else "Idle"
            updated_robot = self.db.update_robot(
                "tiago",
                pose_x=round(nx, 3),
                pose_y=round(ny, 3),
                theta=round(ntheta, 3),
                status=new_status,
                task_description="idle",
                target_destination=None,
                active_waypoints_json="[]",
            )
        else:
            updated_robot = self.db.update_robot(
                "tiago",
                pose_x=round(nx, 3),
                pose_y=round(ny, 3),
                theta=round(ntheta, 3),
                status="Navigating",
                active_waypoints_json=json.dumps(self._nav_waypoints),
            )

        await self.broker.publish(
            "robot.telemetry.tiago",
            {
                "pose": updated_robot["pose"],
                "status": updated_robot["status"],
                "battery": updated_robot["battery_pct"],
                "current_room": updated_robot["current_room"],
                "target_destination": updated_robot["target_destination"],
                "active_route": self._nav_waypoints,
                "arm_pose": updated_robot["arm_pose"],
                "gripper": updated_robot["gripper"],
                "held_object": updated_robot["held_object"],
                "task": updated_robot["task_description"],
            },
        )

    async def _step_virtual_sensors(self) -> None:
        now = time.monotonic()
        robot = self.db.get_robot("tiago")
        rx, ry = float(robot["pose"]["x"]), float(robot["pose"]["y"])

        # Compute whether TIAGo is actually moving (velocity > 0.04 m/s)
        if self._last_robot_pos is None:
            self._last_robot_pos = (rx, ry)
            robot_is_moving = False
        else:
            move_delta = math.hypot(rx - self._last_robot_pos[0], ry - self._last_robot_pos[1])
            self._last_robot_pos = (rx, ry)
            robot_is_moving = move_delta > 0.015 or robot.get("status") == "Navigating"

        env = self.db.get_environment()
        sun_lum = float(env.get("sun_luminosity", 0.85))

        for sensor in self.db.list_devices("sensor"):
            sid = sensor["id"]
            rep = dict(sensor["reported_state"])
            if sensor["proto_type"] == "DistanceSensor":
                sx, sy = float(sensor["translation"][0]), float(sensor["translation"][1])
                radius = float(sensor["config"].get("range_m", 2.8))
                d = math.hypot(rx - sx, ry - sy)

                # Only trigger if TIAGo is actively moving inside the sensor radius OR a stimulus hold is active
                if robot_is_moving and d <= radius:
                    self._sensor_hold_until[sid] = now + 2.5

                triggered = now < self._sensor_hold_until.get(sid, 0.0)
                val = (
                    round(min(900.0, (d / max(0.5, radius)) * 850.0), 1)
                    if (triggered and d <= radius)
                    else (320.0 if triggered else 1000.0)
                )
                new_state = "Motion Detected" if triggered else "Clear"

                # Emit ONLY when `triggered` boolean transitions
                if bool(rep.get("triggered", False)) != triggered:
                    rep["triggered"] = triggered
                    rep["value"] = val
                    rep["state"] = new_state
                    self.db.update_reported_state(sid, rep, also_sync_desired=True)
                    await self.broker.publish(
                        f"sensor.telemetry.{sid}",
                        {
                            "device_id": sid,
                            "wbt_name": sensor["wbt_name"],
                            "triggered": triggered,
                            "value": val,
                            "state": new_state,
                        },
                    )
            elif sensor["proto_type"] == "LightSensor":
                val = round(sun_lum * 1000.0, 1)
                is_dark = val < 300.0
                new_state = "Low Light / Night" if is_dark else "Daylight"
                if bool(rep.get("triggered", False)) != is_dark:
                    rep["triggered"] = is_dark
                    rep["value"] = val
                    rep["state"] = new_state
                    self.db.update_reported_state(sid, rep, also_sync_desired=True)
                    await self.broker.publish(
                        f"sensor.telemetry.{sid}",
                        {
                            "device_id": sid,
                            "wbt_name": sensor["wbt_name"],
                            "triggered": is_dark,
                            "value": val,
                            "state": new_state,
                        },
                    )


    def render_synthetic_camera_frame(self, camera_name: str, width: int = 640, height: int = 480) -> bytes:
        """Generate a dynamic synthetic JPEG frame annotated with live SQLite room state."""
        env = self.db.get_environment()
        tod = env.get("time_of_day", "day")
        bg_colors = {
            "day": (28, 38, 54),
            "sunset": (48, 32, 44),
            "night": (14, 18, 26),
        }
        bg = bg_colors.get(tod, (28, 38, 54))
        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        # HUD Frame
        draw.rectangle([(14, 14), (width - 14, height - 14)], outline=(56, 189, 248), width=2)
        draw.text((28, 26), f"BEACON DIGITAL TWIN // {camera_name.upper()}", fill=(226, 232, 240))
        draw.text(
            (28, 48),
            f"MODE: {self.broker.sim_mode}   |   SKY: {tod.upper()}   |   TS: {time.strftime('%H:%M:%S')}",
            fill=(148, 163, 184),
        )

        # Find camera room and display live devices in that room
        cam_dev = self.db.strict_lookup(camera_name)
        room_id = cam_dev["room_id"] if cam_dev else None
        room_devices = self.db.list_devices(room_id=room_id) if room_id else self.db.list_devices()[:8]

        y_cursor = 90
        draw.text((28, y_cursor), f"LIVE ROOM TELEMETRY ({room_id or 'tiago_pov'}):", fill=(56, 189, 248))
        y_cursor += 24
        for dev in room_devices[:10]:
            st = dev["reported_state"]
            summary_str = st.get("metadata") or st.get("state") or str(st)
            draw.text(
                (36, y_cursor),
                f"• [{dev['domain'].upper()}] {dev['wbt_name']} ({dev['id']}): {summary_str}",
                fill=(203, 213, 225),
            )
            y_cursor += 22

        robot = self.db.get_robot("tiago")
        draw.rectangle([(28, height - 78), (width - 28, height - 26)], fill=(15, 23, 42), outline=(20, 184, 166))
        draw.text(
            (40, height - 66),
            f"TIAGo ROBOT: {robot['status']} @ {robot['current_room']} "
            f"(x={robot['pose']['x']:.2f}m, y={robot['pose']['y']:.2f}m, bat={robot['battery_pct']}%)",
            fill=(45, 212, 191),
        )
        draw.text(
            (40, height - 44),
            f"Arm: {robot['arm_pose']} | Gripper: {robot['gripper']} | Held: {robot['held_object'] or 'None'}",
            fill=(148, 163, 184),
        )

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return buf.getvalue()
