"use client";

import { RefreshCw, Search } from "lucide-react";
import type { FormEvent } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import type { DisplayableError } from "@/lib/api-errors";
import type {
  ReviewCandidateListResponse,
  ReviewCandidateSummary,
} from "@/lib/figure-chain-types";

export type ReviewCandidateSelection = {
  kind: string;
  candidateId: number;
};

export type ReviewCandidateListFilters = {
  kind?: string;
  status?: string;
  minConfidence?: number;
  personId?: string;
  limit: number;
  offset: number;
};

type ReviewCandidateListProps = {
  data: ReviewCandidateListResponse | null;
  error: DisplayableError | null;
  filters: ReviewCandidateListFilters;
  isLoading: boolean;
  selectedCandidateKey: string | null;
  onFiltersChange: (filters: ReviewCandidateListFilters) => void;
  onRefresh: () => void;
  onSelectCandidate: (selection: ReviewCandidateSelection) => void;
};

export function reviewCandidateKey(candidate: ReviewCandidateSelection): string {
  return `${candidate.kind}:${candidate.candidateId}`;
}

function personYears(candidate: ReviewCandidateSummary["person_a"]): string {
  if (candidate.birth_year === null && candidate.death_year === null) {
    return "生卒年不详";
  }
  return `${candidate.birth_year ?? "?"}-${candidate.death_year ?? "?"}`;
}

function formatOptional(value: string | null): string {
  return value && value.trim().length > 0 ? value : "未标注";
}

function parseFilters(form: HTMLFormElement, current: ReviewCandidateListFilters) {
  const data = new FormData(form);
  const minConfidenceRaw = String(data.get("minConfidence") ?? "").trim();
  const minConfidence =
    minConfidenceRaw.length > 0 ? Number(minConfidenceRaw) : undefined;
  const kind = String(data.get("kind") ?? "").trim();
  const status = String(data.get("status") ?? "").trim();
  const personId = String(data.get("personId") ?? "").trim();

  return {
    kind: kind.length > 0 ? kind : undefined,
    status: status.length > 0 ? status : undefined,
    minConfidence: Number.isFinite(minConfidence) ? minConfidence : undefined,
    personId: personId.length > 0 ? personId : undefined,
    limit: current.limit,
    offset: 0,
  };
}

export function ReviewCandidateList({
  data,
  error,
  filters,
  isLoading,
  selectedCandidateKey,
  onFiltersChange,
  onRefresh,
  onSelectCandidate,
}: ReviewCandidateListProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onFiltersChange(parseFilters(event.currentTarget, filters));
  }

  return (
    <section className="rounded border border-stone-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-stone-950">审核候选</h2>
          <p className="mt-1 text-sm text-stone-600">
            共 {data?.count ?? 0} 条候选，当前显示 {data?.items.length ?? 0} 条
          </p>
        </div>
        <button
          aria-label="刷新候选列表"
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded border border-stone-300 text-stone-700 hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
          type="button"
          onClick={onRefresh}
        >
          <RefreshCw aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>

      <form
        className="mt-4 grid gap-3 border-y border-stone-200 py-4 sm:grid-cols-2"
        key={`${filters.kind ?? ""}:${filters.status ?? ""}:${filters.minConfidence ?? ""}:${filters.personId ?? ""}`}
        onSubmit={handleSubmit}
      >
        <label className="block text-sm font-medium text-stone-800">
          kind
          <select
            className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
            defaultValue={filters.kind ?? ""}
            name="kind"
          >
            <option value="">全部</option>
            <option value="relationship">relationship</option>
            <option value="kinship">kinship</option>
            <option value="office">office</option>
          </select>
        </label>
        <label className="block text-sm font-medium text-stone-800">
          status
          <select
            className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
            defaultValue={filters.status ?? ""}
            name="status"
          >
            <option value="">全部</option>
            <option value="needs_review">needs_review</option>
            <option value="promoted">promoted</option>
            <option value="rejected">rejected</option>
          </select>
        </label>
        <label className="block text-sm font-medium text-stone-800">
          min confidence
          <input
            className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
            defaultValue={filters.minConfidence ?? ""}
            max={1}
            min={0}
            name="minConfidence"
            step={0.01}
            type="number"
          />
        </label>
        <label className="block text-sm font-medium text-stone-800">
          person id
          <input
            className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
            defaultValue={filters.personId ?? ""}
            name="personId"
            type="text"
          />
        </label>
        <div className="sm:col-span-2">
          <button
            className="inline-flex min-h-10 items-center gap-2 rounded bg-stone-950 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2"
            type="submit"
          >
            <Search aria-hidden="true" className="h-4 w-4" />
            应用筛选
          </button>
        </div>
      </form>

      <div className="mt-4 space-y-3">
        {error ? <ErrorCallout error={error} /> : null}
        {isLoading ? (
          <div className="rounded border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600">
            正在加载候选记录...
          </div>
        ) : null}
        {!isLoading && !error && data?.items.length === 0 ? (
          <EmptyState title="没有候选记录" description="调整筛选条件后重新查询。" />
        ) : null}
        {!isLoading && !error
          ? data?.items.map((candidate) => {
              const key = reviewCandidateKey({
                kind: candidate.kind,
                candidateId: candidate.candidate_id,
              });
              const selected = selectedCandidateKey === key;
              return (
                <button
                  aria-pressed={selected}
                  className={`grid w-full gap-3 rounded border p-3 text-left text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 ${
                    selected
                      ? "border-amber-500 bg-amber-50"
                      : "border-stone-200 bg-white hover:bg-stone-50"
                  }`}
                  key={key}
                  type="button"
                  onClick={() =>
                    onSelectCandidate({
                      kind: candidate.kind,
                      candidateId: candidate.candidate_id,
                    })
                  }
                >
                  <span className="sr-only">
                    {candidate.kind} {candidate.candidate_id}
                  </span>
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-medium text-stone-950">
                      {candidate.person_a.display_name}
                      {" -> "}
                      {candidate.person_b.display_name}
                    </span>
                    <span className="rounded border border-stone-300 px-2 py-0.5 text-xs text-stone-700">
                      {candidate.status}
                    </span>
                  </span>
                  <span className="grid gap-1 text-stone-600 sm:grid-cols-2">
                    <span>
                      {candidate.person_a.cbdb_id ?? "?"} / {personYears(candidate.person_a)}
                    </span>
                    <span>
                      {candidate.person_b.cbdb_id ?? "?"} / {personYears(candidate.person_b)}
                    </span>
                  </span>
                  <span className="grid gap-1 text-stone-700">
                    <span>relation {formatOptional(candidate.relation_type)}</span>
                    <span>
                      time {formatOptional(candidate.time_summary)} / place{" "}
                      {formatOptional(candidate.place_summary)}
                    </span>
                    <span>
                      confidence {candidate.confidence.toFixed(2)} / evidence{" "}
                      {candidate.evidence_count} / source {candidate.source_count}
                    </span>
                    <span>
                      AI {candidate.latest_ai_job_status ?? "none"} / suggestion{" "}
                      {candidate.has_ai_suggestion ? "yes" : "no"}
                    </span>
                  </span>
                </button>
              );
            })
          : null}
      </div>
    </section>
  );
}
