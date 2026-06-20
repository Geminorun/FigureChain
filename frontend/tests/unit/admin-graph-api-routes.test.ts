import { beforeEach, describe, expect, it, vi } from "vitest";

const forwardMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  forwardToFigureChain: forwardMock,
}));

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

describe("admin graph API routes", () => {
  beforeEach(() => {
    vi.resetModules();
    forwardMock.mockReset();
    forwardMock.mockImplementation(async (path: string, init?: RequestInit) =>
      Response.json({
        path,
        method: init?.method ?? "GET",
        headers: init?.headers,
        body: init?.body,
      }),
    );
  });

  it("forwards graph status requests with operator headers", async () => {
    const { GET } = await import(
      "../../app/api/figure-chain/admin/graph/status/route"
    );

    const response = await GET();

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/graph/status",
      method: "GET",
      headers: ADMIN_HEADERS,
    });
  });

  it("forwards validate encounters requests with operator headers", async () => {
    const { POST } = await import(
      "../../app/api/figure-chain/admin/graph/validate-encounters/route"
    );

    const response = await POST(requestWithBody({ actor: "local" }));

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/graph/validate-encounters",
      method: "POST",
      headers: ADMIN_HEADERS,
      body: JSON.stringify({ actor: "local" }),
    });
  });

  it("forwards sync requests with operator headers", async () => {
    const { POST } = await import(
      "../../app/api/figure-chain/admin/graph/sync/route"
    );

    const response = await POST(requestWithBody({ mode: "rebuild", actor: "local" }));

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/graph/sync",
      method: "POST",
      headers: ADMIN_HEADERS,
      body: JSON.stringify({ mode: "rebuild", actor: "local" }),
    });
  });

  it("forwards validate graph requests with operator headers", async () => {
    const { POST } = await import(
      "../../app/api/figure-chain/admin/graph/validate-graph/route"
    );

    const response = await POST(requestWithBody({ actor: "local" }));

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/graph/validate-graph",
      method: "POST",
      headers: ADMIN_HEADERS,
      body: JSON.stringify({ actor: "local" }),
    });
  });
});

function requestWithBody(body: object): Request {
  return new Request("http://localhost/api/figure-chain/admin/graph", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
