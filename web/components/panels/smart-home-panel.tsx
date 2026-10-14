"use client";

import { useState } from "react";
import { DeviceCategories } from "./smart-home/device-categories";
import { DeviceList } from "./smart-home/device-list";
import { PanelLayout } from "./panel-layout";
import type { SmartCategory } from "@/lib/smart-home-api";

export function SmartHomePanel() {
  const [activeCategory, setActiveCategory] = useState<SmartCategory | null>(
    null,
  );

  return (
    <PanelLayout
      title={activeCategory || "Smart Home"}
      subtitle={
        !activeCategory ? "Live Webots IoT Estate & Automation Hub" : undefined
      }
      onBack={activeCategory ? () => setActiveCategory(null) : undefined}
      className="p-6"
    >
      {activeCategory ? (
        <DeviceList category={activeCategory} />
      ) : (
        <DeviceCategories onSelect={setActiveCategory} />
      )}
    </PanelLayout>
  );
}
