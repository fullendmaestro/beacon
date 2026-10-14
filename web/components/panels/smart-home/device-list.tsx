"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { Camera, Lightbulb, Power } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Drawer,
  DrawerContent,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { CircularSlider } from "@/components/ui/circular-slider";

interface DeviceItem {
  id: number | string;
  name: string;
  state: string;
  metadata: string;
  type: string;
  brightness?: number;
  color?: string;
}

const COLORS = [
  { name: "white", hex: "#ffffff" },
  { name: "warm white", hex: "#ffebaa" },
  { name: "soft white", hex: "#ffd9a6" },
  { name: "red", hex: "#ff0000" },
  { name: "green", hex: "#00ff00" },
  { name: "blue", hex: "#0033ff" },
  { name: "cyan", hex: "#00ffff" },
  { name: "magenta", hex: "#ff00ff" },
  { name: "yellow", hex: "#ffff00" },
  { name: "orange", hex: "#ff8000" },
  { name: "purple", hex: "#9919e6" },
  { name: "pink", hex: "#ff66b2" },
];

export function DeviceList({ category }: { category: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [items, setItems] = useState<DeviceItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCamera, setSelectedCamera] = useState<DeviceItem | null>(null);
  const [selectedLight, setSelectedLight] = useState<DeviceItem | null>(null);

  const fetchDevices = useCallback(async () => {
    if (category !== "Lights" && category !== "Cameras") {
      setItems([]);
      setIsLoading(false);
      return;
    }

    try {
      const endpoint = category === "Cameras" ? "cameras" : "lights";
      const res = await fetch(`http://127.0.0.1:8000/api/${endpoint}`);
      if (res.ok) {
        const data = await res.json();
        setItems(data);

        setSelectedLight((prev) => {
          if (!prev) return null;
          const updated = data.find((d: DeviceItem) => d.id === prev.id);
          return updated || prev;
        });
      }
    } catch (e) {
      console.error("Failed to fetch devices.", e);
    } finally {
      setIsLoading(false);
    }
  }, [category]);

  useEffect(() => {
    fetchDevices();
    const interval = setInterval(
      fetchDevices,
      category === "Cameras" ? 10000 : 2000,
    );
    return () => clearInterval(interval);
  }, [fetchDevices, category]);

  const toggleDevice = async (id: number | string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (category !== "Lights") return;

    setItems((prev) =>
      prev.map((item) =>
        item.id === id
          ? { ...item, state: item.state === "On" ? "Off" : "On" }
          : item,
      ),
    );

    try {
      await fetch(`http://127.0.0.1:8000/api/lights/${id}/toggle`, {
        method: "POST",
      });
    } catch (e) {
      fetchDevices();
    }
  };

  const updateLightState = async (
    id: number | string,
    updates: { power_state?: string; brightness?: number; color?: string },
  ) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              ...updates,
              state: updates.power_state === "off" ? "Off" : "On",
            }
          : item,
      ),
    );
    setSelectedLight((prev) =>
      prev && prev.id === id
        ? {
            ...prev,
            ...updates,
            state: updates.power_state === "off" ? "Off" : "On",
          }
        : prev,
    );

    try {
      await fetch(`http://127.0.0.1:8000/api/lights/${id}/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates),
      });
    } catch (e) {
      fetchDevices();
    }
  };

  return (
    <div
      ref={containerRef}
      className="relative flex h-full flex-col overflow-hidden [transform:translateZ(0)]"
    >
      <div className="flex flex-col gap-6">
        <p className="text-sm text-muted-foreground">
          View the status and manage settings for your connected{" "}
          {category.toLowerCase()}.
        </p>

        <div className="flex flex-col gap-5">
          {isLoading ? (
            <p className="text-sm text-muted-foreground animate-pulse">
              Scanning network...
            </p>
          ) : items.length > 0 ? (
            items.map((item) => {
              const isCamera = category === "Cameras";
              const isOn = item.state === "On" || item.state === "Online";
              const Icon = isCamera ? Camera : Lightbulb;

              return (
                <div
                  key={item.id}
                  className={cn(
                    "flex items-center justify-between gap-3 p-2 rounded-xl transition-colors",
                    !isCamera && "cursor-pointer hover:bg-muted/50",
                  )}
                  onClick={() => !isCamera && setSelectedLight(item)}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "flex size-10 shrink-0 items-center justify-center rounded-lg border transition-colors duration-200",
                        isOn && !isCamera
                          ? "border-orange-400/30 bg-orange-400/10 dark:bg-orange-400/20"
                          : "border-border bg-muted/30",
                      )}
                    >
                      <Icon
                        className={cn(
                          "size-5 transition-colors duration-200",
                          isOn && !isCamera
                            ? "text-orange-400 dark:text-orange-500"
                            : "text-muted-foreground",
                        )}
                      />
                    </div>
                    <div className="flex flex-col">
                      <span
                        className={cn(
                          "text-sm font-medium leading-tight capitalize transition-colors duration-200",
                          isOn ? "text-foreground" : "text-muted-foreground",
                        )}
                      >
                        {item.name}
                      </span>
                      <span className="mt-1 text-xs text-muted-foreground">
                        {item.state} • {item.metadata}
                      </span>
                    </div>
                  </div>

                  {isCamera ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-8 text-xs font-semibold"
                      onClick={() => setSelectedCamera(item)}
                    >
                      View
                    </Button>
                  ) : (
                    <div onClick={(e) => e.stopPropagation()}>
                      <Switch
                        checked={item.state === "On"}
                        onCheckedChange={() => toggleDevice(item.id)}
                      />
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <p className="text-sm text-muted-foreground">
              No active devices found.
            </p>
          )}
        </div>
      </div>

      <Dialog
        open={!!selectedCamera}
        onOpenChange={(open) => !open && setSelectedCamera(null)}
      >
        <DialogContent className="sm:max-w-[600px] border-border bg-card">
          <DialogHeader>
            <DialogTitle className="text-foreground">
              {selectedCamera?.name}
            </DialogTitle>
          </DialogHeader>
          <div className="relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-lg border border-border bg-black">
            {selectedCamera && (
              <>
                <div className="absolute left-4 top-4 z-10 flex items-center gap-2">
                  <span className="relative flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500"></span>
                  </span>
                  <span className="text-xs font-bold uppercase tracking-wider text-white drop-shadow-md">
                    Live
                  </span>
                </div>
                <img
                  src={`http://127.0.0.1:8000/api/cameras/${encodeURIComponent(
                    selectedCamera.name,
                  )}/stream`}
                  alt={`${selectedCamera.name} Feed`}
                  className="h-full w-full object-cover"
                />
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Drawer
        open={!!selectedLight}
        onOpenChange={(open) => !open && setSelectedLight(null)}
      >
        {/* Override the variant class to ensure corners are actually square */}
        <DrawerContent
          className="h-full max-h-full rounded-none border-none data-[swipe-direction=down]:rounded-none"
          container={containerRef.current}
        >
          <div className="flex-1 overflow-y-auto px-4 pb-8">
            <DrawerHeader className="text-left px-0 pt-4">
              <DrawerTitle className="text-xl font-bold">
                {selectedLight?.name}
              </DrawerTitle>
              <p className="text-sm text-muted-foreground">
                {selectedLight?.state} • Brightness{" "}
                {selectedLight?.brightness || 0}%
              </p>
            </DrawerHeader>

            {selectedLight && (
              <div className="flex flex-col items-center gap-8 py-6">
                <CircularSlider
                  className="w-full max-w-[260px]"
                  value={selectedLight.brightness || 0}
                  onChange={(val) =>
                    updateLightState(selectedLight.id, { brightness: val })
                  }
                  disabled={selectedLight.state === "Off"}
                >
                  <div className="flex flex-col items-center justify-center mt-2">
                    <Button
                      variant="outline"
                      size="icon"
                      className={cn(
                        "size-20 rounded-full border-[3px] shadow-sm transition-all duration-300 pointer-events-auto",
                        selectedLight.state === "On"
                          ? "border-blue-500 bg-blue-50 text-blue-500 hover:bg-blue-100 dark:bg-blue-500/10 dark:hover:bg-blue-500/20"
                          : "border-muted bg-muted/30 text-muted-foreground",
                      )}
                      onClick={() =>
                        updateLightState(selectedLight.id, {
                          power_state:
                            selectedLight.state === "On" ? "off" : "on",
                        })
                      }
                    >
                      <Power className="size-8" strokeWidth={2.5} />
                    </Button>

                    <div
                      className={cn(
                        "text-3xl font-extrabold tracking-tight mt-4",
                        selectedLight.state === "On"
                          ? "text-blue-500"
                          : "text-muted-foreground",
                      )}
                    >
                      {selectedLight.state === "On"
                        ? `${selectedLight.brightness}%`
                        : "Off"}
                    </div>
                  </div>
                </CircularSlider>

                <div className="w-full space-y-3 pt-6 border-t border-border/50">
                  <div className="flex flex-col">
                    <h3 className="text-sm font-medium">Color</h3>
                    <p className="text-xs text-muted-foreground capitalize">
                      {selectedLight.color || "Default"}
                    </p>
                  </div>

                  <div className="grid grid-cols-6 gap-3">
                    {COLORS.map((color) => (
                      <button
                        key={color.name}
                        className={cn(
                          "size-10 rounded-full shadow-sm border-2 transition-all hover:scale-110",
                          selectedLight.color === color.hex ||
                            selectedLight.color === color.name
                            ? "border-foreground scale-110"
                            : "border-transparent",
                        )}
                        style={{ backgroundColor: color.hex }}
                        onClick={() =>
                          updateLightState(selectedLight.id, {
                            color: color.name,
                          })
                        }
                        title={color.name}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </DrawerContent>
      </Drawer>
    </div>
  );
}
