from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from beacon_agent.graph import graph
from .hub_demo_client import WebotsDemoClient
from .scenarios import CAPABILITY_SCENARIOS

pytestmark = pytest.mark.anyio


@pytest.fixture
async def demo_client() -> WebotsDemoClient:
    client = WebotsDemoClient()
    if not await client.is_online():
        pytest.skip("Webots Smart Home Hub Controller is not running on http://127.0.0.1:8000")
    return client


async def test_agent_light_control_with_webots_video(demo_client: WebotsDemoClient) -> None:
    """
    1. Focuses Webots camera on the Living Room Main Light.
    2. Starts 1080p Webots MP4 recording.
    3. Sends prompt to Beacon Agent to turn on and style the light.
    4. Verifies physical Webots light state and saves the MP4 video.
    """
    scenario = CAPABILITY_SCENARIOS["light_control"]
    await scenario.setup_fn(demo_client)

    rec_start = await demo_client.start_recording(
        label="agent_light_control",
        filename="webots_light_control_demo.mp4",
    )
    assert rec_start["is_recording"] is True

    try:
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": scenario.prompt}]}
        )
        final_answer = str(result["messages"][-1].content).lower()
        assert "living room" in final_answer

        # Hold recording so the illuminated room is clearly visible in the demo video
        await asyncio.sleep(scenario.post_action_hold_sec)
        assert await scenario.verify_fn(demo_client) is True
    finally:
        rec_stop = await demo_client.stop_recording()

    video_path = Path(rec_stop["video_path"])
    assert video_path.exists(), f"Expected Webots video at {video_path}"
    assert video_path.stat().st_size > 0


async def test_agent_rover_control_with_camera_tracking(demo_client: WebotsDemoClient) -> None:
    """
    1. Switches Webots Viewpoint camera into continuous rover chase-cam tracking mode.
    2. Starts 1080p Webots MP4 recording.
    3. Commands Beacon Agent to navigate the KUKA youBot to the Living Room.
    4. Captures the rover driving while the camera smoothly follows it, then saves the MP4.
    """
    scenario = CAPABILITY_SCENARIOS["rover_navigation"]
    await scenario.setup_fn(demo_client)

    rec_start = await demo_client.start_recording(
        label="agent_rover_control",
        filename="webots_rover_tracking_demo.mp4",
    )
    assert rec_start["is_recording"] is True

    try:
        result = await graph.ainvoke(
            {"messages": [{"role": "user", "content": scenario.prompt}]}
        )
        final_answer = str(result["messages"][-1].content).lower()
        assert "rover" in final_answer or "living room" in final_answer

        await asyncio.sleep(scenario.post_action_hold_sec)
        assert await scenario.verify_fn(demo_client) is True
    finally:
        rec_stop = await demo_client.stop_recording()

    video_path = Path(rec_stop["video_path"])
    assert video_path.exists(), f"Expected Webots rover video at {video_path}"
    assert video_path.stat().st_size > 0