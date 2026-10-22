"use client";

import { useState } from "react";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { PanelLayout } from "./panel-layout";
import { smartHomeApi } from "@/lib/smart-home-api";
import { useBeaconSocket } from "@/lib/use-beacon-socket";

const SCENARIO_CARDS = [
  {
    id: "guest_front_door",
    title: "Guest at Front Door",
    subtitle: "Spawns 3D visitor in Front Porch sensor beam",
    sensorId: "front_porch_motion_sensor",
    cameraName: "Front Door Camera",
    icon: UserPlus,
    accent: "text-sky-500 bg-sky-500/10 border-sky-500/30",
  },
  {
    id: "resident_living_room",
    title: "Resident in Living Room",
    subtitle: "Spawns 3D resident in Living Room sensor beam",
    sensorId: "living_room_motion_sensor",
    cameraName: "Living Room Camera",
    icon: Home,
    accent: "text-emerald-500 bg-emerald-500/10 border-emerald-500/30",
  },
  {
    id: "vehicle_driveway",
    title: "Car Arrives at Driveway Gate",
    subtitle: "Spawns 3D SUV at Driveway Gate sensor & opens gate",
    sensorId: "driveway_gate_motion_sensor",
    cameraName: "Driveway Camera",
    icon: CarFront,
    accent: "text-amber-500 bg-amber-500/10 border-amber-500/30",
  },
  {
    id: "intruder_hallway",
    title: "Motion in West Corridor",
    subtitle: "Spawns 3D figure in Hallway Motion Sensor beam",
    sensorId: "hallway_motion_sensor",
    cameraName: "TIAGo Camera",
    icon: ShieldAlert,
    accent: "text-rose-500 bg-rose-500/10 border-rose-500/30",
  },
  {
    id: "sudden_nightfall",
    title: "Simulate Dusk / Nightfall",
    subtitle: "Drops Webots sun luminosity & trips roof daylight sensor",
    sensorId: "exterior_daylight_sensor",
    cameraName: "Backyard Patio Camera",
    icon: Moon,
    accent: "text-indigo-500 bg-indigo-500/10 border-indigo-500/30",
  },
] as const;

export function SimulatorPanel() {
  const { devices, simMode, connected } = useBeaconSocket();
  const [autoWakeAgent, setAutoWakeAgent] = useState(true);
  const [activeCamera, setActiveCamera] = useState<string>("Front Door Camera");
  const [busyId, setBusyId] = useState<string | null>(null);

  const sensors = devices.filter((d) => d.domain === "sensor");

  const handleTrigger = async (scenarioId: string, camName?: string) => {
    setBusyId(scenarioId);
    if (camName) setActiveCamera(camName);
    try {
      await smartHomeApi.triggerStimulus(scenarioId, autoWakeAgent);
    } finally {
      setTimeout(() => setBusyId(null), 500);
    }
  };

  return (
    <PanelLayout
      title="Webots Event Simulator"
      subtitle="Spawn 3D actors & environmental triggers in real time"
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
      className="p-5 flex flex-col gap-5"
    >
      {/* Connection & Auto-Agent Toggle */}
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
            Reset World
          </Button>
        </div>

        <div className="flex items-center justify-between border-t border-border/50 pt-2.5">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Sparkles className="size-3.5 text-teal-500" />
            <span>Auto-wake Beacon Agent on sensor trigger</span>
          </div>
          <Switch checked={autoWakeAgent} onCheckedChange={setAutoWakeAgent} />
        </div>
      </div>

      {/* Live Camera Preview of the Triggered Zone */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <Camera className="size-3.5 text-teal-500" />
            Live Trigger Verification ({activeCamera})
          </span>
          <span className="flex items-center gap-1 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold text-red-500">
            <span className="size-1.5 rounded-full bg-red-500 animate-pulse" />
            LIVE
          </span>
        </div>
        <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-border bg-black shadow-inner">
          <img
            src={smartHomeApi.getStreamUrl(activeCamera)}
            alt={activeCamera}
            className="h-full w-full object-cover"
          />
        </div>
      </div>

      {/* One-Click Physical Stimulus Scenarios */}
      <div className="flex flex-col gap-2.5">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Spawn Physical Webots Events
        </span>

        <div className="flex flex-col gap-2.5">
          {SCENARIO_CARDS.map((card) => {
            const Icon = card.icon;
            const sensor = sensors.find((s) => s.id === card.sensorId);
            const isTriggered = Boolean(sensor?.reported_state?.triggered);

            return (
              <div
                key={card.id}
                className={cn(
                  "flex items-center justify-between gap-3 rounded-2xl border p-3 transition-all",
                  isTriggered
                    ? "border-red-500/50 bg-red-500/5"
                    : "border-border/60 bg-muted/20 hover:bg-muted/40",
                )}
              >
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
                          Sensor Tripped
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
                  Trigger
                </Button>
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
                      triggered ? "text-red-500 animate-spin" : "text-cyan-500",
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
    </PanelLayout>
  );
}
