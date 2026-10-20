"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Users,
  Package,
  Radar,
  Bot,
  Sparkles,
  ShieldAlert,
  Navigation,
  ArrowUp,
  ArrowDown,
  ArrowLeft as ArrowWest,
  ArrowRight as ArrowEast,
  OctagonX,
  Repeat,
  RotateCcw,
  Camera,
  Check,
  X,
  Zap,
  Sun,
  Sunrise,
  Moon,
  Hand,
  Eye,
  MapPin,
  Radio,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import {
  smartHomeApi,
  type HumanActor,
  type HouseholdObject,
  type SensorDevice,
  type RobotDevice,
  type TasksAndEventsResponse,
  type TimeOfDay,
} from "@/lib/smart-home-api";
import {
  TIAGO_ROOMS,
  TIAGO_ARM_PRESETS,
  TIAGO_HEAD_TARGETS,
} from "@/components/panels/smart-home/constants";

const SCENARIO_CARDS = [
  {
    id: "visitor_front_door",
    title: "Visitor at Front Porch",
    desc: "Walks Sam (Visitor) into Front Porch sensor beam → Ambient porch light + HITL door unlock & TIAGo greeting.",
    badge: "Ambient + HITL",
  },
  {
    id: "driveway_arrival",
    title: "Driveway Gate Arrival",
    desc: "Walks Sam to Driveway Gate sensor → Ambient bollard light + HITL gate & garage opening approval.",
    badge: "HITL Security",
  },
  {
    id: "resident_living_room",
    title: "Resident Enters Living Room",
    desc: "Walks Alex (Resident) into Living Room motion beam → Ambient AI automatically balances room lights.",
    badge: "Ambient AI",
  },
  {
    id: "nightfall_lockdown",
    title: "Nightfall Perimeter Lockdown",
    desc: "Switches exterior sky to Night → Daylight sensor closes blinds & proposes HITL TIAGo security patrol.",
    badge: "Ambient + HITL",
  },
  {
    id: "kitchen_hazard",
    title: "Unattended Cooktop Alert",
    desc: "Activates Induction Cooktop on Boost Sear → triggers HITL safety shutoff & TIAGo kitchen inspection.",
    badge: "HITL Safety",
  },
  {
    id: "deliver_medicine",
    title: "Medication Delivery Errand",
    desc: "Queues HITL task for TIAGo to magnetic-grasp medicine_box in Kitchen and deliver to Master Bedroom.",
    badge: "HITL Errand",
  },
];

const CAMERA_FEEDS = [
  "TIAGo Camera",
  "Living Room Camera",
  "Kitchen Camera",
  "Front Door Camera",
  "Driveway Camera",
  "Bedroom Camera",
  "Backyard Patio Camera",
];

