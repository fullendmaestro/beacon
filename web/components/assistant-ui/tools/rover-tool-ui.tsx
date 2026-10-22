"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
  Bot,
  Compass,
  Navigation,
  Wrench,
  Hand,
  Gauge,
  OctagonX,
} from "lucide-react";
import { ToolCardShell, parseToolResult } from "./shared-tool-card";
import { cn } from "@/lib/utils";

export const GetRoverTelemetryToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_rover_telemetry",
  render: ({ result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title="Beacon Rover Telemetry"
        subtitle={
          data
            ? `${data.status} • ${data.current_room} (${data.battery_pct ?? 98}% Battery)`
            : "Polling KUKA youBot telemetry..."
        }
        icon={Bot}
        iconColorClass="text-emerald-500"
        status={status}
        isError={!!data?.error}
      >
        {data && !data.error && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">Room</div>
              <div className="mt-0.5 truncate text-xs font-bold text-foreground">
                {data.current_room}
              </div>
            </div>
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">Arm Pose</div>
              <div className="mt-0.5 truncate text-xs font-bold text-blue-500">
                {data.arm_pose}
              </div>
            </div>
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">Gripper</div>
              <div className="mt-0.5 truncate text-xs font-bold text-amber-500">
                {data.gripper}
              </div>
            </div>
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const PlanRoverRouteToolUI = makeAssistantToolUI<
  { destination: string },
  unknown
>({
  toolName: "plan_rover_route",
  render: ({ args, result, status }) => {
    const plan = parseToolResult<any>(result);
    const blocked =
      Array.isArray(plan?.blocking_doors) && plan.blocking_doors.length > 0;

    return (
      <ToolCardShell
        title={`Route Plan → ${args.destination.replace(/_/g, " ")}`}
        subtitle={
          plan
            ? `${plan.total_distance_m ?? 0}m • ${(plan.corner_nodes || []).join(" → ")}`
            : "Computing orthogonal Dijkstra route..."
        }
        icon={Compass}
        iconColorClass={blocked ? "text-amber-500" : "text-cyan-500"}
        status={status}
        isError={!!plan?.error}
        badge={
          plan && !plan.error ? (
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                blocked
                  ? "bg-amber-500/15 text-amber-500"
                  : "bg-emerald-500/15 text-emerald-500",
              )}
            >
              {blocked ? `${plan.blocking_doors.length} Door Blocked` : "Clear"}
            </span>
          ) : undefined
        }
      />
    );
  },
});

export const NavigateRoverToRoomToolUI = makeAssistantToolUI<
  { destination: string },
  unknown
>({
  toolName: "navigate_rover_to_room",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const isBlocked =
      data?.status === "blocked_by_door" || data?.success === false;

    return (
      <ToolCardShell
        title={`Dispatch Rover → ${data?.target_destination || args.destination.replace(/_/g, " ")}`}
        subtitle={
          data?.message ||
          (data?.active_route_nodes?.length
            ? `Route: ${data.active_route_nodes.join(" → ")}`
            : `Navigating KUKA youBot to ${args.destination}`)
        }
        icon={Navigation}
        iconColorClass={isBlocked ? "text-amber-500" : "text-emerald-500"}
        status={status}
        isError={isBlocked || !!data?.error}
        badge={
          data?.status ? (
            <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold uppercase text-emerald-500">
              {data.status}
            </span>
          ) : undefined
        }
      />
    );
  },
});

export const NavigateRoverToPoseToolUI = makeAssistantToolUI<
  { x: number; y: number; yaw?: number },
  unknown
>({
  toolName: "navigate_rover_to_pose",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Rover Goto Pose (${args.x}, ${args.y})`}
        subtitle={data?.target_destination || `Heading yaw: ${args.yaw ?? 0} rad`}
        icon={Navigation}
        iconColorClass="text-emerald-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const SetRoverArmPoseToolUI = makeAssistantToolUI<
  { arm_pose: string },
  unknown
>({
  toolName: "set_rover_arm_pose",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`5-DOF Arm Pose: ${args.arm_pose}`}
        subtitle={`KUKA youBot manipulator set to '${data?.arm_pose || args.arm_pose}'`}
        icon={Wrench}
        iconColorClass="text-blue-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const SetRoverGripperToolUI = makeAssistantToolUI<
  { gripper_state: string },
  unknown
>({
  toolName: "set_rover_gripper",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Rover Gripper: ${args.gripper_state.toUpperCase()}`}
        subtitle={`Parallel gripper fingers set to '${data?.gripper || args.gripper_state}'`}
        icon={Hand}
        iconColorClass="text-amber-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const DriveRoverVelocityToolUI = makeAssistantToolUI<
  { vx?: number; vy?: number; omega?: number },
  unknown
>({
  toolName: "drive_rover_velocity",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title="Rover Mecanum Teleop"
        subtitle={`vx=${args.vx ?? 0} m/s, vy=${args.vy ?? 0} m/s, ω=${args.omega ?? 0} rad/s`}
        icon={Gauge}
        iconColorClass="text-purple-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const StopRoverToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "stop_rover",
  render: ({ result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title="Emergency / Navigation Stop"
        subtitle="Halted KUKA youBot base motors and cleared waypoints"
        icon={OctagonX}
        iconColorClass="text-red-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});
