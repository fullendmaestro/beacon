from __future__ import annotations

import json
import math
from typing import Any

from controller import Compass, DistanceSensor, GPS, Motor, Robot

WHEEL_RADIUS = 0.05
LX = 0.228
LY = 0.158
MAX_WHEEL_SPEED = 4.0
DISTANCE_TOLERANCE = 0.12
ANGLE_TOLERANCE = 0.08

ARM_POSES: dict[str, list[float]] = {
    "reset": [0.0, 1.57, -2.635, 1.78, 0.0],
    "front_floor": [0.0, -0.97, -1.55, -0.61, 0.0],
    "front_box": [0.0, 0.0, -0.77, -1.21, 0.0],
    "front_plate": [0.0, -0.62, -0.98, -1.53, 0.0],
    "back_plate_high": [0.0, 0.678, 0.682, 1.74, 0.0],
    "back_plate_low": [0.0, 0.92, 0.42, 1.78, 0.0],
    "inspect_high": [0.0, 0.2, -0.3, -0.8, 0.0],
}


class BeaconRover:
    def __init__(self) -> None:
        self.robot = Robot()
        self.time_step = int(self.robot.getBasicTimeStep())
        self.last_cmd_ts: float = 0.0

        # 4 Mecanum Wheels
        self.wheels: list[Motor] = []
        for i in range(1, 5):
            motor = self.robot.getDevice(f"wheel{i}")
            motor.setPosition(float("inf"))
            motor.setVelocity(0.0)
            self.wheels.append(motor)

        # 5-DOF Arm Motors
        self.arm_motors: list[Motor] = []
        for i in range(1, 6):
            motor = self.robot.getDevice(f"arm{i}")
            motor.setVelocity(0.8)
            self.arm_motors.append(motor)

        # Parallel Gripper Fingers
        self.finger_left: Motor | None = self.robot.getDevice("finger::left")
        self.finger_right: Motor | None = self.robot.getDevice("finger::right")
        if self.finger_left:
            self.finger_left.setVelocity(0.03)
        if self.finger_right:
            self.finger_right.setVelocity(0.03)

        # Navigation Sensors
        self.gps: GPS = self.robot.getDevice("gps")
        if self.gps:
            self.gps.enable(self.time_step)

        self.compass: Compass = self.robot.getDevice("compass")
        if self.compass:
            self.compass.enable(self.time_step)

        # Obstacle Avoidance Distance Sensors
        self.ds_front: DistanceSensor = self.robot.getDevice("ds_front")
        self.ds_left: DistanceSensor = self.robot.getDevice("ds_front_left")
        self.ds_right: DistanceSensor = self.robot.getDevice("ds_front_right")
        for ds in (self.ds_front, self.ds_left, self.ds_right):
            if ds:
                ds.enable(self.time_step)

        self.mode: str = "idle"
        self.waypoints: list[tuple[float, float, float]] = []
        self.current_wp_idx: int = 0
        self.target_pose: tuple[float, float, float] | None = None

        # Unstuck / escape mechanism
        self._last_progress_pos: tuple[float, float] = (0.0, 0.0)
        self._steps_since_progress: int = 0
        self._escape_steps: int = 0       # >0 means currently executing an escape spin
        self._escape_dir: float = 1.0     # +1 CCW, -1 CW
        # ~2 s of no progress (> 3 cm) triggers escape
        self._STUCK_STEPS = int(2000 / self.time_step)
        # ~1.5 s spin-in-place escape duration
        self._ESCAPE_STEPS = int(1500 / self.time_step)

        self.set_arm_pose("reset")
        self.set_gripper("release")

    # ------------------------------------------------------------------
    # Low-level drive
    # ------------------------------------------------------------------

    def set_mecanum_velocity(self, vx: float, vy: float, omega: float) -> None:
        geom = LX + LY
        speeds = [
            (1.0 / WHEEL_RADIUS) * (vx - vy - geom * omega),  # wheel1: Front-Left
            (1.0 / WHEEL_RADIUS) * (vx + vy + geom * omega),  # wheel2: Front-Right
            (1.0 / WHEEL_RADIUS) * (vx + vy - geom * omega),  # wheel3: Rear-Left
            (1.0 / WHEEL_RADIUS) * (vx - vy + geom * omega),  # wheel4: Rear-Right
        ]
        for i in range(4):
            clamped = max(-MAX_WHEEL_SPEED, min(MAX_WHEEL_SPEED, speeds[i]))
            self.wheels[i].setVelocity(clamped)

    def stop_base(self) -> None:
        for wheel in self.wheels:
            wheel.setVelocity(0.0)

    # ------------------------------------------------------------------
    # Arm & gripper
    # ------------------------------------------------------------------

    def set_arm_pose(self, pose_name: str) -> None:
        angles = ARM_POSES.get(pose_name, ARM_POSES["reset"])
        for i, angle in enumerate(angles):
            if i < len(self.arm_motors) and self.arm_motors[i]:
                self.arm_motors[i].setPosition(angle)

    def set_gripper(self, action: str) -> None:
        target = 0.025 if action == "release" else 0.0
        if self.finger_left:
            self.finger_left.setPosition(target)
        if self.finger_right:
            self.finger_right.setPosition(target)

    # ------------------------------------------------------------------
    # Pose estimation
    # ------------------------------------------------------------------

    def get_pose(self) -> tuple[float, float, float]:
        if not self.gps or not self.compass:
            return 0.0, 0.0, 0.0
        pos = self.gps.getValues()
        comp = self.compass.getValues()
        yaw = math.atan2(comp[0], comp[1])
        return pos[0], pos[1], yaw

    # ------------------------------------------------------------------
    # Navigation step — returns True when waypoint is reached
    # ------------------------------------------------------------------

    def step_goto(self) -> bool:
        if not self.target_pose:
            self.stop_base()
            return True

        tx, ty, t_yaw = self.target_pose
        x, y, yaw = self.get_pose()

        dx = tx - x
        dy = ty - y
        dist = math.hypot(dx, dy)
        angle_err = math.atan2(math.sin(t_yaw - yaw), math.cos(t_yaw - yaw))

        # ---- Arrival check ----
        if dist < DISTANCE_TOLERANCE and abs(angle_err) < ANGLE_TOLERANCE:
            self.stop_base()
            self._steps_since_progress = 0
            self._escape_steps = 0
            return True

        # ---- Sensor readings ----
        f_val = self.ds_front.getValue() if self.ds_front else 1000.0
        l_val = self.ds_left.getValue()  if self.ds_left  else 1000.0
        r_val = self.ds_right.getValue() if self.ds_right else 1000.0

        obstacle_front = f_val < 450.0
        obstacle_left  = l_val < 500.0
        obstacle_right = r_val < 500.0

        # ---- Escape manoeuvre: spin in place ----
        if self._escape_steps > 0:
            self.set_mecanum_velocity(0.0, 0.0, self._escape_dir * 0.55)
            self._escape_steps -= 1
            # Keep refreshing progress pos so we don't retrigger immediately
            self._last_progress_pos = (x, y)
            self._steps_since_progress = 0
            return False

        # ---- Progress tracking / stuck detection ----
        lx, ly = self._last_progress_pos
        if math.hypot(x - lx, y - ly) > 0.03:
            self._last_progress_pos = (x, y)
            self._steps_since_progress = 0
        else:
            self._steps_since_progress += 1

        if self._steps_since_progress >= self._STUCK_STEPS:
            # Pick escape direction away from the nearer obstacle
            if obstacle_left and not obstacle_right:
                self._escape_dir = -1.0   # spin CW (turn right)
            elif obstacle_right and not obstacle_left:
                self._escape_dir = 1.0    # spin CCW (turn left)
            elif angle_err > 0:
                self._escape_dir = 1.0
            else:
                self._escape_dir = -1.0
            self._escape_steps = self._ESCAPE_STEPS
            self._steps_since_progress = 0
            self.set_mecanum_velocity(0.0, 0.0, self._escape_dir * 0.55)
            return False

        # ---- Normal proportional navigation ----
        cos_y = math.cos(yaw)
        sin_y = math.sin(yaw)
        local_vx = cos_y * dx + sin_y * dy
        local_vy = -sin_y * dx + cos_y * dy

        # Taper gain near target to prevent overshoot oscillation
        gain = min(1.2, 1.2 * dist)
        vx = max(-0.28, min(0.28, gain * local_vx))
        vy = max(-0.25, min(0.25, gain * local_vy))
        omega = max(-0.6, min(0.6, 1.5 * angle_err))

        # ---- Reactive obstacle avoidance ----
        # Suppress omega during avoidance to prevent the rover spiraling into walls.
        # Prefer strafing over reversing to avoid wedging into corners.
        if obstacle_front:
            vx = -0.06
            vy = -0.18 if l_val < r_val else 0.18
            omega = 0.0
        elif obstacle_left:
            vy = max(vy - 0.15, -0.25)   # strafe right
            vx = min(vx, 0.10)           # slow forward component
        elif obstacle_right:
            vy = min(vy + 0.15, 0.25)    # strafe left
            vx = min(vx, 0.10)

        self.set_mecanum_velocity(vx, vy, omega)
        return False

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    def process_commands(self) -> None:
        raw = self.robot.getCustomData()
        if not raw:
            return
        try:
            cmd: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            return

        ts = float(cmd.get("ts", 0.0))
        if ts <= self.last_cmd_ts:
            return
        self.last_cmd_ts = ts

        action = cmd.get("action")
        if action == "stop":
            self.mode = "idle"
            self.target_pose = None
            self.waypoints.clear()
            self._escape_steps = 0
            self._steps_since_progress = 0
            self.stop_base()
        elif action == "goto":
            self.mode = "goto"
            self.waypoints = [(float(p[0]), float(p[1]), float(p[2])) for p in cmd["waypoints"]]
            self.current_wp_idx = 0
            self.target_pose = self.waypoints[0] if self.waypoints else None
            self._escape_steps = 0
            self._steps_since_progress = 0
            self._last_progress_pos = self.get_pose()[:2]
        elif action == "patrol":
            self.mode = "patrol"
            self.waypoints = [(float(p[0]), float(p[1]), float(p[2])) for p in cmd["waypoints"]]
            self.current_wp_idx = 0
            self.target_pose = self.waypoints[0] if self.waypoints else None
            self._escape_steps = 0
            self._steps_since_progress = 0
            self._last_progress_pos = self.get_pose()[:2]
        elif action == "velocity":
            self.mode = "manual"
            self.set_mecanum_velocity(
                float(cmd.get("vx", 0.0)),
                float(cmd.get("vy", 0.0)),
                float(cmd.get("omega", 0.0)),
            )
        elif action == "arm":
            self.set_arm_pose(str(cmd.get("pose", "reset")))
        elif action == "gripper":
            self.set_gripper(str(cmd.get("gripper_state", "release")))

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while self.robot.step(self.time_step) != -1:
            self.process_commands()

            if self.mode in ("goto", "patrol") and self.target_pose:
                reached = self.step_goto()
                if reached:
                    self.current_wp_idx += 1
                    if self.current_wp_idx < len(self.waypoints):
                        self.target_pose = self.waypoints[self.current_wp_idx]
                        self._last_progress_pos = self.get_pose()[:2]
                        self._steps_since_progress = 0
                    elif self.mode == "patrol" and self.waypoints:
                        self.current_wp_idx = 0
                        self.target_pose = self.waypoints[0]
                        self._last_progress_pos = self.get_pose()[:2]
                        self._steps_since_progress = 0
                    else:
                        self.mode = "idle"
                        self.target_pose = None


if __name__ == "__main__":
    BeaconRover().run()