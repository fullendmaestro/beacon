"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
  Bot,
  Compass,
  Navigation,
  Wrench,
  Hand,
  Eye,
  Package,
  ShieldCheck,
  OctagonX,
  Sparkles,
  Users,
} from "lucide-react";
import { ToolCardShell, parseToolResult } from "./shared-tool-card";
import { cn } from "@/lib/utils";

export const GetTiagoTelemetryToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_tiago_telemetry",
  render: ({ result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title="PAL Robotics TIAGo Telemetry"
        subtitle={
          data
            ? `${data.task || data.status || "Idle"} • ${data.current_room || "Foyer"} (${data.battery ?? data.battery_pct ?? 98}% Battery)`
            : "Polling TIAGo supervisor telemetry..."
        }
        icon={Bot}
        iconColorClass="text-teal-500"
        status={status}
        isError={!!data?.error}
      >
        {data && !data.error && (
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">Room</div>
              <div className="mt-0.5 truncate text-xs font-bold text-foreground">
                {data.current_room || "Foyer"}
              </div>
            </div>
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">Arm Pose</div>
              <div className="mt-0.5 truncate text-xs font-bold text-blue-500">
                {data.arm_pose || "home"}
              </div>
            </div>
            <div className="rounded-xl border border-border/50 bg-muted/20 p-2">
              <div className="text-[10px] text-muted-foreground">Held Object</div>
              <div className="mt-0.5 truncate text-xs font-bold text-teal-500">
                {data.held_object || "Empty"}
              </div>
            </div>
          </div>
        )}
      </ToolCardShell>
    );
  },
});

export const PlanTiagoRouteToolUI = makeAssistantToolUI<
  { destination: string },
  unknown
>({
  toolName: "plan_tiago_route",
  render: ({ args, result, status }) => {
    const plan = parseToolResult<any>(result);
    const blocked =
      Array.isArray(plan?.blocking_doors) && plan.blocking_doors.length > 0;

    return (
      <ToolCardShell
        title={`TIAGo Route Plan → ${args.destination.replace(/_/g, " ")}`}
        subtitle={
          plan
            ? `${plan.distance_m ?? 0}m • ${plan.waypoints?.length ?? 0} waypoints`
            : "Computing orthogonal Manhattan route..."
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

export const NavigateTiagoToRoomToolUI = makeAssistantToolUI<
  { room: string },
  unknown
>({
  toolName: "navigate_tiago_to_room",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Dispatch TIAGo → ${args.room.replace(/_/g, " ")}`}
        subtitle={`Navigating PAL Robotics TIAGo to ${args.room}`}
        icon={Navigation}
        iconColorClass="text-teal-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const NavigateTiagoToPoseToolUI = makeAssistantToolUI<
  { x: number; y: number; theta: number },
  unknown
>({
  toolName: "navigate_tiago_to_pose",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`TIAGo Goto Pose (${args.x}, ${args.y})`}
        subtitle={`Heading θ: ${args.theta ?? 0} rad`}
        icon={Navigation}
        iconColorClass="text-teal-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const SetTiagoArmPoseToolUI = makeAssistantToolUI<
  { pose_name: string },
  unknown
>({
  toolName: "set_tiago_arm_pose",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`7-DoF Arm Pose: ${args.pose_name}`}
        subtitle={`TIAGo manipulator set to '${data?.arm_pose || args.pose_name}'`}
        icon={Wrench}
        iconColorClass="text-blue-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const SetTiagoGripperToolUI = makeAssistantToolUI<
  { state: string },
  unknown
>({
  toolName: "set_tiago_gripper",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Robotiq 2F-85 Gripper: ${args.state.toUpperCase()}`}
        subtitle={`Parallel gripper fingers set to '${data?.gripper || args.state}'`}
        icon={Hand}
        iconColorClass="text-amber-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const PickObjectToolUI = makeAssistantToolUI<
  { object_name: string },
  unknown
>({
  toolName: "pick_object",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Magnetic Grasp Pick: ${args.object_name}`}
        subtitle="Supervisor-Assisted Magnetic Grasp locking object to wrist"
        icon={Hand}
        iconColorClass="text-teal-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const PlaceObjectToolUI = makeAssistantToolUI<
  { location: string },
  unknown
>({
  toolName: "place_object",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Place Object at ${args.location.replace(/_/g, " ")}`}
        subtitle="Releasing magnetic grasp onto target surface"
        icon={Package}
        iconColorClass="text-amber-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const InspectSceneVisuallyToolUI = makeAssistantToolUI<
  { query?: string; room?: string; sweep?: boolean },
  unknown
>({
  toolName: "inspect_scene_visually",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Multimodal Visual Inspector${args.room ? ` (${args.room.replace(/_/g, " ")})` : ""}`}
        subtitle={data?.visual_summary || args.query || "Sweeping head camera & analyzing scene..."}
        icon={Eye}
        iconColorClass="text-cyan-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const DeliverItemToolUI = makeAssistantToolUI<
  { item: string; from_location: string; to_location: string },
  unknown
>({
  toolName: "deliver_item",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Errand: Deliver ${args.item}`}
        subtitle={`From ${args.from_location.replace(/_/g, " ")} → ${args.to_location.replace(/_/g, " ")}`}
        icon={Package}
        iconColorClass="text-teal-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const FetchItemToolUI = makeAssistantToolUI<
  { item: string; from_location: string },
  unknown
>({
  toolName: "fetch_item",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title={`Errand: Fetch ${args.item}`}
        subtitle={`From ${args.from_location.replace(/_/g, " ")} → Foyer Dock`}
        icon={Package}
        iconColorClass="text-teal-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const PatrolHomeToolUI = makeAssistantToolUI<
  { rooms?: string[] },
  unknown
>({
  toolName: "patrol_home",
  render: ({ args, result, status }) => {
    const data = parseToolResult<any>(result);
    const roomsList = data?.rooms || args.rooms || ["living_room", "kitchen", "master_bedroom"];
    return (
      <ToolCardShell
        title="Multi-Room Security Patrol"
        subtitle={`Scanning ${roomsList.join(" → ")}`}
        icon={ShieldCheck}
        iconColorClass="text-emerald-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const StopTiagoToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "stop_tiago",
  render: ({ result, status }) => {
    const data = parseToolResult<any>(result);
    return (
      <ToolCardShell
        title="TIAGo Emergency Stop"
        subtitle="Halted differential drive motors and cleared waypoints"
        icon={OctagonX}
        iconColorClass="text-red-500"
        status={status}
        isError={!!data?.error}
      />
    );
  },
});

export const GetHumansToolUI = makeAssistantToolUI<
  Record<string, never>,
  unknown
>({
  toolName: "get_humans",
  render: ({ result, status }) => {
    const data = parseToolResult<any[]>(result);
    return (
      <ToolCardShell
        title="Home Occupants & Visitors"
        subtitle={
          Array.isArray(data)
            ? data.map((h) => `${h.name}: ${h.current_room} (${h.status})`).join(" • ")
            : "Locating human occupants..."
        }
        icon={Users}
        iconColorClass="text-indigo-500"
        status={status}
      />
    );
  },
});

export const ProposeAiTaskToolUI = makeAssistantToolUI<
  { title: string; description: string; mode?: string },
  unknown
>({
  toolName: "propose_ai_task",
  render: ({ args, status }) => {
    return (
      <ToolCardShell
        title={`AI Task (${(args.mode || "hitl").toUpperCase()}): ${args.title}`}
        subtitle={args.description}
        icon={Sparkles}
        iconColorClass="text-amber-500"
        status={status}
      />
    );
  },
});
