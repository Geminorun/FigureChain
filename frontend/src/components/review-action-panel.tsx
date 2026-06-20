"use client";

import { Check, RotateCcw, X } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { ErrorCallout } from "@/components/error-callout";
import { parseErrorResponse, type DisplayableError } from "@/lib/api-errors";
import type {
  AdminEncounterRetractRequest,
  AdminEncounterRetractResponse,
  AdminReviewActionResponse,
  ReviewActionRequest,
  ReviewActionResponse,
  ReviewCandidateDetail,
} from "@/lib/figure-chain-types";

type ReviewActionPanelResponse = ReviewActionResponse | AdminReviewActionResponse;

type ReviewActionPanelProps = {
  detail: ReviewCandidateDetail | null;
  error: DisplayableError | null;
  isRetracting?: boolean;
  isSubmitting: boolean;
  onActionComplete: (response: ReviewActionPanelResponse | AdminEncounterRetractResponse) => void;
  onMarkNeedsReview: (request: ReviewActionRequest) => Promise<ReviewActionPanelResponse | null>;
  onPromote: (request: ReviewActionRequest) => Promise<ReviewActionPanelResponse | null>;
  onReject: (request: ReviewActionRequest) => Promise<ReviewActionPanelResponse | null>;
  onRetractEncounter?: (
    encounterId: string,
    request: AdminEncounterRetractRequest,
  ) => Promise<AdminEncounterRetractResponse | null>;
  retractError?: DisplayableError | null;
};

async function runAction(
  action: () => Promise<ReviewActionPanelResponse | AdminEncounterRetractResponse | null>,
  onActionComplete: (response: ReviewActionPanelResponse | AdminEncounterRetractResponse) => void,
  onError: (error: DisplayableError) => void,
) {
  try {
    const response = await action();
    if (response) {
      onActionComplete(response);
    }
  } catch (error: unknown) {
    onError(parseErrorResponse(error));
  }
}

