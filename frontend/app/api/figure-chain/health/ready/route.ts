import { forwardToFigureChain } from "@/lib/api-client";

export async function GET(): Promise<Response> {
  return forwardToFigureChain("/health/ready");
}
