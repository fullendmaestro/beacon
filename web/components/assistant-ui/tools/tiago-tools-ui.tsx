"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";
import {
  Bot,
  OctagonX,
  Hand,
  Package,
  Eye,
  Camera,
  MapPin,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  PlanTiagoRouteUI,
  NavigateTiagoToRoomUI,
  FetchItemUI,
  DeliverItemUI,
} from "./tiago-route-tool-ui";

export {
  PlanTiagoRouteUI,
  NavigateTiagoToRoomUI,
  FetchItemUI,
  DeliverItemUI,
};

function parseResult<T = Record<string, any>>(result: unknown): T | null {
  if (!result) return null;
  if (typeof result === "string") {
    try {
      return JSON.parse(result) as T;
    } catch {
      return null;
    }
  }
  if (Array.isArray(result)) {
    if (
      result.length > 0 &&
      typeof result[0] === "object" &&
      result[0] !== null &&
      "text" in result[0]
    ) {
      const combined = result.map((block: any) => block.text).join("\n");
      try {
        return JSON.parse(combined) as T;
      } catch {
        return null;
      }
    }
    return result as unknown as T;
  }
  if (typeof result === "object" && "content" in (result as any)) {
    return parseResult<T>((result as any).content);
  }
  if (typeof result === "object") return result as T;
  return null;
}

function ToolCardShell({
  icon: Icon,
  title,
  subtitle,
  badge,
  badgeVariant = "teal",
  isRunning,
  children,
}: {
  icon: React.ElementType;
  title: string;
  subtitle?: string;
  badge?: string;
  badgeVariant?: "teal" | "amber" | "red" | "emerald";
  isRunning?: boolean;
  children?: React.ReactNode;
}) {
  const badgeColors = {
    teal: "bg-teal-500/15 text-teal-500 border-teal-500/30",
    amber: "bg-amber-500/15 text-amber-500 border-amber-500/30",
    red: "bg-red-500/15 text-red-500 border-red-500/30",
    emerald: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
  };

  return (
    <div className="my-2 flex flex-col gap-3 rounded-2xl border border-border/60 bg-card/80 p-3.5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-teal-500/30 bg-teal-500/10 text-teal-500">
            {isRunning ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Icon className="size-4" />
            )}
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-foreground">
              {title}
            </span>
            {subtitle && (
              <span className="text-[11px] text-muted-foreground">
                {subtitle}
              </span>
            )}
          </div>
        </div>
        {badge && (
          <span
            className={cn(
              "rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
              badgeColors[badgeVariant],
            )}
          >
            {badge}
          </span>
        )}
      </div>
      {children}
    </div>
  );
}

// 1. Telemetry
export const GetTiagoTelemetryUI = makeAssistantToolUI<Record<string, never>, any>({
  toolName: "get_tiago_telemetry",
  render: ({ result, status }) => {
    const data = parseResult(result);
    const isRunning = status.type === "running";
    if (isRunning || !data) {
      return (
        <ToolCardShell
          icon={Bot}
          title="TIAGo Telemetry"
          subtitle="Polling robot sensors & pose..."
          isRunning
        />
      );
    }
    return (
      <ToolCardShell
        icon={Bot}
        title="TIAGo Status Snapshot"
        subtitle={`Task: ${data.task || "idle"}`}
        badge={`${data.battery ?? 100}% Battery`}
        badgeVariant="emerald"
      >
        <div className="grid grid-cols-3 gap-2 rounded-xl bg-muted/40 p-2.5 text-xs">
          <div>
            <span className="text-[10px] text-muted-foreground">Pose (X, Y)</span>
            <p className="font-mono font-semibold">
              {data.pose?.x ?? 0}m, {data.pose?.y ?? 0}m
            </p>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground">Arm / Gripper</span>
            <p className="font-semibold capitalize">
              {data.arm_pose || "home"} • {data.gripper || "open"}
            </p>
          </div>
          <div>
            <span className="text-[10px] text-muted-foreground">Held Item</span>
            <p className="font-semibold capitalize">
              {data.held_object || "None"}
            </p>
          </div>
        </div>
      </ToolCardShell>
    );
  },
});

// 4. Navigate to Pose
export const NavigateTiagoToPoseUI = makeAssistantToolUI<
  { x: number; y: number; theta: number },
  any
>({
  toolName: "navigate_tiago_to_pose",
  render: ({ args, status }) => (
    <ToolCardShell
      icon={MapPin}
      title="Navigating TIAGo to Coordinates"
      subtitle={`X: ${args.x}m, Y: ${args.y}m, θ: ${args.theta} rad`}
      badge={status.type === "running" ? "Moving" : "Dispatched"}
      isRunning={status.type === "running"}
    />
  ),
});

// 5. Stop TIAGo
export const StopTiagoUI = makeAssistantToolUI<Record<string, never>, any>({
  toolName: "stop_tiago",
  render: ({ status }) => (
    <ToolCardShell
      icon={OctagonX}
      title="Emergency Stop Triggered"
      subtitle="Halted TIAGo wheels and active trajectory"
      badge="Stopped"
      badgeVariant="red"
      isRunning={status.type === "running"}
    />
  ),
});

// 6. Arm Pose
export const SetTiagoArmPoseUI = makeAssistantToolUI<{ pose_name: string }, any>({
  toolName: "set_tiago_arm_pose",
  render: ({ args, status }) => (
    <ToolCardShell
      icon={Bot}
      title={`Arm Pose → ${args.pose_name?.replace(/_/g, " ")}`}
      subtitle="7-DoF manipulator preset configuration"
      badge={status.type === "running" ? "Moving" : "Set"}
      isRunning={status.type === "running"}
    />
  ),
});

