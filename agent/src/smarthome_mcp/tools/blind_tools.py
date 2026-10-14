from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..services.blind_service import BlindService


def register_blind_tools(
    mcp: FastMCP, blind_service: BlindService | None = None
) -> None:
    service = blind_service or BlindService()

    @mcp.tool()
    async def get_blinds() -> list[dict[str, Any]]:
        """
        List all motorized window blinds/shades across the home and their current open percentage (0-100%).
        """
        return await service.list_blinds()

    @mcp.tool()
    async def set_blind_position(device_id: str, position: int) -> dict[str, Any]:
        """
        Raise or lower a motorized window blind/shade.

        Args:
            device_id: The ID, room, or name of the blind (e.g. 'Living Room West Blind', 'Master Bedroom Blind').
            position: Percentage from 0 (completely closed/down) to 100 (completely open/raised).
        """
        return await service.set_blind_position(device_id, position)