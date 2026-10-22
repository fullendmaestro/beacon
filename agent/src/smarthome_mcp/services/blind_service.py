from __future__ import annotations

from typing import Any

from .hub_client import HubConnectionError, SmartHomeHubClient, strict_match, strict_not_found_error


class BlindService:
    """Service layer for motorized window roller blinds/shades (strict matching)."""

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
        target = strict_match(blinds, identifier)
        if not target:
            return strict_not_found_error(identifier, domain="blind")

        try:
            updated = await self.hub_client.set_blind_state(str(target["id"]), position)
            return {
                "success": True,
                "message": f"Set '{target['name']}' to {position}% open.",
                **updated,
            }
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}