const BASE_URL =
  process.env.NEXT_PUBLIC_SMART_HOME_API_URL || "http://127.0.0.1:8000";

export type SmartCategory =
  | "Cameras"
  | "Lights"
  | "Locks & Doors"
  | "Blinds"
  | "Thermostats"
  | "Appliances"
  | "Sensors"
  | "Robots";

export type TimeOfDay = "day" | "sunset" | "night";
export type ScenePreset = "morning" | "away" | "movie" | "night";

export interface RobotDevice {
  id: string;
  name: string;
  model: string;
  type: string;
  status: string;
  current_room: string;
  current_node?: string;
  battery_pct: number;
  pose: { x: number; y: number; theta: number };
  target_destination?: string | null;
  arm_pose?: string;
  gripper?: "open" | "closed";
  held_object?: string;
  task_description?: string;
  online: boolean;
}

export interface RoverTelemetry {
  id: string;
  name: string;
  status: string;
  current_node: string;
  current_room: string;
  target_destination: string | null;
  position: [number, number, number];
  heading_rad: number;
  arm_pose: string;
  gripper: "grip" | "release";
  battery_pct: number;
  active_route_nodes: string[];
  available_nodes: string[];
}

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
  robot?: {
    status: string;
    current_room: string;
    target_destination: string | null;
    battery_pct?: number;
  };
  rover?: {
    status: string;
    current_room: string;
    target_destination: string | null;
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

  // Autonomous Mobile Robot (Beacon KUKA youBot)
  getRover: () => request<RoverTelemetry>("/api/rover"),
  planRoverRoute: (destination: string, start_node?: string) => {
    const query = start_node ? `?start_node=${encodeURIComponent(start_node)}` : "";
    return request<Record<string, unknown>>(
      `/api/rover/plan/${encodeURIComponent(destination)}${query}`,
    );
  },
  navigateRover: (destination: string) =>
    request<RoverTelemetry>("/api/rover/navigate", {
      method: "POST",
      body: JSON.stringify({ destination }),
    }),
  gotoRoverPose: (x: number, y: number, yaw = 0.0) =>
    request<RoverTelemetry>("/api/rover/goto_pose", {
      method: "POST",
      body: JSON.stringify({ x, y, yaw }),
    }),
  controlRover: (payload: {
    action: "stop" | "arm" | "gripper" | "velocity";
    arm_pose?: string;
    gripper_state?: "grip" | "release";
    vx?: number;
    vy?: number;
    omega?: number;
  }) =>
    request<RoverTelemetry>("/api/rover/control", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Beacon Home Robots (PAL Robotics TIAGo)
  getRobots: async (): Promise<RobotDevice[]> => {
    try {
      const res = await fetch("/api/robots", { cache: "no-store" });
      if (res.ok) return await res.json();
    } catch {
      // Fallback to hub endpoint
    }
    return request<RobotDevice[]>("/api/robots");
  },
  controlRobot: async (payload: {
    robot_id?: string;
    action: "navigate" | "stop" | "arm" | "gripper" | "head";
    destination?: string;
    pose?: string;
    gripper_state?: "open" | "closed";
    target?: string;
  }): Promise<{ success: boolean; status?: string } | RobotDevice> => {
    try {
      const res = await fetch("/api/robots", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) return await res.json();
    } catch {
      // Fallback
    }
    return request<{ success: boolean; status?: string } | RobotDevice>(
      "/api/robots",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },
  navigateRobot: (room: string, robotId = "tiago") =>
    smartHomeApi.controlRobot({
      robot_id: robotId,
      action: "navigate",
      destination: room,
    }),
  stopRobot: (robotId = "tiago") =>
    smartHomeApi.controlRobot({
      robot_id: robotId,
      action: "stop",
    }),
  setRobotArmPose: (pose: string, robotId = "tiago") =>
    smartHomeApi.controlRobot({
      robot_id: robotId,
      action: "arm",
      pose,
    }),
  setRobotGripper: (gripper_state: "open" | "closed", robotId = "tiago") =>
    smartHomeApi.controlRobot({
      robot_id: robotId,
      action: "gripper",
      gripper_state,
    }),
  setRobotHead: (target: string, robotId = "tiago") =>
    smartHomeApi.controlRobot({
      robot_id: robotId,
      action: "head",
      target,
    }),
};
