"use client";

import { PanelRightClose } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePanelState } from "@/hooks/use-panel-state";
import { ThreadList } from "@/components/assistant-ui/elements/thread-list.aui";

export function ThreadsPanel() {
  const { setActivePanel } = usePanelState();

  return (
    <div className="flex h-full flex-col p-6 gap-6">
      <div className="flex flex-col items-start gap-4">
        <div className="flex w-full items-center justify-between">
          <h2 className="text-xl font-semibold tracking-tight text-foreground">
            Recent Chats
          </h2>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 rounded-full text-muted-foreground hover:bg-muted"
            onClick={() => setActivePanel("none")}
          >
            <PanelRightClose className="size-4" />
            <span className="sr-only">Close panel</span>
          </Button>
        </div>
        <p className="text-sm font-medium text-foreground">
          View your cross-device conversation history.
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        <ThreadList />
      </div>
    </div>
  );
}
