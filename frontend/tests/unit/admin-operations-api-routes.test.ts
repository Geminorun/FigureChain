import { beforeEach, describe, expect, it, vi } from "vitest";

const forwardMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  forwardToFigureChain: forwardMock,
}));

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

describe("admin operation API routes", () => {
  beforeEach(() => {
    vi.resetModules();
    forwardMock.mockReset();
    forwardMock.mockImplementation(async (path: string, init?: RequestInit) =>
      Response.json({ path, headers: init?.headers }),
    );
  });

  it("forwards operation list filters", async () => {
    const { GET } = await import("../../app/api/figure-chain/admin/operations/route");
    const response = await GET(
      new Request(
        "http://localhost/api/figure-chain/admin/operations?status=succeeded&operation_type=sync_graph_rebuild&actor=lyl&limit=20&offset=5&ignored=yes",
      ),
    );

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/operations?status=succeeded&operation_type=sync_graph_rebuild&actor=lyl&limit=20&offset=5",
      headers: ADMIN_HEADERS,
    });
  });

  it("forwards operation detail requests", async () => {
    const { GET } = await import(
      "../../app/api/figure-chain/admin/operations/[operationId]/route"
    );
    const response = await GET(new Request("http://localhost/test"), {
      params: Promise.resolve({ operationId: "operation-1" }),
    });

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/operations/operation-1",
      headers: ADMIN_HEADERS,
    });
  });
});
