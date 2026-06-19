"use client";

import { useJsonResource } from "@/hooks/use-json-resource";
import type { DisplayableError } from "@/lib/api-errors";
import type { SourceWorkDetail } from "@/lib/figure-chain-types";

export type UseSourceWorkDetailResult = {
  detail: SourceWorkDetail | null;
  isLoading: boolean;
  error: DisplayableError | null;
  refresh: () => void;
};

export function useSourceWorkDetail(sourceWorkId: string | null): UseSourceWorkDetailResult {
  const url =
    sourceWorkId === null || sourceWorkId.trim().length === 0
      ? null
      : `/api/figure-chain/source-works/${encodeURIComponent(sourceWorkId)}`;
  const resource = useJsonResource<SourceWorkDetail>(url);
  return {
    detail: resource.data,
    isLoading: resource.isLoading,
    error: resource.error,
    refresh: resource.refresh,
  };
}
