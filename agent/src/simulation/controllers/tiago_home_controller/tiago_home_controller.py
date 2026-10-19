"""TIAGo House-Errand Bot – Webots controller with Ground-Truth Pose & Door Auto-Clearance."""

from __future__ import annotations

import heapq
import json
import logging
import math
import threading
import io
import time
import urllib.request
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
    from controller import Supervisor, Robot  # type: ignore
    _WEBOTS = True
except ImportError:
    _WEBOTS = False

# ═══════════════════════════════════════════════════════════════════════════════
# Constants & Beacon Home Manhattan Navigation Graph
# ═══════════════════════════════════════════════════════════════════════════════

PORT = 8001
SMART_HOME_API = "http://127.0.0.1:8000"
TIME_STEP = 16  # Matches beacon_home.wbt basicTimeStep

WHEEL_RADIUS = 0.0985       # metres
WHEEL_SEPARATION = 0.4044   # metres
MAX_SPEED = 4.5             # rad/s

# Exact orthogonal Manhattan navigation graph matching your red path in beacon_home_1.png.
# Note: Corridor spine uses y = -7.62 to give extra clearance from the Corridor Radiator at y = -6.88.
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

ROOMS: dict[str, tuple[float, float, float]] = {
    k: v["pose"] for k, v in NAV_NODES.items()
}

OBJECTS: list[str] = [
    "cup", "bottle", "plate", "book", "remote_control",
    "medicine_box", "glasses", "phone", "keys", "tray",
]

# Joint order for TIAGo + Robotiq 2F-85:
# [torso_lift_joint, arm_1_joint, arm_2_joint, arm_3_joint, arm_4_joint, arm_6_joint]
# Validated against official tiago_robotiq_grippers.py joint limits (arm_3 min is -2.237).
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


def _fetch_smart_home_doors() -> list[dict[str, Any]]:
    try:
        with urllib.request.urlopen(f"{SMART_HOME_API}/api/doors", timeout=0.6) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []


def _open_door_via_http(door_name: str) -> None:
    """Ensure the Smart Home Hub API also marks the door open."""
    try:
        doors = _fetch_smart_home_doors()
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

    live_doors = _fetch_smart_home_doors()
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


# ═══════════════════════════════════════════════════════════════════════════════
# State Machine & Robot Hardware Setup
# ═══════════════════════════════════════════════════════════════════════════════

class TaskState(Enum):
    IDLE = auto()
    NAVIGATING = auto()
    PICKING = auto()
    PLACING = auto()


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
    nav_phase: str = "unstick"  # 'unstick' | 'rotate_to_goal' | 'drive' | 'final_align'
    nav_start_sim_time: float = 0.0
    errand_id: str = ""
    errand_type: str = ""
    errand_current_step: int = 0
    errand_total_steps: int = 0
    errand_status: str = "idle"
    errand_message: str = ""


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

    # Discover Supervisor self node and Door nodes for ground-truth pose & direct door opening
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

    # Exact 6 arm joints for TIAGo + Robotiq 2F-85 (from official tiago_robotiq_grippers.py)
    _arm_joint_names = [
        "torso_lift_joint",
        "arm_1_joint",
        "arm_2_joint",
        "arm_3_joint",
        "arm_4_joint",
        "arm_6_joint",
    ]
    _arm_joints = [_dev(n) or _StubMotor() for n in _arm_joint_names]

    # Immediately fold the arm out of the radiator using valid joint limits
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
    "left":    (0.5, 0.0),
    "right":  (-0.5, 0.0),
    "up":      (0.0, -0.4),
    "down":    (0.0, 0.4),
}


def _apply_head(target: str) -> bool:
    pan, tilt = _HEAD_TARGETS.get(target, (0.0, 0.0))
    _head_pan.setPosition(pan)
    _head_tilt.setPosition(tilt)
    return True


def _ensure_webots_door_open(door_name: str) -> None:
    """Directly raise any blocking interior door in the Webots scene tree."""
    if door_name in _door_nodes_by_name:
        node, base_z = _door_nodes_by_name[door_name]
        tf = node.getField("translation")
        if tf:
            pos = list(tf.getSFVec3f())
            if pos[2] < base_z + 2.0:
                pos[2] = base_z + 2.25
                tf.setSFVec3f(pos)


# ═══════════════════════════════════════════════════════════════════════════════
# Ground-Truth Pose & Orthogonal Waypoint Follower (Runs in Main Webots Thread)
# ═══════════════════════════════════════════════════════════════════════════════

_odom_left_prev: float = 0.0
_odom_right_prev: float = 0.0
_odom_initialized: bool = False


