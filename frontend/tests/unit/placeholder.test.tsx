import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { WorkspacePlaceholder } from "@/components/lead/workspace-placeholder";
import { TODAY, row, summary } from "./fixtures";

describe("WorkspacePlaceholder", () => {
  it("states what is due and opens the most urgent lead", async () => {
    const onOpen = vi.fn();
    const first = row({ id: "a", name: "Gaurav Singh", due_state: "overdue", days_overdue: 9 });
    render(<WorkspacePlaceholder summary={summary} first={first} today={TODAY} onOpen={onOpen} />);

    expect(screen.getByRole("heading", { name: "4 overdue · 5 due today" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Start with Gaurav Singh/ }));
    expect(onOpen).toHaveBeenCalledWith("a");
  });

  it("says when nothing is due and offers no start button without leads", () => {
    render(
      <WorkspacePlaceholder
        summary={{ ...summary, overdue: 0, today: 0 }}
        first={undefined}
        today={TODAY}
        onOpen={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Nothing due today" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Start with/ })).not.toBeInTheDocument();
  });
});
