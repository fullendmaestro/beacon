"""Webots World Spawner Supervisor — Dynamically spawns VRML nodes from SQLite/Event Broker."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import queue
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

# Ensure src is on sys.path so beacon_hub can be imported if Hub is auto-started
_SRC_DIR = Path(__file__).resolve().parents[3]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

try:
    from controller import Supervisor  # type: ignore[import-not-found]
    _WEBOTS = True
except ImportError:
    Supervisor = None  # type: ignore[assignment,misc]
    _WEBOTS = False

logger = logging.getLogger("world_spawner")

HUB_WS_URL = "ws://127.0.0.1:8000/ws/sim-bridge"


def _ensure_hub_server_running(host: str = "127.0.0.1", port: int = 8000) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        if sock.connect_ex((host, port)) == 0:
            return

    def _run_hub() -> None:
        import uvicorn
        from beacon_hub.main import app

        uvicorn.run(app, host=host, port=port, log_level="warning")

    threading.Thread(target=_run_hub, daemon=True, name="beacon-hub-autostart").start()
    time.sleep(0.5)


def build_vrml_node_string(dev: dict[str, Any]) -> str:
    """Build a Webots R2025a VRML string for a device record."""
    wbt_def = dev.get("wbt_def") or f"DEV_{dev['id'].upper()}"
    wbt_name = dev["wbt_name"].replace('"', '\\"')
    proto = dev["proto_type"]
    domain = dev["domain"]
    tx, ty, tz = [float(c) for c in dev["translation"]]
    rx, ry, rz, ra = [float(c) for c in dev["rotation"]]
    cfg = dev.get("config", {})
    st = dev.get("reported_state", {})

    if domain == "light":
        rgb = st.get("color_rgb", cfg.get("pointLightColor", [1.0, 1.0, 1.0]))
        cr, cg, cb = float(rgb[0]), float(rgb[1]), float(rgb[2])
        intensity = float(st.get("intensity", 2.5 if st.get("state") == "On" else 0.0))
        radius = float(cfg.get("pointLightRadius", 4.5))
        if proto == "CeilingSpotLight":
            return (
                f'DEF {wbt_def} CeilingSpotLight {{\n'
                f'  translation {tx} {ty} {tz}\n'
                f'  name "{wbt_name}"\n'
                f'  spotLightColor {cr} {cg} {cb}\n'
                f'  spotLightIntensity {intensity}\n'
                f'  spotLightRadius {radius}\n'
                f'}}'
            )
        if proto == "FloorLight":
            return (
                f'DEF {wbt_def} FloorLight {{\n'
                f'  translation {tx} {ty} {tz}\n'
                f'  name "{wbt_name}"\n'
                f'  pointLightColor {cr} {cg} {cb}\n'
                f'  pointLightIntensity {intensity}\n'
                f'  pointLightRadius {radius}\n'
                f'}}'
            )
        return (
            f'DEF {wbt_def} CeilingLight {{\n'
            f'  translation {tx} {ty} {tz}\n'
            f'  name "{wbt_name}"\n'
            f'  pointLightColor {cr} {cg} {cb}\n'
            f'  pointLightIntensity {intensity}\n'
            f'  pointLightRadius {radius}\n'
            f'}}'
        )

    if domain == "door":
        pos_pct = float(st.get("position", 0.0)) / 100.0
        axis = cfg.get("axis", "z")
        if proto == "SlidingGate":
            c_pos = float(cfg.get("closed_pos", 2.1))
            o_pos = float(cfg.get("open_pos", -1.6))
            curr_x = c_pos + (o_pos - c_pos) * pos_pct
            return (
                f'DEF {wbt_def} Solid {{\n'
                f'  translation {curr_x} {ty} {tz}\n'
                f'  name "{wbt_name}"\n'
                f'  children [ Shape {{ appearance BrushedAluminium {{}} geometry Box {{ size 3.9 0.1 1.1 }} }} ]\n'
                f'  boundingObject Box {{ size 3.9 0.1 1.1 }}\n'
                f'}}'
            )
        if proto == "OverheadGarageDoor":
            c_pos = float(cfg.get("closed_pos", 1.15))
            o_pos = float(cfg.get("open_pos", 2.30))
            curr_z = c_pos + (o_pos - c_pos) * pos_pct
            return (
                f'DEF {wbt_def} Solid {{\n'
                f'  translation {tx} {ty} {curr_z}\n'
                f'  name "{wbt_name}"\n'
                f'  children [ Shape {{ appearance PaintedWood {{ colorOverride 0.22 0.24 0.27 }} geometry Box {{ size 3.8 0.1 2.2 }} }} ]\n'
                f'  boundingObject Box {{ size 3.8 0.1 2.2 }}\n'
                f'}}'
            )
        # Interior Door PROTO
        c_z = float(cfg.get("closed_z", tz))
        o_z = float(cfg.get("open_z", tz + 2.25))
        curr_z = c_z + (o_z - c_z) * pos_pct
        can_be_open = bool(cfg.get("canBeOpen", False))
        can_be_open_str = "TRUE" if can_be_open else "FALSE"
        has_static_parent_str = "FALSE" if can_be_open else "TRUE"
        joint_at_left = cfg.get("jointAtLeft", True)
        joint_val_str = "TRUE" if joint_at_left else "FALSE"
        return (
            f'DEF {wbt_def} Door {{\n'
            f'  translation {tx} {ty} {curr_z}\n'
            f'  rotation {rx} {ry} {rz} {ra}\n'
            f'  name "{wbt_name}"\n'
            f'  size 0.3 1 2.4\n'
            f'  canBeOpen {can_be_open_str}\n'
            f'  jointAtLeft {joint_val_str}\n'
            f'  doorHandle DoorLever {{\n'
            f'    jointAtLeft {joint_val_str}\n'
            f'    hasStaticParent {has_static_parent_str}\n'
            f'  }}\n'
            f'  frameSize 0.001 0.05 0.05\n'
            f'  frameAppearance BrushedAluminium {{}}\n'
            f'}}'
        )

    if domain == "blind":
        pos_pct = float(st.get("position", 0.0)) / 100.0
        c_z = float(cfg.get("closed_z", 1.25))
        o_z = float(cfg.get("open_z", 2.28))
        curr_z = c_z + (o_z - c_z) * pos_pct
        sz = cfg.get("size", [0.95, 0.04, 2.1])
        return (
            f'DEF {wbt_def} Solid {{\n'
            f'  translation {tx} {ty} {curr_z}\n'
            f'  name "{wbt_name}"\n'
            f'  children [ Shape {{ appearance PBRAppearance {{ baseColor 0.92 0.91 0.88 roughness 0.7 metalness 0.1 }} geometry Box {{ size {sz[0]} {sz[1]} {sz[2]} }} }} ]\n'
            f'}}'
        )

    if domain == "climate":
        return (
            f'DEF {wbt_def} Radiator {{\n'
            f'  translation {tx} {ty} {tz}\n'
            f'  rotation {rx} {ry} {rz} {ra}\n'
            f'  name "{wbt_name}"\n'
            f'}}'
        )

    if domain == "appliance":
        if proto in ("Fridge", "Oven", "WashingMachine", "Barbecue", "WallPlug"):
            return (
                f'DEF {wbt_def} {proto} {{\n'
                f'  translation {tx} {ty} {tz}\n'
                f'  rotation {rx} {ry} {rz} {ra}\n'
                f'  name "{wbt_name}"\n'
                f'}}'
            )
        if proto == "Microwave":
            return (
                f'DEF {wbt_def} Oven {{\n'
                f'  translation {tx} {ty} {tz}\n'
                f'  rotation {rx} {ry} {rz} {ra}\n'
                f'  name "{wbt_name}"\n'
                f'  mainColor 0.2 0.22 0.25\n'
                f'  type "microwave"\n'
                f'}}'
            )
        if proto in ("Cooktop", "HotPlate"):
            return (
                f'DEF {wbt_def} HotPlate {{\n'
                f'  translation {tx} {ty} {tz}\n'
                f'  rotation {rx} {ry} {rz} {ra}\n'
                f'  name "{wbt_name}"\n'
                f'}}'
            )
        if proto == "Television":
            return (
                f'DEF {wbt_def} Television {{\n'
                f'  translation {tx} {ty} {tz}\n'
                f'  rotation {rx} {ry} {rz} {ra}\n'
                f'  name "{wbt_name}"\n'
                f'  controller "<none>"\n'
                f'}}'
            )
        return (
            f'DEF {wbt_def} Solid {{\n'
            f'  translation {tx} {ty} {tz}\n'
            f'  rotation {rx} {ry} {rz} {ra}\n'
            f'  name "{wbt_name}"\n'
            f'}}'
        )

    if domain == "camera":
        w = int(cfg.get("width", 640))
        h = int(cfg.get("height", 480))
        fov = float(cfg.get("fieldOfView", 1.15))
        dev_id = dev["id"]
        return (
            f'DEF {wbt_def} Robot {{\n'
            f'  translation {tx} {ty} {tz}\n'
            f'  rotation {rx} {ry} {rz} {ra}\n'
            f'  name "{wbt_name}"\n'
            f'  controller "iot_device_controller"\n'
            f'  controllerArgs [ "{dev_id}" ]\n'
            f'  children [\n'
            f'    Camera {{\n'
            f'      name "{wbt_name}"\n'
            f'      width {w}\n'
            f'      height {h}\n'
            f'      fieldOfView {fov}\n'
            f'    }}\n'
            f'  ]\n'
            f'}}'
        )

    if domain == "sensor":
        dev_id = dev["id"]
        sensor_node = (
            f'LightSensor {{ name "{wbt_name}" }}'
            if proto == "LightSensor"
            else f'DistanceSensor {{ name "{wbt_name}" lookupTable [ 0 0 0, 4.5 1000 0 ] }}'
        )
        return (
            f'DEF {wbt_def} Robot {{\n'
            f'  translation {tx} {ty} {tz}\n'
            f'  rotation {rx} {ry} {rz} {ra}\n'
            f'  name "{wbt_name}"\n'
            f'  controller "iot_device_controller"\n'
            f'  controllerArgs [ "{dev_id}" ]\n'
            f'  children [ {sensor_node} ]\n'
            f'}}'
        )

    return (
        f'DEF {wbt_def} Solid {{\n'
        f'  translation {tx} {ty} {tz}\n'
        f'  name "{wbt_name}"\n'
        f'}}'
    )


class WorldSpawnerSupervisor:
    """
    Decoupled Webots Scene Manager:
    - Connects to `ws://127.0.0.1:8000/ws/sim-bridge`
    - Spawns all SQLite devices into `DEF DYNAMIC_DEVICES Group`
    - Runs `LightingBridgeWorker` and `BarrierActuatorWorker` (with multi-step interpolation)
    - Emits `sim.bridge.heartbeat`
    """

    def __init__(self) -> None:
        self.supervisor = Supervisor() if (_WEBOTS and Supervisor is not None) else None
        self.time_step = int(self.supervisor.getBasicTimeStep()) if self.supervisor else 16
        self.incoming_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.outgoing_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.spawned_defs: dict[str, str] = {}  # device_id -> wbt_def
        self.device_records: dict[str, dict[str, Any]] = {}
        self.active_interpolations: dict[str, dict[str, Any]] = {}

    def spawn_device_node(self, dev: dict[str, Any]) -> None:
        self.device_records[dev["id"]] = dev
        if not self.supervisor:
            return
        wbt_def = dev.get("wbt_def") or f"DEV_{dev['id'].upper()}"
        if self.supervisor.getFromDef(wbt_def) is not None:
            self.spawned_defs[dev["id"]] = wbt_def
            return
        dyn_group = self.supervisor.getFromDef("DYNAMIC_DEVICES")
        if not dyn_group:
            return
        children_field = dyn_group.getField("children")
        if not children_field:
            return
        vrml_str = build_vrml_node_string(dev)
        children_field.importMFNodeFromString(-1, vrml_str)
        self.spawned_defs[dev["id"]] = wbt_def

    def remove_device_node(self, device_id: str, wbt_def: str | None = None) -> None:
        self.device_records.pop(device_id, None)
        def_name = wbt_def or self.spawned_defs.pop(device_id, None)
        if not self.supervisor or not def_name:
            return
        node = self.supervisor.getFromDef(def_name)
        if node:
            node.remove()

    def apply_lighting_command(self, dev_id: str, action: str, params: dict[str, Any]) -> None:
        from beacon_hub.database.models import ColorUtils

        dev = self.device_records.get(dev_id)
        if not dev:
            return
        rep = dict(dev.get("reported_state", {}))
        max_int = float(dev.get("config", {}).get("maxIntensity", 3.0))
        curr_on = rep.get("state", "On") == "On"
        curr_b = int(rep.get("brightness", 100))

        if action == "toggle":
            target_on = not curr_on
            target_b = curr_b if curr_b > 0 else 100
        else:
            target_on = curr_on
            if params.get("power_state") is not None:
                target_on = str(params["power_state"]).lower() == "on"
            target_b = curr_b if curr_b > 0 else 100
            if params.get("brightness") is not None:
                b_val = max(0, min(100, int(params["brightness"])))
                if b_val == 0:
                    target_on = False
                    target_b = 0
                else:
                    target_on = True
                    target_b = b_val
            if params.get("color") is not None:
                rgb = ColorUtils.parse(params["color"])
                rep["color_rgb"] = rgb
                rep["color"] = ColorUtils.to_hex(rgb)

        intensity = round((target_b / 100.0) * max_int, 2) if target_on else 0.0
        rep["state"] = "On" if target_on else "Off"
        rep["power_state"] = "on" if target_on else "off"
        rep["brightness"] = target_b if target_on else 0
        rep["intensity"] = intensity
        rep["metadata"] = f"Intensity at {intensity:.1f}"
        dev["reported_state"] = rep

        if self.supervisor:
            def_name = self.spawned_defs.get(dev_id) or dev.get("wbt_def")
            node = self.supervisor.getFromDef(def_name) if def_name else None
            if node:
                is_spot = dev["proto_type"] == "CeilingSpotLight"
                i_field = node.getField("spotLightIntensity" if is_spot else "pointLightIntensity")
                c_field = node.getField("spotLightColor" if is_spot else "pointLightColor")
                if i_field:
                    i_field.setSFFloat(intensity)
                if c_field and "color_rgb" in rep:
                    c_field.setSFColor(rep["color_rgb"])

        self.outgoing_queue.put({
            "topic": f"device.state.light.{dev_id}",
            "payload": {
                "device_id": dev_id,
                "wbt_name": dev["wbt_name"],
                "domain": "light",
                "state": rep,
                "source": "webots",
            },
        })

    def enqueue_barrier_interpolation(self, dev_id: str, params: dict[str, Any]) -> None:
        dev = self.device_records.get(dev_id)
        if not dev:
            return
        rep = dict(dev.get("reported_state", {}))
        curr_pos = float(rep.get("position", 0.0))
        target_pos = curr_pos
        if params.get("open_state") is not None:
            target_pos = 100.0 if str(params["open_state"]).lower() == "open" else 0.0
        if params.get("position") is not None:
            target_pos = float(max(0, min(100, int(params["position"]))))

        locked = bool(rep.get("locked", False))
        if params.get("locked") is not None:
            locked = bool(params["locked"])
            if locked and params.get("open_state") is None and params.get("position") is None:
                target_pos = 0.0
        if target_pos > 0:
            locked = False

        self.active_interpolations[dev_id] = {
            "start_pos": curr_pos,
            "target_pos": target_pos,
            "curr_pos": curr_pos,
            "locked": locked,
            "steps_done": 0,
            "total_steps": max(1, int(320 / max(16, self.time_step))),
        }

    def step_barrier_interpolations(self) -> None:
        finished: list[str] = []
        for dev_id, interp in list(self.active_interpolations.items()):
            dev = self.device_records.get(dev_id)
            if not dev:
                finished.append(dev_id)
                continue
            interp["steps_done"] += 1
            ratio_step = min(1.0, interp["steps_done"] / interp["total_steps"])
            curr_pos = interp["start_pos"] + (interp["target_pos"] - interp["start_pos"]) * ratio_step
            pct = round(curr_pos)
            pos_ratio = pct / 100.0

            if self.supervisor:
                def_name = self.spawned_defs.get(dev_id) or dev.get("wbt_def")
                node = self.supervisor.getFromDef(def_name) if def_name else None
                if node:
                    t_field = node.getField("translation")
                    if t_field:
                        pos = list(t_field.getSFVec3f())
                        cfg = dev.get("config", {})
                        if dev["proto_type"] == "SlidingGate":
                            c_p = float(cfg.get("closed_pos", 2.1))
                            o_p = float(cfg.get("open_pos", -1.6))
                            pos[0] = c_p + (o_p - c_p) * pos_ratio
                        else:
                            c_z = float(cfg.get("closed_z", cfg.get("closed_pos", 0.0)))
                            o_z = float(cfg.get("open_z", cfg.get("open_pos", 2.25)))
                            pos[2] = c_z + (o_z - c_z) * pos_ratio
                        t_field.setSFVec3f(pos)

            if ratio_step >= 1.0 or interp["steps_done"] % 5 == 0:
                rep = dict(dev.get("reported_state", {}))
                rep["position"] = int(pct)
                rep["state"] = "Open" if pct > 0 else "Closed"
                if dev["domain"] == "door":
                    rep["locked"] = interp["locked"]
                    rep["metadata"] = f"{'Locked' if interp['locked'] else 'Unlocked'} • {rep['state']} ({int(pct)}%)"
                else:
                    room_name = dev.get("room_name") or rep.get("room") or "Home"
                    rep["metadata"] = f"{room_name} • {int(pct)}% Open"
                dev["reported_state"] = rep
                self.outgoing_queue.put({
                    "topic": f"device.state.{dev['domain']}.{dev_id}",
                    "payload": {
                        "device_id": dev_id,
                        "wbt_name": dev["wbt_name"],
                        "domain": dev["domain"],
                        "state": rep,
                        "source": "webots",
                    },
                })

            if ratio_step >= 1.0:
                finished.append(dev_id)

        for dev_id in finished:
            self.active_interpolations.pop(dev_id, None)

    def apply_environment(self, env: dict[str, Any]) -> None:
        if not self.supervisor:
            return
        sun = self.supervisor.getFromDef("SUN_LIGHT")
        if sun:
            lum_field = sun.getField("luminosity")
            if lum_field:
                lum_field.setSFFloat(float(env.get("sun_luminosity", 0.85)))

    def process_incoming_events(self) -> None:
        while not self.incoming_queue.empty():
            msg = self.incoming_queue.get()
            topic = str(msg.get("topic", ""))
            payload = msg.get("payload", {})

            if topic == "sim.init_manifest":
                for dev in payload.get("devices", []):
                    self.spawn_device_node(dev)
                if "environment" in payload:
                    self.apply_environment(payload["environment"])
                robot = payload.get("robot")
                if robot and self.supervisor:
                    tiago = self.supervisor.getFromDef("BEACON_TIAGO")
                    if tiago:
                        tf = tiago.getField("translation")
                        rf = tiago.getField("rotation")
                        pose = robot.get("pose", {})
                        if tf and "x" in pose and "y" in pose:
                            cur_t = list(tf.getSFVec3f())
                            # Only hot-teleport TIAGo if it has moved away from the Foyer dock
                            if math.hypot(float(pose["x"]) - cur_t[0], float(pose["y"]) - cur_t[1]) > 0.35:
                                tf.setSFVec3f([float(pose["x"]), float(pose["y"]), cur_t[2]])
                                if rf and "theta" in pose:
                                    rf.setSFRotation([0.0, 0.0, 1.0, float(pose["theta"])])
                                tiago.resetPhysics()

            elif topic == "device.lifecycle.provisioned":
                self.spawn_device_node(payload)

            elif topic == "device.lifecycle.removed":
                self.remove_device_node(
                    str(payload.get("device_id", "")), payload.get("wbt_def")
                )

            elif topic.startswith("device.command."):
                domain = payload.get("domain")
                dev_id = str(payload.get("device_id", ""))
                action = str(payload.get("action", "set_state"))
                params = payload.get("params", {})
                if domain == "light":
                    self.apply_lighting_command(dev_id, action, params)
                elif domain in ("door", "blind"):
                    self.enqueue_barrier_interpolation(dev_id, params)
                elif domain in ("climate", "appliance"):
                    # Acknowledge state back to Hub
                    dev = self.device_records.get(dev_id)
                    if dev:
                        rep = dict(dev.get("reported_state", {}))
                        rep.update(params)
                        self.outgoing_queue.put({
                            "topic": f"device.state.{domain}.{dev_id}",
                            "payload": {
                                "device_id": dev_id,
                                "wbt_name": dev["wbt_name"],
                                "domain": domain,
                                "state": rep,
                                "source": "webots",
                            },
                        })

            elif topic == "environment.updated":
                self.apply_environment(payload)

    def run(self) -> None:
        _ensure_hub_server_running()
        ws_thread = threading.Thread(target=self._ws_client_thread, daemon=True, name="spawner-ws")
        ws_thread.start()

        if self.supervisor:
            last_hb = 0.0
            while self.supervisor.step(self.time_step) != -1:
                self.process_incoming_events()
                self.step_barrier_interpolations()
                now = time.monotonic()
                if now - last_hb >= 0.5:
                    last_hb = now
                    self.outgoing_queue.put({
                        "topic": "sim.bridge.heartbeat",
                        "payload": {
                            "sim_time": round(float(self.supervisor.getTime()), 2),
                            "fps": round(1000.0 / max(1, self.time_step), 1),
                            "status": "attached",
                        },
                    })
        else:
            while True:
                self.process_incoming_events()
                self.step_barrier_interpolations()
                time.sleep(0.05)

    def _ws_client_thread(self) -> None:
        asyncio.run(self._ws_loop())

    async def _ws_loop(self) -> None:
        import websockets

        while True:
            try:
                async with websockets.connect(HUB_WS_URL) as ws:
                    async def _sender() -> None:
                        while True:
                            while not self.outgoing_queue.empty():
                                item = self.outgoing_queue.get()
                                await ws.send(json.dumps(item))
                            await asyncio.sleep(0.03)

                    sender_task = asyncio.create_task(_sender())
                    try:
                        async for message in ws:
                            data = json.loads(message)
                            self.incoming_queue.put(data)
                    finally:
                        sender_task.cancel()
            except Exception:  # noqa: BLE001
                await asyncio.sleep(1.0)


if __name__ == "__main__":
    WorldSpawnerSupervisor().run()
