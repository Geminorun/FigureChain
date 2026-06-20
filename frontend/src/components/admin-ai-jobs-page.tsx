"use client";

import Link from "next/link";
import { useState } from "react";

import { ErrorCallout } from "@/components/error-callout";
import {
  type AdminAIJobFilters,
  useAdminAIJobActions,
  useAdminAIJobEvents,
  useAdminAIJobHealth,
  useAdminAIJobs,
} from "@/hooks/use-admin-ai-jobs";
import type { AiJobResponse } from "@/lib/figure-chain-types";

const STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  running: "运行中",
  succeeded: "已成功",
  failed: "已失败",
  cancelled: "已取消",
};

function formatDate(value: string | null): string {
  if (!value) {
    return "未记录";
  }
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

export function AdminAIJobsPage() {
  const [filters, setFilters] = useState<AdminAIJobFilters>({
    limit: 50,
    offset: 0,
  });
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const health = useAdminAIJobHealth();
  const jobs = useAdminAIJobs(filters);
  const actions = useAdminAIJobActions();
  const effectiveSelectedJobId = selectedJobId ?? jobs.data?.items[0]?.id ?? null;
  const events = useAdminAIJobEvents(effectiveSelectedJobId);
  const selectedJob =
    jobs.data?.items.find((item) => item.id === effectiveSelectedJobId) ?? null;

  async function runAction(action: "cancel" | "retry" | "requeue") {
    if (action === "requeue") {
      await actions.requeueJobs("local", filters.limit ?? 50);
      return;
    }
    if (selectedJob === null) {
      return;
    }
    if (action === "cancel") {
      await actions.cancelJob(selectedJob.id, "local");
    } else {
      await actions.retryJob(selectedJob.id, "local");
    }
  }

  return (
    <section className="space-y-5">
      <div className="border-b border-stone-200 pb-4">
        <p className="text-sm font-medium text-amber-700">AI job</p>
        <h2 className="mt-1 text-xl font-semibold text-stone-950">
          AI 任务控制台
        </h2>
        <p className="mt-1 text-sm text-stone-600">
          查看任务、事件、队列健康和 worker heartbeat；写操作统一记录到后台操作。
        </p>
      </div>

      {health.error ? <ErrorCallout error={health.error} /> : null}
      {jobs.error ? <ErrorCallout error={jobs.error} /> : null}
      {events.error ? <ErrorCallout error={events.error} /> : null}
      {actions.error ? <ErrorCallout error={actions.error} /> : null}

      <HealthStrip health={health.data} />

      <section className="rounded border border-stone-200 bg-white p-4">
        <h3 className="font-semibold text-stone-950">筛选</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-5">
          <label className="text-sm font-medium text-stone-700">
            任务状态
            <select
              className="mt-1 w-full rounded border border-stone-300 px-2 py-2 text-sm"
              onChange={(event) =>
                setFilters((current) => ({ ...current, status: event.target.value || undefined }))
              }
              value={filters.status ?? ""}
            >
              <option value="">全部</option>
              <option value="queued">排队中</option>
              <option value="running">运行中</option>
              <option value="succeeded">已成功</option>
              <option value="failed">已失败</option>
              <option value="cancelled">已取消</option>
            </select>
          </label>
          <label className="text-sm font-medium text-stone-700">
            目标类型
            <select
              className="mt-1 w-full rounded border border-stone-300 px-2 py-2 text-sm"
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  target_kind: event.target.value || undefined,
                }))
              }
              value={filters.target_kind ?? ""}
            >
              <option value="">全部</option>
              <option value="relationship">关系候选</option>
              <option value="kinship">亲属候选</option>
            </select>
          </label>
          <label className="text-sm font-medium text-stone-700">
            目标 ID
            <input
              className="mt-1 w-full rounded border border-stone-300 px-2 py-2 text-sm"
              min={1}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  target_id: event.target.value ? Number(event.target.value) : null,
                }))
              }
              type="number"
              value={filters.target_id ?? ""}
            />
          </label>
          <label className="text-sm font-medium text-stone-700">
            队列后端
            <select
              className="mt-1 w-full rounded border border-stone-300 px-2 py-2 text-sm"
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  queue_backend: event.target.value || undefined,
                }))
              }
              value={filters.queue_backend ?? ""}
            >
              <option value="">全部</option>
              <option value="database">数据库</option>
              <option value="rq">RQ</option>
            </select>
          </label>
          <label className="text-sm font-medium text-stone-700">
            每页数量
            <select
              className="mt-1 w-full rounded border border-stone-300 px-2 py-2 text-sm"
              onChange={(event) =>
                setFilters((current) => ({ ...current, limit: Number(event.target.value) }))
              }
              value={filters.limit ?? 50}
            >
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_26rem]">
        <section className="overflow-hidden rounded border border-stone-200 bg-white">
          <div className="border-b border-stone-200 px-4 py-3">
            <h3 className="font-semibold text-stone-950">任务列表</h3>
            <p className="mt-1 text-sm text-stone-600">
              {jobs.loading ? "加载中" : `共 ${jobs.data?.count ?? 0} 条`}
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-stone-200 text-left text-sm">
              <thead className="bg-stone-100 text-xs font-semibold text-stone-600">
                <tr>
                  <th className="px-3 py-2">任务 ID</th>
                  <th className="px-3 py-2">目标</th>
                  <th className="px-3 py-2">状态</th>
                  <th className="px-3 py-2">队列</th>
                  <th className="px-3 py-2">尝试</th>
                  <th className="px-3 py-2">Worker</th>
                  <th className="px-3 py-2">Heartbeat</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {(jobs.data?.items ?? []).map((job) => (
                  <tr
                    className={job.id === effectiveSelectedJobId ? "bg-amber-50" : "bg-white"}
                    key={job.id}
                  >
                    <td className="px-3 py-2">
                      <button
                        className="break-all font-mono text-xs text-amber-800 underline-offset-2 hover:underline"
                        onClick={() => setSelectedJobId(job.id)}
                        type="button"
                      >
                        {job.id}
                      </button>
                    </td>
                    <td className="px-3 py-2 text-stone-700">{targetLabel(job)}</td>
                    <td className="px-3 py-2 text-stone-700">{statusLabel(job.status)}</td>
                    <td className="px-3 py-2 text-stone-700">{job.queue_backend}</td>
                    <td className="px-3 py-2 text-stone-700">
                      {job.attempt_count}/{job.max_attempts}
                    </td>
                    <td className="px-3 py-2 text-stone-700">
                      {job.worker_id ?? "未分配"}
                    </td>
                    <td className="px-3 py-2 text-stone-700">
                      {formatDate(job.heartbeat_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded border border-stone-200 bg-white p-4">
            <h3 className="font-semibold text-stone-950">任务事件</h3>
            {selectedJob === null ? (
              <p className="mt-3 text-sm text-stone-600">请选择一个任务。</p>
            ) : (
              <div className="mt-3 space-y-2">
                <p className="break-all font-mono text-xs text-stone-600">
                  {selectedJob.id}
                </p>
                {(events.data?.items ?? []).map((event) => (
                  <div
                    className="rounded border border-stone-200 p-2 text-sm"
                    key={event.id}
                  >
                    <p className="font-medium text-stone-900">{event.event_type}</p>
                    <p className="text-stone-600">{event.message ?? "无消息"}</p>
                    <p className="text-xs text-stone-500">{formatDate(event.created_at)}</p>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="rounded border border-stone-200 bg-white p-4">
            <h3 className="font-semibold text-stone-950">操作</h3>
            <div className="mt-3 grid gap-2">
              {selectedJob && canCancel(selectedJob.status) ? (
                <button
                  className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm font-medium text-red-900 hover:bg-red-100 disabled:opacity-60"
                  disabled={actions.loading}
                  onClick={() => void runAction("cancel")}
                  type="button"
                >
                  取消任务
                </button>
              ) : null}
              {selectedJob && canRetry(selectedJob.status) ? (
                <button
                  className="rounded border border-stone-300 px-3 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100 disabled:opacity-60"
                  disabled={actions.loading}
                  onClick={() => void runAction("retry")}
                  type="button"
                >
                  重试任务
                </button>
              ) : null}
              <button
                className="rounded border border-stone-300 px-3 py-2 text-sm font-medium text-stone-800 hover:bg-stone-100 disabled:opacity-60"
                disabled={actions.loading}
                onClick={() => void runAction("requeue")}
                type="button"
              >
                重新入队可恢复任务
              </button>
            </div>
            {actions.data ? (
              <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
                <p className="font-medium">已记录后台操作</p>
                <Link
                  className="mt-1 block break-all font-mono text-xs underline-offset-2 hover:underline"
                  href={`/admin/operations?operation_id=${actions.data.operation_id}`}
                >
                  {actions.data.operation_id}
                </Link>
                <code className="mt-2 block break-words rounded bg-white/70 p-2 text-xs">
                  {actions.data.preview}
                </code>
              </div>
            ) : null}
          </section>
        </aside>
      </div>
    </section>
  );
}

function HealthStrip({ health }: { health: ReturnType<typeof useAdminAIJobHealth>["data"] }) {
  const items = [
    ["排队中", health?.queued_count],
    ["运行中", health?.running_count],
    ["长期运行", health?.stale_running_count],
    ["已失败", health?.failed_count],
    ["已取消", health?.cancelled_count],
  ];
  return (
    <div className="grid gap-3 md:grid-cols-5">
      {items.map(([label, value]) => (
        <div className="rounded border border-stone-200 bg-white p-4" key={String(label)}>
          <p className="text-sm text-stone-600">{label}</p>
          <p className="mt-2 text-3xl font-semibold text-stone-950">
            {typeof value === "number" ? value : "加载中"}
          </p>
        </div>
      ))}
    </div>
  );
}

function targetLabel(job: AiJobResponse): string {
  return `${job.target_type}:${job.target_kind}#${job.target_id}`;
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

function canCancel(status: string): boolean {
  return status === "queued" || status === "running";
}

function canRetry(status: string): boolean {
  return status === "failed" || status === "cancelled";
}
