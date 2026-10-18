from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.rover_service import RoverService

DestinationNode = Literal[
    "foyer",
    "front_door",
    "master_junction",
    "bathroom_junction",
    "study_junction",
    "utility_room",
    "master_bedroom",
    "bathroom",
    "hallway",
    "study_bedroom",
    "kitchen_approach",
    "living_room",
    "kitchen",
    "dining_room",
]


def register_rover_tools(mcp: FastMCP, service: RoverService | None = None) -> None:
    """Register autonomous path-planning, waypoint navigation, and manipulation tools."""
    rover_service = service or RoverService()

    @mcp.tool()
    async def get_rover_telemetry() -> dict[str, Any]:
        """
        Retrieve real-time telemetry for the Beacon KUKA youBot, including current node,
        room, 3D world position, heading, arm pose, gripper state, and battery level.
        """
        return await rover_service.get_status()

    @mcp.tool()
    async def plan_rover_route(destination: DestinationNode) -> dict[str, Any]:
        """
        Compute the orthogonal turn-by-turn path from the rover's current position to `destination`.
        Returns the corner waypoints (x, y, yaw), total distance, and any closed doors (`blocking_doors`).
        Always call this first so you can unlock/open any blocking doors before navigating.
        """
        return await rover_service.plan_route(destination)

    @mcp.tool()
    async def navigate_rover_to_room(
        destination: DestinationNode | Literal["patrol"],
    ) -> dict[str, Any]:
        """
        Dispatch the rover along the orthogonal corner-by-corner route to `destination` (or 'patrol').
        Requires all doors along the route to be unlocked and open first.
        """
        return await rover_service.navigate_to_room(destination)

    @mcp.tool()
    async def navigate_rover_to_pose(x: float, y: float, yaw: float = 0.0) -> dict[str, Any]:
        """Send the rover directly to a 2D floor coordinate (x, y, yaw)."""
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
        """Move the KUKA youBot's 5-DOF robotic arm to a preset manipulation or inspection pose."""
        return await rover_service.control({"action": "arm", "arm_pose": arm_pose})

    @mcp.tool()
    async def set_rover_gripper(gripper_state: Literal["grip", "release"]) -> dict[str, Any]:
        """Actuate the KUKA youBot's parallel gripper fingers ('grip' to close, 'release' to open)."""
        return await rover_service.control({"action": "gripper", "gripper_state": gripper_state})

    @mcp.tool()
    async def drive_rover_velocity(vx: float = 0.0, vy: float = 0.0, omega: float = 0.0) -> dict[str, Any]:
        """Drive the Mecanum base directly with linear (vx, vy) and angular (omega) velocities."""
        return await rover_service.control({"action": "velocity", "vx": vx, "vy": vy, "omega": omega})

    @mcp.tool()
    async def stop_rover() -> dict[str, Any]:
        """Immediately halt all rover wheel motors and cancel active navigation."""
        return await rover_service.control({"action": "stop"})