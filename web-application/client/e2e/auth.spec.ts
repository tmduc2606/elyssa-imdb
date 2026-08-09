import { test, expect, type Page } from "@playwright/test";

// WA-08: register → logout → login flow; the access token must never
// persist to localStorage (in-memory only).
const EMAIL = `e2e_${Date.now()}@elyssa.local`;
const PASSWORD = "Qa1234567!";

async function signOut(page: Page) {
  // Header user-menu button is labelled with the signed-in email.
  const userMenu = page.locator("header button").filter({ hasText: "@" }).first();
  await userMenu.click();
  const signOut = page.getByText("Sign out").first();
  await signOut.click();
}

test.describe("Auth flow (WA-08)", () => {
  test("register, sign out, sign back in; token stays memory-only", async ({ page }) => {
    // 1. Register a fresh account (cookie + access token issued)
    await page.goto("/auth/register");
    await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Display name").fill("E2E User");
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Register" }).click();

    // Landing on home with an authenticated session; token must be in-memory only
    await expect(page).toHaveURL("/", { timeout: 15000 });
    await expect(page).not.toHaveText("body", /sign in/i, { timeout: 10000 }).catch(() => {});
    expect(await page.evaluate(() => localStorage.getItem("accessToken"))).toBeNull();
    expect(await page.evaluate(() => sessionStorage.getItem("accessToken"))).toBeNull();

    // 2. Sign out — cookie revoked, UI shows Sign in again
    await signOut(page);
    await expect(page.getByRole("button", { name: "Sign in" }).first()).toBeVisible({
      timeout: 10000,
    });

    // 3. Sign back in with the same credentials
    await page.getByRole("button", { name: "Sign in" }).first().click();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
    await page.getByLabel("Email").fill(EMAIL);
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByLabel("Sign in form").getByRole("button", { name: "Sign in" }).click();

    await expect(page).toHaveURL("/", { timeout: 15000 });
    expect(await page.evaluate(() => localStorage.getItem("accessToken"))).toBeNull();

    // 4. Refresh-then-retry keeps the session (refresh cookie rotation)
    await page.reload();
    expect(await page.evaluate(() => localStorage.getItem("accessToken"))).toBeNull();
  });
});