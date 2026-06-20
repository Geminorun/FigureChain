"use client";

import { useCallback, useState } from "react";

import {
  ADMIN_REVIEW_API_BASE_PATH,
} from "@/hooks/review-api-options";
import {
  useReviewActions,
  type UseReviewActionsResult,
} from "@/hooks/use-review-actions";
import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  AdminEncounterRetractRequest,
  AdminEncounterRetractResponse,
  AdminReviewActionResponse,
} from "@/lib/figure-chain-types";

type AdminReviewActionTarget = {
  kind: string;
  candidateId: number;
} | null;

export type UseAdminReviewActionsResult = UseReviewActionsResult<AdminReviewActionResponse> & {
  retractError: DisplayableError | null;
  isRetracting: boolean;
  retractEncounter: (
    encounterId: string,
    request: AdminEncounterRetractRequest,
  ) => Promise<AdminEncounterRetractResponse | null>;
};

export function useAdminReviewActions(
  target: AdminReviewActionTarget,
): UseAdminReviewActionsResult {
  const reviewActions = useReviewActions<AdminReviewActionResponse>(target, {
    apiBasePath: ADMIN_REVIEW_API_BASE_PATH,
  });
  const [isRetracting, setIsRetracting] = useState(false);
  const [retractError, setRetractError] = useState<DisplayableError | null>(null);

  const retractEncounter = useCallback(
    async (
      encounterId: string,
      request: AdminEncounterRetractRequest,
    ): Promise<AdminEncounterRetractResponse | null> => {
      setIsRetracting(true);
      setRetractError(null);
      try {
        const response = await fetch(
          `${ADMIN_REVIEW_API_BASE_PATH}/encounters/${encodeURIComponent(encounterId)}/retract`,
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
        return body as AdminEncounterRetractResponse;
      } catch (caught: unknown) {
        const parsed = parseErrorResponse(caught);
        setRetractError(parsed);
        return null;
      } finally {
        setIsRetracting(false);
      }
    },
    [],
  );

  return {
    ...reviewActions,
    isRetracting,
    retractError,
    retractEncounter,
  };
}
