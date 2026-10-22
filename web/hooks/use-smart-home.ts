"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  smartHomeApi,
  type SmartCategory,
  type LightDevice,
  type CameraDevice,
  type DoorDevice,
  type BlindDevice,
  type ClimateDevice,
  type ApplianceDevice,
  type SensorDevice,
  type RobotDevice,
  type ScenePreset,
  type TimeOfDay,
  type V2DeviceRecord,
} from "@/lib/smart-home-api";
import { useBeaconSocket } from "@/lib/use-beacon-socket";

export function useSmartHomeSummary() {
  const { summary, refresh, connected, simMode } = useBeaconSocket();
  const [isTriggering, setIsTriggering] = useState(false);

  const triggerScene = async (scene: ScenePreset) => {
    setIsTriggering(true);
    try {
      await smartHomeApi.triggerScene(scene);
      await refresh();
    } finally {
      setIsTriggering(false);
    }
  };

  const setTimeOfDay = async (timeOfDay: TimeOfDay) => {
    try {
      await smartHomeApi.setEnvironment(timeOfDay);
    } catch {
      await refresh();
    }
  };

  return {
    summary,
    connected,
    simMode,
    isTriggering,
    triggerScene,
    setTimeOfDay,
    refreshSummary: refresh,
  };
}

function mapV2ToLights(devices: V2DeviceRecord[]): LightDevice[] {
  return devices
    .filter((d) => d.domain === "light")
    .map((d) => {
      const st = d.reported_state || {};
      const isOn = st.state === "On" || st.power_state === "on";
      return {
        id: d.id,
        device_id: d.id,
        wbt_name: d.wbt_name,
        name: d.wbt_name,
        state: isOn ? "On" : "Off",
        type: d.proto_type,
        brightness: isOn ? Number(st.brightness ?? 100) : 0,
        color: st.color || "#ffffff",
        color_rgb: st.color_rgb || [1, 1, 1],
        translation: d.translation,
        metadata: st.metadata || `Intensity at ${Number(st.intensity ?? 0).toFixed(1)}`,
      };
    });
}

function mapV2ToDoors(devices: V2DeviceRecord[]): DoorDevice[] {
  return devices
    .filter((d) => d.domain === "door")
    .map((d) => {
      const st = d.reported_state || {};
      const pos = Number(st.position ?? 0);
      const locked = Boolean(st.locked);
      const stateStr = pos > 0 ? "Open" : "Closed";
      return {
        id: d.id,
        wbt_name: d.wbt_name,
        name: d.wbt_name,
        type: (d.proto_type as any) || "Door",
        state: stateStr,
        position: pos,
        locked,
        translation: d.translation,
        rotation: d.rotation,
        metadata: `${locked ? "Locked" : "Unlocked"} • ${stateStr} (${pos}%)`,
      };
    });
}

function mapV2ToBlinds(devices: V2DeviceRecord[]): BlindDevice[] {
  return devices
    .filter((d) => d.domain === "blind")
    .map((d) => {
      const st = d.reported_state || {};
      const pos = Number(st.position ?? 0);
      const room = d.room_name || st.room || "Home";
      return {
        id: d.id,
        wbt_name: d.wbt_name,
        name: d.wbt_name,
        room,
        type: "MotorizedBlind",
        state: pos > 0 ? "Open" : "Closed",
        position: pos,
        translation: d.translation,
        metadata: `${room} • ${pos}% Open`,
      };
    });
}

function mapV2ToClimate(devices: V2DeviceRecord[]): ClimateDevice[] {
  return devices
    .filter((d) => d.domain === "climate")
    .map((d) => {
      const st = d.reported_state || {};
      const mode = (st.mode || "eco") as "heat" | "cool" | "eco" | "off";
      const targetTemp = Number(st.target_temp ?? 22.0);
      const currentTemp = Number(st.current_temp ?? 21.5);
      return {
        id: d.id,
        wbt_name: d.wbt_name,
        name: d.wbt_name,
        type: d.proto_type || "Radiator",
        state: mode === "off" || st.state === "Off" ? "Off" : "On",
        mode,
        current_temp: currentTemp,
        target_temp: targetTemp,
        translation: d.translation,
        metadata: `${mode.charAt(0).toUpperCase() + mode.slice(1)} • Target ${targetTemp.toFixed(1)}°C`,
      };
    });
}

