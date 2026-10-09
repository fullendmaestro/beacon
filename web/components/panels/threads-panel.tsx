"use client";

import { PanelRightClose } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePanelState } from "@/hooks/use-panel-state";
import { ThreadList } from "@/components/assistant-ui/elements/thread-list.aui";

export function ThreadsPanel() {
  const { setActivePanel } = usePanelState();

  return (
    <div className="flex h-full flex-col">
      {/* Header Container */}
      <div className="relative flex flex-col items-center justify-center border-b border-border/40 pb-4 pt-6">
        <h2 className="text-base font-semibold tracking-tight text-foreground">
          Recent Chats
        </h2>

        <Button
          variant="secondary"
          size="icon"
          className="absolute right-4 top-6 size-8 rounded-full text-foreground hover:bg-muted"
          onClick={() => setActivePanel("none")}
        >
          <PanelRightClose className="size-4" />
          <span className="sr-only">Close panel</span>
        </Button>
      </div>

      {/* Assistant UI ThreadList Native Integration */}
      <div className="flex-1 overflow-y-auto">
        <ThreadList />
      </div>
    </div>
  );
}