export function ReviewActionPanel({
  detail,
  error,
  isRetracting = false,
  isSubmitting,
  onActionComplete,
  onMarkNeedsReview,
  onPromote,
  onReject,
  onRetractEncounter,
  retractError = null,
}: ReviewActionPanelProps) {
  const [reviewedBy, setReviewedBy] = useState("");
  const [evidenceSummary, setEvidenceSummary] = useState("");
  const [promoteNote, setPromoteNote] = useState("");
  const [allowNonDefault, setAllowNonDefault] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [retractNote, setRetractNote] = useState("");
  const [forceRetract, setForceRetract] = useState(false);
  const [lastOperation, setLastOperation] = useState<{
    operationId: string;
    preview: string;
  } | null>(null);
  const [localError, setLocalError] = useState<DisplayableError | null>(null);
  const reviewerReady = reviewedBy.trim().length > 0;
  const busy = isSubmitting || isRetracting;
  const promoteReady =
    detail !== null &&
    reviewerReady &&
    evidenceSummary.trim().length > 0 &&
    (detail.promotion_readiness.default_promotable || allowNonDefault) &&
    !busy;
  const rejectReady = detail !== null && reviewerReady && rejectReason.trim().length > 0 && !busy;
  const needsReviewReady = detail !== null && reviewerReady && !busy;
  const retractReady =
    detail?.linked_encounter !== null &&
    detail?.linked_encounter !== undefined &&
    onRetractEncounter !== undefined &&
    reviewerReady &&
    retractNote.trim().length > 0 &&
    !busy;

  function complete(response: ReviewActionPanelResponse | AdminEncounterRetractResponse) {
    setLocalError(null);
    if ("operation_id" in response) {
      setLastOperation({
        operationId: response.operation_id,
        preview: response.preview,
      });
    }
    onActionComplete(response);
  }

  async function handlePromote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!promoteReady) {
      return;
    }
    await runAction(
      () =>
        onPromote({
          reviewed_by: reviewedBy.trim(),
          evidence_summary: evidenceSummary.trim(),
          note: promoteNote.trim().length > 0 ? promoteNote.trim() : null,
          allow_non_default: allowNonDefault,
        }),
      complete,
      setLocalError,
    );
  }

  async function handleReject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!rejectReady) {
      return;
    }
    await runAction(
      () =>
        onReject({
          reviewed_by: reviewedBy.trim(),
          reason: rejectReason.trim(),
        }),
      complete,
      setLocalError,
    );
  }

  async function handleNeedsReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!needsReviewReady) {
      return;
    }
    await runAction(
      () =>
        onMarkNeedsReview({
          reviewed_by: reviewedBy.trim(),
          note: reviewNote.trim().length > 0 ? reviewNote.trim() : null,
        }),
      complete,
      setLocalError,
    );
  }

  async function handleRetract(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const encounterId = detail?.linked_encounter?.encounter_id;
    if (!retractReady || !encounterId || !onRetractEncounter) {
      return;
    }
    await runAction(
      () =>
        onRetractEncounter(encounterId, {
          reviewed_by: reviewedBy.trim(),
          note: retractNote.trim(),
          force: forceRetract,
        }),
      complete,
      setLocalError,
    );
  }

  return (
    <section className="rounded border border-stone-200 bg-white p-4 shadow-sm">
      <h2 className="text-base font-semibold text-stone-950">审核动作</h2>
      <div className="mt-4 space-y-4">
        {error ? <ErrorCallout error={error} /> : null}
        {retractError ? <ErrorCallout error={retractError} /> : null}
        {localError ? <ErrorCallout error={localError} /> : null}
        {lastOperation ? (
          <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950">
            <p className="font-medium">操作已记录：{lastOperation.operationId}</p>
            <p className="mt-1">{lastOperation.preview}</p>
          </div>
        ) : null}
        {detail === null ? (
          <EmptyState title="尚未选择候选" description="选择候选后可执行审核动作。" />
        ) : null}

        <label className="block text-sm font-medium text-stone-800">
          reviewed_by
          <input
            className="mt-1 min-h-10 w-full rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
            type="text"
            value={reviewedBy}
            onChange={(event) => setReviewedBy(event.target.value)}
          />
        </label>

        {detail && !detail.promotion_readiness.default_promotable ? (
          <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
            默认不可提升：{detail.promotion_readiness.reasons.join("; ") || "未给出原因"}
          </div>
        ) : null}

        <form className="space-y-3 border-t border-stone-200 pt-4" onSubmit={handlePromote}>
          <label className="block text-sm font-medium text-stone-800">
            evidence summary
            <textarea
              className="mt-1 min-h-24 w-full resize-y rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              value={evidenceSummary}
              onChange={(event) => setEvidenceSummary(event.target.value)}
            />
          </label>
          <label className="block text-sm font-medium text-stone-800">
            promote note
            <textarea
              className="mt-1 min-h-16 w-full resize-y rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              value={promoteNote}
              onChange={(event) => setPromoteNote(event.target.value)}
            />
          </label>
          <label className="flex items-center gap-2 text-sm text-stone-800">
            <input
              checked={allowNonDefault}
              className="h-4 w-4"
              type="checkbox"
              onChange={(event) => setAllowNonDefault(event.target.checked)}
            />
            allow_non_default
          </label>
          <button
            className="inline-flex min-h-10 items-center gap-2 rounded bg-stone-950 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-stone-300"
            disabled={!promoteReady}
            type="submit"
          >
            <Check aria-hidden="true" className="h-4 w-4" />
            提升为 encounter
          </button>
        </form>

        <form className="space-y-3 border-t border-stone-200 pt-4" onSubmit={handleReject}>
          <label className="block text-sm font-medium text-stone-800">
            reject reason
            <textarea
              className="mt-1 min-h-20 w-full resize-y rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              value={rejectReason}
              onChange={(event) => setRejectReason(event.target.value)}
            />
          </label>
          <button
            className="inline-flex min-h-10 items-center gap-2 rounded border border-red-300 px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-300 focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-stone-300 disabled:text-stone-400"
            disabled={!rejectReady}
            type="submit"
          >
            <X aria-hidden="true" className="h-4 w-4" />
            拒绝候选
          </button>
        </form>

        <form className="space-y-3 border-t border-stone-200 pt-4" onSubmit={handleNeedsReview}>
          <label className="block text-sm font-medium text-stone-800">
            review note
            <textarea
              className="mt-1 min-h-16 w-full resize-y rounded border border-stone-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
              value={reviewNote}
              onChange={(event) => setReviewNote(event.target.value)}
            />
          </label>
          <button
            className="inline-flex min-h-10 items-center gap-2 rounded border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:text-stone-400"
            disabled={!needsReviewReady}
            type="submit"
          >
            <RotateCcw aria-hidden="true" className="h-4 w-4" />
            标记待复核
          </button>
        </form>

        {detail?.linked_encounter && onRetractEncounter ? (
          <form className="space-y-3 border-t border-stone-200 pt-4" onSubmit={handleRetract}>
            <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-950">
              当前候选已关联 Encounter：{detail.linked_encounter.encounter_id}
            </div>
            <label className="block text-sm font-medium text-stone-800">
              撤回原因
              <textarea
                className="mt-1 min-h-20 w-full resize-y rounded border border-stone-300 px-3 py-2 text-sm focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-200"
                value={retractNote}
                onChange={(event) => setRetractNote(event.target.value)}
              />
            </label>
            <label className="flex items-center gap-2 text-sm text-stone-800">
              <input
                checked={forceRetract}
                className="h-4 w-4"
                type="checkbox"
                onChange={(event) => setForceRetract(event.target.checked)}
              />
              强制撤回
            </label>
            <button
              className="inline-flex min-h-10 items-center gap-2 rounded border border-red-400 px-4 py-2 text-sm font-medium text-red-800 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-300 focus:ring-offset-2 disabled:cursor-not-allowed disabled:border-stone-300 disabled:text-stone-400"
              disabled={!retractReady}
              type="submit"
            >
              <X aria-hidden="true" className="h-4 w-4" />
              撤回 Encounter
            </button>
          </form>
        ) : null}
      </div>
    </section>
  );
}
