"use client";

import { EncounterEvidenceView } from "@/components/encounter-detail-page";
import { ErrorCallout } from "@/components/error-callout";
import { useEncounterDetail } from "@/hooks/use-encounter-detail";

type EvidencePanelProps = {
  encounterId: string | null;
};

export function EvidencePanel({ encounterId }: EvidencePanelProps) {
  const { detail, isLoading, error } = useEncounterDetail(encounterId);

  if (encounterId === null) {
    return (
      <aside className="rounded border border-dashed border-stone-300 bg-stone-50 p-4 text-sm text-stone-600">
        选择路径中的一条边查看证据详情。
      </aside>
    );
  }

  if (isLoading) {
    return (
      <aside className="rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
        证据加载中...
      </aside>
    );
  }

  if (error) {
    return <ErrorCallout error={error} />;
  }

  if (detail === null) {
    return null;
  }

  return <EncounterEvidenceView detail={detail} />;
}
