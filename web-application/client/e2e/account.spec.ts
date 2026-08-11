import { test, expect } from "@playwright/test";

const EMAIL = `e2e_acc_${Date.now()}@elyssa.local`;
const PASSWORD = "Qa1234567!";
const DISPLAY_NAME = "Audit User";

test.describe("Account settings", () => {
  test("E2E-001: display name persists across reload", async ({ page }) => {
    // Register a fresh account
    await page.goto("/auth/register");
    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Display name").fill(DISPLAY_NAME);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Register" }).click();
    await expect(page).toHaveURL("/", { timeout: 15000 });

    // Navigate to Account page
    await page.goto("/account");
    await expect(page.getByRole("heading", { name: "Account" })).toBeVisible();

    // The form should show the registered display name
    const nameInput = page.getByLabel("Display name");
    await expect(nameInput).toHaveValue(DISPLAY_NAME);

    // Rename
    await nameInput.fill("Audit Renamed");
    await page.getByRole("button", { name: "Save" }).click();
    await expect(page.getByText("Profile updated")).toBeVisible();

    // Persistence gate: reload and check
    await page.reload();
    await expect(page.getByLabel("Display name")).toHaveValue("Audit Renamed");

    // Header shows the new name, not the email
    await expect(page.locator("header")).toContainText("Audit Renamed");
    await expect(page.locator("header")).not.toContainText(EMAIL);
  });
});
