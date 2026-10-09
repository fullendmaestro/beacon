import { Assistant } from "@/components/assistant";

export default function HomePage() {
  return (
    <div className="flex h-svh flex-col bg-background">
      <main className="flex min-h-0 flex-1 flex-col">
        <Assistant />
      </main>
    </div>
  );
}
