import { test, expect } from "@playwright/test";

// WA-17: the title-detail page renders a "Directors" crew section that is
// distinct from the cast list. The Matrix (tt0133093) is in the CI fixtures.
test.describe("Title crew display (WA-17)", () => {
  test("directors and writers render alongside cast", async ({ page }) => {
    await page.goto("/title/tt0133093");

    const directors = page.getByText("Directors", { exact: true });
    await expect(directors).toBeVisible({ timeout: 15000 });

    // Directors section contains the two Wachowskis (fixture crew data)
    await expect(page.locator("body")).toContainText("Lana Wachowski");
    await expect(page.locator("body")).toContainText("Lilly Wachowski");
    await expect(page.getByText("Writers", { exact: true })).toBeVisible();
  });
});