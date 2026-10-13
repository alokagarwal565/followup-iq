import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function seriousViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.help} (${v.nodes.length} nodes)`);
}

test("dashboard and an open lead have no serious accessibility violations", async ({ page }) => {
  await page.goto("/");
  await page.locator("[data-lead-id]").first().click();
  await expect(page.getByRole("textbox", { name: "Next message" })).toBeVisible();
  expect(await seriousViolations(page)).toEqual([]);
});

test("the add lead dialog has no serious accessibility violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("[data-lead-id]").first()).toBeVisible();
  await page.getByRole("button", { name: "Add lead" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(await seriousViolations(page)).toEqual([]);
});

test("security headers are sent", async ({ request }) => {
  const response = await request.get("/");
  const headers = response.headers();
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["content-security-policy"]).toContain("connect-src 'self' http://localhost:8001");
  expect(headers["x-powered-by"]).toBeUndefined();
});

test("on desktop Esc returns focus to the queue and keeps the lead open", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "phones use Esc to go back to the queue");
  await page.goto("/");
  const row = page.locator("[data-lead-id]").nth(1);
  await row.click();
  const draft = page.getByRole("textbox", { name: "Next message" });
  await expect(draft).toBeVisible();
  await page.locator("body").press("Escape");
  await expect(row).toBeFocused();
  await expect(draft).toBeVisible();
});

test.describe("short window (laptop at 150% zoom)", () => {
  test.use({ viewport: { width: 1280, height: 607 } });

  test("the page never scrolls and the draft stays reachable above the actions", async ({
    page,
  }) => {
    await page.goto("/");
    await page.locator("[data-lead-id]").first().click();
    const draft = page.getByRole("textbox", { name: "Next message" });
    const send = page.getByRole("button", { name: "Mark as sent" });
    await expect(send).toBeInViewport();
    expect(
      await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight),
    ).toBe(true);
    await draft.scrollIntoViewIfNeeded();
    await expect(draft).toBeInViewport();
    await expect(send).toBeInViewport();
  });
});

test.describe("dark appearance", () => {
  // Dark mode follows the system setting, so it is checked on the real rendering, not only by
  // the token script.
  test.use({ colorScheme: "dark" });

  test("has no serious accessibility violations with a lead open", async ({ page }) => {
    await page.goto("/");
    await page.locator("[data-lead-id]").first().click();
    await expect(page.getByRole("textbox", { name: "Next message" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
  });
});
