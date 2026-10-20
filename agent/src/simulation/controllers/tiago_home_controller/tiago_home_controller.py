"""TIAGo House-Errand Bot – Webots controller with Supervisor Magnetic Grasp, Vision & Patrol."""

from __future__ import annotations

import base64
import heapq
import io
import json
import logging
import math
import threading
import time
import urllib.request
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]

logger = logging.getLogger("tiago_home_controller")

try:
    from controller import Robot, Supervisor  # type: ignore

    _WEBOTS = True
except ImportError:
    _WEBOTS = False

PORT = 8001
SMART_HOME_API = "http://127.0.0.1:8000"
TIME_STEP = 16

WHEEL_RADIUS = 0.0985
WHEEL_SEPARATION = 0.4044
MAX_SPEED = 4.5

NAV_NODES: dict[str, dict[str, Any]] = {
    "front_door":        {"name": "Front Entrance",          "room": "Foyer",          "pose": (-0.91, -7.62,  0.0)},
    "master_junction":   {"name": "Master Bedroom Junction", "room": "Foyer",          "pose": (-2.15, -7.62, -1.5708)},
    "foyer":             {"name": "Foyer Dock",              "room": "Foyer",          "pose": (-3.10, -7.62,  3.1416)},
    "docking":           {"name": "Foyer Dock",              "room": "Foyer",          "pose": (-3.10, -7.62,  3.1416)},
    "bathroom_junction": {"name": "Bathroom Junction",       "room": "Corridor",       "pose": (-4.94, -7.62, -1.5708)},
    "hallway":           {"name": "West Corridor Corner",    "room": "Corridor",       "pose": (-5.35, -7.62,  1.5708)},
    "study_junction":    {"name": "Study Bedroom Junction",  "room": "Corridor",       "pose": (-6.24, -7.62, -1.5708)},
    "utility_room":      {"name": "Utility Closet",          "room": "Utility",        "pose": (-0.91, -5.90,  1.5708)},
    "master_bedroom":    {"name": "Master Bedroom",          "room": "Master Bedroom", "pose": (-2.15, -9.80, -1.5708)},
    "bedroom":           {"name": "Master Bedroom",          "room": "Master Bedroom", "pose": (-2.15, -9.80, -1.5708)},
    "bathroom":          {"name": "Main Bathroom",           "room": "Bathroom",       "pose": (-4.94, -9.30, -1.5708)},
    "study_bedroom":     {"name": "Study Bedroom",           "room": "Study Bedroom",  "pose": (-6.24, -9.80, -1.5708)},
    "kitchen_approach":  {"name": "Kitchen Door Approach",   "room": "Living Room",    "pose": (-5.35, -3.95,  0.0)},
    "living_room":       {"name": "Living Room",             "room": "Living Room",    "pose": (-5.35, -1.80,  1.5708)},
    "kitchen":           {"name": "Kitchen",                 "room": "Kitchen",        "pose": (-2.35, -3.95,  0.0)},
    "dining_room":       {"name": "Dining Room",             "room": "Dining Room",    "pose": (-9.20, -1.80,  3.1416)},
}

_GRAPH_NODES = {k: v for k, v in NAV_NODES.items() if k not in ("docking", "bedroom")}

NAV_EDGES: list[tuple[str, str, str | None]] = [
    ("front_door", "master_junction", None),
    ("master_junction", "foyer", None),
    ("foyer", "bathroom_junction", None),
    ("bathroom_junction", "hallway", None),
    ("hallway", "study_junction", None),
    ("front_door", "utility_room", "Utility Closet Door"),
    ("master_junction", "master_bedroom", "Master Bedroom Door"),
    ("bathroom_junction", "bathroom", "Main Bathroom Door"),
    ("study_junction", "study_bedroom", "Study Bedroom Door"),
    ("hallway", "kitchen_approach", None),
    ("kitchen_approach", "kitchen", "Kitchen Passage Door"),
    ("kitchen_approach", "living_room", None),
    ("living_room", "dining_room", None),
]

ROOM_ALIASES: dict[str, str] = {
    "docking": "foyer",
    "bedroom": "master_bedroom",
}

ROOMS: dict[str, tuple[float, float, float]] = {k: v["pose"] for k, v in NAV_NODES.items()}

OBJECT_DEFS: dict[str, str] = {
    "cup": "OBJ_CUP",
    "bottle": "OBJ_BOTTLE",
    "medicine_box": "OBJ_MEDICINE_BOX",
    "plate": "OBJ_PLATE",
    "tray": "OBJ_TRAY",
    "remote_control": "OBJ_REMOTE_CONTROL",
    "keys": "OBJ_KEYS",
    "book": "OBJ_BOOK",
    "phone": "OBJ_PHONE",
    "glasses": "OBJ_GLASSES",
}

OBJECTS: list[str] = list(OBJECT_DEFS.keys())

# Target surface coordinates when placing an item in a room
ROOM_PLACE_SURFACES: dict[str, tuple[float, float, float]] = {
    "kitchen":        (-2.35, -2.40, 0.96),
    "living_room":    (-5.85, -2.65, 0.57),
    "dining_room":    (-10.10, -1.63, 0.76),
    "master_bedroom": (-2.40, -9.80, 0.58),
    "bedroom":        (-2.40, -9.80, 0.58),
    "study_bedroom":  (-6.85, -12.20, 0.74),
    "bathroom":       (-5.35, -9.98, 1.08),
    "foyer":          (-2.70, -7.20, 0.45),
    "docking":        (-2.70, -7.20, 0.45),
    "utility_room":   (-1.85, -5.63, 0.88),
}

