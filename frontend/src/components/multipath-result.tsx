"use client";

import { useState } from "react";

import { ChainShareActions } from "@/components/chain-share-actions";
import { ChainPath } from "@/components/chain-path";
import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import type { DisplayableError } from "@/lib/api-errors";
import type {
  ChainPath as ChainPathType,
  MultiPathChainResponse,
  MultiPathItem,
} from "@/lib/figure-chain-types";

type MultiPathResultProps = {
  result: MultiPathChainResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
  onSelectEncounter: (encounterId: string) => void;
};

function toChainPath(path: MultiPathItem): ChainPathType {
  return {
    length: path.length,
    people: path.people,
    edges: path.edges,
  };
}

export function MultiPathResult({
  result,
  isLoading,
  error,
  onSelectEncounter,
}: MultiPathResultProps) {
  const [selectedPathId, setSelectedPathId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        查链中...
      </div>
    );
  }

  if (error) {
    return <ErrorCallout error={error} />;
  }

  if (result === null) {
    return (
      <EmptyState
        title="尚未开始查链"
        description="选择起点和终点人物后，查询多条人物链。"
      />
    );
  }

  if (result.status === "no_path" || result.paths.length === 0) {
    return (
      <EmptyState
        title="暂未找到路径"
        description="可以放宽过滤条件、调高最大路径深度，或等待更多真实接触记录数据。"
      />
    );
  }

  const selected =
    result.paths.find((path) => path.path_id === selectedPathId) ??
    result.paths[0];

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-stone-500">多路径结果</p>
        <h2 className="text-xl font-semibold text-stone-950">
          找到 {result.returned_paths} 条路径
        </h2>
        {result.returned_paths >= result.max_paths ? (
          <p className="text-sm text-amber-800">
            结果已达到最大路径数上限，可收紧过滤或调高上限。
          </p>
        ) : null}
      </div>

      <div className="grid gap-2">
        {result.paths.map((path) => (
          <button
            className={`rounded border px-3 py-2 text-left text-sm ${
              selected.path_id === path.path_id
                ? "border-amber-500 bg-amber-50"
                : "border-stone-200 bg-white hover:bg-stone-50"
            }`}
            key={path.path_id}
            type="button"
            onClick={() => setSelectedPathId(path.path_id)}
          >
            <span className="font-medium">{path.path_id}</span>
            <span className="text-stone-600">
              {" "}
              / 长度 {path.length} / 评分 {path.quality_score.toFixed(2)}
            </span>
          </button>
        ))}
      </div>

      <ChainPath
        path={toChainPath(selected)}
        onSelectEncounter={onSelectEncounter}
      />
      <ChainShareActions path={selected} result={result} />
    </section>
  );
}
