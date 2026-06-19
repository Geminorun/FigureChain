import { forwardToFigureChain } from "@/lib/api-client";

type RouteContext = {
  params: Promise<{ jobId: string }>;
};

export async function POST(
  request: Request,
  context: RouteContext,
): Promise<Response> {
  const { jobId } = await context.params;
  const body = await request.text();
  return forwardToFigureChain(
    `/api/v1/ai/jobs/${encodeURIComponent(jobId)}/cancel`,
    {
      method: "POST",
      body,
    },
  );
}
