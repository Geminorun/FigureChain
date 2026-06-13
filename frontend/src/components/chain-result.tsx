"use client";

import { ChainExplanationPanel } from "@/components/chain-explanation-panel";
import { ChainPath } from "@/components/chain-path";
import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { useChainExplanation } from "@/hooks/use-chain-explanation";
import type { DisplayableError } from "@/lib/api-errors";
import type { ShortestChainResponse } from "@/lib/figure-chain-types";
import { validateChainPathShape } from "@/lib/validation";

type ChainResultProps = {
  result: ShortestChainResponse | null;
  isLoading: boolean;
  error: DisplayableError | null;
  onSelectEncounter: (encounterId: string) => void;
};

export function ChainResult({
  result,
  isLoading,
  error,
  onSelectEncounter,
}: ChainResultProps) {
  const chainHash = result?.status === "found" ? result.chain_hash : null;
  const explanation = useChainExplanation(chainHash);

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
        description="选择起点和终点人物后，查询最短人物链。"
      />
    );
  }

  if (result.status === "no_path" || result.path === null) {
    return (
      <EmptyState
        title="暂未找到路径"
        description="可以调整 max_depth 后重试，或等待后续扩展更多真实 encounter 数据。"
      />
    );
  }

  const shape = validateChainPathShape(result.path);
  if (!shape.ok) {
    return (
      <ErrorCallout
        error={{
          code: "invalid_path_shape",
          message: shape.message,
          details: {},
        }}
      />
    );
  }

  const unavailableMessage =
    explanation.error?.code === "ai_result_not_found"
      ? "这条路径暂时还没有生成 AI 解释。"
      : explanation.error
        ? "AI 解释暂不可用，路径和证据仍可正常查看。"
        : null;

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-1">
        <p className="text-sm font-medium text-stone-500">查询结果</p>
        <h2 className="text-xl font-semibold text-stone-950">
          路径长度：{result.path.length}
        </h2>
      </div>
      <ChainPath path={result.path} onSelectEncounter={onSelectEncounter} />
      <ChainExplanationPanel
        explanation={explanation.explanation}
        isLoading={explanation.isLoading}
        unavailableMessage={unavailableMessage}
      />
    </section>
  );
}
