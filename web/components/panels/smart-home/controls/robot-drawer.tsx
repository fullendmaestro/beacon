"use client";

import { useState } from "react";
import {
  Bot,
  Camera,
  Navigation,
  OctagonX,
  Battery,
  BatteryCharging,
  BatteryMedium,
  BatteryLow,
  Eye,
  Hand,
  MapPin,
  Check,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { cn } from "@/lib/utils";
import {
  TIAGO_ROOMS,
  TIAGO_ARM_PRESETS,
  TIAGO_HEAD_TARGETS,
} from "../constants";
import { smartHomeApi, type RobotDevice } from "@/lib/smart-home-api";

interface RobotDrawerProps {
  robot: RobotDevice | null;
  container: HTMLElement | null;
  onClose: () => void;
  onNavigate: (room: string) => Promise<void> | void;
  onStop: () => Promise<void> | void;
  onSetArmPose: (pose: string) => Promise<void> | void;
  onSetGripper: (state: "open" | "closed") => Promise<void> | void;
  onSetHead: (target: string) => Promise<void> | void;
}

export function RobotDrawer({
  robot,
  container,
  onClose,
  onNavigate,
  onStop,
  onSetArmPose,
  onSetGripper,
  onSetHead,
}: RobotDrawerProps) {
  const [activeActionMsg, setActiveActionMsg] = useState<string | null>(null);

  const showActionFeedback = (msg: string) => {
    setActiveActionMsg(msg);
    setTimeout(() => setActiveActionMsg(null), 3000);
  };

  const getBatteryIcon = (pct: number) => {
    if (pct >= 80) return <Battery className="size-4 text-emerald-500" />;
    if (pct >= 40) return <BatteryMedium className="size-4 text-amber-500" />;
    return <BatteryLow className="size-4 text-red-500" />;
  };

  const isNavigating =
    robot?.status === "Navigating" ||
    robot?.status?.toLowerCase().includes("navigat");

  return (
    <Drawer open={!!robot} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent
        className="h-full max-h-full rounded-none border-none data-[swipe-direction=down]:rounded-none"
        container={container}
      >
        <div className="flex-1 overflow-y-auto px-4 pb-8">
          <DrawerHeader className="px-0 pt-4 text-left">
            <div className="flex items-center justify-between">
              <DrawerTitle className="flex items-center gap-2 text-xl font-bold">
                <Bot className="size-5 text-teal-500" />
                {robot?.name}
              </DrawerTitle>
              {robot && (
                <span
                  className={cn(
                    "flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
                    robot.online
                      ? "bg-emerald-500/15 text-emerald-500"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "size-1.5 rounded-full",
                      robot.online
                        ? "bg-emerald-500 animate-pulse"
                        : "bg-muted-foreground",
                    )}
                  />
                  {robot.online ? "Online" : "Standby"}
                </span>
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              {robot?.model} • {robot?.type}
            </p>
          </DrawerHeader>

          {robot && (
            <div className="flex flex-col gap-6 py-2">
              {/* Telemetry Hero Card */}
              <div className="flex flex-col gap-3 rounded-2xl border border-border/60 bg-muted/30 p-4">
                <div className="flex items-center justify-between border-b border-border/50 pb-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold",
                        isNavigating
                          ? "bg-amber-500/15 text-amber-500"
                          : robot.status === "Docked"
                            ? "bg-emerald-500/15 text-emerald-500"
                            : "bg-blue-500/15 text-blue-500",
                      )}
                    >
                      <span className="size-1.5 rounded-full bg-current animate-pulse" />
                      {robot.status}
                    </span>
                    {robot.target_destination && (
                      <span className="text-xs text-muted-foreground">
                        → {robot.target_destination}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 rounded-full border border-border/60 bg-background/80 px-2.5 py-1 text-xs font-medium">
                    {getBatteryIcon(robot.battery_pct)}
                    <span>{robot.battery_pct}%</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 pt-1 text-xs">
                  <div className="flex flex-col gap-0.5">
                    <span className="text-muted-foreground">Location</span>
                    <span className="font-semibold text-foreground flex items-center gap-1">
                      <MapPin className="size-3 text-teal-500" />
                      {robot.current_room}
                    </span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-muted-foreground">Coordinates</span>
                    <span className="font-mono text-[11px] text-foreground">
                      X: {robot.pose.x.toFixed(2)}m, Y: {robot.pose.y.toFixed(2)}m
                    </span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-muted-foreground">Arm Pose</span>
                    <span className="font-semibold capitalize text-foreground">
                      {robot.arm_pose || "Home"}
                    </span>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <span className="text-muted-foreground">Held Item</span>
                    <span className="font-semibold text-foreground">
                      {robot.held_object ? (
                        <span className="text-teal-500 capitalize">{robot.held_object}</span>
                      ) : (
                        <span className="text-muted-foreground">None (Empty)</span>
                      )}
                    </span>
                  </div>
                </div>

                {activeActionMsg && (
                  <div className="rounded-xl bg-teal-500/15 px-3 py-1.5 text-center text-xs font-medium text-teal-500 animate-in fade-in duration-200">
                    {activeActionMsg}
                  </div>
                )}
              </div>

              {/* Emergency Stop & Security Patrol Buttons */}
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-10 gap-2 rounded-2xl border-teal-500/40 bg-teal-500/10 text-xs font-semibold text-teal-500 transition-colors hover:bg-teal-500/20"
                  onClick={async () => {
                    showActionFeedback("Starting multi-room security patrol...");
                    await smartHomeApi.patrolRobot();
                  }}
                >
                  <RotateCcw className="size-4" />
                  Security Patrol
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-10 gap-2 rounded-2xl border-red-500/40 bg-red-500/10 text-xs font-semibold text-red-500 transition-colors hover:bg-red-500/20"
                  onClick={async () => {
                    showActionFeedback("Halting robot...");
                    await onStop();
                  }}
                >
                  <OctagonX className="size-4" />
                  Emergency Stop
                </Button>
              </div>

              {/* 1. Autonomous Room Navigation */}
              <div className="flex flex-col gap-2.5 border-t border-border/50 pt-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Autonomous Room Dispatch
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {TIAGO_ROOMS.map((dest) => {
                    const isCurrent = robot.current_room.toLowerCase().includes(dest.id);
                    return (
                      <Button
                        key={dest.id}
                        variant={isCurrent ? "secondary" : "outline"}
                        size="sm"
                        className={cn(
                          "h-10 justify-start gap-2 rounded-xl text-xs transition-colors",
                          isCurrent && "border-teal-500/50 bg-teal-500/10 text-teal-600 dark:text-teal-400 font-semibold",
                        )}
                        onClick={async () => {
                          showActionFeedback(`Navigating to ${dest.label}...`);
                          await onNavigate(dest.id);
                        }}
                      >
                        <Navigation className="size-3.5 text-teal-500" />
                        <span className="truncate">{dest.label}</span>
                      </Button>
                    );
                  })}
                </div>
              </div>

              {/* 2. 7-DoF Robotic Arm Configuration */}
              <div className="flex flex-col gap-2.5 border-t border-border/50 pt-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Arm Pose Presets
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    Current: <strong className="text-foreground capitalize">{robot.arm_pose || "Home"}</strong>
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {TIAGO_ARM_PRESETS.map((p) => {
                    const isActive = (robot.arm_pose || "home").toLowerCase() === p.id.toLowerCase();
                    return (
                      <Button
                        key={p.id}
                        variant={isActive ? "default" : "outline"}
                        size="sm"
                        className={cn(
                          "h-12 flex-col items-start justify-center gap-0.5 rounded-xl px-3 text-left transition-colors",
                          isActive && "bg-teal-600 hover:bg-teal-700 text-white",
                        )}
                        onClick={async () => {
                          showActionFeedback(`Moving arm to ${p.label}...`);
                          await onSetArmPose(p.id);
                        }}
                      >
                        <div className="flex w-full items-center justify-between">
                          <span className="text-xs font-semibold">{p.label}</span>
                          {isActive && <Check className="size-3" />}
                        </div>
                        <span className={cn("text-[10px]", isActive ? "text-white/80" : "text-muted-foreground")}>
                          {p.desc}
                        </span>
                      </Button>
                    );
                  })}
                </div>
              </div>

              {/* 3. Robotiq 2F-85 Gripper Controls */}
              <div className="flex flex-col gap-2.5 border-t border-border/50 pt-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Robotiq 2F-85 Gripper
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    State: <strong className="text-foreground capitalize">{robot.gripper || "Open"}</strong>
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant={robot.gripper === "open" ? "default" : "outline"}
                    className={cn(
                      "h-10 gap-2 rounded-xl text-xs",
                      robot.gripper === "open" && "bg-teal-600 hover:bg-teal-700 text-white",
                    )}
                    onClick={async () => {
                      showActionFeedback("Opening gripper...");
                      await onSetGripper("open");
                    }}
                  >
                    <Hand className="size-4" />
                    Open (Release)
                  </Button>
                  <Button
                    variant={robot.gripper === "closed" ? "default" : "outline"}
                    className={cn(
                      "h-10 gap-2 rounded-xl text-xs",
                      robot.gripper === "closed" && "bg-teal-600 hover:bg-teal-700 text-white",
                    )}
                    onClick={async () => {
                      showActionFeedback("Closing gripper...");
                      await onSetGripper("closed");
                    }}
                  >
                    <Hand className="size-4 rotate-180" />
                    Close (Grasp)
                  </Button>
                </div>

                {/* Quick Supervisor Magnetic Grasp Pick / Place */}
                <div className="mt-1 flex flex-col gap-1.5 rounded-xl border border-border/50 bg-muted/20 p-2.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Supervisor Magnetic Grasp (Quick Pick)
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {["cup", "bottle", "medicine_box", "keys", "remote_control", "book"].map((obj) => (
                      <Button
                        key={obj}
                        variant={robot.held_object === obj ? "default" : "outline"}
                        size="sm"
                        className={cn(
                          "h-7 rounded-lg px-2.5 text-[11px] capitalize",
                          robot.held_object === obj && "bg-teal-600 text-white",
                        )}
                        onClick={async () => {
                          showActionFeedback(`Magnetic grasping ${obj}...`);
                          await smartHomeApi.pickRobotObject(obj);
                        }}
                      >
                        {obj.replace("_", " ")}
                      </Button>
                    ))}
                    {robot.held_object && (
                      <Button
                        variant="secondary"
                        size="sm"
                        className="h-7 rounded-lg px-2.5 text-[11px] font-semibold text-amber-500"
                        onClick={async () => {
                          showActionFeedback(`Placing ${robot.held_object} in ${robot.current_room}...`);
                          await smartHomeApi.placeRobotObject(robot.current_node || "living_room");
                        }}
                      >
                        Place Here
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* 4. Head Camera Orientation */}
              <div className="flex flex-col gap-2.5 border-t border-border/50 pt-4">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Head Camera Pan / Tilt
                </span>
                <div className="grid grid-cols-4 gap-2">
                  {TIAGO_HEAD_TARGETS.map((t) => (
                    <Button
                      key={t.id}
                      variant="outline"
                      size="sm"
                      className="h-9 gap-1 rounded-xl text-xs"
                      onClick={async () => {
                        showActionFeedback(`Pointing head ${t.label}...`);
                        await onSetHead(t.id);
                      }}
                    >
                      <Eye className="size-3 text-muted-foreground" />
                      {t.label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* 5. Live Robot Camera Feed */}
              <div className="flex flex-col gap-2.5 border-t border-border/50 pt-4">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    <Camera className="size-3.5 text-teal-500" />
                    Live Head Camera Feed
                  </span>
                  <span className="text-[11px] text-muted-foreground">Orbbec Astra RGB</span>
                </div>
                <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-border/60 bg-black shadow-inner">
                  <div className="absolute left-3 top-3 z-10 flex items-center gap-1.5 rounded-full bg-black/60 px-2 py-0.5 text-[10px] font-semibold text-white backdrop-blur-sm">
                    <span className="size-1.5 rounded-full bg-red-500 animate-pulse" />
                    TIAGo POV Live
                  </div>
                  <img
                    src={smartHomeApi.getStreamUrl("TIAGo Camera")}
                    alt="TIAGo Live Camera Feed"
                    className="h-full w-full object-cover"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
