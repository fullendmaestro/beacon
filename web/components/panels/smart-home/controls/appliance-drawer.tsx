"use client";

import { Power, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { cn } from "@/lib/utils";
import { APPLIANCE_MODE_OPTIONS } from "../constants";
import type { ApplianceDevice } from "@/lib/smart-home-api";

interface ApplianceDrawerProps {
  appliance: ApplianceDevice | null;
  container: HTMLElement | null;
  onClose: () => void;
  onUpdate: (
    id: string,
    payload: { power_state?: "on" | "off"; mode?: string },
  ) => void;
}

export function ApplianceDrawer({
  appliance,
  container,
  onClose,
  onUpdate,
}: ApplianceDrawerProps) {
  const modes = appliance
    ? APPLIANCE_MODE_OPTIONS[appliance.type] || ["Active", "Eco", "Off"]
    : [];

  return (
    <Drawer open={!!appliance} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent
        className="h-full max-h-full rounded-none border-none data-[swipe-direction=down]:rounded-none"
        container={container}
      >
        <div className="flex-1 overflow-y-auto px-4 pb-8">
          <DrawerHeader className="px-0 pt-4 text-left">
            <DrawerTitle className="text-xl font-bold">
              {appliance?.name}
            </DrawerTitle>
            <p className="text-sm text-muted-foreground">
              {appliance?.room} • {appliance?.mode}
            </p>
          </DrawerHeader>

          {appliance && (
            <div className="flex flex-col items-center gap-6 py-6">
              <Button
                variant="outline"
                size="icon"
                className={cn(
                  "size-24 rounded-full border-[3px] shadow-sm transition-all",
                  appliance.state === "On"
                    ? "border-purple-500 bg-purple-500/10 text-purple-500"
                    : "border-muted bg-muted/30 text-muted-foreground",
                )}
                onClick={() =>
                  onUpdate(appliance.id, {
                    power_state: appliance.state === "On" ? "off" : "on",
                  })
                }
              >
                <Power className="size-10" />
              </Button>

              <div className="flex items-center gap-2 rounded-full border border-border px-4 py-1.5 text-xs font-medium">
                <Zap className="size-3.5 text-amber-500" />
                <span>Real-time Draw: {appliance.power_watts} W</span>
              </div>

              <div className="w-full space-y-3 border-t border-border/50 pt-6">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Operating Program / Mode
                </span>
                <div className="grid grid-cols-2 gap-2">
                  {modes.map((m) => (
                    <Button
                      key={m}
                      variant={appliance.mode === m ? "default" : "outline"}
                      className="h-10 rounded-xl text-xs"
                      onClick={() => onUpdate(appliance.id, { mode: m })}
                    >
                      {m}
                    </Button>
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
