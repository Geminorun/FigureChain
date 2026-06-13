import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type RouteContext = {
  params: Promise<{ chainHash: string }>;
};

export async function GET(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const { chainHash } = await context.params;
  return forwardToFigureChain(
    `/api/v1/ai/chains/explanations/${encodeURIComponent(chainHash)}`,
  );
}
