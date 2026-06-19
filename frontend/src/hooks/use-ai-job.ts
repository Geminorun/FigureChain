"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  AiJobCancelRequest,
  AiJobCreateRequest,
  AiJobEvent,
  AiJobEventListResponse,
  AiJobListResponse,
  AiJobResponse,
  AiJobRetryRequest,
} from "@/lib/figure-chain-types";

const POLLABLE_STATUSES = new Set(["queued", "running"]);

export type UseAiJobOptions = {
  targetType: string;
  targetKind: string;
  targetId: number | null;
  pollIntervalMs?: number;
};

export type CreateAiJobOptions = {
  createdBy: string;
  jobType?: string;
  params?: Record<string, unknown>;
};

type AiJobState = {
  jobs: AiJobResponse[];
  activeJob: AiJobResponse | null;
  eventsByJobId: Record<string, AiJobEvent[]>;
  isLoading: boolean;
  isCreating: boolean;
  error: DisplayableError | null;
};

export type UseAiJobResult = AiJobState & {
  refresh: () => void;
  createJob: (options: CreateAiJobOptions) => Promise<AiJobResponse | null>;
  cancelJob: (
    jobId: string,
    options: { cancelledBy: string },
  ) => Promise<AiJobResponse | null>;
  retryJob: (
    jobId: string,
    options: { createdBy: string },
  ) => Promise<AiJobResponse | null>;
  loadEvents: (jobId: string) => Promise<AiJobEvent[]>;
};

function isPollable(job: AiJobResponse | null): job is AiJobResponse {
  return job !== null && POLLABLE_STATUSES.has(job.status);
}

function replaceJob(jobs: AiJobResponse[], job: AiJobResponse): AiJobResponse[] {
  const index = jobs.findIndex((item) => item.id === job.id);
  if (index === -1) {
    return [job, ...jobs];
  }
  return jobs.map((item) => (item.id === job.id ? job : item));
}

