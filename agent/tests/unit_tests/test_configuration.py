from langgraph.pregel import Pregel

from beacon_agent.graph import (
    calculator,
    graph,
    mcp_tools,
    rover_tools,
    smarthome_tools,
    tools,
    utc_now,
)


def test_graph_compiles() -> None:
    assert isinstance(graph, Pregel)


def test_calculator_tool() -> None:
    result = calculator.invoke({"expression": "2 + 3 * 4"})
    assert result == "14"


def test_utc_now_tool() -> None:
    result = utc_now.invoke({})
    assert isinstance(result, str)
    assert "T" in result


def test_smarthome_tools_loaded() -> None:
    tool_names = {t.name for t in smarthome_tools}
    expected_tools = {
        # Lights
        "get_lights",
        "get_light_state",
        "set_power_state",
        "set_brightness",
        "set_color",
        # Access (Doors, Garage, Gate)
        "get_doors",
        "set_door_state",
        "set_door_lock",
        # Blinds
        "get_blinds",
        "set_blind_position",
        # Climate
        "get_climate_zones",
        "set_climate_state",
        # Appliances
        "get_appliances",
        "set_appliance_state",
        # Whole-Home, Sensors & Scenes
        "get_home_summary",
        "get_sensors",
        "get_cameras",
        "trigger_scene",
        "set_environment",
    }
    assert expected_tools.issubset(tool_names)


def test_rover_tools_loaded() -> None:
    tool_names = {t.name for t in rover_tools}
    expected_rover_tools = {
        "get_rover_telemetry",
        "plan_rover_route",
        "navigate_rover_to_room",
        "navigate_rover_to_pose",
        "set_rover_arm_pose",
        "set_rover_gripper",
        "drive_rover_velocity",
        "stop_rover",
    }
    assert expected_rover_tools.issubset(tool_names)
    assert len(mcp_tools) >= 27
    assert len(tools) >= 29