"use client";

import { Plus, MoreVertical } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { PanelLayout } from "./panel-layout";

const LIST_ITEMS = [
  { id: 1, name: "Potatoes", metadata: "Added by you just now" },
  { id: 2, name: "Milk", metadata: "Added by you just now" },
  { id: 3, name: "Cheese", metadata: "Added by you just now" },
];

export function ShoppingListPanel() {
  return (
    <PanelLayout title="Shopping List" subtitle={`${LIST_ITEMS.length} items`}>
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
        </Button>
      </div>

      <div className="px-6 pb-4">
        <button className="flex w-full items-center gap-3 rounded-lg border border-border bg-background px-4 py-3 text-left transition-colors hover:bg-muted/50">
          <Plus className="size-4 text-blue-500 dark:text-blue-400" />
          <span className="text-sm font-medium text-blue-500 dark:text-blue-400">
            Add
          </span>
        </button>
      </div>

      <div className="flex flex-col gap-6 px-6 pb-6">
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
    </PanelLayout>
  );
}
