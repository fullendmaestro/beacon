# agent/src/simulation/controllers/pedestrian/pedestrian.py
"""Articulated Webots Pedestrian controller supporting walk-once, patrol loop, and standing modes."""

from __future__ import annotations

import math
import optparse

try:
    from controller import Supervisor  # type: ignore[import-not-found]
except ImportError:
    Supervisor = object  # type: ignore[assignment,misc]


class Pedestrian(Supervisor):
    """Control a Webots Pedestrian PROTO with realistic 13-joint gait interpolation."""

    def __init__(self) -> None:
        self.BODY_PARTS_NUMBER = 13
        self.WALK_SEQUENCES_NUMBER = 8
        self.ROOT_HEIGHT = 1.27
        self.CYCLE_TO_DISTANCE_RATIO = 0.22
        self.speed = 1.0
        self.current_height_offset = 0.0
        self.joints_position_field = []
        self.joint_names = [
            "leftArmAngle", "leftLowerArmAngle", "leftHandAngle",
            "rightArmAngle", "rightLowerArmAngle", "rightHandAngle",
            "leftLegAngle", "leftLowerLegAngle", "leftFootAngle",
            "rightLegAngle", "rightLowerLegAngle", "rightFootAngle",
            "headAngle",
        ]
        self.height_offsets = [-0.02, 0.04, 0.08, -0.03, -0.02, 0.04, 0.08, -0.03]
        self.angles = [
            [-0.52, -0.15, 0.58, 0.7, 0.52, 0.17, -0.36, -0.74],   # left arm
            [0.0, -0.16, -0.7, -0.38, -0.47, -0.3, -0.58, -0.21],  # left lower arm
            [0.12, 0.0, 0.12, 0.2, 0.0, -0.17, -0.25, 0.0],        # left hand
            [0.52, 0.17, -0.36, -0.74, -0.52, -0.15, 0.58, 0.7],   # right arm
            [-0.47, -0.3, -0.58, -0.21, 0.0, -0.16, -0.7, -0.38],  # right lower arm
            [0.0, -0.17, -0.25, 0.0, 0.12, 0.0, 0.12, 0.2],        # right hand
            [-0.55, -0.85, -1.14, -0.7, -0.56, 0.12, 0.24, 0.4],   # left leg
            [1.4, 1.58, 1.71, 0.49, 0.84, 0.0, 0.14, 0.26],        # left lower leg
            [0.07, 0.07, -0.07, -0.36, 0.0, 0.0, 0.32, -0.07],     # left foot
            [-0.56, 0.12, 0.24, 0.4, -0.55, -0.85, -1.14, -0.7],   # right leg
            [0.84, 0.0, 0.14, 0.26, 1.4, 1.58, 1.71, 0.49],        # right lower leg
            [0.0, 0.0, 0.42, -0.07, 0.07, 0.07, -0.07, -0.36],     # right foot
            [0.18, 0.09, 0.0, 0.09, 0.18, 0.09, 0.0, 0.09],        # head
        ]
        super().__init__()

    def _set_neutral_stand(self, sim_time: float) -> None:
        """Subtle breathing/head-look idle posture when standing."""
        head_sway = 0.08 * math.sin(sim_time * 1.4)
        for i in range(self.BODY_PARTS_NUMBER):
            field = self.joints_position_field[i]
            if not field:
                continue
            if i == 12:  # headAngle
                field.setSFFloat(head_sway)
            else:
                field.setSFFloat(0.0)

    def run(self) -> None:
        opt_parser = optparse.OptionParser()
        opt_parser.add_option(
            "--trajectory",
            default="",
            help="Trajectory in the format [x1 y1, x2 y2, ...]",
        )
        opt_parser.add_option(
            "--speed",
            type=float,
            default=1.0,
            help="Walking speed in [m/s]",
        )
        opt_parser.add_option(
            "--mode",
            default="loop",
            help="Motion mode: 'walk' (stop at final waypoint), 'loop' (continuous patrol), or 'stand'",
        )
        opt_parser.add_option("--step", type=int, help="Time step")
        options, _ = opt_parser.parse_args()

        self.speed = max(0.2, float(options.speed or 1.0))
        self.time_step = int(options.step) if options.step and options.step > 0 else int(self.getBasicTimeStep())
        mode = str(options.mode or "loop").strip().lower()

        self.root_node_ref = self.getSelf()
        self.root_translation_field = self.root_node_ref.getField("translation")
        self.root_rotation_field = self.root_node_ref.getField("rotation")
        for i in range(self.BODY_PARTS_NUMBER):
            self.joints_position_field.append(self.root_node_ref.getField(self.joint_names[i]))

        raw_points = [p.strip() for p in str(options.trajectory).split(",") if p.strip()]
        self.waypoints: list[list[float]] = []
        for pt in raw_points:
            parts = pt.split()
            if len(parts) >= 2:
                self.waypoints.append([float(parts[0]), float(parts[1])])

        # Standing mode or single waypoint
        if mode == "stand" or len(self.waypoints) < 2:
            if len(self.waypoints) == 1:
                pos = self.waypoints[0]
                self.root_translation_field.setSFVec3f([pos[0], pos[1], self.ROOT_HEIGHT])
            while self.step(self.time_step) != -1:
                self._set_neutral_stand(self.getTime())
            return

        # For 'walk' mode (walk from start to target and stop), compute open segments;
        # for 'loop' mode, include closing segment back to waypoint 0.
        is_loop = mode == "loop"
        num_segments = len(self.waypoints) if is_loop else (len(self.waypoints) - 1)
        self.waypoints_distance: list[float] = []
        for i in range(num_segments):
            nxt = (i + 1) % len(self.waypoints)
            dx = self.waypoints[nxt][0] - self.waypoints[i][0]
            dy = self.waypoints[nxt][1] - self.waypoints[i][1]
            seg_len = max(0.001, math.hypot(dx, dy))
            if i == 0:
                self.waypoints_distance.append(seg_len)
            else:
                self.waypoints_distance.append(self.waypoints_distance[i - 1] + seg_len)

        total_path_length = self.waypoints_distance[-1]

        while self.step(self.time_step) != -1:
            sim_time = self.getTime()
            distance = sim_time * self.speed

            if not is_loop and distance >= total_path_length:
                # Reached destination: stand in place at final waypoint
                final_wp = self.waypoints[-1]
                prev_wp = self.waypoints[-2]
                final_angle = math.atan2(final_wp[1] - prev_wp[1], final_wp[0] - prev_wp[0])
                self.root_translation_field.setSFVec3f([final_wp[0], final_wp[1], self.ROOT_HEIGHT])
                self.root_rotation_field.setSFRotation([0.0, 0.0, 1.0, final_angle])
                self._set_neutral_stand(sim_time)
                continue

            current_sequence = int(((sim_time * self.speed) / self.CYCLE_TO_DISTANCE_RATIO) % self.WALK_SEQUENCES_NUMBER)
            ratio = (sim_time * self.speed) / self.CYCLE_TO_DISTANCE_RATIO - int(
                (sim_time * self.speed) / self.CYCLE_TO_DISTANCE_RATIO
            )

            for i in range(self.BODY_PARTS_NUMBER):
                current_angle = (
                    self.angles[i][current_sequence] * (1.0 - ratio)
                    + self.angles[i][(current_sequence + 1) % self.WALK_SEQUENCES_NUMBER] * ratio
                )
                if self.joints_position_field[i]:
                    self.joints_position_field[i].setSFFloat(current_angle)

            self.current_height_offset = (
                self.height_offsets[current_sequence] * (1.0 - ratio)
                + self.height_offsets[(current_sequence + 1) % self.WALK_SEQUENCES_NUMBER] * ratio
            )

            relative_distance = (
                distance - int(distance / total_path_length) * total_path_length
                if is_loop
                else min(distance, total_path_length)
            )

            seg_idx = 0
            for i in range(num_segments):
                if self.waypoints_distance[i] > relative_distance:
                    seg_idx = i
                    break

            prev_cum = 0.0 if seg_idx == 0 else self.waypoints_distance[seg_idx - 1]
            seg_len = max(0.001, self.waypoints_distance[seg_idx] - prev_cum)
            distance_ratio = (relative_distance - prev_cum) / seg_len

            p0 = self.waypoints[seg_idx]
            p1 = self.waypoints[(seg_idx + 1) % len(self.waypoints)]
            x = distance_ratio * p1[0] + (1.0 - distance_ratio) * p0[0]
            y = distance_ratio * p1[1] + (1.0 - distance_ratio) * p0[1]
            angle = math.atan2(p1[1] - p0[1], p1[0] - p0[0])

            self.root_translation_field.setSFVec3f([x, y, self.ROOT_HEIGHT + self.current_height_offset])
            self.root_rotation_field.setSFRotation([0.0, 0.0, 1.0, angle])


if __name__ == "__main__":
    Pedestrian().run()
