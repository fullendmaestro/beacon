"use client";

import { useState, useEffect } from "react";
import {
  UserPlus,
  Home,
  CarFront,
  ShieldAlert,
  Moon,
  RotateCcw,
  Radar,
  Camera,
  Sparkles,
  Zap,
  Footprints,
  Activity,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { PanelLayout } from "./panel-layout";
import {
  smartHomeApi,
  type PedestrianMotionMode,
  type EventRuleRecord,
} from "@/lib/smart-home-api";
import {
  useBeaconSocket,
  setGlobalAutoWakeAgent,
} from "@/lib/use-beacon-socket";

const SCENARIO_CARDS = [
  {
    id: "guest_front_door",
    title: "Visitor Walks to Front Door",
    subtitle: "Webots Pedestrian walks forecourt → Porch sensor",
    sensorId: "front_porch_motion_sensor",
    cameraName: "Front Door Camera",
    kind: "human" as const,
    defaultMode: "walk" as PedestrianMotionMode,
    icon: UserPlus,
    accent: "text-sky-500 bg-sky-500/10 border-sky-500/30",
  },
  {
    id: "resident_living_room",
    title: "Resident Paces Living Room",
    subtitle: "Webots Pedestrian loops Living & Dining Room",
    sensorId: "living_room_motion_sensor",
    cameraName: "Living Room Camera",
    kind: "human" as const,
    defaultMode: "loop" as PedestrianMotionMode,
    icon: Home,
    accent: "text-emerald-500 bg-emerald-500/10 border-emerald-500/30",
  },
  {
    id: "intruder_hallway",
    title: "Pedestrian in West Corridor",
    subtitle: "Webots Pedestrian walks corridor sensor beam",
    sensorId: "hallway_motion_sensor",
    cameraName: "TIAGo Camera",
    kind: "human" as const,
    defaultMode: "loop" as PedestrianMotionMode,
    icon: ShieldAlert,
    accent: "text-rose-500 bg-rose-500/10 border-rose-500/30",
  },
  {
    id: "vehicle_driveway",
    title: "Car Arrives at Driveway Gate",
    subtitle: "Spawns 3D SUV at Driveway Gate sensor & opens gate",
    sensorId: "driveway_gate_motion_sensor",
    cameraName: "Driveway Camera",
    kind: "vehicle" as const,
    defaultMode: "stand" as PedestrianMotionMode,
    icon: CarFront,
    accent: "text-amber-500 bg-amber-500/10 border-amber-500/30",
  },
  {
    id: "sudden_nightfall",
    title: "Simulate Dusk / Nightfall",
    subtitle: "Drops Webots sun luminosity & trips roof daylight sensor",
    sensorId: "exterior_daylight_sensor",
    cameraName: "Backyard Patio Camera",
    kind: "environment" as const,
    defaultMode: "stand" as PedestrianMotionMode,
    icon: Moon,
    accent: "text-indigo-500 bg-indigo-500/10 border-indigo-500/30",
  },
] as const;

const CAMERA_OPTIONS = [
  "Front Door Camera",
  "Living Room Camera",
  "Kitchen Camera",
  "Driveway Camera",
  "Backyard Patio Camera",
  "Bedroom Camera",
  "TIAGo Camera",
];

export function SimulatorPanel() {
  const {
    devices,
    simMode,
    connected,
    pedestrians,
    busEvents,
    autoWakeAgent,
  } = useBeaconSocket();

  const [tab, setTab] = useState<"scenarios" | "events">("scenarios");
  const [activeCamera, setActiveCamera] = useState<string>("Front Door Camera");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pedestrianModes, setPedestrianModes] = useState<
    Record<string, PedestrianMotionMode>
  >({
    guest_front_door: "walk",
    resident_living_room: "loop",
    intruder_hallway: "loop",
  });
  const [rules, setRules] = useState<EventRuleRecord[]>([]);

  const sensors = devices.filter((d) => d.domain === "sensor");

  useEffect(() => {
    if (tab === "events") {
      smartHomeApi.getEventRules().then(setRules).catch(() => {});
    }
  }, [tab]);

  const handleTrigger = async (scenarioId: string, camName?: string) => {
    setBusyId(scenarioId);
    if (camName) setActiveCamera(camName);
    const mode = pedestrianModes[scenarioId];
    try {
      await smartHomeApi.triggerStimulus(
        scenarioId,
        autoWakeAgent,
        mode ? { motion_mode: mode } : undefined,
      );
    } finally {
      setTimeout(() => setBusyId(null), 450);
    }
  };

  const handleDeleteRule = async (ruleId: string) => {
    await smartHomeApi.deleteEventRule(ruleId);
    setRules((prev) => prev.filter((r) => r.id !== ruleId));
  };

  return (
    <PanelLayout
      title="Webots Event Simulator"
      subtitle="Articulated Pedestrian PROTOs, Sensors & Event Reactor"
      headerRight={
        <Button
          variant="ghost"
          size="icon"
          className="size-8 rounded-full text-muted-foreground hover:text-foreground"
          onClick={() => handleTrigger("clear_all")}
          title="Clear all spawned 3D actors"
        >
          <RotateCcw className="size-4" />
        </Button>
      }
      className="p-5 flex flex-col gap-4"
    >
      {/* Top Status & Auto-Wake Bar */}
      <div className="flex flex-col gap-2.5 rounded-2xl border border-border/60 bg-muted/30 p-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "size-2 rounded-full",
                connected ? "bg-emerald-500 animate-pulse" : "bg-amber-500",
              )}
            />
            <span className="text-xs font-semibold text-foreground">
              {simMode === "WEBOTS_ATTACHED"
                ? "Webots 3D Physics Active"
                : "Virtual Twin Active"}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 rounded-full px-2.5 text-[11px]"
            onClick={() => handleTrigger("clear_all")}
          >
            <RotateCcw className="size-3" />
            Clear Actors ({pedestrians.length})
          </Button>
        </div>

        <div className="flex items-center justify-between border-t border-border/50 pt-2.5">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Sparkles className="size-3.5 text-teal-500" />
            <span>Auto-wake Beacon Agent on event trigger</span>
          </div>
          <Switch
            checked={autoWakeAgent}
            onCheckedChange={setGlobalAutoWakeAgent}
          />
        </div>
      </div>

      {/* Sub-navigation Tabs */}
      <div className="grid grid-cols-2 gap-1.5 rounded-2xl border border-border/60 bg-muted/40 p-1">
        <button
          type="button"
          onClick={() => setTab("scenarios")}
          className={cn(
            "flex items-center justify-center gap-1.5 rounded-xl py-1.5 text-xs font-semibold transition-all",
            tab === "scenarios"
              ? "bg-background text-foreground shadow-xs"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Footprints className="size-3.5" />
          3D Pedestrians & Stimuli
        </button>
        <button
          type="button"
          onClick={() => setTab("events")}
          className={cn(
            "flex items-center justify-center gap-1.5 rounded-xl py-1.5 text-xs font-semibold transition-all",
            tab === "events"
              ? "bg-background text-foreground shadow-xs"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          <Activity className="size-3.5" />
          Event Stream ({busEvents.length})
        </button>
      </div>

      {/* Live Verification Camera Monitor */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <Camera className="size-3.5 text-teal-500" />
            Verification Feed
          </span>
          <select
            value={activeCamera}
            onChange={(e) => setActiveCamera(e.target.value)}
            className="h-7 rounded-lg border border-border/60 bg-background px-2 text-[11px] font-medium text-foreground"
          >
            {CAMERA_OPTIONS.map((cam) => (
              <option key={cam} value={cam}>
                {cam}
              </option>
            ))}
          </select>
        </div>

        <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-border bg-black shadow-inner">
          <div className="absolute left-3 top-3 z-10 flex items-center gap-1.5 rounded-full bg-black/65 px-2.5 py-0.5 text-[10px] font-bold text-white backdrop-blur-xs">
            <span className="size-1.5 rounded-full bg-red-500 animate-pulse" />
            {activeCamera}
          </div>
          <img
            src={smartHomeApi.getStreamUrl(activeCamera)}
            alt={activeCamera}
            className="h-full w-full object-cover"
          />
        </div>
      </div>

      {tab === "scenarios" ? (
        <>
          {/* One-Click Physical Stimulus Scenarios */}
          <div className="flex flex-col gap-2.5">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Spawn Webots Pedestrian & Sensor Events
            </span>

            <div className="flex flex-col gap-2.5">
              {SCENARIO_CARDS.map((card) => {
                const Icon = card.icon;
                const sensor = sensors.find((s) => s.id === card.sensorId);
                const isTriggered = Boolean(sensor?.reported_state?.triggered);
                const currentMode =
                  pedestrianModes[card.id] || card.defaultMode;

                return (
                  <div
                    key={card.id}
                    className={cn(
                      "flex flex-col gap-2.5 rounded-2xl border p-3 transition-all",
                      isTriggered
                        ? "border-red-500/50 bg-red-500/5"
                        : "border-border/60 bg-muted/20 hover:bg-muted/40",
                    )}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div
                          className={cn(
                            "flex size-10 shrink-0 items-center justify-center rounded-xl border",
                            card.accent,
                          )}
                        >
                          <Icon className="size-5" />
                        </div>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-semibold text-foreground">
                              {card.title}
                            </span>
                            {isTriggered && (
                              <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-bold text-red-500">
                                Tripped
                              </span>
                            )}
                          </div>
                          <span className="truncate text-xs text-muted-foreground">
                            {card.subtitle}
                          </span>
                        </div>
                      </div>

                      <Button
                        size="sm"
                        variant={isTriggered ? "default" : "outline"}
                        disabled={busyId === card.id}
                        className="h-8 shrink-0 gap-1.5 rounded-xl text-xs font-semibold"
                        onClick={() => handleTrigger(card.id, card.cameraName)}
                      >
                        <Zap className="size-3.5" />
                        Spawn
                      </Button>
                    </div>

                    {/* Pedestrian Gait Mode Selector */}
                    {card.kind === "human" && (
                      <div className="flex items-center justify-between border-t border-border/40 pt-2 text-[11px]">
                        <span className="flex items-center gap-1 text-muted-foreground">
                          <Footprints className="size-3 text-teal-500" />
                          Pedestrian Gait:
                        </span>
                        <div className="flex items-center gap-1">
                          {(["walk", "loop", "stand"] as const).map((m) => (
                            <button
                              key={m}
                              type="button"
                              onClick={() =>
                                setPedestrianModes((prev) => ({
                                  ...prev,
                                  [card.id]: m,
                                }))
                              }
                              className={cn(
                                "rounded-lg px-2 py-0.5 text-[10px] font-semibold capitalize transition-colors",
                                currentMode === m
                                    ? "bg-teal-500/20 text-teal-500 border border-teal-500/40"
                                  : "text-muted-foreground hover:bg-muted",
                              )}
                            >
                              {m === "walk"
                                ? "Walk Path"
                                : m === "loop"
                                  ? "Patrol Loop"
                                  : "Stand Still"}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Live Webots Sensor Telemetry Bar */}
          <div className="flex flex-col gap-2 border-t border-border/50 pt-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Live Webots Sensor Bus
            </span>
            <div className="grid grid-cols-1 gap-1.5">
              {sensors.map((s) => {
                const st = s.reported_state || {};
                const triggered = Boolean(st.triggered);
                return (
                  <div
                    key={s.id}
                    className="flex items-center justify-between rounded-xl border border-border/40 bg-muted/20 px-3 py-1.5 text-xs"
                  >
                    <span className="flex items-center gap-2 font-medium text-foreground">
                      <Radar
                        className={cn(
                          "size-3.5",
                          triggered
                            ? "text-red-500 animate-spin"
                            : "text-cyan-500",
                        )}
                      />
                      {s.wbt_name}
                    </span>
                    <span
                      className={cn(
                        "font-mono text-[11px] font-semibold",
                        triggered ? "text-red-500" : "text-emerald-500",
                      )}
                    >
                      {st.state || "Clear"} ({Number(st.value ?? 1000).toFixed(0)})
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      ) : (
        /* Live Event Stream & Active Automation Rules Tab */
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Active Event Reactor Rules ({rules.length})
            </span>
            <div className="flex flex-col gap-2">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="flex items-center justify-between gap-2 rounded-2xl border border-border/60 bg-muted/20 p-3 text-xs"
                >
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="truncate font-semibold text-foreground">
                      {rule.name}
                    </span>
                    <span className="truncate font-mono text-[10px] text-teal-500">
                      ON {rule.trigger_topic}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-7 shrink-0 text-muted-foreground hover:text-destructive"
                    onClick={() => handleDeleteRule(rule.id)}
                    title="Delete rule"
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-col gap-2 border-t border-border/50 pt-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Real-Time Broker Stream
            </span>
            <div className="flex max-h-64 flex-col gap-1.5 overflow-y-auto pr-1">
              {busEvents.length === 0 ? (
                <p className="text-xs text-muted-foreground py-4 text-center">
                  Trigger a scenario or toggle a device to watch live broker events.
                </p>
              ) : (
                busEvents.map((ev) => (
                  <div
                    key={ev.id}
                    className="flex flex-col gap-0.5 rounded-xl border border-border/40 bg-muted/20 px-2.5 py-1.5 text-[11px]"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono font-semibold text-teal-400">
                        {ev.topic}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(ev.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <span className="truncate text-[10px] text-muted-foreground">
                      {ev.payload?.wbt_name ||
                        ev.payload?.rule_name ||
                        ev.payload?.status ||
                        JSON.stringify(ev.payload)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </PanelLayout>
  );
}
