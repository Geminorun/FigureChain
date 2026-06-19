import type { NextRequest } from "next/server";

import { forwardToFigureChain } from "@/lib/api-client";

import { buildForwardPath } from "../../../_proxy";

const PERSON_ENCOUNTER_QUERY_KEYS = [
  "status",
  "path_eligible",
  "certainty_level",
  "encounter_kind",
  "limit",
  "offset",
];

type PersonEncountersRouteContext = {
  params: Promise<{ personId: string }>;
};

export async function GET(
  request: NextRequest,
  context: PersonEncountersRouteContext,
): Promise<Response> {
  const params = await context.params;
  const url = new URL(request.url);
  return forwardToFigureChain(
    buildForwardPath(
      `/api/v1/people/${encodeURIComponent(params.personId)}/encounters`,
      url.searchParams,
      PERSON_ENCOUNTER_QUERY_KEYS,
    ),
  );
}
