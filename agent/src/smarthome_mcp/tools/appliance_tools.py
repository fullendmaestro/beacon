from __future__ import annotations

from typing import Any, Literal

from fastmcp import FastMCP

from ..services.appliance_service import ApplianceService


def register_appliance_tools(
    mcp: FastMCP, appliance_service: ApplianceService | None = None
) -> None:
    service = appliance_service or ApplianceService()

    @mcp.tool()
    async def get_appliances() -> list[dict[str, Any]]:
        """
        List all smart appliances (Smart TV, Fridge, Oven, Microwave, Cooktop, Washer, Patio Grill)
        and Smart Wall Plugs, including their operating mode and live power draw in Watts.
        """
        return await service.list_appliances()

    @mcp.tool()
    async def set_appliance_state(
        appliance_id: str,
        power_state: Literal["on", "off"] | None = None,
        mode: str | None = None,
    ) -> dict[str, Any]:
        """
        Turn a smart appliance or wall plug on/off or change its operating mode.

        Args:
            appliance_id: Name or ID of the appliance (e.g. 'Living Room Smart TV', 'Smart Oven', 'Smart Washer').
            power_state: 'on' or 'off'.
            mode: Operating program (e.g. 'Cinema 4K HDR', 'Bake 180C', 'Eco Cooling (3C)', 'Quick Wash 20m').
        """
        return await service.update_appliance(
            identifier=appliance_id,
            power_state=power_state,
            mode=mode,
        )