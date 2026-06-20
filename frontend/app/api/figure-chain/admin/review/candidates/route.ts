import { buildForwardPath } from "../../../_proxy";
import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

const ADMIN_REVIEW_CANDIDATE_QUERY_KEYS = [
  "kind",
  "status",
  "min_confidence",
  "person_id",
  "limit",
  "offset",
];

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  return forwardToFigureChain(
    buildForwardPath(
      "/api/v1/admin/review/candidates",
      url.searchParams,
      ADMIN_REVIEW_CANDIDATE_QUERY_KEYS,
    ),
    { headers: ADMIN_HEADERS },
  );
}
