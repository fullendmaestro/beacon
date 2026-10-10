"use client";

import { useEffect, useState, useCallback } from "react";
import { Camera, Lightbulb } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface DeviceItem {
  id: number | string;
  name: string;
  state: string;
  metadata: string;
  type: string;
}

export function DeviceList({ category }: { category: string }) {
  const [items, setItems] = useState<DeviceItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCamera, setSelectedCamera] = useState<DeviceItem | null>(null);

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

  const toggleDevice = async (id: number | string) => {
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

  return (
    <>
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
                  className="flex items-center justify-between gap-3"
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
                    <Switch
                      checked={item.state === "On"}
                      onCheckedChange={() => toggleDevice(item.id)}
                    />
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

      {/* Video Feed Modal */}
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
          <div className="flex aspect-video w-full items-center justify-center overflow-hidden rounded-lg border border-border bg-black relative">
            {selectedCamera && (
              <>
                <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
                  <span className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                  </span>
                  <span className="text-xs font-bold text-white uppercase drop-shadow-md tracking-wider">
                    Live
                  </span>
                </div>
                {/* MJPEG behaves exactly like an image natively */}
                <img
                  src={`http://127.0.0.1:8000/api/cameras/${encodeURIComponent(selectedCamera.name)}/stream`}
                  alt={`${selectedCamera.name} Feed`}
                  className="w-full h-full object-cover"
                />
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
