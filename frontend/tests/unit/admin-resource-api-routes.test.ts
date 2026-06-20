import { beforeEach, describe, expect, it, vi } from "vitest";

const forwardMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  forwardToFigureChain: forwardMock,
}));

describe("admin resource API routes", () => {
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

  it("forwards resource metadata requests with operator headers", async () => {
    const { GET } = await import("../../app/api/figure-chain/admin/resources/route");

    const response = await GET();

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/resources",
      method: "GET",
      headers: {
        "x-figure-role": "operator",
        "x-figure-actor": "local",
      },
    });
  });

  it("forwards resource queries with operator headers", async () => {
    const { POST } = await import(
      "../../app/api/figure-chain/admin/resources/query/route"
    );

    const response = await POST(
      new Request("http://localhost/api/figure-chain/admin/resources/query", {
        method: "POST",
        body: JSON.stringify({ resource: "persons" }),
      }),
    );

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/resources/query",
      method: "POST",
      headers: {
        "x-figure-role": "operator",
        "x-figure-actor": "local",
      },
      body: JSON.stringify({ resource: "persons" }),
    });
  });
});
