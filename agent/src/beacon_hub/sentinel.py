"""Background Sentinel Agent Runner with Event Coalescing, Rate-Limiting, and Bounded Backpressure."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from langchain_core.messages import HumanMessage

from .broker import EventBroker
from .database.connection import DatabaseManager

logger = logging.getLogger("beacon_hub.sentinel")


class BackgroundSentinelService:
    """
    Processes `agent.event.alert` events asynchronously using the dedicated `sentinel_graph`
    in the background so the user's foreground chat thread is never interrupted.

    Anti-Overwhelm Safeguards:
    - Coalescing Window (1.5s): Aggregates multiple alerts arriving within 1.5s into a single batch run.
    - Per-Rule Cooldown (20s): Ignores duplicate alerts from the same rule_id within 20s.
    - Single-Flight Semaphore & Bounded Queue (max 5): Never runs concurrent LLM loops or queues > 5 batches.
    """

    def __init__(
        self,
        db: DatabaseManager,
        broker: EventBroker,
        coalesce_window_sec: float = 1.5,
        per_rule_cooldown_sec: float = 20.0,
        max_queue_size: int = 5,
    ) -> None:
        self.db = db
        self.broker = broker
        self.coalesce_window_sec = coalesce_window_sec
        self.per_rule_cooldown_sec = per_rule_cooldown_sec
        self.max_queue_size = max_queue_size

        self.enabled: bool = True
        self._unsub: Any = None
        self._pending_batch: dict[str, dict[str, Any]] = {}
        self._last_rule_run: dict[str, float] = {}
        self._debounce_task: asyncio.Task[None] | None = None
        self._work_queue: asyncio.Queue[list[dict[str, Any]]] = asyncio.Queue(maxsize=max_queue_size)
        self._worker_task: asyncio.Task[None] | None = None
        self._recent_tasks: list[dict[str, Any]] = []

    def start(self) -> None:
        if self._unsub is None:
            self._unsub = self.broker.subscribe("agent.event.alert", self._on_event_alert)
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop(), name="beacon-sentinel-worker")

    async def stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

    def get_recent_tasks(self, limit: int = 15) -> list[dict[str, Any]]:
        return self._recent_tasks[:limit]

    async def _on_event_alert(self, _topic: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        agent_prompt = payload.get("agent_prompt")
        if not agent_prompt:
            return

        rule_id = str(payload.get("rule_id") or payload.get("trigger_topic") or "default")
        now = time.monotonic()

        # Per-rule cooldown gate to prevent aggressive firing
        last_run = self._last_rule_run.get(rule_id, 0.0)
        if now - last_run < self.per_rule_cooldown_sec:
            logger.debug("Sentinel throttled duplicate alert for rule '%s'", rule_id)
            return

        # Coalesce by rule_id (latest payload for the same rule overwrites within the 1.5s window)
        self._pending_batch[rule_id] = payload

        if self._debounce_task is None or self._debounce_task.done():
            self._debounce_task = asyncio.create_task(self._flush_after_window())

    async def _flush_after_window(self) -> None:
        await asyncio.sleep(self.coalesce_window_sec)
        if not self._pending_batch:
            return

        now = time.monotonic()
        batch = list(self._pending_batch.values())
        for item in batch:
            rid = str(item.get("rule_id") or item.get("trigger_topic") or "default")
            self._last_rule_run[rid] = now
        self._pending_batch.clear()

        # Bounded queue backpressure: if full, drop oldest batch to make room for fresh telemetry
        if self._work_queue.full():
            try:
                self._work_queue.get_nowait()
                self._work_queue.task_done()
            except asyncio.QueueEmpty:
                pass

        await self._work_queue.put(batch)

    async def _worker_loop(self) -> None:
        while True:
            batch = await self._work_queue.get()
            try:
                await self._process_batch(batch)
            except Exception as exc:  # noqa: BLE001
                logger.warning("BackgroundSentinelService batch error: %s", exc)
            finally:
                self._work_queue.task_done()

    async def _process_batch(self, batch: list[dict[str, Any]]) -> None:
        task_id = f"sntl_{uuid.uuid4().hex[:8]}"
        alert_ids = [str(a.get("alert_id", "")) for a in batch]
        rule_names = [str(a.get("rule_name", "Home Event")) for a in batch]
        cameras = [str(a["camera_name"]) for a in batch if a.get("camera_name")]
        primary_camera = cameras[0] if cameras else None

        task_record: dict[str, Any] = {
            "task_id": task_id,
            "alert_ids": alert_ids,
            "title": " + ".join(dict.fromkeys(rule_names)),
            "camera_name": primary_camera,
            "event_count": len(batch),
            "status": "running",
            "summary": "Inspecting sensors and camera feeds...",
            "tool_calls": [],
            "timestamp": time.time(),
        }
        self._recent_tasks = [task_record, *self._recent_tasks][:25]
        await self.broker.publish("sentinel.task.started", task_record)

        # Build coalesced prompt for the background Sentinel agent
        lines = [
            f"Process the following {len(batch)} coalesced smart-home event(s) autonomously in the background:"
        ]
        for idx, item in enumerate(batch, 1):
            lines.append(
                f"{idx}. [{item.get('rule_name')}] (Topic: {item.get('trigger_topic')}): "
                f"{item.get('message')} | Already executed by reactor: {item.get('executed_actions', [])} | "
                f"Directive: {item.get('agent_prompt')}"
            )
        prompt_text = "\n".join(lines)

        try:
            from beacon_agent.graph import sentinel_graph

            result = await sentinel_graph.ainvoke(
                {"messages": [HumanMessage(content=prompt_text)]}
            )
            messages = result.get("messages", [])
            final_text = ""
            tool_calls_made: list[str] = []

            for m in messages:
                t_calls = getattr(m, "tool_calls", None)
                if t_calls:
                    for tc in t_calls:
                        t_name = tc.get("name", "tool")
                        tool_calls_made.append(t_name)
                if getattr(m, "type", "") == "ai" and getattr(m, "content", ""):
                    content = m.content
                    if isinstance(content, str) and content.strip():
                        final_text = content.strip()
                    elif isinstance(content, list):
                        text_parts = [
                            p.get("text", "")
                            for p in content
                            if isinstance(p, dict) and p.get("type") == "text"
                        ]
                        if any(text_parts):
                            final_text = " ".join(text_parts).strip()

            task_record["status"] = "completed"
            task_record["summary"] = final_text or "Background inspection completed."
            task_record["tool_calls"] = list(dict.fromkeys(tool_calls_made))
            task_record["completed_at"] = time.time()

            self.db.log_event("sentinel.task.completed", task_record)
            await self.broker.publish("sentinel.task.completed", task_record)

        except Exception as exc:  # noqa: BLE001
            task_record["status"] = "failed"
            task_record["summary"] = f"Sentinel inspection error: {exc}"
            await self.broker.publish("sentinel.task.failed", task_record)