def _norm_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def _update_pose() -> None:
    """Update _state (x, y, theta) from Webots Supervisor ground-truth (or wheel odometry fallback)."""
    global _odom_left_prev, _odom_right_prev, _odom_initialized
    if not _WEBOTS:
        return

    # 1. Preferred: Exact 3D ground-truth pose from Webots Supervisor
    if _self_node is not None:
        try:
            pos = _self_node.getPosition()
            rot = _self_node.getOrientation()  # 3x3 row-major rotation matrix
            yaw = math.atan2(rot[3], rot[0])
            with _state_lock:
                _state.x = float(pos[0])
                _state.y = float(pos[1])
                _state.theta = _norm_angle(yaw)
            return
        except Exception:
            pass

    # 2. Fallback: Wheel encoders
    left_pos = _left_enc.getValue()
    right_pos = _right_enc.getValue()
    if math.isnan(left_pos) or math.isnan(right_pos):
        return
    if not _odom_initialized:
        _odom_left_prev = left_pos
        _odom_right_prev = right_pos
        _odom_initialized = True
        return

    dl = (left_pos - _odom_left_prev) * WHEEL_RADIUS
    dr = (right_pos - _odom_right_prev) * WHEEL_RADIUS
    _odom_left_prev = left_pos
    _odom_right_prev = right_pos
    dc = (dl + dr) / 2.0
    dtheta = (dr - dl) / WHEEL_SEPARATION

    with _state_lock:
        _state.theta = _norm_angle(_state.theta + dtheta)
        _state.x += dc * math.cos(_state.theta)
        _state.y += dc * math.sin(_state.theta)


def _step_navigation() -> None:
    """Executed exclusively inside the main Webots step loop."""
    if not _WEBOTS or robot is None:
        return

    _update_pose()
    sim_now = robot.getTime()

    # Wait 1.2s at simulation start so the arm finishes folding out of the radiator
    if sim_now < 1.2:
        _set_wheel_speeds(0.0, 0.0)
        return

    with _state_lock:
        if _state.task != TaskState.NAVIGATING or not _state.waypoint_queue:
            return

        # Guarantee any doors along the active route are physically open in Webots
        for d_name in _state.doors_to_clear:
            _ensure_webots_door_open(d_name)

        tx, ty, ttheta = _state.waypoint_queue[0]
        dx = tx - _state.x
        dy = ty - _state.y
        dist = math.hypot(dx, dy)
        desired_heading = math.atan2(dy, dx)
        heading_err = _norm_angle(desired_heading - _state.theta)

        # Phase 0: Back up slightly (0.14m toward -Y) if spawned too close to the north corridor radiator
        if _state.nav_phase == "unstick":
            if _state.y > -7.58 and abs(_norm_angle(_state.theta - 1.5708)) < 0.6:
                _set_wheel_speeds(-2.0, -2.0)
                return
            _set_wheel_speeds(0.0, 0.0)
            _state.nav_phase = "rotate_to_goal"

        # Phase 1: Rotate in place toward next Manhattan waypoint
        if _state.nav_phase == "rotate_to_goal":
            if dist < 0.10:
                _state.nav_phase = "final_align"
            elif abs(heading_err) > 0.05:
                # If facing +Y (1.57 rad) in the corridor and turning toward -X (pi rad),
                # rotate CLOCKWISE (ang < 0) if near the north wall so the right arm swings into open space.
                ang = max(-2.0, min(2.0, heading_err * 3.2))
                if abs(heading_err) < 0.25:
                    ang = math.copysign(max(0.35, abs(ang)), heading_err)
                _set_wheel_speeds(-ang, ang)
                return
            else:
                _set_wheel_speeds(0.0, 0.0)
                _state.nav_phase = "drive"

        # Phase 2: Drive straight along orthogonal corridor segment
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

        # Phase 3: Advance to next corner or align final heading
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


# ═══════════════════════════════════════════════════════════════════════════════
# Errand Runners
# ═══════════════════════════════════════════════════════════════════════════════

def _enqueue_room_nav(room: str) -> dict[str, Any]:
    _update_pose()
    with _state_lock:
        cx, cy = _state.x, _state.y
    plan = _compute_route(cx, cy, room)
    # Also notify Smart Home HTTP server to open any doors on path
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
        _state.task_description = f"picking {obj}"
    _apply_arm_preset("reach_table")
    time.sleep(1.5)
    _apply_gripper("closed")
    time.sleep(0.8)
    _apply_arm_preset("carry")
    with _state_lock:
        _state.gripper_state = "closed"
        _state.held_object = obj
        _state.arm_pose_name = "carry"
        _state.task = TaskState.IDLE
        _state.task_description = "idle"


