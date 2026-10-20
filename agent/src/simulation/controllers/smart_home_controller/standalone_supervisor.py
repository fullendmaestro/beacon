from __future__ import annotations

import io
import math
import time
from typing import Any

from PIL import Image, ImageDraw
from constants import (
    APPLIANCE_DEFAULTS,
    BLIND_DEFS,
    CAMERA_NAMES,
    EXTERIOR_BARRIER_DEFS,
    LIGHT_SENSOR_NAMES,
    MOTION_SENSOR_NAMES,
)


class MockField:
    """In-memory Webots Field emulation for standalone/headless Hub execution."""

    def __init__(self, value: Any) -> None:
        self._value = value

    def getSFString(self) -> str:
        return str(self._value)

    def setSFString(self, val: str) -> None:
        self._value = str(val)

    def getSFFloat(self) -> float:
        return float(self._value)

    def setSFFloat(self, val: float) -> None:
        self._value = float(val)

    def getSFColor(self) -> list[float]:
        return list(self._value)

    def setSFColor(self, val: list[float]) -> None:
        self._value = [float(c) for c in val]

    def getSFVec3f(self) -> list[float]:
        return list(self._value)

    def setSFVec3f(self, val: list[float]) -> None:
        self._value = [float(c) for c in val]

    def getSFRotation(self) -> list[float]:
        return list(self._value)

    def setSFRotation(self, val: list[float]) -> None:
        self._value = [float(c) for c in val]

    def getCount(self) -> int:
        return len(self._value) if isinstance(self._value, list) else 0

    def getMFNode(self, idx: int) -> Any:
        if isinstance(self._value, list) and 0 <= idx < len(self._value):
            return self._value[idx]
        return None


class MockNode:
    """In-memory Webots Node emulation matching beacon_home.wbt scene nodes."""

    def __init__(
        self,
        node_id: int,
        type_name: str,
        fields: dict[str, Any] | None = None,
        def_name: str | None = None,
    ) -> None:
        self._id = node_id
        self._type_name = type_name
        self._def_name = def_name
        self._fields: dict[str, MockField] = {
            k: (v if isinstance(v, MockField) else MockField(v))
            for k, v in (fields or {}).items()
        }

    def getId(self) -> int:
        return self._id

    def getTypeName(self) -> str:
        return self._type_name

    def getField(self, name: str) -> MockField | None:
        return self._fields.get(name)


class MockCamera:
    """Synthetic Webots Camera device that generates a valid BGRA frame."""

    def __init__(self, name: str, width: int = 640, height: int = 480) -> None:
        self.name = name
        self._width = width
        self._height = height
        self._cached_bgra: bytes | None = None

    def enable(self, time_step: int) -> None:
        pass

    def getWidth(self) -> int:
        return self._width

    def getHeight(self) -> int:
        return self._height

    def getImage(self) -> bytes:
        if self._cached_bgra is None:
            img = Image.new("RGBA", (self._width, self._height), (24, 30, 42, 255))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(16, 16), (self._width - 16, self._height - 16)], outline=(64, 160, 255, 255), width=2)
            draw.text((32, 32), f"BEACON LIVE FEED: {self.name}", fill=(230, 240, 255, 255))
            r, g, b, a = img.split()
            bgra = Image.merge("RGBA", (b, g, r, a))
            self._cached_bgra = bgra.tobytes()
        return self._cached_bgra


class MockSensor:
    """Synthetic Webots DistanceSensor / LightSensor device."""

    def __init__(self, name: str, initial_value: float = 1000.0) -> None:
        self.name = name
        self._value = initial_value

    def enable(self, time_step: int) -> None:
        pass

    def getValue(self) -> float:
        return self._value