export default function DemoControlCenterPage() {
  const [humans, setHumans] = useState<HumanActor[]>([]);
  const [selectedHumanId, setSelectedHumanId] = useState<"resident" | "guest">(
    "resident",
  );
  const [teleportMode, setTeleportMode] = useState(false);

  const [objects, setObjects] = useState<HouseholdObject[]>([]);
  const [selectedObject, setSelectedObject] = useState<string>("bottle");
  const [selectedSurface, setSelectedSurface] =
    useState<string>("kitchen_island");
  const [deliverDestRoom, setDeliverDestRoom] = useState<string>("living_room");

  const [sensors, setSensors] = useState<SensorDevice[]>([]);
  const [robot, setRobot] = useState<RobotDevice | null>(null);
  const [tasksData, setTasksData] = useState<TasksAndEventsResponse | null>(
    null,
  );
  const [timeOfDay, setTimeOfDay] = useState<TimeOfDay>("day");
  const [activeCamera, setActiveCamera] = useState<string>("TIAGo Camera");
  const [statusToast, setStatusToast] = useState<string | null>(null);

  const notify = (msg: string) => {
    setStatusToast(msg);
    setTimeout(() => setStatusToast(null), 3500);
  };

  const fetchAll = useCallback(async () => {
    try {
      const [hList, oList, sList, rList, tData, summary] = await Promise.all([
        smartHomeApi.getHumans(),
        smartHomeApi.getObjects(),
        smartHomeApi.getSensors(),
        smartHomeApi.getRobots(),
        smartHomeApi.getTasks(),
        smartHomeApi.getSummary(),
      ]);
      setHumans(hList);
      setObjects(oList);
      setSensors(sList);
      setRobot(rList[0] || null);
      setTasksData(tData);
      if (summary?.environment?.time_of_day) {
        setTimeOfDay(summary.environment.time_of_day);
      }
    } catch {
      // Silent retry if hub is starting
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const timer = setInterval(fetchAll, 1200);
    return () => clearInterval(timer);
  }, [fetchAll]);

  const activeHuman =
    humans.find((h) => h.id === selectedHumanId) || humans[0] || null;
  const activeObjDetail =
    objects.find((o) => o.name === selectedObject) || objects[0] || null;
  const availableSurfaces = activeObjDetail?.available_surfaces || [
    { id: "kitchen_island", name: "Kitchen Island", room: "Kitchen", position: [-2.35, -2.4, 0.96] },
    { id: "coffee_table", name: "Coffee Table", room: "Living Room", position: [-5.85, -2.65, 0.57] },
    { id: "dining_table", name: "Dining Table", room: "Dining Room", position: [-10.1, -1.63, 0.76] },
    { id: "study_desk", name: "Study Desk", room: "Study Bedroom", position: [-6.85, -12.2, 0.74] },
    { id: "master_bed", name: "Master Bed", room: "Master Bedroom", position: [-2.4, -9.8, 0.58] },
    { id: "foyer_bench", name: "Foyer Bench", room: "Foyer", position: [-2.7, -7.2, 0.45] },
  ];

  // --- Handlers ---

  const handleHumanStep = async (dx: number, dy: number) => {
    notify(`Stepping ${selectedHumanId} by (${dx}m, ${dy}m)...`);
    await smartHomeApi.controlHuman({
      human_id: selectedHumanId,
      action: "step",
      dx,
      dy,
    });
    fetchAll();
  };

  const handleHumanLocation = async (locId: string, locName: string) => {
    const loc = activeHuman?.available_locations.find((l) => l.id === locId);
    if (teleportMode && loc) {
      notify(`Teleported ${activeHuman?.name} to ${locName}`);
      await smartHomeApi.controlHuman({
        human_id: selectedHumanId,
        action: "goto_coords",
        x: loc.pos[0],
        y: loc.pos[1],
        teleport: true,
      });
    } else {
      notify(`Walking ${activeHuman?.name} to ${locName}...`);
      await smartHomeApi.controlHuman({
        human_id: selectedHumanId,
        action: "goto_location",
        location: locId,
      });
    }
    fetchAll();
  };

  const handleMoveObject = async (surfaceId: string) => {
    setSelectedSurface(surfaceId);
    notify(`Spawned '${selectedObject}' onto ${surfaceId.replace(/_/g, " ")}`);
    await smartHomeApi.moveObject({
      object_name: selectedObject,
      surface: surfaceId,
    });
    fetchAll();
  };

  const handleResetObjects = async () => {
    notify("Reset all 10 household objects to default room surfaces");
    await smartHomeApi.resetObjects();
    fetchAll();
  };

  const handleTriggerScenario = async (scenarioId: string, title: string) => {
    notify(`Triggered scenario: ${title}`);
    await smartHomeApi.triggerScenario(scenarioId);
    fetchAll();
  };

  const handlePulseSensor = async (sensorId: string, sensorName: string) => {
    notify(`Pulsed Webots sensor: ${sensorName}`);
    await smartHomeApi.triggerSensor(sensorId);
    fetchAll();
  };

  return (
    <div className="min-h-svh w-full bg-background text-foreground">
      {/* Top Bar */}
      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1600px] flex-wrap items-center justify-between gap-4 px-6 py-3.5">
          <div className="flex items-center gap-3">
            <Button
              asChild
              variant="outline"
              size="sm"
              className="h-9 gap-1.5 rounded-full px-3.5 text-xs font-semibold"
            >
              <Link href="/home">
                <ArrowLeft className="size-3.5" />
                Back to Assistant
              </Link>
            </Button>
            <div>
              <h1 className="text-base font-bold tracking-tight">
                Beacon Webots Simulation & AI Control Center
              </h1>
              <p className="text-xs text-muted-foreground">
                Manually walk Pedestrian humans, spawn 3D graspable props, pulse
                sensors, and test Ambient + HITL AI workflows
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {statusToast && (
              <div className="rounded-full bg-teal-500/15 px-3.5 py-1 text-xs font-semibold text-teal-500 animate-in fade-in">
                {statusToast}
              </div>
            )}

            {/* Exterior Time of Day */}
            <div className="flex items-center gap-1 rounded-full border border-border bg-muted/40 p-1">
              {(
                [
                  { id: "day", label: "Day", icon: Sun },
                  { id: "sunset", label: "Sunset", icon: Sunrise },
                  { id: "night", label: "Night", icon: Moon },
                ] as const
              ).map((t) => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={async () => {
                      setTimeOfDay(t.id);
                      await smartHomeApi.setEnvironment(t.id);
                      notify(`Set exterior environment to ${t.label}`);
                    }}
                    className={cn(
                      "flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors",
                      timeOfDay === t.id
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <Icon className="size-3.5" />
                    {t.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </header>

      {/* Main 3-Column Grid */}
      <main className="mx-auto grid max-w-[1600px] grid-cols-1 gap-6 p-6 lg:grid-cols-12">
        {/* LEFT COLUMN (4 cols): Human Pedestrian Controller & 3D Object Spawner */}
        <div className="flex flex-col gap-6 lg:col-span-4">
          {/* 1. Pedestrian Human Actors Card */}
          <section className="flex flex-col gap-4 rounded-3xl border border-border bg-card p-5 shadow-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex size-9 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-500">
                  <Users className="size-5" />
                </div>
                <div>
                  <h2 className="text-sm font-bold">
                    Human Occupant & Visitor Control
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    Webots Pedestrian PROTO with 13-joint gait
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-muted-foreground">Teleport</span>
                <Switch
                  checked={teleportMode}
                  onCheckedChange={setTeleportMode}
                />
              </div>
            </div>

            {/* Selector: Alex (Resident) vs Sam (Visitor) */}
            <div className="grid grid-cols-2 gap-2">
              {humans.map((h) => {
                const isSel = h.id === selectedHumanId;
                return (
                  <button
                    key={h.id}
                    type="button"
                    data-testid={`select-human-${h.id}`}
                    onClick={() => setSelectedHumanId(h.id)}
                    className={cn(
                      "flex flex-col gap-1 rounded-2xl border p-3 text-left transition-colors",
                      isSel
                        ? "border-indigo-500 bg-indigo-500/10"
                        : "border-border/60 bg-muted/20 hover:bg-muted/40",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-foreground">
                        {h.name}
                      </span>
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                          h.status === "Walking"
                            ? "bg-amber-500/20 text-amber-500"
                            : "bg-emerald-500/15 text-emerald-500",
                        )}
                      >
                        {h.status}
                      </span>
                    </div>
                    <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                      <MapPin className="size-3 text-indigo-500" />
                      {h.current_room}
                    </span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      ({h.position[0].toFixed(1)}, {h.position[1].toFixed(1)})
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Manual Directional D-Pad */}
            <div className="flex flex-col gap-2 rounded-2xl border border-border/50 bg-muted/20 p-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Manual Walk D-Pad (1.2m Step)
                </span>
                <div className="flex gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1 rounded-xl text-[11px]"
                    onClick={async () => {
                      notify(`Started continuous patrol loop for ${activeHuman?.name}`);
                      await smartHomeApi.controlHuman({
                        human_id: selectedHumanId,
                        action: "patrol_loop",
                      });
                      fetchAll();
                    }}
                  >
                    <Repeat className="size-3" />
                    Loop Walk
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1 rounded-xl text-[11px] text-red-500"
                    onClick={async () => {
                      notify(`Stopped ${activeHuman?.name}`);
                      await smartHomeApi.controlHuman({
                        human_id: selectedHumanId,
                        action: "stop",
                      });
                      fetchAll();
                    }}
                  >
                    <OctagonX className="size-3" />
                    Stop
                  </Button>
                </div>
              </div>

              <div className="mx-auto grid w-44 grid-cols-3 gap-1.5 py-1">
                <div />
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-9 rounded-xl"
                  onClick={() => handleHumanStep(0, 1.2)}
                  title="Walk North (+Y)"
                >
                  <ArrowUp className="size-4" />
                </Button>
                <div />
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-9 rounded-xl"
                  onClick={() => handleHumanStep(-1.2, 0)}
                  title="Walk West (-X)"
                >
                  <ArrowWest className="size-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-9 rounded-xl text-[10px] font-bold"
                  onClick={async () => {
                    await smartHomeApi.controlHuman({
                      human_id: selectedHumanId,
                      action: "stop",
                    });
                    fetchAll();
                  }}
                >
                  HALT
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-9 rounded-xl"
                  onClick={() => handleHumanStep(1.2, 0)}
                  title="Walk East (+X)"
                >
                  <ArrowEast className="size-4" />
                </Button>
                <div />
                <Button
                  variant="secondary"
                  size="sm"
                  className="h-9 rounded-xl"
                  onClick={() => handleHumanStep(0, -1.2)}
                  title="Walk South (-Y)"
                >
                  <ArrowDown className="size-4" />
                </Button>
                <div />
              </div>
            </div>

            {/* Room & Sensor Zone Presets */}
            <div className="flex flex-col gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {teleportMode
                  ? "Teleport Human to Zone"
                  : "Walk Human to Room / Sensor Zone"}
              </span>
              <div className="grid grid-cols-2 gap-1.5">
                {(activeHuman?.available_locations || []).map((loc) => (
                  <Button
                    key={loc.id}
                    variant="outline"
                    size="sm"
                    data-testid={`human-goto-${loc.id}`}
                    className="h-8 justify-start gap-1.5 rounded-xl text-xs"
                    onClick={() => handleHumanLocation(loc.id, loc.name)}
                  >
                    <Navigation className="size-3 shrink-0 text-indigo-500" />
                    <span className="truncate">{loc.name}</span>
                  </Button>
                ))}
              </div>
            </div>
          </section>

          {/* 2. Physical 3D Household Objects & Surface Spawner */}
          <section className="flex flex-col gap-4 rounded-3xl border border-border bg-card p-5 shadow-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex size-9 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
                  <Package className="size-5" />
                </div>
                <div>
                  <h2 className="text-sm font-bold">
                    3D Graspable Object Spawner
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    Move props across rooms or dispatch TIAGo magnetic grasp
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="h-8 gap-1 rounded-xl text-xs"
                onClick={handleResetObjects}
              >
                <RotateCcw className="size-3.5" />
                Reset All
              </Button>
            </div>

            {/* 10 Graspable Props Grid */}
            <div className="grid grid-cols-2 gap-1.5">
              {objects.map((obj) => {
                const isSel = obj.name === selectedObject;
                const isHeld = robot?.held_object === obj.name;
                return (
                  <button
                    key={obj.name}
                    type="button"
                    data-testid={`select-object-${obj.name}`}
                    onClick={() => setSelectedObject(obj.name)}
                    className={cn(
                      "flex items-center justify-between rounded-xl border px-3 py-2 text-left transition-colors",
                      isSel
                        ? "border-amber-500 bg-amber-500/10"
                        : "border-border/60 bg-muted/20 hover:bg-muted/40",
                    )}
                  >
                    <div className="flex flex-col">
                      <span className="text-xs font-semibold capitalize text-foreground">
                        {obj.name.replace("_", " ")}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {isHeld ? "Held by TIAGo" : obj.room}
                      </span>
                    </div>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {obj.position[0].toFixed(1)},{obj.position[1].toFixed(1)}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Spawn / Move Selected Object onto Room Surface */}
            <div className="flex flex-col gap-2 border-t border-border/50 pt-3">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Spawn &ldquo;{selectedObject.replace("_", " ")}&rdquo; on Surface
              </span>
              <div className="grid grid-cols-2 gap-1.5">
                {availableSurfaces.map((surf) => (
                  <Button
                    key={surf.id}
                    variant={selectedSurface === surf.id ? "default" : "outline"}
                    size="sm"
                    data-testid={`spawn-surface-${surf.id}`}
                    className={cn(
                      "h-8 justify-start gap-1.5 rounded-xl text-xs",
                      selectedSurface === surf.id &&
                        "bg-amber-600 text-white hover:bg-amber-700",
                    )}
                    onClick={() => handleMoveObject(surf.id)}
                  >
                    <MapPin className="size-3 shrink-0" />
                    <span className="truncate">{surf.name}</span>
                  </Button>
                ))}
              </div>
            </div>

            {/* Dispatch TIAGo Magnetic Grasp Errand for Selected Object */}
            <div className="flex flex-col gap-2 rounded-2xl border border-teal-500/30 bg-teal-500/5 p-3">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-teal-500">
                TIAGo Magnetic Grasp Errand Dispatch
              </span>
              <div className="flex items-center gap-2">
                <select
                  value={deliverDestRoom}
                  onChange={(e) => setDeliverDestRoom(e.target.value)}
                  className="h-8 flex-1 rounded-xl border border-border bg-background px-2.5 text-xs"
                >
                  {TIAGO_ROOMS.map((r) => (
                    <option key={r.id} value={r.id}>
                      Deliver to: {r.label}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  className="h-8 rounded-xl bg-teal-600 text-xs font-semibold text-white hover:bg-teal-700"
                  onClick={async () => {
                    const fromRm = (activeObjDetail?.room || "kitchen")
                      .toLowerCase()
                      .replace(/\s+/g, "_");
                    notify(
                      `TIAGo delivering ${selectedObject} from ${fromRm} → ${deliverDestRoom}`,
                    );
                    await smartHomeApi.controlRobot({
                      action: "deliver",
                      item: selectedObject,
                      from_location: fromRm,
                      to_location: deliverDestRoom,
                    });
                    fetchAll();
                  }}
                >
                  Deliver Item
                </Button>
              </div>
            </div>
          </section>
        </div>

        {/* MIDDLE COLUMN (4 cols): Live Camera Feed, TIAGo Direct Controls & Sensor Beams */}
        <div className="flex flex-col gap-6 lg:col-span-4">
          {/* 3. Live Multi-Camera & TIAGo POV Feed */}
          <section className="flex flex-col gap-3 rounded-3xl border border-border bg-card p-5 shadow-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex size-9 items-center justify-center rounded-2xl bg-teal-500/10 text-teal-500">
                  <Camera className="size-5" />
                </div>
                <div>
                  <h2 className="text-sm font-bold">
                    Live Webots Camera & TIAGo POV
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    Real-time MJPEG stream from selected viewpoint
                  </p>
                </div>
              </div>
              <select
                value={activeCamera}
                onChange={(e) => setActiveCamera(e.target.value)}
                className="h-8 rounded-xl border border-border bg-background px-2.5 text-xs font-medium"
              >
                {CAMERA_FEEDS.map((cam) => (
                  <option key={cam} value={cam}>
                    {cam}
                  </option>
                ))}
              </select>
            </div>

            <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-border/60 bg-black">
              <div className="absolute left-3 top-3 z-10 flex items-center gap-1.5 rounded-full bg-black/65 px-2.5 py-0.5 text-[10px] font-semibold text-white backdrop-blur-xs">
                <span className="size-1.5 rounded-full bg-red-500 animate-pulse" />
                {activeCamera}
              </div>
              <img
                src={smartHomeApi.getStreamUrl(activeCamera)}
                alt={activeCamera}
                className="h-full w-full object-cover"
              />
            </div>

            {/* TIAGo Quick Telemetry & Controls */}
            {robot && (
              <div className="flex flex-col gap-3 rounded-2xl border border-border/60 bg-muted/20 p-3.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bot className="size-4 text-teal-500" />
                    <span className="text-xs font-bold">
                      {robot.name} ({robot.status})
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Room: <strong className="text-foreground">{robot.current_room}</strong> • Held:{" "}
                    <strong className="text-teal-500">
                      {robot.held_object || "None"}
                    </strong>
                  </span>
                </div>

                <div className="flex flex-wrap gap-1.5">
                  {TIAGO_ROOMS.map((rm) => (
                    <Button
                      key={rm.id}
                      variant="outline"
                      size="sm"
                      className="h-7 rounded-lg px-2.5 text-[11px]"
                      onClick={async () => {
                        notify(`Navigating TIAGo to ${rm.label}...`);
                        await smartHomeApi.navigateRobot(rm.id);
                        fetchAll();
                      }}
                    >
                      {rm.label}
                    </Button>
                  ))}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/40 pt-2">
                  <div className="flex gap-1">
                    {TIAGO_ARM_PRESETS.map((p) => (
                      <Button
                        key={p.id}
                        variant={robot.arm_pose === p.id ? "default" : "outline"}
                        size="sm"
                        className="h-7 rounded-lg px-2 text-[10px]"
                        onClick={async () => {
                          notify(`TIAGo arm → ${p.label}`);
                          await smartHomeApi.setRobotArmPose(p.id);
                          fetchAll();
                        }}
                      >
                        {p.label}
                      </Button>
                    ))}
                  </div>

                  <div className="flex gap-1">
                    {TIAGO_HEAD_TARGETS.map((t) => (
                      <Button
                        key={t.id}
                        variant="ghost"
                        size="sm"
                        className="h-7 rounded-lg px-1.5 text-[10px]"
                        onClick={async () => {
                          await smartHomeApi.setRobotHead(t.id);
                        }}
                      >
                        <Eye className="mr-0.5 size-3 text-teal-500" />
                        {t.label}
                      </Button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2 pt-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1 rounded-xl border-teal-500/40 bg-teal-500/10 text-xs font-semibold text-teal-500"
                    onClick={async () => {
                      notify("Started TIAGo Multi-Room Security Patrol");
                      await smartHomeApi.patrolRobot();
                      fetchAll();
                    }}
                  >
                    <RotateCcw className="size-3.5" />
                    Patrol Home
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1 rounded-xl text-xs"
                    onClick={async () => {
                      const nextState =
                        robot.gripper === "open" ? "closed" : "open";
                      notify(`Gripper → ${nextState}`);
                      await smartHomeApi.setRobotGripper(nextState);
                      fetchAll();
                    }}
                  >
                    <Hand className="size-3.5" />
                    Gripper: {robot.gripper}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1 rounded-xl border-red-500/40 bg-red-500/10 text-xs font-semibold text-red-500"
                    onClick={async () => {
                      notify("Stopped TIAGo");
                      await smartHomeApi.stopRobot();
                      fetchAll();
                    }}
                  >
                    <OctagonX className="size-3.5" />
                    Stop
                  </Button>
                </div>
              </div>
            )}
          </section>

          {/* 4. Webots Motion & Daylight Sensors with Direct Pulse Triggers */}
          <section className="flex flex-col gap-3 rounded-3xl border border-border bg-card p-5 shadow-xs">
            <div className="flex items-center gap-2">
              <div className="flex size-9 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-500">
                <Radar className="size-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold">
                  Webots Sensor Beams & Manual Pulse
                </h2>
                <p className="text-xs text-muted-foreground">
                  Walk a human across a beam or click Pulse to fire sensor edge
                  events
                </p>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              {sensors.map((s) => (
                <div
                  key={s.id}
                  className={cn(
                    "flex items-center justify-between rounded-2xl border px-3.5 py-2.5 transition-colors",
                    s.triggered
                      ? "border-red-500/50 bg-red-500/10"
                      : "border-border/50 bg-muted/20",
                  )}
                >
                  <div className="flex flex-col">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-foreground">
                        {s.name}
                      </span>
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                          s.triggered
                            ? "bg-red-500 text-white"
                            : "bg-emerald-500/15 text-emerald-500",
                        )}
                      >
                        {s.state}
                      </span>
                    </div>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      Raw Sensor Value: {s.value}
                    </span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    data-testid={`pulse-sensor-${s.id}`}
                    className="h-8 gap-1 rounded-xl text-xs font-semibold"
                    onClick={() => handlePulseSensor(s.id, s.name)}
                  >
                    <Radio className="size-3.5 text-cyan-500" />
                    Pulse Sensor
                  </Button>
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* RIGHT COLUMN (4 cols): Proactive AI Scenarios & Ambient/HITL Tasks Queue */}
        <div className="flex flex-col gap-6 lg:col-span-4">
          {/* 5. One-Click Proactive Scenario Triggers */}
          <section className="flex flex-col gap-3 rounded-3xl border border-border bg-card p-5 shadow-xs">
            <div className="flex items-center gap-2">
              <div className="flex size-9 items-center justify-center rounded-2xl bg-purple-500/10 text-purple-500">
                <Zap className="size-5" />
              </div>
              <div>
                <h2 className="text-sm font-bold">
                  Proactive Webots & AI Scenario Triggers
                </h2>
                <p className="text-xs text-muted-foreground">
                  Simulate end-to-end human + sensor + robot + AI workflows
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {SCENARIO_CARDS.map((sc) => (
                <button
                  key={sc.id}
                  type="button"
                  data-testid={`scenario-${sc.id}`}
                  onClick={() => handleTriggerScenario(sc.id, sc.title)}
                  className="flex flex-col justify-between gap-2 rounded-2xl border border-border/60 bg-muted/20 p-3 text-left transition-colors hover:border-teal-500/50 hover:bg-muted/40"
                >
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between gap-1">
                      <span className="text-xs font-bold text-foreground">
                        {sc.title}
                      </span>
                    </div>
                    <p className="text-[11px] leading-snug text-muted-foreground">
                      {sc.desc}
                    </p>
                  </div>
                  <span className="w-fit rounded-md bg-teal-500/15 px-2 py-0.5 text-[10px] font-bold text-teal-500">
                    {sc.badge}
                  </span>
                </button>
              ))}
            </div>
          </section>

          {/* 6. Live Ambient & Human-in-the-Loop (HITL) AI Task Queue */}
          <section className="flex flex-col gap-4 rounded-3xl border border-border bg-card p-5 shadow-xs">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex size-9 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
                  <Sparkles className="size-5" />
                </div>
                <div>
                  <h2 className="text-sm font-bold">
                    Ambient & HITL AI Tasks Queue
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    Synced with the main sidebar AI Tasks panel
                  </p>
                </div>
              </div>
              {tasksData && tasksData.pending_hitl_count > 0 && (
                <span className="rounded-full bg-amber-500 px-2.5 py-0.5 text-xs font-bold text-white">
                  {tasksData.pending_hitl_count} Pending
                </span>
              )}
            </div>

            <div className="flex items-center justify-between rounded-2xl border border-border/50 bg-muted/20 px-3.5 py-2.5 text-xs">
              <div className="flex items-center gap-2">
                <Sparkles className="size-3.5 text-teal-500" />
                <span className="font-semibold">Ambient Auto-AI</span>
                <Switch
                  checked={tasksData?.ambient_enabled ?? true}
                  onCheckedChange={async (checked) => {
                    const updated = await smartHomeApi.updateTaskSettings({
                      ambient_enabled: checked,
                    });
                    setTasksData(updated);
                  }}
                />
              </div>
              <div className="flex items-center gap-2">
                <ShieldAlert className="size-3.5 text-amber-500" />
                <span className="font-semibold">HITL Approvals</span>
                <Switch
                  checked={tasksData?.hitl_enabled ?? true}
                  onCheckedChange={async (checked) => {
                    const updated = await smartHomeApi.updateTaskSettings({
                      hitl_enabled: checked,
                    });
                    setTasksData(updated);
                  }}
                />
              </div>
            </div>

            <div className="flex max-h-[460px] flex-col gap-2.5 overflow-y-auto pr-1">
              {(tasksData?.tasks || []).map((task) => {
                const isPending = task.status === "pending_approval";
                return (
                  <div
                    key={task.id}
                    className={cn(
                      "flex flex-col gap-2 rounded-2xl border p-3",
                      isPending
                        ? "border-amber-500/40 bg-amber-500/5"
                        : "border-border/50 bg-muted/20",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={cn(
                          "rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase",
                          task.mode === "hitl"
                            ? "bg-amber-500/20 text-amber-500"
                            : "bg-teal-500/20 text-teal-500",
                        )}
                      >
                        {task.mode} • {task.room}
                      </span>
                      <span className="text-[10px] font-semibold uppercase text-muted-foreground">
                        {task.status.replace("_", " ")}
                      </span>
                    </div>
                    <div className="text-xs font-bold text-foreground">
                      {task.title}
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {task.description}
                    </p>
                    {isPending && (
                      <div className="grid grid-cols-2 gap-2 pt-1">
                        <Button
                          size="sm"
                          className="h-8 gap-1 rounded-xl bg-emerald-600 text-xs font-semibold text-white hover:bg-emerald-700"
                          onClick={async () => {
                            notify(`Approved task: ${task.title}`);
                            await smartHomeApi.approveTask(task.id);
                            fetchAll();
                          }}
                        >
                          <Check className="size-3.5" />
                          Approve & Execute
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 gap-1 rounded-xl text-xs"
                          onClick={async () => {
                            notify(`Dismissed task: ${task.title}`);
                            await smartHomeApi.rejectTask(task.id);
                            fetchAll();
                          }}
                        >
                          <X className="size-3.5" />
                          Dismiss
                        </Button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
