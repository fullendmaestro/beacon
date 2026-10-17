from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("smart_home_controller.demo_recorder")

# Curated cinematic camera presets for rooms and capabilities
CINEMATIC_PRESETS: dict[str, dict[str, Any]] = {
    "overview": {
        "position": [-15.5, -14.2, 19.5],
        "target": [-4.8, -6.5, 0.5],
    },
    "living_room_light": {
        "position": [-3.6, -1.2, 3.1],
        "target": [-7.41, -4.34, 1.8],
    },
    "kitchen_light": {
        "position": [-3.5, -4.8, 3.0],
        "target": [-1.33, -2.47, 1.8],
    },
    "master_bedroom_light": {
        "position": [-3.5, -8.5, 3.0],
        "target": [-1.95, -10.57, 1.6],
    },
    "front_door": {
        "position": [-2.8, -7.5, 2.2],
        "target": [0.0, -7.49, 1.1],
    },
    "driveway_gate": {
        "position": [2.1, -4.8, 3.5],
        "target": [2.1, -9.55, 0.6],
    },
    "living_room_blinds": {
        "position": [-6.5, -3.5, 2.2],
        "target": [-11.0, -3.48, 1.25],
    },
    "rover_dock": {
        "position": [-1.2, -5.8, 2.6],
        "target": [-3.1, -7.5, 0.3],
    },
}


def _normalize(v: list[float]) -> list[float]:
    norm = math.sqrt(sum(c * c for c in v))
    if norm < 1e-8:
        return [0.0, 0.0, 1.0]
    return [c / norm for c in v]


def _cross(a: list[float], b: list[float]) -> list[float]:
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]


def _look_at_axis_angle(cam_pos: list[float], target_pos: list[float]) -> list[float]:
    """
    Compute Webots Viewpoint SFRotation [ax, ay, az, angle] in FLU (Forward-Left-Up)
    convention so the camera at `cam_pos` looks directly at `target_pos` with Z-up.
    """
    forward = _normalize([
        target_pos[0] - cam_pos[0],
        target_pos[1] - cam_pos[1],
        target_pos[2] - cam_pos[2],
    ])
    world_up = [0.0, 0.0, 1.0]
    if abs(sum(f * u for f, u in zip(forward, world_up))) > 0.99:
        world_up = [0.0, 1.0, 0.0]

    left = _normalize(_cross(world_up, forward))
    up = _normalize(_cross(forward, left))

    # Rotation matrix columns: [forward, left, up]
    r00, r01, r02 = forward[0], left[0], up[0]
    r10, r11, r12 = forward[1], left[1], up[1]
    r20, r21, r22 = forward[2], left[2], up[2]

    trace = r00 + r11 + r22
    cos_theta = max(-1.0, min(1.0, (trace - 1.0) / 2.0))
    angle = math.acos(cos_theta)

    if abs(angle) < 1e-6:
        return [0.0, 0.0, 1.0, 0.0]

    denom = 2.0 * math.sin(angle)
    if abs(denom) < 1e-6:
        return [0.0, 0.0, 1.0, angle]

    ax = (r21 - r12) / denom
    ay = (r02 - r20) / denom
    az = (r10 - r01) / denom
    axis = _normalize([ax, ay, az])
    return [round(axis[0], 5), round(axis[1], 5), round(axis[2], 5), round(angle, 5)]


def _axis_angle_to_quat(aa: list[float]) -> list[float]:
    ax, ay, az, angle = aa
    half = angle * 0.5
    s = math.sin(half)
    return [math.cos(half), ax * s, ay * s, az * s]


def _quat_to_axis_angle(q: list[float]) -> list[float]:
    w, x, y, z = q
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm > 0:
        w, x, y, z = w / norm, x / norm, y / norm, z / norm
    w = max(-1.0, min(1.0, w))
    angle = 2.0 * math.acos(w)
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-6:
        return [0.0, 0.0, 1.0, 0.0]
    return [x / s, y / s, z / s, angle]


