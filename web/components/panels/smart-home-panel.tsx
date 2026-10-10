"use client";

import { useState } from "react";
import { DeviceCategories } from "./smart-home/device-categories";
import { DeviceList } from "./smart-home/device-list";
import { PanelLayout } from "./panel-layout";

export function SmartHomePanel() {
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  return (
    <PanelLayout
      title={activeCategory || "Smart Home"}
      subtitle={
        !activeCategory
          ? "Manage your devices through the Alexa app."
          : undefined
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
