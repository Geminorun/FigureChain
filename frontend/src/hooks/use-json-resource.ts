"use client";

import { useEffect, useMemo, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";

type ResourceState<T> = {
  url: string | null;
  refreshKey: number;
  data: T | null;
  error: DisplayableError | null;
};

export type JsonResourceResult<T> = {
  data: T | null;
  isLoading: boolean;
  error: DisplayableError | null;
  refresh: () => void;
};

export function useJsonResource<T>(url: string | null): JsonResourceResult<T> {
  const [refreshKey, setRefreshKey] = useState(0);
  const [state, setState] = useState<ResourceState<T>>({
    url: null,
    refreshKey: 0,
    data: null,
    error: null,
  });

  useEffect(() => {
    if (url === null) {
      return;
    }

    const controller = new AbortController();

    fetch(url, { signal: controller.signal })
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        setState({
          url,
          refreshKey,
          data: body as T,
          error: null,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          url,
          refreshKey,
          data: null,
          error: parseErrorResponse(error),
        });
      });

    return () => controller.abort();
  }, [refreshKey, url]);

  return useMemo(
    () => {
      if (url === null) {
        return {
          data: null,
          isLoading: false,
          error: null,
          refresh: () => setRefreshKey((value) => value + 1),
        };
      }
      const isCurrent = state.url === url && state.refreshKey === refreshKey;
      return {
        data: state.url === url ? state.data : null,
        isLoading: !isCurrent,
        error: isCurrent ? state.error : null,
        refresh: () => setRefreshKey((value) => value + 1),
      };
    },
    [refreshKey, state.data, state.error, state.refreshKey, state.url, url],
  );
}