class StandaloneSupervisor:
    """
    Drop-in Webots Supervisor replacement when Webots GUI is not attached,
    pre-populated with all lights, doors, blinds, radiators, appliances,
    cameras, sensors, household objects, humans, and PAL Robotics TIAGo from `beacon_home.wbt`.
    """

    def __init__(self, time_step: int = 32) -> None:
        self._time_step = time_step
        self._nodes: list[MockNode] = []
        self._defs: dict[str, MockNode] = {}
        self._devices: dict[str, Any] = {}

        self._build_world()

    def _add_node(
        self,
        node_id: int,
        type_name: str,
        fields: dict[str, Any],
        def_name: str | None = None,
    ) -> MockNode:
        node = MockNode(node_id=node_id, type_name=type_name, fields=fields, def_name=def_name)
        self._nodes.append(node)
        if def_name:
            self._defs[def_name] = node
        return node

    def _build_world(self) -> None:
        nid = 100

        # Viewpoint & Sun
        self._add_node(
            nid,
            "Viewpoint",
            {
                "position": [-15.5, -14.2, 19.5],
                "orientation": [-0.18, 0.96, 0.21, 1.28],
            },
        )
        nid += 1
        self._add_node(
            nid,
            "TexturedBackgroundLight",
            {"luminosity": 0.8},
            def_name="SUN_LIGHT",
        )
        nid += 1

        # 18 Smart Lights from beacon_home.wbt
        lights_spec = [
            ("CeilingLight", "Kitchen Ceiling Light", [-1.334, -2.471, 2.4], [0.98, 0.92, 0.8], 3.0),
            ("CeilingLight", "Dining Room Light", [-10.124, -1.479, 2.4], [1.0, 1.0, 1.0], 2.5),
            ("CeilingLight", "Living Room Main Light", [-7.412, -4.344, 2.4], [1.0, 1.0, 1.0], 3.0),
            ("CeilingLight", "Foyer Hallway Light", [-1.794, -7.552, 2.4], [0.85, 0.92, 1.0], 2.5),
            ("CeilingLight", "West Corridor Light", [-5.364, -7.552, 2.4], [0.85, 0.92, 1.0], 2.5),
            ("CeilingLight", "Study Bedroom Light", [-7.622, -10.603, 2.4], [1.0, 1.0, 1.0], 2.8),
            ("CeilingLight", "Master Bedroom Light", [-1.945, -10.567, 2.4], [0.95, 0.82, 0.6], 2.8),
            ("CeilingLight", "Garage Ceiling Light", [2.1, -2.8, 2.38], [0.9, 0.95, 1.0], 2.5),
            ("FloorLight", "Living Room Corner Lamp", [-4.77, -0.496, 0.0], [0.95, 0.78, 0.5], 2.4),
            ("FloorLight", "Master Reading Lamp", [-0.59, -12.405, 0.0], [1.0, 1.0, 1.0], 2.0),
            ("FloorLight", "Front Porch Bollard Light", [0.8, -8.2, 0.0], [1.0, 0.85, 0.6], 2.5),
            ("FloorLight", "Driveway Bollard Light", [3.6, -8.8, 0.0], [1.0, 0.85, 0.6], 2.5),
            ("FloorLight", "Patio Lounge Lamp", [-11.5, -6.0, 0.0], [1.0, 0.75, 0.45], 2.0),
            ("CeilingSpotLight", "Guest Restroom Spot 1", [-7.72, -7.51, 2.36], [1.0, 1.0, 1.0], 3.0),
            ("CeilingSpotLight", "Guest Restroom Spot 2", [-8.7, -7.51, 2.36], [1.0, 1.0, 1.0], 3.0),
            ("CeilingSpotLight", "Bathroom Spot 1", [-4.52, -9.1, 2.36], [1.0, 1.0, 1.0], 3.0),
            ("CeilingSpotLight", "Bathroom Spot 2", [-4.52, -10.4, 2.36], [1.0, 1.0, 1.0], 3.0),
            ("CeilingSpotLight", "Bathroom Spot 3", [-4.52, -11.68, 2.36], [1.0, 1.0, 1.0], 3.0),
        ]
        for l_type, l_name, pos, color, intensity in lights_spec:
            int_key = "spotLightIntensity" if l_type == "CeilingSpotLight" else "pointLightIntensity"
            col_key = "spotLightColor" if l_type == "CeilingSpotLight" else "pointLightColor"
            self._add_node(
                nid,
                l_type,
                {
                    "name": l_name,
                    "translation": pos,
                    int_key: intensity,
                    col_key: color,
                },
            )
            nid += 1

        # 7 Interior Doors
        doors_spec = [
            ("Front Entrance Door", [0.0, -7.49, 0.0]),
            ("Kitchen Passage Door", [-3.89, -3.95, 0.0]),
            ("Master Bedroom Door", [-2.15, -8.43, 0.0]),
            ("Study Bedroom Door", [-6.24, -8.43, 0.0]),
            ("Main Bathroom Door", [-4.94, -8.43, 0.0]),
            ("Guest Restroom Door", [-6.97, -7.24, 0.0]),
            ("Utility Closet Door", [-0.91, -6.6, 0.0]),
        ]
        for d_name, pos in doors_spec:
            self._add_node(nid, "Door", {"name": d_name, "translation": pos})
            nid += 1

        # Exterior Barriers (Driveway Gate & Garage Door)
        for def_name, cfg in EXTERIOR_BARRIER_DEFS.items():
            c_pos = float(cfg["closed_pos"])
            trans = [c_pos, -9.55, 0.55] if cfg["axis"] == "x" else [2.1, -5.55, c_pos]
            self._add_node(
                nid,
                "Solid",
                {"name": str(cfg["name"]), "translation": trans},
                def_name=def_name,
            )
            nid += 1

        # 4 Motorized Window Blinds
        for def_name, cfg in BLIND_DEFS.items():
            self._add_node(
                nid,
                "Solid",
                {"name": str(cfg["name"]), "translation": [-5.0, -5.0, float(cfg["closed_z"])]},
                def_name=def_name,
            )
            nid += 1

        # 6 HVAC Radiators
        radiators = [
            "Hallway Radiator",
            "Master Bedroom Radiator",
            "Corridor Radiator",
            "Study Bedroom Radiator",
            "Living Room Radiator",
            "Kitchen Radiator",
        ]
        for r_name in radiators:
            self._add_node(nid, "Radiator", {"name": r_name, "translation": [-4.0, -6.0, 0.36]})
            nid += 1

        # Smart Appliances
        for app_name, cfg in APPLIANCE_DEFAULTS.items():
            self._add_node(nid, str(cfg["type"]), {"name": app_name})
            nid += 1

        # Physical Household Objects (OBJ_*)
        objects_spec = [
            ("OBJ_CUP", "cup", [-2.35, -2.15, 0.955]),
            ("OBJ_BOTTLE", "bottle", [-2.35, -2.45, 1.000]),
            ("OBJ_MEDICINE_BOX", "medicine_box", [-2.35, -2.75, 0.940]),
            ("OBJ_PLATE", "plate", [-2.68, -2.35, 0.915]),
            ("OBJ_TRAY", "tray", [-2.68, -2.70, 0.915]),
            ("OBJ_REMOTE_CONTROL", "remote_control", [-5.85, -2.65, 0.565]),
            ("OBJ_KEYS", "keys", [-10.10, -1.63, 0.755]),
            ("OBJ_BOOK", "book", [-6.85, -12.20, 0.735]),
            ("OBJ_PHONE", "phone", [-2.40, -9.80, 0.580]),
            ("OBJ_GLASSES", "glasses", [-1.43, -3.61, 0.755]),
        ]
        for def_name, obj_name, pos in objects_spec:
            self._add_node(nid, "SolidBox", {"name": obj_name, "translation": pos}, def_name=def_name)
            nid += 1

        # Pedestrian Humans (RESIDENT_HUMAN & GUEST_HUMAN)
        joint_fields = {
            j: 0.0
            for j in (
                "leftArmAngle", "leftLowerArmAngle", "leftHandAngle",
                "rightArmAngle", "rightLowerArmAngle", "rightHandAngle",
                "leftLegAngle", "leftLowerLegAngle", "leftFootAngle",
                "rightLegAngle", "rightLowerLegAngle", "rightFootAngle",
                "headAngle",
            )
        }
        self._add_node(
            nid,
            "Pedestrian",
            {
                "name": "Alex (Resident)",
                "translation": [-6.0, -3.1, 1.27],
                "rotation": [0.0, 0.0, 1.0, 0.0],
                **joint_fields,
            },
            def_name="RESIDENT_HUMAN",
        )
        nid += 1
        self._add_node(
            nid,
            "Pedestrian",
            {
                "name": "Sam (Visitor)",
                "translation": [1.6, -7.49, 1.27],
                "rotation": [0.0, 0.0, 1.0, 3.14159],
                **joint_fields,
            },
            def_name="GUEST_HUMAN",
        )
        nid += 1

        # BEACON_TIAGO (PAL Robotics TIAGo)
        self._add_node(
            nid,
            "Tiago",
            {
                "name": "TIAGo",
                "translation": [-3.1, -7.5, 0.095],
                "rotation": [0.0, 0.0, 1.0, 1.5708],
            },
            def_name="BEACON_TIAGO",
        )

        # Cameras & Sensors
        for cam_name in CAMERA_NAMES:
            self._devices[cam_name] = MockCamera(cam_name)
        for ms_name in MOTION_SENSOR_NAMES:
            self._devices[ms_name] = MockSensor(ms_name, 1000.0)
        for ls_name in LIGHT_SENSOR_NAMES:
            self._devices[ls_name] = MockSensor(ls_name, 800.0)

        self._root = MockNode(1, "Group", {"children": self._nodes})

    def getBasicTimeStep(self) -> float:
        return float(self._time_step)

    def getRoot(self) -> MockNode:
        return self._root

    def getFromDef(self, def_name: str) -> MockNode | None:
        return self._defs.get(def_name)

    def getDevice(self, name: str) -> Any:
        return self._devices.get(name)

    def step(self, time_step: int) -> int:
        time.sleep(max(0.005, time_step / 1000.0))
        return 0
