import type { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET as listAiJobsRoute, POST as createAiJobRoute } from "../../app/api/figure-chain/ai/jobs/route";
import { GET as getAiJobRoute } from "../../app/api/figure-chain/ai/jobs/[jobId]/route";
import { GET as listReviewCandidatesRoute } from "../../app/api/figure-chain/review/candidates/route";
import { GET as getReviewCandidateRoute } from "../../app/api/figure-chain/review/candidates/[kind]/[candidateId]/route";
import { POST as needsReviewCandidateRoute } from "../../app/api/figure-chain/review/candidates/[kind]/[candidateId]/needs-review/route";
import { POST as promoteReviewCandidateRoute } from "../../app/api/figure-chain/review/candidates/[kind]/[candidateId]/promote/route";
import { POST as rejectReviewCandidateRoute } from "../../app/api/figure-chain/review/candidates/[kind]/[candidateId]/reject/route";

function stubJsonFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("review workspace API routes", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("forwards review candidate list query parameters", async () => {
    const fetchMock = stubJsonFetch();

    await listReviewCandidatesRoute(
      new Request(
        "http://localhost/api/figure-chain/review/candidates?kind=relationship&status=needs_review&min_confidence=0.75&person_id=abc&limit=25&offset=50&ignored=1",
      ),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/review/candidates?kind=relationship&status=needs_review&min_confidence=0.75&person_id=abc&limit=25&offset=50",
      expect.any(Object),
    );
  });

  it("forwards review candidate detail requests with encoded parameters", async () => {
    const fetchMock = stubJsonFetch();

    await getReviewCandidateRoute(
      new Request("http://localhost/api/figure-chain/review/candidates/kind/id") as NextRequest,
      {
        params: Promise.resolve({
          kind: "relationship kind",
          candidateId: "960664",
        }),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/review/candidates/relationship%20kind/960664",
      expect.any(Object),
    );
  });

  it.each([
    ["promote", promoteReviewCandidateRoute],
    ["reject", rejectReviewCandidateRoute],
    ["needs-review", needsReviewCandidateRoute],
  ])("forwards %s review actions with the raw JSON body", async (action, route) => {
    const fetchMock = stubJsonFetch();
    const body = JSON.stringify({ reviewed_by: "lyl", reason: "not direct" });

    await route(
      new Request(`http://localhost/api/figure-chain/review/candidates/relationship/960664/${action}`, {
        method: "POST",
        body,
      }) as NextRequest,
      {
        params: Promise.resolve({
          kind: "relationship",
          candidateId: "960664",
        }),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      `http://127.0.0.1:8000/api/v1/review/candidates/relationship/960664/${action}`,
      expect.objectContaining({ method: "POST", body }),
    );
  });

  it("forwards AI job list query parameters", async () => {
    const fetchMock = stubJsonFetch();

    await listAiJobsRoute(
      new Request(
        "http://localhost/api/figure-chain/ai/jobs?target_type=candidate&target_kind=relationship&target_id=960664&limit=5&ignored=1",
      ),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/ai/jobs?target_type=candidate&target_kind=relationship&target_id=960664&limit=5",
      expect.any(Object),
    );
  });

  it("forwards AI job create requests with the raw JSON body", async () => {
    const fetchMock = stubJsonFetch();
    const body = JSON.stringify({
      job_type: "candidate_review_suggestion",
      target_type: "candidate",
      target_kind: "relationship",
      target_id: 960664,
      created_by: "lyl",
      params: {},
    });

    await createAiJobRoute(
      new Request("http://localhost/api/figure-chain/ai/jobs", {
        method: "POST",
        body,
      }),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/ai/jobs",
      expect.objectContaining({ method: "POST", body }),
    );
  });

  it("forwards AI job detail requests with encoded job ids", async () => {
    const fetchMock = stubJsonFetch();

    await getAiJobRoute(
      new Request("http://localhost/api/figure-chain/ai/jobs/id") as NextRequest,
      {
        params: Promise.resolve({ jobId: "job id" }),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/ai/jobs/job%20id",
      expect.any(Object),
    );
  });
});
