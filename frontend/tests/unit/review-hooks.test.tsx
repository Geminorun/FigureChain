import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useAiJob } from "@/hooks/use-ai-job";
import { useAdminReviewActions } from "@/hooks/use-admin-review-actions";
import { useReviewActions } from "@/hooks/use-review-actions";
import { useReviewCandidateDetail } from "@/hooks/use-review-candidate-detail";
import { useReviewCandidates } from "@/hooks/use-review-candidates";

const candidateSummary = {
  kind: "relationship",
  candidate_id: 960664,
  person_a: {
    person_id: "38966b03-8aa7-5143-8021-2d266889b6c5",
    cbdb_id: 780,
    display_name: "許幾",
    primary_name_zh_hant: "許幾",
    primary_name_zh_hans: "许几",
    primary_name_romanized: "Xu Ji",
    birth_year: 1054,
    death_year: 1115,
  },
  person_b: {
    person_id: "46cfdf66-08c4-5876-964b-4a95d098afe9",
    cbdb_id: 630,
    display_name: "韓琦",
    primary_name_zh_hant: "韓琦",
    primary_name_zh_hans: "韩琦",
    primary_name_romanized: "Han Qi",
    birth_year: 1008,
    death_year: 1075,
  },
  relation_type: "visited",
  time_summary: "北宋",
  place_summary: "魏",
  status: "needs_review",
  confidence: 0.92,
  evidence_count: 1,
  source_count: 1,
  promotion_readiness: {
    default_promotable: true,
    default_path_eligible: true,
    reasons: [],
  },
  latest_ai_job_status: null,
  has_ai_suggestion: false,
};

