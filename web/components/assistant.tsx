"use client";

import { useEffect, useMemo, useRef, useState } from "react";
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
import {
  Camera,
  Eye,
  Maximize2,
  Radio,
  Sparkles,
  Video,
  X,
  Zap,
  CheckCircle2,
} from "lucide-react";

import { createClient } from "@/lib/chatApi";
import { smartHomeApi, type CameraDevice } from "@/lib/smart-home-api";
import {
  useBeaconSocket,
  dismissAlertById,
  type BeaconEventAlert,
} from "@/lib/use-beacon-socket";
import { SmartHomeToolUIs, TiagoToolUIs } from "@/components/assistant-ui/tools";
import { CameraModal } from "@/components/panels/smart-home/controls/camera-modal";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ASSISTANT_ID = process.env["NEXT_PUBLIC_LANGGRAPH_ASSISTANT_ID"]!;

function extractSnapshotFromResult(result: unknown): string | null {
  if (!result) return null;
  try {
    const items = Array.isArray(result)
      ? result
      : typeof result === "string"
        ? JSON.parse(result)
        : null;
    if (Array.isArray(items)) {
      for (const item of items) {
        if (item?.type === "image_url" && item?.image_url?.url) {
          return String(item.image_url.url);
        }
      }
    }
  } catch {
    // Fallback to live stream if result is not JSON array
  }
  return null;
}

const InspectCameraToolUI = makeAssistantToolUI<
  { camera_name: string; question?: string },
  unknown
