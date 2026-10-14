"use client";

import { Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { CircularSlider } from "@/components/ui/circular-slider";
import { cn } from "@/lib/utils";
import { LIGHT_COLORS } from "../constants";
import type { LightDevice } from "@/lib/smart-home-api";

interface LightDrawerProps {
  light: LightDevice | null;
  container: HTMLElement | null;
  onClose: () => void;
  onUpdate: (
    id: number,
    updates: { power_state?: string; brightness?: number; color?: string },
  ) => void;
}

export function LightDrawer({
  light,
  container,
  onClose,
  onUpdate,
}: LightDrawerProps) {
  return (
    <Drawer open={!!light} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent
        className="h-full max-h-full rounded-none border-none data-[swipe-direction=down]:rounded-none"
        container={container}
      >
        <div className="flex-1 overflow-y-auto px-4 pb-8">
          <DrawerHeader className="px-0 pt-4 text-left">
            <DrawerTitle className="text-xl font-bold">
              {light?.name}
            </DrawerTitle>
            <p className="text-sm text-muted-foreground">
              {light?.state} • Brightness {light?.brightness || 0}%
            </p>
          </DrawerHeader>

          {light && (
            <div className="flex flex-col items-center gap-8 py-6">
              <CircularSlider
                className="w-full max-w-[250px]"
                value={light.brightness || 0}
                onChange={(val) => onUpdate(light.id, { brightness: val })}
                disabled={light.state === "Off"}
              >
                <div className="mt-2 flex flex-col items-center justify-center">
                  <Button
                    variant="outline"
                    size="icon"
                    className={cn(
                      "pointer-events-auto size-20 rounded-full border-[3px] shadow-sm transition-all duration-300",
                      light.state === "On"
                        ? "border-blue-500 bg-blue-50 text-blue-500 hover:bg-blue-100 dark:bg-blue-500/10 dark:hover:bg-blue-500/20"
                        : "border-muted bg-muted/30 text-muted-foreground",
                    )}
                    onClick={() =>
                      onUpdate(light.id, {
                        power_state: light.state === "On" ? "off" : "on",
                      })
                    }
                  >
                    <Power className="size-8" strokeWidth={2.5} />
                  </Button>

                  <div
                    className={cn(
                      "mt-4 text-3xl font-extrabold tracking-tight",
                      light.state === "On"
                        ? "text-blue-500"
                        : "text-muted-foreground",
                    )}
                  >
                    {light.state === "On" ? `${light.brightness}%` : "Off"}
                  </div>
                </div>
              </CircularSlider>

              <div className="w-full space-y-3 border-t border-border/50 pt-6">
                <div className="flex flex-col">
                  <h3 className="text-sm font-medium">Color</h3>
                  <p className="text-xs capitalize text-muted-foreground">
                    {light.color || "Default"}
                  </p>
                </div>

                <div className="grid grid-cols-6 gap-3">
                  {LIGHT_COLORS.map((c) => (
                    <button
                      key={c.name}
                      className={cn(
                        "size-10 rounded-full border-2 shadow-sm transition-all hover:scale-110",
                        light.color === c.hex || light.color === c.name
                          ? "scale-110 border-foreground"
                          : "border-transparent",
                      )}
                      style={{ backgroundColor: c.hex }}
                      onClick={() => onUpdate(light.id, { color: c.name })}
                      title={c.name}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
