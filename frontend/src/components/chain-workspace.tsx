"use client";

import { ArrowLeftRight } from "lucide-react";
import { useEffect, useState } from "react";

import { DependencyStatusBanner } from "@/components/dependency-status-banner";
import { EvidencePanel } from "@/components/evidence-panel";
import {
  MultiPathFiltersPanel,
  type MultiPathFilterState,
} from "@/components/multipath-filters";
import { MultiPathResult } from "@/components/multipath-result";
import { PersonSelector } from "@/components/person-selector";
import { useMultiPathChain } from "@/hooks/use-multipath-chain";
import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  PersonSearchItem,
  ReadyResponse,
} from "@/lib/figure-chain-types";
import { canSubmitChain, getChainValidationMessage } from "@/lib/validation";

function isReadyResponse(value: unknown): value is ReadyResponse {
  return (
    typeof value === "object" &&
    value !== null &&
    ((value as { status?: unknown }).status === "ready" ||
      (value as { status?: unknown }).status === "not_ready") &&
    typeof (value as { dependencies?: unknown }).dependencies === "object" &&
    (value as { dependencies?: unknown }).dependencies !== null
  );
}

export function ChainWorkspace() {
  const [source, setSource] = useState<PersonSearchItem | null>(null);
  const [target, setTarget] = useState<PersonSearchItem | null>(null);
  const [maxDepth, setMaxDepth] = useState(12);
  const [selectedEncounterId, setSelectedEncounterId] = useState<string | null>(
    null,
  );
  const [multiPathFilters, setMultiPathFilters] =
    useState<MultiPathFilterState>({
      maxPaths: 5,
      extraDepth: 0,
      minCertaintyLevel: "high",
      encounterKinds: [],
    });
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [healthError, setHealthError] = useState<DisplayableError | null>(null);
  const multipath = useMultiPathChain();

  useEffect(() => {
    fetch("/api/figure-chain/health/ready")
      .then(async (response) => {
        const body = (await response.json()) as unknown;
        if (isReadyResponse(body)) {
          setReady(body);
          setHealthError(null);
          return;
        }
        if (!response.ok) {
          throw parseErrorResponse(body);
        }
        throw parseErrorResponse(body);
      })
      .catch((error: unknown) => setHealthError(parseErrorResponse(error)));
  }, []);

  const validationMessage = getChainValidationMessage(source, target, maxDepth);
  const canSubmit = canSubmitChain(source, target, maxDepth, multipath.isLoading);

  async function handleSubmit() {
    if (!source || !target || !canSubmit) {
      return;
    }
    setSelectedEncounterId(null);
    await multipath.findMultiPath({
      source: { person_id: source.person_id },
      target: { person_id: target.person_id },
      max_depth: maxDepth,
      max_paths: multiPathFilters.maxPaths,
      extra_depth: multiPathFilters.extraDepth,
      filters: {
        min_certainty_level: multiPathFilters.minCertaintyLevel,
        encounter_kinds: multiPathFilters.encounterKinds,
        exclude_person_ids: [],
        exclude_encounter_ids: [],
        source_work_ids: [],
        intermediate_dynasty_codes: [],
        intermediate_year_min: null,
        intermediate_year_max: null,
      },
    });
  }

  function swapEndpoints() {
    setSource(target);
    setTarget(source);
    setSelectedEncounterId(null);
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <section className="space-y-5">
        <div className="space-y-3">
          <DependencyStatusBanner ready={ready} />
          {healthError ? (
            <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
              FigureChain API readiness 暂不可用。
            </div>
          ) : null}
        </div>

        <div className="rounded border border-stone-200 bg-white p-4 shadow-sm">
          <div className="grid gap-4">
            <PersonSelector
              label="起点人物"
              selectedPerson={source}
              onSelect={setSource}
            />
            <div className="flex justify-center">
              <button
                aria-label="交换起点和终点"
                className="inline-flex min-h-11 min-w-11 items-center justify-center rounded border border-stone-300 text-stone-700 hover:bg-stone-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                type="button"
                onClick={swapEndpoints}
              >
                <ArrowLeftRight aria-hidden="true" className="h-4 w-4" />
              </button>
            </div>
            <PersonSelector
              label="终点人物"
              selectedPerson={target}
              onSelect={setTarget}
            />
          </div>

          <div className="mt-5 grid gap-3 border-t border-stone-200 pt-4 sm:grid-cols-[1fr_auto] sm:items-end">
            <label className="block text-sm font-medium text-stone-800">
              max_depth
              <input
                className="mt-1 min-h-11 w-full rounded border border-stone-300 px-3 py-2 text-base focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                max={30}
                min={1}
                type="number"
                value={maxDepth}
                onChange={(event) => setMaxDepth(Number(event.target.value))}
              />
            </label>
            <button
              className="min-h-11 rounded bg-stone-950 px-5 py-2 text-sm font-medium text-white hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-stone-300"
              disabled={!canSubmit}
              type="button"
              onClick={handleSubmit}
            >
              {multipath.isLoading ? "查询中..." : "查询人物链"}
            </button>
          </div>
          <div className="mt-4">
            <MultiPathFiltersPanel
              value={multiPathFilters}
              onChange={setMultiPathFilters}
            />
          </div>

          {validationMessage ? (
            <p className="mt-3 text-sm text-amber-800">{validationMessage}</p>
          ) : null}
        </div>
      </section>

      <section className="space-y-5">
        <div className="rounded border border-stone-200 bg-white p-4 shadow-sm">
          <MultiPathResult
            error={multipath.error}
            isLoading={multipath.isLoading}
            result={multipath.result}
            onSelectEncounter={setSelectedEncounterId}
          />
        </div>
        <EvidencePanel encounterId={selectedEncounterId} />
      </section>
    </div>
  );
}
