from __future__ import annotations

import math
from typing import Any

HUMAN_LOCATIONS: dict[str, dict[str, Any]] = {
    "front_porch":    {"name": "Front Porch (Sensor Zone)", "room": "Exterior",       "pos": [0.55, -7.49]},
    "courtyard":      {"name": "Entrance Courtyard",        "room": "Exterior",       "pos": [1.80, -7.49]},
    "driveway_gate":  {"name": "Driveway Gate (Sensor)",    "room": "Exterior",       "pos": [2.10, -8.80]},
    "foyer":          {"name": "Foyer Entrance",            "room": "Foyer",          "pos": [-1.80, -7.50]},
    "hallway":        {"name": "Corridor (Sensor Zone)",    "room": "Corridor",       "pos": [-4.50, -7.50]},
    "living_room":    {"name": "Living Room (Sensor Zone)", "room": "Living Room",    "pos": [-6.00, -2.50]},
    "kitchen":        {"name": "Kitchen Island",            "room": "Kitchen",        "pos": [-1.80, -2.40]},
    "dining_room":    {"name": "Dining Table",              "room": "Dining Room",    "pos": [-9.50, -1.80]},
    "master_bedroom": {"name": "Master Bedroom",            "room": "Master Bedroom", "pos": [-1.80, -10.50]},
    "study_bedroom":  {"name": "Study Bedroom",             "room": "Study Bedroom",  "pos": [-6.80, -11.20]},
    "patio":          {"name": "Backyard Patio",            "room": "Patio",          "pos": [-11.20, -6.50]},
}

JOINT_NAMES = [
    "leftArmAngle", "leftLowerArmAngle", "leftHandAngle",
    "rightArmAngle", "rightLowerArmAngle", "rightHandAngle",
    "leftLegAngle", "leftLowerLegAngle", "leftFootAngle",
    "rightLegAngle", "rightLowerLegAngle", "rightFootAngle",
    "headAngle",
]

HEIGHT_OFFSETS = [-0.02, 0.04, 0.08, -0.03, -0.02, 0.04, 0.08, -0.03]

GAIT_ANGLES = [
    [-0.52, -0.15, 0.58, 0.7, 0.52, 0.17, -0.36, -0.74],
    [0.0, -0.16, -0.7, -0.38, -0.47, -0.3, -0.58, -0.21],
    [0.12, 0.0, 0.12, 0.2, 0.0, -0.17, -0.25, 0.0],
    [0.52, 0.17, -0.36, -0.74, -0.52, -0.15, 0.58, 0.7],
    [-0.47, -0.3, -0.58, -0.21, 0.0, -0.16, -0.7, -0.38],
    [0.0, -0.17, -0.25, 0.0, 0.12, 0.0, 0.12, 0.2],
    [-0.55, -0.85, -1.14, -0.7, -0.56, 0.12, 0.24, 0.4],
    [1.4, 1.58, 1.71, 0.49, 0.84, 0.0, 0.14, 0.26],
    [0.07, 0.07, -0.07, -0.36, 0.0, 0.0, 0.32, -0.07],
    [-0.56, 0.12, 0.24, 0.4, -0.55, -0.85, -1.14, -0.7],
    [0.84, 0.0, 0.14, 0.26, 1.4, 1.58, 1.71, 0.49],
    [0.0, 0.0, 0.42, -0.07, 0.07, 0.07, -0.07, -0.36],
    [0.18, 0.09, 0.0, 0.09, 0.18, 0.09, 0.0, 0.09],
]


