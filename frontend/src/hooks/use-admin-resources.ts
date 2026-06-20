"use client";

import { useCallback, useEffect, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  AdminResourceListResponse,
  AdminResourceQueryRequest,
  AdminResourceQueryResponse,
} from "@/lib/figure-chain-types";

export function useAdminResources() {
  const [data, setData] = useState<AdminResourceListResponse | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/figure-chain/admin/resources");
      const body: unknown = await response.json();
      if (!response.ok) {
        throw body;
      }
      setData(body as AdminResourceListResponse);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadResources() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/figure-chain/admin/resources");
        const body: unknown = await response.json();
        if (!response.ok) {
          throw body;
        }
        if (!cancelled) {
          setData(body as AdminResourceListResponse);
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

    void loadResources();
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, error, loading, refresh: load };
}

export function useAdminResourceQuery() {
  const [data, setData] = useState<AdminResourceQueryResponse | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [loading, setLoading] = useState(false);

  const runQuery = useCallback(async (request: AdminResourceQueryRequest) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/figure-chain/admin/resources/query", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(request),
      });
      const body: unknown = await response.json();
      if (!response.ok) {
        throw body;
      }
      setData(body as AdminResourceQueryResponse);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, error, loading, runQuery, reset };
}
