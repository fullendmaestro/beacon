"use client";

import { ThreadList } from "@/components/assistant-ui/elements/thread-list.aui";
import { PanelLayout } from "./panel-layout";

export function ThreadsPanel() {
  return (
    <PanelLayout
      title="Recent Chats"
      subtitle="View your cross-device conversation history."
      className="p-6"
    >
      <ThreadList />
    </PanelLayout>
  );
}
