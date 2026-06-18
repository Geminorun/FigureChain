"use client";

import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import {
  type PersonEncounterQueryFilters,
  usePersonEncounters,
} from "@/hooks/use-person-encounters";
import { formatLifeYears, formatMaybeText, formatReviewedAt } from "@/lib/formatters";

type PersonEncounterListProps = {
  personId: string;
  filters?: PersonEncounterQueryFilters;
};

export function PersonEncounterList({
  personId,
  filters = { status: "active", limit: 50, offset: 0 },
}: PersonEncounterListProps) {
  const { response, isLoading, error, refresh } = usePersonEncounters(personId, filters);

  if (isLoading) {
    return (
      <div className="rounded border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600">
        Encounter 加载中...
      </div>
    );
  }
  if (error) {
    return <ErrorCallout error={error} />;
  }
  if (!response || response.items.length === 0) {
    return (
      <EmptyState
        title="没有已审核 Encounter"
        description="当前筛选条件下没有可展示的已审核见面证据。"
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-stone-600">
          {response.count} 条记录，offset {response.offset}
        </p>
        <button
          className="min-h-9 rounded border border-stone-300 px-3 text-sm text-stone-700 hover:bg-stone-100"
          type="button"
          onClick={refresh}
        >
          刷新
        </button>
      </div>
      <div className="divide-y divide-stone-200 rounded border border-stone-200">
        {response.items.map((item) => (
          <article className="grid gap-2 p-4" key={item.encounter_id}>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                className="font-mono text-sm font-medium text-stone-950 underline-offset-4 hover:underline"
                href={`/encounters/${item.encounter_id}`}
              >
                {item.encounter_id}
              </Link>
              <span className="rounded bg-stone-100 px-2 py-1 text-xs text-stone-700">
                {item.encounter_kind}
              </span>
              <span className="rounded bg-emerald-50 px-2 py-1 text-xs text-emerald-800">
                {item.certainty_level}
              </span>
            </div>
            <div className="text-sm text-stone-700">
              对方人物：
              <Link
                className="font-medium text-stone-950 underline-offset-4 hover:underline"
                href={`/people/${item.other_person_id}`}
              >
                {item.other_person_name ?? item.other_person_id}
              </Link>
              <span className="ml-2 text-stone-500">
                {formatLifeYears(item.other_person_birth_year, item.other_person_death_year)}
              </span>
            </div>
            <p className="break-words text-sm text-stone-800">{item.evidence_summary}</p>
            <p className="text-xs text-stone-500">
              {formatMaybeText(item.source_title)} / {formatMaybeText(item.pages)} /{" "}
              {formatReviewedAt(item.reviewed_at)}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
