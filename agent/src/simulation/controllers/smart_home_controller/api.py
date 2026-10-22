from __future__ import annotations

from typing import Any

from controller_service import SmartHomeController
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from models import (
    ApplianceUpdateRequest,
    BlindUpdateRequest,
    ClimateUpdateRequest,
    DoorUpdateRequest,
    EnvironmentUpdateRequest,
    LightStateUpdateRequest,
    SceneTriggerRequest,
)


def create_app(controller: SmartHomeController) -> FastAPI:
    """Create and configure the FastAPI app for the Smart Home Hub."""
    app = FastAPI(title="Beacon Simulated Smart Home Hub Controller", version="2.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Home Overview & Automation Scenes ---

    @app.get("/api/home/summary")
    def get_home_summary() -> dict[str, Any]:
        return controller.get_summary()

    @app.post("/api/home/scene")
    def trigger_scene(req: SceneTriggerRequest) -> dict[str, Any]:
        return controller.request_scene(req.scene)

    @app.post("/api/home/environment")
    def update_environment(req: EnvironmentUpdateRequest) -> dict[str, Any]:
        return controller.request_environment_update(req.time_of_day)

    # --- Smart Lights ---

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

    # --- Smart Doors, Garage Door & Driveway Gate ---

    @app.get("/api/doors")
    def get_doors() -> list[dict[str, Any]]:
        return controller.list_doors()

    @app.post("/api/doors/{door_id}/state")
    def update_door_state(door_id: str, req: DoorUpdateRequest) -> dict[str, Any]:
        return controller.request_door_update(
            door_id=door_id,
            open_state=req.open_state,
            locked=req.locked,
            position=req.position,
        )

    # --- Motorized Window Blinds ---

    @app.get("/api/blinds")
    def get_blinds() -> list[dict[str, Any]]:
        return controller.list_blinds()

    @app.post("/api/blinds/{blind_id}/state")
    def update_blind_state(blind_id: str, req: BlindUpdateRequest) -> dict[str, Any]:
        return controller.request_blind_update(blind_id=blind_id, position=req.position)

    # --- HVAC / Climate Zones ---

    @app.get("/api/climate")
    def get_climate_zones() -> list[dict[str, Any]]:
        return controller.list_climate()

    @app.post("/api/climate/{zone_id}/state")
    def update_climate_zone(zone_id: int, req: ClimateUpdateRequest) -> dict[str, Any]:
        return controller.request_climate_update(
            zone_id=zone_id,
            power_state=req.power_state,
            target_temp=req.target_temp,
            mode=req.mode,
        )

    # --- Smart Appliances & Wall Plugs ---

    @app.get("/api/appliances")
    def get_appliances() -> list[dict[str, Any]]:
        return controller.list_appliances()

    @app.post("/api/appliances/{appliance_id}/state")
    def update_appliance_state(appliance_id: str, req: ApplianceUpdateRequest) -> dict[str, Any]:
        return controller.request_appliance_update(
            appliance_id=appliance_id,
            power_state=req.power_state,
            mode=req.mode,
        )

    # --- Motion & Daylight Sensors ---

    @app.get("/api/sensors")
    def get_sensors() -> list[dict[str, Any]]:
        return controller.list_sensors()

    # --- Security Cameras ---

    @app.get("/api/cameras")
    def get_cameras() -> list[dict[str, Any]]:
        return controller.list_cameras()

    @app.get("/api/cameras/{name}/stream")
    def camera_stream(name: str) -> StreamingResponse:
        return StreamingResponse(
            controller.stream_camera(name),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    # --- Beacon Home Robots (PAL Robotics TIAGo) ---

    @app.get("/api/robots")
    def get_robots() -> list[dict[str, Any]]:
        return controller.list_robots()

    @app.post("/api/robots")
    def control_robot_endpoint(req: dict[str, Any]) -> dict[str, Any]:
        return controller.request_robot_action(req)

    return app