import { buildForwardPath } from "../../../_proxy";
import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

const ADMIN_AI_JOB_QUERY_KEYS = [
  "status",
  "target_kind",
  "target_id",
  "queue_backend",
  "limit",
  "offset",
];

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  return forwardToFigureChain(
    buildForwardPath(
      "/api/v1/admin/ai/jobs",
      url.searchParams,
      ADMIN_AI_JOB_QUERY_KEYS,
    ),
    { headers: ADMIN_HEADERS },
  );
}
