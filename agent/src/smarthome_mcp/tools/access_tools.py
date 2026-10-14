from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.access_service import AccessService


def register_access_tools(
    mcp: FastMCP, access_service: AccessService | None = None
) -> None:
    service = access_service or AccessService()

    @mcp.tool()
    async def get_doors() -> list[dict[str, Any]]:
        """
        List all smart doors, locks, the overhead garage door, and the sliding driveway gate.

        Returns:
            List of barrier objects with id, name, type, state ('Open'|'Closed'), position (0-100), and locked boolean.
        """
        return await service.list_doors()

    @mcp.tool()
    async def set_door_state(
        device_id: str,
        open_state: Literal["open", "closed"] | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        """
        Open, close, or partially position a door, garage door, or driveway gate.

        Args:
            device_id: The ID or name of the door/barrier (e.g. 'Front Entrance Door', 'Garage Door', 'Driveway Gate').
            open_state: Either 'open' or 'closed'.
            position: Optional opening percentage from 0 (closed) to 100 (fully open).
        """
        return await service.set_door_open_state(device_id, open_state=open_state, position=position)

    @mcp.tool()
    async def set_door_lock(device_id: str, locked: bool) -> dict[str, Any]:
        """
        Lock or unlock a smart door, garage door, or driveway gate. Locking automatically closes the barrier.

        Args:
            device_id: The ID or name of the door/barrier (e.g. 'Front Entrance Door', 'Driveway Gate').
            locked: True to lock, False to unlock.
        """
        return await service.set_door_lock(device_id, locked=locked)