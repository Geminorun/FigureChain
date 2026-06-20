import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

type RouteContext = {
  params: Promise<{ kind: string; candidateId: string }>;
};

export async function GET(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { kind, candidateId } = await context.params;
  return forwardToFigureChain(
    `/api/v1/admin/review/candidates/${encodeURIComponent(kind)}/${encodeURIComponent(candidateId)}`,
    { headers: ADMIN_HEADERS },
  );
}
