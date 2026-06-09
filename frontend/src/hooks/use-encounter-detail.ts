"use client";

import { useEffect, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { EncounterDetail } from "@/lib/figure-chain-types";

type EncounterDetailState = {
  encounterId: string | null;
  detail: EncounterDetail | null;
  isLoading: boolean;
  error: DisplayableError | null;
};

const detailCache = new Map<string, EncounterDetail>();

export function useEncounterDetail(
  encounterId: string | null,
): Omit<EncounterDetailState, "encounterId"> {
  const [state, setState] = useState<EncounterDetailState>({
    encounterId: null,
    detail: null,
    isLoading: false,
    error: null,
  });
  const cached = encounterId === null ? undefined : detailCache.get(encounterId);

  useEffect(() => {
    if (encounterId === null || cached) {
      return;
    }

    const controller = new AbortController();

    fetch(`/api/figure-chain/encounters/${encodeURIComponent(encounterId)}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        const detail = body as EncounterDetail;
        detailCache.set(encounterId, detail);
        setState({ encounterId, detail, isLoading: false, error: null });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          encounterId,
          detail: null,
          isLoading: false,
          error: parseErrorResponse(error),
        });
      });

    return () => controller.abort();
  }, [cached, encounterId]);

  if (encounterId === null) {
    return { detail: null, isLoading: false, error: null };
  }

  if (cached) {
    return { detail: cached, isLoading: false, error: null };
  }

  if (state.encounterId === encounterId) {
    return {
      detail: state.detail,
      isLoading: state.isLoading,
      error: state.error,
    };
  }

  return { detail: null, isLoading: true, error: null };
}