>({
  toolName: "inspect_camera_feed",
  render: ({ args, result, status }) => {
    const camName = args.camera_name || "TIAGo Camera";
    const snapshotDataUrl = useMemo(() => extractSnapshotFromResult(result), [result]);
    const [viewMode, setViewMode] = useState<"live" | "snapshot">("live");
    const [expandedCam, setExpandedCam] = useState<CameraDevice | null>(null);
    const isRunning = status.type === "running";

    const activeSrc =
      viewMode === "snapshot" && snapshotDataUrl
        ? snapshotDataUrl
        : smartHomeApi.getStreamUrl(camName);

    return (
      <>
        <div className="my-2.5 overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-3.5 py-2.5">
            <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
              <div className="flex size-6 items-center justify-center rounded-lg bg-teal-500/15 text-teal-500">
                <Camera className="size-3.5" />
              </div>
              <span>{camName}</span>
              <span className="text-muted-foreground">•</span>
              <span className="text-[11px] font-normal text-muted-foreground">
                Multimodal Vision Feed
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              {snapshotDataUrl && (
                <div className="flex items-center rounded-full border border-border/60 bg-muted/40 p-0.5 text-[10px] font-semibold">
                  <button
                    type="button"
                    onClick={() => setViewMode("live")}
                    className={cn(
                      "rounded-full px-2 py-0.5 transition-colors",
                      viewMode === "live"
                        ? "bg-background text-foreground shadow-2xs"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    Live Stream
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("snapshot")}
                    className={cn(
                      "rounded-full px-2 py-0.5 transition-colors",
                      viewMode === "snapshot"
                        ? "bg-background text-teal-500 shadow-2xs"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    AI Snapshot
                  </button>
                </div>
              )}

              <span
                className={cn(
                  "flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase",
                  viewMode === "live"
                    ? "bg-red-500/15 text-red-500"
                    : "bg-teal-500/15 text-teal-500",
                )}
              >
                <span
                  className={cn(
                    "size-1.5 rounded-full",
                    viewMode === "live" ? "bg-red-500 animate-pulse" : "bg-teal-500",
                  )}
                />
                {viewMode === "live" ? "Live" : "Captured"}
              </span>

              <Button
                variant="ghost"
                size="icon"
                className="size-6 rounded-full text-muted-foreground hover:text-foreground"
                onClick={() =>
                  setExpandedCam({
                    id: camName,
                    name: camName,
                    state: "Online",
                    metadata: "640x480 • Multimodal Feed",
                    type: "Camera",
                  })
                }
                title="Expand camera feed"
              >
                <Maximize2 className="size-3.5" />
              </Button>
            </div>
          </div>

          {/* Visual Focus Subtitle */}
          {args.question && (
            <div className="flex items-center gap-2 border-b border-border/40 bg-muted/20 px-3.5 py-1.5 text-[11px] text-muted-foreground">
              <Eye className="size-3.5 shrink-0 text-teal-500" />
              <span className="truncate">
                Visual query: <strong className="font-medium text-foreground">{args.question}</strong>
              </span>
            </div>
          )}

          {/* Video / Snapshot Viewport */}
          <div className="relative aspect-video w-full bg-slate-950">
            <img
              src={activeSrc}
              alt={camName}
              className="h-full w-full object-cover"
            />
            {isRunning && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/45 backdrop-blur-[1px]">
                <div className="flex items-center gap-2 rounded-full border border-teal-500/40 bg-slate-900/90 px-3.5 py-1.5 text-xs font-semibold text-teal-400 shadow-lg">
                  <Sparkles className="size-3.5 animate-spin" />
                  Analyzing live frame with Gemini Vision...
                </div>
              </div>
            )}
          </div>
        </div>

        <CameraModal
          camera={expandedCam}
          onClose={() => setExpandedCam(null)}
        />
      </>
    );
  },
});

function EventDrivenAgentBridge() {
  const { alerts, autoWakeAgent } = useBeaconSocket();
  const aui = useAui();
  const lastAlertIdRef = useRef<string | null>(null);
  const [activeToast, setActiveToast] = useState<BeaconEventAlert | null>(null);

  useEffect(() => {
    if (!alerts.length) return;
    const latest = alerts[0];
    if (lastAlertIdRef.current === null) {
      lastAlertIdRef.current = latest.alert_id;
    } else if (latest.alert_id === lastAlertIdRef.current) {
      return;
    }
    lastAlertIdRef.current = latest.alert_id;
    setActiveToast(latest);

    if (autoWakeAgent && latest.agent_prompt) {
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
  }, [alerts, autoWakeAgent, aui]);

  if (!activeToast) return null;

  const handleAskAgentNow = () => {
    const promptText =
      activeToast.agent_prompt ||
      `Inspect '${activeToast.camera_name || "Front Door Camera"}' and report on the event: ${activeToast.message}`;
    aui.thread.append({
      role: "user",
      content: [
        {
          type: "text",
          text: `[AUTONOMOUS HOME EVENT — ${activeToast.rule_name}]: ${activeToast.message}. ${promptText}`,
        },
      ],
    });
    setActiveToast(null);
  };

  return (
    <div className="fixed bottom-6 left-20 z-50 w-80 sm:w-96 animate-in slide-in-from-bottom-5 fade-in duration-300">
      <div className="overflow-hidden rounded-2xl border border-teal-500/40 bg-card/95 shadow-2xl backdrop-blur-md">
        <div className="flex items-center justify-between border-b border-border/60 bg-teal-500/10 px-3.5 py-2">
          <div className="flex items-center gap-2">
            <Zap className="size-4 text-teal-500 animate-bounce" />
            <span className="text-xs font-bold text-foreground">
              {activeToast.rule_name}
            </span>
          </div>
          <button
            type="button"
            onClick={() => {
              dismissAlertById(activeToast.alert_id);
              setActiveToast(null);
            }}
            className="rounded-full p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          >
            <X className="size-3.5" />
          </button>
        </div>

        {/* Live PiP Camera Feed if associated with a camera */}
        {activeToast.camera_name && (
          <div className="relative aspect-video w-full bg-black">
            <div className="absolute left-2.5 top-2.5 z-10 flex items-center gap-1.5 rounded-full bg-black/65 px-2 py-0.5 text-[10px] font-semibold text-white backdrop-blur-xs">
              <span className="size-1.5 rounded-full bg-red-500 animate-pulse" />
              {activeToast.camera_name} (PiP Live)
            </div>
            <img
              src={smartHomeApi.getStreamUrl(activeToast.camera_name)}
              alt={activeToast.camera_name}
              className="h-full w-full object-cover"
            />
          </div>
        )}

        <div className="flex flex-col gap-2 p-3">
          <p className="text-xs text-muted-foreground leading-relaxed">
            {activeToast.message}
          </p>

          {activeToast.executed_actions?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {activeToast.executed_actions.map((act, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-500"
                >
                  <CheckCircle2 className="size-2.5" />
                  {act}
                </span>
              ))}
            </div>
          )}

          <div className="flex items-center justify-between gap-2 pt-1">
            <span className="font-mono text-[10px] text-muted-foreground">
              {activeToast.trigger_topic}
            </span>
            {!autoWakeAgent && (
              <Button
                size="sm"
                className="h-7 gap-1 rounded-xl text-[11px]"
                onClick={handleAskAgentNow}
              >
                <Sparkles className="size-3" />
                Ask Beacon
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
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
