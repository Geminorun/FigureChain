"use client";

import type { ReactNode } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { PersonEncounterList } from "@/components/person-encounter-list";
import { usePersonDetail } from "@/hooks/use-person-detail";
import { formatLifeYears, formatMaybeText } from "@/lib/formatters";

type PersonDetailPageProps = {
  personId: string;
};

export function PersonDetailPage({ personId }: PersonDetailPageProps) {
  const { detail, isLoading, error } = usePersonDetail(personId);

  if (isLoading) {
    return <PageShell>人物详情加载中...</PageShell>;
  }
  if (error) {
    return (
      <PageShell>
        <ErrorCallout error={error} />
      </PageShell>
    );
  }
  if (!detail) {
    return (
      <PageShell>
        <EmptyState title="没有人物详情" description="人物 ID 为空或详情暂不可用。" />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <section className="space-y-5">
        <div className="border-b border-stone-200 pb-4">
          <p className="text-sm text-stone-500">{detail.person_id}</p>
          <h1 className="mt-2 text-3xl font-semibold text-stone-950">
            {detail.display_name}
          </h1>
          <p className="mt-2 text-sm text-stone-600">
            {formatLifeYears(detail.birth_year, detail.death_year)} /{" "}
            {formatMaybeText(detail.dynasty_label_zh)}
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Metric label="active" value={detail.encounter_summary.active_count} />
          <Metric
            label="path eligible"
            value={detail.encounter_summary.path_eligible_count}
          />
          <Metric
            label="high certainty"
            value={detail.encounter_summary.high_certainty_count}
          />
        </div>

        <section className="grid gap-4 md:grid-cols-2">
          <InfoBlock title="基础信息">
            <InfoLine label="繁体名" value={detail.primary_name_zh_hant} />
            <InfoLine label="简体名" value={detail.primary_name_zh_hans} />
            <InfoLine label="罗马字" value={detail.primary_name_romanized} />
            <InfoLine label="index year" value={detail.index_year} />
            <InfoLine label="dynasty" value={detail.dynasty_label_en} />
            <InfoLine label="notes" value={detail.notes} />
          </InfoBlock>
          <InfoBlock title="外部 ID">
            {detail.external_ids.length === 0 ? (
              <p className="text-sm text-stone-600">未记录</p>
            ) : (
              <ul className="space-y-2">
                {detail.external_ids.map((externalId) => (
                  <li className="text-sm text-stone-800" key={externalId.external_id}>
                    {externalId.source_name}: {externalId.external_id}
                  </li>
                ))}
              </ul>
            )}
          </InfoBlock>
          <InfoBlock title="别名">
            {detail.aliases.length === 0 ? (
              <p className="text-sm text-stone-600">未记录</p>
            ) : (
              <ul className="space-y-2">
                {detail.aliases.map((alias) => (
                  <li
                    className="break-words text-sm text-stone-800"
                    key={`${alias.alias_zh_hant}-${alias.alias_type_label_zh}`}
                  >
                    {formatMaybeText(alias.alias_zh_hant ?? alias.alias_zh_hans)}
                    <span className="ml-2 text-stone-500">
                      {formatMaybeText(alias.alias_type_label_zh)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </InfoBlock>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-stone-950">已审核 Encounter</h2>
          <PersonEncounterList personId={personId} />
        </section>
      </section>
    </PageShell>
  );
}

function PageShell({ children }: { children: ReactNode }) {
  return <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>;
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

function InfoBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-3 rounded border border-stone-200 bg-white p-4">
      <h2 className="text-base font-semibold text-stone-950">{title}</h2>
      {children}
    </section>
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
