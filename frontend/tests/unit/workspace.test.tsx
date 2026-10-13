import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AiStatus } from "@/components/lead/ai-status";
import { DraftComposer } from "@/components/lead/draft-composer";
import { LogChatForm } from "@/components/lead/log-chat-form";
import { ApiError, api } from "@/lib/api";
import { businessLocalToIso } from "@/lib/format";
import { TZ, detail, draft, lead } from "./fixtures";
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

beforeEach(() => {
  vi.clearAllMocks();
  mocked.lead.mockResolvedValue(detail());
});

describe("DraftComposer", () => {
  it("shows the AI draft and only enables Save once edited", async () => {
    renderWithClient(<DraftComposer lead={lead()} draft={draft()} timeZone={TZ} />);
    expect(screen.getByText(/AI draft · check before sending/)).toBeInTheDocument();
    const box = screen.getByRole("textbox", { name: /Next message/ });
    expect(box).toHaveValue(draft().body);
    const save = screen.getByRole("button", { name: "Save draft" });
    expect(save).toBeDisabled();
    await userEvent.type(box, " Thanks!");
    expect(save).toBeEnabled();
    mocked.saveDraft.mockResolvedValue(
      draft({ body: `${draft().body} Thanks!`, status: "edited", version: 4 }),
    );
    await userEvent.click(save);
    expect(mocked.saveDraft).toHaveBeenCalledWith("lead-1", {
      body: `${draft().body} Thanks!`,
      version: 3,
    });
  });

  it("explains a version conflict and can save the rep's text over the newer version", async () => {
    mocked.saveDraft.mockRejectedValueOnce(new ApiError(409, "version_conflict", "changed"));
    mocked.lead.mockResolvedValue(detail({ draft: draft({ version: 7 }) }));
    renderWithClient(<DraftComposer lead={lead()} draft={draft()} timeZone={TZ} />);
    const box = screen.getByRole("textbox", { name: /Next message/ });
    await userEvent.clear(box);
    await userEvent.type(box, "My version");
    await userEvent.click(screen.getByRole("button", { name: "Save draft" }));
    expect(await screen.findByText(/changed since you opened it/)).toBeInTheDocument();
    mocked.saveDraft.mockResolvedValue(draft({ body: "My version", version: 8 }));
    await userEvent.click(screen.getByRole("button", { name: "Save mine anyway" }));
    await waitFor(() =>
      expect(mocked.saveDraft).toHaveBeenLastCalledWith("lead-1", {
        body: "My version",
        version: 7,
      }),
    );
  });

  it("marks as sent with the current text and offers Undo", async () => {
    mocked.sendDraft.mockResolvedValue(detail());
    mocked.undoSend.mockResolvedValue(detail());
    renderWithClient(<DraftComposer lead={lead()} draft={draft()} timeZone={TZ} />);
    expect(screen.getByText(/Nothing is sent to WhatsApp/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Mark as sent" }));
    expect(mocked.sendDraft).toHaveBeenCalledWith("lead-1", { body: draft().body, version: 3 });
    await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
    expect(mocked.undoSend).toHaveBeenCalledWith("lead-1");
  });

  it("keeps Undo in the composer bar for as long as the server allows it", async () => {
    // A toast alone would be a time-boxed control; the bar keeps the action reachable.
    mocked.undoSend.mockResolvedValue(detail());
    renderWithClient(
      <DraftComposer
        lead={lead()}
        draft={draft({ status: "sent", sent_at: "2026-10-12T10:35:00Z", can_undo: true })}
        timeZone={TZ}
      />,
    );
    expect(screen.getByText(/Sent at 4:05 pm/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark as sent" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Undo marking as sent" }));
    expect(mocked.undoSend).toHaveBeenCalledWith("lead-1");
  });

  it("lets the rep write another message after one was sent", async () => {
    renderWithClient(
      <DraftComposer
        lead={lead()}
        draft={draft({ status: "sent", sent_at: "2026-10-12T10:35:00Z" })}
        timeZone={TZ}
      />,
    );
    expect(screen.queryByRole("textbox", { name: /Next message/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Write another message" }));
    expect(screen.getByRole("textbox", { name: /Next message/ })).toHaveValue("");
  });

  it("shows the character count only near the limit", async () => {
    renderWithClient(<DraftComposer lead={lead()} draft={draft()} timeZone={TZ} />);
    expect(screen.queryByText(/\/1000/)).not.toBeInTheDocument();
    const box = screen.getByRole("textbox", { name: /Next message/ });
    await userEvent.clear(box);
    await userEvent.click(box);
    await userEvent.paste("x".repeat(820));
    expect(screen.getByText("820/1000")).toBeInTheDocument();
  });

  it("renders the draft after the conversation it answers", () => {
    renderWithClient(
      <DraftComposer
        lead={lead()}
        draft={draft()}
        timeZone={TZ}
        thread={<p>Earlier conversation</p>}
      />,
    );
    const thread = screen.getByText("Earlier conversation");
    const box = screen.getByRole("textbox", { name: /Next message/ });
    expect(thread.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("does not allow sending an empty message", async () => {
    renderWithClient(<DraftComposer lead={lead()} draft={draft()} timeZone={TZ} />);
    await userEvent.clear(screen.getByRole("textbox", { name: /Next message/ }));
    expect(screen.getByRole("button", { name: "Mark as sent" })).toBeDisabled();
  });

  it("offers a newer AI suggestion without overwriting the rep's edit", async () => {
    mocked.acceptSuggestion.mockResolvedValue(draft({ body: "New AI text", version: 5 }));
    renderWithClient(
      <DraftComposer
        lead={lead()}
        draft={draft({
          status: "edited",
          body: "My words",
          suggested_body: "New AI text",
          version: 4,
        })}
        timeZone={TZ}
      />,
    );
    expect(screen.getByRole("textbox", { name: /Next message/ })).toHaveValue("My words");
    const banner = screen.getByRole("region", { name: /New suggestion/ });
    expect(within(banner).getByText("New AI text")).toBeInTheDocument();
    await userEvent.click(within(banner).getByRole("button", { name: "Use new draft" }));
    expect(mocked.acceptSuggestion).toHaveBeenCalledWith("lead-1", 4);
  });

  it("keeps the rep's typing when a newer draft version arrives", async () => {
    const { rerender } = renderWithClient(
      <DraftComposer lead={lead()} draft={draft()} timeZone={TZ} />,
    );
    const box = screen.getByRole("textbox", { name: /Next message/ });
    await userEvent.type(box, " extra");
    rerender(
      <DraftComposer
        lead={lead()}
        draft={draft({ body: "Server text", version: 9 })}
        timeZone={TZ}
      />,
    );
    expect(screen.getByRole("textbox", { name: /Next message/ })).toHaveValue(
      `${draft().body} extra`,
    );
    expect(screen.getByText(/updated in the background/)).toBeInTheDocument();
  });

  it("replaces the composer with a notice for do-not-contact leads", () => {
    renderWithClient(
      <DraftComposer
        lead={lead({ do_not_contact: true })}
        draft={draft({ status: "none", body: "" })}
        timeZone={TZ}
      />,
    );
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByText(/asked not to be contacted/)).toBeInTheDocument();
  });
});

describe("LogChatForm", () => {
  it("defaults to a buyer message and keeps the radio state explicit", () => {
    renderWithClient(<LogChatForm leadId="lead-1" timeZone={TZ} />);
    expect(screen.getByRole("radio", { name: "Buyer" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Rep" })).toHaveAttribute("aria-checked", "false");
  });

  it("submits several messages with one request id and reuses it on retry", async () => {
    mocked.logMessages.mockRejectedValueOnce(new ApiError(0, "network", "offline"));
    mocked.logMessages.mockResolvedValueOnce(detail());
    renderWithClient(<LogChatForm leadId="lead-1" timeZone={TZ} />);
    await userEvent.type(
      screen.getByRole("textbox", { name: "Message 1" }),
      "Please send the quote",
    );
    await userEvent.click(screen.getByRole("button", { name: /Add another message/ }));
    await userEvent.click(screen.getAllByRole("radio", { name: "Rep" })[1]);
    await userEvent.type(screen.getByRole("textbox", { name: "Message 2" }), "Sending today");
    await userEvent.click(screen.getByRole("button", { name: "Log chat" }));
    await userEvent.click(await screen.findByRole("button", { name: "Log chat" }));
    await waitFor(() => expect(mocked.logMessages).toHaveBeenCalledTimes(2));
    const [first, second] = mocked.logMessages.mock.calls.map(([, body]) => body);
    expect(first.client_request_id).toBe(second.client_request_id);
    expect(second.messages).toEqual([
      { sender_type: "buyer", body: "Please send the quote" },
      { sender_type: "rep", body: "Sending today" },
    ]);
  });

  it("requires text before submitting", async () => {
    renderWithClient(<LogChatForm leadId="lead-1" timeZone={TZ} />);
    await userEvent.click(screen.getByRole("button", { name: "Log chat" }));
    expect(await screen.findByText("Write the message text.")).toBeInTheDocument();
    expect(mocked.logMessages).not.toHaveBeenCalled();
  });
});

describe("AiStatus", () => {
  it("announces an update in progress", () => {
    renderWithClient(
      <AiStatus leadId="lead-1" lead={lead({ analysis_status: "pending" })} timeZone={TZ} />,
    );
    expect(screen.getByText(/Reading the latest chat and redrafting/)).toBeInTheDocument();
  });

  it("labels rule-based results and offers a retry", async () => {
    mocked.analyze.mockResolvedValue({ analysis_status: "pending" });
    renderWithClient(
      <AiStatus
        leadId="lead-1"
        lead={lead({
          analysis_status: "failed",
          analysis_source: "rules_fallback",
          analysis_error: "exhausted",
        })}
        timeZone={TZ}
      />,
    );
    expect(screen.getByText(/Rule-based \(AI unavailable\)/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry analysis" }));
    expect(mocked.analyze).toHaveBeenCalledWith("lead-1");
  });

  it("names the model when analysis succeeded", () => {
    renderWithClient(<AiStatus leadId="lead-1" lead={lead()} timeZone={TZ} />);
    expect(screen.getByText(/Analysed by Gemini/)).toBeInTheDocument();
  });
});

describe("businessLocalToIso", () => {
  it("reads a datetime-local value as business time", () => {
    expect(businessLocalToIso("2026-10-12T16:05", TZ)).toBe("2026-10-12T10:35:00.000Z");
  });
});
