import { test, expect } from "@playwright/test";
import fs from "fs";
import { BeaconAppPage } from "../pages/beacon-app.page";
import { WebotsDemoController } from "../utils/webots-demo-controller";
import { MediaArtifactManager } from "../utils/media-artifact-manager";

test.describe("Beacon Capability Demo: Smart Light Control & Rover Tracking", () => {
  test("controls Living Room Main Light via Agent prompt with synchronized Webots camera focus, screenshots & video recordings", async ({
    page,
    request,
  }, testInfo) => {
    const app = new BeaconAppPage(page);
    const webots = new WebotsDemoController(request);
    const media = new MediaArtifactManager("light_control_demo");
    await media.init();

    // 1. Initialize Webots state: sunset sky + Living Room Main Light OFF so turning it ON is dramatic
    await webots.setEnvironment("sunset");
    await webots.setLightStateDirect("Living Room Main Light", {
      power_state: "off",
      brightness: 0,
    });

    // 2. Focus Webots 3D Viewpoint camera directly on the Living Room Main Light
    await webots.focusCamera({
      mode: "focus",
      target_type: "light",
      target_name: "Living Room Main Light",
      duration: 1.2,
    });

    // 3. Start Webots 1080p MP4 recording of the 3D scene
    const webotsVideoPath = await webots.startWebotsRecording(
      "light_control",
      "webots_light_control_demo.mp4",
    );

    try {
      // 4. Open Beacon Web UI and navigate to Smart Home -> Lights panel
      await app.gotoHome();
      await app.openSmartHomePanel();
      await app.openCategory("Lights");

      await app.waitForLightStateInUI("Living Room Main Light", "Off");
      await media.captureScreenshot(page, "01_initial_light_off_state");

      // 5. Type and send the prompt to the Beacon Agent
      const prompt =
        "Turn on the Living Room Main Light, set its brightness to 100%, and set its color to warm white.";
      await app.sendPromptToAgent(prompt);
      await media.captureScreenshot(page, "02_prompt_sent_to_agent");

      // 6. Wait for the Agent's MCP tool call to actuate Webots & reflect in the UI
      await app.waitForLightStateInUI("Living Room Main Light", "On", 100);
      await page.waitForTimeout(1500);
      await media.captureScreenshot(page, "03_agent_controlled_light_on");

      // 7. Open the Light Drawer to showcase the updated brightness (100%) and color swatch
      await app.openLightDrawer("Living Room Main Light");
      await page.waitForTimeout(1500);
      await media.captureScreenshot(page, "04_light_drawer_verified");

      // 8. Verify ground-truth state from the Webots Smart Home Hub API
      const lightState = await webots.getLightState("Living Room Main Light");
      expect(lightState.state).toBe("On");
      expect(lightState.brightness).toBe(100);
    } finally {
      // 9. Stop Webots 3D MP4 recording and finalize Playwright Frontend screen recording
      const recResult = await webots.stopWebotsRecording();
      expect(recResult.video_path).toBe(webotsVideoPath);
      expect(fs.existsSync(webotsVideoPath)).toBeTruthy();

      const frontendVideoPath = await media.finalizeFrontendVideo(page, testInfo);
      if (!frontendVideoPath) {
        throw new Error("Frontend video was not saved");
      }
      expect(fs.existsSync(frontendVideoPath)).toBeTruthy();
    }
  });

  test("dispatches Autonomous Rover via Agent prompt while Webots camera follows the robot", async ({
    page,
    request,
  }, testInfo) => {
    const app = new BeaconAppPage(page);
    const webots = new WebotsDemoController(request);
    const media = new MediaArtifactManager("rover_control_demo");
    await media.init();

    // 1. Set Webots camera to follow BEACON_ROVER continuously
    await webots.setEnvironment("day");
    await webots.focusCamera({
      mode: "follow_rover",
      offset: [-2.2, -2.2, 2.5],
      duration: 1.0,
    });

    // 2. Start Webots 1080p MP4 recording
    const webotsVideoPath = await webots.startWebotsRecording(
      "rover_control",
      "webots_rover_follow_demo.mp4",
    );

    try {
      await app.gotoHome();
      await app.openSmartHomePanel();
      await media.captureScreenshot(page, "01_rover_docked_initial");

      // 3. Send prompt to Beacon Agent to navigate the rover to the Living Room
      await app.sendPromptToAgent(
        "Send the autonomous rover to the living room and raise its arm to inspect_high.",
      );
      await media.captureScreenshot(page, "02_rover_command_submitted");

      // 4. Record for 8 seconds while the rover drives and the Webots camera tracks it
      await page.waitForTimeout(8000);
      await media.captureScreenshot(page, "03_rover_navigating_estate");
    } finally {
      const recResult = await webots.stopWebotsRecording();
      expect(fs.existsSync(recResult.video_path)).toBeTruthy();

      const frontendVideoPath = await media.finalizeFrontendVideo(
        page,
        testInfo,
      );
      expect(frontendVideoPath).not.toBeNull();
    }
  });
});