// 7. Gripper
export const SetTiagoGripperUI = makeAssistantToolUI<{ state: string }, any>({
  toolName: "set_tiago_gripper",
  render: ({ args, status }) => (
    <ToolCardShell
      icon={Hand}
      title={`Robotiq 2F-85 Gripper → ${args.state}`}
      subtitle="Parallel finger actuator"
      badge={args.state}
      isRunning={status.type === "running"}
    />
  ),
});

// 8. Pick Object
export const PickObjectUI = makeAssistantToolUI<{ object_name: string }, any>({
  toolName: "pick_object",
  render: ({ args, status }) => (
    <ToolCardShell
      icon={Package}
      title={`Picking up ${args.object_name?.replace(/_/g, " ")}`}
      subtitle="Aligning arm → grasping → lifting to carry pose"
      badge={status.type === "running" ? "Grasping" : "Picked"}
      isRunning={status.type === "running"}
    />
  ),
});

// 9. Place Object
export const PlaceObjectUI = makeAssistantToolUI<{ location: string }, any>({
  toolName: "place_object",
  render: ({ args, status }) => (
    <ToolCardShell
      icon={Package}
      title={`Placing held object at ${args.location?.replace(/_/g, " ")}`}
      subtitle="Lowering arm → releasing gripper → retracting to home"
      badge={status.type === "running" ? "Placing" : "Placed"}
      isRunning={status.type === "running"}
    />
  ),
});

// 10. Head Look At
export const LookAtUI = makeAssistantToolUI<{ target: string }, any>({
  toolName: "look_at",
  render: ({ args, status }) => (
    <ToolCardShell
      icon={Eye}
      title={`Pointing Head Camera → ${args.target}`}
      subtitle="Adjusting pan/tilt servos"
      badge="Oriented"
      isRunning={status.type === "running"}
    />
  ),
});

// 11. Camera Image
export const GetTiagoCameraImageUI = makeAssistantToolUI<Record<string, never>, any>({
  toolName: "get_tiago_camera_image",
  render: ({ result, status }) => {
    const data = parseResult(result);
    return (
      <ToolCardShell
        icon={Camera}
        title="Captured TIAGo POV Snapshot"
        subtitle={
          data?.image_path
            ? `${data.width ?? 640}x${data.height ?? 480} • ${data.image_path}`
            : "Orbbec Astra RGB Head Camera"
        }
        badge="Snapshot"
        isRunning={status.type === "running"}
      />
    );
  },
});

// 14. Errand Status
export const GetErrandStatusUI = makeAssistantToolUI<Record<string, never>, any>({
  toolName: "get_errand_status",
  render: ({ result, status }) => {
    const data = parseResult(result);
    const stepPct =
      data?.total_steps > 0
        ? Math.round((data.current_step / data.total_steps) * 100)
        : 0;
    return (
      <ToolCardShell
        icon={CheckCircle2}
        title={`Errand Progress (${data?.errand_type || "Task"})`}
        subtitle={data?.message || "Checking errand state..."}
        badge={
          data?.total_steps
            ? `Step ${data.current_step}/${data.total_steps}`
            : data?.status || "Idle"
        }
        badgeVariant={data?.status === "done" ? "emerald" : "teal"}
        isRunning={status.type === "running"}
      >
        {data?.total_steps > 0 && (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-teal-500 transition-all duration-300"
              style={{ width: `${stepPct}%` }}
            />
          </div>
        )}
      </ToolCardShell>
    );
  },
});

// 15. Discovery Lists (Rooms & Objects)
export const ListTiagoRoomsUI = makeAssistantToolUI<Record<string, never>, any>({
  toolName: "list_tiago_rooms",
  render: ({ result, status }) => {
    const data = parseResult(result);
    return (
      <ToolCardShell
        icon={MapPin}
        title="TIAGo Navigation Waypoints"
        subtitle={
          data?.rooms ? `${data.rooms.length} known rooms` : "Loading rooms..."
        }
        badge="Catalogue"
        isRunning={status.type === "running"}
      />
    );
  },
});

export const ListTiagoObjectsUI = makeAssistantToolUI<Record<string, never>, any>({
  toolName: "list_tiago_objects",
  render: ({ result, status }) => {
    const data = parseResult(result);
    return (
      <ToolCardShell
        icon={Package}
        title="Graspable Household Objects"
        subtitle={
          data?.objects
            ? data.objects.join(", ")
            : "Loading interactable objects..."
        }
        badge="Catalogue"
        isRunning={status.type === "running"}
      />
    );
  },
});

export function TiagoToolUIs() {
  return (
    <>
      <GetTiagoTelemetryUI />
      <PlanTiagoRouteUI />
      <NavigateTiagoToRoomUI />
      <NavigateTiagoToPoseUI />
      <StopTiagoUI />
      <SetTiagoArmPoseUI />
      <SetTiagoGripperUI />
      <PickObjectUI />
      <PlaceObjectUI />
      <LookAtUI />
      <GetTiagoCameraImageUI />
      <FetchItemUI />
      <DeliverItemUI />
      <GetErrandStatusUI />
      <ListTiagoRoomsUI />
      <ListTiagoObjectsUI />
    </>
  );
}
