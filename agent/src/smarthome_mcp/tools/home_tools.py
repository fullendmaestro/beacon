from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.home_service import HomeService


def register_home_tools(
    mcp: FastMCP, home_service: HomeService | None = None
) -> None:
    service = home_service or HomeService()

    @mcp.tool()
    async def get_home_summary() -> dict[str, Any]:
        """
        Get an overall status summary of the smart home, including active lights count,
        open doors count, real-time total power consumption in Watts, and exterior time of day.
        """
        return await service.get_summary()

    @mcp.tool()
    async def get_sensors() -> list[dict[str, Any]]:
        """
        Get live telemetry from all motion/presence sensors (Front Porch, Living Room, Hallway, Driveway Gate)
        and the roof ambient daylight sensor.
        """
        return await service.list_sensors()

    @mcp.tool()
    async def get_cameras() -> list[dict[str, Any]]:
        """
        List all 6 interior and exterior security cameras and their online status.
        """
        return await service.list_cameras()

    @mcp.tool()
    async def trigger_scene(
        scene: Literal["morning", "away", "movie", "night"]
    ) -> dict[str, Any]:
        """
        Trigger a whole-home automation scene preset:
        - 'morning': Daylight sky, open all blinds, turn on interior lights.
        - 'movie': Sunset sky, close all blinds, dim living room lights to warm white, turn on Smart TV.
        - 'away': Turn off all lights, close all blinds, close and lock all doors and gates.
        - 'night': Night sky, close blinds, lock all doors/gates, turn on exterior bollard & porch lights.
        """
        return await service.trigger_scene(scene)

    @mcp.tool()
    async def set_environment(
        time_of_day: Literal["day", "sunset", "night"]
    ) -> dict[str, Any]:
        """
        Change the simulated exterior sun luminosity and time of day ('day', 'sunset', or 'night').
        """
        return await service.set_environment(time_of_day)

    @mcp.tool()
    async def get_humans() -> list[dict[str, Any]]:
        """
        Get live positions, rooms, and walking/standing status of all human occupants and visitors
        in the smart home (Alex the Resident and Sam the Visitor).
        """
        return await service.list_humans()

    @mcp.tool()
    async def get_household_objects() -> list[dict[str, Any]]:
        """
        Get the current room and 3D coordinates of all 10 physical household objects
        (cup, bottle, medicine_box, plate, tray, remote_control, keys, book, phone, glasses).
        """
        return await service.list_objects()

    @mcp.tool()
    async def get_ai_tasks() -> dict[str, Any]:
        """
        Get the list of Ambient & Human-in-the-Loop (HITL) AI Tasks and recent Webots sensor events.
        """
        return await service.list_tasks()

    @mcp.tool()
    async def propose_ai_task(
        title: str,
        description: str,
        category: Literal["security", "comfort", "errand", "energy", "safety"] = "errand",
        mode: Literal["ambient", "hitl"] = "hitl",
        room: str = "Living Room",
        proposed_actions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Create a new Ambient (auto-executed) or Human-in-the-Loop (HITL pending approval) AI Task
        in the Beacon AI Tasks sidebar panel.
        Optional `proposed_actions` is a list of action dicts executed upon approval (or immediately if ambient), e.g.:
        - {"type": "light", "label": "Turn on Foyer Light", "light_name": "Foyer Hallway Light", "power_state": "on", "brightness": 90}
        - {"type": "door", "label": "Unlock Front Door", "door_name": "Front Entrance Door", "open_state": "open", "locked": False}
        - {"type": "tiago_navigate", "label": "Send TIAGo to Kitchen", "room": "kitchen"}
        - {"type": "tiago_deliver", "label": "Deliver bottle", "item": "bottle", "from_location": "kitchen", "to_location": "living_room"}
        - {"type": "tiago_patrol", "label": "Security patrol", "rooms": ["living_room", "kitchen"]}
        """
        return await service.create_task(
            title=title,
            description=description,
            category=category,
            mode=mode,
            room=room,
            proposed_actions=proposed_actions,
        )

    @mcp.tool()
    async def approve_ai_task(task_id: str) -> dict[str, Any]:
        """
        Approve and execute a pending Human-in-the-Loop (HITL) AI Task by its task_id.
        """
        return await service.approve_task(task_id)