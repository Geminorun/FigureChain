import { X } from "lucide-react";
import Link from "next/link";

import type { PersonSearchItem } from "@/lib/figure-chain-types";
import { formatExternalIds, formatLifeYears } from "@/lib/formatters";

type SelectedPersonCardProps = {
  label: string;
  person: PersonSearchItem;
  onClear: () => void;
};

export function SelectedPersonCard({
  label,
  person,
  onClear,
}: SelectedPersonCardProps) {
  return (
    <div className="rounded border border-stone-300 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-stone-500">{label}</p>
          <Link
            className="mt-1 block text-lg font-semibold text-stone-950 underline-offset-4 hover:underline"
            href={`/people/${person.person_id}`}
          >
            {person.display_name}
          </Link>
          <p className="text-sm text-stone-600">
            {formatLifeYears(person.birth_year, person.death_year)}
          </p>
          <p className="mt-1 text-xs text-stone-500">
            {formatExternalIds(person.external_ids)}
          </p>
        </div>
        <button
          aria-label={`清除${label}`}
          className="inline-flex min-h-11 min-w-11 items-center justify-center rounded border border-stone-200 text-stone-600 hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
          type="button"
          onClick={onClear}
        >
          <X aria-hidden="true" className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
