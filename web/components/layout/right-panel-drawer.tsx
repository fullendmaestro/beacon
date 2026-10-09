"use client";

import { usePanelState } from "@/hooks/use-panel-state";
import { SmartHomePanel } from "@/components/panels/smart-home-panel";
import { ShoppingListPanel } from "@/components/panels/shopping-list-panel";
import { ThreadsPanel } from "@/components/panels/threads-panel";
import { cn } from "@/lib/utils";

export function RightPanelDrawer() {
  const { activePanel } = usePanelState();
  const isOpen = activePanel !== "none";

  return (
    <div
      className={cn(
        "flex h-full shrink-0 flex-col rounded-3xl border border-border bg-card shadow-sm transition-[width,opacity,margin] duration-300 ease-in-out",
        isOpen
          ? "ml-4 w-80 opacity-100 lg:w-[400px]"
          : "ml-0 w-0 overflow-hidden border-none opacity-0",
      )}
    >
      <div className="relative flex h-full min-w-[20rem] flex-col lg:min-w-[400px]">
        <div className="flex-1 overflow-y-auto">
          {activePanel === "threads" && <ThreadsPanel />}
          {activePanel === "smart-home" && <SmartHomePanel />}
          {activePanel === "shopping-list" && <ShoppingListPanel />}
        </div>
      </div>
    </div>
  );
}
