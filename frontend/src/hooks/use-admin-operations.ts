"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  AdminOperationDetail,
  AdminOperationListResponse,
} from "@/lib/figure-chain-types";

export type AdminOperationFilters = {
  status?: string;
  operationType?: string;
  actor?: string;
  limit: number;
  offset: number;
};

function buildOperationsPath(filters: AdminOperationFilters): string {
  const query = new URLSearchParams();
  if (filters.status) query.set("status", filters.status);
  if (filters.operationType) query.set("operation_type", filters.operationType);
  if (filters.actor) query.set("actor", filters.actor);
  query.set("limit", String(filters.limit));
  query.set("offset", String(filters.offset));
  return `/api/figure-chain/admin/operations?${query.toString()}`;
}

export function useAdminOperations(filters: AdminOperationFilters) {
  const [data, setData] = useState<AdminOperationListResponse | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const requestKey = useMemo(() => JSON.stringify(filters), [filters]);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(buildOperationsPath(filters));
      const body: unknown = await response.json();
      if (!response.ok) {
        throw body;
      }
      setData(body as AdminOperationListResponse);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  const refresh = useCallback(async () => {
    await load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;

    async function loadOperations() {
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(buildOperationsPath(filters));
        const body: unknown = await response.json();
        if (!response.ok) {
          throw body;
        }
        if (!cancelled) {
          setData(body as AdminOperationListResponse);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(parseErrorResponse(caught));
          setData(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadOperations();
    return () => {
      cancelled = true;
    };
  }, [filters, requestKey]);

  return { data, error, isLoading, refresh };
}

export function useAdminOperationDetail(operationId: string | null) {
  const [data, setData] = useState<AdminOperationDetail | null>(null);
  const [error, setError] = useState<DisplayableError | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const load = useCallback(async () => {
    if (!operationId) {
      setData(null);
      setError(null);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/figure-chain/admin/operations/${encodeURIComponent(operationId)}`,
      );
      const body: unknown = await response.json();
      if (!response.ok) {
        throw body;
      }
      setData(body as AdminOperationDetail);
    } catch (caught) {
      setError(parseErrorResponse(caught));
      setData(null);
    } finally {
      setIsLoading(false);
    }
  }, [operationId]);

  useEffect(() => {
    let cancelled = false;

    async function loadOperation() {
      if (!operationId) {
        setData(null);
        setError(null);
        setIsLoading(false);
        return;
      }
      setIsLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `/api/figure-chain/admin/operations/${encodeURIComponent(operationId)}`,
        );
        const body: unknown = await response.json();
        if (!response.ok) {
          throw body;
        }
        if (!cancelled) {
          setData(body as AdminOperationDetail);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(parseErrorResponse(caught));
          setData(null);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadOperation();
    return () => {
      cancelled = true;
    };
  }, [operationId]);

  const refresh = useCallback(async () => {
    await load();
  }, [load]);

  return { data, error, isLoading, refresh };
}
