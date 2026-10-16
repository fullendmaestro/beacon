from __future__ import annotations

import json
import math
import time
from typing import TYPE_CHECKING, Any

from constants import ROVER_WAYPOINTS

if TYPE_CHECKING:
    from .access_manager import AccessManager


class RoverManager:
    """Manages KUKA youBot Supervisor telemetry, waypoint routing, and customData command dispatch."""

    def __init__(self) -> None:
        self.rover_node: Any = None
        self.custom_data_field: Any = None
        self.rover_state: dict[str, Any] = {
            "id": "beacon_rover",
            "name": "Beacon KUKA youBot",
            "status": "Docked",
            "current_room": "Foyer",
            "target_destination": None,
            "position": [-3.1, -7.5, 0.10],
            "heading_rad": 1.57,
            "arm_pose": "reset",
            "gripper": "release",
            "battery_pct": 98,
            "available_destinations": list(ROVER_WAYPOINTS.keys()) + ["patrol"],
        }

    def init_devices(self, supervisor: Any) -> None:
        self.rover_node = supervisor.getFromDef("BEACON_ROVER")
        if self.rover_node:
            self.custom_data_field = self.rover_node.getField("customData")

    def update_telemetry(self) -> None:
        if not self.rover_node:
            return
        t_field = self.rover_node.getField("translation")
        r_field = self.rover_node.getField("rotation")
        if t_field:
            pos = [round(v, 3) for v in t_field.getSFVec3f()]
            self.rover_state["position"] = pos
            self.rover_state["current_room"] = self._infer_room(pos[0], pos[1])
        if r_field:
            rot = r_field.getSFRotation()
            yaw = rot[3] if rot[2] >= 0 else -rot[3]
            self.rover_state["heading_rad"] = round(yaw, 3)

    @staticmethod
    def _infer_room(x: float, y: float) -> str:
        best_room = "Corridor"
        best_dist = float("inf")
        for cfg in ROVER_WAYPOINTS.values():
            wx, wy, _ = cfg["pose"]
            d = math.hypot(x - wx, y - wy)
            if d < best_dist:
                best_dist = d
                best_room = str(cfg["room"])
        return best_room

    def _send_packet(self, payload: dict[str, Any]) -> None:
        payload["ts"] = time.time()
        if self.custom_data_field:
            self.custom_data_field.setSFString(json.dumps(payload))

    def execute_cmd(self, cmd: dict[str, Any], access_mgr: AccessManager) -> dict[str, Any]:
        if not self.rover_node:
            return {"error": "DEF BEACON_ROVER Youbot node not found in beacon_home.wbt"}

        sub_action = cmd.get("sub_action")

        if sub_action == "navigate":
            dest = cmd["destination"]
            if dest == "patrol":
                waypoints = [
                    ROVER_WAYPOINTS["foyer"]["pose"],
                    ROVER_WAYPOINTS["living_room"]["pose"],
                    ROVER_WAYPOINTS["dining_room"]["pose"],
                    ROVER_WAYPOINTS["hallway"]["pose"],
                ]
                self._send_packet({"action": "patrol", "waypoints": waypoints})
                self.rover_state["status"] = "Patrolling"
                self.rover_state["target_destination"] = "Estate Patrol Loop"
                return dict(self.rover_state)

            wp_cfg = ROVER_WAYPOINTS.get(dest)
            if not wp_cfg:
                return {"error": f"Unknown destination '{dest}'"}

            door_name = wp_cfg.get("door_name")
            if door_name:
                access_mgr.open_door_by_name(door_name)

            # Build a per-destination route that avoids the staircase/radiator corner.
            # Kitchen and bedrooms lie in the +Y direction from the foyer dock —
            # route via an open foyer centre point [-2.5, -5.8] to stay clear of
            # the staircase wall and radiator at [-3.5, -7.5].
            # Living/dining/hallway destinations sit to the W/NW so the original
            # corridor intermediate still works for those.
            FOYER_CENTRE   = [-2.5, -5.8, 1.57]  # open foyer centre, clear of stairs
            FOYER_CORRIDOR = [-3.5, -7.5, 1.57]  # original (good for W/N rooms)

            if dest in ("kitchen", "master_bedroom", "study_bedroom"):
                route = [FOYER_CENTRE, wp_cfg["pose"]]
            else:
                route = [FOYER_CORRIDOR, wp_cfg["pose"]]

            self._send_packet({"action": "goto", "waypoints": route})
            self.rover_state["status"] = "Navigating"
            self.rover_state["target_destination"] = wp_cfg["name"]
            return dict(self.rover_state)

        if sub_action == "goto_pose":
            pose = [float(cmd["x"]), float(cmd["y"]), float(cmd.get("yaw", 0.0))]
            self._send_packet({"action": "goto", "waypoints": [pose]})
            self.rover_state["status"] = "Navigating"
            self.rover_state["target_destination"] = f"Coordinates ({pose[0]:.2f}, {pose[1]:.2f})"
            return dict(self.rover_state)

        if sub_action == "control":
            action = cmd.get("action")
            payload: dict[str, Any] = {"action": action}
            if action == "stop":
                self.rover_state["status"] = "Idle"
                self.rover_state["target_destination"] = None
            elif action == "arm":
                pose_name = cmd.get("arm_pose") or "reset"
                payload["pose"] = pose_name
                self.rover_state["arm_pose"] = pose_name
            elif action == "gripper":
                g_state = cmd.get("gripper_state") or "release"
                payload["gripper_state"] = g_state
                self.rover_state["gripper"] = g_state
            elif action == "velocity":
                payload["vx"] = cmd.get("vx", 0.0)
                payload["vy"] = cmd.get("vy", 0.0)
                payload["omega"] = cmd.get("omega", 0.0)
                self.rover_state["status"] = "Manual Teleop"

            self._send_packet(payload)
            return dict(self.rover_state)

        return {"error": f"Unsupported rover sub_action '{sub_action}'"}