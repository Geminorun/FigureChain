"use client";

import { Bot, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import type { DisplayableError } from "@/lib/api-errors";
import type {
  AiJobEvent,
  AiJobResponse,
  ReviewAiJobSummary,
  ReviewCandidateDetail,
} from "@/lib/figure-chain-types";

type ReviewAiPanelProps = {
  activeJob: AiJobResponse | null;
  detail: ReviewCandidateDetail | null;
  error: DisplayableError | null;
  isCreating: boolean;
  jobs: AiJobResponse[];
  eventsByJobId: Record<string, AiJobEvent[]>;
  onCreateJob: (options: { createdBy: string }) => Promise<AiJobResponse | null>;
  onCancelJob: (
    jobId: string,
    options: { cancelledBy: string },
  ) => Promise<AiJobResponse | null>;
  onRetryJob: (
    jobId: string,
    options: { createdBy: string },
  ) => Promise<AiJobResponse | null>;
  onLoadEvents: (jobId: string) => Promise<AiJobEvent[]>;
  onRefreshCandidate: () => void;
};

type JobLike = AiJobResponse | ReviewAiJobSummary;

function jobId(job: JobLike): string {
  return "id" in job ? job.id : job.run_id;
}

function jobPurpose(job: JobLike): string {
  return "job_type" in job ? job.job_type : job.purpose;
}

function jobCreatedAt(job: JobLike): string | null {
  return job.created_at;
}

function isAiJobResponse(job: JobLike): job is AiJobResponse {
  return "queue_backend" in job;
}

function isActiveWorkerStatus(status: string): boolean {
  return status === "queued" || status === "running";
}

function isFailedWorkerStatus(status: string): boolean {
  return status === "failed";
}

export function ReviewAiPanel({
  activeJob,
  detail,
  error,
  isCreating,
  jobs,
  eventsByJobId,
  onCreateJob,
  onCancelJob,
  onRetryJob,
  onLoadEvents,
  onRefreshCandidate,
}: ReviewAiPanelProps) {
  const [createdBy, setCreatedBy] = useState("");
  const refreshedJobs = useRef(new Set<string>());
  const suggestion = detail?.latest_ai_suggestion ?? null;
  const history: JobLike[] = jobs.length > 0 ? jobs : detail?.ai_jobs ?? [];
  const canCreate = detail !== null && !isCreating && createdBy.trim().length > 0;

  useEffect(() => {
    if (activeJob?.status !== "succeeded") {
      return;
    }
    if (refreshedJobs.current.has(activeJob.id)) {
      return;
    }
    refreshedJobs.current.add(activeJob.id);
    onRefreshCandidate();
  }, [activeJob, onRefreshCandidate]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate) {
      return;
    }
    await onCreateJob({ createdBy: createdBy.trim() });
  }

  return (
    <section className="rounded border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <Bot aria-hidden="true" className="mt-0.5 h-5 w-5 text-stone-700" />
        <div>
          <h2 className="text-base font-semibold text-stone-950">AI 建议</h2>
          <p className="mt-1 text-sm text-stone-600">
            针对当前候选生成审核建议，结果只作为人工审核输入。
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-4">
        {error ? <ErrorCallout error={error} /> : null}
        {detail === null ? (
          <EmptyState title="尚未选择候选" description="选择候选后可查看或生成 AI 建议。" />
        ) : null}

        {activeJob && isActiveWorkerStatus(activeJob.status) ? (
          <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
            AI worker 已排队或执行中，结果生成后会刷新详情。
          </div>
        ) : null}

        {activeJob && isFailedWorkerStatus(activeJob.status) ? (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900">
            AI job failed: {activeJob.error_message ?? activeJob.error_code ?? "unknown"}
          </div>
        ) : null}

        <form className="grid gap-3 sm:grid-cols-[1fr_auto]" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-stone-800">
            created_by
            <input
              className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              type="text"
              value={createdBy}
              onChange={(event) => setCreatedBy(event.target.value)}
            />
          </label>
          <div className="flex items-end">
            <button
              className="inline-flex min-h-10 items-center gap-2 rounded bg-stone-950 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-stone-300"
              disabled={!canCreate}
              type="submit"
            >
              <Send aria-hidden="true" className="h-4 w-4" />
              {isCreating ? "提交中..." : "生成 AI 建议"}
            </button>
          </div>
        </form>

        {suggestion ? (
          <div className="border-t border-stone-200 pt-4">
            <p className="text-sm font-medium text-stone-600">
              recommendation {suggestion.recommendation ?? "未给出"} / status{" "}
              {suggestion.status}
            </p>
            <div className="mt-2 max-h-40 overflow-y-auto whitespace-pre-wrap break-words rounded border border-stone-200 bg-stone-50 p-3 text-sm text-stone-800">
              {suggestion.summary ?? "暂无摘要"}
            </div>
          </div>
        ) : detail ? (
          <EmptyState title="暂无 AI 建议" description="提交任务后等待 worker 生成结果。" />
        ) : null}

        <div className="border-t border-stone-200 pt-4">
          <h3 className="text-sm font-semibold text-stone-950">AI job history</h3>
          {history.length === 0 ? (
            <p className="mt-2 text-sm text-stone-600">暂无 job 记录</p>
          ) : (
            <ul className="mt-2 divide-y divide-stone-200 text-sm">
              {history.map((job) => (
                <li className="grid gap-2 py-2" key={jobId(job)}>
                  <p className="font-medium text-stone-950">
                    {jobPurpose(job)} / {job.status}
                  </p>
                  <p className="break-all text-stone-600">{jobId(job)}</p>
                  <p className="text-stone-600">
                    created {jobCreatedAt(job) ?? "unknown"} / finished{" "}
                    {job.finished_at ?? "pending"}
                  </p>
                  {isAiJobResponse(job) ? (
                    <>
                      <p className="text-stone-600">
                        queue {job.queue_backend} / attempt {job.attempt_count}/
                        {job.max_attempts}
                      </p>
                      {job.worker_id ? (
                        <p className="break-all text-stone-600">worker {job.worker_id}</p>
                      ) : null}
                      {job.next_run_at ? (
                        <p className="text-stone-600">next retry {job.next_run_at}</p>
                      ) : null}
                      <div className="flex flex-wrap gap-2">
                        {isActiveWorkerStatus(job.status) ? (
                          <button
                            className="inline-flex min-h-9 items-center rounded border border-stone-300 px-3 py-1.5 text-sm text-stone-800 hover:bg-stone-50"
                            type="button"
                            onClick={() =>
                              void onCancelJob(job.id, {
                                cancelledBy: createdBy.trim() || "local",
                              })
                            }
                          >
                            Cancel
                          </button>
                        ) : null}
                        {isFailedWorkerStatus(job.status) ? (
                          <button
                            className="inline-flex min-h-9 items-center rounded border border-stone-300 px-3 py-1.5 text-sm text-stone-800 hover:bg-stone-50"
                            type="button"
                            onClick={() =>
                              void onRetryJob(job.id, {
                                createdBy: createdBy.trim() || "local",
                              })
                            }
                          >
                            Retry
                          </button>
                        ) : null}
                        <button
                          className="inline-flex min-h-9 items-center rounded border border-stone-300 px-3 py-1.5 text-sm text-stone-800 hover:bg-stone-50"
                          type="button"
                          onClick={() => void onLoadEvents(job.id)}
                        >
                          Events
                        </button>
                      </div>
                      {eventsByJobId[job.id]?.length ? (
                        <ul className="grid gap-1 rounded border border-stone-200 bg-stone-50 p-2 text-stone-700">
                          {eventsByJobId[job.id].map((event) => (
                            <li className="grid gap-0.5" key={event.id}>
                              <p className="font-medium text-stone-800">
                                {event.event_type} / {event.actor}
                              </p>
                              {event.message ? (
                                <p className="break-words text-stone-600">{event.message}</p>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
