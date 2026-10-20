"use client";

import { useState, useEffect, useCallback, useRef } from "react";
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
  type TasksAndEventsResponse,
  type ScenePreset,
  type TimeOfDay,
} from "@/lib/smart-home-api";

export function useSmartHomeSummary(pollInterval = 3500) {
  const [summary, setSummary] = useState<HomeSummary | null>(null);
  const [isTriggering, setIsTriggering] = useState(false);
  const inFlightRef = useRef(false);

  const fetchSummary = useCallback(async () => {
    if (inFlightRef.current) return;
    if (typeof document !== "undefined" && document.hidden) return;
    inFlightRef.current = true;
    try {
      const data = await smartHomeApi.getSummary();
      setSummary(data);
    } catch {
      // Silent retry on next tick if simulation is paused
    } finally {
      inFlightRef.current = false;
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
  const inFlightRef = useRef(false);

  const fetchCategory = useCallback(async () => {
    if (inFlightRef.current) return;
    if (typeof document !== "undefined" && document.hidden) return;
    inFlightRef.current = true;
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
      inFlightRef.current = false;
      setIsLoading(false);
    }
  }, [category]);

  useEffect(() => {
    setIsLoading(true);
    fetchCategory();
    const intervalMs =
      category === "Cameras"
        ? 10000
        : category === "Sensors" || category === "Robots"
          ? 2500
          : 3500;
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

export function useAiTasks(pollInterval = 3500) {
  const [data, setData] = useState<TasksAndEventsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const inFlightRef = useRef(false);

  const fetchTasks = useCallback(async () => {
    if (inFlightRef.current) return;
    if (typeof document !== "undefined" && document.hidden) return;
    inFlightRef.current = true;
    try {
      const res = await smartHomeApi.getTasks();
      setData(res);
    } catch {
      // Silent retry
    } finally {
      inFlightRef.current = false;
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
    const timer = setInterval(fetchTasks, pollInterval);
    return () => clearInterval(timer);
  }, [fetchTasks, pollInterval]);

  const approveTask = async (taskId: string) => {
    await smartHomeApi.approveTask(taskId);
    await fetchTasks();
  };

  const rejectTask = async (taskId: string) => {
    await smartHomeApi.rejectTask(taskId);
    await fetchTasks();
  };

  const updateSettings = async (payload: {
    ambient_enabled?: boolean;
    hitl_enabled?: boolean;
  }) => {
    const updated = await smartHomeApi.updateTaskSettings(payload);
    setData(updated);
  };

  const triggerScenario = async (scenario: string) => {
    await smartHomeApi.triggerScenario(scenario);
    await fetchTasks();
  };

  return {
    data,
    isLoading,
    refresh: fetchTasks,
    approveTask,
    rejectTask,
    updateSettings,
    triggerScenario,
  };
}
