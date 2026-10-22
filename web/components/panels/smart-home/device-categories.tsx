"use client";

import { ChevronRight } from "lucide-react";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { DEVICE_CATEGORIES } from "./constants";
import { HomeStatusHeader } from "./home-status-header";
import { useSmartHomeSummary } from "@/hooks/use-smart-home";
import type { SmartCategory } from "@/lib/smart-home-api";

interface DeviceCategoriesProps {
  onSelect: (category: SmartCategory) => void;
}

export function DeviceCategories({ onSelect }: DeviceCategoriesProps) {
  const { summary, isTriggering, triggerScene, setTimeOfDay } =
    useSmartHomeSummary();

  const getBadgeText = (category: SmartCategory): string | null => {
    if (!summary) return null;
    switch (category) {
      case "Cameras":
        return `${summary.cameras_online} Live`;
      case "Lights":
        return `${summary.lights_on}/${summary.total_lights} On`;
      case "Locks & Doors":
        return `${summary.total_doors} Barriers`;
      case "Blinds":
        return `${summary.blinds_count} Shades`;
      case "Thermostats":
        return `${summary.climate_zones} Zones`;
      case "Robots":
        return summary.robot
          ? `${summary.robot.status} • ${summary.robot.current_room}`
          : summary.rover
            ? `${summary.rover.status} • ${summary.rover.current_room}`
            : "1 Robot";
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <HomeStatusHeader
        summary={summary}
        isTriggering={isTriggering}
        onTriggerScene={triggerScene}
        onSelectTimeOfDay={setTimeOfDay}
      />

      <div className="flex flex-col gap-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Device Categories
        </span>

        <div className="grid grid-cols-2 gap-3">
          {DEVICE_CATEGORIES.map((device) => {
            const Icon = device.icon;
            const badge = getBadgeText(device.name);

            return (
              <Card
                key={device.name}
                className="cursor-pointer rounded-3xl border-transparent bg-muted/60 shadow-none transition-colors hover:bg-muted"
                onClick={() => onSelect(device.name)}
              >
                <CardHeader className="pb-2">
                  <Icon className={cn("size-5", device.colorClass)} />
                  <CardAction className="text-muted-foreground">
                    <ChevronRight size={16} />
                  </CardAction>
                </CardHeader>
                <CardContent className="flex flex-col gap-0.5">
                  <CardTitle className="text-sm font-semibold leading-tight text-foreground">
                    {device.name}
                  </CardTitle>
                  {badge && (
                    <span className="text-[11px] text-muted-foreground">
                      {badge}
                    </span>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
