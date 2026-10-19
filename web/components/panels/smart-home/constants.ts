import {
  Camera,
  Lightbulb,
  Lock,
  Blinds,
  Thermometer,
  PlugZap,
  Radar,
  Bot,
  Sun,
  Sunrise,
  Moon,
  ShieldCheck,
  Film,
  type LucideIcon,
} from "lucide-react";
import type {
  SmartCategory,
  ScenePreset,
  TimeOfDay,
} from "@/lib/smart-home-api";

export interface CategoryMeta {
  name: SmartCategory;
  icon: LucideIcon;
  colorClass: string;
  description: string;
}

export const DEVICE_CATEGORIES: CategoryMeta[] = [
  {
    name: "Cameras",
    icon: Camera,
    colorClass: "text-blue-500 dark:text-blue-400",
    description: "6 live interior & exterior security feeds",
  },
  {
    name: "Lights",
    icon: Lightbulb,
    colorClass: "text-amber-400 dark:text-amber-500",
    description: "Smart ceiling, spot & exterior bollard lights",
  },
  {
    name: "Locks & Doors",
    icon: Lock,
    colorClass: "text-emerald-500 dark:text-emerald-400",
    description: "Entrance locks, garage door & driveway gate",
  },
  {
    name: "Blinds",
    icon: Blinds,
    colorClass: "text-indigo-500 dark:text-indigo-400",
    description: "Motorized window roller shades",
  },
  {
    name: "Thermostats",
    icon: Thermometer,
    colorClass: "text-orange-600 dark:text-orange-500",
    description: "6 room radiator & climate zones",
  },
  {
    name: "Appliances",
    icon: PlugZap,
    colorClass: "text-purple-500 dark:text-purple-400",
    description: "Smart TV, kitchen appliances & wall plugs",
  },
  {
    name: "Sensors",
    icon: Radar,
    colorClass: "text-cyan-500 dark:text-cyan-400",
    description: "Motion presence & roof daylight telemetry",
  },
  {
    name: "Robots",
    icon: Bot,
    colorClass: "text-teal-500 dark:text-teal-400",
    description: "PAL Robotics TIAGo mobile manipulator & errands",
  },
];

export const TIAGO_ROOMS = [
  { id: "foyer", label: "Foyer Dock", room: "Foyer" },
  { id: "living_room", label: "Living Room", room: "Living Room" },
  { id: "kitchen", label: "Kitchen", room: "Kitchen" },
  { id: "dining_room", label: "Dining Room", room: "Dining Room" },
  { id: "master_bedroom", label: "Master Bedroom", room: "Master Bedroom" },
  { id: "bathroom", label: "Main Bathroom", room: "Bathroom" },
  { id: "study_bedroom", label: "Study Bedroom", room: "Study Bedroom" },
];

export const TIAGO_ARM_PRESETS = [
  { id: "home", label: "Home", desc: "Safe rest tuck" },
  { id: "carry", label: "Carry", desc: "Transport position" },
  { id: "reach_table", label: "Reach Table", desc: "Table-height grab" },
  { id: "reach_floor", label: "Reach Floor", desc: "Low pickup" },
  { id: "handover", label: "Handover", desc: "Offer to user" },
];

export const TIAGO_HEAD_TARGETS = [
  { id: "forward", label: "Forward" },
  { id: "left", label: "Left" },
  { id: "right", label: "Right" },
  { id: "down", label: "Look Down" },
];

export const LIGHT_COLORS = [
  { name: "white", hex: "#ffffff" },
  { name: "warm white", hex: "#ffebaa" },
  { name: "soft white", hex: "#ffd9a6" },
  { name: "red", hex: "#ff0000" },
  { name: "green", hex: "#00ff00" },
  { name: "blue", hex: "#0033ff" },
  { name: "cyan", hex: "#00ffff" },
  { name: "magenta", hex: "#ff00ff" },
  { name: "yellow", hex: "#ffff00" },
  { name: "orange", hex: "#ff8000" },
  { name: "purple", hex: "#9919e6" },
  { name: "pink", hex: "#ff66b2" },
];

export const SCENE_PRESETS: {
  id: ScenePreset;
  label: string;
  icon: LucideIcon;
  description: string;
}[] = [
  {
    id: "morning",
    label: "Morning",
    icon: Sunrise,
    description: "Daylight sky, raise blinds, interior lights on",
  },
  {
    id: "movie",
    label: "Movie",
    icon: Film,
    description: "Sunset sky, lower blinds, dim warm living room, TV on",
  },
  {
    id: "away",
    label: "Away",
    icon: ShieldCheck,
    description: "All lights off, close blinds, lock all doors & gates",
  },
  {
    id: "night",
    label: "Goodnight",
    icon: Moon,
    description: "Night sky, lock perimeter, turn on exterior bollards",
  },
];

export const TIME_OF_DAY_OPTIONS: {
  id: TimeOfDay;
  label: string;
  icon: LucideIcon;
}[] = [
  { id: "day", label: "Day", icon: Sun },
  { id: "sunset", label: "Sunset", icon: Sunrise },
  { id: "night", label: "Night", icon: Moon },
];

export const APPLIANCE_MODE_OPTIONS: Record<string, string[]> = {
  Television: ["Cinema 4K HDR", "Ambient Art", "Gaming 120Hz", "Standby"],
  Fridge: ["Eco Cooling (3°C)", "Fast Freeze (-20°C)", "Vacation Mode"],
  Oven: ["Bake 180°C", "Convection Roast 200°C", "Broil", "Warm", "Off"],
  Microwave: ["Reheat", "Defrost", "Popcorn", "Ready"],
  Cooktop: ["Simmer", "Medium Boil", "Boost Sear", "Off"],
  WashingMachine: ["Cotton 40°C", "Quick Wash 20m", "Spin & Drain", "Idle"],
  Barbecue: ["Low Smoke 110°C", "Grill 220°C", "Sear 280°C", "Off"],
  WallPlug: ["On", "Eco Schedule", "Off"],
};
