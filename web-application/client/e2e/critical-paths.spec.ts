import { test, expect } from "@playwright/test";

test.describe("Critical Paths", () => {
  test("1. Homepage loads and displays header with navigation", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: "Elyssa" })).toBeVisible();
    // Scope to the header — the footer also links to Browse/Top Rated.
    const header = page.locator("header");
    await expect(header.getByRole("link", { name: "Browse" }).first()).toBeVisible();
    await expect(header.getByRole("link", { name: "Top Rated" }).first()).toBeVisible();
    await expect(page.getByRole("search")).toBeVisible();
  });

  test("2. Search flow: user can search and see results", async ({ page }) => {
    await page.goto("/");
    const searchInput = page.getByPlaceholder("Search titles, people...");
    await searchInput.fill("Inception");
    await searchInput.press("Enter");
    await expect(page).toHaveURL(/\/search\?q=Inception/);
    await expect(page.getByText("Inception")).toBeVisible();
  });

  test("3. Browse page loads with genre filters", async ({ page }) => {
    await page.goto("/browse");
    await expect(page.getByRole("heading", { name: /browse/i })).toBeVisible();
    // Multiple FilterBar groups share the same label — assert any one.
    await expect(page.getByRole("group", { name: "Filters" }).first()).toBeVisible();
  });

  test("4. Auth flow: registration page has form elements", async ({ page }) => {
    await page.goto("/auth/register");
    await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible();
    await expect(page.getByRole("form", { name: "Registration form" })).toBeVisible();
    await expect(page.getByLabel("Email")).toBeVisible();
    await expect(page.getByLabel("Password")).toBeVisible();
  });

  test("5. 404 page shows on unknown route", async ({ page }) => {
    await page.goto("/this-does-not-exist");
    await expect(page.getByText("404")).toBeVisible();
    await expect(page.getByText("Page not found")).toBeVisible();
    await expect(page.getByRole("link", { name: "Go home" })).toBeVisible();
  });
});
