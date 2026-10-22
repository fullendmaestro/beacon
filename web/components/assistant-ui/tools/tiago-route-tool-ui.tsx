"use client";

import { useMemo } from "react";
import { makeAssistantToolUI } from "@assistant-ui/react";
import { Lock, Unlock, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  FLOORPLAN_VIEWBOX_HEIGHT,
  FLOORPLAN_VIEWBOX_WIDTH,
  buildManhattanPolyline,
  polygonCentroidSvg,
  polygonToSvgPoints,
  worldToSvg,
} from "@/lib/floorplan-geometry";
import { useBeaconSocket } from "@/lib/use-beacon-socket";
import { parseToolResult } from "./shared-tool-card";

function TiagoIsometricSvg({ isMoving }: { isMoving?: boolean }) {
  return (
    <svg
      viewBox="0 0 120 110"
      className="h-24 w-28 drop-shadow-md"
      aria-label="PAL Robotics TIAGo Isometric"
    >
      {/* Ground shadow */}
      <ellipse
        cx="60"
        cy="96"
        rx="34"
        ry="9"
        fill="rgba(20, 184, 166, 0.18)"
      />
      {/* Differential Mobile Base */}
      <path
        d="M32 82 L60 70 L88 82 L60 94 Z"
        fill="#1e293b"
        stroke="#475569"
        strokeWidth="2"
      />
      <path
        d="M32 82 L32 90 L60 102 L88 90 L88 82"
        fill="#0f172a"
        stroke="#334155"
        strokeWidth="2"
      />
      {/* Wheels */}
      <circle cx="44" cy="91" r="6" fill="#020617" stroke="#14b8a6" strokeWidth="2" />
      <circle cx="76" cy="91" r="6" fill="#020617" stroke="#14b8a6" strokeWidth="2" />
      {/* Prismatic Torso Column */}
      <rect
        x="52"
        y="36"
        width="16"
        height="44"
        rx="4"
        fill="#f8fafc"
        stroke="#94a3b8"
        strokeWidth="2"
      />
      <rect x="55" y="44" width="10" height="24" rx="2" fill="#e2e8f0" />
      {/* 7-DoF Manipulator Arm + Robotiq 2F-85 Gripper */}
      <path
        d="M68 46 L86 52 L92 64"
        fill="none"
        stroke="#cbd5e1"
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="68" cy="46" r="4" fill="#f59e0b" />
      <circle cx="86" cy="52" r="3.5" fill="#f59e0b" />
      <path
        d="M89 64 L95 69 M95 62 L98 67"
        stroke="#0f172a"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* Pan-Tilt Head + Orbbec Astra RGB-D Sensor */}
      <rect
        x="48"
        y="18"
        width="24"
        height="15"
        rx="6"
        fill="#f8fafc"
        stroke="#94a3b8"
        strokeWidth="2"
      />
      <rect x="52" y="22" width="16" height="6" rx="2" fill="#0f172a" />
      <circle
        cx="56"
        cy="25"
        r="2"
        fill={isMoving ? "#14b8a6" : "#38bdf8"}
      />
      <circle
        cx="64"
        cy="25"
        r="2"
        fill={isMoving ? "#14b8a6" : "#38bdf8"}
      />
    </svg>
  );
}

interface RouteCardProps {
  title: string;
  destinationLabel: string;
  data: any;
  isRunning: boolean;
}

