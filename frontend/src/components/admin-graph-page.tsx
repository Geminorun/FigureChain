"use client";

import Link from "next/link";

import { ErrorCallout } from "@/components/error-callout";
import {
  useAdminGraphAction,
  useAdminGraphStatus,
} from "@/hooks/use-admin-graph";
import type { AdminGraphBatchSummary } from "@/lib/figure-chain-types";

function formatDate(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

function BatchTable({
  latestSuccess,
  latestFailed,
}: {
  latestSuccess: AdminGraphBatchSummary | null;
  latestFailed: AdminGraphBatchSummary | null;
}) {
  const rows = [
    { label: "最新成功", batch: latestSuccess },
    { label: "最新失败", batch: latestFailed },
  ].filter((row) => row.batch !== null);

  if (rows.length === 0) {
    return (
      <div className="rounded border border-dashed border-stone-300 bg-stone-50 p-4 text-sm text-stone-600">
        暂无 graph projection batch。
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-stone-200 bg-white">
      <table className="min-w-full divide-y divide-stone-200 text-left text-sm">
        <thead className="bg-stone-100 text-xs font-semibold text-stone-600">
          <tr>
            <th className="px-3 py-2">类型</th>
            <th className="px-3 py-2">批次 ID</th>
            <th className="px-3 py-2">模式</th>
            <th className="px-3 py-2">状态</th>
            <th className="px-3 py-2">关系写入</th>
            <th className="px-3 py-2">校验状态</th>
            <th className="px-3 py-2">开始时间</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {rows.map(({ label, batch }) => {
            const value = batch as AdminGraphBatchSummary;
            return (
              <tr key={label}>
                <td className="px-3 py-2 font-medium text-stone-800">{label}</td>
                <td className="px-3 py-2 font-mono text-xs text-stone-700">
                  {value.id}
                </td>
                <td className="px-3 py-2 text-stone-700">{value.mode}</td>
                <td className="px-3 py-2 text-stone-700">{value.status}</td>
                <td className="px-3 py-2 text-stone-700">
                  {value.relationships_written}
                </td>
                <td className="px-3 py-2 text-stone-700">
                  {value.validation_status}
                </td>
                <td className="px-3 py-2 text-stone-700">
                  {formatDate(value.started_at)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function AdminGraphPage() {
  const status = useAdminGraphStatus();
  const action = useAdminGraphAction();

  return (
    <section className="space-y-5">
      <div className="border-b border-stone-200 pb-4">
        <p className="text-sm font-medium text-amber-700">图同步</p>
        <h2 className="mt-1 text-xl font-semibold text-stone-950">
          Neo4j 投影控制台
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          PostgreSQL 仍是事实源；本页只触发既有图投影和校验服务。
        </p>
      </div>

      {status.error ? <ErrorCallout error={status.error} /> : null}
      {action.error ? <ErrorCallout error={action.error} /> : null}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded border border-stone-200 bg-white p-4">
          <p className="text-sm text-stone-600">Active Encounter</p>
          <p className="mt-2 text-3xl font-semibold text-stone-950">
            {status.data?.active_encounter_count ?? "加载中"}
          </p>
        </div>
        <div className="rounded border border-stone-200 bg-white p-4">
          <p className="text-sm text-stone-600">Path Eligible Encounter</p>
          <p className="mt-2 text-3xl font-semibold text-stone-950">
            {status.data?.path_eligible_encounter_count ?? "加载中"}
          </p>
        </div>
      </div>

      <BatchTable
        latestFailed={status.data?.latest_failed ?? null}
        latestSuccess={status.data?.latest_success ?? null}
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="rounded border border-stone-200 bg-white p-4">
          <h3 className="font-semibold text-stone-950">图操作</h3>
          <p className="mt-1 text-sm text-stone-600">
            全量重建会清空并重写 Neo4j FigureChain 投影。
          </p>
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <button
              className="rounded border border-stone-300 px-3 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100 disabled:opacity-60"
              disabled={action.loading}
              onClick={() => void action.validateEncounters("local")}
              type="button"
            >
              校验 Encounter
            </button>
            <button
              className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm font-medium text-red-900 hover:bg-red-100 disabled:opacity-60"
              disabled={action.loading}
              onClick={() => void action.syncGraph("rebuild", "local")}
              type="button"
            >
              全量重建同步
            </button>
            <button
              className="rounded border border-stone-300 px-3 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100 disabled:opacity-60"
              disabled={action.loading}
              onClick={() => void action.syncGraph("incremental", "local")}
              type="button"
            >
              增量同步
            </button>
            <button
              className="rounded border border-stone-300 px-3 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100 disabled:opacity-60"
              disabled={action.loading}
              onClick={() => void action.validateGraph("local")}
              type="button"
            >
              校验图投影
            </button>
          </div>
          {action.data ? (
            <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
              <p className="font-medium">已创建后台操作</p>
              <Link
                className="mt-1 block font-mono text-xs underline-offset-2 hover:underline"
                href={`/admin/operations?operation_id=${action.data.operation_id}`}
              >
                {action.data.operation_id}
              </Link>
              <code className="mt-2 block break-words rounded bg-white/70 p-2 text-xs">
                {action.data.preview}
              </code>
            </div>
          ) : null}
        </section>

        <section className="rounded border border-stone-200 bg-white p-4">
          <h3 className="font-semibold text-stone-950">长期运行操作</h3>
          <p className="mt-1 text-sm text-stone-600">
            进程中断后可能留下 running 状态，需要人工确认。
          </p>
          <div className="mt-3 space-y-2">
            {(status.data?.stale_running_operations ?? []).length === 0 ? (
              <p className="text-sm text-stone-600">暂无 stale running operation。</p>
            ) : (
              status.data?.stale_running_operations.map((operation) => (
                <Link
                  className="block break-words rounded border border-stone-200 p-2 font-mono text-xs text-amber-800 underline-offset-2 hover:bg-stone-50 hover:underline"
                  href={`/admin/operations?operation_id=${operation.operation_id}`}
                  key={operation.operation_id}
                >
                  {operation.operation_id}
                </Link>
              ))
            )}
          </div>
        </section>
      </div>
    </section>
  );
}
