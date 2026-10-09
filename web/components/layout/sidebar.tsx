"use client";

import { Home, Lightbulb, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePanelState, type PanelType } from "@/hooks/use-panel-state";
import { cn } from "@/lib/utils";

const NAV_ITEMS: { id: PanelType; icon: React.ElementType; label: string }[] = [
  { id: "none", icon: Home, label: "Home" },
  { id: "smart-home", icon: Lightbulb, label: "Smart Home" },
  { id: "shopping-list", icon: List, label: "Lists" },
];

export function Sidebar() {
  const { activePanel, setActivePanel } = usePanelState();

  return (
    <aside className="flex flex-col items-center gap-4 rounded-full border border-border bg-card px-2 py-4 shadow-sm">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive =
          (item.id === "none" && activePanel === "none") ||
          (item.id !== "none" && activePanel === item.id);

        return (
          <Button
            key={item.id}
            variant="ghost"
            size="icon"
            className={cn(
              "size-10 rounded-full transition-colors",
              isActive
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "text-muted-foreground hover:bg-muted",
            )}
            onClick={() => setActivePanel(item.id)}
            title={item.label}
          >
            <Icon className="size-5" />
            <span className="sr-only">{item.label}</span>
          </Button>
        );
      })}
    </aside>
  );
}
