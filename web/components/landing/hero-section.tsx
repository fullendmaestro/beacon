import Link from "next/link";
import { Activity } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function HeroSection() {
  return (
    <section className="border-grid">
      <div className="container-wrapper">
        <div className="container flex flex-col items-center gap-2 px-6 py-8 text-center md:py-16 lg:py-20 xl:gap-4">
          <div className="flex justify-center mb-6">
            <Badge
              variant="secondary"
              className="rounded-full px-4 py-1.5 text-sm"
            >
              <Activity
                className="size-4 mr-2 inline-block"
                data-icon="inline-start"
              />
              Ring Camera Integration Live
            </Badge>
          </div>

          <h1 className="leading-tighter max-w-3xl text-3xl font-semibold tracking-tight text-balance text-primary lg:leading-[1.1] lg:font-semibold xl:text-5xl xl:tracking-tighter">
            Smart Home Assistant
          </h1>

          <p className="max-w-4xl text-base text-balance text-foreground sm:text-lg">
            Beacon dynamically orchestrates your home's IoT ecosystem to guide,
            protect, and assist its residents. An event-driven assistant built
            for modern, autonomous living.
          </p>

          <div className="flex w-full items-center justify-center gap-2 pt-2 **:data-[slot=button]:shadow-none">
            <Button size="sm" render={<Link href="/dashboard" />}>
              Open Command Center
            </Button>
            <Button
              variant="ghost"
              size="sm"
              render={<a href="#capabilities" />}
            >
              Explore Capabilities
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}
