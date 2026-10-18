from __future__ import annotations

import io
import time
from collections.abc import Generator
from typing import Any, cast

from constants import CAMERA_NAMES, LIGHT_SENSOR_NAMES, MOTION_SENSOR_NAMES
try:
    from controller import Camera, DistanceSensor, LightSensor
except ImportError:
    Camera = Any  # type: ignore[assignment,misc]
    DistanceSensor = Any  # type: ignore[assignment,misc]
    LightSensor = Any  # type: ignore[assignment,misc]
from PIL import Image


class PerceptionManager:
    """Manages security cameras, MJPEG frame streaming, motion sensors, and daylight sensors."""

    def __init__(self) -> None:
        self.cameras: dict[str, Camera] = {}
        self.camera_frames: dict[str, bytes | None] = {}
        self.motion_sensors: dict[str, DistanceSensor] = {}
        self.light_sensors: dict[str, LightSensor] = {}
        self.sensor_states: dict[str, dict[str, Any]] = {}

    def init_devices(self, supervisor: Any, time_step: int) -> None:
        for name in CAMERA_NAMES:
            device = supervisor.getDevice(name)
            if device:
                cam = cast(Camera, device)
                cam.enable(time_step)
                self.cameras[name] = cam
                self.camera_frames[name] = None

        for name in MOTION_SENSOR_NAMES:
            device = supervisor.getDevice(name)
            if device:
                ds = cast(DistanceSensor, device)
                ds.enable(time_step)
                self.motion_sensors[name] = ds
                self.sensor_states[name] = {
                    "id": name.lower().replace(" ", "_"),
                    "name": name,
                    "type": "MotionSensor",
                    "state": "Clear",
                    "value": 1000.0,
                    "triggered": False,
                }

        for name in LIGHT_SENSOR_NAMES:
            device = supervisor.getDevice(name)
            if device:
                ls = cast(LightSensor, device)
                ls.enable(time_step)
                self.light_sensors[name] = ls
                self.sensor_states[name] = {
                    "id": name.lower().replace(" ", "_"),
                    "name": name,
                    "type": "DaylightSensor",
                    "state": "Bright",
                    "value": 800.0,
                    "triggered": False,
                }

    def step_sensors_and_cameras(self) -> None:
        for name, cam in self.cameras.items():
            img = cam.getImage()
            if img:
                self.camera_frames[name] = img

        for name, ds in self.motion_sensors.items():
            val = ds.getValue()
            triggered = val < 950.0
            self.sensor_states[name]["value"] = round(val, 1)
            self.sensor_states[name]["triggered"] = triggered
            self.sensor_states[name]["state"] = "Motion Detected" if triggered else "Clear"

        for name, ls in self.light_sensors.items():
            val = ls.getValue()
            is_dark = val < 300.0
            self.sensor_states[name]["value"] = round(val, 1)
            self.sensor_states[name]["triggered"] = is_dark
            self.sensor_states[name]["state"] = "Low Light / Night" if is_dark else "Daylight"

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