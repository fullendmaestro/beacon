# agent/src/simulation/controllers/beacon_rover_controller/beacon_rover_controller.py
from __future__ import annotations

import json
import math
from typing import Any

from controller import Compass, GPS, Motor, Robot

# KUKA youBot physical geometry (from Cyberbotics base.c)
WHEEL_RADIUS = 0.05
LX = 0.228
LY = 0.158
MAX_WHEEL_SPEED = 4.0

# Straight-line & turn-in-place control parameters
FORWARD_SPEED = 0.28       # Forward walking speed [m/s]
TURN_SPEED = 0.80          # In-place rotation speed [rad/s]
DIST_TOLERANCE = 0.05      # 5 cm arrival tolerance at each corner
ANGLE_TOLERANCE = 0.025    # ~1.4 deg heading alignment tolerance

ARM_POSES: dict[str, list[float]] = {
    "reset": [0.0, 1.57, -2.635, 1.78, 0.0],
    "front_floor": [0.0, -0.97, -1.55, -0.61, 0.0],
    "front_box": [0.0, 0.0, -0.77, -1.21, 0.0],
    "front_plate": [0.0, -0.62, -0.98, -1.53, 0.0],
    "back_plate_high": [0.0, 0.678, 0.682, 1.74, 0.0],
    "back_plate_low": [0.0, 0.92, 0.42, 1.78, 0.0],
    "inspect_high": [0.0, 0.2, -0.3, -0.8, 0.0],
}