ARM_PRESETS: dict[str, list[float]] = {
    "home":        [0.150,  0.07,   0.0,    -2.237,  1.403,  0.0],
    "carry":       [0.250,  0.07,   0.0,    -2.237,  1.403,  0.0],
    "reach_table": [0.200,  0.331,  0.0337, -1.650,  1.403,  0.0],
    "reach_floor": [0.050,  0.400, -0.300,  -0.200,  1.200,  0.0],
    "handover":    [0.300,  0.500, -1.000,   0.300,  1.403, -0.50],
}


def _build_adj() -> dict[str, list[tuple[str, float, str | None]]]:
    adj: dict[str, list[tuple[str, float, str | None]]] = {k: [] for k in _GRAPH_NODES}
    for u, v, door in NAV_EDGES:
        pu = _GRAPH_NODES[u]["pose"]
        pv = _GRAPH_NODES[v]["pose"]
        dist = math.hypot(pv[0] - pu[0], pv[1] - pu[1])
        adj[u].append((v, dist, door))
        adj[v].append((u, dist, door))
    return adj


_ADJ = _build_adj()


def _nearest_node(x: float, y: float) -> str:
    best_k = "foyer"
    best_d = float("inf")
    for k, cfg in _GRAPH_NODES.items():
        px, py, _ = cfg["pose"]
        d = math.hypot(x - px, y - py)
        if d < best_d:
            best_d = d
            best_k = k
    return best_k


def _simplify_collinear(nodes: list[str]) -> list[str]:
    if len(nodes) <= 2:
        return nodes
    out = [nodes[0]]
    for i in range(1, len(nodes) - 1):
        p0 = _GRAPH_NODES[out[-1]]["pose"]
        p1 = _GRAPH_NODES[nodes[i]]["pose"]
        p2 = _GRAPH_NODES[nodes[i + 1]]["pose"]
        a1 = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        a2 = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        if abs(math.atan2(math.sin(a2 - a1), math.cos(a2 - a1))) > 0.05:
            out.append(nodes[i])
    out.append(nodes[-1])
    return out


