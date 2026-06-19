"use client";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { useSourceWorkDetail } from "@/hooks/use-source-work-detail";
import { formatMaybeText } from "@/lib/formatters";

type SourceWorkDetailPageProps = {
  sourceWorkId: string;
};

export function SourceWorkDetailPage({ sourceWorkId }: SourceWorkDetailPageProps) {
  const { detail, isLoading, error } = useSourceWorkDetail(sourceWorkId);

  if (isLoading) {
    return <main className="mx-auto max-w-4xl px-4 py-6">Source work 加载中...</main>;
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
        <EmptyState title="没有来源详情" description="source work 暂不可用。" />
      </main>
    );
  }

  const title = detail.title_zh ?? detail.title_en ?? `Source Work ${detail.source_work_id}`;
  return (
    <main className="mx-auto max-w-4xl space-y-5 px-4 py-6">
      <section className="border-b border-stone-200 pb-4">
        <p className="text-sm text-stone-500">Source Work {detail.source_work_id}</p>
        <h1 className="mt-2 text-3xl font-semibold text-stone-950">{title}</h1>
        <p className="mt-2 text-sm text-stone-600">text_code {detail.text_code ?? "未记录"}</p>
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        <Metric label="source refs" value={detail.ref_count} />
        <Metric label="encounters" value={detail.encounter_count} />
      </div>

      <section className="space-y-3 rounded border border-stone-200 bg-white p-4">
        <h2 className="text-base font-semibold text-stone-950">来源身份</h2>
        <InfoLine label="source_name" value={detail.source_name} />
        <InfoLine label="source_table" value={detail.source_table} />
        <InfoLine label="source_pk" value={detail.source_pk} />
        <InfoLine label="title_en" value={detail.title_en} />
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-stone-200 bg-white p-4">
      <p className="text-sm text-stone-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-stone-950">
        {label} {value}
      </p>
    </div>
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
