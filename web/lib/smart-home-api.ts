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

export interface HomeSummary {
  lights_on: number;
  total_lights: number;
  doors_open: number;
  total_doors: number;
  blinds_count: number;
  climate_zones: number;
  cameras_online: number;
  estimated_power_watts: number;
  sim_mode?: "WEBOTS_ATTACHED" | "VIRTUAL_PHYSICS_FALLBACK" | string;
  environment: {
    time_of_day: TimeOfDay;
    sun_luminosity: number;
  };
  robot?: {
    id?: string;
    name?: string;
    status: string;
    current_room: string;
    target_destination: string | null;
    battery_pct?: number;
    pose?: { x: number; y: number; theta: number };
  };
}

export interface LightDevice {
  id: string | number;
  device_id?: string;
  wbt_name?: string;
  name: string;
  state: "On" | "Off";
  type: string;
  brightness: number;
  color: string;
  color_rgb: number[];
  translation?: number[];
  metadata: string;
}

export interface CameraDevice {
  id: string;
  wbt_name?: string;
  name: string;
  state: "Online" | "Offline";
  metadata: string;
  type: "Camera";
  translation?: number[];
}

export interface DoorDevice {
  id: string;
  wbt_name?: string;
  name: string;
  type: "Door" | "SlidingGate" | "OverheadGarageDoor";
  state: "Open" | "Closed";
  position: number;
  locked: boolean;
  translation?: number[];
  rotation?: number[];
  metadata: string;
}

export interface BlindDevice {
  id: string;
  wbt_name?: string;
  name: string;
  room: string;
  type: "MotorizedBlind";
  state: "Open" | "Closed";
  position: number;
  translation?: number[];
  metadata: string;
}

export interface ClimateDevice {
  id: string | number;
  wbt_name?: string;
  name: string;
  type: "Radiator" | string;
  state: "On" | "Off";
  mode: "heat" | "cool" | "eco" | "off";
  current_temp: number;
  target_temp: number;
  translation?: number[];
  metadata: string;
}

export interface ApplianceDevice {
  id: string;
  wbt_name?: string;
  name: string;
  type: string;
  room: string;
  state: "On" | "Off";
  mode: string;
  power_watts: number;
  rated_watts: number;
  translation?: number[];
}

export interface SensorDevice {
  id: string;
  wbt_name?: string;
  name: string;
  type: "MotionSensor" | "DaylightSensor";
  state: string;
  value: number;
  triggered: boolean;
  translation?: number[];
}

export interface SimStimulusScenario {
  id: string;
  title: string;
  description: string;
  wbt_def: string;
  name: string;
  kind: "human" | "vehicle" | "environment";
  room_id: string;
  translation: [number, number, number];
  sensor_id: string;
  camera_name: string;
  agent_prompt: string;
}

export interface RoomPolygonRecord {
  id: string;
  name: string;
  polygon_2d: number[][];
}

export interface V2DeviceRecord {
  id: string;
  wbt_name: string;
  wbt_def?: string | null;
  domain: "light" | "door" | "blind" | "climate" | "appliance" | "sensor" | "camera";
  proto_type: string;
  room_id: string | null;
  room_name?: string | null;
  translation: [number, number, number] | number[];
  rotation: [number, number, number, number] | number[];
  config: Record<string, any>;
  controller_name: string;
  online: boolean;
  desired_state: Record<string, any>;
  reported_state: Record<string, any>;
}

export interface NavNodeRecord {
  id: string;
  name: string;
  room_id: string | null;
  room: string;
  x: number;
  y: number;
  default_theta: number;
  is_dock: boolean;
}

export interface NavEdgeRecord {
  id: number;
  from_node: string;
  to_node: string;
  blocking_device_id: string | null;
  blocking_door_name?: string | null;
}

export interface FloorplanData {
  sim_mode: string;
  rooms: RoomPolygonRecord[];
  devices: V2DeviceRecord[];
  nav_nodes: NavNodeRecord[];
  nav_edges: NavEdgeRecord[];
  robot: RobotDevice;
  environment: {
    time_of_day: TimeOfDay;
    sun_luminosity: number;
  };
}