def _fetch_smart_home_json(path: str) -> Any:
    try:
        with urllib.request.urlopen(f"{SMART_HOME_API}{path}", timeout=0.6) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def _open_door_via_http(door_name: str) -> None:
    try:
        doors = _fetch_smart_home_json("/api/doors") or []
        for d in doors:
            if d.get("name") == door_name:
                door_id = d["id"]
                req = urllib.request.Request(
                    f"{SMART_HOME_API}/api/doors/{door_id}/state",
                    data=json.dumps({"open_state": "open", "locked": False, "position": 100}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=0.6)
    except Exception:
        pass


def _ensure_room_light_on(room_name: str) -> None:
    """Turn on room light automatically before visual inspection if dark."""
    try:
        lights = _fetch_smart_home_json("/api/lights") or []
        clean_room = room_name.replace("_", " ").lower()
        for l in lights:
            if clean_room in l.get("name", "").lower() and l.get("state") == "Off":
                req = urllib.request.Request(
                    f"{SMART_HOME_API}/api/lights/{l['id']}/state",
                    data=json.dumps({"power_state": "on", "brightness": 85}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=0.5)
    except Exception:
        pass


def _compute_route(cx: float, cy: float, dest_raw: str) -> dict[str, Any]:
    dest_key = ROOM_ALIASES.get(dest_raw, dest_raw)
    if dest_key not in _GRAPH_NODES:
        raise ValueError(f"Unknown destination: {dest_raw}")

    origin = _nearest_node(cx, cy)
    pq: list[tuple[float, str, list[str], list[str]]] = [(0.0, origin, [origin], [])]
    visited: dict[str, float] = {}
    best_path: list[str] = []
    doors_on_path: list[str] = []
    total_dist = 0.0

    while pq:
        cost, curr, path, doors = heapq.heappop(pq)
        if curr == dest_key:
            best_path = path
            doors_on_path = doors
            total_dist = round(cost, 2)
            break
        if curr in visited and visited[curr] <= cost:
            continue
        visited[curr] = cost
        for nxt, w, door_name in _ADJ.get(curr, []):
            nc = cost + w
            if nxt not in visited or nc < visited[nxt]:
                nd = [*doors, door_name] if door_name else list(doors)
                heapq.heappush(pq, (nc, nxt, [*path, nxt], nd))

    corners = _simplify_collinear(best_path) if best_path else [dest_key]
    waypoints: list[dict[str, float]] = []
    for idx, k in enumerate(corners):
        nx, ny, def_yaw = _GRAPH_NODES[k]["pose"]
        if idx == 0 and len(corners) > 1 and math.hypot(nx - cx, ny - cy) < 0.25:
            continue
        if idx < len(corners) - 1:
            nxt_pose = _GRAPH_NODES[corners[idx + 1]]["pose"]
            yaw = round(math.atan2(nxt_pose[1] - ny, nxt_pose[0] - nx), 4)
        else:
            yaw = round(def_yaw, 4)
        waypoints.append({"x": nx, "y": ny, "theta": yaw})

    live_doors = _fetch_smart_home_json("/api/doors") or []
    blocking_doors: list[dict[str, Any]] = []
    for d_name in doors_on_path:
        matched = next((d for d in live_doors if d.get("name") == d_name), None)
        if matched:
            if matched.get("state") != "Open" or int(matched.get("position", 0)) < 80:
                blocking_doors.append({
                    "id": matched["id"],
                    "name": matched["name"],
                    "state": matched["state"],
                    "locked": matched["locked"],
                })
        else:
            blocking_doors.append({"name": d_name, "state": "Closed", "locked": False})

    return {
        "origin": origin,
        "destination": dest_raw,
        "waypoints": waypoints,
        "doors_on_path": doors_on_path,
        "distance_m": total_dist,
        "blocking_doors": blocking_doors,
    }


class TaskState(Enum):
    IDLE = auto()
    NAVIGATING = auto()
    PICKING = auto()
    PLACING = auto()
    PATROLLING = auto()


@dataclass
class TiagoState:
    x: float = -3.10
    y: float = -7.50
    theta: float = 1.5708
    task: TaskState = TaskState.IDLE
    task_description: str = "idle"
    gripper_state: str = "open"
    arm_pose_name: str = "home"
    held_object: str = ""
    battery: float = 100.0
    waypoint_queue: list[tuple[float, float, float]] = field(default_factory=list)
    doors_to_clear: list[str] = field(default_factory=list)
    nav_phase: str = "unstick"
    errand_id: str = ""
    errand_type: str = ""
    errand_current_step: int = 0
    errand_total_steps: int = 0
    errand_status: str = "idle"
    errand_message: str = ""
    patrol_logs: list[dict[str, Any]] = field(default_factory=list)


_state = TiagoState()
_state_lock = threading.Lock()


class _StubMotor:
    def setVelocity(self, v: float) -> None: ...
    def setPosition(self, p: float) -> None: ...
    def getMaxVelocity(self) -> float: return 2.0


class _StubSensor:
    def enable(self, ts: int) -> None: ...
    def getValue(self) -> float: return 0.0


class _StubCamera:
    def enable(self, ts: int) -> None: ...
    def saveImage(self, path: str, quality: int) -> None: ...


_avail_devices: dict[str, Any] = {}
_self_node: Any = None
_door_nodes_by_name: dict[str, tuple[Any, float]] = {}
_object_nodes_by_name: dict[str, Any] = {}
_human_nodes: dict[str, Any] = {}


def _dev(name: str) -> Any:
    if not _WEBOTS or robot is None:
        return None
    return _avail_devices.get(name)


if _WEBOTS:
    try:
        robot = Supervisor()
    except Exception:
        robot = Robot()

    time_step = int(robot.getBasicTimeStep())
    for i in range(robot.getNumberOfDevices()):
        d = robot.getDeviceByIndex(i)
        if d is not None:
            _avail_devices[d.getName()] = d

    if hasattr(robot, "getSelf"):
        try:
            _self_node = robot.getSelf()
            root = robot.getRoot()
            if root:
                children = root.getField("children")
                for idx in range(children.getCount()):
                    n = children.getMFNode(idx)
                    if n and n.getTypeName() == "Door":
                        nf = n.getField("name")
                        tf = n.getField("translation")
                        if nf and tf:
                            dname = nf.getSFString()
                            base_z = tf.getSFVec3f()[2]
                            _door_nodes_by_name[dname] = (n, base_z)
            for obj_name, def_name in OBJECT_DEFS.items():
                obj_node = robot.getFromDef(def_name)
                if obj_node:
                    _object_nodes_by_name[obj_name] = obj_node
            for h_def in ("RESIDENT_HUMAN", "GUEST_HUMAN"):
                h_node = robot.getFromDef(h_def)
                if h_node:
                    _human_nodes[h_def] = h_node
        except Exception:
            _self_node = None

    _left_wheel = _dev("wheel_left_joint") or _StubMotor()
    _right_wheel = _dev("wheel_right_joint") or _StubMotor()
    _left_wheel.setPosition(float("inf"))
    _right_wheel.setPosition(float("inf"))
    _left_wheel.setVelocity(0.0)
    _right_wheel.setVelocity(0.0)

    _left_enc = _dev("wheel_left_joint_sensor") or _StubSensor()
    _right_enc = _dev("wheel_right_joint_sensor") or _StubSensor()
    _left_enc.enable(time_step)
    _right_enc.enable(time_step)

    _camera = _dev("Astra rgb") or _StubCamera()
    _camera.enable(max(time_step * 8, 128))

    _arm_joint_names = [
        "torso_lift_joint",
        "arm_1_joint",
        "arm_2_joint",
        "arm_3_joint",
        "arm_4_joint",
        "arm_6_joint",
    ]
    _arm_joints = [_dev(n) or _StubMotor() for n in _arm_joint_names]

    for j, target_angle in zip(_arm_joints, ARM_PRESETS["home"]):
        j.setPosition(target_angle)

    _gripper_motor = _dev("front::left finger joint") or _StubMotor()
    if _dev("front::left finger joint") is not None:
        try:
            _gripper_motor.setPosition(float("inf"))
            _gripper_motor.setVelocity(0.0)
        except Exception:
            pass
    _gripper_joints = [_gripper_motor]

    _head_pan = _dev("head_1_joint") or _StubMotor()
    _head_tilt = _dev("head_2_joint") or _StubMotor()
    _head_pan.setPosition(0.0)
    _head_tilt.setPosition(0.0)
else:
    robot = None  # type: ignore
    time_step = TIME_STEP
    _left_wheel = _right_wheel = _StubMotor()
    _left_enc = _right_enc = _StubSensor()
    _camera = _StubCamera()
    _arm_joints = [_StubMotor() for _ in range(6)]
    _gripper_joints = [_StubMotor()]
    _head_pan = _head_tilt = _StubMotor()


def _set_wheel_speeds(left: float, right: float) -> None:
    _left_wheel.setVelocity(max(-MAX_SPEED, min(MAX_SPEED, left)))
    _right_wheel.setVelocity(max(-MAX_SPEED, min(MAX_SPEED, right)))


def _apply_arm_preset(preset: str) -> bool:
    angles = ARM_PRESETS.get(preset)
    if angles is None:
        return False
    for joint, angle in zip(_arm_joints, angles):
        joint.setPosition(angle)
    return True


def _apply_gripper(state: str) -> None:
    vel = 0.4 if state == "closed" else -0.4
    _gripper_joints[0].setVelocity(vel)


_HEAD_TARGETS: dict[str, tuple[float, float]] = {
    "forward": (0.0, 0.0),
    "left":    (0.55, 0.0),
    "right":  (-0.55, 0.0),
    "up":      (0.0, -0.35),
    "down":    (0.0, 0.42),
}


def _apply_head(target: str) -> bool:
    pan, tilt = _HEAD_TARGETS.get(target, (0.0, 0.0))
    _head_pan.setPosition(pan)
    _head_tilt.setPosition(tilt)
    return True


def _ensure_webots_door_open(door_name: str) -> None:
    if door_name in _door_nodes_by_name:
        node, base_z = _door_nodes_by_name[door_name]
        tf = node.getField("translation")
        if tf:
            pos = list(tf.getSFVec3f())
            if pos[2] < base_z + 2.0:
                pos[2] = base_z + 2.25
                tf.setSFVec3f(pos)


# ═══════════════════════════════════════════════════════════════════════════════
# Supervisor-Assisted Magnetic Grasp Kinematic Attachment
# ═══════════════════════════════════════════════════════════════════════════════

def _update_magnetic_grasp() -> None:
    """Keep the currently held object magnetically locked to TIAGo's Robotiq 2F-85 gripper."""
    if not _WEBOTS:
        return
    with _state_lock:
        held = _state.held_object
        rx, ry, rtheta = _state.x, _state.y, _state.theta
        arm_pose = _state.arm_pose_name

    if not held or held not in _object_nodes_by_name:
        return

    obj_node = _object_nodes_by_name[held]
    tf = obj_node.getField("translation")
    if not tf:
        return

    # Compute gripper attachment offset in front of TIAGo's torso based on arm pose
    if arm_pose == "reach_table":
        forward_dist = 0.68
        z_height = 0.88
    elif arm_pose == "handover":
        forward_dist = 0.64
        z_height = 1.05
    elif arm_pose == "reach_floor":
        forward_dist = 0.55
        z_height = 0.35
    else:  # carry / home
        forward_dist = 0.46
        z_height = 0.96

    gx = rx + forward_dist * math.cos(rtheta)
    gy = ry + forward_dist * math.sin(rtheta)
    tf.setSFVec3f([gx, gy, z_height])


def _place_object_on_surface_node(obj_name: str, location_key: str) -> None:
    """Place a 3D object onto the designated surface in the target room."""
    if not _WEBOTS or obj_name not in _object_nodes_by_name:
        return
    obj_node = _object_nodes_by_name[obj_name]
    tf = obj_node.getField("translation")
    if not tf:
        return
    norm_loc = ROOM_ALIASES.get(location_key.lower().strip(), location_key.lower().strip())
    if norm_loc in ROOM_PLACE_SURFACES:
        sx, sy, sz = ROOM_PLACE_SURFACES[norm_loc]
    else:
        with _state_lock:
            sx = _state.x + 0.58 * math.cos(_state.theta)
            sy = _state.y + 0.58 * math.sin(_state.theta)
            sz = 0.78
    tf.setSFVec3f([sx, sy, sz])


def _norm_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def _update_pose() -> None:
    if not _WEBOTS or _self_node is None:
        return
    try:
        pos = _self_node.getPosition()
        rot = _self_node.getOrientation()
        yaw = math.atan2(rot[3], rot[0])
        with _state_lock:
            _state.x = float(pos[0])
            _state.y = float(pos[1])
            _state.theta = _norm_angle(yaw)
    except Exception:
        pass


def _step_navigation() -> None:
    if not _WEBOTS or robot is None:
        return

    _update_pose()
    _update_magnetic_grasp()
    sim_now = robot.getTime()

    if sim_now < 1.2:
        _set_wheel_speeds(0.0, 0.0)
        return

    with _state_lock:
        if _state.task != TaskState.NAVIGATING or not _state.waypoint_queue:
            return

        for d_name in _state.doors_to_clear:
            _ensure_webots_door_open(d_name)

        tx, ty, ttheta = _state.waypoint_queue[0]
        dx = tx - _state.x
        dy = ty - _state.y
        dist = math.hypot(dx, dy)
        desired_heading = math.atan2(dy, dx)
        heading_err = _norm_angle(desired_heading - _state.theta)

        if _state.nav_phase == "unstick":
            if _state.y > -7.58 and abs(_norm_angle(_state.theta - 1.5708)) < 0.6:
                _set_wheel_speeds(-2.0, -2.0)
                return
            _set_wheel_speeds(0.0, 0.0)
            _state.nav_phase = "rotate_to_goal"

        if _state.nav_phase == "rotate_to_goal":
            if dist < 0.10:
                _state.nav_phase = "final_align"
            elif abs(heading_err) > 0.05:
                ang = max(-2.0, min(2.0, heading_err * 3.2))
                if abs(heading_err) < 0.25:
                    ang = math.copysign(max(0.35, abs(ang)), heading_err)
                _set_wheel_speeds(-ang, ang)
                return
            else:
                _set_wheel_speeds(0.0, 0.0)
                _state.nav_phase = "drive"

        if _state.nav_phase == "drive":
            if dist < 0.10:
                _set_wheel_speeds(0.0, 0.0)
                _state.nav_phase = "final_align"
            elif abs(heading_err) > 0.40:
                _state.nav_phase = "rotate_to_goal"
                _set_wheel_speeds(0.0, 0.0)
                return
            else:
                lin = min(MAX_SPEED * 0.75, max(0.8, dist * 2.8))
                ang = heading_err * 2.8
                _set_wheel_speeds(lin - ang, lin + ang)
                return

        if _state.nav_phase == "final_align":
            if len(_state.waypoint_queue) > 1:
                _state.waypoint_queue.pop(0)
                _state.nav_phase = "rotate_to_goal"
                return

            align_err = _norm_angle(ttheta - _state.theta)
            if abs(align_err) > 0.05:
                ang = max(-1.8, min(1.8, align_err * 3.0))
                _set_wheel_speeds(-ang, ang)
            else:
                _set_wheel_speeds(0.0, 0.0)
                _state.waypoint_queue.pop(0)
                _state.task = TaskState.IDLE
                _state.task_description = "idle"


def _wait_for_nav_complete(timeout: float = 90.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        with _state_lock:
            if _state.task != TaskState.NAVIGATING or not _state.waypoint_queue:
                return
        time.sleep(0.1)


def _enqueue_room_nav(room: str) -> dict[str, Any]:
    _update_pose()
    with _state_lock:
        cx, cy = _state.x, _state.y
    plan = _compute_route(cx, cy, room)
    for d_name in plan.get("doors_on_path", []):
        _open_door_via_http(d_name)

    wps = [(wp["x"], wp["y"], wp["theta"]) for wp in plan["waypoints"]]
    with _state_lock:
        _state.waypoint_queue = wps
        _state.doors_to_clear = list(plan.get("doors_on_path", []))
        _state.nav_phase = "unstick"
        _state.task = TaskState.NAVIGATING if wps else TaskState.IDLE
        _state.task_description = f"navigating to {room}" if wps else "idle"
    return plan


def _nav_to_room_sync(room: str) -> None:
    _enqueue_room_nav(room)
    _wait_for_nav_complete()


def _pick_sync(obj: str) -> None:
    with _state_lock:
        _state.task = TaskState.PICKING
        _state.task_description = f"magnetic grasping {obj}"
        _state.arm_pose_name = "reach_table"
    _apply_head("down")
    _apply_gripper("open")
    _apply_arm_preset("reach_table")
    time.sleep(1.1)

    # Magnetically snap object into gripper jaws
    with _state_lock:
        _state.held_object = obj
        _state.gripper_state = "closed"
    _apply_gripper("closed")
    time.sleep(0.6)

    _apply_arm_preset("carry")
    _apply_head("forward")
    with _state_lock:
        _state.arm_pose_name = "carry"
        _state.task = TaskState.IDLE
        _state.task_description = "idle"


def _place_sync(location: str) -> None:
    with _state_lock:
        held = _state.held_object
        _state.task = TaskState.PLACING
        _state.task_description = f"placing {held or 'item'} at {location}"
        _state.arm_pose_name = "reach_table"
    _apply_head("down")
    _apply_arm_preset("reach_table")
    time.sleep(1.0)

    _apply_gripper("open")
    if held:
        _place_object_on_surface_node(held, location)

    with _state_lock:
        _state.gripper_state = "open"
        _state.held_object = ""
    time.sleep(0.5)

    _apply_arm_preset("home")
    _apply_head("forward")
    with _state_lock:
        _state.arm_pose_name = "home"
        _state.task = TaskState.IDLE
        _state.task_description = "idle"


def _get_scene_detections_near(rx: float, ry: float, radius: float = 4.2) -> dict[str, Any]:
    """Inspect nearby 3D objects and humans around TIAGo's current position."""
    nearby_objects: list[dict[str, Any]] = []
    for name, node in _object_nodes_by_name.items():
        tf = node.getField("translation")
        if tf:
            pos = tf.getSFVec3f()
            dist = math.hypot(pos[0] - rx, pos[1] - ry)
            if dist <= radius:
                nearby_objects.append({
                    "object": name,
                    "distance_m": round(dist, 2),
                    "position": [round(pos[0], 2), round(pos[1], 2), round(pos[2], 2)],
                })

    nearby_humans: list[dict[str, Any]] = []
    for h_def, node in _human_nodes.items():
        tf = node.getField("translation")
        nf = node.getField("name")
        if tf:
            pos = tf.getSFVec3f()
            dist = math.hypot(pos[0] - rx, pos[1] - ry)
            if dist <= radius:
                nearby_humans.append({
                    "id": h_def.lower(),
                    "name": nf.getSFString() if nf else h_def,
                    "distance_m": round(dist, 2),
                    "position": [round(pos[0], 2), round(pos[1], 2)],
                })

    return {"nearby_objects": nearby_objects, "nearby_humans": nearby_humans}


def _capture_jpeg_bytes(quality: int = 75) -> bytes | None:
    try:
        w = _camera.getWidth() if hasattr(_camera, "getWidth") else 640
        h = _camera.getHeight() if hasattr(_camera, "getHeight") else 480
        raw = _camera.getImage() if hasattr(_camera, "getImage") else None
        if raw and Image is not None:
            img = Image.frombytes("RGBA", (w, h), raw, "raw", "BGRA")
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=quality)
            return buf.getvalue()
    except Exception:
        pass
    return None


def _run_steps(steps: list[tuple[str, Any]]) -> None:
    for i, (desc, action) in enumerate(steps, 1):
        with _state_lock:
            _state.errand_current_step = i
            _state.errand_message = desc
        try:
            action()
        except Exception as exc:
            with _state_lock:
                _state.errand_status = "error"
                _state.errand_message = str(exc)
                _state.task = TaskState.IDLE
                _state.task_description = "idle"
            return
    with _state_lock:
        _state.errand_status = "done"
        _state.task = TaskState.IDLE
        _state.task_description = "idle"


def _run_fetch(item: str, from_location: str) -> None:
    with _state_lock:
        _state.errand_id = str(uuid.uuid4())[:8]
        _state.errand_type = "fetch"
        _state.errand_total_steps = 4
        _state.errand_current_step = 0
        _state.errand_status = "running"
        _state.errand_message = f"Fetching {item} from {from_location}"
    steps = [
        (f"Navigating to {from_location}", lambda: _nav_to_room_sync(from_location)),
        (f"Magnetic grasping {item}", lambda: _pick_sync(item)),
        ("Returning to foyer dock", lambda: _nav_to_room_sync("docking")),
        ("Errand complete", lambda: None),
    ]
    _run_steps(steps)


def _run_deliver(item: str, from_location: str, to_location: str) -> None:
    with _state_lock:
        _state.errand_id = str(uuid.uuid4())[:8]
        _state.errand_type = "deliver"
        _state.errand_total_steps = 5
        _state.errand_current_step = 0
        _state.errand_status = "running"
        _state.errand_message = f"Delivering {item} from {from_location} to {to_location}"
    steps = [
        (f"Navigating to {from_location}", lambda: _nav_to_room_sync(from_location)),
        (f"Magnetic grasping {item}", lambda: _pick_sync(item)),
        (f"Navigating to {to_location}", lambda: _nav_to_room_sync(to_location)),
        (f"Placing {item} at {to_location}", lambda: _place_sync(to_location)),
        ("Errand complete", lambda: None),
    ]
    _run_steps(steps)


def _run_patrol(rooms: list[str]) -> None:
    with _state_lock:
        _state.errand_id = str(uuid.uuid4())[:8]
        _state.errand_type = "patrol"
        _state.errand_total_steps = len(rooms) + 1
        _state.errand_current_step = 0
        _state.errand_status = "running"
        _state.errand_message = f"Starting security patrol across {len(rooms)} zones"
        _state.patrol_logs.clear()

    steps: list[tuple[str, Any]] = []
    for rm in rooms:
        def _inspect_zone(target_room: str = rm) -> None:
            _ensure_room_light_on(target_room)
            _nav_to_room_sync(target_room)
            for direction in ("left", "right", "down", "forward"):
                _apply_head(direction)
                time.sleep(0.35)
            with _state_lock:
                rx, ry = _state.x, _state.y
            det = _get_scene_detections_near(rx, ry, radius=4.5)
            with _state_lock:
                _state.patrol_logs.append({
                    "room": target_room,
                    "timestamp": time.strftime("%H:%M:%S"),
                    "objects_seen": [o["object"] for o in det["nearby_objects"]],
                    "humans_seen": [h["name"] for h in det["nearby_humans"]],
                })

        steps.append((f"Patrolling & scanning {rm}", _inspect_zone))

    steps.append(("Returning to foyer dock", lambda: _nav_to_room_sync("foyer")))
    _run_steps(steps)


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="TIAGo House-Errand Bot API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RoomRequest(BaseModel):
    room: str

class PoseRequest(BaseModel):
    x: float
    y: float
    theta: float

class RoutePlanRequest(BaseModel):
    destination: str

class ArmPoseRequest(BaseModel):
    pose: str

class GripperRequest(BaseModel):
    state: str

class PickRequest(BaseModel):
    object: str

class PlaceRequest(BaseModel):
    location: str

class LookAtRequest(BaseModel):
    target: str

class FetchRequest(BaseModel):
    item: str
    from_location: str

class DeliverRequest(BaseModel):
    item: str
    from_location: str
    to_location: str

class PatrolRequest(BaseModel):
    rooms: list[str] | None = None

class VisionInspectRequest(BaseModel):
    query: str = "Describe what is visible in the room, including any objects, appliances, or people."
    room: str | None = None
    sweep: bool = True


@app.get("/telemetry")
def telemetry() -> JSONResponse:
    with _state_lock:
        nearest = _nearest_node(_state.x, _state.y)
        room_label = _GRAPH_NODES.get(nearest, {}).get("room", "Foyer")
        return JSONResponse({
            "pose": {"x": round(_state.x, 3), "y": round(_state.y, 3), "theta": round(_state.theta, 3)},
            "current_node": nearest,
            "current_room": room_label,
            "battery": round(_state.battery, 1),
            "gripper": _state.gripper_state,
            "arm_pose": _state.arm_pose_name,
            "task": _state.task_description,
            "held_object": _state.held_object,
            "patrol_logs": list(_state.patrol_logs),
        })


@app.post("/route/plan")
def route_plan(req: RoutePlanRequest) -> JSONResponse:
    if req.destination not in ROOMS:
        raise HTTPException(status_code=404, detail=f"Unknown destination: {req.destination}")
    with _state_lock:
        cx, cy = _state.x, _state.y
    plan = _compute_route(cx, cy, req.destination)
    return JSONResponse(plan)


@app.post("/navigate/room")
def navigate_room(req: RoomRequest) -> JSONResponse:
    if req.room not in ROOMS:
        raise HTTPException(status_code=404, detail=f"Unknown room: {req.room}")
    plan = _enqueue_room_nav(req.room)
    coords = ROOMS[req.room]
    return JSONResponse({
        "status": "navigating",
        "room": req.room,
        "waypoints": plan["waypoints"],
        "blocking_doors": plan["blocking_doors"],
        "target": {"x": coords[0], "y": coords[1], "theta": coords[2]},
    })


@app.post("/navigate/pose")
def navigate_pose(req: PoseRequest) -> JSONResponse:
    with _state_lock:
        _state.waypoint_queue = [(req.x, req.y, req.theta)]
        _state.nav_phase = "unstick"
        _state.task = TaskState.NAVIGATING
        _state.task_description = f"navigating to ({req.x:.2f}, {req.y:.2f})"
    return JSONResponse({"status": "navigating", "target": {"x": req.x, "y": req.y, "theta": req.theta}})


@app.post("/stop")
def stop() -> JSONResponse:
    with _state_lock:
        _state.waypoint_queue.clear()
        _state.task = TaskState.IDLE
        _state.task_description = "idle"
    _set_wheel_speeds(0.0, 0.0)
    return JSONResponse({"status": "stopped"})


@app.post("/arm/pose")
def arm_pose(req: ArmPoseRequest) -> JSONResponse:
    if req.pose not in ARM_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown arm pose: {req.pose}. Valid: {list(ARM_PRESETS)}")
    _apply_arm_preset(req.pose)
    with _state_lock:
        _state.arm_pose_name = req.pose
    return JSONResponse({"status": "ok", "arm_pose": req.pose})


@app.post("/gripper/set")
def gripper_set(req: GripperRequest) -> JSONResponse:
    if req.state not in ("open", "closed"):
        raise HTTPException(status_code=400, detail="state must be 'open' or 'closed'")
    _apply_gripper(req.state)
    with _state_lock:
        _state.gripper_state = req.state
        if req.state == "open" and _state.held_object:
            nearest = _nearest_node(_state.x, _state.y)
            _place_object_on_surface_node(_state.held_object, nearest)
            _state.held_object = ""
    return JSONResponse({"status": "ok", "gripper": req.state})


@app.post("/manipulate/pick")
def manipulate_pick(req: PickRequest) -> JSONResponse:
    if req.object not in OBJECTS:
        raise HTTPException(status_code=404, detail=f"Object '{req.object}' not in known objects catalogue.")
    threading.Thread(target=_pick_sync, args=(req.object,), daemon=True, name="tiago-pick").start()
    return JSONResponse({"status": "picking", "object": req.object, "mode": "supervisor_magnetic_grasp"})


@app.post("/manipulate/place")
def manipulate_place(req: PlaceRequest) -> JSONResponse:
    with _state_lock:
        if not _state.held_object:
            return JSONResponse({"status": "error", "message": "No object is currently held."})
    threading.Thread(target=_place_sync, args=(req.location,), daemon=True, name="tiago-place").start()
    return JSONResponse({"status": "placing", "location": req.location})


@app.post("/head/look_at")
def head_look_at(req: LookAtRequest) -> JSONResponse:
    _apply_head(req.target)
    return JSONResponse({"status": "ok", "looking_at": req.target})


@app.get("/camera/snapshot")
def camera_snapshot() -> JSONResponse:
    snap_path = f"/tmp/tiago_snap_{uuid.uuid4().hex[:8]}.jpg"
    try:
        _camera.saveImage(snap_path, 90)
    except Exception:
        snap_path = ""
    jpg = _capture_jpeg_bytes(quality=80)
    b64 = base64.b64encode(jpg).decode("ascii") if jpg else ""
    with _state_lock:
        rx, ry = _state.x, _state.y
    det = _get_scene_detections_near(rx, ry)
    return JSONResponse({
        "status": "ok",
        "image_path": snap_path,
        "width": 640,
        "height": 480,
        "base64_jpeg": b64,
        **det,
    })


@app.get("/camera/frame_base64")
def camera_frame_base64() -> JSONResponse:
    jpg = _capture_jpeg_bytes(quality=80)
    b64 = base64.b64encode(jpg).decode("ascii") if jpg else ""
    with _state_lock:
        rx, ry = _state.x, _state.y
    det = _get_scene_detections_near(rx, ry)
    return JSONResponse({
        "status": "ok",
        "width": 640,
        "height": 480,
        "base64_jpeg": b64,
        **det,
    })


@app.post("/vision/inspect")
def vision_inspect(req: VisionInspectRequest) -> JSONResponse:
    """Navigate (optional), ensure room lights on, pan/tilt head camera, and capture visual + scene telemetry."""
    if req.room:
        if req.room not in ROOMS:
            raise HTTPException(status_code=404, detail=f"Unknown room: {req.room}")
        _ensure_room_light_on(req.room)
        _nav_to_room_sync(req.room)
    else:
        with _state_lock:
            cur_node = _nearest_node(_state.x, _state.y)
        _ensure_room_light_on(cur_node)

    if req.sweep:
        for t in ("left", "right", "down", "forward"):
            _apply_head(t)
            time.sleep(0.25)

    jpg = _capture_jpeg_bytes(quality=80)
    b64 = base64.b64encode(jpg).decode("ascii") if jpg else ""
    with _state_lock:
        rx, ry, rtheta = _state.x, _state.y, _state.theta
        held = _state.held_object
        cur_node = _nearest_node(rx, ry)
        cur_room = _GRAPH_NODES.get(cur_node, {}).get("room", "Foyer")

    det = _get_scene_detections_near(rx, ry, radius=4.5)
    return JSONResponse({
        "status": "ok",
        "query": req.query,
        "room": cur_room,
        "node": cur_node,
        "pose": {"x": round(rx, 2), "y": round(ry, 2), "theta": round(rtheta, 2)},
        "held_object": held,
        "nearby_objects": det["nearby_objects"],
        "nearby_humans": det["nearby_humans"],
        "base64_jpeg": b64,
    })


@app.get("/camera/frame")
def camera_frame() -> Response:
    jpg = _capture_jpeg_bytes(quality=75)
    if jpg:
        return Response(content=jpg, media_type="image/jpeg")
    return Response(status_code=503)


@app.get("/camera/stream")
def camera_stream() -> StreamingResponse:
    def gen():
        while True:
            jpg = _capture_jpeg_bytes(quality=60)
            if jpg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            time.sleep(0.08)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/rooms")
def rooms() -> JSONResponse:
    return JSONResponse({"rooms": list(ROOMS.keys())})


@app.get("/objects")
def objects() -> JSONResponse:
    out: list[dict[str, Any]] = []
    for name in OBJECTS:
        pos = None
        if name in _object_nodes_by_name:
            tf = _object_nodes_by_name[name].getField("translation")
            if tf:
                pos = [round(v, 3) for v in tf.getSFVec3f()]
        out.append({"name": name, "position": pos})
    return JSONResponse({"objects": OBJECTS, "details": out})


@app.post("/errand/fetch")
def errand_fetch(req: FetchRequest) -> JSONResponse:
    with _state_lock:
        if _state.errand_status == "running":
            return JSONResponse({"status": "busy", "message": "An errand is already running."})
    threading.Thread(target=_run_fetch, args=(req.item, req.from_location), daemon=True, name="tiago-errand").start()
    return JSONResponse({"status": "started", "errand": "fetch", "item": req.item, "from": req.from_location})


@app.post("/errand/deliver")
def errand_deliver(req: DeliverRequest) -> JSONResponse:
    with _state_lock:
        if _state.errand_status == "running":
            return JSONResponse({"status": "busy", "message": "An errand is already running."})
    threading.Thread(
        target=_run_deliver, args=(req.item, req.from_location, req.to_location), daemon=True, name="tiago-errand"
    ).start()
    return JSONResponse({"status": "started", "errand": "deliver", "item": req.item})


@app.post("/errand/patrol")
def errand_patrol(req: PatrolRequest) -> JSONResponse:
    with _state_lock:
        if _state.errand_status == "running":
            return JSONResponse({"status": "busy", "message": "An errand is already running."})
    target_rooms = req.rooms or ["living_room", "dining_room", "kitchen", "master_bedroom", "study_bedroom"]
    threading.Thread(target=_run_patrol, args=(target_rooms,), daemon=True, name="tiago-patrol").start()
    return JSONResponse({"status": "started", "errand": "patrol", "rooms": target_rooms})


@app.get("/errand/status")
def errand_status() -> JSONResponse:
    with _state_lock:
        return JSONResponse({
            "task_id": _state.errand_id,
            "errand_type": _state.errand_type,
            "current_step": _state.errand_current_step,
            "total_steps": _state.errand_total_steps,
            "status": _state.errand_status,
            "message": _state.errand_message,
            "held_object": _state.held_object,
            "patrol_logs": list(_state.patrol_logs),
        })


def _start_api() -> None:
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


def main() -> None:
    api_thread = threading.Thread(target=_start_api, daemon=True, name="tiago-api")
    api_thread.start()

    if _WEBOTS and robot is not None:
        _last_battery_tick = time.time()
        while robot.step(time_step) != -1:
            _step_navigation()
            now = time.time()
            if now - _last_battery_tick > 60:
                with _state_lock:
                    _state.battery = max(0.0, _state.battery - 0.5)
                _last_battery_tick = now
    else:
        api_thread.join()


if __name__ == "__main__":
    main()
