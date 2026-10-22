"""SQLite WAL connection manager, strict registry queries, and navigation graph engine."""

from __future__ import annotations

import heapq
import json
import math
import os
import re
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import Any

from .models import (
     SCHEMA_DDL,
    ColorUtils,
    DeviceProvisionRequest,
    NavNodeProvisionRequest,
)
from .seed_default_estate import seed_estate_tables

ROOM_ALIASES: dict[str, str] = {
    "docking": "foyer",
    "bedroom": "master_bedroom",
    "master": "master_bedroom",
    "study": "study_bedroom",
    "living": "living_room",
    "dining": "dining_room",
    "utility": "utility_room",
}


def _point_in_polygon(x: float, y: float, poly: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon check with boundary tolerance."""
    if not poly:
        return False
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    if min(xs) - 0.25 <= x <= max(xs) + 0.25 and min(ys) - 0.25 <= y <= max(ys) + 0.25:
        inside = False
        n = len(poly)
        p1x, p1y = poly[0][0], poly[0][1]
        for i in range(1, n + 1):
            p2x, p2y = poly[i % n][0], poly[i % n][1]
            if y > min(p1y, p2y) and y <= max(p1y, p2y) and x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
            p1x, p1y = p2x, p2y
        if inside:
            return True
        # Check bounding rectangle for axis-aligned room boxes
        if min(xs) - 0.2 <= x <= max(xs) + 0.2 and min(ys) - 0.2 <= y <= max(ys) + 0.2:
            return True
    return False


def _point_to_segment_dist(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


class DatabaseManager:
    """Thread-safe SQLite WAL database manager for Beacon Core Hub."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            env_path = os.getenv("BEACON_DB_PATH")
            if env_path:
                db_path = Path(env_path)
            else:
                db_path = Path(__file__).resolve().parents[3] / "beacon_state.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA_DDL)
            seed_estate_tables(self._conn)

    def _row_to_device(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "wbt_name": row["wbt_name"],
            "wbt_def": row["wbt_def"],
            "domain": row["domain"],
            "proto_type": row["proto_type"],
            "room_id": row["room_id"],
            "room_name": row["room_name"] if "room_name" in row.keys() else None,
            "translation": json.loads(row["translation"]),
            "rotation": json.loads(row["rotation"]),
            "config": json.loads(row["config_json"]),
            "controller_name": row["controller_name"],
            "online": bool(row["online"]),
            "desired_state": json.loads(row["desired_state"]),
            "reported_state": json.loads(row["reported_state"]),
        }

    # --- Strict Device Lookup ---

    def strict_lookup(self, identifier: str, domain: str | None = None) -> dict[str, Any] | None:
        """
        Strict exact-match predicate on `d.id = :identifier OR d.wbt_name = :identifier`.
        Case-sensitive, zero substring matching, zero room-name guessing.
        """
        if not identifier:
            return None
        with self._lock:
            if domain:
                cur = self._conn.execute(
                    """
                    SELECT d.*, s.online, s.desired_state, s.reported_state, r.name as room_name
                    FROM devices d
                    JOIN device_states s ON d.id = s.device_id
                    LEFT JOIN rooms r ON d.room_id = r.id
                    WHERE (d.id = :identifier OR d.wbt_name = :identifier)
                      AND d.domain = :domain
                    """,
                    {"identifier": identifier, "domain": domain},
                )
            else:
                cur = self._conn.execute(
                    """
                    SELECT d.*, s.online, s.desired_state, s.reported_state, r.name as room_name
                    FROM devices d
                    JOIN device_states s ON d.id = s.device_id
                    LEFT JOIN rooms r ON d.room_id = r.id
                    WHERE d.id = :identifier OR d.wbt_name = :identifier
                    """,
                    {"identifier": identifier},
                )
            row = cur.fetchone()
            return self._row_to_device(row) if row else None

    def list_devices(
        self, domain: str | None = None, room_id: str | None = None
    ) -> list[dict[str, Any]]:
        query = """
            SELECT d.*, s.online, s.desired_state, s.reported_state, r.name as room_name
            FROM devices d
            JOIN device_states s ON d.id = s.device_id
            LEFT JOIN rooms r ON d.room_id = r.id
            WHERE 1=1
        """
        params: dict[str, Any] = {}
        if domain:
            query += " AND d.domain = :domain"
            params["domain"] = domain
        if room_id:
            query += " AND d.room_id = :room_id"
            params["room_id"] = room_id
        query += " ORDER BY d.created_at ASC, d.id ASC"
        with self._lock:
            cur = self._conn.execute(query, params)
            return [self._row_to_device(r) for r in cur.fetchall()]

    # --- Room & Polygon Inference ---

    def list_rooms(self) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute("SELECT id, name, polygon_2d FROM rooms ORDER BY id ASC")
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "polygon_2d": json.loads(r["polygon_2d"]),
                }
                for r in cur.fetchall()
            ]

    def infer_room_id(self, x: float, y: float) -> str:
        rooms = self.list_rooms()
        for r in rooms:
            if _point_in_polygon(x, y, r["polygon_2d"]):
                return r["id"]
        # Fallback to closest polygon centroid
        best_id = "foyer"
        best_dist = float("inf")
        for r in rooms:
            poly = r["polygon_2d"]
            if poly:
                cx = sum(p[0] for p in poly) / len(poly)
                cy = sum(p[1] for p in poly) / len(poly)
                d = math.hypot(x - cx, y - cy)
                if d < best_dist:
                    best_dist = d
                    best_id = r["id"]
        return best_id

    # --- Dynamic Device Provisioning & Removal ---

    def provision_device(self, req: DeviceProvisionRequest) -> dict[str, Any]:
        slug = re.sub(r"[^a-z0-9]+", "_", req.wbt_name.lower()).strip("_")
        dev_id = req.id or f"dev_{req.domain}_{slug}_{uuid.uuid4().hex[:4]}"
        wbt_def = req.wbt_def or f"DEV_{slug.upper()}_{uuid.uuid4().hex[:4].upper()}"
        room_id = req.room_id or self.infer_room_id(req.translation[0], req.translation[1])

        default_controllers = {
            "light": "LightingBridgeWorker",
            "door": "BarrierActuatorWorker",
            "blind": "BarrierActuatorWorker",
            "climate": "ClimateBridgeWorker",
            "appliance": "iot_device_controller",
            "sensor": "iot_device_controller",
            "camera": "iot_device_controller",
        }
        controller_name = req.controller_name or default_controllers.get(
            req.domain, "iot_device_controller"
        )

        # Normalize initial state by domain
        init_state = dict(req.initial_state)
        cfg = dict(req.config)
        if req.domain == "light":
            p_state = str(init_state.get("power_state", init_state.get("state", "on"))).lower()
            is_on = p_state == "on"
            brightness = int(init_state.get("brightness", 100 if is_on else 0))
            col_raw = init_state.get("color", cfg.get("pointLightColor", "#ffffff"))
            rgb = ColorUtils.parse(col_raw)
            hex_col = ColorUtils.to_hex(rgb)
            max_int = float(cfg.get("maxIntensity", 3.0))
            intensity = round((brightness / 100.0) * max_int, 2) if is_on else 0.0
            init_state = {
                "state": "On" if is_on else "Off",
                "power_state": "on" if is_on else "off",
                "brightness": brightness,
                "color": hex_col,
                "color_rgb": rgb,
                "intensity": intensity,
                "metadata": f"Intensity at {intensity:.1f}",
            }
            cfg.setdefault("pointLightColor", rgb)
            cfg.setdefault("maxIntensity", max_int)
            cfg.setdefault("pointLightRadius", 4.5)
        elif req.domain == "door":
            pos = int(init_state.get("position", 0))
            locked = bool(init_state.get("locked", False))
            state_str = "Open" if pos > 0 else "Closed"
            init_state = {
                "state": state_str,
                "position": pos,
                "locked": locked,
                "type": req.proto_type,
                "metadata": f"{'Locked' if locked else 'Unlocked'} • {state_str} ({pos}%)",
            }
            cfg.setdefault("axis", "z")
            cfg.setdefault("closed_z", req.translation[2])
            cfg.setdefault("open_z", req.translation[2] + 2.25)
        elif req.domain == "blind":
            pos = int(init_state.get("position", 0))
            state_str = "Open" if pos > 0 else "Closed"
            room_label = room_id.replace("_", " ").title()
            init_state = {
                "state": state_str,
                "position": pos,
                "room": room_label,
                "type": "MotorizedBlind",
                "metadata": f"{room_label} • {pos}% Open",
            }
            cfg.setdefault("closed_z", 1.25)
            cfg.setdefault("open_z", 2.28)
        elif req.domain == "climate":
            mode = str(init_state.get("mode", "eco")).lower()
            target_t = float(init_state.get("target_temp", 22.0))
            curr_t = float(init_state.get("current_temp", 21.5))
            state_str = "Off" if mode == "off" else "On"
            init_state = {
                "state": state_str,
                "mode": mode,
                "current_temp": curr_t,
                "target_temp": target_t,
                "type": req.proto_type,
                "metadata": f"{mode.title()} • Target {target_t:.1f}°C",
            }
        elif req.domain == "appliance":
            rated_w = float(cfg.get("rated_watts", init_state.get("rated_watts", 150.0)))
            is_on = str(init_state.get("state", init_state.get("power_state", "On"))).lower() == "on"
            mode = str(init_state.get("mode", "Active" if is_on else "Off"))
            room_label = room_id.replace("_", " ").title()
            init_state = {
                "state": "On" if is_on else "Off",
                "mode": mode,
                "power_watts": rated_w if is_on else 2.5,
                "rated_watts": rated_w,
                "type": req.proto_type,
                "room": room_label,
            }
        elif req.domain == "sensor":
            s_type = "DaylightSensor" if req.proto_type == "LightSensor" else "MotionSensor"
            init_state = {
                "type": s_type,
                "state": "Clear" if s_type == "MotionSensor" else "Daylight",
                "value": float(init_state.get("value", 1000.0 if s_type == "MotionSensor" else 850.0)),
                "triggered": bool(init_state.get("triggered", False)),
            }
            cfg.setdefault("range_m", 2.8)
        elif req.domain == "camera":
            w = int(cfg.get("width", 640))
            h = int(cfg.get("height", 480))
            init_state = {
                "state": "Online",
                "metadata": f"Live • {w}x{h}",
                "type": "Camera",
            }

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO devices (
                    id, wbt_name, wbt_def, domain, proto_type, room_id,
                    translation, rotation, config_json, controller_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dev_id,
                    req.wbt_name,
                    wbt_def,
                    req.domain,
                    req.proto_type,
                    room_id,
                    json.dumps(req.translation),
                    json.dumps(req.rotation),
                    json.dumps(cfg),
                    controller_name,
                ),
            )
            state_str_json = json.dumps(init_state)
            self._conn.execute(
                """
                INSERT INTO device_states (device_id, online, desired_state, reported_state)
                VALUES (?, 1, ?, ?)
                """,
                (dev_id, state_str_json, state_str_json),
            )

            # If a door is added near a navigation edge threshold, automatically link blocking_device_id
            if req.domain == "door":
                self._auto_link_door_to_nav_edges(dev_id, req.translation[0], req.translation[1])

            self._conn.commit()

        rec = self.strict_lookup(dev_id)
        assert rec is not None
        return rec

    def _auto_link_door_to_nav_edges(self, door_id: str, dx: float, dy: float) -> None:
        cur = self._conn.execute(
            """
            SELECT e.id, n1.x as x1, n1.y as y1, n2.x as x2, n2.y as y2
            FROM nav_edges e
            JOIN nav_nodes n1 ON e.from_node = n1.id
            JOIN nav_nodes n2 ON e.to_node = n2.id
            """
        )
        for edge in cur.fetchall():
            dist = _point_to_segment_dist(dx, dy, edge["x1"], edge["y1"], edge["x2"], edge["y2"])
            if dist <= 0.65:
                self._conn.execute(
                    "UPDATE nav_edges SET blocking_device_id = ? WHERE id = ?",
                    (door_id, edge["id"]),
                )

    def remove_device(self, identifier: str) -> dict[str, Any] | None:
        rec = self.strict_lookup(identifier)
        if not rec:
            return None
        with self._lock:
            self._conn.execute("DELETE FROM devices WHERE id = ?", (rec["id"],))
            self._conn.commit()
        return rec

    # --- State Updates ---

    def update_desired_state(self, device_id: str, desired_patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT desired_state FROM device_states WHERE device_id = ?", (device_id,)
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Device state not found for {device_id}")
            current = json.loads(row["desired_state"])
            current.update({k: v for k, v in desired_patch.items() if v is not None})
            self._conn.execute(
                """
                UPDATE device_states
                SET desired_state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE device_id = ?
                """,
                (json.dumps(current), device_id),
            )
            self._conn.commit()
            return current

    def update_reported_state(
        self,
        device_id: str,
        reported_patch: dict[str, Any],
        also_sync_desired: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT desired_state, reported_state FROM device_states WHERE device_id = ?",
                (device_id,),
            )
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Device state not found for {device_id}")
            rep = json.loads(row["reported_state"])
            rep.update({k: v for k, v in reported_patch.items() if v is not None})
            if also_sync_desired:
                des = json.loads(row["desired_state"])
                des.update({k: v for k, v in reported_patch.items() if v is not None})
                self._conn.execute(
                    """
                    UPDATE device_states
                    SET desired_state = ?, reported_state = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE device_id = ?
                    """,
                    (json.dumps(des), json.dumps(rep), device_id),
                )
            else:
                self._conn.execute(
                    """
                    UPDATE device_states
                    SET reported_state = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE device_id = ?
                    """,
                    (json.dumps(rep), device_id),
                )
            self._conn.commit()
            return rep

    # --- Domain Projections for Frontend & MCP ---

    def format_light(self, dev: dict[str, Any]) -> dict[str, Any]:
        st = dev["reported_state"]
        is_on = st.get("state", "On") == "On"
        return {
            "id": dev["id"],
            "device_id": dev["id"],
            "wbt_name": dev["wbt_name"],
            "name": dev["wbt_name"],
            "room_id": dev["room_id"],
            "type": dev["proto_type"],
            "state": "On" if is_on else "Off",
            "power_state": "on" if is_on else "off",
            "brightness": int(st.get("brightness", 100)) if is_on else 0,
            "color": st.get("color", "#ffffff"),
            "color_rgb": st.get("color_rgb", [1.0, 1.0, 1.0]),
            "intensity": float(st.get("intensity", 0.0)),
            "translation": dev["translation"],
            "metadata": st.get("metadata", f"Intensity at {float(st.get('intensity', 0.0)):.1f}"),
        }

    def format_door(self, dev: dict[str, Any]) -> dict[str, Any]:
        st = dev["reported_state"]
        pos = int(st.get("position", 0))
        locked = bool(st.get("locked", False))
        state_str = "Open" if pos > 0 else "Closed"
        return {
            "id": dev["id"],
            "wbt_name": dev["wbt_name"],
            "name": dev["wbt_name"],
            "room_id": dev["room_id"],
            "type": dev["proto_type"],
            "state": state_str,
            "position": pos,
            "locked": locked,
            "translation": dev["translation"],
            "rotation": dev["rotation"],
            "metadata": f"{'Locked' if locked else 'Unlocked'} • {state_str} ({pos}%)",
        }

    def format_blind(self, dev: dict[str, Any]) -> dict[str, Any]:
        st = dev["reported_state"]
        pos = int(st.get("position", 0))
        state_str = "Open" if pos > 0 else "Closed"
        room_name = dev.get("room_name") or st.get("room") or "Home"
        return {
            "id": dev["id"],
            "wbt_name": dev["wbt_name"],
            "name": dev["wbt_name"],
            "room": room_name,
            "room_id": dev["room_id"],
            "type": "MotorizedBlind",
            "state": state_str,
            "position": pos,
            "translation": dev["translation"],
            "metadata": f"{room_name} • {pos}% Open",
        }

    def format_climate(self, dev: dict[str, Any]) -> dict[str, Any]:
        st = dev["reported_state"]
        mode = str(st.get("mode", "eco")).lower()
        target_t = float(st.get("target_temp", 22.0))
        curr_t = float(st.get("current_temp", 21.5))
        state_str = "Off" if mode == "off" or st.get("state") == "Off" else "On"
        return {
            "id": dev["id"],
            "wbt_name": dev["wbt_name"],
            "name": dev["wbt_name"],
            "room_id": dev["room_id"],
            "type": dev["proto_type"],
            "state": state_str,
            "mode": mode,
            "current_temp": round(curr_t, 1),
            "target_temp": round(target_t, 1),
            "translation": dev["translation"],
            "metadata": f"{mode.title()} • Target {target_t:.1f}°C",
        }

    def format_appliance(self, dev: dict[str, Any]) -> dict[str, Any]:
        st = dev["reported_state"]
        is_on = st.get("state", "Off") == "On"
        rated_w = float(st.get("rated_watts", dev["config"].get("rated_watts", 100.0)))
        power_w = float(st.get("power_watts", rated_w if is_on else 2.5))
        room_name = dev.get("room_name") or st.get("room") or "Home"
        return {
            "id": dev["id"],
            "wbt_name": dev["wbt_name"],
            "name": dev["wbt_name"],
            "type": dev["proto_type"],
            "room": room_name,
            "room_id": dev["room_id"],
            "state": "On" if is_on else "Off",
            "mode": str(st.get("mode", "Active" if is_on else "Off")),
            "power_watts": round(power_w, 1),
            "rated_watts": round(rated_w, 1),
            "translation": dev["translation"],
        }

    def format_sensor(self, dev: dict[str, Any]) -> dict[str, Any]:
        st = dev["reported_state"]
        return {
            "id": dev["id"],
            "wbt_name": dev["wbt_name"],
            "name": dev["wbt_name"],
            "room_id": dev["room_id"],
            "type": st.get("type", "MotionSensor"),
            "state": st.get("state", "Clear"),
            "value": round(float(st.get("value", 1000.0)), 1),
            "triggered": bool(st.get("triggered", False)),
            "translation": dev["translation"],
        }

    def format_camera(self, dev: dict[str, Any]) -> dict[str, Any]:
        st = dev["reported_state"]
        return {
            "id": dev["id"],
            "wbt_name": dev["wbt_name"],
            "name": dev["wbt_name"],
            "room_id": dev["room_id"],
            "state": st.get("state", "Online"),
            "metadata": st.get("metadata", "Live • 640x480"),
            "type": "Camera",
            "translation": dev["translation"],
        }

    # --- Navigation Graph & Route Planner ---

    def list_nav_nodes(self) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT n.*, r.name as room_name
                FROM nav_nodes n
                LEFT JOIN rooms r ON n.room_id = r.id
                ORDER BY n.id ASC
                """
            )
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "room_id": r["room_id"],
                    "room": r["room_name"] or (r["room_id"] or "Home").replace("_", " ").title(),
                    "x": float(r["x"]),
                    "y": float(r["y"]),
                    "default_theta": float(r["default_theta"]),
                    "is_dock": bool(r["is_dock"]),
                }
                for r in cur.fetchall()
            ]

    def list_nav_edges(self) -> list[dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT e.id, e.from_node, e.to_node, e.blocking_device_id, d.wbt_name as blocking_door_name
                FROM nav_edges e
                LEFT JOIN devices d ON e.blocking_device_id = d.id
                ORDER BY e.id ASC
                """
            )
            return [
                {
                    "id": r["id"],
                    "from_node": r["from_node"],
                    "to_node": r["to_node"],
                    "blocking_device_id": r["blocking_device_id"],
                    "blocking_door_name": r["blocking_door_name"],
                }
                for r in cur.fetchall()
            ]

    def add_nav_node(self, req: NavNodeProvisionRequest) -> dict[str, Any]:
        room_id = req.room_id or self.infer_room_id(req.x, req.y)
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO nav_nodes (id, name, room_id, x, y, default_theta, is_dock)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (req.id, req.name, room_id, req.x, req.y, req.default_theta, 1 if req.is_dock else 0),
            )
            for target_node in req.connect_to:
                self._conn.execute(
                    "INSERT INTO nav_edges (from_node, to_node, blocking_device_id) VALUES (?, ?, NULL)",
                    (req.id, target_node),
                )
            # Check if any existing door sits on the newly created edges
            for door in self.list_devices(domain="door"):
                self._auto_link_door_to_nav_edges(
                    door["id"], door["translation"][0], door["translation"][1]
                )
            self._conn.commit()
        return {
            "id": req.id,
            "name": req.name,
            "room_id": room_id,
            "x": req.x,
            "y": req.y,
            "default_theta": req.default_theta,
            "is_dock": req.is_dock,
        }

    def nearest_nav_node(self, x: float, y: float) -> dict[str, Any]:
        nodes = self.list_nav_nodes()
        if not nodes:
            return {"id": "foyer", "name": "Foyer Dock", "room": "Foyer", "x": -3.10, "y": -7.62, "default_theta": 3.1416}
        return min(nodes, key=lambda n: math.hypot(x - n["x"], y - n["y"]))

    def resolve_destination_node(self, dest_raw: str) -> str:
        clean = dest_raw.strip().lower().replace(" ", "_")
        aliased = ROOM_ALIASES.get(clean, clean)
        nodes = {n["id"]: n for n in self.list_nav_nodes()}
        if aliased in nodes:
            return aliased
        # Match by room_id or node name
        for nid, n in nodes.items():
            if n["room_id"] == aliased or n["name"].lower().replace(" ", "_") == aliased:
                return nid
        raise ValueError(f"Unknown destination '{dest_raw}'. Valid nodes: {list(nodes.keys())}")

    def compute_route(self, cx: float, cy: float, dest_raw: str) -> dict[str, Any]:
        dest_key = self.resolve_destination_node(dest_raw)
        nodes = {n["id"]: n for n in self.list_nav_nodes()}
        edges = self.list_nav_edges()

        adj: dict[str, list[tuple[str, float, str | None]]] = {k: [] for k in nodes}
        for e in edges:
            u, v, b_id = e["from_node"], e["to_node"], e["blocking_device_id"]
            if u in nodes and v in nodes:
                dist = math.hypot(nodes[v]["x"] - nodes[u]["x"], nodes[v]["y"] - nodes[u]["y"])
                adj[u].append((v, dist, b_id))
                adj[v].append((u, dist, b_id))

        origin_node = self.nearest_nav_node(cx, cy)
        origin = origin_node["id"]

        pq: list[tuple[float, str, list[str], list[str]]] = [(0.0, origin, [origin], [])]
        visited: dict[str, float] = {}
        best_path: list[str] = []
        door_ids_on_path: list[str] = []
        total_dist = 0.0

        while pq:
            cost, curr, path, door_ids = heapq.heappop(pq)
            if curr == dest_key:
                best_path = path
                door_ids_on_path = door_ids
                total_dist = round(cost, 2)
                break
            if curr in visited and visited[curr] <= cost:
                continue
            visited[curr] = cost
            for nxt, w, b_id in adj.get(curr, []):
                nc = cost + w
                if nxt not in visited or nc < visited[nxt]:
                    nd = [*door_ids, b_id] if b_id else list(door_ids)
                    heapq.heappush(pq, (nc, nxt, [*path, nxt], nd))

        # Simplify collinear Manhattan segments
        if len(best_path) > 2:
            simplified = [best_path[0]]
            for i in range(1, len(best_path) - 1):
                p0 = nodes[simplified[-1]]
                p1 = nodes[best_path[i]]
                p2 = nodes[best_path[i + 1]]
                a1 = math.atan2(p1["y"] - p0["y"], p1["x"] - p0["x"])
                a2 = math.atan2(p2["y"] - p1["y"], p2["x"] - p1["x"])
                if abs(math.atan2(math.sin(a2 - a1), math.cos(a2 - a1))) > 0.05:
                    simplified.append(best_path[i])
            simplified.append(best_path[-1])
            corners = simplified
        else:
            corners = best_path if best_path else [dest_key]

        waypoints: list[dict[str, Any]] = []
        for idx, k in enumerate(corners):
            n = nodes[k]
            nx, ny, def_yaw = n["x"], n["y"], n["default_theta"]
            if idx < len(corners) - 1:
                nxt = nodes[corners[idx + 1]]
                yaw = round(math.atan2(nxt["y"] - ny, nxt["x"] - nx), 4)
            else:
                yaw = round(def_yaw, 4)
            waypoints.append({
                "node_id": k,
                "name": n["name"],
                "room": n["room"],
                "x": nx,
                "y": ny,
                "theta": yaw,
            })

        blocking_doors: list[dict[str, Any]] = []
        doors_on_path_names: list[str] = []
        all_doors_on_path: list[dict[str, Any]] = []
        for d_id in door_ids_on_path:
            d_rec = self.strict_lookup(d_id)
            if d_rec:
                formatted = self.format_door(d_rec)
                doors_on_path_names.append(formatted["wbt_name"])
                door_info = {
                    "id": formatted["id"],
                    "wbt_name": formatted["wbt_name"],
                    "name": formatted["name"],
                    "state": formatted["state"],
                    "position": formatted["position"],
                    "locked": formatted["locked"],
                    "translation": formatted["translation"],
                }
                all_doors_on_path.append(door_info)
                if formatted["state"] != "Open" or int(formatted["position"]) < 80:
                    blocking_doors.append(door_info)

        eta_seconds = round((total_dist / 0.6) + (len(blocking_doors) * 2.0), 1)
        return {
            "origin": origin,
            "origin_name": origin_node["name"],
            "origin_pose": {"x": round(cx, 3), "y": round(cy, 3)},
            "destination": dest_key,
            "destination_name": nodes[dest_key]["name"],
            "destination_room": nodes[dest_key]["room"],
            "node_path": best_path,
            "waypoints": waypoints,
            "doors_on_path": doors_on_path_names,
            "doors_on_path_details": all_doors_on_path,
            "distance_m": total_dist,
            "eta_seconds": eta_seconds,
            "blocking_doors": blocking_doors,
        }

    # --- Robot & Errands State ---

    def get_robot(self, robot_id: str = "tiago") -> dict[str, Any]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM robots WHERE id = ?", (robot_id,))
            row = cur.fetchone()
            if not row:
                return {
                    "id": "tiago",
                    "name": "TIAGo",
                    "model": "PAL Robotics TIAGo",
                    "type": "Mobile Manipulator",
                    "status": "Docked",
                    "current_room": "Foyer",
                    "current_node": "foyer",
                    "battery_pct": 92,
                    "pose": {"x": -3.10, "y": -7.62, "theta": 1.5708},
                    "target_destination": None,
                    "arm_pose": "home",
                    "gripper": "open",
                    "held_object": "",
                    "task_description": "idle",
                    "active_route": [],
                    "online": True,
                }
            px = float(row["pose_x"])
            py = float(row["pose_y"])
            theta = float(row["theta"])
            nearest = self.nearest_nav_node(px, py)
            return {
                "id": row["id"],
                "name": row["name"],
                "model": row["model"],
                "type": "Mobile Manipulator",
                "status": row["status"],
                "current_room": nearest["room"],
                "current_node": nearest["id"],
                "battery_pct": round(float(row["battery_pct"]), 1),
                "pose": {"x": round(px, 3), "y": round(py, 3), "theta": round(theta, 3)},
                "target_destination": row["target_destination"],
                "arm_pose": row["arm_pose"],
                "gripper": row["gripper"],
                "held_object": row["held_object"],
                "task_description": row["task_description"],
                "active_route": json.loads(row["active_waypoints_json"]),
                "doors_to_clear": json.loads(row["doors_to_clear_json"]),
                "online": bool(row["online"]),
            }

    def update_robot(self, robot_id: str = "tiago", **fields: Any) -> dict[str, Any]:
        allowed = {
            "pose_x",
            "pose_y",
            "theta",
            "battery_pct",
            "status",
            "task_description",
            "arm_pose",
            "gripper",
            "held_object",
            "target_destination",
            "active_waypoints_json",
            "doors_to_clear_json",
            "online",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = [*updates.values(), robot_id]
            with self._lock:
                self._conn.execute(
                    f"UPDATE robots SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    values,
                )
                self._conn.commit()
        return self.get_robot(robot_id)

    def get_latest_errand(self) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM errands ORDER BY updated_at DESC LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return {
                    "task_id": "",
                    "errand_type": "",
                    "current_step": 0,
                    "total_steps": 0,
                    "status": "idle",
                    "message": "No active errand",
                }
            return {
                "task_id": row["task_id"],
                "errand_type": row["errand_type"],
                "item": row["item"],
                "from_location": row["from_location"],
                "to_location": row["to_location"],
                "current_step": int(row["current_step"]),
                "total_steps": int(row["total_steps"]),
                "status": row["status"],
                "message": row["message"],
            }

    def upsert_errand(
        self,
        task_id: str,
        errand_type: str,
        item: str = "",
        from_location: str = "",
        to_location: str = "",
        current_step: int = 0,
        total_steps: int = 0,
        status: str = "running",
        message: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO errands (
                    task_id, robot_id, errand_type, item, from_location, to_location,
                    current_step, total_steps, status, message, updated_at
                ) VALUES (?, 'tiago', ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(task_id) DO UPDATE SET
                    current_step = excluded.current_step,
                    total_steps = excluded.total_steps,
                    status = excluded.status,
                    message = excluded.message,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    task_id,
                    errand_type,
                    item,
                    from_location,
                    to_location,
                    current_step,
                    total_steps,
                    status,
                    message,
                ),
            )
            self._conn.commit()
        return self.get_latest_errand()

    # --- Environment & Summary ---

    def get_environment(self) -> dict[str, Any]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT value_json FROM environment_config WHERE key = 'environment'"
            )
            row = cur.fetchone()
            if row:
                return json.loads(row["value_json"])
            return {"time_of_day": "day", "sun_luminosity": 0.85}

    def set_environment(self, time_of_day: str) -> dict[str, Any]:
        lum_map = {"day": 0.85, "sunset": 0.30, "night": 0.04}
        env = {"time_of_day": time_of_day, "sun_luminosity": lum_map.get(time_of_day, 0.85)}
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO environment_config (key, value_json) VALUES ('environment', ?)",
                (json.dumps(env),),
            )
            self._conn.commit()
        return env

    def get_summary(self, sim_mode: str = "VIRTUAL_PHYSICS_FALLBACK") -> dict[str, Any]:
        lights = [self.format_light(d) for d in self.list_devices("light")]
        doors = [self.format_door(d) for d in self.list_devices("door")]
        blinds = self.list_devices("blind")
        climates = [self.format_climate(d) for d in self.list_devices("climate")]
        appliances = [self.format_appliance(d) for d in self.list_devices("appliance")]
        cameras = self.list_devices("camera")
        robot = self.get_robot("tiago")

        lights_on = sum(1 for l in lights if l["state"] == "On")
        doors_open = sum(1 for d in doors if d["state"] == "Open")
        appliance_watts = sum(a["power_watts"] for a in appliances)
        light_watts = lights_on * 12.0
        hvac_watts = sum(350.0 for c in climates if c["state"] == "On")

        return {
            "lights_on": lights_on,
            "total_lights": len(lights),
            "doors_open": doors_open,
            "total_doors": len(doors),
            "blinds_count": len(blinds),
            "climate_zones": len(climates),
            "cameras_online": len(cameras) + 1,  # +1 for TIAGo Head Camera
            "estimated_power_watts": round(appliance_watts + light_watts + hvac_watts, 1),
            "environment": self.get_environment(),
            "sim_mode": sim_mode,
            "robot": {
                "id": robot["id"],
                "name": robot["name"],
                "status": robot["status"],
                "current_room": robot["current_room"],
                "target_destination": robot["target_destination"],
                "battery_pct": robot["battery_pct"],
                "pose": robot["pose"],
            },
        }

    def log_event(self, topic: str, payload: dict[str, Any]) -> None:
        if topic == "sim.bridge.heartbeat":
            return
        with self._lock:
            self._conn.execute(
                "INSERT INTO events_log (topic, payload_json) VALUES (?, ?)",
                (topic, json.dumps(payload)),
            )
            # Keep events_log bounded to recent 500 events
            self._conn.execute(
                "DELETE FROM events_log WHERE id NOT IN (SELECT id FROM events_log ORDER BY id DESC LIMIT 500)"
            )
            self._conn.commit()


_db_instance: DatabaseManager | None = None
_db_init_lock = threading.Lock()


def get_db() -> DatabaseManager:
    global _db_instance
    if _db_instance is None:
        with _db_init_lock:
            if _db_instance is None:
                _db_instance = DatabaseManager()
    return _db_instance
