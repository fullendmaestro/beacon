"""Isolated Per-Device Webots Controller (`iot_device_controller`) for Cameras, Sensors, and Smart Appliances."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import sys
import threading
import time
from typing import Any

try:
    from controller import Camera, DistanceSensor, LightSensor, Robot  # type: ignore[import-not-found]
    _WEBOTS = True
except ImportError:
    Robot = None  # type: ignore[assignment,misc]
    Camera = Any  # type: ignore[assignment,misc]
    DistanceSensor = Any  # type: ignore[assignment,misc]
    LightSensor = Any  # type: ignore[assignment,misc]
    _WEBOTS = False

try:
    from PIL import Image
except ImportError:
    Image = None  # type: ignore[assignment]


class IoTDeviceController:
    """
    Process-isolated Webots controller bound to a single `device_id` via `controllerArgs`.
    Uses adaptive baseline calibration and edge-triggered hysteresis so static walls/doors
    never cause false-positive motion floods.
    """

    def __init__(self, device_id: str) -> None:
        self.device_id = device_id
        self.robot = Robot() if (_WEBOTS and Robot is not None) else None
        self.time_step = int(self.robot.getBasicTimeStep()) if self.robot else 32
        self.outgoing_queue: list[dict[str, Any]] = []
        self.camera: Any = None
        self.distance_sensor: Any = None
        self.light_sensor: Any = None
        self.wbt_name = device_id

        # Edge-triggered & adaptive baseline state
        self._calibration_samples: list[float] = []
        self._baseline_dist: float | None = None
        self._prev_dist: float | None = None
        self._motion_hold_until: float = 0.0
        self._last_emitted_triggered: bool | None = None
        self._last_emitted_value: float = -1.0
        self._last_emit_ts: float = 0.0
        self._last_cam_ts: float = 0.0

        if self.robot:
            for i in range(self.robot.getNumberOfDevices()):
                dev = self.robot.getDeviceByIndex(i)
                if not dev:
                    continue
                self.wbt_name = dev.getName()
                if hasattr(dev, "getImage"):
                    self.camera = dev
                    self.camera.enable(max(self.time_step * 8, 128))
                elif hasattr(dev, "getLookupTable"):
                    self.distance_sensor = dev
                    self.distance_sensor.enable(self.time_step)
                elif hasattr(dev, "getValue"):
                    self.light_sensor = dev
                    self.light_sensor.enable(self.time_step)

    def run(self) -> None:
        t = threading.Thread(target=lambda: asyncio.run(self._ws_loop()), daemon=True)
        t.start()

        last_sample = 0.0
        if self.robot:
            while self.robot.step(self.time_step) != -1:
                now = time.monotonic()
                if now - last_sample >= 0.25:
                    last_sample = now
                    self._sample_local_devices(now)
        else:
            while True:
                time.sleep(0.5)

    def _sample_local_devices(self, now: float) -> None:
        # 1. Motion / Distance Sensor with Static-Background Calibration & Delta Detection
        if self.distance_sensor is not None:
            raw_val = float(self.distance_sensor.getValue())
            if not (0.0 <= raw_val <= 10000.0):
                raw_val = 1000.0
            val = round(raw_val, 1)

            # Collect first 6 samples (~1.5s) to lock in static room geometry (walls, furniture, docked robot)
            if self._baseline_dist is None:
                self._calibration_samples.append(val)
                if len(self._calibration_samples) >= 6:
                    self._baseline_dist = sum(self._calibration_samples) / len(self._calibration_samples)
                    self._prev_dist = val
                return

            prev = self._prev_dist if self._prev_dist is not None else val
            self._prev_dist = val

            # True motion occurs when either:
            # (a) Instantaneous step delta > 25 units (moving body crossing the ray), or
            # (b) Object is > 55 units closer than the calibrated static room baseline
            step_delta = abs(val - prev)
            baseline_drop = self._baseline_dist - val

            if step_delta >= 25.0 or baseline_drop >= 55.0:
                self._motion_hold_until = now + 3.0  # Hold triggered state for 3s to prevent rapid chatter
            else:
                # Slowly adapt baseline to gradual static changes (e.g. a door left open)
                self._baseline_dist = 0.98 * self._baseline_dist + 0.02 * val

            triggered = now < self._motion_hold_until

            # Emit ONLY on state transition (Clear <-> Motion Detected) or significant value shift while triggered
            state_changed = triggered != self._last_emitted_triggered
            value_shifted = triggered and abs(val - self._last_emitted_value) >= 40.0
            if state_changed or value_shifted:
                self._last_emitted_triggered = triggered
                self._last_emitted_value = val
                self._last_emit_ts = now
                self.outgoing_queue.append({
                    "topic": f"sensor.telemetry.{self.device_id}",
                    "payload": {
                        "device_id": self.device_id,
                        "wbt_name": self.wbt_name,
                        "triggered": triggered,
                        "value": val,
                        "state": "Motion Detected" if triggered else "Clear",
                    },
                })

        # 2. Daylight / Light Sensor with Hysteresis (Triggers < 280 lux, Clears > 340 lux)
        if self.light_sensor is not None:
            raw_val = float(self.light_sensor.getValue())
            val = round(raw_val, 1)
            prev_trig = bool(self._last_emitted_triggered)
            triggered = (val < 280.0) if not prev_trig else (val < 340.0)

            state_changed = triggered != self._last_emitted_triggered
            value_shifted = abs(val - self._last_emitted_value) >= 50.0 and (now - self._last_emit_ts >= 5.0)
            if state_changed or value_shifted:
                self._last_emitted_triggered = triggered
                self._last_emitted_value = val
                self._last_emit_ts = now
                self.outgoing_queue.append({
                    "topic": f"sensor.telemetry.{self.device_id}",
                    "payload": {
                        "device_id": self.device_id,
                        "wbt_name": self.wbt_name,
                        "triggered": triggered,
                        "value": val,
                        "state": "Low Light / Night" if triggered else "Daylight",
                    },
                })

        # 3. Camera Frame (Throttled to ~2 FPS background sync to save bandwidth)
        if self.camera is not None and Image is not None and (now - self._last_cam_ts >= 0.5):
            self._last_cam_ts = now
            try:
                raw = self.camera.getImage()
                if raw:
                    w = int(self.camera.getWidth())
                    h = int(self.camera.getHeight())
                    img = Image.frombytes("RGBA", (w, h), raw, "raw", "BGRA")
                    buf = io.BytesIO()
                    img.convert("RGB").save(buf, format="JPEG", quality=60)
                    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                    self.outgoing_queue.append({
                        "topic": "camera.frame",
                        "payload": {
                            "device_id": self.device_id,
                            "camera_name": self.wbt_name,
                            "jpeg_base64": b64,
                        },
                    })
            except Exception:  # noqa: BLE001
                pass

    async def _ws_loop(self) -> None:
        import urllib.parse
        import websockets

        encoded_id = urllib.parse.quote(self.device_id, safe="")
        url = f"ws://127.0.0.1:8000/ws/device/{encoded_id}"
        while True:
            try:
                async with websockets.connect(url) as ws:
                    async def _sender() -> None:
                        while True:
                            while self.outgoing_queue:
                                msg = self.outgoing_queue.pop(0)
                                await ws.send(json.dumps(msg))
                            await asyncio.sleep(0.05)

                    send_task = asyncio.create_task(_sender())
                    try:
                        async for raw in ws:
                            msg = json.loads(raw)
                            topic = str(msg.get("topic", ""))
                            payload = msg.get("payload", {})
                            if topic.startswith("device.command."):
                                params = payload.get("params", {})
                                self.outgoing_queue.append({
                                    "topic": f"device.state.{payload.get('domain', 'appliance')}.{self.device_id}",
                                    "payload": {
                                        "device_id": self.device_id,
                                        "wbt_name": self.wbt_name,
                                        "state": params,
                                        "source": "iot_device_controller",
                                    },
                                })
                    finally:
                        send_task.cancel()
            except Exception:  # noqa: BLE001
                await asyncio.sleep(1.0)


if __name__ == "__main__":
    dev_id_arg = sys.argv[1] if len(sys.argv) > 1 else "generic_iot_device"
    IoTDeviceController(dev_id_arg).run()
