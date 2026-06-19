"use client";

import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { useSourceRefDetail } from "@/hooks/use-source-ref-detail";
import { formatMaybeText, formatReviewedAt } from "@/lib/formatters";

type SourceRefDetailPageProps = {
  sourceRefId: string;
};

export function SourceRefDetailPage({ sourceRefId }: SourceRefDetailPageProps) {
  const { detail, isLoading, error } = useSourceRefDetail(sourceRefId);

  if (isLoading) {
    return <main className="mx-auto max-w-4xl px-4 py-6">Source ref 加载中...</main>;
  }
  if (error) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-6">
        <ErrorCallout error={error} />
      </main>
    );
  }
  if (!detail) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-6">
        <EmptyState title="没有 source ref" description="source ref 暂不可用。" />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl space-y-5 px-4 py-6">
      <section className="border-b border-stone-200 pb-4">
        <p className="text-sm text-stone-500">Source Ref</p>
        <h1 className="mt-2 text-3xl font-semibold text-stone-950">
          Source Ref {detail.source_ref_id}
        </h1>
        <p className="mt-2 break-words text-sm text-stone-600">
          {formatMaybeText(detail.pages)} / {formatMaybeText(detail.ref_source_table)}:
          {formatMaybeText(detail.ref_source_pk)}
        </p>
      </section>

      <section className="space-y-3 rounded border border-stone-200 bg-white p-4">
        <h2 className="text-base font-semibold text-stone-950">Source Work</h2>
        {detail.source_work ? (
          <Link
            className="text-sm font-medium text-stone-950 underline-offset-4 hover:underline"
            href={`/source-works/${detail.source_work.source_work_id}`}
          >
            {detail.source_work.title_zh ??
              detail.source_work.title_en ??
              `Source Work ${detail.source_work.source_work_id}`}
          </Link>
        ) : (
          <p className="text-sm text-stone-600">未关联 source work</p>
        )}
      </section>

      <section className="space-y-3 rounded border border-stone-200 bg-white p-4">
        <h2 className="text-base font-semibold text-stone-950">引用内容</h2>
        <InfoLine label="source_name" value={detail.source_name} />
        <InfoLine label="source_table" value={detail.source_table} />
        <InfoLine label="source_pk" value={detail.source_pk} />
        <InfoLine label="notes" value={detail.notes} />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-stone-950">Linked Encounter Evidence</h2>
        {detail.linked_encounter_evidence.length === 0 ? (
          <EmptyState title="没有关联证据" description="这个 source ref 尚未关联 encounter evidence。" />
        ) : (
          <div className="divide-y divide-stone-200 rounded border border-stone-200 bg-white">
            {detail.linked_encounter_evidence.map((item) => (
              <article className="space-y-2 p-4" key={item.evidence_id}>
                <Link
                  className="font-medium text-stone-950 underline-offset-4 hover:underline"
                  href={`/encounters/${item.encounter_id}`}
                >
                  Encounter {item.encounter_id}
                </Link>
                <p className="break-words text-sm text-stone-800">{item.evidence_summary}</p>
                <p className="text-xs text-stone-500">
                  {item.evidence_kind} / {formatMaybeText(item.pages)} /{" "}
                  {formatReviewedAt(item.created_at)}
                </p>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function InfoLine({ label, value }: { label: string; value: string | number | null }) {
  return (
    <p className="grid gap-1 text-sm text-stone-700 sm:grid-cols-[9rem_1fr]">
      <span className="text-stone-500">{label}</span>
      <span className="break-words">{formatMaybeText(value?.toString())}</span>
    </p>
  );
}
