"use client";

import { useEffect, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type { AIChainExplanation } from "@/lib/figure-chain-types";

type ChainExplanationState = {
  chainHash: string | null;
  explanation: AIChainExplanation | null;
  error: DisplayableError | null;
};

type UseChainExplanationResult = {
  explanation: AIChainExplanation | null;
  isLoading: boolean;
  error: DisplayableError | null;
};

export function useChainExplanation(chainHash: string | null): UseChainExplanationResult {
  const [state, setState] = useState<ChainExplanationState>({
    chainHash: null,
    explanation: null,
    error: null,
  });

  useEffect(() => {
    if (!chainHash) {
      return;
    }

    let cancelled = false;

    fetch(`/api/figure-chain/ai/chains/explanations/${encodeURIComponent(chainHash)}`)
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        if (!cancelled) {
          setState({
            chainHash,
            explanation: body as AIChainExplanation,
            error: null,
          });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({
            chainHash,
            explanation: null,
            error: parseErrorResponse(error),
          });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [chainHash]);

  if (!chainHash) {
    return { explanation: null, isLoading: false, error: null };
  }
  if (state.chainHash !== chainHash) {
    return { explanation: null, isLoading: true, error: null };
  }
  return { explanation: state.explanation, isLoading: false, error: state.error };
}
