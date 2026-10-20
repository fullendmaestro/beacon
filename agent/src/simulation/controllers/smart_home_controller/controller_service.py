from __future__ import annotations

import json
import logging
import math
import queue
import threading
import urllib.request
from collections.abc import Generator
from typing import Any

from constants import APPLIANCE_DEFAULTS, NAV_NODES, SUPPORTED_LIGHT_TYPES
try:
    from controller import Supervisor
except ImportError:
    Supervisor = None  # type: ignore[assignment,misc]
from fastapi import HTTPException
from managers import (
    AccessManager,
    ClimateApplianceManager,
    EventTaskManager,
    HumanManager,
    LightingManager,
    PerceptionManager,
)

logger = logging.getLogger("smart_home_controller")


class SmartHomeController:
    """
    Central Webots Supervisor orchestrator delegating to modular domain managers:
      - LightingManager (lights, dimmers, RGB color)
      - AccessManager (doors, locks, garage door, driveway gate, motorized blinds)
      - ClimateApplianceManager (HVAC radiators, smart appliances, wall plugs, sun/sky)
      - PerceptionManager (security cameras, MJPEG streams, motion & daylight sensors)
      - HumanManager (Pedestrian human actors with 13-joint walking gait)
      - EventTaskManager (Graspable 3D household objects, sensor edge triggers, Ambient & HITL AI tasks)
    """

    def __init__(self, supervisor: Any | None = None) -> None:
        if supervisor is not None:
            self.supervisor = supervisor
        elif Supervisor is not None:
            try:
                self.supervisor = Supervisor()
            except Exception:
                from standalone_supervisor import StandaloneSupervisor

                self.supervisor = StandaloneSupervisor()
        else:
            from standalone_supervisor import StandaloneSupervisor

            self.supervisor = StandaloneSupervisor()
        self.time_step = int(self.supervisor.getBasicTimeStep())
        self.command_queue: queue.Queue = queue.Queue()
        self.state_lock = threading.Lock()

        self.lighting = LightingManager()
        self.access = AccessManager()
        self.climate_appliances = ClimateApplianceManager()
        self.perception = PerceptionManager()
        self.humans = HumanManager()
        self.events_tasks = EventTaskManager()
        self.tiago_node: Any = None
        self.tiago_fallback: dict[str, Any] = {
            "status": "Docked",
            "current_room": "Foyer",
            "current_node": "foyer",
            "target_destination": None,
            "battery_pct": 98,
            "pose": {"x": -3.10, "y": -7.50, "theta": 1.5708},
            "arm_pose": "home",
            "gripper": "open",
            "held_object": "",
            "task_description": "idle",
            "patrol_logs": [],
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

    def init_devices(self) -> None:
        """Scan Webots scene tree and initialize all domain managers."""
        root_nodes = self._scan_root_children()
        self.climate_appliances.sun_node = self.supervisor.getFromDef("SUN_LIGHT")
        self.tiago_node = self.supervisor.getFromDef("BEACON_TIAGO")

        with self.state_lock:
            for node in root_nodes:
                type_name = node.getTypeName()
                node_id = node.getId()
                name_field = node.getField("name")
                name = name_field.getSFString() if name_field else f"{type_name}_{node_id}"

                if type_name in SUPPORTED_LIGHT_TYPES:
                    self.lighting.register_node(node, node_id, name, type_name)
                elif type_name == "Door":
                    self.access.register_door_node(node, node_id, name)
                elif type_name == "Radiator":
                    self.climate_appliances.register_radiator(node, node_id, name)
                elif name in APPLIANCE_DEFAULTS:
                    self.climate_appliances.register_appliance(node, name)

            self.climate_appliances.ensure_all_default_appliances()
            self.access.init_def_barriers_and_blinds(self.supervisor)
            self.humans.init_devices(self.supervisor)
            self.events_tasks.init_devices(self.supervisor)

        self.perception.init_devices(self.supervisor, self.time_step)

        logger.info(
            "Initialized %d lights, %d doors/gates, %d blinds, %d HVAC zones, %d appliances, %d cameras, %d sensors, %d humans, %d objects, TIAGo=%s.",
            len(self.lighting.light_nodes),
            len(self.access.door_nodes),
            len(self.access.blind_nodes),
            len(self.climate_appliances.climate_nodes),
            len(self.climate_appliances.appliance_states),
            len(self.perception.cameras),
            len(self.perception.sensor_states),
            len(self.humans.human_nodes),
            len(self.events_tasks.object_nodes),
            bool(self.tiago_node),
        )

    def dispatch_command(self, cmd: dict[str, Any], timeout: float = 2.0) -> dict[str, Any]:
        completion = threading.Event()
        response_holder: dict[str, Any] = {}
        cmd["completion"] = completion
        cmd["response"] = response_holder
        self.command_queue.put(cmd)
        completion.wait(timeout=timeout)
        return response_holder.get("result", {"status": "command_queued"})

    @staticmethod
    def _infer_nearest_node(x: float, y: float) -> tuple[str, str]:
        best_key = "foyer"
        best_room = "Foyer"
        best_d = float("inf")
        for k, cfg in NAV_NODES.items():
            px, py, _ = cfg["pose"]
            d = math.hypot(x - px, y - py)
            if d < best_d:
                best_d = d
                best_key = k
                best_room = str(cfg["room"])
        return best_key, best_room

    # --- Lights Facade ---

    def list_lights(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return self.lighting.list_lights()

    def get_light(self, node_id: int) -> dict[str, Any]:
        with self.state_lock:
            return self.lighting.get_light(node_id)

    def request_toggle(self, node_id: int) -> dict[str, Any]:
        if node_id not in self.lighting.light_nodes:
            raise HTTPException(status_code=404, detail="Light not found")
        return self.dispatch_command({"domain": "light", "action": "toggle", "node_id": node_id})

    def request_set_state(
        self,
        node_id: int,
        power_state: str | None = None,
        brightness: int | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        if node_id not in self.lighting.light_nodes:
            raise HTTPException(status_code=404, detail="Light not found")
        return self.dispatch_command({
            "domain": "light",
            "action": "set_state",
            "node_id": node_id,
            "power_state": power_state,
            "brightness": brightness,
            "color": color,
        })

    # --- Access (Doors & Blinds) Facade ---

    def list_doors(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return self.access.list_doors()

    def request_door_update(
        self,
        door_id: str,
        open_state: str | None = None,
        locked: bool | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        if door_id not in self.access.door_states:
            raise HTTPException(status_code=404, detail="Door or barrier not found")
        return self.dispatch_command({
            "domain": "door",
            "door_id": door_id,
            "open_state": open_state,
            "locked": locked,
            "position": position,
        })

    def list_blinds(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return self.access.list_blinds()

    def request_blind_update(self, blind_id: str, position: int) -> dict[str, Any]:
        if blind_id not in self.access.blind_states:
            raise HTTPException(status_code=404, detail="Window blind not found")
        return self.dispatch_command({
            "domain": "blind",
            "blind_id": blind_id,
            "position": position,
        })

    # --- Climate & Appliances Facade ---

    def list_climate(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return list(self.climate_appliances.climate_states.values())

    def request_climate_update(
        self,
        zone_id: int,
        power_state: str | None = None,
        target_temp: float | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        with self.state_lock:
            return self.climate_appliances.update_climate(zone_id, power_state, target_temp, mode)

    def list_appliances(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return list(self.climate_appliances.appliance_states.values())

    def request_appliance_update(
        self,
        appliance_id: str,
        power_state: str | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        with self.state_lock:
            return self.climate_appliances.update_appliance(appliance_id, power_state, mode)

    # --- Sensors, Cameras, Environment & Scenes Facade ---

    def list_sensors(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return list(self.perception.sensor_states.values())

    def list_cameras(self) -> list[dict[str, Any]]:
        return self.perception.list_cameras()

    def stream_camera(self, name: str) -> Generator[bytes]:
        return self.perception.stream_camera(name)

    def get_summary(self) -> dict[str, Any]:
        robots = self.list_robots()
        tiago_info = robots[0] if robots else self.tiago_fallback
        with self.state_lock:
            lights_on = sum(1 for l in self.lighting.light_states.values() if l["state"] == "On")
            doors_open = sum(1 for d in self.access.door_states.values() if d["state"] == "Open")
            appliance_watts = sum(a["power_watts"] for a in self.climate_appliances.appliance_states.values())
            light_watts = lights_on * 12.0
            hvac_watts = sum(350.0 for c in self.climate_appliances.climate_states.values() if c["state"] == "On")
            pending_hitl = sum(1 for t in self.events_tasks.tasks if t["status"] == "pending_approval")
            return {
                "lights_on": lights_on,
                "total_lights": len(self.lighting.light_states),
                "doors_open": doors_open,
                "total_doors": len(self.access.door_states),
                "blinds_count": len(self.access.blind_states),
                "climate_zones": len(self.climate_appliances.climate_states),
                "cameras_online": len(self.perception.list_cameras()),
                "estimated_power_watts": round(appliance_watts + light_watts + hvac_watts, 1),
                "environment": dict(self.climate_appliances.environment_state),
                "pending_tasks": pending_hitl,
                "robot": {
                    "id": "tiago",
                    "name": "TIAGo",
                    "status": tiago_info["status"],
                    "current_room": tiago_info["current_room"],
                    "target_destination": tiago_info.get("target_destination"),
                    "battery_pct": tiago_info.get("battery_pct", 98),
                    "held_object": tiago_info.get("held_object", ""),
                },
            }

    def request_environment_update(self, time_of_day: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "environment", "time_of_day": time_of_day})

    def request_scene(self, scene: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "scene", "scene": scene})

    # --- Humans, Household Objects & AI Tasks Facade ---

    def list_humans(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return self.humans.list_humans()

    def request_human_control(self, req_data: dict[str, Any]) -> dict[str, Any]:
        return self.dispatch_command({"domain": "human", **req_data})

    def list_objects(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return self.events_tasks.list_objects()

    def request_object_move(
        self,
        object_name: str,
        surface: str | None = None,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> dict[str, Any]:
        return self.dispatch_command({
            "domain": "object_move",
            "object_name": object_name,
            "surface": surface,
            "x": x,
            "y": y,
            "z": z,
        })

    def request_objects_reset(self) -> list[dict[str, Any]]:
        res = self.dispatch_command({"domain": "object_reset"})
        return res if isinstance(res, list) else self.list_objects()

    def get_tasks_and_events(self) -> dict[str, Any]:
        with self.state_lock:
            return self.events_tasks.get_state()

    def request_create_task(self, req_data: dict[str, Any]) -> dict[str, Any]:
        return self.dispatch_command({"domain": "task_create", **req_data})

    def request_approve_task(self, task_id: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "task_approve", "task_id": task_id})

    def request_reject_task(self, task_id: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "task_reject", "task_id": task_id})

    def request_task_settings(
        self,
        ambient_enabled: bool | None = None,
        hitl_enabled: bool | None = None,
    ) -> dict[str, Any]:
        with self.state_lock:
            if ambient_enabled is not None:
                self.events_tasks.ambient_enabled = ambient_enabled
            if hitl_enabled is not None:
                self.events_tasks.hitl_enabled = hitl_enabled
            return self.events_tasks.get_state()

    def request_trigger_scenario(self, scenario: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "scenario_trigger", "scenario": scenario})

    def request_pulse_sensor(self, sensor_id: str, duration: float = 8.0) -> dict[str, Any]:
        return self.dispatch_command({"domain": "sensor_pulse", "sensor_id": sensor_id, "duration": duration})

    # --- Beacon Home Robots (PAL Robotics TIAGo) Facade ---

    def list_robots(self) -> list[dict[str, Any]]:
        tiago_direct = None
        try:
            req = urllib.request.Request("http://127.0.0.1:8001/telemetry")
            with urllib.request.urlopen(req, timeout=0.3) as resp:
                if resp.status == 200:
                    tiago_direct = json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

        with self.state_lock:
            fb = self.tiago_fallback
            if tiago_direct:
                pose = tiago_direct.get("pose", {})
                x = pose.get("x", fb["pose"]["x"])
                y = pose.get("y", fb["pose"]["y"])
                theta = pose.get("theta", fb["pose"]["theta"])
                nearest_node, room_name = self._infer_nearest_node(x, y)
                task = tiago_direct.get("task", "idle")
                is_docked = nearest_node == "foyer" and math.hypot(x - (-3.10), y - (-7.62)) < 0.4
                status = (
                    "Navigating"
                    if "navigat" in task.lower()
                    else ("Docked" if is_docked and task == "idle" else ("Idle" if task == "idle" else task))
                )
                return [
                    {
                        "id": "tiago",
                        "name": "TIAGo",
                        "model": "PAL Robotics TIAGo",
                        "type": "Mobile Manipulator",
                        "status": status,
                        "current_room": tiago_direct.get("current_room", room_name),
                        "current_node": tiago_direct.get("current_node", nearest_node),
                        "battery_pct": round(tiago_direct.get("battery", 85)),
                        "pose": {"x": round(x, 3), "y": round(y, 3), "theta": round(theta, 3)},
                        "target_destination": task.replace("navigating to", "").strip() if "navigating to" in task else None,
                        "arm_pose": tiago_direct.get("arm_pose", "home"),
                        "gripper": tiago_direct.get("gripper", "open"),
                        "held_object": tiago_direct.get("held_object", ""),
                        "task_description": task,
                        "patrol_logs": tiago_direct.get("patrol_logs", []),
                        "online": True,
                    }
                ]

            return [
                {
                    "id": "tiago",
                    "name": "TIAGo",
                    "model": "PAL Robotics TIAGo",
                    "type": "Mobile Manipulator",
                    "status": fb["status"],
                    "current_room": fb["current_room"],
                    "current_node": fb["current_node"],
                    "battery_pct": fb["battery_pct"],
                    "pose": dict(fb["pose"]),
                    "target_destination": fb["target_destination"],
                    "arm_pose": fb["arm_pose"],
                    "gripper": fb["gripper"],
                    "held_object": fb["held_object"],
                    "task_description": fb["task_description"],
                    "patrol_logs": list(fb["patrol_logs"]),
                    "online": bool(self.tiago_node),
                }
            ]

    def request_robot_action(self, action_data: dict[str, Any]) -> dict[str, Any]:
        action = action_data.get("action")
        try:
            if action == "navigate" and action_data.get("destination"):
                payload = json.dumps({"room": action_data["destination"]}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/navigate/room",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "stop":
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/stop",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "arm" and action_data.get("pose"):
                payload = json.dumps({"pose": action_data["pose"]}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/arm/pose",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "gripper" and action_data.get("gripper_state"):
                payload = json.dumps({"state": action_data["gripper_state"]}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/gripper/set",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "head" and action_data.get("target"):
                payload = json.dumps({"target": action_data["target"]}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/head/look_at",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "pick" and action_data.get("object"):
                payload = json.dumps({"object": action_data["object"]}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/manipulate/pick",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "place" and action_data.get("location"):
                payload = json.dumps({"location": action_data["location"]}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/manipulate/place",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "patrol":
                payload = json.dumps({"rooms": action_data.get("rooms")}).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/errand/patrol",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "fetch" and action_data.get("item") and action_data.get("from_location"):
                payload = json.dumps({
                    "item": action_data["item"],
                    "from_location": action_data["from_location"],
                }).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/errand/fetch",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            elif action == "deliver" and action_data.get("item"):
                payload = json.dumps({
                    "item": action_data["item"],
                    "from_location": action_data.get("from_location", "kitchen"),
                    "to_location": action_data.get("to_location", "living_room"),
                }).encode("utf-8")
                req = urllib.request.Request(
                    "http://127.0.0.1:8001/errand/deliver",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
        except Exception:
            pass

        # Standalone fallback state updates when Webots TIAGo process on :8001 is offline
        with self.state_lock:
            fb = self.tiago_fallback
            if action == "navigate" and action_data.get("destination"):
                dest = str(action_data["destination"])
                if dest in NAV_NODES:
                    px, py, ptheta = NAV_NODES[dest]["pose"]
                    fb["pose"] = {"x": px, "y": py, "theta": ptheta}
                    fb["current_node"] = dest
                    fb["current_room"] = str(NAV_NODES[dest]["room"])
                fb["status"] = "Navigating"
                fb["target_destination"] = dest
                fb["task_description"] = f"navigating to {dest}"
            elif action == "stop":
                fb["status"] = "Idle"
                fb["target_destination"] = None
                fb["task_description"] = "idle"
            elif action == "arm" and action_data.get("pose"):
                fb["arm_pose"] = str(action_data["pose"])
            elif action == "gripper" and action_data.get("gripper_state"):
                fb["gripper"] = str(action_data["gripper_state"])
                if fb["gripper"] == "open":
                    fb["held_object"] = ""
            elif action == "pick" and action_data.get("object"):
                fb["held_object"] = str(action_data["object"])
                fb["gripper"] = "closed"
                fb["arm_pose"] = "carry"
            elif action == "place" and action_data.get("location"):
                if fb["held_object"]:
                    self.events_tasks.move_object(fb["held_object"], surface=None)
                fb["held_object"] = ""
                fb["gripper"] = "open"
                fb["arm_pose"] = "home"
            elif action == "patrol":
                fb["status"] = "Patrolling"
                fb["task_description"] = "patrolling home zones"
        return {"success": True, "status": "ok"}

    # --- Multi-Domain Scene Execution ---

    def _execute_scene_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        scene = cmd["scene"]
        if scene == "morning":
            self.climate_appliances.execute_environment_cmd({"time_of_day": "day"})
            for b_id in self.access.blind_states:
                self.access.execute_blind_cmd({"blind_id": b_id, "position": 100})
            for l_id, l_state in self.lighting.light_states.items():
                is_exterior = "Bollard" in l_state["name"] or "Patio" in l_state["name"]
                self.lighting.execute_cmd({
                    "node_id": l_id,
                    "action": "set_state",
                    "power_state": "off" if is_exterior else "on",
                    "brightness": 80,
                })
        elif scene == "away":
            for l_id in self.lighting.light_states:
                self.lighting.execute_cmd({"node_id": l_id, "action": "set_state", "power_state": "off"})
            for b_id in self.access.blind_states:
                self.access.execute_blind_cmd({"blind_id": b_id, "position": 0})
            for d_id in self.access.door_states:
                self.access.execute_door_cmd({"door_id": d_id, "open_state": "closed", "locked": True})
        elif scene == "movie":
            self.climate_appliances.execute_environment_cmd({"time_of_day": "sunset"})
            for b_id in self.access.blind_states:
                self.access.execute_blind_cmd({"blind_id": b_id, "position": 0})
            for l_id, l_state in self.lighting.light_states.items():
                in_living = "Living Room" in l_state["name"]
                self.lighting.execute_cmd({
                    "node_id": l_id,
                    "action": "set_state",
                    "power_state": "on" if in_living else "off",
                    "brightness": 25 if in_living else 0,
                    "color": "warm white",
                })
            if "living_room_smart_tv" in self.climate_appliances.appliance_states:
                self.climate_appliances.appliance_states["living_room_smart_tv"]["state"] = "On"
                self.climate_appliances.appliance_states["living_room_smart_tv"]["mode"] = "Cinema 4K HDR"
        elif scene == "night":
            self.climate_appliances.execute_environment_cmd({"time_of_day": "night"})
            for b_id in self.access.blind_states:
                self.access.execute_blind_cmd({"blind_id": b_id, "position": 0})
            for d_id in self.access.door_states:
                self.access.execute_door_cmd({"door_id": d_id, "open_state": "closed", "locked": True})
            for l_id, l_state in self.lighting.light_states.items():
                is_exterior = "Bollard" in l_state["name"] or "Porch" in l_state["name"]
                self.lighting.execute_cmd({
                    "node_id": l_id,
                    "action": "set_state",
                    "power_state": "on" if is_exterior else "off",
                    "brightness": 60 if is_exterior else 0,
                })
        return {"success": True, "scene": scene}

    # --- Main Webots Step Loop ---

    def step_simulation(self) -> None:
        with self.state_lock:
            self.perception.step_sensors_and_cameras()
            self.humans.step_humans(self.time_step / 1000.0)
            self.events_tasks.step_events(
                self.perception.sensor_states,
                self.lighting,
                self.access,
                self.climate_appliances,
            )

        while not self.command_queue.empty():
            cmd = self.command_queue.get()
            try:
                with self.state_lock:
                    domain = cmd.get("domain", "light")
                    if domain == "light":
                        res = self.lighting.execute_cmd(cmd)
                    elif domain == "door":
                        res = self.access.execute_door_cmd(cmd)
                    elif domain == "blind":
                        res = self.access.execute_blind_cmd(cmd)
                    elif domain == "environment":
                        res = self.climate_appliances.execute_environment_cmd(cmd)
                    elif domain == "scene":
                        res = self._execute_scene_cmd(cmd)
                    elif domain == "human":
                        res = self.humans.execute_cmd(cmd)
                    elif domain == "object_move":
                        res = self.events_tasks.move_object(
                            object_name=cmd["object_name"],
                            surface=cmd.get("surface"),
                            x=cmd.get("x"),
                            y=cmd.get("y"),
                            z=cmd.get("z"),
                        )
                    elif domain == "object_reset":
                        res = self.events_tasks.reset_objects()
                    elif domain == "task_create":
                        res = self.events_tasks.create_custom_task(
                            title=cmd["title"],
                            description=cmd["description"],
                            category=cmd.get("category", "errand"),
                            mode=cmd.get("mode", "hitl"),
                            trigger_source=cmd.get("trigger_source", "Beacon AI Agent"),
                            room=cmd.get("room", "Living Room"),
                            proposed_actions=cmd.get("proposed_actions", []),
                            lighting=self.lighting,
                            access=self.access,
                            climate_appliances=self.climate_appliances,
                        )
                    elif domain == "task_approve":
                        res = self.events_tasks.approve_task(
                            cmd["task_id"],
                            self.lighting,
                            self.access,
                            self.climate_appliances,
                        )
                    elif domain == "task_reject":
                        res = self.events_tasks.reject_task(cmd["task_id"])
                    elif domain == "scenario_trigger":
                        res = self.events_tasks.trigger_scenario_event(
                            cmd["scenario"],
                            self.lighting,
                            self.access,
                            self.climate_appliances,
                            self.humans,
                            self.perception.sensor_states,
                        )
                    elif domain == "sensor_pulse":
                        self.events_tasks.pulse_sensor_override(cmd["sensor_id"], float(cmd.get("duration", 8.0)))
                        self.events_tasks._sensor_cooldowns.clear()
                        self.events_tasks.step_events(
                            self.perception.sensor_states,
                            self.lighting,
                            self.access,
                            self.climate_appliances,
                        )
                        res = {"status": "triggered", "sensor_id": cmd["sensor_id"]}
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