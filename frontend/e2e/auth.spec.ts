import { expect, test } from "@playwright/test";

test("public auth surfaces are accessible", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Welcome back" })).toBeVisible();
  await page.getByRole("link", { name: "Create an account" }).click();
  await expect(page.getByRole("heading", { name: "Join your community" })).toBeVisible();
});

test("development role credentials are shown on the login page", async ({ page }) => {
  await page.goto("/login");
  const credentials = page.getByRole("complementary", { name: "Development login accounts" });
  await expect(credentials).toContainText("admin@demo.civicgrid.dev");
  await expect(credentials).toContainText("CivicGridCitizen@2026!");
});

test("unauthenticated users are redirected from a protected page", async ({ page }) => {
  await page.goto("/admin");
  await expect(page).toHaveURL(/\/login\?next=/);
});

for (const width of [320, 375, 430, 768, 1024, 1280, 1440]) {
  test("public shell has no horizontal overflow at " + width + "px", async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/");
    const dimensions = await page.evaluate(() => ({
      body: document.body.scrollWidth,
      viewport: window.innerWidth,
    }));
    expect(dimensions.body).toBeLessThanOrEqual(dimensions.viewport);
    await page.goto("/login");
    const authDimensions = await page.evaluate(() => ({
      body: document.body.scrollWidth,
      viewport: window.innerWidth,
    }));
    expect(authDimensions.body).toBeLessThanOrEqual(authDimensions.viewport);
  });
}

test.describe("credentialed JWT flows", () => {
  test.skip(!process.env.E2E_CITIZEN_EMAIL || !process.env.E2E_CITIZEN_PASSWORD, "Set E2E_CITIZEN_EMAIL and E2E_CITIZEN_PASSWORD");
  test("citizen login and role denial", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email address").fill(process.env.E2E_CITIZEN_EMAIL!);
    await page.getByLabel("Password", { exact: true }).fill(process.env.E2E_CITIZEN_PASSWORD!);
    await page.getByRole("button", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/citizen/);
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/citizen/);
  });
});
