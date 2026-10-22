"""In-process Asyncio Pub/Sub Event Broker with wildcard topic matching and WebSocket multiplexing."""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("beacon_hub.broker")

SubscriberCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]


@dataclass
class Subscription:
    pattern: str
    callback: SubscriberCallback


@dataclass
class EventBroker:
    """
    Asynchronous Topic Exchange supporting wildcard topic patterns (e.g. `device.command.*`, `*`)
    and bridging events between FastAPI HTTP endpoints, SQLite persistence, Webots controllers,
    and Next.js WebSocket clients.
    """

    _subscriptions: list[Subscription] = field(default_factory=list)
    _ui_sockets: set[WebSocket] = field(default_factory=set)
    _sim_bridge_sockets: set[WebSocket] = field(default_factory=set)
    _device_sockets: dict[str, set[WebSocket]] = field(default_factory=dict)
    _last_sim_heartbeat: float = 0.0
    _sim_fps: float = 0.0
    _sim_time: float = 0.0
    _camera_frames: dict[str, bytes] = field(default_factory=dict)

    @property
    def is_webots_attached(self) -> bool:
        return bool(self._sim_bridge_sockets) or (time.monotonic() - self._last_sim_heartbeat) <= 1.5

    @property
    def sim_mode(self) -> str:
        return "WEBOTS_ATTACHED" if self.is_webots_attached else "VIRTUAL_PHYSICS_FALLBACK"

    def record_heartbeat(self, sim_time: float = 0.0, fps: float = 60.0) -> None:
        self._last_sim_heartbeat = time.monotonic()
        self._sim_time = sim_time
        self._sim_fps = fps

    def update_camera_frame(self, camera_name: str, jpeg_bytes: bytes) -> None:
        self._camera_frames[camera_name] = jpeg_bytes

    def get_camera_frame(self, camera_name: str) -> bytes | None:
        return self._camera_frames.get(camera_name)

    def subscribe(self, pattern: str, callback: SubscriberCallback) -> Callable[[], None]:
        sub = Subscription(pattern=pattern, callback=callback)
        self._subscriptions.append(sub)

        def _unsubscribe() -> None:
            if sub in self._subscriptions:
                self._subscriptions.remove(sub)

        return _unsubscribe

    async def register_ui_socket(self, ws: WebSocket) -> None:
        self._ui_sockets.add(ws)

    def unregister_ui_socket(self, ws: WebSocket) -> None:
        self._ui_sockets.discard(ws)

    async def register_sim_bridge_socket(self, ws: WebSocket) -> None:
        self._sim_bridge_sockets.add(ws)
        self.record_heartbeat()

    def unregister_sim_bridge_socket(self, ws: WebSocket) -> None:
        self._sim_bridge_sockets.discard(ws)

    async def register_device_socket(self, device_id: str, ws: WebSocket) -> None:
        self._device_sockets.setdefault(device_id, set()).add(ws)

    def unregister_device_socket(self, device_id: str, ws: WebSocket) -> None:
        if device_id in self._device_sockets:
            self._device_sockets[device_id].discard(ws)
            if not self._device_sockets[device_id]:
                del self._device_sockets[device_id]

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish an event to in-process subscribers, UI WebSockets, and Webots bridges."""
        if topic == "sim.bridge.heartbeat":
            self.record_heartbeat(
                sim_time=float(payload.get("sim_time", 0.0)),
                fps=float(payload.get("fps", 60.0)),
            )

        envelope = {
            "topic": topic,
            "payload": payload,
            "timestamp": time.time(),
            "sim_mode": self.sim_mode,
        }
        serialized = json.dumps(envelope)

        # 1. Notify in-process subscribers matching pattern
        for sub in list(self._subscriptions):
            if fnmatch.fnmatch(topic, sub.pattern) or sub.pattern == "#":
                try:
                    res = sub.callback(topic, payload)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Subscriber error on topic %s: %s", topic, exc)

        # 2. Broadcast to Next.js UI WebSockets (skip high-frequency raw sim heartbeat)
        if self._ui_sockets and topic != "sim.bridge.heartbeat":
            dead_ui: list[WebSocket] = []
            for ws in list(self._ui_sockets):
                try:
                    await ws.send_text(serialized)
                except Exception:  # noqa: BLE001
                    dead_ui.append(ws)
            for ws in dead_ui:
                self._ui_sockets.discard(ws)

        # 3. Forward commands and lifecycle events to Webots world_spawner / sim-bridge sockets
        if self._sim_bridge_sockets and (
            topic.startswith("device.lifecycle.")
            or topic.startswith("device.command.")
            or topic.startswith("robot.command.")
            or topic in ("environment.updated", "scene.triggered")
        ):
            dead_sim: list[WebSocket] = []
            for ws in list(self._sim_bridge_sockets):
                try:
                    await ws.send_text(serialized)
                except Exception:  # noqa: BLE001
                    dead_sim.append(ws)
            for ws in dead_sim:
                self._sim_bridge_sockets.discard(ws)

        # 4. Forward per-device commands to isolated iot_device_controller sockets
        if topic.startswith("device.command."):
            parts = topic.split(".", 3)
            if len(parts) == 4:
                dev_id = parts[3]
                dev_sockets = self._device_sockets.get(dev_id, set())
                dead_dev: list[WebSocket] = []
                for ws in list(dev_sockets):
                    try:
                        await ws.send_text(serialized)
                    except Exception:  # noqa: BLE001
                        dead_dev.append(ws)
                for ws in dead_dev:
                    dev_sockets.discard(ws)

    def publish_threadsafe(
        self, loop: asyncio.AbstractEventLoop, topic: str, payload: dict[str, Any]
    ) -> None:
        """Schedule a publish call from a synchronous thread."""
        asyncio.run_coroutine_threadsafe(self.publish(topic, payload), loop)


_broker_instance: EventBroker | None = None


def get_broker() -> EventBroker:
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = EventBroker()
    return _broker_instance
