from __future__ import annotations

from typing import Any

from ..util.matcher import match_device
from .hub_client import HubConnectionError, SmartHomeHubClient


class BlindService:
    """Service layer for motorized window roller blinds/shades."""

    def __init__(self, hub_client: SmartHomeHubClient | None = None):
        self.hub_client = hub_client or SmartHomeHubClient()

    async def list_blinds(self) -> list[dict[str, Any]]:
        return await self.hub_client.get_blinds()

    async def set_blind_position(self, identifier: str, position: int) -> dict[str, Any]:
        if not (0 <= position <= 100):
            return {
                "success": False,
                "error": f"Position must be between 0 (closed) and 100 (open), got {position}.",
            }

        blinds = await self.list_blinds()
        target = match_device(blinds, identifier)
        if not target:
            return {
                "success": False,
                "error": f"Window blind '{identifier}' was not found.",
            }

        try:
            updated = await self.hub_client.set_blind_state(str(target["id"]), position)
            return {
                "success": True,
                "message": f"Set '{target['name']}' to {position}% open.",
                **updated,
            }
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}