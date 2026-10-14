"use client";

import { Blinds } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { CircularSlider } from "@/components/ui/circular-slider";
import type { BlindDevice } from "@/lib/smart-home-api";

interface BlindDrawerProps {
  blind: BlindDevice | null;
  container: HTMLElement | null;
  onClose: () => void;
  onUpdate: (id: string, position: number) => void;
}

const PRESETS = [0, 25, 50, 75, 100];

export function BlindDrawer({
  blind,
  container,
  onClose,
  onUpdate,
}: BlindDrawerProps) {
  return (
    <Drawer open={!!blind} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent
        className="h-full max-h-full rounded-none border-none data-[swipe-direction=down]:rounded-none"
        container={container}
      >
        <div className="flex-1 overflow-y-auto px-4 pb-8">
          <DrawerHeader className="px-0 pt-4 text-left">
            <DrawerTitle className="text-xl font-bold">
              {blind?.name}
            </DrawerTitle>
            <p className="text-sm text-muted-foreground">{blind?.metadata}</p>
          </DrawerHeader>

          {blind && (
            <div className="flex flex-col items-center gap-8 py-6">
              <CircularSlider
                className="w-full max-w-[250px]"
                value={blind.position}
                onChange={(val) => onUpdate(blind.id, val)}
              >
                <div className="flex flex-col items-center justify-center">
                  <Blinds className="size-10 text-indigo-500" />
                  <span className="mt-2 text-3xl font-extrabold text-foreground">
                    {blind.position}%
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {blind.position === 0 ? "Closed" : "Raised"}
                  </span>
                </div>
              </CircularSlider>

              <div className="w-full space-y-3 border-t border-border/50 pt-6">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Quick Positions
                </span>
                <div className="grid grid-cols-5 gap-2">
                  {PRESETS.map((pct) => (
                    <Button
                      key={pct}
                      variant={blind.position === pct ? "default" : "outline"}
                      size="sm"
                      className="rounded-xl text-xs"
                      onClick={() => onUpdate(blind.id, pct)}
                    >
                      {pct === 0 ? "Close" : pct === 100 ? "Open" : `${pct}%`}
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
