"""Unit and integration tests for the decoupled Beacon Core Hub architecture."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from beacon_hub.database.connection import DatabaseManager
from beacon_hub.database.models import DeviceProvisionRequest
from beacon_hub.main import create_hub_app


def test_sqlite_wal_and_strict_lookup(tmp_path: Path) -> None:
    db_file = tmp_path / "test_beacon.db"
    db = DatabaseManager(db_path=db_file)

    # Verify seeded rooms and devices exist
    rooms = db.list_rooms()
    assert len(rooms) >= 10
    lights = db.list_devices(domain="light")
    assert len(lights) == 18

    # Strict exact match by id or wbt_name works
    by_id = db.strict_lookup("dev_light_01", domain="light")
    assert by_id is not None
    assert by_id["wbt_name"] == "Kitchen Ceiling Light"

    by_name = db.strict_lookup("Kitchen Ceiling Light", domain="light")
    assert by_name is not None
    assert by_name["id"] == "dev_light_01"

    # Fuzzy / lowercase / substring queries MUST return None
    assert db.strict_lookup("kitchen ceiling light", domain="light") is None
    assert db.strict_lookup("living room light", domain="light") is None
    assert db.strict_lookup("tv", domain="appliance") is None


def test_dynamic_provisioning_and_nav_edge_linking(tmp_path: Path) -> None:
    db_file = tmp_path / "test_prov.db"
    db = DatabaseManager(db_path=db_file)

    # Provision a light without room_id -> should auto-infer 'kitchen' from [-1.5, -2.0]
    new_light = db.provision_device(
        DeviceProvisionRequest(
            wbt_name="Kitchen Island Pendant",
            domain="light",
            proto_type="CeilingLight",
            translation=[-1.5, -2.0, 2.4],
            initial_state={"power_state": "on", "brightness": 85, "color": "#fae6cc"},
        )
    )
    assert new_light["room_id"] == "kitchen"
    assert new_light["reported_state"]["brightness"] == 85

    # Provision a door right on the hallway -> kitchen_approach segment (x=-5.35, y=-5.5)
    new_door = db.provision_device(
        DeviceProvisionRequest(
            wbt_name="Living Spine Security Door",
            domain="door",
            proto_type="Door",
            translation=[-5.35, -5.5, 0.0],
            initial_state={"position": 0, "locked": True},
        )
    )
    route = db.compute_route(-3.10, -7.62, "living_room")
    blocking_names = [d["wbt_name"] for d in route["blocking_doors"]]
    assert "Living Spine Security Door" in blocking_names

    # Remove dynamic device
    removed = db.remove_device(new_light["id"])
    assert removed is not None
    assert db.strict_lookup(new_light["id"]) is None


def test_hub_api_and_websockets() -> None:
    app = create_hub_app()
    with TestClient(app) as client:
        # 1. Floorplan endpoint
        fp_res = client.get("/api/v2/floorplan")
        assert fp_res.status_code == 200
        fp = fp_res.json()
        assert "rooms" in fp
        assert "devices" in fp
        assert "nav_nodes" in fp
        assert "nav_edges" in fp

        # 2. Strict 404 on fuzzy device identifier
        bad_res = client.post(
            "/api/lights/living%20room%20light/state",
            json={"power_state": "on"},
        )
        assert bad_res.status_code == 404
        assert bad_res.json()["error_code"] == "DEVICE_NOT_FOUND_STRICT"

        # 3. Exact wbt_name command succeeds
        ok_res = client.post(
            "/api/lights/Kitchen%20Ceiling%20Light/state",
            json={"power_state": "on", "brightness": 55},
        )
        assert ok_res.status_code == 200
        assert ok_res.json()["brightness"] == 55

        # 4. Route planner endpoint
        route_res = client.post(
            "/api/v2/robots/tiago/route",
            json={"destination": "kitchen"},
        )
        assert route_res.status_code == 200
        r_data = route_res.json()
        assert r_data["destination"] == "kitchen"
        assert len(r_data["waypoints"]) >= 2

        # 5. WebSocket /ws/events snapshot
        with client.websocket_connect("/ws/events") as ws:
            msg = ws.receive_json()
            assert msg["topic"] == "hub.snapshot"
            assert "devices" in msg["payload"]
