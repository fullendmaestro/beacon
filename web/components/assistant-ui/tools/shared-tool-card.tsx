"use client";

import React from "react";
import {
  Loader2,
  CheckCircle2,
  AlertTriangle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

export function parseToolResult<T = any>(result: unknown): T | null {
  if (result === undefined || result === null) return null;

  if (typeof result === "string") {
    try {
      return JSON.parse(result) as T;
    } catch {
      return result as unknown as T;
    }
  }

  if (Array.isArray(result)) {
    // Check if it's an MCP content block array: [{ type: "text", text: "..." }]
    if (
      result.length > 0 &&
      typeof result[0] === "object" &&
      result[0] !== null &&
      "type" in result[0] &&
      "text" in result[0]
    ) {
      const combined = result.map((block: any) => block.text).join("\n");
      try {
        return JSON.parse(combined) as T;
      } catch {
        return combined as unknown as T;
      }
    }
    return result as unknown as T;
  }

  if (typeof result === "object" && "content" in (result as any)) {
    return parseToolResult<T>((result as any).content);
  }

  return result as T;
}

interface ToolCardShellProps {
  title: string;
  subtitle?: string;
  icon: LucideIcon;
  iconColorClass?: string;
  status: { type: string };
  isError?: boolean;
  badge?: React.ReactNode;
  children?: React.ReactNode;
}

export function ToolCardShell({
  title,
  subtitle,
  icon: Icon,
  iconColorClass = "text-primary",
  status,
  isError,
  badge,
  children,
}: ToolCardShellProps) {
  const isRunning = status.type === "running";

  return (
    <div className="my-2.5 w-full max-w-md overflow-hidden rounded-2xl border border-border/70 bg-card/90 shadow-xs backdrop-blur-xs transition-all">
      <div className="flex items-center justify-between gap-3 border-b border-border/40 bg-muted/30 px-3.5 py-2.5">
        <div className="flex items-center gap-2.5 min-w-0">
          <div
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-xl border border-border/50 bg-background",
              iconColorClass,
            )}
          >
            {isRunning ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            ) : (
              <Icon className="size-4" />
            )}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="truncate text-xs font-semibold text-foreground">
              {title}
            </span>
            {subtitle && (
              <span className="truncate text-[11px] text-muted-foreground">
                {subtitle}
              </span>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {badge}
          {!isRunning &&
            (isError ? (
              <AlertTriangle className="size-4 text-destructive" />
            ) : (
              <CheckCircle2 className="size-4 text-emerald-500" />
            ))}
        </div>
      </div>

      {children && <div className="p-3.5 text-xs">{children}</div>}
    </div>
  );
}
