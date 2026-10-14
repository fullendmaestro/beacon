"use client";

import { Zap, Lightbulb, DoorOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { SCENE_PRESETS, TIME_OF_DAY_OPTIONS } from "./constants";
import type { HomeSummary, ScenePreset, TimeOfDay } from "@/lib/smart-home-api";

interface HomeStatusHeaderProps {
  summary: HomeSummary | null;
  isTriggering: boolean;
  onTriggerScene: (scene: ScenePreset) => void;
  onSelectTimeOfDay: (tod: TimeOfDay) => void;
}

export function HomeStatusHeader({
  summary,
  isTriggering,
  onTriggerScene,
  onSelectTimeOfDay,
}: HomeStatusHeaderProps) {
  const activeTime = summary?.environment.time_of_day ?? "day";

  return (
    <div className="flex flex-col gap-4">
      {/* Live Telemetry Pills */}
      <div className="grid grid-cols-3 gap-2">
        <div className="flex flex-col rounded-2xl border border-border/60 bg-muted/40 px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-amber-500">
            <Lightbulb className="size-3.5" />
            <span className="text-[11px] font-semibold uppercase tracking-wider">
              Lights
            </span>
          </div>
          <span className="mt-1 text-sm font-bold text-foreground">
            {summary ? `${summary.lights_on}/${summary.total_lights} On` : "—"}
          </span>
        </div>

        <div className="flex flex-col rounded-2xl border border-border/60 bg-muted/40 px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-emerald-500">
            <DoorOpen className="size-3.5" />
            <span className="text-[11px] font-semibold uppercase tracking-wider">
              Access
            </span>
          </div>
          <span className="mt-1 text-sm font-bold text-foreground">
            {summary
              ? summary.doors_open > 0
                ? `${summary.doors_open} Open`
                : "All Locked"
              : "—"}
          </span>
        </div>

        <div className="flex flex-col rounded-2xl border border-border/60 bg-muted/40 px-3 py-2.5">
          <div className="flex items-center gap-1.5 text-purple-500">
            <Zap className="size-3.5" />
            <span className="text-[11px] font-semibold uppercase tracking-wider">
              Load
            </span>
          </div>
          <span className="mt-1 text-sm font-bold text-foreground">
            {summary ? `${summary.estimated_power_watts} W` : "—"}
          </span>
        </div>
      </div>

      {/* Exterior Sky & Sun Control */}
      <div className="flex items-center justify-between rounded-2xl border border-border/60 bg-card px-3 py-2">
        <span className="text-xs font-medium text-muted-foreground">
          Exterior Sun
        </span>
        <div className="flex items-center gap-1">
          {TIME_OF_DAY_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const isSelected = activeTime === opt.id;
            return (
              <Button
                key={opt.id}
                variant={isSelected ? "default" : "ghost"}
                size="sm"
                className={cn(
                  "h-7 gap-1.5 rounded-full px-2.5 text-xs",
                  !isSelected && "text-muted-foreground",
                )}
                onClick={() => onSelectTimeOfDay(opt.id)}
              >
                <Icon className="size-3.5" />
                {opt.label}
              </Button>
            );
          })}
        </div>
      </div>

      {/* Quick Automation Scenes */}
      <div className="flex flex-col gap-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Quick Scenes
        </span>
        <div className="grid grid-cols-4 gap-2">
          {SCENE_PRESETS.map((scene) => {
            const Icon = scene.icon;
            return (
              <button
                key={scene.id}
                disabled={isTriggering}
                onClick={() => onTriggerScene(scene.id)}
                title={scene.description}
                className="flex flex-col items-center justify-center gap-1.5 rounded-2xl border border-border/60 bg-muted/50 px-2 py-2.5 text-center transition-colors hover:bg-muted active:scale-95 disabled:opacity-50"
              >
                <Icon className="size-4 text-foreground" />
                <span className="text-[11px] font-medium text-foreground">
                  {scene.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
