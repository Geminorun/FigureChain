import { Sparkles } from "lucide-react";

import type { AIChainExplanation } from "@/lib/figure-chain-types";

type ChainExplanationPanelProps = {
  explanation: AIChainExplanation | null;
  isLoading: boolean;
  unavailableMessage: string | null;
};

export function ChainExplanationPanel({
  explanation,
  isLoading,
  unavailableMessage,
}: ChainExplanationPanelProps) {
  if (isLoading) {
    return (
      <section className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        AI 解释加载中...
      </section>
    );
  }

  if (explanation === null) {
    if (!unavailableMessage) {
      return null;
    }
    return (
      <section className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        {unavailableMessage}
      </section>
    );
  }

  return (
    <section className="space-y-3 rounded border border-stone-200 bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-stone-700">
        <Sparkles aria-hidden="true" className="h-4 w-4 text-amber-600" />
        <span>AI 解释</span>
      </div>
      <p className="text-sm leading-6 text-stone-800">{explanation.summary}</p>
      <div className="space-y-2">
        {explanation.edge_explanations.map((edge) => (
          <div
            key={edge.encounter_id}
            className="border-l-2 border-amber-300 pl-3 text-sm text-stone-700"
          >
            <p>{edge.explanation}</p>
            <p className="mt-1 text-xs text-stone-500">
              接触记录 ID：{edge.encounter_id}
            </p>
          </div>
        ))}
      </div>
      <p className="text-xs text-stone-500">
        生成时间：{new Date(explanation.created_at).toLocaleString()}
      </p>
    </section>
  );
}
