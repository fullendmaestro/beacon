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
    Connects to `ws://127.0.0.1:8000/ws/device/<device_id>`, listens only for its own
    `device.command.<domain>.<id>`, and publishes sensor telemetry or camera frames.
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

        if self.robot:
            for i in range(self.robot.getNumberOfDevices()):
                dev = self.robot.getDeviceByIndex(i)
                if not dev:
                    continue
                self.wbt_name = dev.getName()
                nt = dev.getNodeType()
                # Node types or duck-typing for Camera / DistanceSensor / LightSensor
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

        last_pub = 0.0
        if self.robot:
            while self.robot.step(self.time_step) != -1:
                now = time.monotonic()
                if now - last_pub >= 0.25:
                    last_pub = now
                    self._sample_local_devices()
        else:
            while True:
                time.sleep(0.5)

    def _sample_local_devices(self) -> None:
        if self.distance_sensor is not None:
            val = round(float(self.distance_sensor.getValue()), 1)
            triggered = val < 950.0
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
        if self.light_sensor is not None:
            val = round(float(self.light_sensor.getValue()), 1)
            triggered = val < 300.0
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
        if self.camera is not None and Image is not None:
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