def _place_sync(location: str) -> None:
    with _state_lock:
        _state.task = TaskState.PLACING
        _state.task_description = f"placing at {location}"
    _apply_arm_preset("reach_table")
    time.sleep(1.2)
    _apply_gripper("open")
    time.sleep(0.6)
    _apply_arm_preset("home")
    with _state_lock:
        _state.gripper_state = "open"
        _state.held_object = ""
        _state.arm_pose_name = "home"
        _state.task = TaskState.IDLE
        _state.task_description = "idle"


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
    import uuid
    with _state_lock:
        _state.errand_id = str(uuid.uuid4())[:8]
        _state.errand_type = "fetch"
        _state.errand_total_steps = 4
        _state.errand_current_step = 0
        _state.errand_status = "running"
        _state.errand_message = f"Fetching {item} from {from_location}"
    steps = [
        (f"Navigating to {from_location}", lambda: _nav_to_room_sync(from_location)),
        (f"Picking {item}", lambda: _pick_sync(item)),
        ("Returning to docking station", lambda: _nav_to_room_sync("docking")),
        ("Errand complete", lambda: None),
    ]
    _run_steps(steps)


def _run_deliver(item: str, from_location: str, to_location: str) -> None:
    import uuid
    with _state_lock:
        _state.errand_id = str(uuid.uuid4())[:8]
        _state.errand_type = "deliver"
        _state.errand_total_steps = 5
        _state.errand_current_step = 0
        _state.errand_status = "running"
        _state.errand_message = f"Delivering {item} from {from_location} to {to_location}"
    steps = [
        (f"Navigating to {from_location}", lambda: _nav_to_room_sync(from_location)),
        (f"Picking {item}", lambda: _pick_sync(item)),
        (f"Navigating to {to_location}", lambda: _nav_to_room_sync(to_location)),
        (f"Placing {item}", lambda: _place_sync(to_location)),
        ("Errand complete", lambda: None),
    ]
    _run_steps(steps)


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(title="TIAGo House-Errand Bot API", version="1.2.0")
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


@app.get("/telemetry")
def telemetry() -> JSONResponse:
    with _state_lock:
        return JSONResponse({
            "pose": {"x": round(_state.x, 3), "y": round(_state.y, 3), "theta": round(_state.theta, 3)},
            "battery": round(_state.battery, 1),
            "gripper": _state.gripper_state,
            "arm_pose": _state.arm_pose_name,
            "task": _state.task_description,
            "held_object": _state.held_object,
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
    return JSONResponse({"status": "ok", "gripper": req.state})


@app.post("/manipulate/pick")
def manipulate_pick(req: PickRequest) -> JSONResponse:
    if req.object not in OBJECTS:
        raise HTTPException(status_code=404, detail=f"Object '{req.object}' not in known objects catalogue.")
    threading.Thread(target=_pick_sync, args=(req.object,), daemon=True, name="tiago-pick").start()
    return JSONResponse({"status": "picking", "object": req.object})


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
    import uuid
    snap_path = f"/tmp/tiago_snap_{uuid.uuid4().hex[:8]}.jpg"
    try:
        _camera.saveImage(snap_path, 90)
    except Exception:
        snap_path = ""
    return JSONResponse({"status": "ok", "image_path": snap_path, "width": 640, "height": 480})


@app.get("/camera/frame")
def camera_frame() -> Response:
    try:
        w = _camera.getWidth() if hasattr(_camera, "getWidth") else 640
        h = _camera.getHeight() if hasattr(_camera, "getHeight") else 480
        raw = _camera.getImage() if hasattr(_camera, "getImage") else None
        if raw and Image is not None:
            img = Image.frombytes("RGBA", (w, h), raw, "raw", "BGRA")
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=75)
            return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception:
        pass
    return Response(status_code=503)


@app.get("/camera/stream")
def camera_stream() -> StreamingResponse:
    def gen():
        w = _camera.getWidth() if hasattr(_camera, "getWidth") else 640
        h = _camera.getHeight() if hasattr(_camera, "getHeight") else 480
        while True:
            try:
                raw = _camera.getImage() if hasattr(_camera, "getImage") else None
                if raw and Image is not None:
                    img = Image.frombytes("RGBA", (w, h), raw, "raw", "BGRA")
                    buf = io.BytesIO()
                    img.convert("RGB").save(buf, format="JPEG", quality=60)
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + buf.getvalue() + b"\r\n"
                    )
            except Exception:
                pass
            time.sleep(0.08)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/rooms")
def rooms() -> JSONResponse:
    return JSONResponse({"rooms": list(ROOMS.keys())})


@app.get("/objects")
def objects() -> JSONResponse:
    return JSONResponse({"objects": OBJECTS})


@app.post("/errand/fetch")
def errand_fetch(req: FetchRequest) -> JSONResponse:
    with _state_lock:
        if _state.errand_status == "running":
            return JSONResponse({"status": "busy", "message": "An errand is already running."})
    threading.Thread(
        target=_run_fetch, args=(req.item, req.from_location), daemon=True, name="tiago-errand"
    ).start()
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
