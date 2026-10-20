"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Sparkles,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  Bot,
  Zap,
  Sliders,
  Radio,
  Check,
  X,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAiTasks } from "@/hooks/use-smart-home";
import { PanelLayout } from "./panel-layout";
import type { AiTask } from "@/lib/smart-home-api";

type FilterTab = "all" | "hitl" | "ambient";

const QUICK_SCENARIOS = [
  { id: "visitor_front_door", label: "Visitor at Door" },
  { id: "driveway_arrival", label: "Driveway Gate" },
  { id: "nightfall_lockdown", label: "Night Patrol" },
  { id: "kitchen_hazard", label: "Cooktop Alert" },
];

export function AiTasksPanel() {
  const {
    data,
    isLoading,
    approveTask,
    rejectTask,
    updateSettings,
    triggerScenario,
  } = useAiTasks(2000);
  const [tab, setTab] = useState<FilterTab>("all");
  const [busyTaskId, setBusyTaskId] = useState<string | null>(null);
  const [expandedTaskId, setExpandedTaskId] = useState<string | null>(null);

  const tasks = data?.tasks ?? [];
  const events = data?.events ?? [];
  const pendingCount = data?.pending_hitl_count ?? 0;

  const filteredTasks = tasks.filter((t) => {
    if (tab === "hitl") return t.mode === "hitl";
    if (tab === "ambient") return t.mode === "ambient";
    return true;
  });

  const handleApprove = async (taskId: string) => {
    setBusyTaskId(taskId);
    try {
      await approveTask(taskId);
    } finally {
      setBusyTaskId(null);
    }
  };

  const handleReject = async (taskId: string) => {
    setBusyTaskId(taskId);
    try {
      await rejectTask(taskId);
    } finally {
      setBusyTaskId(null);
    }
  };

  const getStatusBadge = (task: AiTask) => {
    switch (task.status) {
      case "pending_approval":
        return (
          <span className="flex items-center gap-1 rounded-full bg-amber-500/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-amber-500">
            <Clock className="size-3" />
            Needs Approval
          </span>
        );
      case "running":
        return (
          <span className="flex items-center gap-1 rounded-full bg-blue-500/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-500">
            <Zap className="size-3 animate-pulse" />
            Executing
          </span>
        );
      case "completed":
        return (
          <span className="flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-emerald-500">
            <CheckCircle2 className="size-3" />
            {task.mode === "ambient" ? "Auto-Executed" : "Approved"}
          </span>
        );
      case "rejected":
        return (
          <span className="flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
            <XCircle className="size-3" />
            Dismissed
          </span>
        );
    }
  };

  return (
    <PanelLayout
      title="AI Tasks & Workflows"
      subtitle="Ambient Background AI & Human-in-the-Loop"
      className="flex flex-col gap-5 p-5"
    >
      {/* Engine Mode Switches */}
      <div className="flex flex-col gap-3 rounded-2xl border border-border/60 bg-muted/30 p-3.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-teal-500" />
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-foreground">
                Ambient Background AI
              </span>
              <span className="text-[11px] text-muted-foreground">
                Auto-runs safe lighting & comfort rules
              </span>
            </div>
          </div>
          <Switch
            checked={data?.ambient_enabled ?? true}
            onCheckedChange={(checked) =>
              updateSettings({ ambient_enabled: checked })
            }
          />
        </div>

        <div className="h-px bg-border/50" />

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="size-4 text-amber-500" />
            <div className="flex flex-col">
              <span className="text-xs font-semibold text-foreground">
                Human-in-the-Loop (HITL)
              </span>
              <span className="text-[11px] text-muted-foreground">
                Requires approval for locks, robot & safety
              </span>
            </div>
          </div>
          <Switch
            checked={data?.hitl_enabled ?? true}
            onCheckedChange={(checked) =>
              updateSettings({ hitl_enabled: checked })
            }
          />
        </div>
      </div>

      {/* Quick Simulation Event Triggers + Link to /demo */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Simulate Sensor Event
          </span>
          <Link
            href="/demo"
            className="flex items-center gap-1 text-[11px] font-semibold text-teal-500 hover:underline"
          >
            <Sliders className="size-3" />
            Full /demo Lab
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-1.5">
          {QUICK_SCENARIOS.map((sc) => (
            <Button
              key={sc.id}
              variant="outline"
              size="sm"
              className="h-8 justify-start gap-1.5 rounded-xl text-[11px] font-medium"
              onClick={() => triggerScenario(sc.id)}
            >
              <Radio className="size-3 text-teal-500" />
              <span className="truncate">{sc.label}</span>
            </Button>
          ))}
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="grid grid-cols-3 gap-1 rounded-2xl bg-muted/60 p-1">
        <button
          type="button"
          onClick={() => setTab("all")}
          className={cn(
            "rounded-xl py-1.5 text-xs font-semibold transition-colors",
            tab === "all"
              ? "bg-background text-foreground shadow-xs"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          All ({tasks.length})
        </button>
        <button
          type="button"
          onClick={() => setTab("hitl")}
          className={cn(
            "flex items-center justify-center gap-1 rounded-xl py-1.5 text-xs font-semibold transition-colors",
            tab === "hitl"
              ? "bg-background text-foreground shadow-xs"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          HITL
          {pendingCount > 0 && (
            <span className="rounded-full bg-amber-500 px-1.5 py-0.2 text-[10px] font-bold text-white">
              {pendingCount}
            </span>
          )}
        </button>
        <button
          type="button"
          onClick={() => setTab("ambient")}
          className={cn(
            "rounded-xl py-1.5 text-xs font-semibold transition-colors",
            tab === "ambient"
              ? "bg-background text-foreground shadow-xs"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          Ambient
        </button>
      </div>

      {/* Tasks Feed */}
      {isLoading ? (
        <p className="animate-pulse text-xs text-muted-foreground">
          Syncing Ambient & HITL task queue...
        </p>
      ) : filteredTasks.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-6 text-center text-xs text-muted-foreground">
          No tasks in this view. Trigger a sensor event above or walk a human in{" "}
          <Link href="/demo" className="font-semibold text-teal-500 underline">
            /demo
          </Link>
          .
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filteredTasks.map((task) => {
            const isPending = task.status === "pending_approval";
            const isBusy = busyTaskId === task.id;
            const isExpanded = expandedTaskId === task.id;

            return (
              <div
                key={task.id}
                data-testid={`ai-task-card-${task.id}`}
                className={cn(
                  "flex flex-col gap-2.5 rounded-2xl border p-3.5 transition-colors",
                  isPending
                    ? "border-amber-500/40 bg-amber-500/5"
                    : "border-border/60 bg-muted/20",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        "rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase",
                        task.mode === "hitl"
                          ? "bg-amber-500/20 text-amber-500"
                          : "bg-teal-500/20 text-teal-500",
                      )}
                    >
                      {task.mode === "hitl" ? "HITL" : "Ambient"}
                    </span>
                    <span className="text-[11px] font-medium text-muted-foreground">
                      {task.room} • {task.created_at}
                    </span>
                  </div>
                  {getStatusBadge(task)}
                </div>

                <div className="flex flex-col gap-1">
                  <h3 className="text-sm font-semibold leading-snug text-foreground">
                    {task.title}
                  </h3>
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {task.description}
                  </p>
                </div>

                {/* Proposed / Executed Actions */}
                {task.proposed_actions.length > 0 && (
                  <div className="flex flex-col gap-1 rounded-xl border border-border/50 bg-background/60 p-2.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {task.mode === "ambient"
                        ? "Autonomous Actions"
                        : "Proposed Actions"}
                    </span>
                    {task.proposed_actions.map((act, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-1.5 text-xs text-foreground"
                      >
                        <Bot className="size-3 shrink-0 text-teal-500" />
                        <span className="truncate">
                          {act.label || `${act.type}`}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* HITL Approval Buttons */}
                {isPending && (
                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <Button
                      size="sm"
                      data-testid={`approve-${task.id}`}
                      disabled={isBusy}
                      className="h-8 gap-1.5 rounded-xl bg-emerald-600 text-xs font-semibold text-white hover:bg-emerald-700"
                      onClick={() => handleApprove(task.id)}
                    >
                      <Check className="size-3.5" />
                      Approve & Run
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      data-testid={`reject-${task.id}`}
                      disabled={isBusy}
                      className="h-8 gap-1.5 rounded-xl text-xs font-semibold"
                      onClick={() => handleReject(task.id)}
                    >
                      <X className="size-3.5" />
                      Dismiss
                    </Button>
                  </div>
                )}

                {/* Expandable Execution Log */}
                {task.logs && task.logs.length > 0 && (
                  <div className="border-t border-border/40 pt-1.5">
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedTaskId(isExpanded ? null : task.id)
                      }
                      className="flex w-full items-center justify-between text-[11px] font-medium text-muted-foreground hover:text-foreground"
                    >
                      <span>Trigger: {task.trigger_source}</span>
                      {isExpanded ? (
                        <ChevronUp className="size-3.5" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                    </button>
                    {isExpanded && (
                      <div className="mt-1.5 flex flex-col gap-1 rounded-lg bg-muted/40 p-2 font-mono text-[10px] text-muted-foreground">
                        {task.logs.map((line, i) => (
                          <div key={i}>{line}</div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Recent Sensor & Supervisor Event Stream */}
      {events.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-border/50 pt-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Live Sensor & Supervisor Event Log
          </span>
          <div className="flex flex-col gap-1.5">
            {events.slice(0, 6).map((evt) => (
              <div
                key={evt.id}
                className="flex flex-col gap-0.5 rounded-xl border border-border/40 bg-muted/20 px-3 py-2 text-xs"
              >
                <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                  <span className="font-semibold text-teal-500">
                    {evt.source}
                  </span>
                  <span>{evt.timestamp}</span>
                </div>
                <span className="text-foreground">{evt.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </PanelLayout>
  );
}
