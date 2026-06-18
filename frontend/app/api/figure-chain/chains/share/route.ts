import { forwardToFigureChain } from "@/lib/api-client";

export async function POST(request: Request): Promise<Response> {
  const body = await request.text();
  return forwardToFigureChain("/api/v1/chains/share", {
    method: "POST",
    body,
  });
}
