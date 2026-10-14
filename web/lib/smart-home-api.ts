const BASE_URL =
  process.env.NEXT_PUBLIC_SMART_HOME_API_URL || "http://127.0.0.1:8000";

export type SmartCategory =
  | "Cameras"
  | "Lights"
  | "Locks & Doors"
  | "Blinds"
  | "Thermostats"
  | "Appliances"
  | "Sensors";

export type TimeOfDay = "day" | "sunset" | "night";
export type ScenePreset = "morning" | "away" | "movie" | "night";

export interface HomeSummary {
  lights_on: number;
  total_lights: number;
  doors_open: number;
  total_doors: number;
  blinds_count: number;
  climate_zones: number;
  cameras_online: number;
  estimated_power_watts: number;
  environment: {
    time_of_day: TimeOfDay;
    sun_luminosity: number;
  };
}

export interface LightDevice {
  id: number;
  name: string;
  state: "On" | "Off";
  type: string;
  brightness: number;
  color: string;
  color_rgb: number[];
  metadata: string;
}

export interface CameraDevice {
  id: string;
  name: string;
  state: "Online" | "Offline";
  metadata: string;
  type: "Camera";
}

export interface DoorDevice {
  id: string;
  name: string;
  type: "Door" | "SlidingGate" | "OverheadGarageDoor";
  state: "Open" | "Closed";
  position: number;
  locked: boolean;
  metadata: string;
}

export interface BlindDevice {
  id: string;
  name: string;
  room: string;
  type: "MotorizedBlind";
  state: "Open" | "Closed";
  position: number;
  metadata: string;
}

export interface ClimateDevice {
  id: number;
  name: string;
  type: "Radiator";
  state: "On" | "Off";
  mode: "heat" | "cool" | "eco" | "off";
  current_temp: number;
  target_temp: number;
  metadata: string;
}

export interface ApplianceDevice {
  id: string;
  name: string;
  type: string;
  room: string;
  state: "On" | "Off";
  mode: string;
  power_watts: number;
  rated_watts: number;
}

export interface SensorDevice {
  id: string;
  name: string;
  type: "MotionSensor" | "DaylightSensor";
  state: string;
  value: number;
  triggered: boolean;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    throw new Error(`Smart Home API error (${res.status}): ${path}`);
  }
  return res.json() as Promise<T>;
}

export const smartHomeApi = {
  getStreamUrl: (cameraName: string) =>
    `${BASE_URL}/api/cameras/${encodeURIComponent(cameraName)}/stream`,

  getSummary: () => request<HomeSummary>("/api/home/summary"),

  triggerScene: (scene: ScenePreset) =>
    request<{ success: boolean; scene: string }>("/api/home/scene", {
      method: "POST",
      body: JSON.stringify({ scene }),
    }),

  setEnvironment: (time_of_day: TimeOfDay) =>
    request<{ time_of_day: TimeOfDay; sun_luminosity: number }>(
      "/api/home/environment",
      {
        method: "POST",
        body: JSON.stringify({ time_of_day }),
      },
    ),

  // Lights
  getLights: () => request<LightDevice[]>("/api/lights"),
  toggleLight: (id: number) =>
    request<LightDevice>(`/api/lights/${id}/toggle`, { method: "POST" }),
  updateLight: (
    id: number,
    payload: { power_state?: string; brightness?: number; color?: string },
  ) =>
    request<LightDevice>(`/api/lights/${id}/state`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Cameras
  getCameras: () => request<CameraDevice[]>("/api/cameras"),

  // Doors, Garage & Gate
  getDoors: () => request<DoorDevice[]>("/api/doors"),
  updateDoor: (
    id: string,
    payload: {
      open_state?: "open" | "closed";
      locked?: boolean;
      position?: number;
    },
  ) =>
    request<DoorDevice>(`/api/doors/${id}/state`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Motorized Blinds
  getBlinds: () => request<BlindDevice[]>("/api/blinds"),
  updateBlind: (id: string, position: number) =>
    request<BlindDevice>(`/api/blinds/${id}/state`, {
      method: "POST",
      body: JSON.stringify({ position }),
    }),

  // Thermostats / Climate Zones
  getClimate: () => request<ClimateDevice[]>("/api/climate"),
  updateClimate: (
    id: number,
    payload: {
      power_state?: "on" | "off";
      target_temp?: number;
      mode?: "heat" | "cool" | "eco" | "off";
    },
  ) =>
    request<ClimateDevice>(`/api/climate/${id}/state`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Appliances & Smart Plugs
  getAppliances: () => request<ApplianceDevice[]>("/api/appliances"),
  updateAppliance: (
    id: string,
    payload: { power_state?: "on" | "off"; mode?: string },
  ) =>
    request<ApplianceDevice>(`/api/appliances/${id}/state`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Motion & Daylight Sensors
  getSensors: () => request<SensorDevice[]>("/api/sensors"),
};
