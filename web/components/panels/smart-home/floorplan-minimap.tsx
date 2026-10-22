"use client";

import { useState } from "react";
import {
  Bot,
  Lightbulb,
  Lock,
  Unlock,
  Navigation,
  Plus,
  Radio,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  FLOORPLAN_VIEWBOX_HEIGHT,
  FLOORPLAN_VIEWBOX_WIDTH,
  buildManhattanPolyline,
  polygonCentroidSvg,
  polygonToSvgPoints,
  worldToSvg,
} from "@/lib/floorplan-geometry";
import { smartHomeApi, type V2DeviceRecord } from "@/lib/smart-home-api";
import { useBeaconSocket } from "@/lib/use-beacon-socket";

interface FloorplanMinimapProps {
  onOpenProvisionModal?: () => void;
}

export function FloorplanMinimap({ onOpenProvisionModal }: FloorplanMinimapProps) {
  const { rooms, devices, navNodes, navEdges, robot, connected, simMode } =
    useBeaconSocket();
  const [hoveredItem, setHoveredItem] = useState<string | null>(null);
  const [dispatchingRoom, setDispatchingRoom] = useState<string | null>(null);

  const lights = devices.filter((d) => d.domain === "light");
  const doors = devices.filter((d) => d.domain === "door");
  const sensors = devices.filter((d) => d.domain === "sensor");

  const nodeMap = new Map(navNodes.map((n) => [n.id, n]));
  const activeRoute: Array<{ x: number; y: number }> =
    ((robot as any)?.active_route as Array<{ x: number; y: number }>) || [];

  const handleToggleLight = async (dev: V2DeviceRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await smartHomeApi.toggleLight(dev.id);
    } catch {
      // Handled by socket state
    }
  };

  const handleToggleDoor = async (dev: V2DeviceRecord, e: React.MouseEvent) => {
    e.stopPropagation();
    const isOpen =
      dev.reported_state?.state === "Open" ||
      Number(dev.reported_state?.position || 0) > 0;
    try {
      await smartHomeApi.updateDoor(dev.id, {
        open_state: isOpen ? "closed" : "open",
        locked: false,
        position: isOpen ? 0 : 100,
      });
    } catch {
      // Handled by socket state
    }
  };

  const handleDispatchToRoom = async (roomId: string) => {
    // Map room polygon ID to navigable node ID if available
    const matchingNode =
      navNodes.find((n) => n.id === roomId) ||
      navNodes.find((n) => n.room_id === roomId);
    if (!matchingNode) return;

    setDispatchingRoom(matchingNode.name);
    try {
      await smartHomeApi.navigateRobot(matchingNode.id);
    } finally {
      setTimeout(() => setDispatchingRoom(null), 1500);
    }
  };

  const robotPose = robot?.pose || { x: -3.1, y: -7.62, theta: 1.5708 };
  const robotSvg = worldToSvg(robotPose.x, robotPose.y);
  // In Webots +X is East (right) and +Y is North (screen up), so SVG angle in degrees is -(theta * 180 / pi)
  const robotHeadingDeg = (-robotPose.theta * 180) / Math.PI;

  return (
    <div className="flex flex-col gap-3">
      {/* Status Bar */}
      <div className="flex items-center justify-between gap-2 rounded-2xl border border-border/60 bg-muted/30 px-3 py-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "size-2 rounded-full",
              connected ? "bg-emerald-500 animate-pulse" : "bg-amber-500",
            )}
          />
          <span className="text-[11px] font-semibold uppercase tracking-wider text-foreground">
            {simMode === "WEBOTS_ATTACHED" ? "Webots 3D Attached" : "Virtual Physics Twin"}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {onOpenProvisionModal && (
            <Button
              variant="outline"
              size="sm"
              className="h-7 gap-1 rounded-full px-2.5 text-[11px]"
              onClick={onOpenProvisionModal}
            >
              <Plus className="size-3" />
              Provision Device
            </Button>
          )}
        </div>
      </div>

      {/* Interactive 2D Floorplan SVG Canvas */}
      <div className="relative overflow-hidden rounded-3xl border border-border/70 bg-slate-950 p-2 shadow-inner">
        <svg
          viewBox={`0 0 ${FLOORPLAN_VIEWBOX_WIDTH} ${FLOORPLAN_VIEWBOX_HEIGHT}`}
          className="h-auto w-full select-none"
        >
          <defs>
            <pattern
              id="floorplan-grid"
              width="50"
              height="50"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 50 0 L 0 0 0 50"
                fill="none"
                stroke="rgba(148, 163, 184, 0.08)"
                strokeWidth="1"
              />
            </pattern>

            {/* Dynamic radial glow gradients for each smart light */}
            {lights.map((l) => {
              const st = l.reported_state || {};
              const isOn = st.state === "On" || st.power_state === "on";
              const colorHex = st.color || "#fbbf24";
              const brightness = isOn ? Number(st.brightness ?? 100) / 100 : 0;
              return (
                <radialGradient key={`grad-${l.id}`} id={`light-glow-${l.id}`}>
                  <stop
                    offset="0%"
                    stopColor={colorHex}
                    stopOpacity={Math.min(0.75, brightness * 0.7)}
                  />
                  <stop
                    offset="60%"
                    stopColor={colorHex}
                    stopOpacity={Math.min(0.28, brightness * 0.25)}
                  />
                  <stop offset="100%" stopColor={colorHex} stopOpacity={0} />
                </radialGradient>
              );
            })}
          </defs>

          {/* Subtle 1m x 1m metric grid */}
          <rect
            x="0"
            y="0"
            width={FLOORPLAN_VIEWBOX_WIDTH}
            height={FLOORPLAN_VIEWBOX_HEIGHT}
            fill="url(#floorplan-grid)"
          />

          {/* 1. Vector Architectural Layer (Room Polygons) */}
          {rooms.map((room) => {
            const pts = polygonToSvgPoints(room.polygon_2d);
            const center = polygonCentroidSvg(room.polygon_2d);
            const isNavigable = navNodes.some(
              (n) => n.id === room.id || n.room_id === room.id,
            );
            return (
              <g
                key={room.id}
                onClick={() => isNavigable && handleDispatchToRoom(room.id)}
                onMouseEnter={() => setHoveredItem(`Room: ${room.name} (Click to dispatch TIAGo)`)}
                onMouseLeave={() => setHoveredItem(null)}
                className={cn(isNavigable && "cursor-pointer")}
              >
                <polygon
                  points={pts}
                  fill="rgba(30, 41, 59, 0.72)"
                  stroke="rgba(148, 163, 184, 0.35)"
                  strokeWidth="2.5"
                  className="transition-colors hover:fill-slate-800/90"
                />
                <text
                  x={center.x}
                  y={center.y}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="rgba(148, 163, 184, 0.65)"
                  fontSize="13"
                  fontWeight="700"
                  letterSpacing="0.08em"
                  className="pointer-events-none uppercase"
                >
                  {room.name}
                </text>
              </g>
            );
          })}

          {/* 2. Orthogonal Manhattan Navigation Graph Spine */}
          {navEdges.map((edge) => {
            const u = nodeMap.get(edge.from_node);
            const v = nodeMap.get(edge.to_node);
            if (!u || !v) return null;
            const p1 = worldToSvg(u.x, u.y);
            const p2 = worldToSvg(v.x, v.y);
            return (
              <line
                key={edge.id}
                x1={p1.x}
                y1={p1.y}
                x2={p2.x}
                y2={p2.y}
                stroke="rgba(45, 212, 191, 0.22)"
                strokeWidth="2"
                strokeDasharray="5 5"
              />
            );
          })}

          {/* Active TIAGo Route Polyline */}
          {activeRoute.length > 0 && (
            <polyline
              points={buildManhattanPolyline(activeRoute, {
                x: robotPose.x,
                y: robotPose.y,
              })}
              fill="none"
              stroke="#14b8a6"
              strokeWidth="4.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* 3. Live Light Glow Gradients & Interactive Light Nodes */}
          {lights.map((light) => {
            const [wx, wy] = light.translation;
            const pt = worldToSvg(wx, wy);
            const st = light.reported_state || {};
            const isOn = st.state === "On" || st.power_state === "on";
            const colorHex = st.color || "#fbbf24";
            return (
              <g
                key={light.id}
                onClick={(e) => handleToggleLight(light, e)}
                onMouseEnter={() =>
                  setHoveredItem(
                    `${light.wbt_name} (${isOn ? `${st.brightness ?? 100}%` : "Off"}) — Click to toggle`,
                  )
                }
                onMouseLeave={() => setHoveredItem(null)}
                className="cursor-pointer"
              >
                {isOn && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={68}
                    fill={`url(#light-glow-${light.id})`}
                    className="pointer-events-none"
                  />
                )}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={8}
                  fill={isOn ? colorHex : "#334155"}
                  stroke="#0f172a"
                  strokeWidth="2"
                />
              </g>
            );
          })}

          {/* 4. Live Doors & Exterior Gates */}
          {doors.map((door) => {
            const [wx, wy] = door.translation;
            const pt = worldToSvg(wx, wy);
            const st = door.reported_state || {};
            const pos = Number(st.position ?? 0);
            const locked = Boolean(st.locked);
            const isOpen = pos > 0;
            const strokeColor = locked ? "#10b981" : "#f59e0b";
            // Slide/open offset based on position (0-100%)
            const openOffset = (pos / 100) * 18;

            return (
              <g
                key={door.id}
                onClick={(e) => handleToggleDoor(door, e)}
                onMouseEnter={() =>
                  setHoveredItem(
                    `${door.wbt_name}: ${locked ? "Locked" : "Unlocked"} • ${st.state || "Closed"} (${pos}%) — Click to actuate`,
                  )
                }
                onMouseLeave={() => setHoveredItem(null)}
                className="cursor-pointer"
              >
                <rect
                  x={pt.x - 16 + openOffset}
                  y={pt.y - 5}
                  width={32 - openOffset * 0.6}
                  height={10}
                  rx={4}
                  fill={isOpen ? "rgba(16, 185, 129, 0.25)" : strokeColor}
                  stroke={strokeColor}
                  strokeWidth="2"
                />
              </g>
            );
          })}

          {/* 5. Motion & Daylight Sensors (Pulsing Radar Rings) */}
          {sensors.map((sensor) => {
            const [wx, wy] = sensor.translation;
            const pt = worldToSvg(wx, wy);
            const triggered = Boolean(sensor.reported_state?.triggered);
            return (
              <g
                key={sensor.id}
                onMouseEnter={() =>
                  setHoveredItem(
                    `${sensor.wbt_name}: ${sensor.reported_state?.state} (${sensor.reported_state?.value})`,
                  )
                }
                onMouseLeave={() => setHoveredItem(null)}
              >
                {triggered && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={32}
                    fill="rgba(239, 68, 68, 0.18)"
                    stroke="#ef4444"
                    strokeWidth="1.5"
                    strokeDasharray="4 2"
                  />
                )}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={5.5}
                  fill={triggered ? "#ef4444" : "#06b6d4"}
                  stroke="#0f172a"
                  strokeWidth="1.5"
                />
              </g>
            );
          })}

          {/* 6. Live TIAGo Robot Marker & Heading Cone */}
          <g
            transform={`translate(${robotSvg.x}, ${robotSvg.y})`}
            onMouseEnter={() =>
              setHoveredItem(
                `TIAGo Bot: ${robot?.status || "Docked"} @ ${robot?.current_room || "Foyer"} (${robotPose.x}m, ${robotPose.y}m)`,
              )
            }
            onMouseLeave={() => setHoveredItem(null)}
          >
            {/* Directional Heading Cone */}
            <g transform={`rotate(${robotHeadingDeg})`}>
              <polygon
                points="0,0 34,-15 34,15"
                fill="rgba(20, 184, 166, 0.28)"
                stroke="rgba(20, 184, 166, 0.6)"
                strokeWidth="1"
              />
            </g>
            <circle
              cx="0"
              cy="0"
              r="12"
              fill="#14b8a6"
              stroke="#0f172a"
              strokeWidth="3"
            />
            <circle cx="0" cy="0" r="4" fill="#ffffff" />
          </g>
        </svg>

        {/* Bottom HUD Legend / Hover Tooltip */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 px-2 pt-2 text-[11px] text-slate-300">
          {hoveredItem ? (
            <span className="font-medium text-teal-300">{hoveredItem}</span>
          ) : dispatchingRoom ? (
            <span className="flex items-center gap-1.5 font-medium text-teal-400">
              <Navigation className="size-3.5 animate-bounce" />
              Dispatching TIAGo to {dispatchingRoom}...
            </span>
          ) : (
            <span className="text-slate-400">
              Click any light/door to toggle • Click any room to dispatch TIAGo
            </span>
          )}
          <div className="flex items-center gap-3 text-[10px] text-slate-400">
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-amber-400" /> Light
            </span>
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-emerald-500" /> Locked Door
            </span>
            <span className="flex items-center gap-1">
              <span className="size-2 rounded-full bg-teal-400" /> TIAGo
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
