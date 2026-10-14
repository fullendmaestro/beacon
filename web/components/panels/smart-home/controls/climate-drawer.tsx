"use client";

import { Flame, Snowflake, Leaf, PowerOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { CircularSlider } from "@/components/ui/circular-slider";
import type { ClimateDevice } from "@/lib/smart-home-api";

interface ClimateDrawerProps {
  zone: ClimateDevice | null;
  container: HTMLElement | null;
  onClose: () => void;
  onUpdate: (
    id: number,
    payload: {
      power_state?: "on" | "off";
      target_temp?: number;
      mode?: "heat" | "cool" | "eco" | "off";
    },
  ) => void;
}

const MODES = [
  { id: "heat", label: "Heat", icon: Flame },
  { id: "cool", label: "Cool", icon: Snowflake },
  { id: "eco", label: "Eco", icon: Leaf },
  { id: "off", label: "Off", icon: PowerOff },
] as const;

export function ClimateDrawer({
  zone,
  container,
  onClose,
  onUpdate,
}: ClimateDrawerProps) {
  // Map 15°C..30°C <-> 0..100 for CircularSlider
  const sliderVal = zone
    ? Math.round(((zone.target_temp - 15) / 15) * 100)
    : 50;

  const handleSliderChange = (pct: number) => {
    if (!zone) return;
    const temp = Math.round((15 + (pct / 100) * 15) * 2) / 2;
    onUpdate(zone.id, { target_temp: temp });
  };

  return (
    <Drawer open={!!zone} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent
        className="h-full max-h-full rounded-none border-none data-[swipe-direction=down]:rounded-none"
        container={container}
      >
        <div className="flex-1 overflow-y-auto px-4 pb-8">
          <DrawerHeader className="px-0 pt-4 text-left">
            <DrawerTitle className="text-xl font-bold">
              {zone?.name}
            </DrawerTitle>
            <p className="text-sm text-muted-foreground">
              Current {zone?.current_temp.toFixed(1)}°C • {zone?.metadata}
            </p>
          </DrawerHeader>

          {zone && (
            <div className="flex flex-col items-center gap-8 py-6">
              <CircularSlider
                className="w-full max-w-[250px]"
                value={sliderVal}
                onChange={handleSliderChange}
                disabled={zone.state === "Off"}
              >
                <div className="flex flex-col items-center justify-center">
                  <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Target
                  </span>
                  <span className="mt-1 text-3xl font-extrabold text-orange-500">
                    {zone.target_temp.toFixed(1)}°C
                  </span>
                  <span className="mt-1 text-xs capitalize text-muted-foreground">
                    Mode: {zone.mode}
                  </span>
                </div>
              </CircularSlider>

              <div className="w-full space-y-3 border-t border-border/50 pt-6">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  HVAC Mode
                </span>
                <div className="grid grid-cols-4 gap-2">
                  {MODES.map((m) => {
                    const Icon = m.icon;
                    return (
                      <Button
                        key={m.id}
                        variant={zone.mode === m.id ? "default" : "outline"}
                        className="flex h-14 flex-col gap-1 rounded-2xl text-xs"
                        onClick={() => onUpdate(zone.id, { mode: m.id })}
                      >
                        <Icon className="size-4" />
                        {m.label}
                      </Button>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
