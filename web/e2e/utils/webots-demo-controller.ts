import { APIRequestContext, expect } from "@playwright/test";

const HUB_BASE_URL =
  process.env.NEXT_PUBLIC_SMART_HOME_API_URL || "http://127.0.0.1:8000";

export interface FocusOptions {
  mode?: "focus" | "follow_rover";
  preset?: string;
  target_type?: "light" | "door" | "blind" | "rover";
  target_name?: string;
  offset?: [number, number, number];
  duration?: number;
}

export class WebotsDemoController {
  constructor(private readonly request: APIRequestContext) {}

  async setEnvironment(timeOfDay: "day" | "sunset" | "night"): Promise<void> {
    const res = await this.request.post(
      `${HUB_BASE_URL}/api/home/environment`,
      {
        data: { time_of_day: timeOfDay },
      },
    );
    expect(res.ok()).toBeTruthy();
  }

  async setLightStateDirect(
    lightName: string,
    state: { power_state: "on" | "off"; brightness?: number; color?: string },
  ): Promise<void> {
    const lightsRes = await this.request.get(`${HUB_BASE_URL}/api/lights`);
    expect(lightsRes.ok()).toBeTruthy();
    const lights = (await lightsRes.json()) as Array<{
      id: number;
      name: string;
    }>;
    const target = lights.find((l) =>
      l.name.toLowerCase().includes(lightName.toLowerCase()),
    );
    if (!target) {
      throw new Error(`Light "${lightName}" not found in Webots hub`);
    }
    const updateRes = await this.request.post(
      `${HUB_BASE_URL}/api/lights/${target.id}/state`,
      { data: state },
    );
    expect(updateRes.ok()).toBeTruthy();
  }

  async getLightState(lightName: string): Promise<{
    id: number;
    name: string;
    state: "On" | "Off";
    brightness: number;
    color: string;
  }> {
    const res = await this.request.get(`${HUB_BASE_URL}/api/lights`);
    expect(res.ok()).toBeTruthy();
    const lights = await res.json();
    const found = lights.find((l: { name: string }) =>
      l.name.toLowerCase().includes(lightName.toLowerCase()),
    );
    if (!found) {
      throw new Error(`Light "${lightName}" not found`);
    }
    return found;
  }

  async focusCamera(options: FocusOptions): Promise<void> {
    const duration = options.duration ?? 1.2;
    const res = await this.request.post(
      `${HUB_BASE_URL}/api/demo/camera/focus`,
      {
        data: {
          ...options,
          duration,
        },
      },
    );
    expect(res.ok()).toBeTruthy();
    // Wait for the smooth Viewpoint camera interpolation to settle
    await new Promise((r) => setTimeout(r, (duration + 0.3) * 1000));
  }

  async startWebotsRecording(
    label: string,
    filename?: string,
  ): Promise<string> {
    const res = await this.request.post(
      `${HUB_BASE_URL}/api/demo/recording/start`,
      {
        data: {
          label,
          filename,
          width: 1920,
          height: 1080,
          quality: 95,
          acceleration: 1,
        },
      },
    );
    expect(res.ok()).toBeTruthy();
    const body = await res.json();
    return body.video_path as string;
  }

  async stopWebotsRecording(): Promise<{
    video_path: string;
    duration_seconds: number;
  }> {
    const res = await this.request.post(
      `${HUB_BASE_URL}/api/demo/recording/stop`,
    );
    expect(res.ok()).toBeTruthy();
    const stopData = await res.json();

    // Poll until Webots finishes encoding the MP4 file
    for (let i = 0; i < 30; i++) {
      const statusRes = await this.request.get(
        `${HUB_BASE_URL}/api/demo/status`,
      );
      const status = await statusRes.json();
      if (status.movie_ready) break;
      await new Promise((r) => setTimeout(r, 400));
    }

    return stopData;
  }
}
