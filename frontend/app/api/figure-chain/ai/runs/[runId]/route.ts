import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type RouteContext = {
  params: Promise<{ runId: string }>;
};

export async function GET(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const { runId } = await context.params;
  return forwardToFigureChain(`/api/v1/ai/runs/${encodeURIComponent(runId)}`);
}