export interface ProvisionDevicePayload {
  wbt_name: string;
  domain: "light" | "door" | "blind" | "climate" | "appliance" | "sensor" | "camera";
  proto_type: string;
  room_id?: string;
  translation: [number, number, number];
  rotation?: [number, number, number, number];
  config?: Record<string, any>;
  initial_state?: Record<string, any>;
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
  getWsUrl: () => {
    const wsBase = BASE_URL.replace(/^http/, "ws");
    return `${wsBase}/ws/events`;
  },

  getStreamUrl: (cameraName: string) =>
    `${BASE_URL}/api/cameras/${encodeURIComponent(cameraName)}/stream`,

  // V2 Decoupled Floorplan & Provisioning Endpoints
  getFloorplan: () => request<FloorplanData>("/api/v2/floorplan"),

  getV2Devices: (domain?: string, room_id?: string) => {
    const params = new URLSearchParams();
    if (domain) params.set("domain", domain);
    if (room_id) params.set("room_id", room_id);
    const qs = params.toString() ? `?${params.toString()}` : "";
    return request<V2DeviceRecord[]>(`/api/v2/devices${qs}`);
  },

  provisionDevice: (payload: ProvisionDevicePayload) =>
    request<{ success: boolean; device: V2DeviceRecord }>("/api/v2/devices", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  removeDevice: (identifier: string) =>
    request<{ success: boolean; device_id: string }>(
      `/api/v2/devices/${encodeURIComponent(identifier)}`,
      { method: "DELETE" },
    ),

  commandDevice: (
    identifier: string,
    action: string,
    params: Record<string, any>,
  ) =>
    request<{ success: boolean; device: V2DeviceRecord }>(
      `/api/v2/devices/${encodeURIComponent(identifier)}/command`,
      {
        method: "POST",
        body: JSON.stringify({ action, params }),
      },
    ),

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
  toggleLight: (id: string | number) =>
    request<LightDevice>(`/api/lights/${encodeURIComponent(String(id))}/toggle`, {
      method: "POST",
    }),
  updateLight: (
    id: string | number,
    payload: { power_state?: string; brightness?: number; color?: string },
  ) =>
    request<LightDevice>(`/api/lights/${encodeURIComponent(String(id))}/state`, {
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
    request<DoorDevice>(`/api/doors/${encodeURIComponent(id)}/state`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Motorized Blinds
  getBlinds: () => request<BlindDevice[]>("/api/blinds"),
  updateBlind: (id: string, position: number) =>
    request<BlindDevice>(`/api/blinds/${encodeURIComponent(id)}/state`, {
      method: "POST",
      body: JSON.stringify({ position }),
    }),

  // Thermostats / Climate Zones
  getClimate: () => request<ClimateDevice[]>("/api/climate"),
  updateClimate: (
    id: string | number,
    payload: {
      power_state?: "on" | "off";
      target_temp?: number;
      mode?: "heat" | "cool" | "eco" | "off";
    },
  ) =>
    request<ClimateDevice>(`/api/climate/${encodeURIComponent(String(id))}/state`, {
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


  // Beacon Home Robots (PAL Robotics TIAGo)
  getRobots: () => request<RobotDevice[]>("/api/robots"),
  controlRobot: (payload: {
    robot_id?: string;
    action: "navigate" | "stop" | "arm" | "gripper" | "head";
    destination?: string;
    pose?: string;
    gripper_state?: "open" | "closed";
    target?: string;
  }) =>
    request<{ success: boolean; status?: string } | RobotDevice>(
      "/api/robots",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
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

  // Webots Event Simulator Stimuli
  getStimuli: () => request<SimStimulusScenario[]>("/api/v2/sim/stimuli"),
  triggerStimulus: (scenario_id: string, trigger_agent = true) =>
    request<{ success: boolean; scenario?: SimStimulusScenario }>(
      "/api/v2/sim/stimulus",
      {
        method: "POST",
        body: JSON.stringify({ scenario_id, trigger_agent }),
      },
    ),
};
