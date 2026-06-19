import { forwardToFigureChain } from "@/lib/api-client";

type RouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function GET(
  _request: Request,
  context: RouteContext,
): Promise<Response> {
  const { jobId } = await context.params;
  return forwardToFigureChain(
    `/api/v1/ai/jobs/${encodeURIComponent(jobId)}/events`,
  );
}
