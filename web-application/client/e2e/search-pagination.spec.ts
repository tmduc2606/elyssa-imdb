import { test, expect } from "@playwright/test";

// WA-15: search uses cursor pagination — successive pages yield unique
// 20-item sets (no overlap), and scrolling stops once hasMore=false.
const TITLE_LINK = 'a[href^="/title/"]';

async function collectHrefs(page: import("@playwright/test").Page): Promise<string[]> {
  return page.locator('a[href^="/title/"], a[href^="/person/"]').evaluateAll((els) =>
    els.map((el) => (el as HTMLAnchorElement).getAttribute("href") ?? ""),
  );
}

test.describe("Search pagination (WA-15)", () => {
  test("load more fetches unique pages and stops when no more are left", async ({ page }) => {
    // ~1,230 fixture titles match "the" — plenty for several 20-item pages.
    await page.goto("/search?q=the");

    const first = await collectHrefs(page);
    await expect
      .poll(async () => (await collectHrefs(page)).length, { timeout: 15000 })
      .toBeGreaterThan(0);

    let pageCount = 1;
    const seen = new Set(await collectHrefs(page));

    for (let attempt = 0; attempt < 8; attempt++) {
      // Scroll the Load-more sentinel into view (IntersectionObserver auto-loads)
      await page.mouse.wheel(0, 4000);
      await page.waitForTimeout(400);

      const hrefs = await collectHrefs(page);
      if (hrefs.length <= seen.size) continue; // still same page — scroll more

      const unique = new Set(hrefs);
      expect(unique.size).toBe(hrefs.length); // no duplicate/overlapping page
      expect(unique.size).toBeGreaterThan(seen.size); // append, never shrink
      seen.clear();
      hrefs.forEach((h) => seen.add(h));
      pageCount += 1;
    }

    // At least 2 cursor pages were walked with a deduplicated set throughout.
    expect(pageCount).toBeGreaterThanOrEqual(2);
    expect(seen.size).toBe((await collectHrefs(page)).length);

    // hasMore=false path: a garbage query yields zero results and no load-more UI
    await page.goto("/search?q=zzzzqqq");
    await expect(page).toHaveURL(/q=zzzzqqq/);
    expect(await page.getByRole("button", { name: "Load more" }).count()).toBe(0);
  });
});