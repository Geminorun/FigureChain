import { FileSearch } from "lucide-react";

import type { ChainPath as ChainPathType } from "@/lib/figure-chain-types";
import { formatLifeYears, formatMaybeText } from "@/lib/formatters";

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
              <p className="text-lg font-semibold text-stone-950">
                {person.display_name}
              </p>
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
                        {edge.encounter_kind} · {edge.certainty_level}
                      </p>
                      <p>页码：{formatMaybeText(edge.pages)}</p>
                      <p className="text-xs text-stone-500">
                        encounter_id: {edge.encounter_id}
                      </p>
                    </div>
                    <button
                      className="inline-flex min-h-11 items-center justify-center gap-2 rounded bg-stone-950 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2"
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
