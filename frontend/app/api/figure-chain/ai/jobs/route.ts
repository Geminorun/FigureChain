import { buildForwardPath } from "../../_proxy";
import { forwardToFigureChain } from "@/lib/api-client";

const AI_JOB_QUERY_KEYS = ["target_type", "target_kind", "target_id", "limit"];

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  return forwardToFigureChain(
    buildForwardPath("/api/v1/ai/jobs", url.searchParams, AI_JOB_QUERY_KEYS),
  );
}

export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  return forwardToFigureChain("/api/v1/ai/jobs", {
    method: "POST",
    body,
  });
}
