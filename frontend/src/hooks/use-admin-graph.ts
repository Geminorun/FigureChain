"use client";

import { useCallback, useEffect, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  AdminGraphOperationResponse,
  AdminGraphStatusResponse,
} from "@/lib/figure-chain-types";

type GraphSyncMode = "rebuild" | "incremental";

export function useAdminGraphStatus() {
  const [data, setData] = useState<AdminGraphStatusResponse | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/figure-chain/admin/graph/status");
      const body: unknown = await response.json();
      if (!response.ok) {
        throw body;
      }
      setData(body as AdminGraphStatusResponse);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadStatus() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/figure-chain/admin/graph/status");
        const body: unknown = await response.json();
        if (!response.ok) {
          throw body;
        }
        if (!cancelled) {
          setData(body as AdminGraphStatusResponse);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(parseErrorResponse(caught));
          setData(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadStatus();
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, error, loading, refresh };
}

export function useAdminGraphAction() {
  const [data, setData] = useState<AdminGraphOperationResponse | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [loading, setLoading] = useState(false);

  const postAction = useCallback(async (path: string, body: object) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const responseBody: unknown = await response.json();
      if (!response.ok) {
        throw responseBody;
      }
      setData(responseBody as AdminGraphOperationResponse);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const validateEncounters = useCallback(
    async (actor: string) =>
      postAction("/api/figure-chain/admin/graph/validate-encounters", { actor }),
    [postAction],
  );

  const syncGraph = useCallback(
    async (mode: GraphSyncMode, actor: string) =>
      postAction("/api/figure-chain/admin/graph/sync", { mode, actor }),
    [postAction],
  );

  const validateGraph = useCallback(
    async (actor: string) =>
      postAction("/api/figure-chain/admin/graph/validate-graph", { actor }),
    [postAction],
  );

  return {
    data,
    error,
    loading,
    validateEncounters,
    syncGraph,
    validateGraph,
  };
}
