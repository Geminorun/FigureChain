import { buildForwardPath } from "../../_proxy";
import { forwardToFigureChain } from "@/lib/api-client";

const REVIEW_CANDIDATE_QUERY_KEYS = [
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
      "/api/v1/review/candidates",
      url.searchParams,
      REVIEW_CANDIDATE_QUERY_KEYS,
    ),
  );
}
