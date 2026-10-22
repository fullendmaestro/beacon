"""FastAPI routers for Beacon Core Hub."""

from .devices import router as devices_router
from .floorplan import router as floorplan_router
from .provisioning import router as provisioning_router
from .ws import router as ws_router

__all__ = [
    "devices_router",
    "floorplan_router",
    "provisioning_router",
    "ws_router",
]
