import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("should render dashboard page", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h2")).toContainText("仪表盘");
  });

  test("sidebar should show navigation links", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".sidebar")).toBeVisible();
    await expect(page.locator("text=仪表盘")).toBeVisible();
    await expect(page.locator("text=上传")).toBeVisible();
    await expect(page.locator("text=任务列表")).toBeVisible();
  });

  test("should navigate to upload page", async ({ page }) => {
    await page.goto("/");
    await page.click("text=上传");
    await expect(page).toHaveURL(/\/upload/);
  });

  test("should navigate to jobs page", async ({ page }) => {
    await page.goto("/");
    await page.click("text=任务列表");
    await expect(page).toHaveURL(/\/jobs/);
  });

  test("should navigate to settings page", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.locator("h2")).toContainText("设置");
  });
});
