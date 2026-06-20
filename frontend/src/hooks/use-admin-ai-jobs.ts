"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  AdminAIJobActionResponse,
  AdminAIJobListResponse,
  AiJobEventListResponse,
  AiJobHealthResponse,
  AiJobResponse,
} from "@/lib/figure-chain-types";

export type AdminAIJobFilters = {
  status?: string;
  target_kind?: string;
  target_id?: number | null;
  queue_backend?: string;
  limit?: number;
  offset?: number;
};

export function useAdminAIJobs(filters: AdminAIJobFilters) {
  const [data, setData] = useState<AdminAIJobListResponse | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [loading, setLoading] = useState(false);
  const query = useMemo(() => buildJobsQuery(filters), [filters]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/figure-chain/admin/ai/jobs${query}`);
      const body: unknown = await response.json();
      if (!response.ok) {
        throw body;
      }
      setData(body as AdminAIJobListResponse);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [query]);

  useEffect(() => {
    let cancelled = false;

    async function loadJobs() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/figure-chain/admin/ai/jobs${query}`);
        const body: unknown = await response.json();
        if (!response.ok) {
          throw body;
        }
        if (!cancelled) {
          setData(body as AdminAIJobListResponse);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(parseErrorResponse(caught));
          setData(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadJobs();
    return () => {
      cancelled = true;
    };
  }, [query]);

  return { data, error, loading, refresh };
}

export function useAdminAIJob(jobId: string | null) {
  return useAdminAIJobResource<AiJobResponse>(
    jobId ? `/api/figure-chain/admin/ai/jobs/${encodeURIComponent(jobId)}` : null,
  );
}

export function useAdminAIJobEvents(jobId: string | null) {
  return useAdminAIJobResource<AiJobEventListResponse>(
    jobId
      ? `/api/figure-chain/admin/ai/jobs/${encodeURIComponent(jobId)}/events`
      : null,
  );
}

export function useAdminAIJobHealth() {
  return useAdminAIJobResource<AiJobHealthResponse>(
    "/api/figure-chain/admin/ai/health",
  );
}

export function useAdminAIJobActions() {
  const [data, setData] = useState<AdminAIJobActionResponse | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [loading, setLoading] = useState(false);

  const postAction = useCallback(async (path: string, body: object) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const responseBody: unknown = await response.json();
      if (!response.ok) {
        throw responseBody;
      }
      setData(responseBody as AdminAIJobActionResponse);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const cancelJob = useCallback(
    async (jobId: string, actor: string) =>
      postAction(`/api/figure-chain/admin/ai/jobs/${encodeURIComponent(jobId)}/cancel`, {
        actor,
      }),
    [postAction],
  );

  const retryJob = useCallback(
    async (jobId: string, actor: string) =>
      postAction(`/api/figure-chain/admin/ai/jobs/${encodeURIComponent(jobId)}/retry`, {
        actor,
      }),
    [postAction],
  );

  const requeueJobs = useCallback(
    async (actor: string, limit: number) =>
      postAction("/api/figure-chain/admin/ai/jobs/requeue", { actor, limit }),
    [postAction],
  );

  return { data, error, loading, cancelJob, retryJob, requeueJobs };
}

function useAdminAIJobResource<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (path === null) {
      setData(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(path);
      const body: unknown = await response.json();
      if (!response.ok) {
        throw body;
      }
      setData(body as T);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    let cancelled = false;

    async function loadResource() {
      if (path === null) {
        setData(null);
        setError(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(path);
        const body: unknown = await response.json();
        if (!response.ok) {
          throw body;
        }
        if (!cancelled) {
          setData(body as T);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(parseErrorResponse(caught));
          setData(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadResource();
    return () => {
      cancelled = true;
    };
  }, [path]);

  return { data, error, loading, refresh };
}

function buildJobsQuery(filters: AdminAIJobFilters): string {
  const query = new URLSearchParams();
  setString(query, "status", filters.status);
  setString(query, "target_kind", filters.target_kind);
  setString(query, "queue_backend", filters.queue_backend);
  setNumber(query, "target_id", filters.target_id);
  setNumber(query, "limit", filters.limit);
  setNumber(query, "offset", filters.offset);
  const value = query.toString();
  return value ? `?${value}` : "";
}

function setString(query: URLSearchParams, key: string, value: string | undefined): void {
  if (value && value.trim()) {
    query.set(key, value.trim());
  }
}

function setNumber(
  query: URLSearchParams,
  key: string,
  value: number | null | undefined,
): void {
  if (typeof value === "number" && Number.isFinite(value)) {
    query.set(key, String(value));
  }
}
