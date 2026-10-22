"""Standalone Beacon Core Hub Service (Port 8000) — FastAPI + Event Broker + SQLite WAL + Virtual Physics."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .broker import get_broker
from .database.connection import get_db
from .fallback.virtual_physics_worker import VirtualPhysicsWorker
from .routers import (
    devices_router,
    floorplan_router,
    provisioning_router,
    ws_router,
)

_fallback_worker: VirtualPhysicsWorker | None = None


def get_fallback_worker() -> VirtualPhysicsWorker:
    global _fallback_worker
    if _fallback_worker is None:
        _fallback_worker = VirtualPhysicsWorker(db=get_db(), broker=get_broker())
    return _fallback_worker


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    worker = get_fallback_worker()
    worker.start()
    try:
        yield
    finally:
        await worker.stop()


def create_hub_app() -> FastAPI:
    app = FastAPI(
        title="Beacon Core Hub Service",
        description="Decoupled IoT & Robotics Digital Twin Control Plane with SQLite WAL & Async Event Broker",
        version="2.2.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(provisioning_router)
    app.include_router(floorplan_router)
    app.include_router(devices_router)
    app.include_router(ws_router)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        broker = get_broker()
        return {
            "status": "ok",
            "sim_mode": broker.sim_mode,
            "webots_attached": broker.is_webots_attached,
        }

    return app


app = create_hub_app()


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
