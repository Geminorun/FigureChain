"use client";

import { Search } from "lucide-react";
import { useId, useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { SelectedPersonCard } from "@/components/selected-person-card";
import { usePersonSearch } from "@/hooks/use-person-search";
import type { PersonSearchItem } from "@/lib/figure-chain-types";
import { formatExternalIds, formatLifeYears } from "@/lib/formatters";

type PersonSelectorProps = {
  label: string;
  selectedPerson: PersonSearchItem | null;
  onSelect: (person: PersonSearchItem | null) => void;
};

export function PersonSelector({
  label,
  selectedPerson,
  onSelect,
}: PersonSelectorProps) {
  const id = useId();
  const [query, setQuery] = useState("");
  const { items, isLoading, error } = usePersonSearch(query);

  if (selectedPerson !== null) {
    return (
      <SelectedPersonCard
        label={label}
        person={selectedPerson}
        onClear={() => onSelect(null)}
      />
    );
  }

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-stone-800" htmlFor={id}>
        {label}
      </label>
      <div className="relative">
        <Search
          aria-hidden="true"
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400"
        />
        <input
          id={id}
          className="min-h-11 w-full rounded border border-stone-300 bg-white py-2 pl-9 pr-3 text-base text-stone-950 outline-none placeholder:text-stone-400 focus:border-amber-500 focus:ring-2 focus:ring-amber-200"
          placeholder="输入人物姓名、别名或罗马字"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <div aria-busy={isLoading} className="min-h-28 space-y-2">
        {error ? <ErrorCallout error={error} /> : null}
        {isLoading ? (
          <div className="rounded border border-stone-200 bg-white p-3 text-sm text-stone-600">
            搜索中...
          </div>
        ) : null}
        {!isLoading && query.trim().length > 0 && items.length === 0 && !error ? (
          <EmptyState
            title="没有候选人物"
            description="换一个姓名、繁简体或别名再试。"
          />
        ) : null}
        {items.map((person) => {
          const lifeYears = formatLifeYears(person.birth_year, person.death_year);
          const externalIds = formatExternalIds(person.external_ids);
          return (
            <button
              key={person.person_id}
              aria-label={`选择 ${person.display_name} ${lifeYears} ${externalIds}`}
              className="w-full rounded border border-stone-200 bg-white p-3 text-left shadow-sm transition hover:border-amber-300 hover:bg-amber-50 focus:outline-none focus:ring-2 focus:ring-amber-500"
              type="button"
              onClick={() => onSelect(person)}
            >
              <span className="block text-base font-semibold text-stone-950">
                {person.display_name}
              </span>
              <span className="mt-1 block text-sm text-stone-600">
                {lifeYears}
              </span>
              {person.primary_name_romanized ? (
                <span className="mt-1 block text-sm text-stone-500">
                  {person.primary_name_romanized}
                </span>
              ) : null}
              <span className="mt-1 block text-xs text-stone-500">
                {externalIds}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
