from __future__ import annotations

import io
import logging
import queue
import threading
import time
from collections.abc import Generator
from typing import Any, cast

from constants import (
    CAMERA_NAMES,
    MAX_LIGHT_INTENSITY,
    SUPPORTED_LIGHT_TYPES,
    ColorUtils,
)
from controller import Camera, Supervisor
from fastapi import HTTPException
from PIL import Image

logger = logging.getLogger("smart_home_controller")


class SmartHomeController:
    """
    Manages Webots device discovery, synchronization, camera frames,
    and thread-safe state modification for smart home fixtures.
    """

    def __init__(self, supervisor: Supervisor | None = None) -> None:
        self.supervisor = supervisor or Supervisor()
        self.time_step = int(self.supervisor.getBasicTimeStep())
        self.command_queue: queue.Queue = queue.Queue()

        self.light_nodes: dict[int, Any] = {}
        self.light_states: dict[int, dict[str, Any]] = {}
        self.state_lock = threading.Lock()

        self.cameras: dict[str, Camera] = {}
        self.camera_frames: dict[str, bytes | None] = {}

    def discover_lights(self) -> dict[int, Any]:
        """Discover light nodes from the scene tree root with fallback to ID scan."""
        discovered: dict[int, Any] = {}
        root = self.supervisor.getRoot()
        if root:
            children_field: Any = root.getField("children")
            if children_field:
                for idx in range(children_field.getCount()):
                    node = children_field.getMFNode(idx)
                    if node and node.getTypeName() in SUPPORTED_LIGHT_TYPES:
                        discovered[node.getId()] = node

        if not discovered:
            for i in range(100000):
                node = self.supervisor.getFromId(i)
                if node and node.getTypeName() in SUPPORTED_LIGHT_TYPES:
                    discovered[node.getId()] = node

        return discovered

    @staticmethod
    def get_light_fields(node: Any) -> tuple[Any, Any]:
        """Return (intensity_field, color_field) based on PROTO type."""
        type_name = node.getTypeName()
        if type_name == "CeilingSpotLight":
            return node.getField("spotLightIntensity"), node.getField("spotLightColor")
        return node.getField("pointLightIntensity"), node.getField("pointLightColor")

    def init_devices(self) -> None:
        """Scan and populate initial caches for lights and cameras."""
        self.light_nodes = self.discover_lights()

        with self.state_lock:
            for node_id, node in self.light_nodes.items():
                type_name = node.getTypeName()
                name_field = node.getField("name")
                name = name_field.getSFString() if name_field else type_name

                i_field, c_field = self.get_light_fields(node)
                raw_intensity = i_field.getSFFloat() if i_field else 0.0
                raw_color = c_field.getSFColor() if c_field else [1.0, 1.0, 1.0]

                is_on = raw_intensity > 0
                brightness_pct = round(min(100.0, (raw_intensity / MAX_LIGHT_INTENSITY) * 100)) if is_on else 0

                self.light_states[node_id] = {
                    "id": node_id,
                    "name": name,
                    "type": type_name,
                    "state": "On" if is_on else "Off",
                    "intensity": raw_intensity,
                    "brightness": brightness_pct if brightness_pct > 0 else 100,
                    "color_rgb": raw_color,
                    "color_hex": ColorUtils.to_hex(raw_color),
                    "metadata": f"Intensity at {raw_intensity:.1f}",
                }

        for name in CAMERA_NAMES:
            device = self.supervisor.getDevice(name)
            if device:
                cam = cast(Camera, device)
                cam.enable(self.time_step)
                self.cameras[name] = cam
                self.camera_frames[name] = None

        logger.info("Initialized %d lights and %d cameras.", len(self.light_nodes), len(self.cameras))

    # --- HTTP API Handlers ---

    def list_lights(self) -> list[dict[str, Any]]:
        with self.state_lock:
            return [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "state": s["state"],
                    "type": s["type"],
                    "brightness": s["brightness"] if s["state"] == "On" else 0,
                    "color": s["color_hex"],
                    "color_rgb": s["color_rgb"],
                    "metadata": f"Intensity at {s['intensity']:.1f}",
                }
                for s in self.light_states.values()
            ]

    def get_light(self, node_id: int) -> dict[str, Any]:
        with self.state_lock:
            s = self.light_states.get(node_id)
            if not s:
                raise HTTPException(status_code=404, detail="Light not found")
            return {
                "id": s["id"],
                "name": s["name"],
                "state": s["state"],
                "type": s["type"],
                "brightness": s["brightness"] if s["state"] == "On" else 0,
                "color": s["color_hex"],
                "color_rgb": s["color_rgb"],
                "metadata": f"Intensity at {s['intensity']:.1f}",
            }

    def dispatch_command(self, cmd: dict[str, Any], timeout: float = 2.0) -> dict[str, Any]:
        """Dispatch a command to the simulation thread and block until acknowledged."""
        completion = threading.Event()
        response_holder: dict[str, Any] = {}
        cmd["completion"] = completion
        cmd["response"] = response_holder
        self.command_queue.put(cmd)
        completion.wait(timeout=timeout)
        return response_holder.get("result", {"status": "command_queued"})

    def request_toggle(self, node_id: int) -> dict[str, Any]:
        if node_id not in self.light_nodes:
            raise HTTPException(status_code=404, detail="Light not found")
        return self.dispatch_command({"action": "toggle", "node_id": node_id})

    def request_set_state(
        self,
        node_id: int,
        power_state: str | None = None,
        brightness: int | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        if node_id not in self.light_nodes:
            raise HTTPException(status_code=404, detail="Light not found")
        return self.dispatch_command({
            "action": "set_state",
            "node_id": node_id,
            "power_state": power_state,
            "brightness": brightness,
            "color": color,
        })

    def list_cameras(self) -> list[dict[str, Any]]:
        return [
            {
                "id": name,
                "name": name,
                "state": "Online",
                "metadata": f"Live • {cam.getWidth()}x{cam.getHeight()}",
                "type": "Camera",
            }
            for name, cam in self.cameras.items()
        ]

    def stream_camera(self, name: str) -> Generator[bytes]:
        cam = self.cameras.get(name)
        if not cam:
            return

        width = cam.getWidth()
        height = cam.getHeight()

        while True:
            raw = self.camera_frames.get(name)
            if raw:
                try:
                    img = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA")
                    buf = io.BytesIO()
                    img.convert("RGB").save(buf, format="JPEG", quality=60)
                    frame = buf.getvalue()

                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                    )
                except (ValueError, OSError):
                    pass
            time.sleep(0.05)

    # --- Webots Simulation Thread Execution ---

    def execute_light_command(self, cmd: dict[str, Any]) -> None:
        node_id = cmd["node_id"]
        node = self.light_nodes.get(node_id)
        if not node:
            if "response" in cmd:
                cmd["response"]["result"] = {"error": "Light not found"}
            if "completion" in cmd:
                cmd["completion"].set()
            return

        i_field, c_field = self.get_light_fields(node)
        action = cmd.get("action")

        with self.state_lock:
            state = self.light_states.get(node_id, {})
            current_intensity = i_field.getSFFloat() if i_field else 0.0
            current_brightness = state.get("brightness", 100)

            if action == "toggle":
                new_is_on = not (current_intensity > 0)
                target_intensity = (MAX_LIGHT_INTENSITY * (current_brightness / 100.0)) if new_is_on else 0.0
                if i_field:
                    i_field.setSFFloat(target_intensity)

                state["state"] = "On" if new_is_on else "Off"
                state["intensity"] = target_intensity
                state["metadata"] = f"Intensity at {target_intensity:.1f}"

            elif action == "set_state":
                target_is_on = state.get("state") == "On"

                if cmd.get("power_state"):
                    target_is_on = cmd["power_state"].lower() == "on"

                if cmd.get("brightness") is not None:
                    b_val = max(0, min(100, int(cmd["brightness"])))
                    if b_val == 0:
                        target_is_on = False
                    else:
                        target_is_on = True
                        current_brightness = b_val
                    state["brightness"] = current_brightness

                if cmd.get("color"):
                    parsed_rgb = ColorUtils.parse(cmd["color"])
                    if c_field:
                        c_field.setSFColor(parsed_rgb)
                    state["color_rgb"] = parsed_rgb
                    state["color_hex"] = ColorUtils.to_hex(parsed_rgb)

                target_intensity = (MAX_LIGHT_INTENSITY * (current_brightness / 100.0)) if target_is_on else 0.0
                if i_field:
                    i_field.setSFFloat(target_intensity)

                state["state"] = "On" if target_is_on else "Off"
                state["intensity"] = target_intensity
                state["metadata"] = f"Intensity at {target_intensity:.1f}"

            if "response" in cmd:
                cmd["response"]["result"] = {
                    "success": True,
                    "id": node_id,
                    "state": state["state"],
                    "brightness": state["brightness"] if state["state"] == "On" else 0,
                    "color": state["color_hex"],
                    "intensity": state["intensity"],
                }
            if "completion" in cmd:
                cmd["completion"].set()

    def step_simulation(self) -> None:
        """Process camera images and queued commands during a simulation tick."""
        for name, cam in self.cameras.items():
            img = cam.getImage()
            if img:
                self.camera_frames[name] = img

        while not self.command_queue.empty():
            cmd = self.command_queue.get()
            try:
                self.execute_light_command(cmd)
            except Exception as e:  # noqa: BLE001
                logger.error("Error executing simulation command: %s", e)
                if "completion" in cmd:
                    cmd["completion"].set()
