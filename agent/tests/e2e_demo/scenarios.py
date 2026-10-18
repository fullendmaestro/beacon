from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Awaitable
from .hub_demo_client import WebotsDemoClient


@dataclass(frozen=True)
class CapabilityDemoScenario:
    id: str
    title: str
    prompt: str
    setup_fn: Callable[[WebotsDemoClient], Awaitable[None]]
    verify_fn: Callable[[WebotsDemoClient], Awaitable[bool]]
    post_action_hold_sec: float = 2.5


async def _setup_light_demo(client: WebotsDemoClient) -> None:
    # Set exterior to sunset so interior light changes are dramatic and vivid on video
    await client.set_environment("sunset")
    await client.set_light_direct("Living Room Main Light", power_state="off", brightness=0)
    await client.focus_on_device("Living Room Main Light", target_type="light", duration=1.2)


async def _verify_light_demo(client: WebotsDemoClient) -> bool:
    lights = await client.get_lights()
    living_light = next((l for l in lights if "Living Room Main Light" in l["name"]), None)
    if not living_light:
        return False
    return living_light["state"] == "On" and living_light["brightness"] >= 80


async def _setup_rover_demo(client: WebotsDemoClient) -> None:
    await client.set_environment("day")
    await client.follow_rover(duration=1.0, offset=[-2.0, -2.0, 2.5])


async def _verify_rover_demo(client: WebotsDemoClient) -> bool:
    rover = await client.get_rover()
    return (
        rover["status"] in ("Navigating", "Patrolling")
        or rover["target_destination"] is not None
        or rover["current_node"] == "living_room"
        or rover["arm_pose"] == "inspect_high"
    )


CAPABILITY_SCENARIOS: dict[str, CapabilityDemoScenario] = {
    "light_control": CapabilityDemoScenario(
        id="light_control",
        title="Smart Light Power, Brightness & Color Control",
        prompt=(
            "Turn on the Living Room Main Light, set its brightness to 100%, "
            "and change its color to warm white."
        ),
        setup_fn=_setup_light_demo,
        verify_fn=_verify_light_demo,
        post_action_hold_sec=2.5,
    ),
    "rover_navigation": CapabilityDemoScenario(
        id="rover_navigation",
        title="Autonomous KUKA youBot Room Navigation with Camera Tracking",
        prompt=(
            "Navigate the rover to the living room and set its robotic arm pose to inspect_high."
        ),
        setup_fn=_setup_rover_demo,
        verify_fn=_verify_rover_demo,
        post_action_hold_sec=6.0,
    ),
}