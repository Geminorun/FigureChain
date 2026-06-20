import { beforeEach, describe, expect, it, vi } from "vitest";

const forwardMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  forwardToFigureChain: forwardMock,
}));

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

describe("admin review API routes", () => {
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

  it("forwards candidate list query keys with operator headers", async () => {
    const { GET } = await import(
      "../../app/api/figure-chain/admin/review/candidates/route"
    );

    const response = await GET(
      new Request(
        "http://localhost/api/figure-chain/admin/review/candidates?kind=relationship&status=needs_review&min_confidence=0.75&person_id=abc&limit=25&offset=50&ignored=1",
      ),
    );

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/review/candidates?kind=relationship&status=needs_review&min_confidence=0.75&person_id=abc&limit=25&offset=50",
      method: "GET",
      headers: ADMIN_HEADERS,
    });
  });

  it("forwards candidate detail requests with encoded parameters", async () => {
    const { GET } = await import(
      "../../app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/route"
    );

    const response = await GET(new Request("http://localhost"), {
      params: Promise.resolve({
        kind: "relationship kind",
        candidateId: "960/664",
      }),
    });

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/review/candidates/relationship%20kind/960%2F664",
      method: "GET",
      headers: ADMIN_HEADERS,
    });
  });

  it.each([
    ["promote", "../../app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/promote/route"],
    ["reject", "../../app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/reject/route"],
    ["needs-review", "../../app/api/figure-chain/admin/review/candidates/[kind]/[candidateId]/needs-review/route"],
  ])("forwards %s bodies unchanged", async (action, routePath) => {
    const route = await import(routePath);
    const body = { reviewed_by: "local", reason: "not direct" };

    const response = await route.POST(requestWithBody(body), {
      params: Promise.resolve({
        kind: "relationship",
        candidateId: "960664",
      }),
    });

    expect(await response.json()).toEqual({
      path: `/api/v1/admin/review/candidates/relationship/960664/${action}`,
      method: "POST",
      headers: ADMIN_HEADERS,
      body: JSON.stringify(body),
    });
  });

  it("forwards encounter retract bodies unchanged", async () => {
    const { POST } = await import(
      "../../app/api/figure-chain/admin/review/encounters/[encounterId]/retract/route"
    );
    const body = { reviewed_by: "local", note: "撤回误判", force: false };

    const response = await POST(requestWithBody(body), {
      params: Promise.resolve({ encounterId: "encounter/id" }),
    });

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/review/encounters/encounter%2Fid/retract",
      method: "POST",
      headers: ADMIN_HEADERS,
      body: JSON.stringify(body),
    });
  });
});

function requestWithBody(body: object): Request {
  return new Request("http://localhost/api/figure-chain/admin/review", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
