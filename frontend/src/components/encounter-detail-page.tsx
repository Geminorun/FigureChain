"use client";

import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { useEncounterDetail } from "@/hooks/use-encounter-detail";
import type { EncounterDetail } from "@/lib/figure-chain-types";
import {
  formatExternalIds,
  formatLifeYears,
  formatMaybeText,
  formatReviewedAt,
} from "@/lib/formatters";

type EncounterDetailPageProps = {
  encounterId: string;
};

type EncounterEvidenceViewProps = {
  detail: EncounterDetail;
};

export function EncounterDetailPage({ encounterId }: EncounterDetailPageProps) {
  const { detail, isLoading, error } = useEncounterDetail(encounterId);

  if (isLoading) {
    return <main className="mx-auto max-w-5xl px-4 py-6">Encounter 加载中...</main>;
  }
  if (error) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6">
        <ErrorCallout error={error} />
      </main>
    );
  }
  if (!detail) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-6">
        <EmptyState title="没有 Encounter 详情" description="Encounter ID 为空或详情暂不可用。" />
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-6">
      <EncounterEvidenceView detail={detail} />
    </main>
  );
}

export function EncounterEvidenceView({ detail }: EncounterEvidenceViewProps) {
  return (
    <section className="space-y-5 rounded border border-stone-200 bg-white p-4 shadow-sm">
      <div className="border-b border-stone-200 pb-4">
        <p className="font-mono text-xs text-stone-500">{detail.encounter_id}</p>
        <h1 className="mt-2 break-words text-2xl font-semibold text-stone-950">
          {detail.evidence_summary}
        </h1>
        <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <DetailDatum label="状态" value={detail.status} />
          <DetailDatum label="类型" value={detail.encounter_kind} />
          <DetailDatum label="可信度" value={detail.certainty_level} />
          <DetailDatum label="path eligible" value={detail.path_eligible ? "yes" : "no"} />
          <DetailDatum label="页码" value={formatMaybeText(detail.pages)} />
          <DetailDatum label="审核时间" value={formatReviewedAt(detail.reviewed_at)} />
        </dl>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {[detail.person_a, detail.person_b].map((person) => (
          <div key={person.person_id} className="rounded border border-stone-200 p-3">
            <Link
              className="font-medium text-stone-950 underline-offset-4 hover:underline"
              href={`/people/${person.person_id}`}
            >
              {person.display_name}
            </Link>
            <p className="text-sm text-stone-600">
              {formatLifeYears(person.birth_year, person.death_year)}
            </p>
            <p className="text-xs text-stone-500">CBDB: {person.cbdb_id ?? "未记录"}</p>
            <p className="break-words text-xs text-stone-500">
              {formatExternalIds(person.external_ids)}
            </p>
          </div>
        ))}
      </div>

      <section>
        <h2 className="text-sm font-semibold text-stone-950">Evidence</h2>
        <div className="mt-2 space-y-2">
          {detail.evidence.map((item) => (
            <div key={item.evidence_id} className="rounded border border-stone-200 p-3 text-sm">
              <p className="break-words font-medium text-stone-900">
                {item.evidence_summary}
              </p>
              <p className="mt-1 text-stone-600">
                {item.evidence_kind} · candidate_id {item.candidate_id ?? "未记录"}
              </p>
              <p className="text-stone-500">页码：{formatMaybeText(item.pages)}</p>
              {item.source_ref_id ? (
                <Link
                  className="mt-1 inline-flex text-stone-950 underline-offset-4 hover:underline"
                  href={`/source-refs/${item.source_ref_id}`}
                >
                  source_ref {item.source_ref_id}
                </Link>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-stone-950">Source refs</h2>
        <div className="mt-2 space-y-2">
          {detail.source_refs.map((ref) => (
            <div key={ref.source_ref_id} className="rounded border border-stone-200 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <Link
                  className="font-medium text-stone-950 underline-offset-4 hover:underline"
                  href={`/source-refs/${ref.source_ref_id}`}
                >
                  source_ref {ref.source_ref_id}
                </Link>
                {ref.source_work_id ? (
                  <Link
                    className="text-stone-700 underline-offset-4 hover:underline"
                    href={`/source-works/${ref.source_work_id}`}
                  >
                    source_work {ref.source_work_id}
                  </Link>
                ) : null}
              </div>
              <p className="mt-1 break-words text-stone-900">
                {ref.title_zh ?? ref.title_en ?? "未记录题名"}
              </p>
              <p className="mt-1 text-stone-600">页码：{formatMaybeText(ref.pages)}</p>
              <p className="mt-1 break-words text-stone-500">{formatMaybeText(ref.notes)}</p>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
}

function DetailDatum({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-stone-500">{label}</dt>
      <dd className="break-words text-stone-900">{value}</dd>
    </div>
  );
}
