"use client";

import { useState } from "react";

import { ReviewActionPanel } from "@/components/review-action-panel";
import { ReviewAiPanel } from "@/components/review-ai-panel";
import { ReviewCandidateDetail } from "@/components/review-candidate-detail";
import {
  ReviewCandidateList,
  reviewCandidateKey,
  type ReviewCandidateListFilters,
  type ReviewCandidateSelection,
} from "@/components/review-candidate-list";
import { useAiJob } from "@/hooks/use-ai-job";
import { ADMIN_REVIEW_API_BASE_PATH, DEFAULT_REVIEW_API_BASE_PATH } from "@/hooks/review-api-options";
import { useAdminReviewActions } from "@/hooks/use-admin-review-actions";
import { useReviewActions } from "@/hooks/use-review-actions";
import { useReviewCandidateDetail } from "@/hooks/use-review-candidate-detail";
import { useReviewCandidates } from "@/hooks/use-review-candidates";

const DEFAULT_FILTERS: ReviewCandidateListFilters = {
  status: "needs_review",
  limit: 20,
  offset: 0,
};

type ReviewWorkspaceProps = {
  reviewApiBasePath?: string;
  mode?: "review" | "admin";
};

export function ReviewWorkspace({
  reviewApiBasePath = DEFAULT_REVIEW_API_BASE_PATH,
  mode = "review",
}: ReviewWorkspaceProps) {
  const [filters, setFilters] = useState<ReviewCandidateListFilters>(DEFAULT_FILTERS);
  const [selection, setSelection] = useState<ReviewCandidateSelection | null>(null);
  const candidates = useReviewCandidates(filters, { apiBasePath: reviewApiBasePath });
  const candidateDetail = useReviewCandidateDetail(
    selection?.kind ?? null,
    selection?.candidateId ?? null,
    { apiBasePath: reviewApiBasePath },
  );
  const reviewActions = useReviewActions(selection, { apiBasePath: reviewApiBasePath });
  const adminActions = useAdminReviewActions(selection);
  const actions = mode === "admin" ? adminActions : reviewActions;
  const ai = useAiJob({
    targetType: "candidate",
    targetKind: selection?.kind ?? "",
    targetId: selection?.candidateId ?? null,
  });
  const selectedCandidateKey = selection ? reviewCandidateKey(selection) : null;

  function refreshSelectedCandidate() {
    candidateDetail.refresh();
    candidates.refresh();
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(22rem,0.9fr)_minmax(0,1.1fr)]">
      <ReviewCandidateList
        data={candidates.data}
        error={candidates.error}
        filters={filters}
        isLoading={candidates.isLoading}
        selectedCandidateKey={selectedCandidateKey}
        onFiltersChange={(nextFilters) => {
          setFilters(nextFilters);
          setSelection(null);
        }}
        onRefresh={candidates.refresh}
        onSelectCandidate={setSelection}
      />

      <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-1">
        <ReviewCandidateDetail
          detail={candidateDetail.detail}
          error={candidateDetail.error}
          isLoading={candidateDetail.isLoading}
        />
        <ReviewAiPanel
          activeJob={ai.activeJob}
          detail={candidateDetail.detail}
          error={ai.error}
          isCreating={ai.isCreating}
          jobs={ai.jobs}
          eventsByJobId={ai.eventsByJobId}
          onCreateJob={ai.createJob}
          onCancelJob={ai.cancelJob}
          onRetryJob={ai.retryJob}
          onLoadEvents={ai.loadEvents}
          onRefreshCandidate={refreshSelectedCandidate}
        />
        <ReviewActionPanel
          detail={candidateDetail.detail}
          error={actions.error}
          isRetracting={mode === "admin" ? adminActions.isRetracting : false}
          isSubmitting={actions.isSubmitting}
          onActionComplete={refreshSelectedCandidate}
          onMarkNeedsReview={actions.markNeedsReview}
          onPromote={actions.promote}
          onReject={actions.reject}
          onRetractEncounter={mode === "admin" ? adminActions.retractEncounter : undefined}
          retractError={mode === "admin" ? adminActions.retractError : null}
        />
      </div>
    </div>
  );
}

export { ADMIN_REVIEW_API_BASE_PATH };