async function postJobAction(
  jobId: string,
  action: "cancel" | "retry",
  body: AiJobCancelRequest | AiJobRetryRequest,
): Promise<AiJobResponse> {
  const response = await fetch(
    `/api/figure-chain/ai/jobs/${encodeURIComponent(jobId)}/${action}`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
  const payload = (await response.json()) as unknown;
  if (!response.ok) {
    throw parseErrorResponse(payload);
  }
  return payload as AiJobResponse;
}

export function useAiJob({
  targetType,
  targetKind,
  targetId,
  pollIntervalMs = 2000,
}: UseAiJobOptions): UseAiJobResult {
  const [refreshToken, setRefreshToken] = useState(0);
  const [state, setState] = useState<AiJobState>({
    jobs: [],
    activeJob: null,
    eventsByJobId: {},
    isLoading: targetId !== null,
    isCreating: false,
    error: null,
  });
  const targetKey = targetId === null ? "" : `${targetType}:${targetKind}:${targetId}`;
  const listPath = useMemo(() => {
    if (targetId === null) {
      return null;
    }
    const query = new URLSearchParams({
      target_type: targetType,
      target_kind: targetKind,
      target_id: String(targetId),
      limit: "20",
    });
    return `/api/figure-chain/ai/jobs?${query.toString()}`;
  }, [targetId, targetKind, targetType]);

  useEffect(() => {
    if (listPath === null) {
      setState({
        jobs: [],
        activeJob: null,
        eventsByJobId: {},
        isLoading: false,
        isCreating: false,
        error: null,
      });
      return;
    }

    const controller = new AbortController();
    setState((current) => ({
      ...current,
      activeJob: null,
      eventsByJobId: {},
      isLoading: true,
      error: null,
    }));

    fetch(listPath, { signal: controller.signal })
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        const data = body as AiJobListResponse;
        setState((current) => ({
          ...current,
          jobs: data.items,
          activeJob: data.items.find(isPollable) ?? null,
          isLoading: false,
          error: null,
        }));
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState((current) => ({
          ...current,
          jobs: [],
          activeJob: null,
          eventsByJobId: {},
          isLoading: false,
          error: parseErrorResponse(error),
        }));
      });

    return () => controller.abort();
  }, [listPath, refreshToken]);

  useEffect(() => {
    if (!isPollable(state.activeJob)) {
      return;
    }
    const jobId = state.activeJob.id;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(`/api/figure-chain/ai/jobs/${encodeURIComponent(jobId)}`, {
        signal: controller.signal,
      })
        .then(async (response) => {
          const body = (await response.json()) as unknown;
          if (!response.ok) {
            throw parseErrorResponse(body);
          }
          const job = body as AiJobResponse;
          setState((current) => ({
            ...current,
            jobs: replaceJob(current.jobs, job),
            activeJob: job,
            error: null,
          }));
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) {
            return;
          }
          setState((current) => ({
            ...current,
            error: parseErrorResponse(error),
          }));
        });
    }, pollIntervalMs);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [pollIntervalMs, state.activeJob, targetKey]);

  const refresh = useCallback(() => {
    setRefreshToken((value) => value + 1);
  }, []);

  const createJob = useCallback(
    async ({
      createdBy,
      jobType = "candidate_review_suggestion",
      params = {},
    }: CreateAiJobOptions): Promise<AiJobResponse | null> => {
      if (targetId === null) {
        return null;
      }
      const request: AiJobCreateRequest = {
        job_type: jobType,
        target_type: targetType,
        target_kind: targetKind,
        target_id: targetId,
        created_by: createdBy,
        params,
      };

      setState((current) => ({ ...current, isCreating: true, error: null }));
      try {
        const response = await fetch("/api/figure-chain/ai/jobs", {
          method: "POST",
          body: JSON.stringify(request),
        });
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        const job = body as AiJobResponse;
        setState((current) => ({
          ...current,
          jobs: replaceJob(current.jobs, job),
          activeJob: isPollable(job) ? job : null,
          isCreating: false,
          error: null,
        }));
        return job;
      } catch (error: unknown) {
        setState((current) => ({
          ...current,
          isCreating: false,
          error: parseErrorResponse(error),
        }));
        return null;
      }
    },
    [targetId, targetKind, targetType],
  );

  const cancelJob = useCallback(
    async (
      jobId: string,
      { cancelledBy }: { cancelledBy: string },
    ): Promise<AiJobResponse | null> => {
      try {
        const job = await postJobAction(jobId, "cancel", { cancelled_by: cancelledBy });
        setState((current) => ({
          ...current,
          jobs: replaceJob(current.jobs, job),
          activeJob: isPollable(job) ? job : null,
          error: null,
        }));
        return job;
      } catch (error: unknown) {
        setState((current) => ({ ...current, error: parseErrorResponse(error) }));
        return null;
      }
    },
    [],
  );

  const retryJob = useCallback(
    async (
      jobId: string,
      { createdBy }: { createdBy: string },
    ): Promise<AiJobResponse | null> => {
      try {
        const job = await postJobAction(jobId, "retry", { created_by: createdBy });
        setState((current) => ({
          ...current,
          jobs: replaceJob(current.jobs, job),
          activeJob: isPollable(job) ? job : null,
          error: null,
        }));
        return job;
      } catch (error: unknown) {
        setState((current) => ({ ...current, error: parseErrorResponse(error) }));
        return null;
      }
    },
    [],
  );

  const loadEvents = useCallback(async (jobId: string): Promise<AiJobEvent[]> => {
    try {
      const response = await fetch(
        `/api/figure-chain/ai/jobs/${encodeURIComponent(jobId)}/events`,
      );
      const body = (await response.json()) as unknown;
      if (!response.ok) {
        throw parseErrorResponse(body);
      }
      const payload = body as AiJobEventListResponse;
      setState((current) => ({
        ...current,
        eventsByJobId: {
          ...current.eventsByJobId,
          [jobId]: payload.items,
        },
        error: null,
      }));
      return payload.items;
    } catch (error: unknown) {
      setState((current) => ({ ...current, error: parseErrorResponse(error) }));
      return [];
    }
  }, []);

  return { ...state, refresh, createJob, cancelJob, retryJob, loadEvents };
}
