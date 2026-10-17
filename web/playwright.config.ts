import { defineConfig, devices } from "@playwright/test";
import path from "path";

export const ARTIFACTS_ROOT = path.resolve(process.cwd(), "../artifacts");

export default defineConfig({
  testDir: "./e2e/specs",
  testMatch: "**/*.spec.ts",
  timeout: 120_000,
  expect: {
    timeout: 30_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: [
    ["list"],
    [
      "html",
      {
        outputFolder: path.join(ARTIFACTS_ROOT, "playwright-report"),
        open: "never",
      },
    ],
  ],
  outputDir: path.join(ARTIFACTS_ROOT, "test-results"),
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000",
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    colorScheme: "dark",
    video: {
      mode: "on",
      size: { width: 1920, height: 1080 },
    },
    screenshot: "on",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium-demo",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1920, height: 1080 },
      },
    },
  ],
});