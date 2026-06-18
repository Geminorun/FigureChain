"use client";

import { useMemo } from "react";

import { useJsonResource } from "@/hooks/use-json-resource";
import type { DisplayableError } from "@/lib/api-errors";
import type { PersonEncounterListResponse } from "@/lib/figure-chain-types";

export type PersonEncounterQueryFilters = {
  status?: string | null;
  pathEligible?: boolean | null;
  certaintyLevel?: string | null;
  encounterKind?: string | null;
  limit?: number;
  offset?: number;
};

export type UsePersonEncountersResult = {
  response: PersonEncounterListResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
  refresh: () => void;
};

export function usePersonEncounters(
  personId: string | null,
  filters: PersonEncounterQueryFilters = {},
): UsePersonEncountersResult {
  const url = useMemo(() => buildPersonEncountersUrl(personId, filters), [personId, filters]);
  const resource = useJsonResource<PersonEncounterListResponse>(url);
  return {
    response: resource.data,
    isLoading: resource.isLoading,
    error: resource.error,
    refresh: resource.refresh,
  };
}

function buildPersonEncountersUrl(
  personId: string | null,
  filters: PersonEncounterQueryFilters,
): string | null {
  if (personId === null || personId.trim().length === 0) {
    return null;
  }
  const query = new URLSearchParams();
  if (filters.status !== undefined && filters.status !== null) {
    query.set("status", filters.status);
  }
  if (filters.pathEligible !== undefined && filters.pathEligible !== null) {
    query.set("path_eligible", String(filters.pathEligible));
  }
  if (filters.certaintyLevel !== undefined && filters.certaintyLevel !== null) {
    query.set("certainty_level", filters.certaintyLevel);
  }
  if (filters.encounterKind !== undefined && filters.encounterKind !== null) {
    query.set("encounter_kind", filters.encounterKind);
  }
  if (filters.limit !== undefined) {
    query.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    query.set("offset", String(filters.offset));
  }
  const queryString = query.toString();
  const basePath = `/api/figure-chain/people/${encodeURIComponent(personId)}/encounters`;
  return queryString ? `${basePath}?${queryString}` : basePath;
}
