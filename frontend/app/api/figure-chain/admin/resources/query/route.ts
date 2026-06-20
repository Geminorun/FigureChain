import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

export async function POST(request: Request): Promise<Response> {
  return forwardToFigureChain("/api/v1/admin/resources/query", {
    method: "POST",
    headers: ADMIN_HEADERS,
    body: await request.text(),
  });
}
