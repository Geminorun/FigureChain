"use client";

import { useJsonResource } from "@/hooks/use-json-resource";
import type { DisplayableError } from "@/lib/api-errors";
import type { PersonDetail } from "@/lib/figure-chain-types";

export type UsePersonDetailResult = {
  detail: PersonDetail | null;
  isLoading: boolean;
  error: DisplayableError | null;
  refresh: () => void;
};

export function usePersonDetail(personId: string | null): UsePersonDetailResult {
  const url =
    personId === null || personId.trim().length === 0
      ? null
      : `/api/figure-chain/people/${encodeURIComponent(personId)}`;
  const resource = useJsonResource<PersonDetail>(url);
  return {
    detail: resource.data,
    isLoading: resource.isLoading,
    error: resource.error,
    refresh: resource.refresh,
  };
}
