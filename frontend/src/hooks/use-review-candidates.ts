"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { ReviewCandidateListResponse } from "@/lib/figure-chain-types";

export type ReviewCandidateFilters = {
  kind?: string;
  status?: string;
  minConfidence?: number;
  personId?: string;
  limit?: number;
  offset?: number;
};

type ReviewCandidatesState = {
  requestKey: string | null;
  data: ReviewCandidateListResponse | null;
  error: DisplayableError | null;
};

export type UseReviewCandidatesResult = {
  data: ReviewCandidateListResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
  refresh: () => void;
};

function buildCandidateQuery(filters: ReviewCandidateFilters): string {
  const query = new URLSearchParams();
  if (filters.kind) {
    query.set("kind", filters.kind);
  }
  if (filters.status) {
    query.set("status", filters.status);
  }
  if (filters.minConfidence !== undefined) {
    query.set("min_confidence", String(filters.minConfidence));
  }
  if (filters.personId) {
    query.set("person_id", filters.personId);
  }
  if (filters.limit !== undefined) {
    query.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    query.set("offset", String(filters.offset));
  }
  return query.toString();
}

export function useReviewCandidates(
  filters: ReviewCandidateFilters = {},
): UseReviewCandidatesResult {
  const {
    kind,
    status,
    minConfidence,
    personId,
    limit,
    offset,
  } = filters;
  const [refreshToken, setRefreshToken] = useState(0);
  const [state, setState] = useState<ReviewCandidatesState>({
    requestKey: null,
    data: null,
    error: null,
  });
  const queryString = useMemo(
    () => buildCandidateQuery({ kind, status, minConfidence, personId, limit, offset }),
    [kind, status, minConfidence, personId, limit, offset],
  );
  const requestKey = `${queryString}:${refreshToken}`;

  useEffect(() => {
    const controller = new AbortController();
    const path = queryString
      ? `/api/figure-chain/review/candidates?${queryString}`
      : "/api/figure-chain/review/candidates";

    fetch(path, { signal: controller.signal })
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        setState({
          requestKey,
          data: body as ReviewCandidateListResponse,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          requestKey,
          data: null,
          error: parseErrorResponse(error),
        });
      });

    return () => controller.abort();
  }, [queryString, requestKey]);

  const refresh = useCallback(() => {
    setRefreshToken((value) => value + 1);
  }, []);

  const isLoading = state.requestKey !== requestKey;
  return {
    data: isLoading ? state.data : state.data,
    isLoading,
    error: isLoading ? null : state.error,
    refresh,
  };
}