function TiagoRouteSplitCard({
  title,
  destinationLabel,
  data,
  isRunning,
}: RouteCardProps) {
  const { rooms, devices, robot } = useBeaconSocket();

  const waypoints: Array<{ x: number; y: number; theta?: number; name?: string }> =
    data?.waypoints || [];
  const originPose: { x: number; y: number } =
    data?.origin_pose ||
    (waypoints.length > 0
      ? { x: waypoints[0].x, y: waypoints[0].y }
      : { x: -3.1, y: -7.62 });
  const destPose: { x: number; y: number } =
    waypoints.length > 0
      ? {
          x: waypoints[waypoints.length - 1].x,
          y: waypoints[waypoints.length - 1].y,
        }
      : data?.target || { x: -2.35, y: -3.95 };

  const liveRobotPose = robot?.pose || originPose;
  const remainingDistM = useMemo(() => {
    if (!waypoints.length) return Number(data?.distance_m ?? 0);
    const dx = destPose.x - liveRobotPose.x;
    const dy = destPose.y - liveRobotPose.y;
    const direct = Math.hypot(dx, dy);
    if (direct < 0.25) return 0;
    return Number(Math.max(direct, Number(data?.distance_m ?? direct)).toFixed(1));
  }, [waypoints.length, data?.distance_m, destPose.x, destPose.y, liveRobotPose.x, liveRobotPose.y]);

  // Match doors on path with live SQLite device states so lock badges turn green when opened
  const doorsOnPath = useMemo(() => {
    const rawDoors: any[] =
      data?.doors_on_path_details || data?.blocking_doors || [];
    return rawDoors.map((d) => {
      const liveDev = devices.find(
        (ld) => ld.id === d.id || ld.wbt_name === (d.wbt_name || d.name),
      );
      const isOpen = liveDev
        ? liveDev.reported_state?.state === "Open" ||
          Number(liveDev.reported_state?.position || 0) >= 80
        : d.state === "Open";
      const isLocked = liveDev
        ? Boolean(liveDev.reported_state?.locked)
        : Boolean(d.locked);
      const trans = liveDev?.translation || d.translation || [-3.89, -3.95, 0];
      return {
        id: d.id || d.name,
        name: d.wbt_name || d.name,
        isOpen,
        isLocked,
        translation: trans,
      };
    });
  }, [data?.doors_on_path_details, data?.blocking_doors, devices]);

  const blockingCount = doorsOnPath.filter((d) => !d.isOpen).length;
  const clearedCount = doorsOnPath.filter((d) => d.isOpen).length;

  // Dynamic ETA formula from specification: ETA = remaining_distance_m / 0.6 + (blocking_doors * 2s)
  const etaSeconds = Math.max(
    0,
    Math.round(remainingDistM / 0.6 + blockingCount * 2),
  );
  const arrivalTimeStr = useMemo(() => {
    const arrival = new Date(Date.now() + etaSeconds * 1000);
    return arrival.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  }, [etaSeconds]);

  const originSvg = worldToSvg(originPose.x, originPose.y);
  const destSvg = worldToSvg(destPose.x, destPose.y);
  const robotSvg = worldToSvg(liveRobotPose.x, liveRobotPose.y);
  const polylinePoints = buildManhattanPolyline(waypoints, originPose);

  const arrived =
    !isRunning &&
    waypoints.length > 0 &&
    Math.hypot(destPose.x - liveRobotPose.x, destPose.y - liveRobotPose.y) < 0.35;

  const liveSubtitle = useMemo(() => {
    if (isRunning) return "Computing orthogonal Manhattan route...";
    if (blockingCount > 0) {
      return `Clearing ${doorsOnPath.find((d) => !d.isOpen)?.name || "Door"}...`;
    }
    if (arrived) {
      return `Arrived at ${destinationLabel}`;
    }
    if (robot?.status === "Navigating") {
      return `Driving Manhattan Spine → ${destinationLabel}`;
    }
    return `${ Number(data?.distance_m ?? remainingDistM).toFixed(1)}m • ${
      clearedCount > 0
        ? `${clearedCount} Door(s) Auto-Cleared`
        : blockingCount > 0
          ? `${blockingCount} Door(s) Blocking`
          : "Path Clear"
    }`;
  }, [
    isRunning,
    blockingCount,
    doorsOnPath,
    arrived,
    destinationLabel,
    robot?.status,
    data?.distance_m,
    remainingDistM,
    clearedCount,
  ]);

  return (
    <div className="my-3 w-full max-w-2xl overflow-hidden rounded-3xl border border-border/70 bg-card/95 p-4 shadow-md backdrop-blur-xs">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-12 sm:items-center">
        {/* Left Pane: 2D Manhattan Route Preview Mini-Map */}
        <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 p-2.5 sm:col-span-7">
          <svg
            viewBox={`0 0 ${FLOORPLAN_VIEWBOX_WIDTH} ${FLOORPLAN_VIEWBOX_HEIGHT}`}
            className="h-48 w-full select-none"
          >
            {/* Room Polygons */}
            {rooms.map((r) => {
              const pts = polygonToSvgPoints(r.polygon_2d);
              const c = polygonCentroidSvg(r.polygon_2d);
              return (
                <g key={r.id}>
                  <polygon
                    points={pts}
                    fill="rgba(30, 41, 59, 0.82)"
                    stroke="rgba(148, 163, 184, 0.32)"
                    strokeWidth="2.5"
                  />
                  <text
                    x={c.x}
                    y={c.y}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill="rgba(148, 163, 184, 0.55)"
                    fontSize="14"
                    fontWeight="700"
                    className="uppercase"
                  >
                    {r.name}
                  </text>
                </g>
              );
            })}

            {/* Corridor Spine Labels */}
            <text
              x={worldToSvg(-3.5, -7.62).x}
              y={worldToSvg(-3.5, -7.62).y + 22}
              textAnchor="middle"
              fill="rgba(45, 212, 191, 0.5)"
              fontSize="11"
              fontWeight="600"
              letterSpacing="0.08em"
            >
              EAST-WEST CORRIDOR
            </text>

            {/* Orthogonal Manhattan Route Polyline */}
            {polylinePoints && (
              <>
                <polyline
                  points={polylinePoints}
                  fill="none"
                  stroke="rgba(20, 184, 166, 0.25)"
                  strokeWidth="12"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <polyline
                  points={polylinePoints}
                  fill="none"
                  stroke="#14b8a6"
                  strokeWidth="5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </>
            )}

            {/* Origin Marker (○) */}
            <circle
              cx={originSvg.x}
              cy={originSvg.y}
              r="9"
              fill="#0f172a"
              stroke="#94a3b8"
              strokeWidth="3.5"
            />

            {/* Destination Marker (▣) */}
            <rect
              x={destSvg.x - 10}
              y={destSvg.y - 10}
              width="20"
              height="20"
              rx="4"
              fill="#14b8a6"
              stroke="#0f172a"
              strokeWidth="3"
            />
            <rect
              x={destSvg.x - 4}
              y={destSvg.y - 4}
              width="8"
              height="8"
              rx="1.5"
              fill="#ffffff"
            />

            {/* Blocking / Cleared Door Badges along the route */}
            {doorsOnPath.map((door) => {
              const dSvg = worldToSvg(door.translation[0], door.translation[1]);
              return (
                <g
                  key={door.id}
                  transform={`translate(${dSvg.x}, ${dSvg.y})`}
                >
                  <rect
                    x="-16"
                    y="-12"
                    width="32"
                    height="24"
                    rx="8"
                    fill={door.isOpen ? "#065f46" : "#78350f"}
                    stroke={door.isOpen ? "#10b981" : "#f59e0b"}
                    strokeWidth="2.5"
                  />
                  <circle
                    cx="0"
                    cy="0"
                    r="5"
                    fill={door.isOpen ? "#34d399" : "#fbbf24"}
                  />
                </g>
              );
            })}

            {/* Live TIAGo Robot Puck */}
            <g transform={`translate(${robotSvg.x}, ${robotSvg.y})`}>
              <circle
                cx="0"
                cy="0"
                r="16"
                fill="rgba(20, 184, 166, 0.25)"
              />
              <circle
                cx="0"
                cy="0"
                r="10"
                fill="#14b8a6"
                stroke="#ffffff"
                strokeWidth="3"
              />
            </g>
          </svg>

          <div className="mt-1.5 flex items-center justify-between px-1 text-[10px] font-medium text-slate-400">
            <span>2D Manhattan Route Preview</span>
            <span className="font-mono text-teal-400">
              {waypoints.length} waypoints • {Number(data?.distance_m ?? remainingDistM).toFixed(1)}m
            </span>
          </div>
        </div>

        {/* Right Pane: Isometric TIAGo Render + Live ETA & Door Status */}
        <div className="flex flex-col items-center justify-between gap-2 text-center sm:col-span-5 sm:items-start sm:text-left">
          <div className="flex w-full items-center justify-center rounded-2xl bg-muted/40 py-2">
            <TiagoIsometricSvg isMoving={robot?.status === "Navigating" || isRunning} />
          </div>

          <div className="flex w-full flex-col gap-1 px-1">
            <div className="flex items-center justify-between gap-2">
              <span className="text-base font-bold tracking-tight text-foreground">
                {title}
              </span>
              {isRunning && (
                <Loader2 className="size-4 animate-spin text-teal-500" />
              )}
            </div>

            <p className="text-xs font-semibold text-teal-500">
              {arrived
                ? `Arrived • 0 sec away`
                : `${arrivalTimeStr} arrival • ${etaSeconds}s away`}
            </p>

            <p className="text-[11px] text-muted-foreground">{liveSubtitle}</p>

            {doorsOnPath.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {doorsOnPath.map((d) => (
                  <span
                    key={d.id}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold",
                      d.isOpen
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
                        : "border-amber-500/30 bg-amber-500/10 text-amber-500",
                    )}
                  >
                    {d.isOpen ? (
                      <Unlock className="size-3" />
                    ) : (
                      <Lock className="size-3" />
                    )}
                    {d.name} ({d.isOpen ? "Cleared" : "Blocking"})
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export const PlanTiagoRouteUI = makeAssistantToolUI<
  { destination: string },
  any
>({
  toolName: "plan_tiago_route",
  render: ({ args, result, status }) => {
    const data = parseToolResult(result);
    const destLabel = (
      data?.destination_name ||
      args.destination ||
      "Destination"
    ).replace(/_/g, " ");
    return (
      <TiagoRouteSplitCard
        title="TIAGo Bot"
        destinationLabel={destLabel}
        data={data}
        isRunning={status.type === "running"}
      />
    );
  },
});

export const NavigateTiagoToRoomUI = makeAssistantToolUI<{ room: string }, any>({
  toolName: "navigate_tiago_to_room",
  render: ({ args, result, status }) => {
    const data = parseToolResult(result);
    const destLabel = (
      data?.destination_name ||
      args.room ||
      "Room"
    ).replace(/_/g, " ");
    return (
      <TiagoRouteSplitCard
        title={`TIAGo → ${destLabel}`}
        destinationLabel={destLabel}
        data={data}
        isRunning={status.type === "running"}
      />
    );
  },
});

export const FetchItemUI = makeAssistantToolUI<
  { item: string; from_location: string },
  any
>({
  toolName: "fetch_item",
  render: ({ args, result, status }) => {
    const data = parseToolResult(result);
    const fromLabel = (args.from_location || "Room").replace(/_/g, " ");
    return (
      <TiagoRouteSplitCard
        title={`Fetch ${args.item || "Item"}`}
        destinationLabel={`${fromLabel} → Foyer`}
        data={data}
        isRunning={status.type === "running"}
      />
    );
  },
});

export const DeliverItemUI = makeAssistantToolUI<
  { item: string; from_location: string; to_location: string },
  any
>({
  toolName: "deliver_item",
  render: ({ args, result, status }) => {
    const data = parseToolResult(result);
    const toLabel = (args.to_location || "Destination").replace(/_/g, " ");
    return (
      <TiagoRouteSplitCard
        title={`${toLabel} Delivery`}
        destinationLabel={toLabel}
        data={data}
        isRunning={status.type === "running"}
      />
    );
  },
});
