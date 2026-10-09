import { Assistant } from "@/components/assistant";
import { Sidebar } from "@/components/layout/sidebar";
import { RightPanelDrawer } from "@/components/layout/right-panel-drawer";
import { Thread } from "@/components/assistant-ui/elements/thread.aui";

export default function HomePage() {
  return (
    <Assistant>
      <div className="flex h-svh w-full items-center overflow-hidden bg-background p-4 lg:p-6">
        {/* Floating Left Navigation Pill */}
        <div className="z-10 flex h-full shrink-0 items-center pr-4 lg:pr-6">
          <Sidebar />
        </div>

        {/* Main Chat Interface */}
        <main className="relative z-0 flex h-full min-w-0 flex-1 flex-col [&_[data-aui-scroller]]:no-scrollbar [&_[data-radix-scroll-area-viewport]]:no-scrollbar">
          <div className="h-full w-full overflow-hidden">
            <Thread />
          </div>
        </main>

        {/* Side-by-Side Context Panel */}
        <RightPanelDrawer />
      </div>
    </Assistant>
  );
}
