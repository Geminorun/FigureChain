import { beforeEach, describe, expect, it, vi } from "vitest";

const forwardMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api-client", () => ({
  forwardToFigureChain: forwardMock,
}));

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

describe("admin AI jobs API routes", () => {
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

  it("forwards list query keys with operator headers", async () => {
    const { GET } = await import(
      "../../app/api/figure-chain/admin/ai/jobs/route"
    );

    const response = await GET(
      new Request(
        "http://localhost/api/figure-chain/admin/ai/jobs?status=queued&target_kind=relationship&target_id=12&queue_backend=rq&limit=10&offset=5&ignored=1",
      ),
    );

    expect(await response.json()).toEqual({
      path: "/api/v1/admin/ai/jobs?status=queued&target_kind=relationship&target_id=12&queue_backend=rq&limit=10&offset=5",
      method: "GET",
      headers: ADMIN_HEADERS,
    });
  });

  it("forwards detail and events paths with encoded job id", async () => {
    const detail = await import(
      "../../app/api/figure-chain/admin/ai/jobs/[jobId]/route"
    );
    const events = await import(
      "../../app/api/figure-chain/admin/ai/jobs/[jobId]/events/route"
    );

    const context = { params: Promise.resolve({ jobId: "job/id" }) };
    const detailResponse = await detail.GET(new Request("http://localhost"), context);
    const eventsResponse = await events.GET(new Request("http://localhost"), context);

    expect(await detailResponse.json()).toEqual({
      path: "/api/v1/admin/ai/jobs/job%2Fid",
      method: "GET",
      headers: ADMIN_HEADERS,
    });
    expect(await eventsResponse.json()).toEqual({
      path: "/api/v1/admin/ai/jobs/job%2Fid/events",
      method: "GET",
      headers: ADMIN_HEADERS,
    });
  });

  it("forwards cancel and retry bodies unchanged", async () => {
    const cancel = await import(
      "../../app/api/figure-chain/admin/ai/jobs/[jobId]/cancel/route"
    );
    const retry = await import(
      "../../app/api/figure-chain/admin/ai/jobs/[jobId]/retry/route"
    );
    const context = { params: Promise.resolve({ jobId: "job-1" }) };

    const cancelResponse = await cancel.POST(requestWithBody({ actor: "local" }), context);
    const retryResponse = await retry.POST(requestWithBody({ actor: "local" }), context);

    expect(await cancelResponse.json()).toEqual({
      path: "/api/v1/admin/ai/jobs/job-1/cancel",
      method: "POST",
      headers: ADMIN_HEADERS,
      body: JSON.stringify({ actor: "local" }),
    });
    expect(await retryResponse.json()).toEqual({
      path: "/api/v1/admin/ai/jobs/job-1/retry",
      method: "POST",
      headers: ADMIN_HEADERS,
      body: JSON.stringify({ actor: "local" }),
    });
  });

  it("forwards requeue and health requests with operator headers", async () => {
    const requeue = await import(
      "../../app/api/figure-chain/admin/ai/jobs/requeue/route"
    );
    const health = await import(
      "../../app/api/figure-chain/admin/ai/health/route"
    );

    const requeueResponse = await requeue.POST(
      requestWithBody({ actor: "local", limit: 20 }),
    );
    const healthResponse = await health.GET();

    expect(await requeueResponse.json()).toEqual({
      path: "/api/v1/admin/ai/jobs/requeue",
      method: "POST",
      headers: ADMIN_HEADERS,
      body: JSON.stringify({ actor: "local", limit: 20 }),
    });
    expect(await healthResponse.json()).toEqual({
      path: "/api/v1/admin/ai/health",
      method: "GET",
      headers: ADMIN_HEADERS,
    });
  });
});

function requestWithBody(body: object): Request {
  return new Request("http://localhost/api/figure-chain/admin/ai/jobs", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
