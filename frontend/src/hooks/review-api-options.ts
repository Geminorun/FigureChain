export type ReviewApiOptions = {
  apiBasePath?: string;
};

export const DEFAULT_REVIEW_API_BASE_PATH = "/api/figure-chain/review";
export const ADMIN_REVIEW_API_BASE_PATH = "/api/figure-chain/admin/review";

export function resolveReviewApiBasePath(options: ReviewApiOptions = {}): string {
  return (options.apiBasePath ?? DEFAULT_REVIEW_API_BASE_PATH).replace(/\/+$/, "");
}
