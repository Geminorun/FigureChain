import { forwardToFigureChain } from "@/lib/api-client";

type RouteContext = {
  params: Promise<{ shareSlug: string }>;
};

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  const { shareSlug } = await context.params;
  return forwardToFigureChain(
    `/api/v1/chains/share/${encodeURIComponent(shareSlug)}`,
  );
}
