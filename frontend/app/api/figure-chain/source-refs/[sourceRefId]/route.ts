import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type SourceRefRouteContext = {
  params: Promise<{ sourceRefId: string }>;
};

export async function GET(
  _request: NextRequest,
  context: SourceRefRouteContext,
): Promise<Response> {
  const params = await context.params;
  return forwardToFigureChain(
    `/api/v1/source-refs/${encodeURIComponent(params.sourceRefId)}`,
  );
}
