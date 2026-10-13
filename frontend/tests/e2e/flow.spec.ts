import { expect, test, type Page } from "@playwright/test";

// The full rep journey from the brief, run against the real API with the deterministic fake AI.
test.describe("rep workflow", () => {
  test.skip(({ viewport }) => (viewport?.width ?? 0) < 1024, "desktop journey");

  const row = (page: Page, name: string) => page.locator("[data-lead-id]", { hasText: name });

  test("triage, edit, send, undo, add a lead, log a chat, persist", async ({ page }) => {
    // 1. Overdue follow-ups are the first thing on screen.
    await page.goto("/");
    const overdueHeading = page.getByRole("heading", { name: /^Overdue \(\d+\)$/ });
    await expect(overdueHeading).toBeVisible();

    // 2. Open the most urgent overdue lead.
    const first = page.locator("[data-due=overdue]").first();
    const name = (await first.locator("span.font-semibold").first().textContent())?.trim() ?? "";
    await first.click();
    await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();

    // 3. Its reason and conversation are visible, with the draft as the next message.
    await expect(page.getByRole("heading", { name: /^Why (Hot|Warm|Cold)$/ })).toBeVisible();
    // The region exists for every lead; Excel-only leads show an empty state instead of messages.
    await expect(page.getByRole("region", { name: "Conversation" })).toBeVisible();

    // 4. Edit and save the draft.
    const box = page.getByRole("textbox", { name: "Next message" });
    await box.fill(`Hi, quick follow-up from the E2E run on our last conversation.`);
    await page.getByRole("button", { name: "Save draft" }).click();
    await expect(page.getByText("Edited by you")).toBeVisible();

    // 5. Mark as sent: the lead leaves Overdue immediately, even before AI finishes.
    await page.getByRole("button", { name: "Mark as sent" }).click();
    await expect(page.getByText(/Marked as sent to/)).toBeVisible();
    await expect(row(page, name)).not.toHaveAttribute("data-due", "overdue");

    // 6. Undo (kept in the composer bar, not only in the toast) brings it back.
    await page.getByRole("button", { name: "Undo marking as sent" }).click();
    await expect(row(page, name)).toHaveAttribute("data-due", "overdue");

    // 7. Send again for real.
    await page.getByRole("button", { name: "Mark as sent" }).click();
    await expect(row(page, name)).not.toHaveAttribute("data-due", "overdue");

    // 8. Add a new lead: it is analysed and due today (first touch).
    const leadName = `E2E Buyer ${Date.now() % 100000}`;
    await page.getByRole("button", { name: "Add lead" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Name").fill(leadName);
    await dialog.getByLabel("Company").fill("E2E Packaging Co");
    await dialog
      .getByRole("textbox", { name: "Phone" })
      .fill(`+91 98${String(Date.now()).slice(-8)}`);
    await dialog.getByRole("button", { name: "Add lead" }).click();
    await expect(page.getByRole("heading", { level: 2, name: leadName })).toBeVisible();
    await expect(row(page, leadName)).toHaveAttribute("data-due", "today");

    // 9. Log a chat with a quote request: the agent re-tags the lead Hot.
    await page.getByRole("button", { name: "Log chat" }).click();
    const logDialog = page.getByRole("dialog", { name: "Log chat" });
    await logDialog
      .getByRole("textbox", { name: "Message 1" })
      .fill("Please send a quotation, we want to order this month.");
    await logDialog.getByRole("button", { name: "Log chat" }).click();
    await expect(logDialog).toBeHidden();
    const header = page
      .locator("header")
      .filter({ has: page.getByRole("heading", { level: 2, name: leadName }) });
    await expect(header.getByText("Hot", { exact: true })).toBeVisible();
    await expect(page.getByText(/Tag changed: Warm → Hot/)).toBeVisible();

    // 10. Everything survives a reload.
    await page.reload();
    await expect(page.getByRole("heading", { level: 2, name: leadName })).toBeVisible();
    await expect(header.getByText("Hot", { exact: true })).toBeVisible();
    await expect(
      page
        .getByRole("list", { name: "Conversation" })
        .getByText("Please send a quotation, we want to order this month."),
    ).toBeVisible();
  });
});

test.describe("mobile", () => {
  test.skip(({ viewport }) => (viewport?.width ?? 0) >= 1024, "mobile journey");

  test("queue first, then a full-screen lead with a way back", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /^Overdue \(\d+\)$/ })).toBeVisible();
    await page.locator("[data-lead-id]").first().click();
    await expect(page.getByRole("button", { name: "Back to queue" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Next message" })).toBeVisible();
    await page.getByRole("button", { name: "Back to queue" }).click();
    await expect(page.getByRole("heading", { name: /^Overdue \(\d+\)$/ })).toBeVisible();
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(scrollWidth).toBeLessThanOrEqual(390);
  });
});
