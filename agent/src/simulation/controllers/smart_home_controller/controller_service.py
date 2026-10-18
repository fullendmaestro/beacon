from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Generator
from typing import Any

from constants import APPLIANCE_DEFAULTS, SUPPORTED_LIGHT_TYPES
try:
    from controller import Supervisor
except ImportError:
    Supervisor = None  # type: ignore[assignment,misc]
from fastapi import HTTPException
from managers import (
    AccessManager,
    ClimateApplianceManager,
    DemoRecorderManager,
    LightingManager,
    PerceptionManager,
    RoverManager,
)

logger = logging.getLogger("smart_home_controller")


class SmartHomeController:
    """
    Central Webots Supervisor orchestrator delegating to modular domain managers:
      - LightingManager (lights, dimmers, RGB color)
      - AccessManager (doors, locks, garage door, driveway gate, motorized blinds)
      - ClimateApplianceManager (HVAC radiators, smart appliances, wall plugs, sun/sky)
      - PerceptionManager (security cameras, MJPEG streams, motion & daylight sensors)
      - RoverManager (KUKA youBot autonomous navigation, 5-DOF arm, gripper, telemetry)
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
        self.rover = RoverManager()

        self.demo = DemoRecorderManager()

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
            self.rover.init_devices(self.supervisor)

            self.demo.init_devices(self.supervisor, root_nodes)

        self.perception.init_devices(self.supervisor, self.time_step)

        logger.info(
            "Initialized %d lights, %d doors/gates, %d blinds, %d HVAC zones, %d appliances, %d cameras, %d sensors, and Rover=%s.",
            len(self.lighting.light_nodes),
            len(self.access.door_nodes),
            len(self.access.blind_nodes),
            len(self.climate_appliances.climate_nodes),
            len(self.climate_appliances.appliance_states),
            len(self.perception.cameras),
            len(self.perception.sensor_states),
            bool(self.rover.rover_node),
        )

    def dispatch_command(self, cmd: dict[str, Any], timeout: float = 2.0) -> dict[str, Any]:
        completion = threading.Event()
        response_holder: dict[str, Any] = {}
        cmd["completion"] = completion
        cmd["response"] = response_holder
        self.command_queue.put(cmd)
        completion.wait(timeout=timeout)
        return response_holder.get("result", {"status": "command_queued"})

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
        with self.state_lock:
            lights_on = sum(1 for l in self.lighting.light_states.values() if l["state"] == "On")
            doors_open = sum(1 for d in self.access.door_states.values() if d["state"] == "Open")
            appliance_watts = sum(a["power_watts"] for a in self.climate_appliances.appliance_states.values())
            light_watts = lights_on * 12.0
            hvac_watts = sum(350.0 for c in self.climate_appliances.climate_states.values() if c["state"] == "On")
            return {
                "lights_on": lights_on,
                "total_lights": len(self.lighting.light_states),
                "doors_open": doors_open,
                "total_doors": len(self.access.door_states),
                "blinds_count": len(self.access.blind_states),
                "climate_zones": len(self.climate_appliances.climate_states),
                "cameras_online": len(self.perception.cameras),
                "estimated_power_watts": round(appliance_watts + light_watts + hvac_watts, 1),
                "environment": dict(self.climate_appliances.environment_state),
                "rover": {
                    "status": self.rover.rover_state["status"],
                    "current_room": self.rover.rover_state["current_room"],
                    "target_destination": self.rover.rover_state["target_destination"],
                },
            }

    def request_environment_update(self, time_of_day: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "environment", "time_of_day": time_of_day})

    def request_scene(self, scene: str) -> dict[str, Any]:
        return self.dispatch_command({"domain": "scene", "scene": scene})

    # --- Autonomous Mobile Robot (Rover) Facade ---

    def get_rover_state(self) -> dict[str, Any]:
        with self.state_lock:
            return dict(self.rover.rover_state)

    def request_rover_route_plan(self, destination: str, start_node: str | None = None) -> dict[str, Any]:
        return self.dispatch_command({
            "domain": "rover",
            "sub_action": "plan_route",
            "destination": destination,
            "start_node": start_node,
        })

    def request_rover_navigation(self, destination: str) -> dict[str, Any]:
        return self.dispatch_command({
            "domain": "rover",
            "sub_action": "navigate",
            "destination": destination,
        })

    def request_rover_pose(self, x: float, y: float, yaw: float = 0.0) -> dict[str, Any]:
        return self.dispatch_command({
            "domain": "rover",
            "sub_action": "goto_pose",
            "x": x,
            "y": y,
            "yaw": yaw,
        })

    def request_rover_control(self, req_data: dict[str, Any]) -> dict[str, Any]:
        return self.dispatch_command({
            "domain": "rover",
            "sub_action": "control",
            **req_data,
        })

    # --- Demo Cinematography & Video Recording Facade ---

    def request_camera_focus(self, req_data: dict[str, Any]) -> dict[str, Any]:
        return self.dispatch_command({"domain": "demo_camera", **req_data})

    def request_recording_start(self, req_data: dict[str, Any]) -> dict[str, Any]:
        return self.dispatch_command({"domain": "demo_record_start", **req_data})

    def request_recording_stop(self) -> dict[str, Any]:
        return self.dispatch_command({"domain": "demo_record_stop"})

    def get_demo_status(self) -> dict[str, Any]:
        with self.state_lock:
            return self.demo.get_status()

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
            self.rover.execute_cmd({"sub_action": "navigate", "destination": "patrol"}, self.access)
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
            self.rover.update_telemetry()
            self.demo.step()

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
                    elif domain == "rover":
                        res = self.rover.execute_cmd(cmd, self.access)
                    elif domain == "demo_camera":
                        res = self.demo.focus_camera(
                            cmd,
                            self.lighting,
                            self.access,
                            self.rover,
                            self.time_step,
                        )
                    elif domain == "demo_record_start":
                        res = self.demo.start_recording(cmd)
                    elif domain == "demo_record_stop":
                        res = self.demo.stop_recording()
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