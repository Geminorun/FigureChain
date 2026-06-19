"use client";

import { useJsonResource } from "@/hooks/use-json-resource";
import type { DisplayableError } from "@/lib/api-errors";
import type { SourceRefDetail } from "@/lib/figure-chain-types";

export type UseSourceRefDetailResult = {
  detail: SourceRefDetail | null;
  isLoading: boolean;
  error: DisplayableError | null;
  refresh: () => void;
};

export function useSourceRefDetail(sourceRefId: string | null): UseSourceRefDetailResult {
  const url =
    sourceRefId === null || sourceRefId.trim().length === 0
      ? null
      : `/api/figure-chain/source-refs/${encodeURIComponent(sourceRefId)}`;
  const resource = useJsonResource<SourceRefDetail>(url);
  return {
    detail: resource.data,
    isLoading: resource.isLoading,
    error: resource.error,
    refresh: resource.refresh,
  };
}
