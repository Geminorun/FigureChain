"use client";

import { useCallback, useState } from "react";

import { resolveReviewApiBasePath, type ReviewApiOptions } from "@/hooks/review-api-options";
import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { ReviewActionRequest, ReviewActionResponse } from "@/lib/figure-chain-types";

type ReviewActionTarget = {
  kind: string;
  candidateId: number;
} | null;

export type UseReviewActionsResult<TActionResponse = ReviewActionResponse> = {
  error: DisplayableError | null;
  isSubmitting: boolean;
  markNeedsReview: (request: ReviewActionRequest) => Promise<TActionResponse | null>;
  promote: (request: ReviewActionRequest) => Promise<TActionResponse | null>;
  reject: (request: ReviewActionRequest) => Promise<TActionResponse | null>;
};

export function useReviewActions<TActionResponse = ReviewActionResponse>(
  target: ReviewActionTarget,
  options: ReviewApiOptions = {},
): UseReviewActionsResult<TActionResponse> {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<DisplayableError | null>(null);
  const apiBasePath = resolveReviewApiBasePath(options);

  const postAction = useCallback(
    async (
      action: "promote" | "reject" | "needs-review",
      request: ReviewActionRequest,
    ): Promise<TActionResponse | null> => {
      if (target === null) {
        return null;
      }
      setIsSubmitting(true);
      setError(null);
      try {
        const response = await fetch(
          `${apiBasePath}/candidates/${encodeURIComponent(target.kind)}/${encodeURIComponent(String(target.candidateId))}/${action}`,
          {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(request),
          },
        );
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        return body as TActionResponse;
      } catch (caught: unknown) {
        const parsed = parseErrorResponse(caught);
        setError(parsed);
        return null;
      } finally {
        setIsSubmitting(false);
      }
    },
    [apiBasePath, target],
  );

  return {
    error,
    isSubmitting,
    markNeedsReview: (request) => postAction("needs-review", request),
    promote: (request) => postAction("promote", request),
    reject: (request) => postAction("reject", request),
  };
}
