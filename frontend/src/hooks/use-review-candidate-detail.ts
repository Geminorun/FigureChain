"use client";

import { useCallback, useEffect, useState } from "react";

import { resolveReviewApiBasePath, type ReviewApiOptions } from "@/hooks/review-api-options";
import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { ReviewCandidateDetail } from "@/lib/figure-chain-types";

type ReviewCandidateDetailState = {
  requestKey: string | null;
  detail: ReviewCandidateDetail | null;
  error: DisplayableError | null;
};

export type UseReviewCandidateDetailResult = {
  detail: ReviewCandidateDetail | null;
  isLoading: boolean;
  error: DisplayableError | null;
  refresh: () => void;
};

export function useReviewCandidateDetail(
  kind: string | null,
  candidateId: number | string | null,
  options: ReviewApiOptions = {},
): UseReviewCandidateDetailResult {
  const [refreshToken, setRefreshToken] = useState(0);
  const [state, setState] = useState<ReviewCandidateDetailState>({
    requestKey: null,
    detail: null,
    error: null,
  });
  const apiBasePath = resolveReviewApiBasePath(options);
  const requestKey =
    !kind || candidateId === null
      ? null
      : `${apiBasePath}:${kind}:${String(candidateId)}:${refreshToken}`;

  useEffect(() => {
    if (requestKey === null || !kind || candidateId === null) {
      return;
    }

    const controller = new AbortController();

    fetch(
      `${apiBasePath}/candidates/${encodeURIComponent(kind)}/${encodeURIComponent(String(candidateId))}`,
      { signal: controller.signal },
    )
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        setState({
          requestKey,
          detail: body as ReviewCandidateDetail,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          requestKey,
          detail: null,
          error: parseErrorResponse(error),
        });
      });

    return () => controller.abort();
  }, [apiBasePath, candidateId, kind, requestKey]);

  const refresh = useCallback(() => {
    setRefreshToken((value) => value + 1);
  }, []);

  if (requestKey === null) {
    return { detail: null, isLoading: false, error: null, refresh };
  }

  const isLoading = state.requestKey !== requestKey;
  return {
    detail: isLoading ? null : state.detail,
    isLoading,
    error: isLoading ? null : state.error,
    refresh,
  };
}