function mapV2ToAppliances(devices: V2DeviceRecord[]): ApplianceDevice[] {
  return devices
    .filter((d) => d.domain === "appliance")
    .map((d) => {
      const st = d.reported_state || {};
      const isOn = st.state === "On";
      const rated = Number(st.rated_watts ?? d.config?.rated_watts ?? 100);
      return {
        id: d.id,
        wbt_name: d.wbt_name,
        name: d.wbt_name,
        type: d.proto_type,
        room: d.room_name || st.room || "Home",
        state: isOn ? "On" : "Off",
        mode: st.mode || (isOn ? "Active" : "Off"),
        power_watts: Number(st.power_watts ?? (isOn ? rated : 2.5)),
        rated_watts: rated,
        translation: d.translation,
      };
    });
}

function mapV2ToSensors(devices: V2DeviceRecord[]): SensorDevice[] {
  return devices
    .filter((d) => d.domain === "sensor")
    .map((d) => {
      const st = d.reported_state || {};
      return {
        id: d.id,
        wbt_name: d.wbt_name,
        name: d.wbt_name,
        type: st.type || (d.proto_type === "LightSensor" ? "DaylightSensor" : "MotionSensor"),
        state: st.state || "Clear",
        value: Number(st.value ?? 1000),
        triggered: Boolean(st.triggered),
        translation: d.translation,
      };
    });
}

function mapV2ToCameras(devices: V2DeviceRecord[]): CameraDevice[] {
  const cams: CameraDevice[] = devices
    .filter((d) => d.domain === "camera")
    .map((d) => ({
      id: d.id,
      wbt_name: d.wbt_name,
      name: d.wbt_name,
      state: "Online",
      metadata: d.reported_state?.metadata || "Live • 640x480",
      type: "Camera",
      translation: d.translation,
    }));
  cams.push({
    id: "TIAGo Camera",
    wbt_name: "TIAGo Camera",
    name: "TIAGo Camera",
    state: "Online",
    metadata: "Live • 640x480 (Orbbec Astra RGB)",
    type: "Camera",
  });
  return cams;
}

export function useCategoryDevices(_category: SmartCategory) {
  const { devices, robot, refresh } = useBeaconSocket();
  const [lightsOverride, setLights] = useState<LightDevice[] | null>(null);
  const [doorsOverride, setDoors] = useState<DoorDevice[] | null>(null);
  const [blindsOverride, setBlinds] = useState<BlindDevice[] | null>(null);
  const [climateOverride, setClimate] = useState<ClimateDevice[] | null>(null);
  const [appliancesOverride, setAppliances] = useState<ApplianceDevice[] | null>(null);
  const [robotsOverride, setRobots] = useState<RobotDevice[] | null>(null);

  // Clear optimistic overrides whenever fresh WebSocket device state arrives
  useEffect(() => {
    setLights(null);
    setDoors(null);
    setBlinds(null);
    setClimate(null);
    setAppliances(null);
    setRobots(null);
  }, [devices, robot]);

  const lights = useMemo(() => lightsOverride ?? mapV2ToLights(devices), [lightsOverride, devices]);
  const cameras = useMemo(() => mapV2ToCameras(devices), [devices]);
  const doors = useMemo(() => doorsOverride ?? mapV2ToDoors(devices), [doorsOverride, devices]);
  const blinds = useMemo(() => blindsOverride ?? mapV2ToBlinds(devices), [blindsOverride, devices]);
  const climate = useMemo(() => climateOverride ?? mapV2ToClimate(devices), [climateOverride, devices]);
  const appliances = useMemo(
    () => appliancesOverride ?? mapV2ToAppliances(devices),
    [appliancesOverride, devices],
  );
  const sensors = useMemo(() => mapV2ToSensors(devices), [devices]);
  const robots = useMemo(
    () => robotsOverride ?? (robot ? [robot] : []),
    [robotsOverride, robot],
  );

  const isLoading = devices.length === 0 && !robot;

  const wrapSetter = useCallback(
    <T,>(current: T[], setter: React.Dispatch<React.SetStateAction<T[] | null>>) =>
      (updater: React.SetStateAction<T[]>) => {
        setter((prev) => {
          const base = prev ?? current;
          return typeof updater === "function"
            ? (updater as (p: T[]) => T[])(base)
            : updater;
        });
      },
    [],
  );

  return {
    lights,
    setLights: wrapSetter(lights, setLights),
    cameras,
    doors,
    setDoors: wrapSetter(doors, setDoors),
    blinds,
    setBlinds: wrapSetter(blinds, setBlinds),
    climate,
    setClimate: wrapSetter(climate, setClimate),
    appliances,
    setAppliances: wrapSetter(appliances, setAppliances),
    sensors,
    robots,
    setRobots: wrapSetter(robots, setRobots),
    isLoading,
    refresh,
  };
}

