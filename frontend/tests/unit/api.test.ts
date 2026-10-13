import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "@/lib/api";

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("returns parsed JSON on success", async () => {
    vi.stubGlobal("fetch", respond(200, { status: "ok", db: "ok", ai: "configured" }));
    await expect(api.ready()).resolves.toEqual({ status: "ok", db: "ok", ai: "configured" });
  });

  it("maps the error envelope to ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      respond(409, {
        error: {
          code: "duplicate_phone",
          message: "A lead with this phone number already exists",
          request_id: "abc",
          details: { existing_lead_id: "123" },
        },
      }),
    );
    const error = await api.lead("x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      code: "duplicate_phone",
      requestId: "abc",
      details: { existing_lead_id: "123" },
    });
  });

  it("reports a network failure as a recoverable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.meta()).rejects.toMatchObject({ code: "network", status: 0 });
  });

  it("reports a timeout distinctly", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          );
        });
      }),
    );
    await expect(api.meta({ timeoutMs: 10 })).rejects.toMatchObject({ code: "timeout" });
  });

  it("sends JSON bodies and query parameters", async () => {
    const fetchMock = respond(200, { items: [], total: 0 });
    vi.stubGlobal("fetch", fetchMock);
    await api.leads({ rep: "Priya Sharma", q: "rahul", due_state: undefined });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("/api/v1/leads?");
    expect(url).toContain("rep=Priya+Sharma");
    expect(url).toContain("q=rahul");
    expect(url).not.toContain("due_state");

    const post = respond(200, {});
    vi.stubGlobal("fetch", post);
    await api.saveDraft("id-1", { body: "Hi", version: 2 });
    const [, init] = post.mock.calls[0];
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ body: "Hi", version: 2 });
  });
});
