import { Flame, Lock, Moon } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function FeaturesSection() {
  return (
    <div
      className="container-wrapper flex-1 section-soft md:py-12"
      id="capabilities"
    >
      <div className="container flex flex-col gap-12 px-6 py-8 md:gap-20">
        <div className="flex flex-col gap-4 text-center items-center">
          <h2 className="text-2xl font-bold tracking-tight md:text-3xl">
            Core Systems
          </h2>
          <p className="text-muted-foreground max-w-[85%] md:max-w-2xl">
            Beacon uses multi-agent coordination frameworks to process distinct
            household events autonomously across three main pillars.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-col gap-2">
              <div className="flex size-12 items-center justify-center rounded-lg bg-red-500/10">
                <Flame className="size-6 text-red-500" />
              </div>
              <CardTitle>Emergency Guidance</CardTitle>
              <CardDescription>
                Dynamic egress routing & first responder handoff.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Instantly map the safest exit routes and hijack connected displays
              to broadcast evacuation instructions during high-stress
              situations. Automatically transmit hazard data to emergency
              services.
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-col gap-2">
              <div className="flex size-12 items-center justify-center rounded-lg bg-emerald-500/10">
                <Lock className="size-6 text-emerald-500" />
              </div>
              <CardTitle>Perimeter Defense</CardTitle>
              <CardDescription>
                Predictive deterrence & geofenced lockdown.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Simulate occupancy when unusual perimeter activity is detected by
              integrated Ring cameras[cite: 11]. Secure deadbolts, arm systems,
              and drop power to fire-hazards upon resident departure.
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-col gap-2">
              <div className="flex size-12 items-center justify-center rounded-lg bg-blue-500/10">
                <Moon className="size-6 text-blue-500" />
              </div>
              <CardTitle>Resident Assistance</CardTitle>
              <CardDescription>
                Rhythmic environment adaptation.
              </CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              Seamlessly transition lighting color temperatures based on the
              time of day. Utilize presence sensors to continuously hand off
              podcasts or news briefings to the nearest active speaker as you
              move.
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
