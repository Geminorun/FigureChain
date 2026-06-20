import { FileSearch } from "lucide-react";
import Link from "next/link";

import type { ChainPath as ChainPathType } from "@/lib/figure-chain-types";
import {
  formatCertaintyLevel,
  formatEncounterKind,
  formatLifeYears,
  formatMaybeText,
} from "@/lib/formatters";

type ChainPathProps = {
  path: ChainPathType;
  onSelectEncounter: (encounterId: string) => void;
};

export function ChainPath({ path, onSelectEncounter }: ChainPathProps) {
  return (
    <ol className="space-y-4">
      {path.people.map((person, index) => {
        const edge = path.edges[index];
        return (
          <li key={`${person.person_id}-${index}`} className="space-y-3">
            <div className="rounded border border-stone-200 bg-white p-4 shadow-sm">
              <Link
                className="text-lg font-semibold text-stone-950 underline-offset-4 hover:underline"
                href={`/people/${person.person_id}`}
              >
                {person.display_name}
              </Link>
              <p className="text-sm text-stone-600">
                {formatLifeYears(person.birth_year, person.death_year)}
              </p>
              {person.cbdb_external_id ? (
                <p className="mt-1 text-xs text-stone-500">
                  CBDB: {person.cbdb_external_id}
                </p>
              ) : null}
            </div>
            {edge ? (
              <div className="ml-4 border-l-2 border-amber-300 pl-4">
                <div className="rounded border border-amber-200 bg-amber-50 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="space-y-1 text-sm text-stone-800">
                      <p className="font-medium">{edge.evidence_summary}</p>
                      <p>
                        {formatEncounterKind(edge.encounter_kind)} ·{" "}
                        {formatCertaintyLevel(edge.certainty_level)}
                      </p>
                      <p>页码：{formatMaybeText(edge.pages)}</p>
                      <p className="text-xs text-stone-500">
                        接触记录 ID：{" "}
                        <Link
                          className="font-mono text-stone-700 underline-offset-4 hover:underline"
                          href={`/encounters/${edge.encounter_id}`}
                        >
                          {edge.encounter_id}
                        </Link>
                      </p>
                    </div>
                    <button
                      className="inline-flex min-h-11 w-full shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded bg-stone-950 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 sm:w-auto"
                      type="button"
                      onClick={() => onSelectEncounter(edge.encounter_id)}
                    >
                      <FileSearch aria-hidden="true" className="h-4 w-4" />
                      查看证据
                    </button>
                  </div>
                </div>
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
