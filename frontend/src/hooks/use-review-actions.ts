"use client";

import { useCallback, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { ReviewActionRequest, ReviewActionResponse } from "@/lib/figure-chain-types";

type ReviewActionTarget = {
  kind: string;
  candidateId: number;
} | null;

export type UseReviewActionsResult = {
  error: DisplayableError | null;
  isSubmitting: boolean;
  markNeedsReview: (request: ReviewActionRequest) => Promise<ReviewActionResponse | null>;
  promote: (request: ReviewActionRequest) => Promise<ReviewActionResponse | null>;
  reject: (request: ReviewActionRequest) => Promise<ReviewActionResponse | null>;
};

export function useReviewActions(target: ReviewActionTarget): UseReviewActionsResult {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<DisplayableError | null>(null);

  const postAction = useCallback(
    async (
      action: "promote" | "reject" | "needs-review",
      request: ReviewActionRequest,
    ): Promise<ReviewActionResponse | null> => {
      if (target === null) {
        return null;
      }
      setIsSubmitting(true);
      setError(null);
      try {
        const response = await fetch(
          `/api/figure-chain/review/candidates/${encodeURIComponent(target.kind)}/${encodeURIComponent(String(target.candidateId))}/${action}`,
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
        return body as ReviewActionResponse;
      } catch (caught: unknown) {
        const parsed = parseErrorResponse(caught);
        setError(parsed);
        return null;
      } finally {
        setIsSubmitting(false);
      }
    },
    [target],
  );

  return {
    error,
    isSubmitting,
    markNeedsReview: (request) => postAction("needs-review", request),
    promote: (request) => postAction("promote", request),
    reject: (request) => postAction("reject", request),
  };
}
