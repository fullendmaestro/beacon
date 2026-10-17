import fs from "fs/promises";
import path from "path";
import { Page, TestInfo } from "@playwright/test";

export class MediaArtifactManager {
  private readonly screenshotsDir: string;
  private readonly frontendVideosDir: string;

  constructor(private readonly scenarioName: string) {
    const root = path.resolve(__dirname, "../../../artifacts");
    this.screenshotsDir = path.join(root, "screenshots", scenarioName);
    this.frontendVideosDir = path.join(root, "videos", "frontend");
  }

  async init(): Promise<void> {
    await fs.mkdir(this.screenshotsDir, { recursive: true });
    await fs.mkdir(this.frontendVideosDir, { recursive: true });
  }

  async captureScreenshot(page: Page, stepLabel: string): Promise<string> {
    const filePath = path.join(this.screenshotsDir, `${stepLabel}.png`);
    await page.screenshot({
      path: filePath,
      fullPage: false,
      animations: "allow",
    });
    return filePath;
  }

  async finalizeFrontendVideo(
    page: Page,
    testInfo: TestInfo,
  ): Promise<string | null> {
    const video = page.video();
    if (!video) return null;

    // Close the page so Playwright flushes the WebM video stream to disk
    await page.close();

    const targetVideoPath = path.join(
      this.frontendVideosDir,
      `frontend_${this.scenarioName}.webm`,
    );
    await video.saveAs(targetVideoPath);

    await testInfo.attach(`frontend_${this.scenarioName}.webm`, {
      path: targetVideoPath,
      contentType: "video/webm",
    });

    return targetVideoPath;
  }
}
