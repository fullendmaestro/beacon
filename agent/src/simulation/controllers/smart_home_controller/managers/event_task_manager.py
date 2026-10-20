from __future__ import annotations

import json
import threading
import time
import urllib.request
import uuid
from typing import Any

OBJECT_DEF_MAP: dict[str, dict[str, Any]] = {
    "cup":            {"def": "OBJ_CUP",            "default_room": "Kitchen",        "pos": [-2.35, -2.15, 0.955]},
    "bottle":         {"def": "OBJ_BOTTLE",         "default_room": "Kitchen",        "pos": [-2.35, -2.45, 1.000]},
    "medicine_box":   {"def": "OBJ_MEDICINE_BOX",   "default_room": "Kitchen",        "pos": [-2.35, -2.75, 0.940]},
    "plate":          {"def": "OBJ_PLATE",          "default_room": "Kitchen",        "pos": [-2.68, -2.35, 0.915]},
    "tray":           {"def": "OBJ_TRAY",           "default_room": "Kitchen",        "pos": [-2.68, -2.70, 0.915]},
    "remote_control": {"def": "OBJ_REMOTE_CONTROL", "default_room": "Living Room",    "pos": [-5.85, -2.65, 0.565]},
    "keys":           {"def": "OBJ_KEYS",           "default_room": "Dining Room",    "pos": [-10.10, -1.63, 0.755]},
    "book":           {"def": "OBJ_BOOK",           "default_room": "Study Bedroom",  "pos": [-6.85, -12.20, 0.735]},
    "phone":          {"def": "OBJ_PHONE",          "default_room": "Master Bedroom", "pos": [-2.40, -9.80, 0.580]},
    "glasses":        {"def": "OBJ_GLASSES",        "default_room": "Kitchen",        "pos": [-1.43, -3.61, 0.755]},
}

SURFACE_PRESETS: dict[str, tuple[float, float, float, str]] = {
    "kitchen_island":  (-2.35, -2.40, 0.96, "Kitchen"),
    "breakfast_table": (-1.43, -3.61, 0.76, "Kitchen"),
    "coffee_table":    (-5.85, -2.65, 0.57, "Living Room"),
    "dining_table":    (-10.10, -1.63, 0.76, "Dining Room"),
    "study_desk":      (-6.85, -12.20, 0.74, "Study Bedroom"),
    "master_bed":      (-2.40, -9.80, 0.58, "Master Bedroom"),
    "bathroom_vanity": (-5.35, -9.98, 1.08, "Bathroom"),
    "foyer_bench":     (-2.70, -7.20, 0.45, "Foyer"),
}


