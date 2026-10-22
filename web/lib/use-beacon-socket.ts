"use client";

import { useEffect, useState, useCallback } from "react";
import {
  smartHomeApi,
  type FloorplanData,
  type HomeSummary,
  type V2DeviceRecord,
  type RobotDevice,
  type RoomPolygonRecord,
  type NavNodeRecord,
  type NavEdgeRecord,
} from "./smart-home-api";

export interface BeaconEventAlert {
  alert_id: string;
  rule_id: string;
  rule_name: string;
  trigger_topic: string;
  message: string;
  executed_actions: string[];
  camera_name?: string | null;
  agent_prompt?: string | null;
  timestamp: number;
}

interface BeaconSocketStore {
  connected: boolean;
  simMode: string;
  summary: HomeSummary | null;
  rooms: RoomPolygonRecord[];
  devices: V2DeviceRecord[];
  navNodes: NavNodeRecord[];
  navEdges: NavEdgeRecord[];
  robot: RobotDevice | null;
  alerts: BeaconEventAlert[];
}

const initialState: BeaconSocketStore = {
  connected: false,
  simMode: "VIRTUAL_PHYSICS_FALLBACK",
  summary: null,
  rooms: [],
  devices: [],
  navNodes: [],
  navEdges: [],
  robot: null,
  alerts: [],
};

let storeState: BeaconSocketStore = { ...initialState };
const listeners = new Set<(state: BeaconSocketStore) => void>();
let wsInstance: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let isConnecting = false;

function notify() {
  for (const listener of listeners) {
    listener(storeState);
  }
}

function recomputeSummary(state: BeaconSocketStore): HomeSummary | null {
  if (!state.summary && state.devices.length === 0) return state.summary;
  const lights = state.devices.filter((d) => d.domain === "light");
  const doors = state.devices.filter((d) => d.domain === "door");
  const blinds = state.devices.filter((d) => d.domain === "blind");
  const climates = state.devices.filter((d) => d.domain === "climate");
  const appliances = state.devices.filter((d) => d.domain === "appliance");
  const cameras = state.devices.filter((d) => d.domain === "camera");

  const lightsOn = lights.filter(
    (l) => l.reported_state?.state === "On" || l.reported_state?.power_state === "on",
  ).length;
  const doorsOpen = doors.filter(
    (d) => d.reported_state?.state === "Open" || Number(d.reported_state?.position || 0) > 0,
  ).length;

  const appWatts = appliances.reduce(
    (acc, a) => acc + Number(a.reported_state?.power_watts ?? 2.5),
    0,
  );
  const hvacWatts = climates.reduce(
    (acc, c) => acc + (c.reported_state?.state === "On" ? 350 : 0),
    0,
  );
  const lightWatts = lightsOn * 12;

  return {
    lights_on: lightsOn,
    total_lights: lights.length,
    doors_open: doorsOpen,
    total_doors: doors.length,
    blinds_count: blinds.length,
    climate_zones: climates.length,
    cameras_online: cameras.length + 1,
    estimated_power_watts: Number((appWatts + hvacWatts + lightWatts).toFixed(1)),
    sim_mode: state.simMode,
    environment: state.summary?.environment || {
      time_of_day: "day",
      sun_luminosity: 0.85,
    },
    robot: state.robot
      ? {
          id: state.robot.id,
          name: state.robot.name,
          status: state.robot.status,
          current_room: state.robot.current_room,
          target_destination: state.robot.target_destination ?? null,
          battery_pct: state.robot.battery_pct,
          pose: state.robot.pose,
        }
      : state.summary?.robot,
  };
}

async function fetchInitialHttpSnapshot() {
  try {
    const [fp, sum] = await Promise.all([
      smartHomeApi.getFloorplan(),
      smartHomeApi.getSummary(),
    ]);
    storeState = {
      ...storeState,
      simMode: fp.sim_mode || sum.sim_mode || storeState.simMode,
      summary: sum,
      rooms: fp.rooms || [],
      devices: fp.devices || [],
      navNodes: fp.nav_nodes || [],
      navEdges: fp.nav_edges || [],
      robot: fp.robot || null,
    };
    notify();
  } catch {
    // Hub may still be starting up
  }
}

