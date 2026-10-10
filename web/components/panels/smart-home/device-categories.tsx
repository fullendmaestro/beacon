import {
  Camera,
  Lightbulb,
  Monitor,
  Lock,
  Thermometer,
  ChevronRight,
  ChevronDown,
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

interface DeviceCategoriesProps {
  onSelect: (category: string) => void;
}

export function DeviceCategories({ onSelect }: DeviceCategoriesProps) {
  return (
    <div className="flex flex-col gap-6">
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

      <div className="grid grid-cols-2 gap-3">
        {DEVICES.map((device) => {
          const Icon = device.icon;
          return (
            <Card
              key={device.name}
              className="cursor-pointer rounded-3xl border-transparent bg-muted/60 shadow-none transition-colors hover:bg-muted"
              onClick={() => onSelect(device.name)}
            >
              <CardHeader>
                <Icon className={cn(device.colorClass)} />
                <CardAction className="text-muted-foreground">
                  <ChevronRight size={16} />
                </CardAction>
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
