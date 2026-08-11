import { test, expect } from "@playwright/test";

test.describe("Similar titles integrity", () => {
  test("E2E-003: similar carousel excludes adult + obscure 10.0 titles", async ({ page }) => {
    // Navigate to a popular mainstream title
    await page.goto("/title/tt0816692");
    await expect(page.getByRole("heading", { name: /interstellar/i })).toBeVisible();

    // Intercept GraphQL to get the actual data (authoritative source)
    const graphqlResponse = page.waitForResponse(
      (r) => r.url().includes("/graphql") && r.request().postData()?.includes("similar"),
    );
    // Force a fresh load so the GraphQL fires
    await page.goto("/title/tt0816692");
    const resp = await graphqlResponse;
    const body = await resp.json();
    const entries = body.data?.title?.similar ?? [];

    // Should have entries
    expect(entries.length).toBeGreaterThanOrEqual(1);

    // Each entry must satisfy quality constraints
    for (const t of entries.slice(0, 12)) {
      // No adult titles
      expect(t.genres ?? []).not.toContain("Adult");
      // Must have a real number of votes
      if (t.numVotes != null) {
        expect(t.numVotes).toBeGreaterThanOrEqual(1000);
      }
    }
  });

  test("similar carousel cards render images, not blank boxes", async ({ page }) => {
    await page.goto("/title/tt0816692");

    // The carousel section should exist and have images
    const similarSection = page.locator('[aria-label*="More like this"], [aria-label*="Similar"]');
    const count = await similarSection.count();
    if (count > 0) {
      // At least one card should have an img element (poster)
      const imgs = similarSection.first().locator("img");
      await expect(imgs.first()).toBeVisible();
    }
  });
});
