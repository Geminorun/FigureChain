import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type SourceWorkRouteContext = {
  params: Promise<{ sourceWorkId: string }>;
};

export async function GET(
  _request: NextRequest,
  context: SourceWorkRouteContext,
): Promise<Response> {
  const params = await context.params;
  return forwardToFigureChain(
    `/api/v1/source-works/${encodeURIComponent(params.sourceWorkId)}`,
  );
}
