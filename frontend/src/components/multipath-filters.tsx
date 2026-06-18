"use client";

import { useState } from "react";

export type MultiPathFilterState = {
  maxPaths: number;
  extraDepth: number;
  minCertaintyLevel: "high" | "medium" | "low";
  encounterKinds: string[];
  excludePersonIds: string[];
  excludeEncounterIds: string[];
};

type MultiPathFiltersPanelProps = {
  value: MultiPathFilterState;
  onChange: (value: MultiPathFilterState) => void;
};

const ENCOUNTER_KIND_OPTIONS = [
  "direct_interaction",
  "family_contact",
  "manual_contact",
  "co_presence",
];

function parseIdList(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[\s,;]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  );
}

export function MultiPathFiltersPanel({
  value,
  onChange,
}: MultiPathFiltersPanelProps) {
  const [personIdsText, setPersonIdsText] = useState(() =>
    value.excludePersonIds.join("\n"),
  );
  const [encounterIdsText, setEncounterIdsText] = useState(() =>
    value.excludeEncounterIds.join("\n"),
  );

  function update(next: Partial<MultiPathFilterState>) {
    onChange({ ...value, ...next });
  }

  function toggleKind(kind: string) {
    const nextKinds = value.encounterKinds.includes(kind)
      ? value.encounterKinds.filter((item) => item !== kind)
      : [...value.encounterKinds, kind];
    update({ encounterKinds: nextKinds });
  }

  return (
    <fieldset className="grid gap-3 border-t border-stone-200 pt-4 sm:grid-cols-3">
      <legend className="text-sm font-semibold text-stone-950">
        多路径过滤
      </legend>
      <label className="block text-sm font-medium text-stone-800">
        max_paths
        <input
          aria-label="max_paths"
          className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
          max={20}
          min={1}
          type="number"
          value={value.maxPaths}
          onChange={(event) => update({ maxPaths: Number(event.target.value) })}
        />
      </label>
      <label className="block text-sm font-medium text-stone-800">
        extra_depth
        <input
          aria-label="extra_depth"
          className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
          max={2}
          min={0}
          type="number"
          value={value.extraDepth}
          onChange={(event) =>
            update({ extraDepth: Number(event.target.value) })
          }
        />
      </label>
      <label className="block text-sm font-medium text-stone-800">
        min_certainty_level
        <select
          aria-label="min_certainty_level"
          className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
          value={value.minCertaintyLevel}
          onChange={(event) =>
            update({
              minCertaintyLevel: event.target
                .value as MultiPathFilterState["minCertaintyLevel"],
            })
          }
        >
          <option value="high">high</option>
          <option value="medium">medium</option>
          <option value="low">low</option>
        </select>
      </label>
      <div className="sm:col-span-3">
        <p className="text-sm font-medium text-stone-800">encounter_kinds</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {ENCOUNTER_KIND_OPTIONS.map((kind) => (
            <label
              className="inline-flex items-center gap-2 text-sm text-stone-700"
              key={kind}
            >
              <input
                checked={value.encounterKinds.includes(kind)}
                type="checkbox"
                onChange={() => toggleKind(kind)}
              />
              {kind}
            </label>
          ))}
        </div>
      </div>
      <label className="block text-sm font-medium text-stone-800 sm:col-span-3">
        exclude_person_ids
        <textarea
          aria-label="exclude_person_ids"
          className="mt-1 min-h-20 w-full resize-y rounded border border-stone-300 px-3 py-2 font-mono text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
          value={personIdsText}
          onChange={(event) => {
            const nextText = event.target.value;
            setPersonIdsText(nextText);
            update({ excludePersonIds: parseIdList(nextText) });
          }}
        />
      </label>
      <label className="block text-sm font-medium text-stone-800 sm:col-span-3">
        exclude_encounter_ids
        <textarea
          aria-label="exclude_encounter_ids"
          className="mt-1 min-h-20 w-full resize-y rounded border border-stone-300 px-3 py-2 font-mono text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
          value={encounterIdsText}
          onChange={(event) => {
            const nextText = event.target.value;
            setEncounterIdsText(nextText);
            update({ excludeEncounterIds: parseIdList(nextText) });
          }}
        />
      </label>
    </fieldset>
  );
}
