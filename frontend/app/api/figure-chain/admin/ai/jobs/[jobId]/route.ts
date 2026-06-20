import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

type RouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const { jobId } = await context.params;
  return forwardToFigureChain(
    `/api/v1/admin/ai/jobs/${encodeURIComponent(jobId)}`,
    { headers: ADMIN_HEADERS },
  );
}
