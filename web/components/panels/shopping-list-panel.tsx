"use client";

import { Plus, MoreVertical, PanelRightClose } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { usePanelState } from "@/hooks/use-panel-state";

const LIST_ITEMS = [
  { id: 1, name: "Potatoes", metadata: "Added by you just now" },
  { id: 2, name: "Milk", metadata: "Added by you just now" },
  { id: 3, name: "Cheese", metadata: "Added by you just now" },
  { id: 4, name: "Apples (4)", metadata: "Added by Adam yesterday" },
  { id: 5, name: "Spinach", metadata: "Added by Adam yesterday" },
  {
    id: 6,
    name: "Organic boneless spicy chicken",
    metadata: "Added by Adam yesterday",
  },
];

export function ShoppingListPanel() {
  const { setActivePanel } = usePanelState();

  return (
    <div className="flex h-full flex-col">
      {/* Header Container */}
      <div className="relative flex flex-col items-center justify-center border-b border-border/40 pb-4 pt-6">
        <h2 className="text-base font-semibold tracking-tight text-foreground">
          Shopping List
        </h2>
        <p className="text-xs text-muted-foreground">7 items</p>

        <Button
          variant="secondary"
          size="icon"
          className="absolute right-4 top-6 size-8 rounded-full text-foreground hover:bg-muted"
          onClick={() => setActivePanel("none")}
        >
          <PanelRightClose className="size-4" />
          <span className="sr-only">Close panel</span>
        </Button>
      </div>

      {/* Controls Container */}
      <div className="flex items-center justify-between px-6 py-4">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-foreground">
            Show Completed
          </span>
          <Switch />
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-8 text-muted-foreground hover:bg-muted"
        >
          <MoreVertical className="size-4" />
          <span className="sr-only">More options</span>
        </Button>
      </div>

      {/* Add Item Input Field */}
      <div className="px-6 pb-4">
        <button className="flex w-full items-center gap-3 rounded-lg border border-border bg-background px-4 py-3 text-left transition-colors hover:bg-muted/50">
          <Plus className="size-4 text-blue-500 dark:text-blue-400" />
          <span className="text-sm font-medium text-blue-500 dark:text-blue-400">
            Add
          </span>
        </button>
      </div>

      {/* Scrollable Items List */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">
        <div className="flex flex-col gap-6">
          {LIST_ITEMS.map((item) => (
            <div key={item.id} className="flex items-start gap-4">
              <Checkbox
                id={`item-${item.id}`}
                className="mt-0.5 size-5 rounded-[4px] border-border/80 shadow-none data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
              />
              <div className="flex flex-col gap-0.5">
                <label
                  htmlFor={`item-${item.id}`}
                  className="text-sm font-medium leading-none text-foreground peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  {item.name}
                </label>
                <span className="text-xs text-muted-foreground">
                  {item.metadata}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
