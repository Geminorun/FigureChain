"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { useChainShare } from "@/hooks/use-chain-share";
import type { ChainEdge, ChainPerson, ChainShareDetail } from "@/lib/figure-chain-types";
import { formatLifeYears, formatMaybeText } from "@/lib/formatters";

type SharePageProps = {
  shareSlug: string;
};

export function SharePage({ shareSlug }: SharePageProps) {
  const share = useChainShare();
  const { error, isLoading, loadShare } = share;
  const [detail, setDetail] = useState<ChainShareDetail | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    loadShare(shareSlug, controller.signal)
      .then(setDetail)
      .catch(() => undefined);
    return () => controller.abort();
  }, [loadShare, shareSlug]);

  if (isLoading && detail === null) {
    return <main className="mx-auto max-w-5xl px-4 py-6">分享快照加载中...</main>;
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
        <EmptyState title="没有分享快照" description="分享链接不存在或暂不可用。" />
      </main>
    );
  }

  const people = listOfObjects<ChainPerson>(detail.path_payload.people);
  const edges = listOfObjects<ChainEdge & { source_refs?: unknown }>(detail.path_payload.edges);
  const heading = `${people[0]?.display_name ?? "未记录"} -> ${
    people.at(-1)?.display_name ?? "未记录"
  }`;

  return (
    <main className="mx-auto max-w-5xl space-y-5 px-4 py-6">
      <section className="border-b border-stone-200 pb-4">
        <p className="font-mono text-sm text-stone-500">{detail.share_slug}</p>
        <h1 className="mt-2 text-3xl font-semibold text-stone-950">{heading}</h1>
        <p className="mt-2 break-all font-mono text-sm text-stone-600">
          {detail.chain_hash}
        </p>
      </section>

      {typeof detail.path_payload.partial_warning === "string" ? (
        <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
          {detail.path_payload.partial_warning}
        </div>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-stone-950">路径人物</h2>
        <ol className="grid gap-2">
          {people.map((person, index) => (
            <li className="rounded border border-stone-200 bg-white p-3" key={person.person_id}>
              <span className="text-sm text-stone-500">{index + 1}. </span>
              <Link
                className="font-medium text-stone-950 underline-offset-4 hover:underline"
                href={`/people/${person.person_id}`}
              >
                {person.display_name}
              </Link>
              <span className="ml-2 text-sm text-stone-600">
                {formatLifeYears(person.birth_year, person.death_year)}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-stone-950">事实证据</h2>
        {edges.map((edge) => (
          <article className="space-y-2 rounded border border-stone-200 bg-white p-3" key={edge.encounter_id}>
            <Link
              className="font-medium text-stone-950 underline-offset-4 hover:underline"
              href={`/encounters/${edge.encounter_id}`}
            >
              Encounter {edge.encounter_id}
            </Link>
            <p className="break-words text-sm text-stone-800">{edge.evidence_summary}</p>
            <p className="text-sm text-stone-600">
              {edge.encounter_kind} / {edge.certainty_level} / pages{" "}
              {formatMaybeText(edge.pages)}
            </p>
            <div className="flex flex-wrap gap-2 text-sm">
              {listOfObjects<{ source_ref_id?: unknown; source_work_id?: unknown }>(
                edge.source_refs,
              ).map((sourceRef) => (
                <span key={`${sourceRef.source_ref_id}:${sourceRef.source_work_id}`}>
                  {sourceRef.source_ref_id ? (
                    <Link
                      className="text-stone-950 underline-offset-4 hover:underline"
                      href={`/source-refs/${sourceRef.source_ref_id}`}
                    >
                      source_ref {String(sourceRef.source_ref_id)}
                    </Link>
                  ) : null}
                  {sourceRef.source_work_id ? (
                    <>
                      {" "}
                      /{" "}
                      <Link
                        className="text-stone-950 underline-offset-4 hover:underline"
                        href={`/source-works/${sourceRef.source_work_id}`}
                      >
                        source_work {String(sourceRef.source_work_id)}
                      </Link>
                    </>
                  ) : null}
                </span>
              ))}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

function listOfObjects<T extends object>(value: unknown): T[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is T => typeof item === "object" && item !== null);
}