def normalize_angle(angle: float) -> float:
    """Wrap angle to [-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))


class BeaconRover:
    def __init__(self) -> None:
        self.robot = Robot()
        self.time_step = int(self.robot.getBasicTimeStep())
        self.last_cmd_ts: float = 0.0

        # 4 Mecanum Wheels (wheel1: FL, wheel2: FR, wheel3: RL, wheel4: RR)
        self.wheels: list[Motor] = []
        for i in range(1, 5):
            motor = self.robot.getDevice(f"wheel{i}")
            motor.setPosition(float("inf"))
            motor.setVelocity(0.0)
            self.wheels.append(motor)

        # 5-DOF Arm
        self.arm_motors: list[Motor] = []
        for i in range(1, 6):
            motor = self.robot.getDevice(f"arm{i}")
            if motor:
                motor.setVelocity(0.8)
            self.arm_motors.append(motor)

        # Parallel Gripper
        self.finger_left: Motor | None = self.robot.getDevice("finger::left")
        self.finger_right: Motor | None = self.robot.getDevice("finger::right")
        if self.finger_left:
            self.finger_left.setVelocity(0.03)
        if self.finger_right:
            self.finger_right.setVelocity(0.03)

        # GPS & Compass
        self.gps: GPS = self.robot.getDevice("gps")
        if self.gps:
            self.gps.enable(self.time_step)

        self.compass: Compass = self.robot.getDevice("compass")
        if self.compass:
            self.compass.enable(self.time_step)

        # Navigation state
        self.mode: str = "idle"
        self.nav_phase: str = "turn"  # "turn" -> "drive" -> "turn_final"
        self.waypoints: list[tuple[float, float, float]] = []
        self.current_wp_idx: int = 0

        self.set_arm_pose("reset")
        self.set_gripper("release")

    # ------------------------------------------------------------------
    # Low-level Wheel Kinematics (Matches Cyberbotics base_turn_left / base_forwards)
    # ------------------------------------------------------------------

    def set_velocity(self, vx: float, vy: float, omega: float) -> None:
        """
        Drive Mecanum wheels:
          vx > 0: all wheels roll forward (+SPEED)
          omega > 0 (CCW / turn left): left wheels (1, 3) roll backward (-), right wheels (2, 4) roll forward (+)
        """
        geom = LX + LY
        speeds = [
            (1.0 / WHEEL_RADIUS) * (vx - vy - geom * omega),  # wheel1 (Front-Left)
            (1.0 / WHEEL_RADIUS) * (vx + vy + geom * omega),  # wheel2 (Front-Right)
            (1.0 / WHEEL_RADIUS) * (vx + vy - geom * omega),  # wheel3 (Rear-Left)
            (1.0 / WHEEL_RADIUS) * (vx - vy + geom * omega),  # wheel4 (Rear-Right)
        ]
        for i in range(4):
            self.wheels[i].setVelocity(max(-MAX_WHEEL_SPEED, min(MAX_WHEEL_SPEED, speeds[i])))

    def stop_base(self) -> None:
        for wheel in self.wheels:
            wheel.setVelocity(0.0)

    # ------------------------------------------------------------------
    # Arm & Gripper
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
    # Exact ENU Pose Estimation (Matches Cyberbotics base.c vector2_angle)
    # ------------------------------------------------------------------

    def get_pose(self) -> tuple[float, float, float]:
        if not self.gps or not self.compass:
            return 0.0, 0.0, 0.0
        pos = self.gps.getValues()
        comp = self.compass.getValues()
        # In Webots ENU, comp = [cos(yaw), -sin(yaw), 0]
        # True world yaw in (-pi, pi] (0 = East/+X, +pi/2 = North/+Y, pi = West/-X, -pi/2 = South/-Y):
        yaw = math.atan2(-comp[1], comp[0])
        return pos[0], pos[1], yaw

    # ------------------------------------------------------------------
    # Step-by-Step Orthogonal Navigation: Face Direction -> Walk Straight
    # ------------------------------------------------------------------

    def step_waypoint(self) -> bool:
        tx, ty, final_yaw = self.waypoints[self.current_wp_idx]
        x, y, yaw = self.get_pose()

        dx = tx - x
        dy = ty - y
        dist = math.hypot(dx, dy)
        is_last_wp = (self.current_wp_idx == len(self.waypoints) - 1) and (self.mode != "patrol")

        # 1. Rotate in place to face the waypoint
        if self.nav_phase == "turn":
            if dist <= DIST_TOLERANCE:
                self.stop_base()
                if is_last_wp:
                    self.nav_phase = "turn_final"
                    return False
                return True

            target_heading = math.atan2(dy, dx)
            err = normalize_angle(target_heading - yaw)
            if abs(err) <= ANGLE_TOLERANCE:
                self.stop_base()
                self.nav_phase = "drive"
                return False

            omega = max(-TURN_SPEED, min(TURN_SPEED, 2.0 * err))
            if abs(omega) < 0.15:
                omega = math.copysign(0.15, err)
            self.set_velocity(0.0, 0.0, omega)
            return False

        # 2. Walk straight forward along the line toward the waypoint
        if self.nav_phase == "drive":
            if dist <= DIST_TOLERANCE:
                self.stop_base()
                if is_last_wp:
                    self.nav_phase = "turn_final"
                    return False
                return True

            target_heading = math.atan2(dy, dx)
            err = normalize_angle(target_heading - yaw)

            # If knocked off heading by > 12 degrees, pause and re-align in place
            if abs(err) > 0.21:
                self.stop_base()
                self.nav_phase = "turn"
                return False

            vx = min(FORWARD_SPEED, max(0.08, 1.4 * dist))
            omega = max(-0.4, min(0.4, 1.5 * err))
            self.set_velocity(vx, 0.0, omega)
            return False

        # 3. Rotate in place at final destination to desired room orientation
        if self.nav_phase == "turn_final":
            err = normalize_angle(final_yaw - yaw)
            if abs(err) <= ANGLE_TOLERANCE:
                self.stop_base()
                return True

            omega = max(-TURN_SPEED, min(TURN_SPEED, 2.0 * err))
            if abs(omega) < 0.15:
                omega = math.copysign(0.15, err)
            self.set_velocity(0.0, 0.0, omega)
            return False

        return True

    # ------------------------------------------------------------------
    # Command Processing
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
            self.waypoints.clear()
            self.stop_base()
        elif action in ("goto", "patrol"):
            self.mode = action
            raw_wps = [(float(p[0]), float(p[1]), float(p[2])) for p in cmd.get("waypoints", [])]
            rx, ry, _ = self.get_pose()
            if len(raw_wps) > 1 and math.hypot(raw_wps[0][0] - rx, raw_wps[0][1] - ry) < 0.10:
                raw_wps = raw_wps[1:]
            self.waypoints = raw_wps
            self.current_wp_idx = 0
            self.nav_phase = "turn"
        elif action == "velocity":
            self.mode = "manual"
            self.set_velocity(
                float(cmd.get("vx", 0.0)),
                float(cmd.get("vy", 0.0)),
                float(cmd.get("omega", 0.0)),
            )
        elif action == "arm":
            self.set_arm_pose(str(cmd.get("pose", "reset")))
        elif action == "gripper":
            self.set_gripper(str(cmd.get("gripper_state", "release")))

    def run(self) -> None:
        while self.robot.step(self.time_step) != -1:
            self.process_commands()

            if self.mode in ("goto", "patrol") and self.waypoints:
                if self.step_waypoint():
                    self.current_wp_idx += 1
                    self.nav_phase = "turn"
                    if self.current_wp_idx >= len(self.waypoints):
                        if self.mode == "patrol":
                            self.current_wp_idx = 0
                        else:
                            self.mode = "idle"
                            self.waypoints.clear()
                            self.stop_base()


if __name__ == "__main__":
    BeaconRover().run()