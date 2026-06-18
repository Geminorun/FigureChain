"use client";

import { useCallback, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  ChainShareCreateRequest,
  ChainShareCreateResponse,
  ChainShareDetail,
  MarkdownExportRequest,
  MarkdownExportResponse,
} from "@/lib/figure-chain-types";

type ChainShareState = {
  isLoading: boolean;
  error: DisplayableError | null;
};

export type ChainShareHook = ChainShareState & {
  createShare: (request: ChainShareCreateRequest) => Promise<ChainShareCreateResponse>;
  loadShare: (shareSlug: string, signal?: AbortSignal) => Promise<ChainShareDetail>;
  exportMarkdown: (request: MarkdownExportRequest) => Promise<MarkdownExportResponse>;
};

export function useChainShare(): ChainShareHook {
  const [state, setState] = useState<ChainShareState>({
    isLoading: false,
    error: null,
  });

  const requestJson = useCallback(
    async <TResponse,>(
      url: string,
      init: RequestInit,
      signal?: AbortSignal,
    ): Promise<TResponse> => {
      setState({ isLoading: true, error: null });
      try {
        const response = await fetch(url, { ...init, signal });
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        setState({ isLoading: false, error: null });
        return body as TResponse;
      } catch (error: unknown) {
        if (signal?.aborted) {
          throw error;
        }
        const parsed = parseErrorResponse(error);
        setState({ isLoading: false, error: parsed });
        throw parsed;
      }
    },
    [],
  );

  const createShare = useCallback(
    (request: ChainShareCreateRequest) =>
      requestJson<ChainShareCreateResponse>("/api/figure-chain/chains/share", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      }),
    [requestJson],
  );
  const loadShare = useCallback(
    (shareSlug: string, signal?: AbortSignal) =>
      requestJson<ChainShareDetail>(
        `/api/figure-chain/chains/share/${encodeURIComponent(shareSlug)}`,
        { method: "GET" },
        signal,
      ),
    [requestJson],
  );
  const exportMarkdown = useCallback(
    (request: MarkdownExportRequest) =>
      requestJson<MarkdownExportResponse>("/api/figure-chain/chains/export/markdown", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      }),
    [requestJson],
  );

  return {
    isLoading: state.isLoading,
    error: state.error,
    createShare,
    loadShare,
    exportMarkdown,
  };
}
