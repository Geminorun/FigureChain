"use client";

import {
  ADMIN_REVIEW_API_BASE_PATH,
  ReviewWorkspace,
} from "@/components/review-workspace";

export function AdminReviewWorkspace() {
  return <ReviewWorkspace mode="admin" reviewApiBasePath={ADMIN_REVIEW_API_BASE_PATH} />;
}
