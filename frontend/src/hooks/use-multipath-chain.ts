"use client";

import { useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  MultiPathChainRequest,
  MultiPathChainResponse,
} from "@/lib/figure-chain-types";

type MultiPathChainState = {
  result: MultiPathChainResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
};

export function useMultiPathChain() {
  const [state, setState] = useState<MultiPathChainState>({
    result: null,
    isLoading: false,
    error: null,
  });

  async function findMultiPath(request: MultiPathChainRequest): Promise<void> {
    setState({ result: null, isLoading: true, error: null });
    try {
      const response = await fetch("/api/figure-chain/chains/multipath", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      });
      const body = (await response.json()) as unknown;
      if (!response.ok) {
        throw parseErrorResponse(body);
      }
      setState({
        result: body as MultiPathChainResponse,
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

  return { ...state, findMultiPath };
}
