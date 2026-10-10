"use client";

import { useEffect, useState, useCallback } from "react";
import { Camera, Lightbulb, Monitor, Lock, Thermometer } from "lucide-react";
import { Switch } from "@/components/ui/switch";

interface DeviceItem {
  id: number;
  name: string;
  state: string;
  metadata: string;
  type: string;
}

export function DeviceList({ category }: { category: string }) {
  const [items, setItems] = useState<DeviceItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchDevices = useCallback(async () => {
    if (category !== "Lights") {
      setItems([]);
      setIsLoading(false);
      return;
    }

    try {
      const res = await fetch("http://127.0.0.1:8000/api/lights");
      if (res.ok) {
        const data = await res.json();
        setItems(data);
      }
    } catch (e) {
      console.error(
        "Failed to fetch lights. Ensure the Webots controller is running.",
        e,
      );
    } finally {
      setIsLoading(false);
    }
  }, [category]);

  useEffect(() => {
    fetchDevices();
    // Optional: Set up polling to keep state in sync if lights are changed elsewhere
    const interval = setInterval(fetchDevices, 2000);
    return () => clearInterval(interval);
  }, [fetchDevices]);

  const toggleDevice = async (id: number) => {
    // Optimistic UI update
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
      console.error("Failed to toggle light", e);
      fetchDevices(); // Revert on failure
    }
  };

  return (
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
          items.map((item) => (
            <div
              key={item.id}
              className="flex items-center justify-between gap-3"
            >
              <div className="flex items-center gap-3">
                <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-muted/30">
                  <Lightbulb className="size-5 text-orange-400" />
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-medium leading-tight text-foreground capitalize">
                    {item.name}
                  </span>
                  <span className="mt-1 text-xs text-muted-foreground">
                    {item.state} • {item.metadata}
                  </span>
                </div>
              </div>
              <Switch
                checked={item.state === "On"}
                onCheckedChange={() => toggleDevice(item.id)}
              />
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">
            No active devices found on the local network.
          </p>
        )}
      </div>
    </div>
  );
}
