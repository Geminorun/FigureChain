"use client";

import { useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  ShortestChainRequest,
  ShortestChainResponse,
} from "@/lib/figure-chain-types";

type ShortestChainState = {
  result: ShortestChainResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
};

export function useShortestChain() {
  const [state, setState] = useState<ShortestChainState>({
    result: null,
    isLoading: false,
    error: null,
  });

  async function findShortestChain(request: ShortestChainRequest): Promise<void> {
    setState({ result: null, isLoading: true, error: null });
    try {
      const response = await fetch("/api/figure-chain/chains/shortest", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      });
      const body = (await response.json()) as unknown;
      if (!response.ok) {
        throw parseErrorResponse(body);
      }
      setState({
        result: body as ShortestChainResponse,
        isLoading: false,
        error: null,
      });
    } catch (error: unknown) {
      setState({
        result: null,
        isLoading: false,
        error: parseErrorResponse(error),
      });
    }
  }

  return {
    ...state,
    findShortestChain,
  };
}
