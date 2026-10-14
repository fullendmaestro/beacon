"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { Thermometer, PlugZap, Zap } from "lucide-react";
import { ToolCardShell, parseToolResult } from "./shared-tool-card";

export const GetClimateZonesToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_climate_zones",
  render: ({ result, status }) => {
    const zones = parseToolResult<any[]>(result) || [];
    return (
      <ToolCardShell
        title="Climate & HVAC Zones"
        subtitle={`${zones.length} room thermostats`}
        icon={Thermometer}
        iconColorClass="text-orange-500"
        status={status}
      >
        {Array.isArray(zones) && zones.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {zones.map((z) => (
              <div
                key={z.id}
                className="flex items-center justify-between rounded-xl border border-border/50 bg-muted/20 px-2.5 py-1.5"
              >
                <div className="flex flex-col min-w-0">
                  <span className="truncate font-medium text-foreground">
                    {z.name.replace(" Radiator", "")}
                  </span>
                  <span className="text-[10px] capitalize text-muted-foreground">
                    {z.mode}
                  </span>
                </div>
                <span className="font-bold text-orange-500">
                  {z.target_temp}°C
                </span>
              </div>
            ))}
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const SetClimateStateToolUI = makeAssistantToolUI<
  {
    zone_id: string;
    target_temp?: number;
    mode?: string;
    power_state?: string;
  },
  unknown
>({
  toolName: "set_climate_state",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={data?.name || args.zone_id}
        subtitle={
          data?.metadata ||
          `Mode: ${args.mode || "updated"} • Target: ${args.target_temp ?? "—"}°C`
        }
        icon={Thermometer}
        iconColorClass="text-orange-500"
        status={status}
        isError={data?.success === false}
        badge={
          data?.target_temp && (
            <span className="rounded-full bg-orange-500/15 px-2 py-0.5 text-[11px] font-bold text-orange-500">
              {data.target_temp}°C
            </span>
          )
        }
      />
    );
  },
});

export const GetAppliancesToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_appliances",
  render: ({ result, status }) => {
    const appliances = parseToolResult<any[]>(result) || [];
    const totalWatts = Array.isArray(appliances)
      ? appliances.reduce((acc, a) => acc + (Number(a.power_watts) || 0), 0)
      : 0;

    return (
      <ToolCardShell
        title="Smart Appliances & Plugs"
        subtitle={`Total Appliance Load: ${totalWatts.toFixed(1)} W`}
        icon={PlugZap}
        iconColorClass="text-purple-500"
        status={status}
      >
        {Array.isArray(appliances) && appliances.length > 0 && (
          <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto pr-1">
            {appliances.map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between rounded-xl border border-border/50 bg-muted/20 px-2.5 py-1.5"
              >
                <div className="flex flex-col min-w-0">
                  <span className="truncate font-medium text-foreground">
                    {a.name}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {a.room} • {a.mode}
                  </span>
                </div>
                <span className="flex items-center gap-1 text-[11px] font-semibold text-purple-500">
                  <Zap className="size-3" />
                  {a.power_watts}W
                </span>
              </div>
            ))}
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const SetApplianceStateToolUI = makeAssistantToolUI<
  { appliance_id: string; power_state?: string; mode?: string },
  unknown
>({
  toolName: "set_appliance_state",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={data?.name || args.appliance_id}
        subtitle={
          data?.message ||
          `State: ${args.power_state || "updated"} • Mode: ${args.mode || "default"}`
        }
        icon={PlugZap}
        iconColorClass="text-purple-500"
        status={status}
        isError={data?.success === false}
        badge={
          data?.power_watts !== undefined && (
            <span className="rounded-full bg-purple-500/15 px-2 py-0.5 text-[10px] font-bold text-purple-500">
              {data.power_watts} W
            </span>
          )
        }
      />
    );
  },
});
