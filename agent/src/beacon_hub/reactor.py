# agent/src/beacon_hub/reactor.py
"""Autonomous Event Reactor Engine for Beacon Core Hub."""

from __future__ import annotations

import fnmatch
import logging
import time
import uuid
from typing import Any

from .broker import EventBroker
from .database.connection import DatabaseManager

logger = logging.getLogger("beacon_hub.reactor")


class EventReactor:
    """
    Subscribes to the in-process EventBroker and evaluates event-driven rules
    on rising-edge state transitions whenever sensors trigger or devices change state.
    """

    def __init__(self, db: DatabaseManager, broker: EventBroker) -> None:
        self.db = db
        self.broker = broker
        self._unsub: Any = None
        # Track last known boolean `triggered` state per topic to enforce rising-edge evaluation
        self._last_topic_triggered: dict[str, bool] = {}

    def start(self) -> None:
        if self._unsub is None:
            self._unsub = self.broker.subscribe("*", self._on_any_event)

    def stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

    async def _on_any_event(self, topic: str, payload: dict[str, Any]) -> None:
        if topic in (
            "sim.bridge.heartbeat",
            "agent.event.alert",
            "hub.snapshot",
            "camera.frame",
            "pedestrian.telemetry",
        ) or topic.startswith("sentinel.task."):
            return

        # Enforce rising-edge transition detection on sensor.telemetry.*
        if topic.startswith("sensor.telemetry."):
            curr_trig = bool(payload.get("triggered", False))
            prev_trig = self._last_topic_triggered.get(topic, False)
            self._last_topic_triggered[topic] = curr_trig

            # Only log and evaluate rules when transitioning changes (e.g., Clear -> Motion)
            if curr_trig == prev_trig and not payload.get("stimulus"):
                return
            self.db.log_event(topic, payload)

            # If triggered directly by /api/v2/sim/stimulus, the stimulus endpoint emits its own rich alert
            if payload.get("stimulus"):
                return

        rules = self.db.list_event_rules()
        now = time.monotonic()

        for rule in rules:
            if not rule["enabled"]:
                continue
            if not fnmatch.fnmatch(topic, rule["trigger_topic"]):
                continue
            if now - rule["last_triggered_at"] < rule["cooldown_sec"]:
                continue
            if not self._matches_condition(rule["condition"], payload):
                continue

            self.db.mark_rule_triggered(rule["id"], now)
            await self._execute_rule(rule, topic, payload)

    @staticmethod
    def _matches_condition(condition: dict[str, Any], payload: dict[str, Any]) -> bool:
        if not condition:
            return True
        for k, expected in condition.items():
            actual = payload.get(k)
            if actual is None and isinstance(payload.get("state"), dict):
                actual = payload["state"].get(k)
            if actual != expected:
                return False
        return True

    async def _execute_rule(
        self, rule: dict[str, Any], trigger_topic: str, trigger_payload: dict[str, Any]
    ) -> None:
        executed_actions: list[str] = []
        camera_used: str | None = None
        alert_message = f"Rule '{rule['name']}' triggered by {trigger_topic}."

        for act in rule.get("actions", []):
            act_type = act.get("type")
            if act_type == "device_command":
                dev = self.db.strict_lookup(str(act.get("device_id", "")))
                if dev:
                    params = act.get("params", {})
                    self.db.update_desired_state(dev["id"], params)
                    await self.broker.publish(
                        f"device.command.{dev['domain']}.{dev['id']}",
                        {
                            "command_id": f"evt_{uuid.uuid4().hex[:6]}",
                            "device_id": dev["id"],
                            "wbt_name": dev["wbt_name"],
                            "wbt_def": dev.get("wbt_def"),
                            "domain": dev["domain"],
                            "action": act.get("action", "set_state"),
                            "params": params,
                        },
                    )
                    executed_actions.append(f"{dev['wbt_name']} -> {params}")

            elif act_type == "robot_navigate":
                room = str(act.get("destination", "foyer"))
                await self.broker.publish(
                    "robot.command.tiago",
                    {"action": "navigate", "destination": room, "room": room},
                )
                executed_actions.append(f"Dispatched TIAGo to {room}")

            elif act_type == "camera_alert":
                camera_used = str(act.get("camera_name", "Front Door Camera"))
                if act.get("message"):
                    alert_message = str(act["message"])

        alert_payload = {
            "alert_id": f"alrt_{uuid.uuid4().hex[:8]}",
            "rule_id": rule["id"],
            "rule_name": rule["name"],
            "trigger_topic": trigger_topic,
            "trigger_payload": trigger_payload,
            "message": alert_message,
            "executed_actions": executed_actions,
            "camera_name": camera_used,
            "agent_prompt": rule.get("agent_prompt"),
            "timestamp": time.time(),
        }
        self.db.log_event("agent.event.alert", alert_payload)
        await self.broker.publish("agent.event.alert", alert_payload)
