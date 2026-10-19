from __future__ import annotations

import io
import time
import urllib.request
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
        self.stream_subscribers: dict[str, int] = {}
        self._last_cam_step: float = 0.0
        self.motion_sensors: dict[str, DistanceSensor] = {}
        self.light_sensors: dict[str, LightSensor] = {}
        self.sensor_states: dict[str, dict[str, Any]] = {}

    def init_devices(self, supervisor: Any, time_step: int) -> None:
        # Sample cameras at 128ms (~8 FPS) rather than 16ms to avoid saturating Webots OpenGL rendering
        cam_period = max(time_step * 8, 128)
        for name in CAMERA_NAMES:
            device = supervisor.getDevice(name)
            if device:
                cam = cast(Camera, device)
                cam.enable(cam_period)
                self.cameras[name] = cam
                self.camera_frames[name] = None
                self.stream_subscribers[name] = 0

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
        now = time.time()
        # Only grab camera frames when there are active stream subscribers,
        # throttled to at most ~10 FPS (every 100ms) to prevent memory allocation storms.
        if any(v > 0 for v in self.stream_subscribers.values()):
            if now - self._last_cam_step >= 0.1:
                self._last_cam_step = now
                for name, count in list(self.stream_subscribers.items()):
                    if count > 0 and name in self.cameras:
                        cam = self.cameras[name]
                        try:
                            img = cam.getImage()
                            if img:
                                self.camera_frames[name] = img
                        except (MemoryError, ValueError, Exception):
                            pass

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
        cams = [
            {
                "id": name,
                "name": name,
                "state": "Online",
                "metadata": f"Live • {cam.getWidth()}x{cam.getHeight()}",
                "type": "Camera",
            }
            for name, cam in self.cameras.items()
            if name != "Rover Mast Camera"
        ]
        if not any(c["name"] == "TIAGo Camera" for c in cams):
            cams.append({
                "id": "TIAGo Camera",
                "name": "TIAGo Camera",
                "state": "Online",
                "metadata": "Live • 640x480 (Orbbec Astra RGB)",
                "type": "Camera",
            })
        return cams

    def stream_camera(self, name: str) -> Generator[bytes]:
        if name in ("TIAGo Camera", "tiago_camera", "TIAGo Head Camera", "Astra rgb"):
            try:
                req = urllib.request.Request("http://127.0.0.1:8001/camera/stream")
                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        yield chunk
                return
            except Exception:
                pass

            # Fallback frame polling
            for _ in range(50):
                try:
                    req = urllib.request.Request("http://127.0.0.1:8001/camera/frame")
                    with urllib.request.urlopen(req, timeout=1.0) as resp:
                        frame = resp.read()
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                        )
                except Exception:
                    pass
                time.sleep(0.1)
            return

        cam = self.cameras.get(name)
        if not cam:
            return
        width = cam.getWidth()
        height = cam.getHeight()

        self.stream_subscribers[name] = self.stream_subscribers.get(name, 0) + 1
        try:
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
                time.sleep(0.08)
        finally:
            self.stream_subscribers[name] = max(0, self.stream_subscribers.get(name, 1) - 1)