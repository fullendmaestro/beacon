"use client";

import { Lock, Unlock, DoorOpen, DoorClosed } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { CircularSlider } from "@/components/ui/circular-slider";
import { cn } from "@/lib/utils";
import type { DoorDevice } from "@/lib/smart-home-api";

interface DoorLockDrawerProps {
  door: DoorDevice | null;
  container: HTMLElement | null;
  onClose: () => void;
  onUpdate: (
    id: string,
    payload: {
      open_state?: "open" | "closed";
      locked?: boolean;
      position?: number;
    },
  ) => void;
}

export function DoorLockDrawer({
  door,
  container,
  onClose,
  onUpdate,
}: DoorLockDrawerProps) {
  return (
    <Drawer open={!!door} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent
        className="h-full max-h-full rounded-none border-none data-[swipe-direction=down]:rounded-none"
        container={container}
      >
        <div className="flex-1 overflow-y-auto px-4 pb-8">
          <DrawerHeader className="px-0 pt-4 text-left">
            <DrawerTitle className="text-xl font-bold">
              {door?.name}
            </DrawerTitle>
            <p className="text-sm text-muted-foreground">{door?.metadata}</p>
          </DrawerHeader>

          {door && (
            <div className="flex flex-col items-center gap-8 py-6">
              <CircularSlider
                className="w-full max-w-[250px]"
                value={door.position}
                onChange={(val) => onUpdate(door.id, { position: val })}
              >
                <div className="mt-2 flex flex-col items-center justify-center">
                  <Button
                    variant="outline"
                    size="icon"
                    className={cn(
                      "pointer-events-auto size-20 rounded-full border-[3px] shadow-sm transition-all duration-300",
                      door.locked
                        ? "border-emerald-500 bg-emerald-500/10 text-emerald-500"
                        : "border-amber-500 bg-amber-500/10 text-amber-500",
                    )}
                    onClick={() =>
                      onUpdate(door.id, {
                        locked: !door.locked,
                        ...(door.locked ? {} : { open_state: "closed" }),
                      })
                    }
                  >
                    {door.locked ? (
                      <Lock className="size-8" />
                    ) : (
                      <Unlock className="size-8" />
                    )}
                  </Button>
                  <div className="mt-3 text-xl font-bold text-foreground">
                    {door.locked ? "Locked" : `${door.position}% Open`}
                  </div>
                </div>
              </CircularSlider>

              <div className="grid w-full grid-cols-2 gap-3 border-t border-border/50 pt-6">
                <Button
                  variant={door.state === "Open" ? "default" : "outline"}
                  className="h-11 gap-2 rounded-2xl"
                  onClick={() =>
                    onUpdate(door.id, {
                      open_state: "open",
                      locked: false,
                      position: 100,
                    })
                  }
                >
                  <DoorOpen className="size-4" />
                  Open Fully
                </Button>
                <Button
                  variant={door.state === "Closed" ? "default" : "outline"}
                  className="h-11 gap-2 rounded-2xl"
                  onClick={() =>
                    onUpdate(door.id, { open_state: "closed", position: 0 })
                  }
                >
                  <DoorClosed className="size-4" />
                  Close
                </Button>
              </div>
            </div>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
