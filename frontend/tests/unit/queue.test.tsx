import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FilterBar } from "@/components/queue/filter-bar";
import { QueuePanel } from "@/components/queue/queue-panel";
import { TagBadge } from "@/components/tag-badge";
import { TODAY, TZ, row, summary } from "./fixtures";

const ITEMS = [
  row({ id: "a", name: "Overdue Lead", due_state: "overdue", days_overdue: 3 }),
  row({
    id: "b",
    name: "Today Lead",
    due_state: "today",
    days_overdue: 0,
    next_follow_up_date: TODAY,
  }),
  row({
    id: "c",
    name: "Tomorrow Lead",
    due_state: "upcoming",
    days_overdue: 0,
    next_follow_up_date: "2026-10-13",
    classification: "Warm",
  }),
  row({
    id: "d",
    name: "Later Lead",
    due_state: "upcoming",
    days_overdue: 0,
    next_follow_up_date: "2026-11-30",
    classification: "Cold",
  }),
  row({
    id: "e",
    name: "Blocked Lead",
    due_state: "none",
    days_overdue: 0,
    next_follow_up_date: null,
    classification: "Cold",
    do_not_contact: true,
  }),
];

function renderPanel(overrides: Partial<Parameters<typeof QueuePanel>[0]> = {}) {
  const onSelect = vi.fn();
  const onRetry = vi.fn();
  const onClearFilters = vi.fn();
  render(
    <QueuePanel
      items={ITEMS}
      status="success"
      today={TODAY}
      timeZone={TZ}
      selectedId={null}
      filtered={false}
      onSelect={onSelect}
      onRetry={onRetry}
      onClearFilters={onClearFilters}
      {...overrides}
    />,
  );
  return { onSelect, onRetry, onClearFilters };
}

describe("QueuePanel", () => {
  it("groups leads into overdue, today, upcoming and no follow-up, in that order", () => {
    renderPanel();
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["Overdue (1)", "Due today (1)", "Upcoming (2)", "No follow-up (1)"]);
  });

  it("makes overdue rows unmistakable with text, not colour alone", () => {
    renderPanel();
    const overdue = screen.getByRole("link", { name: /Overdue Lead/ });
    expect(within(overdue).getByText("3d overdue")).toBeInTheDocument();
    expect(overdue).toHaveAttribute("data-due", "overdue");
  });

  it("labels upcoming dates relative to the server's today", () => {
    renderPanel();
    expect(
      within(screen.getByRole("link", { name: /Tomorrow Lead/ })).getByText("Tomorrow"),
    ).toBeVisible();
    expect(
      within(screen.getByRole("link", { name: /Later Lead/ })).getByText("Mon, 30 Nov"),
    ).toBeVisible();
  });

  it("marks the selected lead and reports clicks", async () => {
    const { onSelect } = renderPanel({ selectedId: "b" });
    expect(screen.getByRole("link", { name: /Today Lead/ })).toHaveAttribute(
      "aria-current",
      "true",
    );
    await userEvent.click(screen.getByRole("link", { name: /Overdue Lead/ }));
    expect(onSelect).toHaveBeenCalledWith("a");
  });

  it("keeps do-not-contact leads collapsed until asked", async () => {
    renderPanel();
    expect(screen.queryByRole("link", { name: /Blocked Lead/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Show no follow-up leads/ }));
    expect(screen.getByRole("link", { name: /Blocked Lead/ })).toBeInTheDocument();
  });

  it("shows a loading state while the queue is fetched", () => {
    renderPanel({ items: [], status: "pending" });
    expect(screen.getByRole("status", { name: /Loading follow-ups/ })).toBeInTheDocument();
  });

  it("offers a retry when the queue fails to load", async () => {
    const { onRetry } = renderPanel({ items: [], status: "error" });
    expect(screen.getByText(/couldn't load the follow-up queue/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("says when there are no leads at all", () => {
    renderPanel({ items: [], filtered: false });
    expect(screen.getByText(/No leads yet/)).toBeInTheDocument();
  });

  it("offers to clear filters when nothing matches", async () => {
    const { onClearFilters } = renderPanel({ items: [], filtered: true });
    expect(screen.getByText(/No leads match/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(onClearFilters).toHaveBeenCalled();
  });
});

describe("FilterBar", () => {
  it("shows live counts and toggles a segment", async () => {
    const onChange = vi.fn();
    render(<FilterBar summary={summary} active="all" onChange={onChange} />);
    const overdue = screen.getByRole("button", { name: /Overdue 4/ });
    expect(overdue).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: /All active 21/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await userEvent.click(overdue);
    expect(onChange).toHaveBeenCalledWith("overdue");
  });

  it("returns to all when the active segment is clicked again", async () => {
    const onChange = vi.fn();
    render(<FilterBar summary={summary} active="hot" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /Hot 6/ }));
    expect(onChange).toHaveBeenCalledWith("all");
  });
});

describe("TagBadge", () => {
  it("always pairs the colour with a text label", () => {
    render(<TagBadge label="Hot" />);
    expect(screen.getByText("Hot")).toBeInTheDocument();
  });

  it("shows an explicit state for unanalysed leads", () => {
    render(<TagBadge label={null} />);
    expect(screen.getByText("Not tagged yet")).toBeInTheDocument();
  });
});
