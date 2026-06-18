import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type RouteContext = {
  params: Promise<{ kind: string; candidateId: string }>;
};

export async function POST(
  request: NextRequest,
  context: RouteContext,
): Promise<Response> {
  const { kind, candidateId } = await context.params;
  const body = await request.text();
  return forwardToFigureChain(
    `/api/v1/review/candidates/${encodeURIComponent(kind)}/${encodeURIComponent(candidateId)}/needs-review`,
    {
      method: "POST",
      body,
    },
  );
}
