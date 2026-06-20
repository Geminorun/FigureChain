import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

type RouteContext = {
  params: Promise<{ encounterId: string }>;
};

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { encounterId } = await context.params;
  return forwardToFigureChain(
    `/api/v1/admin/review/encounters/${encodeURIComponent(encounterId)}/retract`,
    {
      method: "POST",
      headers: ADMIN_HEADERS,
      body: await request.text(),
    },
  );
}
