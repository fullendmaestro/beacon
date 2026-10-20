from __future__ import annotations

import math
from typing import Any

from constants import BLIND_DEFS, EXTERIOR_BARRIER_DEFS


def apply_hinge_door_pose(
    node: Any,
    base_trans: list[float],
    base_yaw: float,
    ratio: float,
    leaf_half_width: float = 0.5,
) -> None:
    """Swing an interior Webots Door node around its hinge axis by ratio * 90 deg."""
    swing_angle = ratio * (math.pi / 2.0)
    pos_field = node.getField("position")
    if pos_field:
        try:
            pos_field.setSFFloat(swing_angle)
        except Exception:
            pass

    r_field = node.getField("rotation")
    t_field = node.getField("translation")
    new_yaw = base_yaw + swing_angle

    # Hinge pivot is located at one edge of the door leaf along its local Y axis
    hinge_x = base_trans[0] - leaf_half_width * math.sin(base_yaw)
    hinge_y = base_trans[1] + leaf_half_width * math.cos(base_yaw)
    new_x = hinge_x + leaf_half_width * math.sin(new_yaw)
    new_y = hinge_y - leaf_half_width * math.cos(new_yaw)

    if r_field:
        try:
            r_field.setSFRotation([0.0, 0.0, 1.0, round(new_yaw, 4)])
        except Exception:
            pass
    if t_field:
        try:
            t_field.setSFVec3f([round(new_x, 4), round(new_y, 4), base_trans[2]])
        except Exception:
            pass


class AccessManager:
    """Manages interior doors, exterior gates/garage doors, and motorized window blinds."""

    def __init__(self) -> None:
        self.door_nodes: dict[str, Any] = {}
        self.door_states: dict[str, dict[str, Any]] = {}
        self.blind_nodes: dict[str, Any] = {}
        self.blind_states: dict[str, dict[str, Any]] = {}

    def register_door_node(self, node: Any, node_id: int, name: str) -> None:
        door_id = f"door_{node_id}"
        self.door_nodes[door_id] = node
        t_field = node.getField("translation")
        r_field = node.getField("rotation")
        base_trans = list(t_field.getSFVec3f()) if t_field else [0.0, 0.0, 0.0]
        base_rot = list(r_field.getSFRotation()) if r_field else [0.0, 0.0, 1.0, 0.0]
        base_yaw = float(base_rot[3]) * (1.0 if (len(base_rot) < 3 or base_rot[2] >= 0) else -1.0)
        self.door_states[door_id] = {
            "id": door_id,
            "name": name,
            "type": "Door",
            "state": "Closed",
            "position": 0,
            "locked": "Entrance" in name,
            "axis": "interior_door",
            "base_translation": base_trans,
            "base_yaw": base_yaw,
        }

    def init_def_barriers_and_blinds(self, supervisor: Any) -> None:
        for def_name, cfg in EXTERIOR_BARRIER_DEFS.items():
            node = supervisor.getFromDef(def_name)
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

        for def_name, cfg in BLIND_DEFS.items():
            node = supervisor.getFromDef(def_name)
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

    def list_doors(self) -> list[dict[str, Any]]:
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

    def list_blinds(self) -> list[dict[str, Any]]:
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

    def execute_door_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
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
        elif axis == "interior_door":
            apply_hinge_door_pose(
                node=node,
                base_trans=list(state["base_translation"]),
                base_yaw=float(state["base_yaw"]),
                ratio=ratio,
            )

        state["position"] = target_pct
        state["state"] = "Open" if target_pct > 0 else "Closed"
        return dict(state)

    def execute_blind_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
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