def _post_tiago(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:8001{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"status": "queued_offline", "error": str(exc)}


class EventTaskManager:
    """
    Manages:
      1. Physical 3D household objects in Webots (spawning/moving/resetting props).
      2. Proactive Webots sensor edge detection & event log stream.
      3. Ambient AI (autonomous background actions) & Human-in-the-Loop (HITL) approval tasks.
    """

    def __init__(self) -> None:
        self.object_nodes: dict[str, Any] = {}
        self.object_states: dict[str, dict[str, Any]] = {}
        self.tasks: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.ambient_enabled: bool = True
        self.hitl_enabled: bool = True
        self._prev_sensor_triggered: dict[str, bool] = {}
        self._sensor_cooldowns: dict[str, float] = {}
        self._manual_sensor_overrides: dict[str, float] = {}

        for name, cfg in OBJECT_DEF_MAP.items():
            self.object_states[name] = {
                "name": name,
                "def_name": cfg["def"],
                "room": cfg["default_room"],
                "position": list(cfg["pos"]),
                "default_position": list(cfg["pos"]),
                "default_room": cfg["default_room"],
            }

        # Seed initial ambient & HITL tasks so the AI Tasks sidebar panel is rich on startup
        self._seed_initial_tasks()

    def _seed_initial_tasks(self) -> None:
        now_str = time.strftime("%H:%M:%S")
        self.tasks = [
            {
                "id": "task-hitl-porch-visitor",
                "title": "Visitor Detected at Entrance Courtyard",
                "description": (
                    "Sam (Visitor) is standing near the Front Entrance. Approve to unlock and open the "
                    "Front Entrance Door, turn on the Foyer Hallway Light, and send TIAGo to greet them."
                ),
                "category": "security",
                "mode": "hitl",
                "status": "pending_approval",
                "trigger_source": "Front Porch Motion Sensor",
                "room": "Foyer",
                "created_at": now_str,
                "executed_at": None,
                "proposed_actions": [
                    {"type": "light", "label": "Turn on Foyer Hallway Light (90%)", "light_name": "Foyer Hallway Light", "power_state": "on", "brightness": 90},
                    {"type": "door", "label": "Unlock & Open Front Entrance Door", "door_name": "Front Entrance Door", "open_state": "open", "locked": False},
                    {"type": "tiago_navigate", "label": "Dispatch TIAGo to Front Door", "room": "front_door"},
                ],
                "logs": ["[Sensor] Presence detected near Front Entrance Courtyard."],
            },
            {
                "id": "task-hitl-deliver-drink",
                "title": "Deliver Bottle from Kitchen to Living Room",
                "description": (
                    "Alex (Resident) is in the Living Room. Approve to command TIAGo to pick up the "
                    "bottle from the Kitchen Island using magnetic grasp and deliver it to the Living Room coffee table."
                ),
                "category": "errand",
                "mode": "hitl",
                "status": "pending_approval",
                "trigger_source": "Resident Comfort Assistant",
                "room": "Living Room",
                "created_at": now_str,
                "executed_at": None,
                "proposed_actions": [
                    {"type": "door", "label": "Open Kitchen Passage Door", "door_name": "Kitchen Passage Door", "open_state": "open", "locked": False},
                    {"type": "tiago_deliver", "label": "TIAGo Deliver bottle (Kitchen → Living Room)", "item": "bottle", "from_location": "kitchen", "to_location": "living_room"},
                ],
                "logs": ["[HITL] Awaiting resident confirmation before dispatching TIAGo manipulator."],
            },
            {
                "id": "task-ambient-eco-climate",
                "title": "Ambient Living Room Illumination & Eco HVAC",
                "description": (
                    "Automatically balanced Living Room lighting and radiator setpoint when resident occupancy was confirmed."
                ),
                "category": "comfort",
                "mode": "ambient",
                "status": "completed",
                "trigger_source": "Living Room Motion Sensor",
                "room": "Living Room",
                "created_at": now_str,
                "executed_at": now_str,
                "proposed_actions": [
                    {"type": "light", "label": "Set Living Room Main Light to 80%", "light_name": "Living Room Main Light", "power_state": "on", "brightness": 80},
                ],
                "logs": [
                    "[Ambient AI] Occupancy verified in Living Room.",
                    "[Ambient AI] Executed lighting balance automatically without interrupting user.",
                ],
            },
        ]

    def init_devices(self, supervisor: Any) -> None:
        for name, cfg in OBJECT_DEF_MAP.items():
            node = supervisor.getFromDef(cfg["def"])
            if node:
                self.object_nodes[name] = node
                tf = node.getField("translation")
                if tf:
                    pos = [round(v, 3) for v in tf.getSFVec3f()]
                    self.object_states[name]["position"] = pos

    def sync_object_positions(self) -> None:
        for name, node in self.object_nodes.items():
            tf = node.getField("translation")
            if tf:
                pos = [round(v, 3) for v in tf.getSFVec3f()]
                self.object_states[name]["position"] = pos
                self.object_states[name]["room"] = self._infer_object_room(pos[0], pos[1])

    @staticmethod
    def _infer_object_room(x: float, y: float) -> str:
        if x > -3.8 and y > -4.8:
            return "Kitchen"
        if x <= -3.8 and x > -8.0 and y > -6.0:
            return "Living Room"
        if x <= -8.0 and y > -6.0:
            return "Dining Room"
        if y <= -8.4 and x > -3.8:
            return "Master Bedroom"
        if y <= -8.4 and x <= -5.8:
            return "Study Bedroom"
        if y <= -8.4 and -5.8 < x <= -3.8:
            return "Bathroom"
        return "Foyer"

    def list_objects(self) -> list[dict[str, Any]]:
        self.sync_object_positions()
        surfaces = [
            {"id": k, "name": k.replace("_", " ").title(), "room": v[3], "position": [v[0], v[1], v[2]]}
            for k, v in SURFACE_PRESETS.items()
        ]
        return [
            {
                **state,
                "available_surfaces": surfaces,
            }
            for state in self.object_states.values()
        ]

    def move_object(
        self,
        object_name: str,
        surface: str | None = None,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> dict[str, Any]:
        if object_name not in self.object_states:
            return {"error": f"Unknown object '{object_name}'"}

        state = self.object_states[object_name]
        if surface and surface in SURFACE_PRESETS:
            sx, sy, sz, room_label = SURFACE_PRESETS[surface]
            # Add slight deterministic offset per object so multiple items on same surface don't overlap
            idx = list(OBJECT_DEF_MAP.keys()).index(object_name)
            offset_x = ((idx % 3) - 1) * 0.09
            offset_y = ((idx // 3) - 1) * 0.08
            target_pos = [round(sx + offset_x, 3), round(sy + offset_y, 3), round(sz, 3)]
            state["room"] = room_label
        elif x is not None and y is not None:
            tz = z if z is not None else state["position"][2]
            target_pos = [round(float(x), 3), round(float(y), 3), round(float(tz), 3)]
            state["room"] = self._infer_object_room(target_pos[0], target_pos[1])
        else:
            target_pos = list(state["default_position"])
            state["room"] = state["default_room"]

        state["position"] = target_pos
        node = self.object_nodes.get(object_name)
        if node:
            tf = node.getField("translation")
            if tf:
                tf.setSFVec3f(target_pos)

        self._record_event(
            event_type="object_moved",
            source=f"Object: {object_name}",
            message=f"Moved '{object_name}' to {state['room']} ({target_pos[0]}, {target_pos[1]}, {target_pos[2]})",
        )
        return dict(state)

    def reset_objects(self) -> list[dict[str, Any]]:
        for name, cfg in OBJECT_DEF_MAP.items():
            pos = list(cfg["pos"])
            self.object_states[name]["position"] = pos
            self.object_states[name]["room"] = cfg["default_room"]
            node = self.object_nodes.get(name)
            if node:
                tf = node.getField("translation")
                if tf:
                    tf.setSFVec3f(pos)
        self._record_event(
            event_type="objects_reset",
            source="Simulation Supervisor",
            message="Reset all 10 household objects to their default room surfaces.",
        )
        return self.list_objects()

    def _record_event(self, event_type: str, source: str, message: str, task_id: str | None = None) -> dict[str, Any]:
        evt = {
            "id": f"evt-{uuid.uuid4().hex[:8]}",
            "type": event_type,
            "source": source,
            "message": message,
            "timestamp": time.strftime("%H:%M:%S"),
            "task_id": task_id,
        }
        self.events.insert(0, evt)
        del self.events[40:]
        return evt

    def pulse_sensor_override(self, sensor_id_or_name: str, duration_sec: float = 8.0) -> None:
        self._manual_sensor_overrides[sensor_id_or_name] = time.time() + duration_sec

    def step_events(
        self,
        sensor_states: dict[str, dict[str, Any]],
        lighting: Any,
        access: Any,
        climate_appliances: Any,
    ) -> None:
        now = time.time()
        # Apply active manual sensor pulses so Webots and standalone mode both show triggered sensors
        for s_name, s_state in sensor_states.items():
            sid = s_state.get("id", "")
            override_until = max(
                self._manual_sensor_overrides.get(s_name, 0.0),
                self._manual_sensor_overrides.get(sid, 0.0),
            )
            if now < override_until:
                s_state["triggered"] = True
                if s_state.get("type") == "MotionSensor":
                    s_state["value"] = 320.0
                    s_state["state"] = "Motion Detected"
                else:
                    s_state["value"] = 120.0
                    s_state["state"] = "Low Light / Night"

            triggered = bool(s_state.get("triggered", False))
            was_triggered = self._prev_sensor_triggered.get(s_name, False)
            self._prev_sensor_triggered[s_name] = triggered

            # Rising-edge detection with cooldown
            if triggered and not was_triggered:
                last_cd = self._sensor_cooldowns.get(s_name, 0.0)
                if now - last_cd >= 12.0:
                    self._sensor_cooldowns[s_name] = now
                    self._handle_sensor_rising_edge(s_name, lighting, access, climate_appliances)

    def _handle_sensor_rising_edge(
        self,
        sensor_name: str,
        lighting: Any,
        access: Any,
        climate_appliances: Any,
    ) -> None:
        now_str = time.strftime("%H:%M:%S")

        if "Front Porch" in sensor_name:
            # Ambient action: turn on Front Porch Bollard Light automatically
            if self.ambient_enabled:
                self._execute_single_action(
                    {"type": "light", "light_name": "Front Porch Bollard Light", "power_state": "on", "brightness": 100},
                    lighting,
                    access,
                    climate_appliances,
                )
                amb_task = {
                    "id": f"task-amb-{uuid.uuid4().hex[:6]}",
                    "title": "Porch Courtesy Illumination",
                    "description": "Front Porch Motion Sensor triggered — automatically turned on Front Porch Bollard Light.",
                    "category": "comfort",
                    "mode": "ambient",
                    "status": "completed",
                    "trigger_source": sensor_name,
                    "room": "Exterior",
                    "created_at": now_str,
                    "executed_at": now_str,
                    "proposed_actions": [
                        {"type": "light", "label": "Turn on Front Porch Bollard Light (100%)", "light_name": "Front Porch Bollard Light", "power_state": "on", "brightness": 100}
                    ],
                    "logs": [f"[{now_str}] Sensor edge detected on {sensor_name}.", f"[{now_str}] Ambient AI turned on Front Porch Bollard Light."],
                }
                self.tasks.insert(0, amb_task)

            # HITL task: ask resident whether to unlock Front Entrance Door & send TIAGo to greet
            if self.hitl_enabled:
                hitl_task = {
                    "id": f"task-hitl-{uuid.uuid4().hex[:6]}",
                    "title": "Front Porch Visitor Greeting & Door Unlock",
                    "description": "Motion detected at the Front Porch. Approve to unlock & open the Front Entrance Door and dispatch TIAGo to the Foyer entrance.",
                    "category": "security",
                    "mode": "hitl",
                    "status": "pending_approval",
                    "trigger_source": sensor_name,
                    "room": "Foyer",
                    "created_at": now_str,
                    "executed_at": None,
                    "proposed_actions": [
                        {"type": "door", "label": "Unlock & Open Front Entrance Door", "door_name": "Front Entrance Door", "open_state": "open", "locked": False},
                        {"type": "light", "label": "Turn on Foyer Hallway Light", "light_name": "Foyer Hallway Light", "power_state": "on", "brightness": 95},
                        {"type": "tiago_navigate", "label": "Navigate TIAGo to Front Entrance", "room": "front_door"},
                    ],
                    "logs": [f"[{now_str}] Waiting for human approval to unlock Front Entrance Door."],
                }
                self.tasks.insert(0, hitl_task)
                self._record_event("sensor_trigger", sensor_name, "Front Porch motion detected — created Ambient light action & HITL door unlock request.", hitl_task["id"])

        elif "Driveway Gate" in sensor_name:
            if self.ambient_enabled:
                self._execute_single_action(
                    {"type": "light", "light_name": "Driveway Bollard Light", "power_state": "on", "brightness": 100},
                    lighting,
                    access,
                    climate_appliances,
                )
            if self.hitl_enabled:
                hitl_task = {
                    "id": f"task-hitl-{uuid.uuid4().hex[:6]}",
                    "title": "Driveway Gate Arrival — Open Gate & Garage?",
                    "description": "Motion detected at the Driveway Gate sensor beam. Approve to open the sliding Driveway Gate and Overhead Garage Door.",
                    "category": "security",
                    "mode": "hitl",
                    "status": "pending_approval",
                    "trigger_source": sensor_name,
                    "room": "Exterior",
                    "created_at": now_str,
                    "executed_at": None,
                    "proposed_actions": [
                        {"type": "door", "label": "Unlock & Open Driveway Gate", "door_name": "Driveway Gate", "open_state": "open", "locked": False},
                        {"type": "door", "label": "Open Garage Door", "door_name": "Garage Door", "open_state": "open", "locked": False},
                        {"type": "light", "label": "Turn on Garage Ceiling Light", "light_name": "Garage Ceiling Light", "power_state": "on", "brightness": 100},
                    ],
                    "logs": [f"[{now_str}] Driveway Gate sensor triggered; awaiting HITL approval to open perimeter barriers."],
                }
                self.tasks.insert(0, hitl_task)
                self._record_event("sensor_trigger", sensor_name, "Driveway Gate motion detected — queued HITL barrier approval.", hitl_task["id"])

        elif "Hallway" in sensor_name:
            if self.ambient_enabled:
                self._execute_single_action(
                    {"type": "light", "light_name": "West Corridor Light", "power_state": "on", "brightness": 85},
                    lighting,
                    access,
                    climate_appliances,
                )
                amb_task = {
                    "id": f"task-amb-{uuid.uuid4().hex[:6]}",
                    "title": "Corridor Motion Path Lighting",
                    "description": "Hallway Motion Sensor triggered — Ambient AI illuminated West Corridor Light to 85%.",
                    "category": "comfort",
                    "mode": "ambient",
                    "status": "completed",
                    "trigger_source": sensor_name,
                    "room": "Corridor",
                    "created_at": now_str,
                    "executed_at": now_str,
                    "proposed_actions": [
                        {"type": "light", "label": "Turn on West Corridor Light (85%)", "light_name": "West Corridor Light", "power_state": "on", "brightness": 85}
                    ],
                    "logs": [f"[{now_str}] Ambient AI illuminated corridor on motion."],
                }
                self.tasks.insert(0, amb_task)
                self._record_event("sensor_trigger", sensor_name, "Hallway motion detected — Ambient AI turned on corridor lighting.", amb_task["id"])

        elif "Living Room" in sensor_name:
            if self.ambient_enabled:
                self._execute_single_action(
                    {"type": "light", "light_name": "Living Room Main Light", "power_state": "on", "brightness": 85},
                    lighting,
                    access,
                    climate_appliances,
                )
                self._execute_single_action(
                    {"type": "light", "light_name": "Living Room Corner Lamp", "power_state": "on", "brightness": 75},
                    lighting,
                    access,
                    climate_appliances,
                )
                amb_task = {
                    "id": f"task-amb-{uuid.uuid4().hex[:6]}",
                    "title": "Living Room Occupancy Comfort Scene",
                    "description": "Living Room Motion Sensor detected resident presence — Ambient AI turned on Living Room lights.",
                    "category": "comfort",
                    "mode": "ambient",
                    "status": "completed",
                    "trigger_source": sensor_name,
                    "room": "Living Room",
                    "created_at": now_str,
                    "executed_at": now_str,
                    "proposed_actions": [
                        {"type": "light", "label": "Turn on Living Room Main Light (85%)", "light_name": "Living Room Main Light", "power_state": "on", "brightness": 85},
                        {"type": "light", "label": "Turn on Living Room Corner Lamp (75%)", "light_name": "Living Room Corner Lamp", "power_state": "on", "brightness": 75},
                    ],
                    "logs": [f"[{now_str}] Ambient AI activated Living Room comfort lighting."],
                }
                self.tasks.insert(0, amb_task)
                self._record_event("sensor_trigger", sensor_name, "Living Room motion detected — Ambient AI adjusted room lighting.", amb_task["id"])

        elif "Daylight" in sensor_name:
            if self.ambient_enabled:
                for b_id in access.blind_states:
                    access.execute_blind_cmd({"blind_id": b_id, "position": 0})
                for l_name in ("Front Porch Bollard Light", "Driveway Bollard Light", "Patio Lounge Lamp"):
                    self._execute_single_action(
                        {"type": "light", "light_name": l_name, "power_state": "on", "brightness": 75},
                        lighting,
                        access,
                        climate_appliances,
                    )
                amb_task = {
                    "id": f"task-amb-{uuid.uuid4().hex[:6]}",
                    "title": "Dusk Exterior Lighting & Privacy Shades",
                    "description": "Exterior Daylight Sensor detected low ambient light (<300 lux) — closed motorized blinds and enabled exterior bollards.",
                    "category": "energy",
                    "mode": "ambient",
                    "status": "completed",
                    "trigger_source": sensor_name,
                    "room": "Whole Home",
                    "created_at": now_str,
                    "executed_at": now_str,
                    "proposed_actions": [
                        {"type": "blind_all", "label": "Close all 4 motorized window blinds (0%)", "position": 0},
                        {"type": "light", "label": "Turn on Exterior Bollard & Patio Lights", "light_name": "Front Porch Bollard Light", "power_state": "on", "brightness": 75},
                    ],
                    "logs": [f"[{now_str}] Low daylight detected; closed blinds and enabled exterior lights."],
                }
                self.tasks.insert(0, amb_task)

            if self.hitl_enabled:
                hitl_task = {
                    "id": f"task-hitl-{uuid.uuid4().hex[:6]}",
                    "title": "Nightfall Security Patrol & Perimeter Lockdown",
                    "description": "Exterior daylight dropped to night levels. Approve to lock all exterior doors and dispatch TIAGo on a multi-room security patrol.",
                    "category": "security",
                    "mode": "hitl",
                    "status": "pending_approval",
                    "trigger_source": sensor_name,
                    "room": "Whole Home",
                    "created_at": now_str,
                    "executed_at": None,
                    "proposed_actions": [
                        {"type": "lock_all_doors", "label": "Close & Lock All Perimeter Doors"},
                        {"type": "tiago_patrol", "label": "Dispatch TIAGo on Multi-Room Security Patrol", "rooms": ["living_room", "kitchen", "master_bedroom"]},
                    ],
                    "logs": [f"[{now_str}] Nightfall detected; awaiting human approval for full security patrol."],
                }
                self.tasks.insert(0, hitl_task)
                self._record_event("sensor_trigger", sensor_name, "Low light detected — Ambient shades closed & HITL security patrol proposed.", hitl_task["id"])

        del self.tasks[30:]

    def _execute_single_action(
        self,
        action: dict[str, Any],
        lighting: Any,
        access: Any,
        climate_appliances: Any,
    ) -> str:
        atype = action.get("type", "")
        if atype == "light":
            target_name = action.get("light_name", "").lower()
            for lid, lstate in lighting.light_states.items():
                if target_name in lstate["name"].lower():
                    lighting.execute_cmd({
                        "node_id": lid,
                        "action": "set_state",
                        "power_state": action.get("power_state", "on"),
                        "brightness": action.get("brightness", 85),
                        "color": action.get("color"),
                    })
                    return f"Light '{lstate['name']}' set to {action.get('power_state', 'on')}"
        elif atype == "door":
            target_name = action.get("door_name", "").lower()
            for did, dstate in access.door_states.items():
                if target_name in dstate["name"].lower() or target_name == did.lower():
                    access.execute_door_cmd({
                        "door_id": did,
                        "open_state": action.get("open_state", "open"),
                        "locked": action.get("locked", False),
                        "position": 100 if action.get("open_state", "open") == "open" else 0,
                    })
                    return f"Door '{dstate['name']}' set to {action.get('open_state', 'open')}"
        elif atype == "lock_all_doors":
            for did in access.door_states:
                access.execute_door_cmd({"door_id": did, "open_state": "closed", "locked": True, "position": 0})
            return "Closed and locked all doors and gates"
        elif atype == "blind_all":
            pos = int(action.get("position", 0))
            for bid in access.blind_states:
                access.execute_blind_cmd({"blind_id": bid, "position": pos})
            return f"Set all window blinds to {pos}%"
        elif atype == "appliance":
            app_id = action.get("appliance_id", "")
            if app_id in climate_appliances.appliance_states:
                climate_appliances.update_appliance(app_id, action.get("power_state", "off"), action.get("mode"))
                return f"Updated appliance '{app_id}'"
        elif atype == "tiago_navigate":
            room = action.get("room", "foyer")
            threading.Thread(target=_post_tiago, args=("/navigate/room", {"room": room}), daemon=True).start()
            return f"Dispatched TIAGo to {room}"
        elif atype == "tiago_fetch":
            item = action.get("item", "cup")
            from_loc = action.get("from_location", "kitchen")
            threading.Thread(target=_post_tiago, args=("/errand/fetch", {"item": item, "from_location": from_loc}), daemon=True).start()
            return f"Started TIAGo fetch errand: {item} from {from_loc}"
        elif atype == "tiago_deliver":
            item = action.get("item", "bottle")
            from_loc = action.get("from_location", "kitchen")
            to_loc = action.get("to_location", "living_room")
            threading.Thread(
                target=_post_tiago,
                args=("/errand/deliver", {"item": item, "from_location": from_loc, "to_location": to_loc}),
                daemon=True,
            ).start()
            return f"Started TIAGo delivery errand: {item} from {from_loc} to {to_loc}"
        elif atype == "tiago_patrol":
            rooms = action.get("rooms", ["living_room", "kitchen", "master_bedroom"])
            threading.Thread(target=_post_tiago, args=("/errand/patrol", {"rooms": rooms}), daemon=True).start()
            return f"Started TIAGo security patrol across {', '.join(rooms)}"
        return f"Executed {atype}"

    def approve_task(
        self,
        task_id: str,
        lighting: Any,
        access: Any,
        climate_appliances: Any,
    ) -> dict[str, Any]:
        for t in self.tasks:
            if t["id"] == task_id:
                t["status"] = "running"
                now_str = time.strftime("%H:%M:%S")
                t["logs"].append(f"[{now_str}] Approved by human operator — executing actions...")
                for act in t.get("proposed_actions", []):
                    res_msg = self._execute_single_action(act, lighting, access, climate_appliances)
                    t["logs"].append(f"[{now_str}] {res_msg}")
                t["status"] = "completed"
                t["executed_at"] = now_str
                self._record_event("task_approved", "Human-in-the-Loop", f"Approved & executed task: {t['title']}", task_id)
                return dict(t)
        return {"error": f"Task '{task_id}' not found"}

    def reject_task(self, task_id: str) -> dict[str, Any]:
        for t in self.tasks:
            if t["id"] == task_id:
                now_str = time.strftime("%H:%M:%S")
                t["status"] = "rejected"
                t["executed_at"] = now_str
                t["logs"].append(f"[{now_str}] Dismissed by human operator.")
                self._record_event("task_rejected", "Human-in-the-Loop", f"Dismissed task: {t['title']}", task_id)
                return dict(t)
        return {"error": f"Task '{task_id}' not found"}

    def create_custom_task(
        self,
        title: str,
        description: str,
        category: str = "errand",
        mode: str = "hitl",
        trigger_source: str = "Beacon AI Agent",
        room: str = "Living Room",
        proposed_actions: list[dict[str, Any]] | None = None,
        lighting: Any = None,
        access: Any = None,
        climate_appliances: Any = None,
    ) -> dict[str, Any]:
        now_str = time.strftime("%H:%M:%S")
        actions = proposed_actions or []
        is_ambient = mode == "ambient" and self.ambient_enabled
        task: dict[str, Any] = {
            "id": f"task-{mode}-{uuid.uuid4().hex[:6]}",
            "title": title,
            "description": description,
            "category": category,
            "mode": mode,
            "status": "completed" if is_ambient else "pending_approval",
            "trigger_source": trigger_source,
            "room": room,
            "created_at": now_str,
            "executed_at": now_str if is_ambient else None,
            "proposed_actions": actions,
            "logs": [f"[{now_str}] Created by {trigger_source} ({mode.upper()})."],
        }
        if is_ambient and lighting and access and climate_appliances:
            for act in actions:
                msg = self._execute_single_action(act, lighting, access, climate_appliances)
                task["logs"].append(f"[{now_str}] {msg}")
        self.tasks.insert(0, task)
        del self.tasks[30:]
        self._record_event("task_created", trigger_source, f"Created {mode.upper()} task: {title}", task["id"])
        return dict(task)

    def trigger_scenario_event(
        self,
        scenario: str,
        lighting: Any,
        access: Any,
        climate_appliances: Any,
        humans: Any,
        sensor_states: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Trigger a rich Webots + AI scenario from the /demo Control Center or Agent."""
        now_str = time.strftime("%H:%M:%S")
        if scenario == "visitor_front_door":
            humans.execute_cmd({"human_id": "guest", "action": "goto_location", "location": "front_porch"})
            self.pulse_sensor_override("Front Porch Motion Sensor", 10.0)
            self._sensor_cooldowns.pop("Front Porch Motion Sensor", None)
            self.step_events(sensor_states, lighting, access, climate_appliances)
            return {"status": "triggered", "scenario": scenario, "message": "Sam (Visitor) walked to Front Porch and triggered Front Porch Motion Sensor."}

        if scenario == "driveway_arrival":
            humans.execute_cmd({"human_id": "guest", "action": "goto_location", "location": "driveway_gate"})
            self.pulse_sensor_override("Driveway Gate Motion Sensor", 10.0)
            self._sensor_cooldowns.pop("Driveway Gate Motion Sensor", None)
            self.step_events(sensor_states, lighting, access, climate_appliances)
            return {"status": "triggered", "scenario": scenario, "message": "Triggered Driveway Gate arrival sensor and queued HITL gate approval."}

        if scenario == "resident_living_room":
            humans.execute_cmd({"human_id": "resident", "action": "goto_location", "location": "living_room"})
            self.pulse_sensor_override("Living Room Motion Sensor", 10.0)
            self._sensor_cooldowns.pop("Living Room Motion Sensor", None)
            self.step_events(sensor_states, lighting, access, climate_appliances)
            return {"status": "triggered", "scenario": scenario, "message": "Alex (Resident) entered Living Room — Ambient AI adjusted lighting."}

        if scenario == "nightfall_lockdown":
            climate_appliances.execute_environment_cmd({"time_of_day": "night"})
            self.pulse_sensor_override("Exterior Daylight Sensor", 10.0)
            self._sensor_cooldowns.pop("Exterior Daylight Sensor", None)
            self.step_events(sensor_states, lighting, access, climate_appliances)
            return {"status": "triggered", "scenario": scenario, "message": "Simulated nightfall — Ambient AI closed blinds & proposed HITL security patrol."}

        if scenario == "kitchen_hazard":
            if "induction_cooktop" in climate_appliances.appliance_states:
                climate_appliances.update_appliance("induction_cooktop", "on", "Boost Sear")
            task = self.create_custom_task(
                title="Unattended Kitchen Cooktop Alert",
                description="Induction Cooktop is running on Boost Sear with no resident in the Kitchen. Approve to turn off cooktop and send TIAGo to inspect Kitchen.",
                category="safety",
                mode="hitl",
                trigger_source="Appliance Safety Monitor",
                room="Kitchen",
                proposed_actions=[
                    {"type": "appliance", "label": "Turn Off Induction Cooktop", "appliance_id": "induction_cooktop", "power_state": "off", "mode": "Off"},
                    {"type": "tiago_navigate", "label": "Dispatch TIAGo to Inspect Kitchen", "room": "kitchen"},
                ],
            )
            return {"status": "triggered", "scenario": scenario, "task": task, "message": "Triggered unattended cooktop safety alert (HITL)."}

        if scenario == "deliver_medicine":
            task = self.create_custom_task(
                title="Medication Reminder & TIAGo Delivery",
                description="Scheduled evening medication reminder for Alex. Approve to dispatch TIAGo to grasp medicine_box from Kitchen and deliver to Master Bedroom.",
                category="errand",
                mode="hitl",
                trigger_source="Health & Errand Scheduler",
                room="Master Bedroom",
                proposed_actions=[
                    {"type": "door", "label": "Open Kitchen & Master Bedroom Doors", "door_name": "Kitchen Passage Door", "open_state": "open", "locked": False},
                    {"type": "tiago_deliver", "label": "Deliver medicine_box (Kitchen → Master Bedroom)", "item": "medicine_box", "from_location": "kitchen", "to_location": "master_bedroom"},
                ],
            )
            return {"status": "triggered", "scenario": scenario, "task": task, "message": "Queued HITL medication delivery task."}

        return {"error": f"Unknown scenario '{scenario}'"}

    def get_state(self) -> dict[str, Any]:
        pending_count = sum(1 for t in self.tasks if t["status"] == "pending_approval")
        ambient_count = sum(1 for t in self.tasks if t["mode"] == "ambient")
        return {
            "ambient_enabled": self.ambient_enabled,
            "hitl_enabled": self.hitl_enabled,
            "pending_hitl_count": pending_count,
            "ambient_completed_count": ambient_count,
            "tasks": list(self.tasks),
            "events": list(self.events),
        }
