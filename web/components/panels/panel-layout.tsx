"use client";

import { PanelRightClose, ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePanelState } from "@/hooks/use-panel-state";
import { cn } from "@/lib/utils";

interface PanelLayoutProps {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  children: React.ReactNode;
  className?: string;
  headerRight?: React.ReactNode;
}

export function PanelLayout({
  title,
  subtitle,
  onBack,
  children,
  className,
  headerRight,
}: PanelLayoutProps) {
  const { setActivePanel } = usePanelState();

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="relative flex min-h-[4.5rem] flex-col items-center justify-center border-b border-border/40 px-12 py-3">
        {onBack && (
          <Button
            variant="ghost"
            size="icon"
            className="absolute left-4 top-1/2 -translate-y-1/2 size-8 rounded-full"
            onClick={onBack}
          >
            <ChevronLeft className="size-5" />
            <span className="sr-only">Go back</span>
          </Button>
        )}

        <h2 className="text-base font-semibold tracking-tight text-foreground">
          {title}
        </h2>
        {subtitle && (
          <p className="text-xs text-muted-foreground text-center">
            {subtitle}
          </p>
        )}

        <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2">
          {headerRight}
          <Button
            variant="ghost"
            size="icon"
            className="size-8 rounded-full text-foreground hover:bg-muted"
            onClick={() => setActivePanel("none")}
          >
            <PanelRightClose className="size-4" />
            <span className="sr-only">Close panel</span>
          </Button>
        </div>
      </div>

      {/* Body */}
      <div className={cn("flex-1 overflow-y-auto", className)}>{children}</div>
    </div>
  );
}
