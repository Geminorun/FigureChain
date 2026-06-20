import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

export async function GET(): Promise<Response> {
  return forwardToFigureChain("/api/v1/admin/graph/status", {
    headers: ADMIN_HEADERS,
  });
}
