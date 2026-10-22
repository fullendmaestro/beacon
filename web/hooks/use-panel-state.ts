"use client";

import { create } from "zustand";

export type PanelType = "none" | "threads" | "smart-home" | "shopping-list";

interface PanelState {
  activePanel: PanelType;
  setActivePanel: (panel: PanelType) => void;
}

export const usePanelState = create<PanelState>((set) => ({
  activePanel: "none",
  setActivePanel: (panel) => set({ activePanel: panel }),
}));
