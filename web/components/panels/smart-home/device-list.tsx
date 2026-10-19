"use client";

import { useState, useRef } from "react";
import {
  Camera,
  Lightbulb,
  Lock,
  Unlock,
  Blinds,
  Thermometer,
  PlugZap,
  Radar,
  Sun,
  Bot,
  Navigation,
  OctagonX,
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useCategoryDevices } from "@/hooks/use-smart-home";
import {
  smartHomeApi,
  type SmartCategory,
  type CameraDevice,
  type LightDevice,
  type DoorDevice,
  type BlindDevice,
  type ClimateDevice,
  type ApplianceDevice,
} from "@/lib/smart-home-api";
import { CameraModal } from "./controls/camera-modal";
import { LightDrawer } from "./controls/light-drawer";
import { DoorLockDrawer } from "./controls/door-lock-drawer";
import { BlindDrawer } from "./controls/blind-drawer";
import { ClimateDrawer } from "./controls/climate-drawer";
import { ApplianceDrawer } from "./controls/appliance-drawer";

export function DeviceList({ category }: { category: SmartCategory }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const {
    lights,
    setLights,
    cameras,
    doors,
    setDoors,
    blinds,
    setBlinds,
    climate,
    setClimate,
    appliances,
    setAppliances,
    sensors,
    rover,
    setRover,
    isLoading,
    refresh,
  } = useCategoryDevices(category);

  const [selectedCamera, setSelectedCamera] = useState<CameraDevice | null>(
    null,
  );
  const [selectedLightId, setSelectedLightId] = useState<number | null>(null);
  const [selectedDoorId, setSelectedDoorId] = useState<string | null>(null);
  const [selectedBlindId, setSelectedBlindId] = useState<string | null>(null);
  const [selectedZoneId, setSelectedZoneId] = useState<number | null>(null);
  const [selectedApplianceId, setSelectedApplianceId] = useState<string | null>(
    null,
  );

  const selectedLight = lights.find((l) => l.id === selectedLightId) || null;
  const selectedDoor = doors.find((d) => d.id === selectedDoorId) || null;
  const selectedBlind = blinds.find((b) => b.id === selectedBlindId) || null;
  const selectedZone = climate.find((c) => c.id === selectedZoneId) || null;
  const selectedAppliance =
    appliances.find((a) => a.id === selectedApplianceId) || null;

  // --- Handlers with Optimistic Updates ---

  const handleToggleLight = async (id: number) => {
    setLights((prev) =>
      prev.map((l) =>
        l.id === id ? { ...l, state: l.state === "On" ? "Off" : "On" } : l,
      ),
    );
    try {
      await smartHomeApi.toggleLight(id);
    } catch {
      refresh();
    }
  };

  const handleUpdateLight = async (
    id: number,
    updates: { power_state?: string; brightness?: number; color?: string },
  ) => {
    setLights((prev) =>
      prev.map((l) =>
        l.id === id
          ? {
              ...l,
              ...updates,
              state: updates.power_state === "off" ? "Off" : "On",
            }
          : l,
      ),
    );
    try {
      await smartHomeApi.updateLight(id, updates);
    } catch {
      refresh();
    }
  };

  const handleUpdateDoor = async (
    id: string,
    payload: {
      open_state?: "open" | "closed";
      locked?: boolean;
      position?: number;
    },
  ) => {
    try {
      const updated = await smartHomeApi.updateDoor(id, payload);
      setDoors((prev) => prev.map((d) => (d.id === id ? updated : d)));
    } catch {
      refresh();
    }
  };

  const handleUpdateBlind = async (id: string, position: number) => {
    setBlinds((prev) =>
      prev.map((b) =>
        b.id === id
          ? {
              ...b,
              position,
              state: position > 0 ? "Open" : "Closed",
              metadata: `${b.room} • ${position}% Open`,
            }
          : b,
      ),
    );
    try {
      await smartHomeApi.updateBlind(id, position);
    } catch {
      refresh();
    }
  };

  const handleUpdateClimate = async (
    id: number,
    payload: {
      power_state?: "on" | "off";
      target_temp?: number;
      mode?: "heat" | "cool" | "eco" | "off";
    },
  ) => {
    try {
      const updated = await smartHomeApi.updateClimate(id, payload);
      setClimate((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch {
      refresh();
    }
  };

  const handleUpdateAppliance = async (
    id: string,
    payload: { power_state?: "on" | "off"; mode?: string },
  ) => {
    try {
      const updated = await smartHomeApi.updateAppliance(id, payload);
      setAppliances((prev) => prev.map((a) => (a.id === id ? updated : a)));
    } catch {
      refresh();
    }
  };

  return (
    <div
      ref={containerRef}
      className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden [transform:translateZ(0)]"
    >
      <div className="flex flex-1 min-h-0 flex-col gap-5 overflow-y-auto pr-1 pb-4">
        <p className="text-sm text-muted-foreground">
          Tap any device to open detailed controls, or use the quick switches.
        </p>

        {isLoading ? (
          <p className="animate-pulse text-sm text-muted-foreground">
            Scanning Webots smart home bus...
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {/* 1. CAMERAS */}
            {category === "Cameras" &&
              cameras.map((cam) => (
                <div
                  key={cam.id}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-border/50 bg-muted/20 p-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-500">
                      <Camera className="size-5" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-foreground">
                        {cam.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {cam.state} • {cam.metadata}
                      </span>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 rounded-xl text-xs font-semibold"
                    onClick={() => setSelectedCamera(cam)}
                  >
                    Live View
                  </Button>
                </div>
              ))}

            {/* 2. LIGHTS */}
            {category === "Lights" &&
              lights.map((light) => {
                const isOn = light.state === "On";
                return (
                  <div
                    key={light.id}
                    onClick={() => setSelectedLightId(light.id)}
                    className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-border/50 bg-muted/20 p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          "flex size-10 items-center justify-center rounded-xl border transition-colors",
                          isOn
                            ? "border-amber-400/30 bg-amber-400/15 text-amber-400"
                            : "border-border bg-muted/30 text-muted-foreground",
                        )}
                      >
                        <Lightbulb className="size-5" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">
                          {light.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {light.state} • {light.brightness}%
                        </span>
                      </div>
                    </div>
                    <div onClick={(e) => e.stopPropagation()}>
                      <Switch
                        checked={isOn}
                        onCheckedChange={() => handleToggleLight(light.id)}
                      />
                    </div>
                  </div>
                );
              })}

            {/* 3. LOCKS, DOORS & EXTERIOR GATES */}
            {category === "Locks & Doors" &&
              doors.map((door) => {
                const isOpen = door.state === "Open";
                return (
                  <div
                    key={door.id}
                    onClick={() => setSelectedDoorId(door.id)}
                    className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-border/50 bg-muted/20 p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          "flex size-10 items-center justify-center rounded-xl border",
                          door.locked
                            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-500"
                            : "border-amber-500/30 bg-amber-500/10 text-amber-500",
                        )}
                      >
                        {door.locked ? (
                          <Lock className="size-5" />
                        ) : (
                          <Unlock className="size-5" />
                        )}
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">
                          {door.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {door.metadata}
                        </span>
                      </div>
                    </div>
                    <div onClick={(e) => e.stopPropagation()}>
                      <Button
                        variant={isOpen ? "default" : "outline"}
                        size="sm"
                        className="h-8 rounded-xl text-xs"
                        onClick={() =>
                          handleUpdateDoor(door.id, {
                            open_state: isOpen ? "closed" : "open",
                          })
                        }
                      >
                        {isOpen ? "Close" : "Open"}
                      </Button>
                    </div>
                  </div>
                );
              })}

            {/* 4. MOTORIZED BLINDS */}
            {category === "Blinds" &&
              blinds.map((blind) => {
                const isOpen = blind.position > 0;
                return (
                  <div
                    key={blind.id}
                    onClick={() => setSelectedBlindId(blind.id)}
                    className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-border/50 bg-muted/20 p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex size-10 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-500">
                        <Blinds className="size-5" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">
                          {blind.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {blind.metadata}
                        </span>
                      </div>
                    </div>
                    <div onClick={(e) => e.stopPropagation()}>
                      <Switch
                        checked={isOpen}
                        onCheckedChange={(checked) =>
                          handleUpdateBlind(blind.id, checked ? 100 : 0)
                        }
                      />
                    </div>
                  </div>
                );
              })}

            {/* 5. THERMOSTATS / CLIMATE ZONES */}
            {category === "Thermostats" &&
              climate.map((zone) => (
                <div
                  key={zone.id}
                  onClick={() => setSelectedZoneId(zone.id)}
                  className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-border/50 bg-muted/20 p-3 transition-colors hover:bg-muted/50"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-xl bg-orange-500/10 text-orange-500">
                      <Thermometer className="size-5" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-foreground">
                        {zone.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {zone.metadata}
                      </span>
                    </div>
                  </div>
                  <span className="text-sm font-bold text-orange-500">
                    {zone.target_temp.toFixed(1)}°C
                  </span>
                </div>
              ))}

            {/* 6. SMART APPLIANCES & WALL PLUGS */}
            {category === "Appliances" &&
              appliances.map((app) => {
                const isOn = app.state === "On";
                return (
                  <div
                    key={app.id}
                    onClick={() => setSelectedApplianceId(app.id)}
                    className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-border/50 bg-muted/20 p-3 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          "flex size-10 items-center justify-center rounded-xl",
                          isOn
                            ? "bg-purple-500/15 text-purple-500"
                            : "bg-muted/40 text-muted-foreground",
                        )}
                      >
                        <PlugZap className="size-5" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">
                          {app.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {app.mode} • {app.power_watts} W
                        </span>
                      </div>
                    </div>
                    <div onClick={(e) => e.stopPropagation()}>
                      <Switch
                        checked={isOn}
                        onCheckedChange={(checked) =>
                          handleUpdateAppliance(app.id, {
                            power_state: checked ? "on" : "off",
                          })
                        }
                      />
                    </div>
                  </div>
                );
              })}

            {/* 7. MOTION & DAYLIGHT SENSORS */}
            {category === "Sensors" &&
              sensors.map((sensor) => {
                const isMotion = sensor.type === "MotionSensor";
                const Icon = isMotion ? Radar : Sun;
                return (
                  <div
                    key={sensor.id}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-border/50 bg-muted/20 p-3"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          "flex size-10 items-center justify-center rounded-xl",
                          sensor.triggered
                            ? "bg-red-500/15 text-red-500"
                            : "bg-cyan-500/10 text-cyan-500",
                        )}
                      >
                        <Icon className="size-5" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">
                          {sensor.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          Raw reading: {sensor.value}
                        </span>
                      </div>
                    </div>
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-1 text-xs font-semibold",
                        sensor.triggered
                          ? "bg-red-500/15 text-red-500"
                          : "bg-emerald-500/15 text-emerald-500",
                      )}
                    >
                      {sensor.state}
                    </span>
                  </div>
                );
              })}

            {/* 8. AUTONOMOUS ROVER (KUKA YOUBOT) */}
            {category === "Rover" && rover && (
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between gap-3 rounded-2xl border border-border/50 bg-muted/20 p-3">
                  <div className="flex items-center gap-3">
                    <div className="flex size-10 items-center justify-center rounded-xl bg-teal-500/15 text-teal-500">
                      <Bot className="size-5" />
                    </div>
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-foreground">
                        {rover.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {rover.status} • {rover.current_room} ({rover.battery_pct}% Battery)
                      </span>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5 rounded-xl text-xs text-red-500"
                    onClick={async () => {
                      const updated = await smartHomeApi.controlRover({ action: "stop" });
                      setRover(updated);
                    }}
                  >
                    <OctagonX className="size-3.5" />
                    Stop
                  </Button>
                </div>

                <div className="flex flex-col gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Quick Room Dispatch
                  </span>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { id: "foyer", label: "Foyer Dock" },
                      { id: "living_room", label: "Living Room" },
                      { id: "kitchen", label: "Kitchen" },
                      { id: "dining_room", label: "Dining Room" },
                      { id: "master_bedroom", label: "Master Bedroom" },
                      { id: "patrol", label: "Estate Patrol" },
                    ].map((dest) => (
                      <Button
                        key={dest.id}
                        variant="outline"
                        size="sm"
                        className="justify-start gap-2 rounded-xl text-xs"
                        onClick={async () => {
                          const updated = await smartHomeApi.navigateRover(dest.id);
                          if (updated && "status" in updated && updated.id) {
                            setRover(updated);
                          } else {
                            refresh();
                          }
                        }}
                      >
                        <Navigation className="size-3.5 text-teal-500" />
                        {dest.label}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Interactive Modals & Drawers */}
      <CameraModal
        camera={selectedCamera}
        onClose={() => setSelectedCamera(null)}
      />

      <LightDrawer
        light={selectedLight}
        container={containerRef.current}
        onClose={() => setSelectedLightId(null)}
        onUpdate={handleUpdateLight}
      />

      <DoorLockDrawer
        door={selectedDoor}
        container={containerRef.current}
        onClose={() => setSelectedDoorId(null)}
        onUpdate={handleUpdateDoor}
      />

      <BlindDrawer
        blind={selectedBlind}
        container={containerRef.current}
        onClose={() => setSelectedBlindId(null)}
        onUpdate={handleUpdateBlind}
      />

      <ClimateDrawer
        zone={selectedZone}
        container={containerRef.current}
        onClose={() => setSelectedZoneId(null)}
        onUpdate={handleUpdateClimate}
      />

      <ApplianceDrawer
        appliance={selectedAppliance}
        container={containerRef.current}
        onClose={() => setSelectedApplianceId(null)}
        onUpdate={handleUpdateAppliance}
      />
    </div>
  );
}
