"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  AssistantRuntimeProvider,
  makeAssistantToolUI,
  useAui,
} from "@assistant-ui/react";
import {
  unstable_createLangGraphStream,
  useLangGraphRuntime,
  type LangChainMessage,
} from "@assistant-ui/react-langgraph";
import { Camera } from "lucide-react";

import { createClient } from "@/lib/chatApi";
import { smartHomeApi } from "@/lib/smart-home-api";
import { useBeaconSocket } from "@/lib/use-beacon-socket";
import { SmartHomeToolUIs, TiagoToolUIs } from "@/components/assistant-ui/tools";

const ASSISTANT_ID = process.env["NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID"]!;

const InspectCameraToolUI = makeAssistantToolUI<
  { camera_name: string; question?: string },
  unknown
>({
  toolName: "inspect_camera_feed",
  render: ({ args }) => {
    const camName = args.camera_name || "TIAGo Camera";
    return (
      <div className="my-2 overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b border-border/60 px-3.5 py-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <Camera className="size-4 text-teal-500" />
            <span>{camName} — Agent Vision Feed</span>
          </div>
          <span className="flex items-center gap-1.5 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold uppercase text-red-500">
            <span className="size-1.5 rounded-full bg-red-500 animate-pulse" />
            Live
          </span>
        </div>
        <div className="relative aspect-video w-full bg-black">
          <img
            src={smartHomeApi.getStreamUrl(camName)}
            alt={camName}
            className="h-full w-full object-cover"
          />
        </div>
      </div>
    );
  },
});

function EventDrivenAgentBridge() {
  const { alerts } = useBeaconSocket();
  const aui = useAui();
  const lastAlertIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!alerts.length) return;
    const latest = alerts[0];
    if (lastAlertIdRef.current === null) {
      lastAlertIdRef.current = latest.alert_id;
      return;
    }
    if (latest.alert_id === lastAlertIdRef.current) return;
    lastAlertIdRef.current = latest.alert_id;

    if (latest.agent_prompt) {
      aui.thread.append({
        role: "user",
        content: [
          {
            type: "text",
            text: `[AUTONOMOUS HOME EVENT — ${latest.rule_name}]: ${latest.message}. ${latest.agent_prompt}`,
          },
        ],
      });
    }
  }, [alerts, aui]);

  return null;
}

export function Assistant({ children }: { children: React.ReactNode }) {
  const client = useMemo(() => createClient(), []);
  const stream = useMemo(
    () =>
      unstable_createLangGraphStream({
        client,
        assistantId: ASSISTANT_ID,
      }),
    [client],
  );

  const runtime = useLangGraphRuntime({
    unstable_allowCancellation: true,
    stream,
    create: async () => {
      const { thread_id } = await client.threads.create();
      return { externalId: thread_id };
    },
    load: async (externalId) => {
      const state = await client.threads.getState<{
        messages: LangChainMessage[];
      }>(externalId);
      return {
        messages: state.values.messages,
        interrupts: state.tasks[0]?.interrupts,
      };
    },
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <SmartHomeToolUIs />
      <TiagoToolUIs />
      <InspectCameraToolUI />
      <EventDrivenAgentBridge />
      {children}
    </AssistantRuntimeProvider>
  );
}
