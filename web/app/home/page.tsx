import { Assistant } from "@/components/assistant";
import { Sidebar } from "@/components/layout/sidebar";
import { RightPanelDrawer } from "@/components/layout/right-panel-drawer";

export default function HomePage() {
  return (
    <div className="flex h-svh w-full items-center p-4 lg:p-6 bg-background overflow-hidden">
      {/* Floating Left Navigation Pill */}
      <div className="z-10 flex h-full items-center shrink-0 pr-4 lg:pr-6">
        <Sidebar />
      </div>

      {/* Main Chat Interface */}
      <main className="flex min-w-0 flex-1 flex-col h-full relative z-0">
        <Assistant />
      </main>

      {/* Side-by-Side Context Panel */}
      <RightPanelDrawer />
    </div>
  );
}
