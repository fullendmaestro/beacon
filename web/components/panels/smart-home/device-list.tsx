import { Camera, Lightbulb, Monitor, Lock, Thermometer } from "lucide-react";

const DEVICE_ITEMS: Record<
  string,
  { name: string; state: string; metadata: string }[]
> = {
  Cameras: [
    { name: "Front Door Camera", state: "Online", metadata: "Feed active" },
    { name: "Backyard Camera", state: "Online", metadata: "Feed active" },
    {
      name: "Garage Camera",
      state: "Offline",
      metadata: "Last seen 2 hours ago",
    },
  ],
  Lights: [
    { name: "Living Room Light", state: "On", metadata: "Brightness at 80%" },
    { name: "Kitchen Main", state: "Off", metadata: "Brightness at 0%" },
    { name: "Bedroom Lamp", state: "On", metadata: "Brightness at 100%" },
  ],
  Devices: [],
  Locks: [],
  Thermostats: [],
};

function getCategoryIcon(category: string) {
  switch (category) {
    case "Cameras":
      return <Camera className="size-5 text-muted-foreground" />;
    case "Lights":
      return <Lightbulb className="size-5 text-muted-foreground" />;
    case "Locks":
      return <Lock className="size-5 text-muted-foreground" />;
    case "Thermostats":
      return <Thermometer className="size-5 text-muted-foreground" />;
    default:
      return <Monitor className="size-5 text-muted-foreground" />;
  }
}

interface DeviceListProps {
  category: string;
}

export function DeviceList({ category }: DeviceListProps) {
  const items = DEVICE_ITEMS[category] || [];

  return (
    <div className="flex flex-col gap-6">
      {/* Category Description */}
      <p className="text-sm text-muted-foreground">
        View the status and manage settings for your connected{" "}
        {category.toLowerCase()}.
      </p>

      {/* Device List matching attachment card styles */}
      <div className="flex flex-col gap-5">
        {items.length > 0 ? (
          items.map((item, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-muted/30">
                {getCategoryIcon(category)}
              </div>
              <div className="flex flex-col">
                <span className="text-sm font-medium leading-tight text-foreground">
                  {item.name}
                </span>
                <span className="mt-1 text-xs text-muted-foreground">
                  {item.state} • {item.metadata}
                </span>
              </div>
            </div>
          ))
        ) : (
          <p className="text-sm text-muted-foreground">
            No devices found in this category.
          </p>
        )}
      </div>
    </div>
  );
}
