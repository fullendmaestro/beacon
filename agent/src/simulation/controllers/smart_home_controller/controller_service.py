from __future__ import annotations

import io
import logging
import queue
import threading
import time
from collections.abc import Generator
from typing import Any, cast

from constants import (
    APPLIANCE_DEFAULTS,
    BLIND_DEFS,
    CAMERA_NAMES,
    EXTERIOR_BARRIER_DEFS,
    LIGHT_SENSOR_NAMES,
    MAX_LIGHT_INTENSITY,
    MOTION_SENSOR_NAMES,
    SUPPORTED_LIGHT_TYPES,
    ColorUtils,
)
from controller import Camera, DistanceSensor, LightSensor, Supervisor
from fastapi import HTTPException
from PIL import Image

logger = logging.getLogger("smart_home_controller")


class SmartHomeController:
    """
    Manages Webots device discovery, physical actuation (lights, doors, gates,
    blinds, climate, appliances, exterior sun), live sensors, and camera streams.
    """

    def __init__(self, supervisor: Supervisor | None = None) -> None:
        self.supervisor = supervisor or Supervisor()
        self.time_step = int(self.supervisor.getBasicTimeStep())
        self.command_queue: queue.Queue = queue.Queue()
        self.state_lock = threading.Lock()

        # Lights
        self.light_nodes: dict[int, Any] = {}
        self.light_states: dict[int, dict[str, Any]] = {}

        # Doors & Exterior Barriers (Garage Door + Driveway Gate)
        self.door_nodes: dict[str, Any] = {}
        self.door_states: dict[str, dict[str, Any]] = {}

        # Motorized Window Blinds
        self.blind_nodes: dict[str, Any] = {}
        self.blind_states: dict[str, dict[str, Any]] = {}

        # HVAC / Climate Radiators
        self.climate_nodes: dict[int, Any] = {}
        self.climate_states: dict[int, dict[str, Any]] = {}

        # Smart Appliances & Wall Plugs
        self.appliance_nodes: dict[str, Any] = {}
        self.appliance_states: dict[str, dict[str, Any]] = {}

        # Cameras & Sensors
        self.cameras: dict[str, Camera] = {}
        self.camera_frames: dict[str, bytes | None] = {}
        self.motion_sensors: dict[str, DistanceSensor] = {}
        self.light_sensors: dict[str, LightSensor] = {}
        self.sensor_states: dict[str, dict[str, Any]] = {}

        # Environment (Sun / Sky)
        self.sun_node: Any = None
        self.environment_state: dict[str, Any] = {
            "time_of_day": "day",
            "sun_luminosity": 0.8,
        }

    def _scan_root_children(self) -> list[Any]:
        nodes: list[Any] = []
        root = self.supervisor.getRoot()
        if not root:
            return nodes
        children_field: Any = root.getField("children")
        if not children_field:
            return nodes
        for idx in range(children_field.getCount()):
            node = children_field.getMFNode(idx)
            if node:
                nodes.append(node)
        return nodes

    @staticmethod
    def get_light_fields(node: Any) -> tuple[Any, Any]:
        type_name = node.getTypeName()
        if type_name == "CeilingSpotLight":
            return node.getField("spotLightIntensity"), node.getField("spotLightColor")
        return node.getField("pointLightIntensity"), node.getField("pointLightColor")

    def init_devices(self) -> None:
        """Scan scene tree and initialize all smart home fixtures, actuators, and sensors."""
        root_nodes = self._scan_root_children()
        self.sun_node = self.supervisor.getFromDef("SUN_LIGHT")

        with self.state_lock:
            for node in root_nodes:
                type_name = node.getTypeName()
                node_id = node.getId()
                name_field = node.getField("name")
                name = name_field.getSFString() if name_field else f"{type_name}_{node_id}"

                # 1. Lights
                if type_name in SUPPORTED_LIGHT_TYPES:
                    self.light_nodes[node_id] = node
                    i_field, c_field = self.get_light_fields(node)
                    raw_intensity = i_field.getSFFloat() if i_field else 0.0
                    raw_color = c_field.getSFColor() if c_field else [1.0, 1.0, 1.0]
                    is_on = raw_intensity > 0
                    brightness_pct = round(min(100.0, (raw_intensity / MAX_LIGHT_INTENSITY) * 100)) if is_on else 0

                    self.light_states[node_id] = {
                        "id": node_id,
                        "name": name,
                        "type": type_name,
                        "state": "On" if is_on else "Off",
                        "intensity": raw_intensity,
                        "brightness": brightness_pct if brightness_pct > 0 else 100,
                        "color_rgb": raw_color,
                        "color_hex": ColorUtils.to_hex(raw_color),
                        "metadata": f"Intensity at {raw_intensity:.1f}",
                    }

                # 2. Interior & Entrance Doors
                elif type_name == "Door":
                    door_id = f"door_{node_id}"
                    self.door_nodes[door_id] = node
                    self.door_states[door_id] = {
                        "id": door_id,
                        "name": name,
                        "type": "Door",
                        "state": "Closed",
                        "position": 0,
                        "locked": "Entrance" in name,
                        "axis": "rotation",
                        "base_pos": node.getField("rotation").getSFRotation() if node.getField("rotation") else [0, 0, 1, 0],
                    }

                # 3. Climate / Radiators
                elif type_name == "Radiator":
                    self.climate_nodes[node_id] = node
                    self.climate_states[node_id] = {
                        "id": node_id,
                        "name": name,
                        "type": "Radiator",
                        "state": "On",
                        "mode": "eco",
                        "current_temp": 21.5,
                        "target_temp": 22.0,
                        "metadata": "Eco • Target 22.0°C",
                    }

                # 4. Smart Appliances & Wall Plugs
                elif name in APPLIANCE_DEFAULTS:
                    app_id = name.lower().replace(" ", "_")
                    defaults = APPLIANCE_DEFAULTS[name]
                    self.appliance_nodes[app_id] = node
                    is_active = defaults["mode"] not in ("Off", "Standby", "Idle")
                    self.appliance_states[app_id] = {
                        "id": app_id,
                        "name": name,
                        "type": str(defaults["type"]),
                        "room": str(defaults["room"]),
                        "state": "On" if is_active else "Off",
                        "mode": str(defaults["mode"]),
                        "power_watts": float(defaults["wattage"]) if is_active else 2.5,
                        "rated_watts": float(defaults["wattage"]),
                    }

            # Also register any appliances inside groups (like Kitchen Block)
            for app_name, defaults in APPLIANCE_DEFAULTS.items():
                app_id = app_name.lower().replace(" ", "_")
                if app_id not in self.appliance_states:
                    is_active = defaults["mode"] not in ("Off", "Standby", "Idle")
                    self.appliance_states[app_id] = {
                        "id": app_id,
                        "name": app_name,
                        "type": str(defaults["type"]),
                        "room": str(defaults["room"]),
                        "state": "On" if is_active else "Off",
                        "mode": str(defaults["mode"]),
                        "power_watts": float(defaults["wattage"]) if is_active else 2.5,
                        "rated_watts": float(defaults["wattage"]),
                    }

            # 5. Exterior Barriers (Driveway Gate & Garage Door via DEF)
            for def_name, cfg in EXTERIOR_BARRIER_DEFS.items():
                node = self.supervisor.getFromDef(def_name)
                if node:
                    barrier_id = def_name.lower()
                    self.door_nodes[barrier_id] = node
                    self.door_states[barrier_id] = {
                        "id": barrier_id,
                        "name": str(cfg["name"]),
                        "type": str(cfg["type"]),
                        "state": "Closed",
                        "position": 0,
                        "locked": True,
                        "axis": str(cfg["axis"]),
                        "closed_pos": float(cfg["closed_pos"]),
                        "open_pos": float(cfg["open_pos"]),
                    }

            # 6. Motorized Window Blinds via DEF
            for def_name, cfg in BLIND_DEFS.items():
                node = self.supervisor.getFromDef(def_name)
                if node:
                    blind_id = def_name.lower()
                    self.blind_nodes[blind_id] = node
                    self.blind_states[blind_id] = {
                        "id": blind_id,
                        "name": str(cfg["name"]),
                        "room": str(cfg["room"]),
                        "type": "MotorizedBlind",
                        "state": "Closed",
                        "position": 0,
                        "closed_z": float(cfg["closed_z"]),
                        "open_z": float(cfg["open_z"]),
                    }

        # 7. Cameras
        for name in CAMERA_NAMES:
            device = self.supervisor.getDevice(name)
            if device:
                cam = cast(Camera, device)
                cam.enable(self.time_step)
                self.cameras[name] = cam
                self.camera_frames[name] = None

        # 8. Motion & Daylight Sensors
        for name in MOTION_SENSOR_NAMES:
            device = self.supervisor.getDevice(name)
            if device:
                ds = cast(DistanceSensor, device)
                ds.enable(self.time_step)
                self.motion_sensors[name] = ds
                self.sensor_states[name] = {
                    "id": name.lower().replace(" ", "_"),
                    "name": name,
                    "type": "MotionSensor",
                    "state": "Clear",
                    "value": 1000.0,
                    "triggered": False,
                }

        for name in LIGHT_SENSOR_NAMES:
            device = self.supervisor.getDevice(name)
            if device:
                ls = cast(LightSensor, device)
                ls.enable(self.time_step)
                self.light_sensors[name] = ls
                self.sensor_states[name] = {
                    "id": name.lower().replace(" ", "_"),
                    "name": name,
                    "type": "DaylightSensor",
                    "state": "Bright",
                    "value": 800.0,
                    "triggered": False,
                }

        logger.info(
            "Initialized %d lights, %d doors/gates, %d blinds, %d HVAC zones, %d appliances, %d cameras, %d sensors.",
            len(self.light_nodes),
            len(self.door_nodes),
            len(self.blind_nodes),
            len(self.climate_nodes),
            len(self.appliance_states),
            len(self.cameras),
            len(self.sensor_states),
        )

    # --- Thread-Safe Command Dispatcher ---

    def dispatch_command(self, cmd: dict[str, Any], timeout: float = 2.0) -> dict[str, Any]:
        completion = threading.Event()
        response_holder: dict[str, Any] = {}
        cmd["completion"] = completion
        cmd["response"] = response_holder
        self.command_queue.put(cmd)
        completion.wait(timeout=timeout)
        return response_holder.get("result", {"status": "command_queued"})

    # --- Lights API Methods ---

    def list_lights(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "state": s["state"],
                    "type": s["type"],
                    "brightness": s["brightness"] if s["state"] == "On" else 0,
                    "color": s["color_hex"],
                    "color_rgb": s["color_rgb"],
                    "metadata": f"Intensity at {s['intensity']:.1f}",
                }
                for s in self.light_states.values()
            ]

    def get_light(self, node_id: int) -> dict[str, Any]:
        with self.state_lock:
            s = self.light_states.get(node_id)
            if not s:
                raise HTTPException(status_code=404, detail="Light not found")
            return {
                "id": s["id"],
                "name": s["name"],
                "state": s["state"],
                "type": s["type"],
                "brightness": s["brightness"] if s["state"] == "On" else 0,
                "color": s["color_hex"],
                "color_rgb": s["color_rgb"],
                "metadata": f"Intensity at {s['intensity']:.1f}",
            }

    def request_toggle(self, node_id: int) -> dict[str, Any]:
        if node_id not in self.light_nodes:
            raise HTTPException(status_code=404, detail="Light not found")
        return self.dispatch_command({"domain": "light", "action": "toggle", "node_id": node_id})

    def request_set_state(
        self,
        node_id: int,
        power_state: str | None = None,
        brightness: int | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        if node_id not in self.light_nodes:
            raise HTTPException(status_code=404, detail="Light not found")
        return self.dispatch_command({
            "domain": "light",
            "action": "set_state",
            "node_id": node_id,
            "power_state": power_state,
            "brightness": brightness,
            "color": color,
        })

    # --- Doors & Exterior Gates API Methods ---

    def list_doors(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "type": s["type"],
                    "state": s["state"],
                    "position": s["position"],
                    "locked": s["locked"],
                    "metadata": f"{'Locked' if s['locked'] else 'Unlocked'} • {s['state']} ({s['position']}%)",
                }
                for s in self.door_states.values()
            ]

    def request_door_update(
        self,
        door_id: str,
        open_state: str | None = None,
        locked: bool | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        if door_id not in self.door_states:
            raise HTTPException(status_code=404, detail="Door or barrier not found")
        return self.dispatch_command({
            "domain": "door",
            "door_id": door_id,
            "open_state": open_state,
            "locked": locked,
            "position": position,
        })

    # --- Motorized Window Blinds API Methods ---

    def list_blinds(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "room": s["room"],
                    "type": s["type"],
                    "state": s["state"],
                    "position": s["position"],
                    "metadata": f"{s['room']} • {s['position']}% Open",
                }
                for s in self.blind_states.values()
            ]

    def request_blind_update(self, blind_id: str, position: int) -> dict[str, Any]:
        if blind_id not in self.blind_states:
            raise HTTPException(status_code=404, detail="Window blind not found")
        return self.dispatch_command({
            "domain": "blind",
            "blind_id": blind_id,
            "position": position,
        })

    # --- Climate / HVAC API Methods ---

    def list_climate(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return list(self.climate_states.values())

    def request_climate_update(
        self,
        zone_id: int,
        power_state: str | None = None,
        target_temp: float | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        with self.state_lock:
            zone = self.climate_states.get(zone_id)
            if not zone:
                raise HTTPException(status_code=404, detail="Climate zone not found")
            if power_state is not None:
                zone["state"] = "On" if power_state.lower() == "on" else "Off"
            if mode is not None:
                zone["mode"] = mode.lower()
                if zone["mode"] == "off":
                    zone["state"] = "Off"
                else:
                    zone["state"] = "On"
            if target_temp is not None:
                zone["target_temp"] = round(float(target_temp), 1)
            zone["metadata"] = f"{zone['mode'].title()} • Target {zone['target_temp']:.1f}°C"
            return dict(zone)

    # --- Smart Appliances & Energy API Methods ---

    def list_appliances(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return list(self.appliance_states.values())

    def request_appliance_update(
        self,
        appliance_id: str,
        power_state: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        with self.state_lock:
            app = self.appliance_states.get(appliance_id)
            if not app:
                raise HTTPException(status_code=404, detail="Appliance not found")
            if power_state is not None:
                is_on = power_state.lower() == "on"
                app["state"] = "On" if is_on else "Off"
                app["power_watts"] = app["rated_watts"] if is_on else 2.5
                if not is_on:
                    app["mode"] = "Off"
                elif app["mode"] == "Off":
                    app["mode"] = "Active"
            if mode is not None:
                app["mode"] = mode
                if mode.lower() not in ("off", "standby", "idle"):
                    app["state"] = "On"
                    app["power_watts"] = app["rated_watts"]
            return dict(app)

    # --- Sensors, Environment & Scenes API Methods ---

    def list_sensors(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return list(self.sensor_states.values())

    def get_summary(self) -> dict[str, Any]:
        with self.state_lock:
            lights_on = sum(1 for l in self.light_states.values() if l["state"] == "On")
            doors_open = sum(1 for d in self.door_states.values() if d["state"] == "Open")
            appliance_watts = sum(a["power_watts"] for a in self.appliance_states.values())
            light_watts = lights_on * 12.0
            hvac_watts = sum(350.0 for c in self.climate_states.values() if c["state"] == "On")
            return {
                "lights_on": lights_on,
                "total_lights": len(self.light_states),
                "doors_open": doors_open,
                "total_doors": len(self.door_states),
                "blinds_count": len(self.blind_states),
                "climate_zones": len(self.climate_states),
                "cameras_online": len(self.cameras),
                "estimated_power_watts": round(appliance_watts + light_watts + hvac_watts, 1),
                "environment": dict(self.environment_state),
            }

    def request_environment_update(self, time_of_day: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "environment", "time_of_day": time_of_day})

    def request_scene(self, scene: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "scene", "scene": scene})

    # --- Cameras ---

    def list_cameras(self) -> list[dict[str, Any]]:
        return [
            {
                "id": name,
                "name": name,
                "state": "Online",
                "metadata": f"Live • {cam.getWidth()}x{cam.getHeight()}",
                "type": "Camera",
            }
            for name, cam in self.cameras.items()
        ]

    def stream_camera(self, name: str) -> Generator[bytes]:
        cam = self.cameras.get(name)
        if not cam:
            return

        width = cam.getWidth()
        height = cam.getHeight()

        while True:
            raw = self.camera_frames.get(name)
            if raw:
                try:
                    img = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA")
                    buf = io.BytesIO()
                    img.convert("RGB").save(buf, format="JPEG", quality=60)
                    frame = buf.getvalue()

                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
                except (ValueError, OSError):
                    pass
            time.sleep(0.05)

    # --- Webots Simulation Thread Execution ---

    def _execute_light_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        node_id = cmd["node_id"]
        node = self.light_nodes.get(node_id)
        if not node:
            return {"error": "Light not found"}

        i_field, c_field = self.get_light_fields(node)
        action = cmd.get("action")
        state = self.light_states[node_id]
        current_intensity = i_field.getSFFloat() if i_field else 0.0
        current_brightness = state.get("brightness", 100)

        if action == "toggle":
            new_is_on = not (current_intensity > 0)
            target_intensity = (MAX_LIGHT_INTENSITY * (current_brightness / 100.0)) if new_is_on else 0.0
            if i_field:
                i_field.setSFFloat(target_intensity)
            state["state"] = "On" if new_is_on else "Off"
            state["intensity"] = target_intensity
            state["metadata"] = f"Intensity at {target_intensity:.1f}"

        elif action == "set_state":
            target_is_on = state.get("state") == "On"
            if cmd.get("power_state"):
                target_is_on = cmd["power_state"].lower() == "on"
            if cmd.get("brightness") is not None:
                b_val = max(0, min(100, int(cmd["brightness"])))
                if b_val == 0:
                    target_is_on = False
                else:
                    target_is_on = True
                    current_brightness = b_val
                state["brightness"] = current_brightness
            if cmd.get("color"):
                parsed_rgb = ColorUtils.parse(cmd["color"])
                if c_field:
                    c_field.setSFColor(parsed_rgb)
                state["color_rgb"] = parsed_rgb
                state["color_hex"] = ColorUtils.to_hex(parsed_rgb)

            target_intensity = (MAX_LIGHT_INTENSITY * (current_brightness / 100.0)) if target_is_on else 0.0
            if i_field:
                i_field.setSFFloat(target_intensity)
            state["state"] = "On" if target_is_on else "Off"
            state["intensity"] = target_intensity
            state["metadata"] = f"Intensity at {target_intensity:.1f}"

        return {
            "success": True,
            "id": node_id,
            "state": state["state"],
            "brightness": state["brightness"] if state["state"] == "On" else 0,
            "color": state["color_hex"],
            "intensity": state["intensity"],
        }

    def _execute_door_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        door_id = cmd["door_id"]
        node = self.door_nodes.get(door_id)
        state = self.door_states.get(door_id)
        if not node or not state:
            return {"error": "Door not found"}

        if cmd.get("locked") is not None:
            state["locked"] = bool(cmd["locked"])

        target_pct = state["position"]
        if cmd.get("open_state") is not None:
            target_pct = 100 if cmd["open_state"].lower() == "open" else 0
        if cmd.get("position") is not None:
            target_pct = max(0, min(100, int(cmd["position"])))

        if target_pct > 0 and state["locked"]:
            state["locked"] = False

        ratio = target_pct / 100.0
        axis = state["axis"]
        t_field = node.getField("translation")

        if axis in ("x", "z") and t_field:
            pos = list(t_field.getSFVec3f())
            closed_p = float(state["closed_pos"])
            open_p = float(state["open_pos"])
            new_val = closed_p + (open_p - closed_p) * ratio
            if axis == "x":
                pos[0] = new_val
            else:
                pos[2] = new_val
            t_field.setSFVec3f(pos)

        state["position"] = target_pct
        state["state"] = "Open" if target_pct > 0 else "Closed"
        return dict(state)

    def _execute_blind_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        blind_id = cmd["blind_id"]
        node = self.blind_nodes.get(blind_id)
        state = self.blind_states.get(blind_id)
        if not node or not state:
            return {"error": "Blind not found"}

        pct = max(0, min(100, int(cmd["position"])))
        ratio = pct / 100.0
        t_field = node.getField("translation")
        if t_field:
            pos = list(t_field.getSFVec3f())
            pos[2] = float(state["closed_z"]) + (float(state["open_z"]) - float(state["closed_z"])) * ratio
            t_field.setSFVec3f(pos)

        state["position"] = pct
        state["state"] = "Open" if pct > 0 else "Closed"
        return dict(state)

    def _execute_environment_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        tod = cmd["time_of_day"]
        lum_map = {"day": 0.85, "sunset": 0.3, "night": 0.04}
        lum = lum_map.get(tod, 0.85)
        if self.sun_node:
            lum_field = self.sun_node.getField("luminosity")
            if lum_field:
                lum_field.setSFFloat(lum)
        self.environment_state["time_of_day"] = tod
        self.environment_state["sun_luminosity"] = lum
        return dict(self.environment_state)

    def _execute_scene_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        scene = cmd["scene"]
        if scene == "morning":
            self._execute_environment_cmd({"time_of_day": "day"})
            for b_id in self.blind_states:
                self._execute_blind_cmd({"blind_id": b_id, "position": 100})
            for l_id, l_state in self.light_states.items():
                is_exterior = "Bollard" in l_state["name"] or "Patio" in l_state["name"]
                self._execute_light_cmd({
                    "node_id": l_id,
                    "action": "set_state",
                    "power_state": "off" if is_exterior else "on",
                    "brightness": 80,
                })
        elif scene == "away":
            for l_id in self.light_states:
                self._execute_light_cmd({"node_id": l_id, "action": "set_state", "power_state": "off"})
            for b_id in self.blind_states:
                self._execute_blind_cmd({"blind_id": b_id, "position": 0})
            for d_id in self.door_states:
                self._execute_door_cmd({"door_id": d_id, "open_state": "closed", "locked": True})
        elif scene == "movie":
            self._execute_environment_cmd({"time_of_day": "sunset"})
            for b_id in self.blind_states:
                self._execute_blind_cmd({"blind_id": b_id, "position": 0})
            for l_id, l_state in self.light_states.items():
                in_living = "Living Room" in l_state["name"]
                self._execute_light_cmd({
                    "node_id": l_id,
                    "action": "set_state",
                    "power_state": "on" if in_living else "off",
                    "brightness": 25 if in_living else 0,
                    "color": "warm white",
                })
            if "living_room_smart_tv" in self.appliance_states:
                self.appliance_states["living_room_smart_tv"]["state"] = "On"
                self.appliance_states["living_room_smart_tv"]["mode"] = "Cinema 4K HDR"
        elif scene == "night":
            self._execute_environment_cmd({"time_of_day": "night"})
            for b_id in self.blind_states:
                self._execute_blind_cmd({"blind_id": b_id, "position": 0})
            for d_id in self.door_states:
                self._execute_door_cmd({"door_id": d_id, "open_state": "closed", "locked": True})
            for l_id, l_state in self.light_states.items():
                is_exterior = "Bollard" in l_state["name"] or "Porch" in l_state["name"]
                self._execute_light_cmd({
                    "node_id": l_id,
                    "action": "set_state",
                    "power_state": "on" if is_exterior else "off",
                    "brightness": 60 if is_exterior else 0,
                })
        return {"success": True, "scene": scene}

    def step_simulation(self) -> None:
        """Process camera frames, sensor telemetry, and queued actuator commands each step."""
        for name, cam in self.cameras.items():
            img = cam.getImage()
            if img:
                self.camera_frames[name] = img

        with self.state_lock:
            for name, ds in self.motion_sensors.items():
                val = ds.getValue()
                triggered = val < 950.0
                self.sensor_states[name]["value"] = round(val, 1)
                self.sensor_states[name]["triggered"] = triggered
                self.sensor_states[name]["state"] = "Motion Detected" if triggered else "Clear"

            for name, ls in self.light_sensors.items():
                val = ls.getValue()
                is_dark = val < 300.0
                self.sensor_states[name]["value"] = round(val, 1)
                self.sensor_states[name]["triggered"] = is_dark
                self.sensor_states[name]["state"] = "Low Light / Night" if is_dark else "Daylight"

        while not self.command_queue.empty():
            cmd = self.command_queue.get()
            try:
                with self.state_lock:
                    domain = cmd.get("domain", "light")
                    if domain == "light":
                        res = self._execute_light_cmd(cmd)
                    elif domain == "door":
                        res = self._execute_door_cmd(cmd)
                    elif domain == "blind":
                        res = self._execute_blind_cmd(cmd)
                    elif domain == "environment":
                        res = self._execute_environment_cmd(cmd)
                    elif domain == "scene":
                        res = self._execute_scene_cmd(cmd)
                    else:
                        res = {"error": f"Unknown domain {domain}"}

                if "response" in cmd:
                    cmd["response"]["result"] = res
            except Exception as e:  # noqa: BLE001
                logger.error("Error executing simulation command: %s", e)
                if "response" in cmd:
                    cmd["response"]["result"] = {"error": str(e)}
            finally:
                if "completion" in cmd:
                    cmd["completion"].set()