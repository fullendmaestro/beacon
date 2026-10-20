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
  patrol_logs?: {
    room: string;
    timestamp: string;
    objects_seen: string[];
    humans_seen: string[];
  }[];
  online: boolean;
}

export interface HumanLocationOption {
  id: string;
  name: string;
  room: string;
  pos: [number, number];
}

export interface HumanActor {
  id: "resident" | "guest";
  def_name: string;
  name: string;
  role: string;
  position: [number, number, number];
  heading: number;
  speed: number;
  status: "Standing" | "Walking";
  current_room: string;
  waypoints: [number, number][];
  loop: boolean;
  available_locations: HumanLocationOption[];
}

export interface SurfaceOption {
  id: string;
  name: string;
  room: string;
  position: [number, number, number];
}

export interface HouseholdObject {
  name: string;
  def_name: string;
  room: string;
  position: [number, number, number];
  default_position: [number, number, number];
  default_room: string;
  available_surfaces: SurfaceOption[];
}

export interface ProposedAction {
  type: string;
  label?: string;
  [key: string]: unknown;
}

export interface AiTask {
  id: string;
  title: string;
  description: string;
  category: "security" | "comfort" | "errand" | "energy" | "safety";
  mode: "ambient" | "hitl";
  status: "pending_approval" | "running" | "completed" | "rejected";
  trigger_source: string;
  room: string;
  created_at: string;
  executed_at: string | null;
  proposed_actions: ProposedAction[];
  logs: string[];
}

export interface SimEvent {
  id: string;
  type: string;
  source: string;
  message: string;
  timestamp: string;
  task_id?: string | null;
}

export interface TasksAndEventsResponse {
  ambient_enabled: boolean;
  hitl_enabled: boolean;
  pending_hitl_count: number;
  ambient_completed_count: number;
  tasks: AiTask[];
  events: SimEvent[];
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
  pending_tasks?: number;
  environment: {
    time_of_day: TimeOfDay;
    sun_luminosity: number;
  };
  robot?: {
    status: string;
    current_room: string;
    target_destination: string | null;
    battery_pct?: number;
    held_object?: string;
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
  triggerSensor: (sensorId: string) =>
    request<{ status: string; sensor_id: string }>(
      `/api/sensors/${encodeURIComponent(sensorId)}/trigger`,
      { method: "POST" },
    ),

  // Beacon Home Robots (PAL Robotics TIAGo)
  getRobots: () => request<RobotDevice[]>("/api/robots"),
  controlRobot: (payload: {
    robot_id?: string;
    action:
      | "navigate"
      | "stop"
      | "arm"
      | "gripper"
      | "head"
      | "pick"
      | "place"
      | "patrol"
      | "fetch"
      | "deliver";
    destination?: string;
    pose?: string;
    gripper_state?: "open" | "closed";
    target?: string;
    object?: string;
    location?: string;
    rooms?: string[];
    item?: string;
    from_location?: string;
    to_location?: string;
  }) =>
    request<{ success?: boolean; status?: string } | RobotDevice>(
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
  pickRobotObject: (object: string) =>
    smartHomeApi.controlRobot({
      action: "pick",
      object,
    }),
  placeRobotObject: (location: string) =>
    smartHomeApi.controlRobot({
      action: "place",
      location,
    }),
  patrolRobot: (rooms?: string[]) =>
    smartHomeApi.controlRobot({
      action: "patrol",
      rooms,
    }),

  // Humans (Pedestrian PROTO Actors)
  getHumans: () => request<HumanActor[]>("/api/humans"),
  controlHuman: (payload: {
    human_id: "resident" | "guest";
    action: "goto_location" | "goto_coords" | "step" | "patrol_loop" | "stop";
    location?: string;
    x?: number;
    y?: number;
    dx?: number;
    dy?: number;
    teleport?: boolean;
  }) =>
    request<HumanActor>("/api/humans/control", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Physical Graspable 3D Household Objects
  getObjects: () => request<HouseholdObject[]>("/api/objects"),
  moveObject: (payload: {
    object_name: string;
    surface?: string;
    x?: number;
    y?: number;
    z?: number;
  }) =>
    request<HouseholdObject>("/api/objects/move", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  resetObjects: () =>
    request<HouseholdObject[]>("/api/objects/reset", {
      method: "POST",
    }),

  // Ambient & Human-in-the-Loop (HITL) AI Tasks & Events
  getTasks: () => request<TasksAndEventsResponse>("/api/tasks"),
  createTask: (payload: {
    title: string;
    description: string;
    category?: "security" | "comfort" | "errand" | "energy" | "safety";
    mode?: "ambient" | "hitl";
    trigger_source?: string;
    room?: string;
    proposed_actions?: ProposedAction[];
  }) =>
    request<AiTask>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  approveTask: (taskId: string) =>
    request<AiTask>(`/api/tasks/${encodeURIComponent(taskId)}/approve`, {
      method: "POST",
    }),
  rejectTask: (taskId: string) =>
    request<AiTask>(`/api/tasks/${encodeURIComponent(taskId)}/reject`, {
      method: "POST",
    }),
  updateTaskSettings: (payload: {
    ambient_enabled?: boolean;
    hitl_enabled?: boolean;
  }) =>
    request<TasksAndEventsResponse>("/api/tasks/settings", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  triggerScenario: (scenario: string) =>
    request<{ status: string; scenario: string; message: string }>(
      "/api/events/trigger",
      {
        method: "POST",
        body: JSON.stringify({ scenario }),
      },
    ),
};
