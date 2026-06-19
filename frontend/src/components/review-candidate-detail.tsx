import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import type { DisplayableError } from "@/lib/api-errors";
import type {
  ReviewCandidateDetail as ReviewCandidateDetailType,
  ReviewCandidatePerson,
} from "@/lib/figure-chain-types";

type ReviewCandidateDetailProps = {
  detail: ReviewCandidateDetailType | null;
  error: DisplayableError | null;
  isLoading: boolean;
};

function optional(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "未标注";
  }
  return String(value);
}

function yesNo(value: boolean): string {
  return value ? "yes" : "no";
}

function PersonBlock({ label, person }: { label: string; person: ReviewCandidatePerson }) {
  return (
    <div className="border-t border-stone-200 py-3 first:border-t-0">
      <p className="text-xs font-medium uppercase text-stone-500">{label}</p>
      {person.person_id ? (
        <Link
          className="mt-1 block text-base font-semibold text-stone-950 underline-offset-4 hover:underline"
          href={`/people/${person.person_id}`}
        >
          {person.display_name}
        </Link>
      ) : (
        <p className="mt-1 text-base font-semibold text-stone-950">{person.display_name}</p>
      )}
      <p className="mt-1 text-sm text-stone-600">
        CBDB {optional(person.cbdb_id)} / {optional(person.primary_name_romanized)} /{" "}
        {optional(person.birth_year)}-{optional(person.death_year)}
      </p>
      <p className="mt-1 break-all text-xs text-stone-500">{optional(person.person_id)}</p>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <p className="grid gap-1 border-t border-stone-200 py-2 text-sm sm:grid-cols-[9rem_1fr]">
      <span className="font-medium text-stone-600">{label}</span>
      <span className="break-words text-stone-950">{value}</span>
    </p>
  );
}

export function ReviewCandidateDetail({
  detail,
  error,
  isLoading,
}: ReviewCandidateDetailProps) {
  return (
    <section className="rounded border border-stone-200 bg-white p-4 shadow-sm">
      <h2 className="text-base font-semibold text-stone-950">候选详情</h2>
      <div className="mt-4 space-y-4">
        {error ? <ErrorCallout error={error} /> : null}
        {isLoading ? (
          <div className="rounded border border-stone-200 bg-stone-50 p-4 text-sm text-stone-600">
            正在加载候选详情...
          </div>
        ) : null}
        {!isLoading && !error && detail === null ? (
          <EmptyState title="请选择候选记录" description="从左侧候选列表选择一条记录。" />
        ) : null}
        {!isLoading && !error && detail ? (
          <>
            <div>
              <p className="text-sm font-medium text-stone-600">
                {detail.kind} {detail.candidate_id}
              </p>
              <p className="mt-1 text-sm text-stone-600">
                status {detail.status} / confidence {detail.confidence.toFixed(2)}
              </p>
            </div>

            <div>
              <PersonBlock label="person a" person={detail.person_a} />
              <PersonBlock label="person b" person={detail.person_b} />
            </div>

            <div>
              <h3 className="text-sm font-semibold text-stone-950">关系与时空</h3>
              <DetailRow label="relation_type" value={optional(detail.relation.relation_type)} />
              <DetailRow label="basis" value={optional(detail.relation.basis)} />
              <DetailRow label="strength" value={optional(detail.relation.strength)} />
              <DetailRow label="source" value={optional(detail.relation.source_name)} />
              <DetailRow label="source_table" value={optional(detail.relation.source_table)} />
              <DetailRow label="source_pk" value={optional(detail.relation.source_pk)} />
              <DetailRow label="time" value={optional(detail.time?.summary)} />
              <DetailRow label="pages" value={optional(detail.time?.pages)} />
              <DetailRow label="place" value={optional(detail.place?.summary)} />
              <DetailRow label="notes" value={optional(detail.relation.notes)} />
            </div>

            <div>
              <h3 className="text-sm font-semibold text-stone-950">来源</h3>
              {detail.source_refs.length === 0 ? (
                <p className="mt-2 text-sm text-stone-600">暂无 source refs</p>
              ) : (
                <ul className="mt-2 divide-y divide-stone-200 text-sm">
                  {detail.source_refs.map((source) => (
                    <li className="py-2" key={source.source_ref_id}>
                      <p className="font-medium text-stone-950">
                        {optional(source.title_zh ?? source.title_en)}
                      </p>
                      <p className="text-stone-600">
                        <Link
                          className="text-stone-950 underline-offset-4 hover:underline"
                          href={`/source-refs/${source.source_ref_id}`}
                        >
                          source_ref {source.source_ref_id}
                        </Link>{" "}
                        /{" "}
                        {source.source_work_id ? (
                          <Link
                            className="text-stone-950 underline-offset-4 hover:underline"
                            href={`/source-works/${source.source_work_id}`}
                          >
                            work {source.source_work_id}
                          </Link>
                        ) : (
                          `work ${optional(source.source_work_id)}`
                        )}{" "}
                        / pages {optional(source.pages)}
                      </p>
                      <p className="mt-1 break-words text-stone-700">{optional(source.notes)}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold text-stone-950">证据</h3>
              {detail.evidence.length === 0 ? (
                <p className="mt-2 text-sm text-stone-600">暂无 evidence</p>
              ) : (
                <ul className="mt-2 divide-y divide-stone-200 text-sm">
                  {detail.evidence.map((evidence, index) => (
                    <li className="py-2" key={`${evidence.evidence_id ?? "none"}:${index}`}>
                      <p className="font-medium text-stone-950">{evidence.evidence_summary}</p>
                      <p className="text-stone-600">
                        evidence {optional(evidence.evidence_id)} /{" "}
                        {evidence.source_ref_id ? (
                          <Link
                            className="text-stone-950 underline-offset-4 hover:underline"
                            href={`/source-refs/${evidence.source_ref_id}`}
                          >
                            source_ref {evidence.source_ref_id}
                          </Link>
                        ) : (
                          `source_ref ${optional(evidence.source_ref_id)}`
                        )}{" "}
                        / {evidence.evidence_kind} / pages{" "}
                        {optional(evidence.pages)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div>
              <h3 className="text-sm font-semibold text-stone-950">提升状态</h3>
              <DetailRow
                label="default promotable"
                value={yesNo(detail.promotion_readiness.default_promotable)}
              />
              <DetailRow
                label="default path eligible"
                value={yesNo(detail.promotion_readiness.default_path_eligible)}
              />
              <DetailRow
                label="reasons"
                value={
                  detail.promotion_readiness.reasons.length > 0
                    ? detail.promotion_readiness.reasons.join("; ")
                    : "无"
                }
              />
              <DetailRow
                label="linked encounter"
                value={
                  detail.linked_encounter
                    ? `${detail.linked_encounter.encounter_id} / ${optional(detail.linked_encounter.status)}`
                    : "未关联"
                }
              />
            </div>
          </>
        ) : null}
      </div>
    </section>
  );
}
