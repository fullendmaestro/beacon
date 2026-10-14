"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
  Home,
  Radar,
  Camera,
  Sparkles,
  Sun,
  Calculator,
  Clock,
} from "lucide-react";
import { ToolCardShell, parseToolResult } from "./shared-tool-card";
import { smartHomeApi } from "@/lib/smart-home-api";
import { cn } from "@/lib/utils";

export const GetHomeSummaryToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_home_summary",
  render: ({ result, status }) => {
    const summary = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title="Estate Telemetry Summary"
        subtitle={
          summary
            ? `Sky: ${summary.environment?.time_of_day?.toUpperCase()} • Power: ${summary.estimated_power_watts} W`
            : "Gathering estate telemetry..."
        }
        icon={Home}
        iconColorClass="text-blue-500"
        status={status}
      >
        {summary && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">Lights On</div>
              <div className="mt-0.5 text-sm font-bold text-amber-500">
                {summary.lights_on}/{summary.total_lights}
              </div>
            </div>
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">
                Open Doors
              </div>
              <div className="mt-0.5 text-sm font-bold text-emerald-500">
                {summary.doors_open}/{summary.total_doors}
              </div>
            </div>
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">Load</div>
              <div className="mt-0.5 text-sm font-bold text-purple-500">
                {summary.estimated_power_watts} W
              </div>
            </div>
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const GetSensorsToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_sensors",
  render: ({ result, status }) => {
    const sensors = parseToolResult<any[]>(result) || [];
    return (
      <ToolCardShell
        title="Motion & Daylight Telemetry"
        subtitle={`${sensors.length} environmental sensors polled`}
        icon={Radar}
        iconColorClass="text-cyan-500"
        status={status}
      >
        {Array.isArray(sensors) && sensors.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {sensors.map((s) => (
              <div
                key={s.id}
                className="flex items-center justify-between rounded-xl border border-border/50 bg-muted/20 px-2.5 py-1.5"
              >
                <span className="font-medium text-foreground">{s.name}</span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                    s.triggered
                      ? "bg-red-500/15 text-red-500"
                      : "bg-emerald-500/15 text-emerald-500",
                  )}
                >
                  {s.state} ({s.value})
                </span>
              </div>
            ))}
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const GetCamerasToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_cameras",
  render: ({ result, status }) => {
    const cameras = parseToolResult<any[]>(result) || [];
    return (
      <ToolCardShell
        title="Security Camera Matrix"
        subtitle={`${cameras.length} live Webots feeds online`}
        icon={Camera}
        iconColorClass="text-blue-500"
        status={status}
      >
        {Array.isArray(cameras) && cameras.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {cameras.map((cam) => (
              <div
                key={cam.id}
                className="group relative aspect-video overflow-hidden rounded-xl border border-border bg-black"
              >
                <img
                  src={smartHomeApi.getStreamUrl(cam.name)}
                  alt={cam.name}
                  className="h-full w-full object-cover"
                />
                <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-2 py-1">
                  <span className="text-[10px] font-semibold text-white">
                    {cam.name}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const TriggerSceneToolUI = makeAssistantToolUI<
  { scene: string },
  unknown
>({
  toolName: "trigger_scene",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Smart Scene: ${args.scene.toUpperCase()}`}
        subtitle={
          data?.message || `Executed '${args.scene}' whole-home automation`
        }
        icon={Sparkles}
        iconColorClass="text-amber-500"
        status={status}
        isError={data?.success === false}
      />
    );
  },
});

export const SetEnvironmentToolUI = makeAssistantToolUI<
  { time_of_day: string },
  unknown
>({
  toolName: "set_environment",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title="Exterior Sky & Sun Updated"
        subtitle={`Time of day set to '${args.time_of_day}' (Luminosity: ${data?.sun_luminosity ?? "auto"})`}
        icon={Sun}
        iconColorClass="text-amber-400"
        status={status}
        isError={data?.success === false}
      />
    );
  },
});

export const CalculatorToolUI = makeAssistantToolUI<
  { expression: string },
  unknown
>({
  toolName: "calculator",
  render: ({ args, result, status }) => {
    const val = parseToolResult<string>(result);
    return (
      <ToolCardShell
        title={`Calculate: ${args.expression}`}
        subtitle={val ? `Result = ${val}` : "Computing..."}
        icon={Calculator}
        iconColorClass="text-emerald-500"
        status={status}
      />
    );
  },
});

export const UtcNowToolUI = makeAssistantToolUI<Record<string, never>, unknown>(
  {
    toolName: "utc_now",
    render: ({ result, status }) => {
      const val = parseToolResult<string>(result);
      return (
        <ToolCardShell
          title="System Clock (UTC)"
          subtitle={val || "Reading UTC clock..."}
          icon={Clock}
          iconColorClass="text-blue-400"
          status={status}
        />
      );
    },
  },
);
