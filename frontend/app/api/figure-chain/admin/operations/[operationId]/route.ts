import { forwardToFigureChain } from "@/lib/api-client";

const ADMIN_HEADERS = {
  "x-figure-role": "operator",
  "x-figure-actor": "local",
};

type OperationRouteContext = {
  params: Promise<{ operationId: string }>;
};

export async function GET(
  _request: Request,
  context: OperationRouteContext,
): Promise<Response> {
  const { operationId } = await context.params;
  return forwardToFigureChain(
    `/api/v1/admin/operations/${encodeURIComponent(operationId)}`,
    { headers: ADMIN_HEADERS },
  );
}
