"use client";

import { useState } from "react";
import { Map, LayoutGrid, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { DeviceCategories } from "./smart-home/device-categories";
import { DeviceList } from "./smart-home/device-list";
import { FloorplanMinimap } from "./smart-home/floorplan-minimap";
import { ProvisionDeviceModal } from "./smart-home/provision-device-modal";
import { PanelLayout } from "./panel-layout";
import type { SmartCategory } from "@/lib/smart-home-api";

export function SmartHomePanel() {
  const [activeCategory, setActiveCategory] = useState<SmartCategory | null>(
    null,
  );
  const [viewMode, setViewMode] = useState<"floorplan" | "categories">(
    "floorplan",
  );
  const [isProvisionOpen, setIsProvisionOpen] = useState(false);

  return (
    <PanelLayout
      title={activeCategory || "Smart Home"}
      subtitle={
        !activeCategory
          ? "Decoupled SQLite Digital Twin & Event Broker"
          : undefined
      }
      onBack={activeCategory ? () => setActiveCategory(null) : undefined}
      headerRight={
        !activeCategory ? (
          <Button
            variant="ghost"
            size="icon"
            className="size-8 rounded-full"
            onClick={() => setIsProvisionOpen(true)}
            title="Provision new IoT device"
          >
            <Plus className="size-4" />
          </Button>
        ) : undefined
      }
      className={cn("p-6", activeCategory && "flex flex-col")}
    >
      {activeCategory ? (
        <DeviceList category={activeCategory} />
      ) : (
        <div className="flex flex-col gap-5">
          {/* Top View Mode Toggle: Live 2D Floorplan vs Device Categories */}
          <div className="grid grid-cols-2 gap-1.5 rounded-2xl border border-border/60 bg-muted/40 p-1">
            <button
              type="button"
              onClick={() => setViewMode("floorplan")}
              className={cn(
                "flex items-center justify-center gap-1.5 rounded-xl py-1.5 text-xs font-semibold transition-all",
                viewMode === "floorplan"
                  ? "bg-background text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Map className="size-3.5" />
              2D Floorplan Map
            </button>
            <button
              type="button"
              onClick={() => setViewMode("categories")}
              className={cn(
                "flex items-center justify-center gap-1.5 rounded-xl py-1.5 text-xs font-semibold transition-all",
                viewMode === "categories"
                  ? "bg-background text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <LayoutGrid className="size-3.5" />
              Device Categories
            </button>
          </div>

          {viewMode === "floorplan" && (
            <FloorplanMinimap
              onOpenProvisionModal={() => setIsProvisionOpen(true)}
            />
          )}

          <DeviceCategories onSelect={setActiveCategory} />
        </div>
      )}

      <ProvisionDeviceModal
        open={isProvisionOpen}
        onOpenChange={setIsProvisionOpen}
      />
    </PanelLayout>
  );
}
