"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface CircularSliderProps {
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  disabled?: boolean;
  className?: string;
  children?: React.ReactNode;
}

export function CircularSlider({
  value,
  onChange,
  min = 0,
  max = 100,
  disabled = false,
  className,
  children,
}: CircularSliderProps) {
  const svgRef = React.useRef<SVGSVGElement>(null);
  const [isDragging, setIsDragging] = React.useState(false);

  // SVG Coordinates setup
  const cx = 150;
  const cy = 150;
  const r = 120;

  // Start at bottom-left (135°), sweep clockwise to bottom-right (405°)
  const startAngle = 135;
  const endAngle = 405;
  const totalAngle = endAngle - startAngle;

  const polarToCartesian = (
    centerX: number,
    centerY: number,
    radius: number,
    angleInDegrees: number,
  ) => {
    // Standard math: 0 is right, 90 is bottom, 180 is left, 270 is top
    const angleInRadians = (angleInDegrees * Math.PI) / 180.0;
    return {
      x: centerX + radius * Math.cos(angleInRadians),
      y: centerY + radius * Math.sin(angleInRadians),
    };
  };

  const describeArc = (
    x: number,
    y: number,
    radius: number,
    startA: number,
    endA: number,
  ) => {
    // Prevent rendering errors when start and end are exactly identical
    const safeEndA = startA === endA ? endA + 0.01 : endA;
    const start = polarToCartesian(x, y, radius, startA);
    const end = polarToCartesian(x, y, radius, safeEndA);
    const largeArcFlag = safeEndA - startA <= 180 ? "0" : "1";
    // Sweep-flag 1 means clockwise
    return [
      "M",
      start.x,
      start.y,
      "A",
      radius,
      radius,
      0,
      largeArcFlag,
      1,
      end.x,
      end.y,
    ].join(" ");
  };

  const clamp = (val: number, minimum: number, maximum: number) =>
    Math.min(Math.max(val, minimum), maximum);

  const handlePointer = React.useCallback(
    (clientX: number, clientY: number) => {
      if (disabled || !svgRef.current) return;

      const rect = svgRef.current.getBoundingClientRect();
      const x = clientX - rect.left - rect.width / 2;
      const y = clientY - rect.top - rect.height / 2;

      let angle = (Math.atan2(y, x) * 180) / Math.PI;
      if (angle < 0) angle += 360;

      // Shift 0-90 quadrant to 360-450 to cleanly map into our 135 to 405 range
      if (angle < 90) angle += 360;

      let percentage = (angle - startAngle) / totalAngle;
      percentage = clamp(percentage, 0, 1);

      // Prevent sudden snapping across the empty gap at the bottom
      if (percentage > 0.95 && value < 20) percentage = 0;
      if (percentage < 0.05 && value > 80) percentage = 1;

      const newValue = Math.round(percentage * (max - min) + min);
      if (newValue !== value) {
        onChange(newValue);
      }
    },
    [disabled, value, max, min, onChange, totalAngle],
  );

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (disabled) return;
    setIsDragging(true);
    (e.target as Element).setPointerCapture(e.pointerId);
    handlePointer(e.clientX, e.clientY);
  };

  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (isDragging) {
      handlePointer(e.clientX, e.clientY);
    }
  };

  const onPointerUp = (e: React.PointerEvent<SVGSVGElement>) => {
    setIsDragging(false);
    (e.target as Element).releasePointerCapture(e.pointerId);
  };

  const clampedValue = clamp(value, min, max);
  const currentAngle =
    startAngle + ((clampedValue - min) / (max - min)) * totalAngle;
  const thumbPos = polarToCartesian(cx, cy, r, currentAngle);

  return (
    <div className={cn("relative flex items-center justify-center", className)}>
      <svg
        ref={svgRef}
        viewBox="0 0 300 300"
        className={cn(
          "w-full h-full touch-none select-none",
          disabled && "opacity-50",
        )}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
      >
        {/* Background Track */}
        <path
          d={describeArc(cx, cy, r, startAngle, endAngle)}
          fill="none"
          stroke="currentColor"
          strokeWidth="14"
          strokeLinecap="round"
          className="text-blue-500/10 dark:text-blue-500/20"
        />
        {/* Active Track */}
        {!disabled && clampedValue >= min && (
          <path
            d={describeArc(cx, cy, r, startAngle, currentAngle)}
            fill="none"
            stroke="currentColor"
            strokeWidth="14"
            strokeLinecap="round"
            className="text-blue-500 transition-all duration-75"
          />
        )}
        {/* Thumb */}
        {!disabled && (
          <circle
            cx={thumbPos.x}
            cy={thumbPos.y}
            r="16"
            fill="white"
            className={cn(
              "transition-transform duration-75 drop-shadow-md",
              isDragging ? "scale-110" : "scale-100",
            )}
            style={{ transformOrigin: `${thumbPos.x}px ${thumbPos.y}px` }}
          />
        )}
      </svg>
      {/* Centered Content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        {children}
      </div>
    </div>
  );
}