class HumanManager:
    """Controls Pedestrian PROTO humans in Webots with realistic walking gait animations."""

    ROOT_HEIGHT = 1.27
    CYCLE_TO_DIST = 0.22
    WALK_SEQ_NUM = 8

    def __init__(self) -> None:
        self.human_nodes: dict[str, Any] = {}
        self.human_joints: dict[str, list[Any]] = {}
        self.humans: dict[str, dict[str, Any]] = {
            "resident": {
                "id": "resident",
                "def_name": "RESIDENT_HUMAN",
                "name": "Alex (Resident)",
                "role": "Resident",
                "position": [-6.0, -3.1, 1.27],
                "heading": 0.0,
                "speed": 1.15,
                "status": "Standing",
                "current_room": "Living Room",
                "waypoints": [],
                "loop": False,
                "walk_dist": 0.0,
            },
            "guest": {
                "id": "guest",
                "def_name": "GUEST_HUMAN",
                "name": "Sam (Visitor)",
                "role": "Visitor",
                "position": [1.6, -7.49, 1.27],
                "heading": 3.14159,
                "speed": 1.15,
                "status": "Standing",
                "current_room": "Exterior",
                "waypoints": [],
                "loop": False,
                "walk_dist": 0.0,
            },
        }

    def init_devices(self, supervisor: Any) -> None:
        for hid, state in self.humans.items():
            node = supervisor.getFromDef(state["def_name"])
            if node:
                self.human_nodes[hid] = node
                joints = []
                for jname in JOINT_NAMES:
                    jf = node.getField(jname)
                    if jf:
                        joints.append(jf)
                self.human_joints[hid] = joints
                tf = node.getField("translation")
                if tf:
                    state["position"] = [round(v, 3) for v in tf.getSFVec3f()]
                    state["current_room"] = self._infer_room(state["position"][0], state["position"][1])

    @staticmethod
    def _infer_room(x: float, y: float) -> str:
        best_room = "Living Room"
        best_d = float("inf")
        for cfg in HUMAN_LOCATIONS.values():
            px, py = cfg["pos"]
            d = math.hypot(x - px, y - py)
            if d < best_d:
                best_d = d
                best_room = str(cfg["room"])
        return best_room

    def list_humans(self) -> list[dict[str, Any]]:
        return [
            {
                **h,
                "available_locations": [
                    {"id": k, "name": v["name"], "room": v["room"], "pos": v["pos"]}
                    for k, v in HUMAN_LOCATIONS.items()
                ],
            }
            for h in self.humans.values()
        ]

    def _reset_stance(self, hid: str) -> None:
        for jf in self.human_joints.get(hid, []):
            jf.setSFFloat(0.0)
        node = self.human_nodes.get(hid)
        if node:
            tf = node.getField("translation")
            if tf:
                pos = list(tf.getSFVec3f())
                pos[2] = self.ROOT_HEIGHT
                tf.setSFVec3f(pos)

    def step_humans(self, dt_sec: float) -> None:
        for hid, h in self.humans.items():
            wps: list[list[float]] = h["waypoints"]
            if not wps:
                if h["status"] != "Standing":
                    h["status"] = "Standing"
                    self._reset_stance(hid)
                continue

            target = wps[0]
            px, py, _ = h["position"]
            dx = target[0] - px
            dy = target[1] - py
            dist = math.hypot(dx, dy)
            step_len = float(h["speed"]) * dt_sec

            if dist <= step_len:
                nx, ny = target[0], target[1]
                finished = wps.pop(0)
                if h["loop"] and finished:
                    wps.append(finished)
            else:
                angle = math.atan2(dy, dx)
                h["heading"] = round(angle, 4)
                nx = px + (dx / dist) * step_len
                ny = py + (dy / dist) * step_len

            h["walk_dist"] += step_len
            cycle_pos = h["walk_dist"] / self.CYCLE_TO_DIST
            seq = int(cycle_pos) % self.WALK_SEQ_NUM
            ratio = cycle_pos - int(cycle_pos)
            nxt_seq = (seq + 1) % self.WALK_SEQ_NUM

            h_offset = HEIGHT_OFFSETS[seq] * (1.0 - ratio) + HEIGHT_OFFSETS[nxt_seq] * ratio
            nz = self.ROOT_HEIGHT + h_offset
            h["position"] = [round(nx, 3), round(ny, 3), round(nz, 3)]
            h["current_room"] = self._infer_room(nx, ny)
            h["status"] = "Walking"

            node = self.human_nodes.get(hid)
            if node:
                tf = node.getField("translation")
                rf = node.getField("rotation")
                if tf:
                    tf.setSFVec3f([nx, ny, nz])
                if rf:
                    rf.setSFRotation([0.0, 0.0, 1.0, float(h["heading"])])

            joints = self.human_joints.get(hid, [])
            for i, jf in enumerate(joints):
                if i < len(GAIT_ANGLES):
                    ang = GAIT_ANGLES[i][seq] * (1.0 - ratio) + GAIT_ANGLES[i][nxt_seq] * ratio
                    jf.setSFFloat(ang)

    def execute_cmd(self, cmd: dict[str, Any]) -> dict[str, Any]:
        hid = cmd.get("human_id", "resident")
        if hid not in self.humans:
            return {"error": f"Unknown human_id '{hid}'"}

        h = self.humans[hid]
        action = cmd.get("action", "goto_location")

        if action == "stop":
            h["waypoints"] = []
            h["loop"] = False
            h["status"] = "Standing"
            self._reset_stance(hid)
            return dict(h)

        if action == "goto_location":
            loc = cmd.get("location", "living_room")
            if loc not in HUMAN_LOCATIONS:
                return {"error": f"Unknown location '{loc}'"}
            tx, ty = HUMAN_LOCATIONS[loc]["pos"]
            h["waypoints"] = [[tx, ty]]
            h["loop"] = False
            h["status"] = "Walking"
            return dict(h)

        if action == "goto_coords":
            tx = float(cmd.get("x", h["position"][0]))
            ty = float(cmd.get("y", h["position"][1]))
            if cmd.get("teleport"):
                h["waypoints"] = []
                h["position"] = [round(tx, 3), round(ty, 3), self.ROOT_HEIGHT]
                h["current_room"] = self._infer_room(tx, ty)
                node = self.human_nodes.get(hid)
                if node:
                    tf = node.getField("translation")
                    if tf:
                        tf.setSFVec3f([tx, ty, self.ROOT_HEIGHT])
                self._reset_stance(hid)
            else:
                h["waypoints"] = [[tx, ty]]
                h["loop"] = False
                h["status"] = "Walking"
            return dict(h)

        if action == "step":
            dx = float(cmd.get("dx", 0.0))
            dy = float(cmd.get("dy", 0.0))
            tx = h["position"][0] + dx
            ty = h["position"][1] + dy
            h["waypoints"] = [[tx, ty]]
            h["loop"] = False
            h["status"] = "Walking"
            return dict(h)

        if action == "patrol_loop":
            h["waypoints"] = [
                [-6.0, -2.5],
                [-5.35, -7.5],
                [-1.8, -7.5],
                [-5.35, -7.5],
            ]
            h["loop"] = True
            h["status"] = "Walking"
            return dict(h)

        return dict(h)
