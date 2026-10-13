import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AddLeadDialog } from "@/components/add-lead-dialog";
import { ApiError, api } from "@/lib/api";
import { TODAY, detail, lead, meta } from "./fixtures";
import { renderWithClient } from "./render";

vi.mock("@/lib/api", async (original) => {
  const actual = await original<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: Object.fromEntries(
      Object.keys(actual.api).map((key) => [key, vi.fn()]),
    ) as unknown as typeof actual.api,
  };
});
const mocked = vi.mocked(api);

function setup() {
  const onCreated = vi.fn();
  const onOpenExisting = vi.fn();
  const onOpenChange = vi.fn();
  renderWithClient(
    <AddLeadDialog
      open
      onOpenChange={onOpenChange}
      meta={meta}
      defaultRep="Arjun Mehta"
      onCreated={onCreated}
      onOpenExisting={onOpenExisting}
    />,
  );
  return { onCreated, onOpenExisting, onOpenChange };
}

async function fillRequired() {
  await userEvent.type(screen.getByLabelText("Name"), "Kavita Iyer");
  await userEvent.type(screen.getByLabelText("Company"), "Masala Magic Foods");
  await userEvent.type(screen.getByLabelText("Phone"), "+91 90000 01234");
}

beforeEach(() => vi.clearAllMocks());

describe("AddLeadDialog", () => {
  it("validates a field when the rep leaves it", async () => {
    setup();
    await userEvent.click(screen.getByLabelText("Name"));
    await userEvent.tab();
    expect(await screen.findByText("Enter the contact's name.")).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
  });

  it("rejects a phone number without enough digits", async () => {
    setup();
    await userEvent.type(screen.getByLabelText("Phone"), "12ab");
    await userEvent.tab();
    expect(await screen.findByText(/7 to 15 digits/)).toBeInTheDocument();
  });

  it("creates the lead with the default rep and opens it", async () => {
    mocked.createLead.mockResolvedValue(detail({ lead: lead({ id: "new-1" }) }));
    const { onCreated } = setup();
    await fillRequired();
    await userEvent.click(screen.getByRole("button", { name: "Add lead" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("new-1"));
    const body = mocked.createLead.mock.calls[0][0];
    expect(body).toMatchObject({
      name: "Kavita Iyer",
      company: "Masala Magic Foods",
      phone: "+91 90000 01234",
      assigned_rep: "Arjun Mehta",
      source: "WhatsApp",
    });
    expect(body.client_request_id).toEqual(expect.any(String));
  });

  it("offers to open the existing lead when the phone is a duplicate", async () => {
    mocked.createLead.mockRejectedValue(
      new ApiError(409, "duplicate_phone", "exists", "r1", { existing_lead_id: "old-7" }),
    );
    const { onOpenExisting } = setup();
    await fillRequired();
    await userEvent.click(screen.getByRole("button", { name: "Add lead" }));
    expect(await screen.findByText(/already exists/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Open existing lead" }));
    expect(onOpenExisting).toHaveBeenCalledWith("old-7");
  });

  it("does not allow a last contact date in the future", () => {
    setup();
    expect(screen.getByLabelText(/Last contact/)).toHaveAttribute("max", TODAY);
  });
});
