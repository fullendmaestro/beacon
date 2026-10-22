from __future__ import annotations

import heapq
import json
import math
import time
from typing import TYPE_CHECKING, Any

from constants import NAV_EDGES, NAV_NODES

if TYPE_CHECKING:
    from .access_manager import AccessManager


class RoverManager:
    """
    Manages KUKA youBot Supervisor telemetry, orthogonal Dijkstra path planning,
    collinear corner simplification, door-obstacle inspection, and command dispatch.
    """

    def __init__(self) -> None:
        self.rover_node: Any = None
        self.custom_data_field: Any = None
        self.active_waypoints: list[list[float]] = []
        self._cmd_seq: int = 0
        self._cmd_history: list[dict[str, Any]] = []
        self.rover_state: dict[str, Any] = {
            "id": "beacon_rover",
            "name": "Beacon KUKA youBot",
            "status": "Docked",
            "current_node": "foyer",
            "current_room": "Foyer",
            "target_destination": None,
            "position": [-3.1, -7.5, 0.10],
            "heading_rad": 1.57,
            "arm_pose": "reset",
            "gripper": "release",
            "battery_pct": 98,
            "active_route_nodes": [],
            "available_nodes": list(NAV_NODES.keys()),
        }
        self._adj: dict[str, list[tuple[str, float, str | None]]] = self._build_graph()

    @staticmethod
    def _build_graph() -> dict[str, list[tuple[str, float, str | None]]]:
        adj: dict[str, list[tuple[str, float, str | None]]] = {k: [] for k in NAV_NODES}
        for u, v, door_name in NAV_EDGES:
            if u in NAV_NODES and v in NAV_NODES:
                pu = NAV_NODES[u]["pose"]
                pv = NAV_NODES[v]["pose"]
                dist = math.hypot(pv[0] - pu[0], pv[1] - pu[1])
                adj[u].append((v, dist, door_name))
                adj[v].append((u, dist, door_name))
        return adj

    def init_devices(self, supervisor: Any) -> None:
        self.rover_node = (
            supervisor.getFromDef("BEACON_TIAGO")
            or supervisor.getFromDef("BEACON_ROVER")
        )
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
            nearest_key, room_name = self._infer_nearest_node(pos[0], pos[1])
            self.rover_state["current_node"] = nearest_key
            self.rover_state["current_room"] = room_name

            if self.rover_state["status"] == "Navigating" and self.active_waypoints:
                final_wp = self.active_waypoints[-1]
                if math.hypot(pos[0] - final_wp[0], pos[1] - final_wp[1]) < 0.08:
                    self.rover_state["status"] = "Docked" if nearest_key == "foyer" else "Idle"
                    self.rover_state["target_destination"] = None
                    self.rover_state["active_route_nodes"] = []
                    self.active_waypoints.clear()

        if r_field:
            rot = r_field.getSFRotation()
            yaw = math.atan2(rot[2], 0.0) if False else (rot[3] if rot[2] >= 0 else -rot[3])
            yaw = math.atan2(math.sin(yaw), math.cos(yaw))
            self.rover_state["heading_rad"] = round(yaw, 3)

    @staticmethod
    def _infer_nearest_node(x: float, y: float) -> tuple[str, str]:
        best_key = "foyer"
        best_room = "Foyer"
        best_dist = float("inf")
        for key, cfg in NAV_NODES.items():
            wx, wy, _ = cfg["pose"]
            d = math.hypot(x - wx, y - wy)
            if d < best_dist:
                best_dist = d
                best_key = key
                best_room = str(cfg["room"])
        return best_key, best_room

    @staticmethod
    def _simplify_collinear_nodes(nodes: list[str]) -> list[str]:
        """
        Collapse intermediate collinear nodes along straight lines so the rover
        only stops and turns at actual 90-degree corners.
        """
        if len(nodes) <= 2:
            return nodes
        simplified = [nodes[0]]
        for i in range(1, len(nodes) - 1):
            p_prev = NAV_NODES[simplified[-1]]["pose"]
            p_curr = NAV_NODES[nodes[i]]["pose"]
            p_next = NAV_NODES[nodes[i + 1]]["pose"]

            ang1 = math.atan2(p_curr[1] - p_prev[1], p_curr[0] - p_prev[0])
            ang2 = math.atan2(p_next[1] - p_curr[1], p_next[0] - p_curr[0])
            # Keep node only if the direction changes (> ~3 degrees)
            if abs(math.atan2(math.sin(ang2 - ang1), math.cos(ang2 - ang1))) > 0.05:
                simplified.append(nodes[i])
        simplified.append(nodes[-1])
        return simplified

    def plan_route(
        self,
        destination_node: str,
        access_mgr: AccessManager,
        start_node: str | None = None,
    ) -> dict[str, Any]:
        if destination_node not in NAV_NODES:
            return {
                "error": f"Unknown destination_node '{destination_node}'",
                "available_nodes": list(NAV_NODES.keys()),
            }

        if start_node and start_node in NAV_NODES:
            origin = start_node
        else:
            origin, _ = self._infer_nearest_node(
                self.rover_state["position"][0],
                self.rover_state["position"][1],
            )

        pq: list[tuple[float, str, list[str], list[str]]] = [(0.0, origin, [origin], [])]
        visited: dict[str, float] = {}

        best_nodes: list[str] = []
        door_names_on_path: list[str] = []
        total_distance = 0.0

        while pq:
            cost, curr, path, doors = heapq.heappop(pq)
            if curr == destination_node:
                best_nodes = path
                door_names_on_path = doors
                total_distance = round(cost, 2)
                break
            if curr in visited and visited[curr] <= cost:
                continue
            visited[curr] = cost
            for nxt, weight, edge_door in self._adj.get(curr, []):
                nxt_cost = cost + weight
                if nxt not in visited or nxt_cost < visited[nxt]:
                    nxt_doors = [*doors, edge_door] if edge_door else list(doors)
                    heapq.heappush(pq, (nxt_cost, nxt, [*path, nxt], nxt_doors))

        if not best_nodes:
            return {"error": f"No valid route from '{origin}' to '{destination_node}'"}

        corner_nodes = self._simplify_collinear_nodes(best_nodes)

        waypoints: list[dict[str, Any]] = []
        for idx, n_key in enumerate(corner_nodes):
            nx, ny, default_yaw = NAV_NODES[n_key]["pose"]
            if idx < len(corner_nodes) - 1:
                next_pose = NAV_NODES[corner_nodes[idx + 1]]["pose"]
                seg_yaw = round(math.atan2(next_pose[1] - ny, next_pose[0] - nx), 4)
            else:
                seg_yaw = round(default_yaw, 4)
            waypoints.append({
                "node": n_key,
                "name": NAV_NODES[n_key]["name"],
                "room": NAV_NODES[n_key]["room"],
                "x": nx,
                "y": ny,
                "yaw": seg_yaw,
            })

        required_doors: list[dict[str, Any]] = []
        blocking_doors: list[dict[str, Any]] = []
        for d_name in door_names_on_path:
            for d_id, d_state in access_mgr.door_states.items():
                if d_state["name"] == d_name:
                    door_info = {
                        "door_id": d_id,
                        "name": d_state["name"],
                        "state": d_state["state"],
                        "locked": d_state["locked"],
                        "position": d_state["position"],
                    }
                    required_doors.append(door_info)
                    if d_state["state"] != "Open" or d_state["position"] < 80:
                        blocking_doors.append(door_info)

        return {
            "origin_node": origin,
            "destination_node": destination_node,
            "total_distance_m": total_distance,
            "corner_nodes": corner_nodes,
            "waypoints": waypoints,
            "doors_on_route": required_doors,
            "blocking_doors": blocking_doors,
            "ready_to_traverse": len(blocking_doors) == 0,
        }

    def _send_packet(self, payload: dict[str, Any]) -> None:
        self._cmd_seq += 1
        packet = {**payload, "cmd_id": self._cmd_seq, "ts": time.time()}
        self._cmd_history.append(packet)
        if len(self._cmd_history) > 10:
            self._cmd_history = self._cmd_history[-10:]
        if self.custom_data_field:
            self.custom_data_field.setSFString(json.dumps({"commands": self._cmd_history}))

    def execute_cmd(self, cmd: dict[str, Any], access_mgr: AccessManager) -> dict[str, Any]:
        if not self.rover_node:
            return {"error": "DEF BEACON_ROVER Youbot node not found in beacon_home.wbt"}

        sub_action = cmd.get("sub_action")

        if sub_action == "plan_route":
            return self.plan_route(
                destination_node=cmd["destination"],
                access_mgr=access_mgr,
                start_node=cmd.get("start_node"),
            )

        if sub_action == "navigate":
            dest = cmd["destination"]
            if dest == "patrol":
                patrol_loop = ["foyer", "hallway", "living_room", "dining_room", "living_room", "hallway"]
                cur_node, _ = self._infer_nearest_node(
                    self.rover_state["position"][0],
                    self.rover_state["position"][1],
                )
                entry_plan = self.plan_route(
                    destination_node="foyer",
                    access_mgr=access_mgr,
                    start_node=cur_node,
                )
                if entry_plan.get("blocking_doors"):
                    return {
                        "success": False,
                        "status": "blocked_by_door",
                        "message": (
                            "Route to patrol corridor is blocked by closed/locked smart door(s). "
                            "Unlock and open the blocking door(s) first, then start patrol."
                        ),
                        "blocking_doors": entry_plan["blocking_doors"],
                        "planned_route": entry_plan,
                    }
                entry_nodes = entry_plan.get("corner_nodes", ["foyer"])
                full_patrol_nodes = entry_nodes[:-1] + patrol_loop if len(entry_nodes) > 1 else patrol_loop
                waypoints = [list(NAV_NODES[n]["pose"]) for n in full_patrol_nodes]
                self.active_waypoints = waypoints
                self._send_packet({"action": "patrol", "waypoints": waypoints})
                self.rover_state["status"] = "Patrolling"
                self.rover_state["target_destination"] = "Estate Patrol Loop"
                self.rover_state["active_route_nodes"] = full_patrol_nodes
                return dict(self.rover_state)

            plan = self.plan_route(destination_node=dest, access_mgr=access_mgr)
            if "error" in plan:
                return plan

            if plan["blocking_doors"]:
                return {
                    "success": False,
                    "status": "blocked_by_door",
                    "message": (
                        "Route is blocked by closed/locked smart door(s). "
                        "Unlock and open the blocking door(s) using the Smart Home door tools first, "
                        "then dispatch the rover."
                    ),
                    "blocking_doors": plan["blocking_doors"],
                    "planned_route": plan,
                }

            pose_list = [[wp["x"], wp["y"], wp["yaw"]] for wp in plan["waypoints"]]
            self.active_waypoints = pose_list
            self._send_packet({"action": "goto", "waypoints": pose_list})
            self.rover_state["status"] = "Navigating"
            self.rover_state["target_destination"] = NAV_NODES[dest]["name"]
            self.rover_state["active_route_nodes"] = plan["corner_nodes"]
            return {
                **self.rover_state,
                "planned_route": plan,
            }

        if sub_action == "goto_pose":
            pose = [float(cmd["x"]), float(cmd["y"]), float(cmd.get("yaw", 0.0))]
            self.active_waypoints = [pose]
            self._send_packet({"action": "goto", "waypoints": [pose]})
            self.rover_state["status"] = "Navigating"
            self.rover_state["target_destination"] = f"Coordinates ({pose[0]:.2f}, {pose[1]:.2f})"
            self.rover_state["active_route_nodes"] = []
            return dict(self.rover_state)

        if sub_action == "control":
            action = cmd.get("action")
            payload: dict[str, Any] = {"action": action}
            if action == "stop":
                self.rover_state["status"] = "Idle"
                self.rover_state["target_destination"] = None
                self.rover_state["active_route_nodes"] = []
                self.active_waypoints.clear()
            elif action == "arm":
                pose_name = cmd.get("arm_pose") or "reset"
                payload["pose"] = pose_name
                self.rover_state["arm_pose"] = pose_name
            elif action == "gripper":
                g_state = cmd.get("gripper_state") or "release"
                payload["gripper_state"] = g_state
                self.rover_state["gripper"] = g_state
            elif action == "velocity":
                vx = float(cmd.get("vx", 0.0))
                vy = float(cmd.get("vy", 0.0))
                omega = float(cmd.get("omega", 0.0))
                payload["vx"] = vx
                payload["vy"] = vy
                payload["omega"] = omega
                self.active_waypoints.clear()
                self.rover_state["target_destination"] = None
                self.rover_state["active_route_nodes"] = []
                if abs(vx) < 1e-4 and abs(vy) < 1e-4 and abs(omega) < 1e-4:
                    self.rover_state["status"] = "Idle"
                else:
                    payload["omega"] = cmd.get("omega", 0.0)
                self.rover_state["status"] = "Manual Teleop"

            self._send_packet(payload)
            return dict(self.rover_state)

        return {"error": f"Unsupported rover sub_action '{sub_action}'"}