function ensureWebSocketConnected() {
  if (typeof window === "undefined") return;
  if (wsInstance && (wsInstance.readyState === WebSocket.OPEN || wsInstance.readyState === WebSocket.CONNECTING)) {
    return;
  }
  if (isConnecting) return;
  isConnecting = true;

  try {
    const ws = new WebSocket(smartHomeApi.getWsUrl());
    wsInstance = ws;

    ws.onopen = () => {
      isConnecting = false;
      storeState = { ...storeState, connected: true };
      notify();
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        const topic: string = msg.topic || "";
        const payload: any = msg.payload || {};
        if (msg.sim_mode) {
          storeState.simMode = msg.sim_mode;
        }

        if (topic === "hub.snapshot") {
          storeState = {
            connected: true,
            simMode: payload.sim_mode || storeState.simMode,
            summary: payload.summary || storeState.summary,
            rooms: payload.rooms || storeState.rooms,
            devices: payload.devices || storeState.devices,
            navNodes: payload.nav_nodes || storeState.navNodes,
            navEdges: payload.nav_edges || storeState.navEdges,
            robot: payload.robot || storeState.robot,
            alerts: storeState.alerts,
          };
          notify();
          return;
        }

        if (topic === "agent.event.alert") {
          const nextAlerts = [payload as BeaconEventAlert, ...storeState.alerts].slice(0, 20);
          storeState = { ...storeState, alerts: nextAlerts };
          notify();
          return;
        }

        if (topic === "device.lifecycle.provisioned") {
          const exists = storeState.devices.some((d) => d.id === payload.id);
          const nextDevices = exists
            ? storeState.devices.map((d) => (d.id === payload.id ? payload : d))
            : [...storeState.devices, payload];
          storeState = { ...storeState, devices: nextDevices };
          storeState.summary = recomputeSummary(storeState);
          notify();
          return;
        }

        if (topic === "device.lifecycle.removed") {
          const remId = payload.device_id || payload.id;
          const nextDevices = storeState.devices.filter((d) => d.id !== remId);
          storeState = { ...storeState, devices: nextDevices };
          storeState.summary = recomputeSummary(storeState);
          notify();
          return;
        }

        if (topic.startsWith("device.state.") || topic.startsWith("sensor.telemetry.")) {
          const devId = payload.device_id;
          const nextDevices = storeState.devices.map((d) => {
            if (d.id !== devId) return d;
            const nextReported = payload.state
              ? { ...d.reported_state, ...payload.state }
              : {
                  ...d.reported_state,
                  triggered: payload.triggered ?? d.reported_state.triggered,
                  value: payload.value ?? d.reported_state.value,
                  state: payload.state ?? d.reported_state.state,
                };
            return {
              ...d,
              reported_state: nextReported,
            };
          });
          storeState = { ...storeState, devices: nextDevices };
          storeState.summary = recomputeSummary(storeState);
          notify();
          return;
        }

        if (topic === "robot.telemetry.tiago") {
          const prevRobot = storeState.robot || {
            id: "tiago",
            name: "TIAGo",
            model: "PAL Robotics TIAGo",
            type: "Mobile Manipulator",
            status: "Docked",
            current_room: "Foyer",
            battery_pct: 92,
            pose: { x: -3.1, y: -7.62, theta: 1.5708 },
            online: true,
          };
          const nextRobot: RobotDevice = {
            ...prevRobot,
            pose: payload.pose || prevRobot.pose,
            status: payload.status || prevRobot.status,
            battery_pct: payload.battery ?? payload.battery_pct ?? prevRobot.battery_pct,
            current_room: payload.current_room || prevRobot.current_room,
            target_destination:
              payload.target_destination !== undefined
                ? payload.target_destination
                : prevRobot.target_destination,
            arm_pose: payload.arm_pose || prevRobot.arm_pose,
            gripper: payload.gripper || prevRobot.gripper,
            held_object:
              payload.held_object !== undefined ? payload.held_object : prevRobot.held_object,
            task_description: payload.task || payload.task_description || prevRobot.task_description,
            online: true,
          };
          (nextRobot as any).active_route = payload.active_route || (prevRobot as any).active_route || [];
          storeState = { ...storeState, robot: nextRobot };
          storeState.summary = recomputeSummary(storeState);
          notify();
          return;
        }

        if (topic === "environment.updated") {
          if (storeState.summary) {
            storeState = {
              ...storeState,
              summary: {
                ...storeState.summary,
                environment: payload,
              },
            };
            notify();
          }
          return;
        }

        if (topic === "scene.triggered") {
          fetchInitialHttpSnapshot();
        }
      } catch {
        // Ignore malformed frame
      }
    };

    ws.onclose = () => {
      isConnecting = false;
      wsInstance = null;
      storeState = { ...storeState, connected: false };
      notify();
      if (!reconnectTimer) {
        reconnectTimer = setTimeout(() => {
          reconnectTimer = null;
          ensureWebSocketConnected();
        }, 1500);
      }
    };

    ws.onerror = () => {
      isConnecting = false;
    };
  } catch {
    isConnecting = false;
  }
}

export function useBeaconSocket() {
  const [state, setState] = useState<BeaconSocketStore>(storeState);

  useEffect(() => {
    listeners.add(setState);
    if (!storeState.summary && storeState.devices.length === 0) {
      fetchInitialHttpSnapshot();
    }
    ensureWebSocketConnected();
    return () => {
      listeners.delete(setState);
    };
  }, []);

  const refresh = useCallback(async () => {
    await fetchInitialHttpSnapshot();
  }, []);

  return {
    ...state,
    refresh,
  };
}
