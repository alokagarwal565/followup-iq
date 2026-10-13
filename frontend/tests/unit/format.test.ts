import { describe, expect, it } from "vitest";
import {
  addDays,
  daysBetween,
  dueLabel,
  formatDateOnly,
  formatDateTime,
  lastContactLabel,
  plural,
} from "@/lib/format";

const TZ = "Asia/Kolkata";

describe("date-only values", () => {
  it("formats a calendar day without shifting it, whatever the browser timezone", () => {
    // The suite runs with TZ=America/Los_Angeles (see vitest config), where naive parsing shifts a day.
    expect(formatDateOnly("2026-10-12")).toBe("Mon, 12 Oct");
  });

  it("adds days across month and year boundaries", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-10-12", -12)).toBe("2026-09-30");
  });

  it("counts whole days between calendar days", () => {
    expect(daysBetween("2026-10-09", "2026-10-12")).toBe(3);
    expect(daysBetween("2026-10-12", "2026-10-12")).toBe(0);
  });
});

describe("due labels", () => {
  const today = "2026-10-12";
  it("uses the server-computed overdue count", () => {
    expect(
      dueLabel({ due_state: "overdue", days_overdue: 3, next_follow_up_date: "2026-10-09" }, today),
    ).toBe("3d overdue");
  });
  it("names today and tomorrow, and dates further out", () => {
    expect(
      dueLabel({ due_state: "today", days_overdue: 0, next_follow_up_date: today }, today),
    ).toBe("Today");
    expect(
      dueLabel(
        { due_state: "upcoming", days_overdue: 0, next_follow_up_date: "2026-10-13" },
        today,
      ),
    ).toBe("Tomorrow");
    expect(
      dueLabel(
        { due_state: "upcoming", days_overdue: 0, next_follow_up_date: "2026-10-15" },
        today,
      ),
    ).toBe("Thu, 15 Oct");
  });
  it("says when there is no follow-up", () => {
    expect(dueLabel({ due_state: "none", days_overdue: 0, next_follow_up_date: null }, today)).toBe(
      "No follow-up",
    );
  });
});

describe("timestamps", () => {
  it("shows business-timezone time", () => {
    // 10:35 UTC is 16:05 in India.
    expect(formatDateTime("2026-10-12T10:35:00Z", TZ)).toBe("12 Oct, 4:05 pm");
  });

  it("describes last contact relative to the business day", () => {
    expect(lastContactLabel(null, "2026-10-12", TZ)).toBe("Never contacted");
    expect(lastContactLabel("2026-10-12T04:00:00Z", "2026-10-12", TZ)).toBe("Last contact today");
    expect(lastContactLabel("2026-10-11T04:00:00Z", "2026-10-12", TZ)).toBe(
      "Last contact yesterday",
    );
    // 20:00 UTC on the 7th is already the 8th in India: 4 days before the 12th.
    expect(lastContactLabel("2026-10-07T20:00:00Z", "2026-10-12", TZ)).toBe("Last contact 4d ago");
  });
});

describe("plural", () => {
  it("pluralises simple nouns", () => {
    expect(plural(1, "lead")).toBe("1 lead");
    expect(plural(3, "lead")).toBe("3 leads");
  });
});
