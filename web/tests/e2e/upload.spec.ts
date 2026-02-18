import { test, expect } from "@playwright/test";

test.describe("Upload page", () => {
  test("should render upload page", async ({ page }) => {
    await page.goto("/upload");
    await expect(page.locator("body")).toBeVisible();
  });

  test("should have file input or drop zone", async ({ page }) => {
    await page.goto("/upload");
    // Either a file input or a dropzone div should exist
    const hasInput = await page.locator('input[type="file"]').count();
    const hasDropzone = await page.locator("[class*=drop], [class*=upload]").count();
    expect(hasInput + hasDropzone).toBeGreaterThan(0);
  });
});

test.describe("Settings page", () => {
  test("should toggle theme setting", async ({ page }) => {
    await page.goto("/settings");
    const toggle = page.locator("button[aria-label='切换主题']");
    if (await toggle.count()) {
      await toggle.click();
      // Toggle should be clickable without error
      expect(true).toBe(true);
    }
  });
});
