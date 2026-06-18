import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type PersonRouteContext = {
  params: Promise<{ personId: string }>;
};

export async function GET(
  _request: NextRequest,
  context: PersonRouteContext,
): Promise<Response> {
  const params = await context.params;
  return forwardToFigureChain(`/api/v1/people/${encodeURIComponent(params.personId)}`);
}
