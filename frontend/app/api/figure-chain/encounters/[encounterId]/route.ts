import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

type EncounterRouteContext = {
  params: Promise<{ encounterId: string }>;
};

export async function GET(
  _request: NextRequest,
  context: EncounterRouteContext,
): Promise<Response> {
  const params = await context.params;
  return forwardToFigureChain(
    `/api/v1/encounters/${encodeURIComponent(params.encounterId)}`,
  );
}
