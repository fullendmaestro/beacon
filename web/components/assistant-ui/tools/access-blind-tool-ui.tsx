"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import { Lock, Unlock, DoorOpen, Blinds } from "lucide-react";
import { ToolCardShell, parseToolResult } from "./shared-tool-card";
import { cn } from "@/lib/utils";

export const GetDoorsToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_doors",
  render: ({ result, status }) => {
    const doors = parseToolResult<any[]>(result) || [];
    return (
      <ToolCardShell
        title="Doors, Locks & Exterior Gates"
        subtitle={`${doors.length} access barriers monitored`}
        icon={Lock}
        iconColorClass="text-emerald-500"
        status={status}
      >
        {Array.isArray(doors) && doors.length > 0 && (
          <div className="flex flex-col gap-1.5">
            {doors.map((d) => (
              <div
                key={d.id}
                className="flex items-center justify-between rounded-xl border border-border/50 bg-muted/20 px-2.5 py-1.5"
              >
                <span className="font-medium text-foreground">{d.name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-muted-foreground">
                    {d.state} ({d.position}%)
                  </span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                      d.locked
                        ? "bg-emerald-500/15 text-emerald-500"
                        : "bg-amber-500/15 text-amber-500",
                    )}
                  >
                    {d.locked ? "Locked" : "Unlocked"}
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

export const SetDoorStateToolUI = makeAssistantToolUI<
  { device_id: string; open_state?: "open" | "closed"; position?: number },
  unknown
>({
  toolName: "set_door_state",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const pct =
      data?.position ?? args.position ?? (args.open_state === "open" ? 100 : 0);

    return (
      <ToolCardShell
        title={data?.name || args.device_id}
        subtitle={data?.message || `Barrier set to ${pct}% open`}
        icon={DoorOpen}
        iconColorClass="text-emerald-500"
        status={status}
        isError={data?.success === false}
        badge={
          <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-500">
            {pct}% OPEN
          </span>
        }
      />
    );
  },
});

export const SetDoorLockToolUI = makeAssistantToolUI<
  { device_id: string; locked: boolean },
  unknown
>({
  toolName: "set_door_lock",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const isLocked = data?.locked ?? args.locked;

    return (
      <ToolCardShell
        title={data?.name || args.device_id}
        subtitle={
          data?.message || (isLocked ? "Barrier locked" : "Barrier unlocked")
        }
        icon={isLocked ? Lock : Unlock}
        iconColorClass={isLocked ? "text-emerald-500" : "text-amber-500"}
        status={status}
        isError={data?.success === false}
        badge={
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
              isLocked
                ? "bg-emerald-500/15 text-emerald-500"
                : "bg-amber-500/15 text-amber-500",
            )}
          >
            {isLocked ? "Locked" : "Unlocked"}
          </span>
        }
      />
    );
  },
});

export const GetBlindsToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_blinds",
  render: ({ result, status }) => {
    const blinds = parseToolResult<any[]>(result) || [];
    return (
      <ToolCardShell
        title="Motorized Window Blinds"
        subtitle={`${blinds.length} window shades`}
        icon={Blinds}
        iconColorClass="text-indigo-500"
        status={status}
      >
        {Array.isArray(blinds) && blinds.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {blinds.map((b) => (
              <div
                key={b.id}
                className="flex items-center justify-between rounded-xl border border-border/50 bg-muted/20 px-2.5 py-1.5"
              >
                <span className="truncate font-medium text-foreground">
                  {b.name}
                </span>
                <span className="text-[11px] font-semibold text-indigo-500">
                  {b.position}%
                </span>
              </div>
            ))}
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const SetBlindPositionToolUI = makeAssistantToolUI<
  { device_id: string; position: number },
  unknown
>({
  toolName: "set_blind_position",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const pct = data?.position ?? args.position ?? 0;

    return (
      <ToolCardShell
        title={data?.name || args.device_id}
        subtitle={data?.message || `Shade set to ${pct}% open`}
        icon={Blinds}
        iconColorClass="text-indigo-500"
        status={status}
        isError={data?.success === false}
      >
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
          />
        </div>
      </ToolCardShell>
    );
  },
});
