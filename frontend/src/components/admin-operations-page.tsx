"use client";

import { RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import {
  type AdminOperationFilters,
  useAdminOperations,
} from "@/hooks/use-admin-operations";

const DEFAULT_FILTERS: AdminOperationFilters = {
  limit: 50,
  offset: 0,
};

function formatJson(value: Record<string, unknown>): string {
  const entries = Object.keys(value);
  if (entries.length === 0) {
    return "无";
  }
  return JSON.stringify(value);
}

function formatRelatedResource(type: string | null, id: string | null): string {
  if (!type && !id) {
    return "无";
  }
  return [type, id].filter(Boolean).join(" / ");
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

export function AdminOperationsPage() {
  const [filters] = useState<AdminOperationFilters>(DEFAULT_FILTERS);
  const stableFilters = useMemo(() => filters, [filters]);
  const { data, error, isLoading, refresh } = useAdminOperations(stableFilters);

  return (
    <section className="space-y-4">
      <div className="flex flex-col justify-between gap-3 border-b border-stone-200 pb-4 sm:flex-row sm:items-end">
        <div>
          <p className="text-sm font-medium text-amber-700">操作历史</p>
          <h2 className="mt-1 text-xl font-semibold text-stone-950">
            后台操作记录
          </h2>
          <p className="mt-1 text-sm text-stone-600">
            查看图同步、AI 任务和人工维护动作的本地审计记录。
          </p>
        </div>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 rounded border border-stone-300 bg-white px-3 text-sm font-medium text-stone-900 hover:bg-stone-100 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isLoading}
          onClick={() => void refresh()}
          type="button"
        >
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
          刷新
        </button>
      </div>

      {error ? <ErrorCallout error={error} /> : null}

      {isLoading && !data ? (
        <p className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
          正在加载操作历史...
        </p>
      ) : null}

      {data && data.items.length === 0 ? (
        <EmptyState
          description="后台操作执行后会在这里留下审计记录。"
          title="暂无后台操作"
        />
      ) : null}

      {data && data.items.length > 0 ? (
        <div className="overflow-x-auto rounded border border-stone-200 bg-white">
          <table className="min-w-full divide-y divide-stone-200 text-left text-sm">
            <thead className="bg-stone-100 text-xs font-semibold uppercase text-stone-600">
              <tr>
                <th className="px-4 py-3">操作</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3">操作者</th>
                <th className="px-4 py-3">关联资源</th>
                <th className="px-4 py-3">结果</th>
                <th className="px-4 py-3">更新时间</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {data.items.map((operation) => (
                <tr className="align-top" key={operation.operation_id}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-stone-950">
                      {operation.operation_type}
                    </p>
                    <p className="mt-1 font-mono text-xs text-stone-500">
                      {operation.operation_id}
                    </p>
                  </td>
                  <td className="px-4 py-3 text-stone-800">
                    {operation.status}
                  </td>
                  <td className="px-4 py-3 text-stone-800">
                    {operation.actor}
                  </td>
                  <td className="px-4 py-3 text-stone-700">
                    {formatRelatedResource(
                      operation.related_resource_type,
                      operation.related_resource_id,
                    )}
                  </td>
                  <td className="max-w-md px-4 py-3">
                    <code className="whitespace-pre-wrap break-words text-xs text-stone-700">
                      {operation.error_message ??
                        formatJson(operation.result_summary)}
                    </code>
                  </td>
                  <td className="px-4 py-3 text-stone-700">
                    {formatDateTime(operation.updated_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
