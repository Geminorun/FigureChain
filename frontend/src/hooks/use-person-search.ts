"use client";

import { useEffect, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  PeopleSearchResponse,
  PersonSearchItem,
} from "@/lib/figure-chain-types";

type PersonSearchResult = {
  items: PersonSearchItem[];
  isLoading: boolean;
  error: DisplayableError | null;
};

type PersonSearchState = PersonSearchResult & {
  query: string;
};

export function usePersonSearch(query: string, limit = 10): PersonSearchResult {
  const trimmedQuery = query.trim();
  const [state, setState] = useState<PersonSearchState>({
    query: "",
    items: [],
    isLoading: false,
    error: null,
  });

  useEffect(() => {
    if (trimmedQuery.length === 0) {
      return;
    }

    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      setState({
        query: trimmedQuery,
        items: [],
        isLoading: true,
        error: null,
      });

      const params = new URLSearchParams({
        q: trimmedQuery,
        limit: String(limit),
      });

      fetch(`/api/figure-chain/people/search?${params.toString()}`, {
        signal: controller.signal,
      })
        .then(async (response) => {
          const body = (await response.json()) as unknown;
          if (!response.ok) {
            throw parseErrorResponse(body);
          }
          const data = body as PeopleSearchResponse;
          setState({
            query: trimmedQuery,
            items: data.items,
            isLoading: false,
            error: null,
          });
        })
        .catch((error: unknown) => {
          if (controller.signal.aborted) {
            return;
          }
          setState({
            query: trimmedQuery,
            items: [],
            isLoading: false,
            error: parseErrorResponse(error),
          });
        });
    }, 300);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [trimmedQuery, limit]);

  if (trimmedQuery.length === 0) {
    return { items: [], isLoading: false, error: null };
  }

  if (state.query !== trimmedQuery) {
    return { items: [], isLoading: true, error: null };
  }

  return state;
}
