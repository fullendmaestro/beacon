"use client";

import Link from "next/link";
import { Home, Clock, Lightbulb, Sparkles, Sliders } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePanelState, type PanelType } from "@/hooks/use-panel-state";
import { useAiTasks } from "@/hooks/use-smart-home";
import { cn } from "@/lib/utils";

const NAV_ITEMS: { id: PanelType; icon: React.ElementType; label: string }[] = [
  { id: "none", icon: Home, label: "Home" },
  { id: "threads", icon: Clock, label: "Recent Chats" },
  { id: "smart-home", icon: Lightbulb, label: "Smart Home" },
  { id: "ai-tasks", icon: Sparkles, label: "AI Tasks (Ambient & HITL)" },
];

export function Sidebar() {
  const { activePanel, setActivePanel } = usePanelState();
  const { data: tasksData } = useAiTasks(3000);
  const pendingCount = tasksData?.pending_hitl_count ?? 0;

  return (
    <aside className="flex flex-col items-center gap-4 rounded-full border border-border bg-card px-2 py-4 shadow-sm">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive =
          (item.id === "none" && activePanel === "none") ||
          (item.id !== "none" && activePanel === item.id);

        return (
          <div key={item.id} className="relative">
            <Button
              data-testid={`nav-${item.id}`}
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
            {item.id === "ai-tasks" && pendingCount > 0 && (
              <span className="pointer-events-none absolute -right-0.5 -top-0.5 flex size-4 items-center justify-center rounded-full bg-amber-500 text-[10px] font-bold text-white shadow-sm">
                {pendingCount}
              </span>
            )}
          </div>
        );
      })}

      <div className="h-px w-6 bg-border/60" />

      <Button
        asChild
        variant="ghost"
        size="icon"
        className="size-10 rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        title="Simulation & Demo Control Center (/demo)"
      >
        <Link href="/demo" data-testid="nav-demo">
          <Sliders className="size-5" />
          <span className="sr-only">Demo Control Center</span>
        </Link>
      </Button>
    </aside>
  );
}
