from __future__ import annotations

from typing import Any

from ..util.matcher import match_device
from .hub_client import HubConnectionError, SmartHomeHubClient


class AccessService:
    """Service layer for smart doors, locks, garage doors, and driveway gates."""

    def __init__(self, hub_client: SmartHomeHubClient | None = None):
        self.hub_client = hub_client or SmartHomeHubClient()

    async def list_doors(self) -> list[dict[str, Any]]:
        return await self.hub_client.get_doors()

    async def find_door(self, identifier: str) -> dict[str, Any] | None:
        doors = await self.list_doors()
        return match_device(doors, identifier)

    async def set_door_open_state(
        self,
        identifier: str,
        open_state: str | None = None,
        position: int | None = None,
    ) -> dict[str, Any]:
        target = await self.find_door(identifier)
        if not target:
            return {
                "success": False,
                "error": f"Door or gate '{identifier}' was not found.",
            }

        try:
            updated = await self.hub_client.set_door_state(
                door_id=str(target["id"]),
                open_state=open_state,
                position=position,
            )
            return {
                "success": True,
                "message": f"Updated '{target['name']}' to {updated.get('state')} ({updated.get('position')}%).",
                **updated,
            }
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}

    async def set_door_lock(self, identifier: str, locked: bool) -> dict[str, Any]:
        target = await self.find_door(identifier)
        if not target:
            return {
                "success": False,
                "error": f"Door or lock '{identifier}' was not found.",
            }

        try:
            updated = await self.hub_client.set_door_state(
                door_id=str(target["id"]),
                locked=locked,
                open_state="closed" if locked else None,
            )
            action_str = "Locked" if locked else "Unlocked"
            return {
                "success": True,
                "message": f"{action_str} '{target['name']}'.",
                **updated,
            }
        except HubConnectionError as e:
            return {"success": False, "error": str(e)}