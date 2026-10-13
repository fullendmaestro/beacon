from langgraph.pregel import Pregel

from beacon_agent.graph import calculator, graph, smarthome_tools, tools, utc_now


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
    tool_names = [t.name for t in smarthome_tools]
    assert "get_lights" in tool_names
    assert "set_power_state" in tool_names
    assert len(tools) >= 7

