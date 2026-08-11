import { test, expect } from "@playwright/test";

const EMAIL = `e2e_wl_${Date.now()}@elyssa.local`;
const PASSWORD = "Qa1234567!";

test.describe("Watchlist mechanism", () => {
  test.beforeAll(async ({ browser }) => {
    // Register a shared user for watchlist tests
    const page = await browser.newPage();
    await page.goto("/auth/register");
    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Display name").fill("Watchlist Tester");
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Register" }).click();
    await expect(page).toHaveURL("/", { timeout: 15000 });
    await page.close();
  });

  test("E2E-002: add to watchlist, verify card, interact with notes", async ({ page }) => {
    // Navigate to Interstellar detail
    await page.goto("/title/tt0816692");
    await expect(page.getByRole("heading", { name: /interstellar/i })).toBeVisible();

    // Click the watchlist button
    const wlBtn = page.getByRole("button", { name: /watchlist/i }).first();
    await wlBtn.click();

    // Navigate to watchlist page
    await page.goto("/watchlist");
    await expect(page.getByRole("heading", { name: /watchlist/i })).toBeVisible();

    // Interstellar card should appear
    const card = page.getByText("Interstellar").first();
    await expect(card).toBeVisible();

    // "Add notes" button should be present and interactable
    const noteBtn = page.getByRole("button", { name: /add notes/i }).first();
    await expect(noteBtn).toBeVisible();
    await expect(noteBtn).toBeEnabled();

    // Click to open notes, type, blur to save
    await noteBtn.click();
    const textarea = page.getByPlaceholder(/private note/i).first();
    await textarea.fill("**Favourite**");
    await textarea.blur();

    // Persistence gate: reload
    await page.reload();
    await expect(page.getByRole("button", { name: /edit notes/i }).first()).toBeVisible();
  });
});
