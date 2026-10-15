from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.rover_service import RoverService


def register_rover_tools(mcp: FastMCP, service: RoverService | None = None) -> None:
    """Register autonomous navigation, manipulation, and teleop tools on the Rover FastMCP server."""
    rover_service = service or RoverService()

    @mcp.tool()
    async def get_rover_telemetry() -> dict[str, Any]:
        """
        Retrieve real-time telemetry for the Beacon KUKA youBot autonomous mobile robot,
        including current room, 3D world position, heading, arm pose, gripper state, and battery level.
        """
        return await rover_service.get_status()

    @mcp.tool()
    async def navigate_rover_to_room(
        destination: Literal[
            "foyer",
            "living_room",
            "dining_room",
            "kitchen",
            "hallway",
            "master_bedroom",
            "study_bedroom",
            "patrol",
        ],
    ) -> dict[str, Any]:
        """
        Dispatch the autonomous mobile robot to a target room or start an estate patrol loop.
        Automatically unlocks and opens any closed smart doors along the route.
        """
        return await rover_service.navigate_to_room(destination)

    @mcp.tool()
    async def navigate_rover_to_pose(x: float, y: float, yaw: float = 0.0) -> dict[str, Any]:
        """
        Send the autonomous mobile robot to exact Webots 2D floor coordinates (x, y) and heading (yaw in radians).
        """
        return await rover_service.navigate_to_coordinates(x, y, yaw)

    @mcp.tool()
    async def set_rover_arm_pose(
        arm_pose: Literal[
            "reset",
            "front_floor",
            "front_box",
            "front_plate",
            "back_plate_high",
            "back_plate_low",
            "inspect_high",
        ],
    ) -> dict[str, Any]:
        """
        Move the KUKA youBot's 5-DOF robotic arm to a preset manipulation or inspection pose.
        """
        return await rover_service.control({"action": "arm", "arm_pose": arm_pose})

    @mcp.tool()
    async def set_rover_gripper(gripper_state: Literal["grip", "release"]) -> dict[str, Any]:
        """
        Actuate the KUKA youBot's parallel gripper fingers ('grip' to close, 'release' to open).
        """
        return await rover_service.control({"action": "gripper", "gripper_state": gripper_state})

    @mcp.tool()
    async def drive_rover_velocity(vx: float = 0.0, vy: float = 0.0, omega: float = 0.0) -> dict[str, Any]:
        """
        Drive the omnidirectional Mecanum base directly with linear velocities vx (forward, -0.3 to 0.3 m/s),
        vy (strafe left, -0.3 to 0.3 m/s), and angular velocity omega (CCW rotation, -1.0 to 1.0 rad/s).
        """
        return await rover_service.control({"action": "velocity", "vx": vx, "vy": vy, "omega": omega})

    @mcp.tool()
    async def stop_rover() -> dict[str, Any]:
        """
        Immediately halt all rover wheel motors and cancel active waypoint or patrol navigation.
        """
        return await rover_service.control({"action": "stop"})