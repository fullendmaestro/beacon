"use client";

import { useState, useEffect, useCallback } from "react";
import {
  smartHomeApi,
  type SmartCategory,
  type HomeSummary,
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
} from "@/lib/smart-home-api";

export function useSmartHomeSummary(pollInterval = 2500) {
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);

  const fetchSummary = useCallback(async () => {
    try {
      const data = await smartHomeApi.getSummary();
      setSummary(data);
    } catch {
      // Silent retry on next tick if simulation is paused
    }
  }, []);

  useEffect(() => {
    fetchSummary();
    const timer = setInterval(fetchSummary, pollInterval);
    return () => clearInterval(timer);
  }, [fetchSummary, pollInterval]);

  const triggerScene = async (scene: ScenePreset) => {
    setIsTriggering(true);
    try {
      await smartHomeApi.triggerScene(scene);
      await fetchSummary();
    } finally {
      setIsTriggering(false);
    }
  };

  const setTimeOfDay = async (timeOfDay: TimeOfDay) => {
    setSummary((prev) =>
      prev
        ? {
            ...prev,
            environment: { ...prev.environment, time_of_day: timeOfDay },
          }
        : prev,
    );
    try {
      await smartHomeApi.setEnvironment(timeOfDay);
      await fetchSummary();
    } catch {
      fetchSummary();
    }
  };

  return {
    summary,
    isTriggering,
    triggerScene,
    setTimeOfDay,
    refreshSummary: fetchSummary,
  };
}

export function useCategoryDevices(category: SmartCategory) {
  const [lights, setLights] = useState<LightDevice[]>([]);
  const [cameras, setCameras] = useState<CameraDevice[]>([]);
  const [doors, setDoors] = useState<DoorDevice[]>([]);
  const [blinds, setBlinds] = useState<BlindDevice[]>([]);
  const [climate, setClimate] = useState<ClimateDevice[]>([]);
  const [appliances, setAppliances] = useState<ApplianceDevice[]>([]);
  const [sensors, setSensors] = useState<SensorDevice[]>([]);
  const [robots, setRobots] = useState<RobotDevice[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCategory = useCallback(async () => {
    try {
      switch (category) {
        case "Lights":
          setLights(await smartHomeApi.getLights());
          break;
        case "Cameras":
          setCameras(await smartHomeApi.getCameras());
          break;
        case "Locks & Doors":
          setDoors(await smartHomeApi.getDoors());
          break;
        case "Blinds":
          setBlinds(await smartHomeApi.getBlinds());
          break;
        case "Thermostats":
          setClimate(await smartHomeApi.getClimate());
          break;
        case "Appliances":
          setAppliances(await smartHomeApi.getAppliances());
          break;
        case "Sensors":
          setSensors(await smartHomeApi.getSensors());
          break;
        case "Robots":
          setRobots(await smartHomeApi.getRobots());
          break;
      }
    } catch {
      // Silent retry on next poll tick if Smart Home Hub is offline or restarting
    } finally {
      setIsLoading(false);
    }
  }, [category]);

  useEffect(() => {
    setIsLoading(true);
    fetchCategory();
    const intervalMs =
      category === "Cameras"
        ? 8000
        : category === "Sensors" || category === "Robots"
          ? 1200
          : 2000;
    const timer = setInterval(fetchCategory, intervalMs);
    return () => clearInterval(timer);
  }, [fetchCategory, category]);

  return {
    lights,
    setLights,
    cameras,
    doors,
    setDoors,
    blinds,
    setBlinds,
    climate,
    setClimate,
    appliances,
    setAppliances,
    sensors,
    robots,
    setRobots,
    isLoading,
    refresh: fetchCategory,
  };
}
