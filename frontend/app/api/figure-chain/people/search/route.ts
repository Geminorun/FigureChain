import { forwardToFigureChain } from "@/lib/api-client";

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  const query = new URLSearchParams();
  const q = url.searchParams.get("q");
  const limit = url.searchParams.get("limit");

  if (q !== null) {
    query.set("q", q);
  }
  if (limit !== null) {
    query.set("limit", limit);
  }

  return forwardToFigureChain(`/api/v1/people/search?${query.toString()}`);
}
