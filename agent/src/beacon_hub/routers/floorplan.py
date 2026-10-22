"""2D Floorplan topology endpoint (/api/v2/floorplan)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..broker import get_broker
from ..database.connection import get_db

router = APIRouter(prefix="/api/v2", tags=["floorplan"])


@router.get("/floorplan")
async def get_floorplan() -> dict[str, Any]:
    db = get_db()
    broker = get_broker()
    return {
        "sim_mode": broker.sim_mode,
        "rooms": db.list_rooms(),
        "devices": db.list_devices(),
        "nav_nodes": db.list_nav_nodes(),
        "nav_edges": db.list_nav_edges(),
        "robot": db.get_robot("tiago"),
        "environment": db.get_environment(),
    }
