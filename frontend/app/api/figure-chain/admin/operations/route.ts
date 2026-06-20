import { buildForwardPath } from "../../_proxy";
import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

const ADMIN_OPERATION_QUERY_KEYS = [
  "status",
  "operation_type",
  "actor",
  "limit",
  "offset",
];

export async function GET(request: Request): Promise<Response> {
  const url = new URL(request.url);
  return forwardToFigureChain(
    buildForwardPath(
      "/api/v1/admin/operations",
      url.searchParams,
      ADMIN_OPERATION_QUERY_KEYS,
    ),
    { headers: ADMIN_HEADERS },
  );
}