const candidateDetail = {
  ...candidateSummary,
  relation: {
    relation_type: "visited",
    basis: "source_ref",
    strength: "high",
    notes: null,
    source_name: "CBDB",
    source_table: "assoc_data",
    source_pk: "960664",
  },
  time: { summary: "北宋", pages: "11905" },
  place: { summary: "魏" },
  source_refs: [],
  evidence: [],
  linked_encounter: null,
  latest_ai_suggestion: null,
  ai_jobs: [],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

async function flushPromises(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

function aiJob(overrides: Record<string, unknown> = {}) {
  return {
    id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
    job_type: "candidate_review_suggestion",
    target_type: "candidate",
    target_kind: "relationship",
    target_id: 960664,
    status: "queued",
    created_by: "lyl",
    params: {},
    result_ref_type: null,
    result_ref_id: null,
    error_code: null,
    error_message: null,
    queue_backend: "rq",
    queue_name: "figure-ai",
    queue_job_id: "rq-job-501",
    enqueued_at: "2026-06-19T00:00:01Z",
    attempt_count: 1,
    max_attempts: 3,
    next_run_at: null,
    cancel_requested_at: null,
    worker_id: "worker-1",
    heartbeat_at: "2026-06-19T00:00:02Z",
    started_at: null,
    finished_at: null,
    created_at: "2026-06-18T00:00:00Z",
    updated_at: "2026-06-18T00:00:00Z",
    ...overrides,
  };
}

describe("review workspace hooks", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("loads review candidates and supports refresh", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [candidateSummary], count: 1, limit: 20, offset: 0 }))
      .mockResolvedValueOnce(jsonResponse({ items: [], count: 0, limit: 20, offset: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useReviewCandidates({
        kind: "relationship",
        status: "needs_review",
        minConfidence: 0.75,
        personId: "38966b03-8aa7-5143-8021-2d266889b6c5",
        limit: 20,
        offset: 0,
      }),
    );

    await flushPromises();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.data?.items).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/review/candidates?kind=relationship&status=needs_review&min_confidence=0.75&person_id=38966b03-8aa7-5143-8021-2d266889b6c5&limit=20&offset=0",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );

    await act(async () => {
      result.current.refresh();
    });

    await waitFor(() => expect(result.current.data?.count).toBe(0));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("loads review candidates from a configured admin base path", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ items: [candidateSummary], count: 1, limit: 20, offset: 0 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useReviewCandidates(
        { kind: "relationship", limit: 20 },
        { apiBasePath: "/api/figure-chain/admin/review" },
      ),
    );

    await flushPromises();
    expect(result.current.error).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/admin/review/candidates?kind=relationship&limit=20",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("surfaces review candidate load errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "dependency_unavailable",
              message: "PostgreSQL unavailable",
              details: {},
            },
          },
          503,
        ),
      ),
    );

    const { result } = renderHook(() => useReviewCandidates({ limit: 20 }));

    await flushPromises();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error?.code).toBe("dependency_unavailable");
    expect(result.current.data).toBeNull();
  });

  it("loads review candidate details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(candidateDetail)));

    const { result } = renderHook(() => useReviewCandidateDetail("relationship", 960664));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.detail?.candidate_id).toBe(960664);
  });

  it("loads review candidate details from a configured admin base path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(candidateDetail));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useReviewCandidateDetail("relationship", 960664, {
        apiBasePath: "/api/figure-chain/admin/review",
      }),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/admin/review/candidates/relationship/960664",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("posts review actions to a configured admin base path", async () => {
    const actionResponse = {
      operation_id: "operation-1",
      operation_type: "promote_candidate",
      status: "succeeded",
      action: {
        kind: "relationship",
        candidate_id: 960664,
        status: "promoted",
        reviewed_by: "local",
        encounter: { encounter_id: "encounter-1", status: "active" },
        message: null,
      },
      preview: "已提升候选 960664",
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(actionResponse));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useReviewActions(
        { kind: "relationship", candidateId: 960664 },
        { apiBasePath: "/api/figure-chain/admin/review" },
      ),
    );

    await act(async () => {
      const response = await result.current.promote({
        reviewed_by: "local",
        evidence_summary: "明确同席",
      });
      expect(response).toEqual(actionResponse);
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/admin/review/candidates/relationship/960664/promote",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          reviewed_by: "local",
          evidence_summary: "明确同席",
        }),
      }),
    );
  });

  it("retracts encounters through the admin review hook", async () => {
    const retractResponse = {
      operation_id: "operation-2",
      operation_type: "retract_encounter",
      status: "succeeded",
      result: {
        encounter_id: "encounter-1",
        status: "retracted",
        path_eligible: false,
        linked_candidates_updated: 1,
      },
      preview: "已撤回 encounter-1",
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(retractResponse));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAdminReviewActions({ kind: "relationship", candidateId: 960664 }),
    );

    await act(async () => {
      const response = await result.current.retractEncounter("encounter/1", {
        reviewed_by: "local",
        note: "证据不足",
        force: false,
      });
      expect(response).toEqual(retractResponse);
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/figure-chain/admin/review/encounters/encounter%2F1/retract",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          reviewed_by: "local",
          note: "证据不足",
          force: false,
        }),
      }),
    );
  });

  it("creates AI jobs, polls active jobs, and stops after terminal status", async () => {
    const queuedJob = {
      id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
      job_type: "candidate_review_suggestion",
      target_type: "candidate",
      target_kind: "relationship",
      target_id: 960664,
      status: "queued",
      created_by: "lyl",
      params: {},
      result_ref_type: null,
      result_ref_id: null,
      error_code: null,
      error_message: null,
      started_at: null,
      finished_at: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [], count: 0, limit: 20 }))
      .mockResolvedValueOnce(jsonResponse(queuedJob))
      .mockResolvedValueOnce(jsonResponse({ ...queuedJob, status: "running" }))
      .mockResolvedValueOnce(jsonResponse({ ...queuedJob, status: "succeeded", finished_at: "2026-06-18T00:00:10Z" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAiJob({
        targetType: "candidate",
        targetKind: "relationship",
        targetId: 960664,
        pollIntervalMs: 1,
      }),
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.createJob({ createdBy: "lyl" });
    });

    expect(result.current.activeJob?.status).toBe("queued");

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4));
    expect(result.current.activeJob?.status).toBe("succeeded");
    await new Promise((resolve) => window.setTimeout(resolve, 10));
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("stops polling old AI jobs when the candidate target changes", async () => {
    vi.useFakeTimers();
    const activeJob = {
      id: "9d6958d5-c0e5-4112-9659-bb47c27cbdb7",
      job_type: "candidate_review_suggestion",
      target_type: "candidate",
      target_kind: "relationship",
      target_id: 960664,
      status: "queued",
      created_by: "lyl",
      params: {},
      result_ref_type: null,
      result_ref_id: null,
      error_code: null,
      error_message: null,
      started_at: null,
      finished_at: null,
      created_at: "2026-06-18T00:00:00Z",
      updated_at: "2026-06-18T00:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [activeJob], count: 1, limit: 20 }))
      .mockResolvedValue(jsonResponse({ items: [], count: 0, limit: 20 }));
    vi.stubGlobal("fetch", fetchMock);

    const { rerender } = renderHook(
      ({ targetId }) =>
        useAiJob({
          targetType: "candidate",
          targetKind: "relationship",
          targetId,
          pollIntervalMs: 2000,
        }),
      { initialProps: { targetId: 960664 } },
    );

    await flushPromises();
    const oldJobUrl = `/api/figure-chain/ai/jobs/${activeJob.id}`;
    const oldJobCallsBeforeSwitch = fetchMock.mock.calls.filter(
      ([url]) => url === oldJobUrl,
    ).length;

    rerender({ targetId: 960665 });
    await flushPromises();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });

    const oldJobCallsAfterSwitch = fetchMock.mock.calls.filter(
      ([url]) => url === oldJobUrl,
    ).length;
    expect(oldJobCallsAfterSwitch).toBe(oldJobCallsBeforeSwitch);
  });

  it("cancels the active AI job", async () => {
    const activeJob = aiJob();
    const cancelledJob = aiJob({
      status: "cancelled",
      cancel_requested_at: "2026-06-19T00:00:03Z",
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [activeJob], count: 1, limit: 20 }))
      .mockResolvedValueOnce(jsonResponse(cancelledJob));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAiJob({
        targetType: "candidate",
        targetKind: "relationship",
        targetId: 960664,
      }),
    );

    await waitFor(() => expect(result.current.jobs).toHaveLength(1));
    await act(async () => {
      await result.current.cancelJob(activeJob.id, { cancelledBy: "lyl" });
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/figure-chain/ai/jobs/${activeJob.id}/cancel`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ cancelled_by: "lyl" }),
      }),
    );
    expect(result.current.jobs[0]?.status).toBe("cancelled");
  });

  it("retries failed AI jobs", async () => {
    const failedJob = aiJob({ status: "failed", error_message: "timeout" });
    const retryJob = aiJob({ id: "new-job-id", status: "queued" });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [failedJob], count: 1, limit: 20 }))
      .mockResolvedValueOnce(jsonResponse(retryJob));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAiJob({
        targetType: "candidate",
        targetKind: "relationship",
        targetId: 960664,
      }),
    );

    await waitFor(() => expect(result.current.jobs).toHaveLength(1));
    await act(async () => {
      await result.current.retryJob(failedJob.id, { createdBy: "lyl" });
    });

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/figure-chain/ai/jobs/${failedJob.id}/retry`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ created_by: "lyl" }),
      }),
    );
    expect(result.current.activeJob?.id).toBe("new-job-id");
  });

  it("loads AI job events", async () => {
    const activeJob = aiJob();
    const event = {
      id: "event-1",
      job_id: activeJob.id,
      event_type: "retry_scheduled",
      actor: "worker",
      message: "provider timeout",
      metadata: { delay_seconds: 10 },
      created_at: "2026-06-19T00:00:04Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ items: [activeJob], count: 1, limit: 20 }))
      .mockResolvedValueOnce(jsonResponse({ items: [event], count: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useAiJob({
        targetType: "candidate",
        targetKind: "relationship",
        targetId: 960664,
      }),
    );

    await waitFor(() => expect(result.current.jobs).toHaveLength(1));
    await act(async () => {
      await result.current.loadEvents(activeJob.id);
    });

    expect(fetchMock).toHaveBeenCalledWith(`/api/figure-chain/ai/jobs/${activeJob.id}/events`);
    expect(result.current.eventsByJobId[activeJob.id]).toEqual([event]);
  });
});
