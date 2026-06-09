"use client";

import { ErrorCallout } from "@/components/error-callout";
import { useEncounterDetail } from "@/hooks/use-encounter-detail";
import {
  formatExternalIds,
  formatMaybeText,
  formatReviewedAt,
} from "@/lib/formatters";

type EvidencePanelProps = {
  encounterId: string | null;
};

export function EvidencePanel({ encounterId }: EvidencePanelProps) {
  const { detail, isLoading, error } = useEncounterDetail(encounterId);

  if (encounterId === null) {
    return (
      <aside className="rounded border border-dashed border-stone-300 bg-stone-50 p-4 text-sm text-stone-600">
        选择路径中的一条边查看证据详情。
      </aside>
    );
  }

  if (isLoading) {
    return (
      <aside className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        证据加载中...
      </aside>
    );
  }

  if (error) {
    return <ErrorCallout error={error} />;
  }

  if (detail === null) {
    return null;
  }

  return (
    <aside className="space-y-4 rounded border border-stone-200 bg-white p-4 shadow-sm">
      <div>
        <p className="text-xs font-medium uppercase text-stone-500">Encounter</p>
        <h2 className="mt-1 text-lg font-semibold text-stone-950">
          {detail.evidence_summary}
        </h2>
        <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-stone-500">状态</dt>
            <dd className="text-stone-900">{detail.status}</dd>
          </div>
          <div>
            <dt className="text-stone-500">可信度</dt>
            <dd className="text-stone-900">{detail.certainty_level}</dd>
          </div>
          <div>
            <dt className="text-stone-500">页码</dt>
            <dd className="text-stone-900">{formatMaybeText(detail.pages)}</dd>
          </div>
          <div>
            <dt className="text-stone-500">审核时间</dt>
            <dd className="text-stone-900">
              {formatReviewedAt(detail.reviewed_at)}
            </dd>
          </div>
        </dl>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {[detail.person_a, detail.person_b].map((person) => (
          <div
            key={person.person_id}
            className="rounded border border-stone-200 p-3"
          >
            <p className="font-medium text-stone-950">{person.display_name}</p>
            <p className="text-sm text-stone-600">
              CBDB: {person.cbdb_id ?? "未记录"}
            </p>
            <p className="text-xs text-stone-500">
              {formatExternalIds(person.external_ids)}
            </p>
          </div>
        ))}
      </div>

      <div>
        <h3 className="text-sm font-semibold text-stone-950">Evidence</h3>
        <div className="mt-2 space-y-2">
          {detail.evidence.map((item) => (
            <div
              key={item.evidence_id}
              className="rounded border border-stone-200 p-3 text-sm"
            >
              <p className="font-medium text-stone-900">
                {item.evidence_summary}
              </p>
              <p className="mt-1 text-stone-600">
                {item.evidence_kind} · candidate_id{" "}
                {item.candidate_id ?? "未记录"}
              </p>
              <p className="text-stone-500">页码：{formatMaybeText(item.pages)}</p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-stone-950">Source refs</h3>
        <div className="mt-2 space-y-2">
          {detail.source_refs.map((ref) => (
            <div
              key={ref.source_ref_id}
              className="rounded border border-stone-200 p-3 text-sm"
            >
              <p className="font-medium text-stone-900">
                {ref.title_zh ??
                  ref.title_en ??
                  `source_work_id ${ref.source_work_id ?? "未记录"}`}
              </p>
              <p className="mt-1 text-stone-600">
                页码：{formatMaybeText(ref.pages)}
              </p>
              <p className="mt-1 text-stone-500">
                {formatMaybeText(ref.notes)}
              </p>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
