from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

CTRL_DIR = Path(__file__).resolve().parents[2] / "src" / "simulation" / "controllers" / "smart_home_controller"
if str(CTRL_DIR) not in sys.path:
    sys.path.insert(0, str(CTRL_DIR))

from api import create_app  # noqa: E402
from controller_service import SmartHomeController  # noqa: E402
from standalone_supervisor import StandaloneSupervisor  # noqa: E402


def _make_controller() -> SmartHomeController:
    ctrl = SmartHomeController(supervisor=StandaloneSupervisor())
    ctrl.init_devices()
    return ctrl


def test_standalone_hub_summary_and_lights() -> None:
    ctrl = _make_controller()
    app = create_app(ctrl)
    client = TestClient(app)

    summary = client.get("/api/home/summary").json()
    assert summary["total_lights"] == 18
    assert summary["total_doors"] == 9
    assert summary["blinds_count"] == 4
    assert summary["climate_zones"] == 6
    assert summary["cameras_online"] == 7
    assert summary["rover"]["status"] == "Docked"


def test_rover_plan_route_and_door_blocking() -> None:
    ctrl = _make_controller()

    # Route from foyer to living_room has no doors on path
    plan_lr = ctrl.rover.plan_route("living_room", ctrl.access)
    assert plan_lr["ready_to_traverse"] is True
    assert plan_lr["blocking_doors"] == []
    assert plan_lr["corner_nodes"] == ["foyer", "hallway", "living_room"]

    # Route from foyer to kitchen is blocked by closed Kitchen Passage Door
    plan_kitchen = ctrl.rover.plan_route("kitchen", ctrl.access)
    assert plan_kitchen["ready_to_traverse"] is False
    assert len(plan_kitchen["blocking_doors"]) == 1
    door_id = plan_kitchen["blocking_doors"][0]["door_id"]

    # Attempting to navigate while door is closed returns blocked_by_door
    nav_blocked = ctrl.rover.execute_cmd(
        {"sub_action": "navigate", "destination": "kitchen"},
        ctrl.access,
    )
    assert nav_blocked["status"] == "blocked_by_door"

    # Open the Kitchen Passage Door and re-dispatch
    ctrl.access.execute_door_cmd({"door_id": door_id, "open_state": "open", "locked": False})
    nav_ok = ctrl.rover.execute_cmd(
        {"sub_action": "navigate", "destination": "kitchen"},
        ctrl.access,
    )
    assert nav_ok["status"] == "Navigating"
    assert nav_ok["target_destination"] == "Kitchen"


def test_rover_command_queue_preserves_rapid_commands() -> None:
    ctrl = _make_controller()

    # Dispatch navigation + arm pose in rapid succession (same simulation step)
    ctrl.rover.execute_cmd(
        {"sub_action": "navigate", "destination": "living_room"},
        ctrl.access,
    )
    ctrl.rover.execute_cmd(
        {"sub_action": "control", "action": "arm", "arm_pose": "inspect_high"},
        ctrl.access,
    )

    raw_custom_data = ctrl.rover.custom_data_field.getSFString()
    assert '"commands"' in raw_custom_data
    assert '"goto"' in raw_custom_data
    assert '"inspect_high"' in raw_custom_data
