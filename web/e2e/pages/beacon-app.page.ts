import { expect, Locator, Page } from "@playwright/test";

export class BeaconAppPage {
  readonly page: Page;
  readonly smartHomeNavButton: Locator;
  readonly composerInput: Locator;

  constructor(page: Page) {
    this.page = page;
    this.smartHomeNavButton = page.locator('button[title="Smart Home"]');
    this.composerInput = page.getByRole("textbox", { name: "Message input" });
  }

  async gotoHome(): Promise<void> {
    await this.page.goto("/home", { waitUntil: "domcontentloaded" });
    await expect(this.smartHomeNavButton).toBeVisible();
  }

  async openSmartHomePanel(): Promise<void> {
    await this.smartHomeNavButton.click();
    await expect(
      this.page.getByRole("heading", { name: "Smart Home" }),
    ).toBeVisible();
  }

  async openCategory(
    category:
      | "Cameras"
      | "Lights"
      | "Locks & Doors"
      | "Blinds"
      | "Thermostats"
      | "Appliances"
      | "Sensors"
      | "Robots"
      | "Rover",
  ): Promise<void> {
    const card = this.page
      .locator('[data-slot="card"]')
      .filter({ hasText: category })
      .first();
    await card.click();
    await expect(
      this.page.getByRole("heading", { name: category }),
    ).toBeVisible();
  }

  async openLightDrawer(lightName: string): Promise<void> {
    const row = this.page.getByText(lightName, { exact: true }).first();
    await expect(row).toBeVisible();
    await row.click();
    await expect(
      this.page.getByRole("heading", { name: lightName }),
    ).toBeVisible();
  }

  async sendPromptToAgent(
    prompt: string,
    typewriterDelayMs = 28,
  ): Promise<void> {
    await this.composerInput.click();
    // Type smoothly so the keystrokes look natural and clear in the demo video
    await this.composerInput.pressSequentially(prompt, {
      delay: typewriterDelayMs,
    });
    await this.page.waitForTimeout(300);
    await this.composerInput.press("Enter");
  }

  async waitForLightStateInUI(
    lightName: string,
    expectedState: "On" | "Off",
    expectedBrightness?: number,
  ): Promise<void> {
    const expectedText =
      expectedBrightness !== undefined
        ? `${expectedState} • ${expectedBrightness}%`
        : expectedState;

    await expect(
      this.page
        .locator("div")
        .filter({ hasText: lightName })
        .filter({ hasText: expectedText })
        .first(),
    ).toBeVisible({ timeout: 35_000 });
  }
}
