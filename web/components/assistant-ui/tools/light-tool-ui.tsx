"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { Lightbulb, Palette, SunMedium } from "lucide-react";
import { ToolCardShell, parseToolResult } from "./shared-tool-card";
import { cn } from "@/lib/utils";

export const GetLightsToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_lights",
  render: ({ result, status }) => {
    const lights = parseToolResult<any[]>(result) || [];
    const onCount = Array.isArray(lights)
      ? lights.filter((l) => l.power_state === "on" || l.state === "On").length
      : 0;

    return (
      <ToolCardShell
        title="Smart Lighting Scan"
        subtitle={
          status.type === "running"
            ? "Scanning lighting bus..."
            : `${onCount} of ${lights.length} lights active`
        }
        icon={Lightbulb}
        iconColorClass="text-amber-400"
        status={status}
      >
        {Array.isArray(lights) && lights.length > 0 && (
          <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
            {lights.map((l) => {
              const isOn = l.power_state === "on" || l.state === "On";
              return (
                <div
                  key={l.device_id || l.id}
                  className="flex items-center justify-between gap-2 rounded-xl border border-border/50 bg-muted/20 px-2.5 py-1.5"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span
                      className="size-2.5 shrink-0 rounded-full border border-border"
                      style={{
                        backgroundColor: isOn
                          ? l.color || "#fbbf24"
                          : "transparent",
                      }}
                    />
                    <span className="truncate font-medium text-foreground">
                      {l.name}
                    </span>
                  </div>
                  <span
                    className={cn(
                      "shrink-0 text-[10px] font-semibold uppercase",
                      isOn ? "text-amber-500" : "text-muted-foreground",
                    )}
                  >
                    {isOn ? `${l.brightness}%` : "Off"}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const GetLightStateToolUI = makeAssistantToolUI<
  { device_id: string },
  unknown
>({
  toolName: "get_light_state",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const isError = data?.isError || data?.success === false;
    const isOn = data?.power_state === "on";

    return (
      <ToolCardShell
        title={data?.name || `Inspect Light (${args.device_id})`}
        subtitle={isOn ? `On • ${data?.brightness ?? 100}%` : "Off"}
        icon={Lightbulb}
        iconColorClass={isOn ? "text-amber-400" : "text-muted-foreground"}
        status={status}
        isError={isError}
      />
    );
  },
});

export const SetPowerStateToolUI = makeAssistantToolUI<
  { device_id: string; power_state: "on" | "off" },
  unknown
>({
  toolName: "set_power_state",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const isError = data?.success === false;
    const isOn = (data?.power_state || args.power_state) === "on";

    return (
      <ToolCardShell
        title={data?.name || args.device_id}
        subtitle={
          status.type === "running"
            ? `Turning ${args.power_state}...`
            : data?.message || data?.error || `Power set to ${args.power_state}`
        }
        icon={Lightbulb}
        iconColorClass={isOn ? "text-amber-400" : "text-muted-foreground"}
        status={status}
        isError={isError}
        badge={
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
              isOn
                ? "bg-amber-500/15 text-amber-500"
                : "bg-muted text-muted-foreground",
            )}
          >
            {isOn ? "ON" : "OFF"}
          </span>
        }
      />
    );
  },
});

export const SetBrightnessToolUI = makeAssistantToolUI<
  { device_id: string; brightness_level: number },
  unknown
>({
  toolName: "set_brightness",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const pct = data?.brightness_level ?? args.brightness_level ?? 0;

    return (
      <ToolCardShell
        title={data?.name || args.device_id}
        subtitle={`Brightness adjusted to ${pct}%`}
        icon={SunMedium}
        iconColorClass="text-amber-400"
        status={status}
        isError={data?.success === false}
      >
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-amber-400 transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
          />
        </div>
      </ToolCardShell>
    );
  },
});

export const SetColorToolUI = makeAssistantToolUI<
  { device_id: string; color: string },
  unknown
>({
  toolName: "set_color",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const hexOrColor = data?.color || args.color;

    return (
      <ToolCardShell
        title={data?.name || args.device_id}
        subtitle={`Color set to ${args.color}`}
        icon={Palette}
        iconColorClass="text-pink-500"
        status={status}
        isError={data?.success === false}
        badge={
          <span
            className="size-4 rounded-full border border-border shadow-xs"
            style={{ backgroundColor: hexOrColor }}
            title={hexOrColor}
          />
        }
      />
    );
  },
});
