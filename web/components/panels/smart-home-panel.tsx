"use client";

import {
  Camera,
  Lightbulb,
  Monitor,
  Lock,
  Thermometer,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

const DEVICES = [
  {
    name: "Cameras",
    icon: Camera,
    colorClass: "text-blue-500 dark:text-blue-400",
  },
  {
    name: "Lights",
    icon: Lightbulb,
    colorClass: "text-orange-400 dark:text-orange-500",
  },
  {
    name: "Devices",
    icon: Monitor,
    colorClass: "text-muted-foreground",
  },
  {
    name: "Locks",
    icon: Lock,
    colorClass: "text-muted-foreground",
  },
  {
    name: "Thermostats",
    icon: Thermometer,
    colorClass: "text-orange-600 dark:text-orange-500",
  },
];

export function SmartHomePanel() {
  return (
    <div className="flex h-full flex-col gap-6 p-6">
      <div className="flex flex-col items-start gap-4">
        <h2 className="text-xl font-semibold tracking-tight text-foreground">
          Smart Home
        </h2>

        <Button
          variant="outline"
          className="h-8 rounded-full border border-border bg-card px-4 text-sm font-medium shadow-sm hover:bg-muted"
        >
          Favorites
          <ChevronDown data-icon="inline-end" />
        </Button>
      </div>

      <p className="text-sm font-medium text-foreground">
        Manage your devices through the Alexa app.
      </p>

      {/* 2-Column Grid visual */}
      <div className="grid grid-cols-2 gap-3">
        {DEVICES.map((device) => {
          const Icon = device.icon;
          return (
            <Card
              key={device.name}
              className="rounded-3xl border-transparent bg-muted/60 shadow-none transition-colors hover:bg-muted"
            >
              <CardHeader>
                <Icon className={cn(device.colorClass)} />
                <CardAction className="text-muted-foreground">
                  <ChevronRight size={16} />
                </CardAction>{" "}
              </CardHeader>

              <CardContent>
                <CardTitle className="text-sm font-medium leading-tight text-foreground">
                  {device.name}
                </CardTitle>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