def _slerp_axis_angle(aa1: list[float], aa2: list[float], t: float) -> list[float]:
    q1 = _axis_angle_to_quat(aa1)
    q2 = _axis_angle_to_quat(aa2)
    dot = sum(a * b for a, b in zip(q1, q2))
    if dot < 0.0:
        q2 = [-c for c in q2]
        dot = -dot
    if dot > 0.9995:
        q = [q1[i] + t * (q2[i] - q1[i]) for i in range(4)]
        return _quat_to_axis_angle(q)
    theta_0 = math.acos(max(-1.0, min(1.0, dot)))
    sin_theta_0 = math.sin(theta_0)
    theta = theta_0 * t
    s1 = math.cos(theta) - dot * math.sin(theta) / sin_theta_0
    s2 = math.sin(theta) / sin_theta_0
    q = [s1 * q1[i] + s2 * q2[i] for i in range(4)]
    return _quat_to_axis_angle(q)


class DemoRecorderManager:
    """
    Controls the Webots 3D Viewpoint camera for clear capability demonstrations
    (smooth zoom/focus on lights, doors, blinds, or continuous tracking of the rover)
    and manages native Webots MP4 video recordings.
    """

    def __init__(self, artifacts_dir: str | Path | None = None) -> None:
        self.supervisor: Any = None
        self.viewpoint_node: Any = None
        self.vp_pos_field: Any = None
        self.vp_ori_field: Any = None

        default_dir = Path(__file__).resolve().parents[5] / "artifacts" / "videos" / "webots"
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else default_dir
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Animation & tracking state
        self._anim_start_pos: list[float] | None = None
        self._anim_target_pos: list[float] | None = None
        self._anim_start_ori: list[float] | None = None
        self._anim_target_ori: list[float] | None = None
        self._anim_step: int = 0
        self._anim_total_steps: int = 0

        self.follow_mode: bool = False
        self.follow_node: Any = None
        self.follow_offset: list[float] = [-2.4, -2.4, 2.8]

        # Recording state
        self.is_recording: bool = False
        self.current_video_path: str | None = None
        self.last_video_path: str | None = None
        self.recording_label: str | None = None
        self.recording_started_at: float | None = None

    def init_devices(self, supervisor: Any, root_nodes: list[Any]) -> None:
        self.supervisor = supervisor
        for node in root_nodes:
            if node.getTypeName() == "Viewpoint":
                self.viewpoint_node = node
                self.vp_pos_field = node.getField("position")
                self.vp_ori_field = node.getField("orientation")
                break

    def _start_camera_transition(
        self,
        cam_pos: list[float],
        target_pos: list[float],
        duration_sec: float = 1.0,
        time_step_ms: int = 16,
    ) -> dict[str, Any]:
        if not self.vp_pos_field or not self.vp_ori_field:
            return {"success": False, "error": "Viewpoint node not found in Webots world"}

        current_pos = list(self.vp_pos_field.getSFVec3f())
        current_ori = list(self.vp_ori_field.getSFRotation())
        target_ori = _look_at_axis_angle(cam_pos, target_pos)

        total_steps = max(1, int((duration_sec * 1000.0) / max(1, time_step_ms)))
        self._anim_start_pos = current_pos
        self._anim_target_pos = cam_pos
        self._anim_start_ori = current_ori
        self._anim_target_ori = target_ori
        self._anim_step = 0
        self._anim_total_steps = total_steps

        return {
            "success": True,
            "camera_position": [round(c, 3) for c in cam_pos],
            "target_position": [round(c, 3) for c in target_pos],
            "camera_orientation": target_ori,
            "transition_seconds": duration_sec,
        }

    def focus_camera(
        self,
        cmd: dict[str, Any],
        lighting_mgr: Any,
        access_mgr: Any,
        rover_mgr: Any,
        time_step_ms: int,
    ) -> dict[str, Any]:
        """
        Focus the Webots Viewpoint camera on:
        - A named preset (`preset`: 'overview', 'living_room_light', 'kitchen_light', 'rover_dock', etc.)
        - A continuous tracking target (`mode`: 'follow_rover')
        - Any specific smart home device by name or ID (`target_type`: 'light'|'door'|'blind'|'rover', `target_name`: str)
        - Custom coordinates (`camera_position`, `target_position`)
        """
        mode = cmd.get("mode", "focus")
        duration = float(cmd.get("duration", 1.0))

        # 1. Continuous Rover Tracking Mode
        if mode == "follow_rover" or cmd.get("target_type") == "rover":
            self.follow_mode = True
            self.follow_node = rover_mgr.rover_node
            if cmd.get("offset"):
                self.follow_offset = [float(x) for x in cmd["offset"]]
            else:
                self.follow_offset = [-2.2, -2.2, 2.6]

            if self.follow_node:
                t_field = self.follow_node.getField("translation")
                r_pos = list(t_field.getSFVec3f()) if t_field else [-3.1, -7.5, 0.2]
                cam_pos = [
                    r_pos[0] + self.follow_offset[0],
                    r_pos[1] + self.follow_offset[1],
                    r_pos[2] + self.follow_offset[2],
                ]
                res = self._start_camera_transition(cam_pos, r_pos, duration, time_step_ms)
                return {**res, "mode": "follow_rover"}

        # Disable follow mode when focusing on static targets
        self.follow_mode = False
        self.follow_node = None

        # 2. Named Cinematic Preset
        preset_name = cmd.get("preset")
        if preset_name and preset_name in CINEMATIC_PRESETS:
            preset = CINEMATIC_PRESETS[preset_name]
            res = self._start_camera_transition(
                list(preset["position"]),
                list(preset["target"]),
                duration,
                time_step_ms,
            )
            return {**res, "preset": preset_name}

        # 3. Explicit Camera & Target Coordinates
        if cmd.get("camera_position") and cmd.get("target_position"):
            cam_pos = [float(x) for x in cmd["camera_position"]]
            target_pos = [float(x) for x in cmd["target_position"]]
            return self._start_camera_transition(cam_pos, target_pos, duration, time_step_ms)

        # 4. Dynamic Device Node Lookup (Light, Door, Blind)
        target_name = str(cmd.get("target_name", "")).strip().lower()
        target_node = None
        device_label = target_name

        # Search lights
        for node_id, l_state in lighting_mgr.light_states.items():
            if target_name in l_state["name"].lower() or target_name == str(node_id):
                target_node = lighting_mgr.light_nodes.get(node_id)
                device_label = l_state["name"]
                break

        # Search doors/gates if not found in lights
        if not target_node:
            for d_id, d_state in access_mgr.door_states.items():
                if target_name in d_state["name"].lower() or target_name == d_id.lower():
                    target_node = access_mgr.door_nodes.get(d_id)
                    device_label = d_state["name"]
                    break

        # Search blinds if still not found
        if not target_node:
            for b_id, b_state in access_mgr.blind_states.items():
                if target_name in b_state["name"].lower() or target_name == b_id.lower():
                    target_node = access_mgr.blind_nodes.get(b_id)
                    device_label = b_state["name"]
                    break

        if target_node:
            t_field = target_node.getField("translation")
            node_pos = list(t_field.getSFVec3f()) if t_field else [-5.0, -5.0, 1.5]
            # Position the camera at an interior/exterior vantage point 3.2m offset so both
            # the light fixture and the illuminated furniture below it are clearly framed
            look_target = [node_pos[0], node_pos[1], max(1.0, node_pos[2] - 0.65)]
            offset = cmd.get("offset") or [2.6, 2.4, 0.55]
            cam_pos = [
                node_pos[0] + float(offset[0]),
                node_pos[1] + float(offset[1]),
                min(3.1, max(1.7, node_pos[2] + float(offset[2]))),
            ]
            res = self._start_camera_transition(cam_pos, look_target, duration, time_step_ms)
            return {**res, "focused_device": device_label}

        return {"success": False, "error": f"Could not resolve camera target '{target_name or preset_name}'"}

    def step(self) -> None:
        """Advance smooth camera transitions or continuous rover tracking every simulation step."""
        if not self.vp_pos_field or not self.vp_ori_field:
            return

        # 1. Active interpolated transition
        if self._anim_total_steps > 0 and self._anim_step < self._anim_total_steps:
            self._anim_step += 1
            raw_t = self._anim_step / float(self._anim_total_steps)
            # Smooth cubic ease-in-out
            t = 3.0 * raw_t * raw_t - 2.0 * raw_t * raw_t * raw_t

            assert self._anim_start_pos and self._anim_target_pos
            assert self._anim_start_ori and self._anim_target_ori

            interp_pos = [
                self._anim_start_pos[i] + t * (self._anim_target_pos[i] - self._anim_start_pos[i])
                for i in range(3)
            ]
            interp_ori = _slerp_axis_angle(self._anim_start_ori, self._anim_target_ori, t)

            self.vp_pos_field.setSFVec3f(interp_pos)
            self.vp_ori_field.setSFRotation(interp_ori)
            return

        # 2. Continuous smooth tracking for moving targets (Rover)
        if self.follow_mode and self.follow_node:
            t_field = self.follow_node.getField("translation")
            if not t_field:
                return
            r_pos = list(t_field.getSFVec3f())
            desired_cam = [
                r_pos[0] + self.follow_offset[0],
                r_pos[1] + self.follow_offset[1],
                r_pos[2] + self.follow_offset[2],
            ]
            cur_cam = list(self.vp_pos_field.getSFVec3f())
            alpha = 0.08  # Exponential smoothing factor
            smoothed_cam = [cur_cam[i] + alpha * (desired_cam[i] - cur_cam[i]) for i in range(3)]
            look_target = [r_pos[0], r_pos[1], r_pos[2] + 0.25]
            desired_ori = _look_at_axis_angle(smoothed_cam, look_target)

            self.vp_pos_field.setSFVec3f(smoothed_cam)
            self.vp_ori_field.setSFRotation(desired_ori)

    # ------------------------------------------------------------------
    # Webots Native MP4 Video Recording
    # ------------------------------------------------------------------

    def start_recording(self, cmd: dict[str, Any]) -> dict[str, Any]:
        if not self.supervisor:
            return {"success": False, "error": "Supervisor not initialized"}

        if self.is_recording:
            self.stop_recording()

        label = str(cmd.get("label", "capability_demo")).strip().lower().replace(" ", "_")
        width = int(cmd.get("width", 1920))
        height = int(cmd.get("height", 1080))
        quality = int(cmd.get("quality", 95))
        acceleration = int(cmd.get("acceleration", 1))
        caption = bool(cmd.get("caption", False))

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = cmd.get("filename") or f"webots_{label}_{timestamp}.mp4"
        output_path = (self.artifacts_dir / filename).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.supervisor.movieStartRecording(
            str(output_path),
            width,
            height,
            0,  # codec (0 = default MPEG-4/H.264)
            quality,
            acceleration,
            caption,
        )
        self.is_recording = True
        self.current_video_path = str(output_path)
        self.recording_label = label
        self.recording_started_at = time.time()

        logger.info("Started Webots video recording: %s (%dx%d)", self.current_video_path, width, height)
        return {
            "success": True,
            "is_recording": True,
            "label": label,
            "video_path": self.current_video_path,
            "resolution": f"{width}x{height}",
        }

    def stop_recording(self) -> dict[str, Any]:
        if not self.supervisor or not self.is_recording:
            return {
                "success": True,
                "is_recording": False,
                "video_path": self.last_video_path,
            }

        self.supervisor.movieStopRecording()
        self.is_recording = False
        saved_path = self.current_video_path
        self.last_video_path = saved_path
        self.current_video_path = None
        duration = round(time.time() - (self.recording_started_at or time.time()), 2)

        logger.info("Stopped Webots video recording: %s (%.2fs)", saved_path, duration)
        return {
            "success": True,
            "is_recording": False,
            "label": self.recording_label,
            "video_path": saved_path,
            "duration_seconds": duration,
            "movie_ready": bool(self.supervisor.movieIsReady()),
        }

    def get_status(self) -> dict[str, Any]:
        vp_pos = list(self.vp_pos_field.getSFVec3f()) if self.vp_pos_field else None
        vp_ori = list(self.vp_ori_field.getSFRotation()) if self.vp_ori_field else None
        return {
            "is_recording": self.is_recording,
            "label": self.recording_label,
            "current_video_path": self.current_video_path,
            "last_video_path": self.last_video_path,
            "movie_ready": bool(self.supervisor.movieIsReady()) if self.supervisor else False,
            "movie_failed": bool(self.supervisor.movieFailed()) if self.supervisor else False,
            "follow_mode": self.follow_mode,
            "viewpoint": {
                "position": [round(x, 3) for x in vp_pos] if vp_pos else None,
                "orientation": [round(x, 4) for x in vp_ori] if vp_ori else None,
            },
            "available_presets": list(CINEMATIC_PRESETS.keys()),
        }