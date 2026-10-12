from __future__ import annotations

from typing import Any

from controller_service import SmartHomeController
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from models import LightStateUpdateRequest


def create_app(controller: SmartHomeController) -> FastAPI:
    """Create and configure the FastAPI app for the Smart Home Hub."""
    app = FastAPI(title="Beacon Simulated Smart Home Hub Controller")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/lights")
    def get_lights() -> list[dict[str, Any]]:
        return controller.list_lights()

    @app.get("/api/lights/{node_id}")
    def get_light_by_id(node_id: int) -> dict[str, Any]:
        return controller.get_light(node_id)

    @app.post("/api/lights/{node_id}/toggle")
    def toggle_light(node_id: int) -> dict[str, Any]:
        return controller.request_toggle(node_id)

    @app.post("/api/lights/{node_id}/state")
    def set_light_state_endpoint(node_id: int, req: LightStateUpdateRequest) -> dict[str, Any]:
        return controller.request_set_state(
            node_id=node_id,
            power_state=req.power_state,
            brightness=req.brightness,
            color=req.color,
        )

    @app.get("/api/cameras")
    def get_cameras() -> list[dict[str, Any]]:
        return controller.list_cameras()

    @app.get("/api/cameras/{name}/stream")
    def camera_stream(name: str) -> StreamingResponse:
        return StreamingResponse(
            controller.stream_camera(name),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    return app
