const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export function getFigureChainApiBaseUrl(): string {
  const configured = process.env.FIGURE_CHAIN_API_BASE_URL?.trim();
  if (!configured) {
    return DEFAULT_API_BASE_URL;
  }
  return configured.replace(/\/+$/, "");
}

export async function forwardToFigureChain(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const baseUrl = getFigureChainApiBaseUrl();
  const upstreamUrl = `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;

  try {
    const upstream = await fetch(upstreamUrl, {
      ...init,
      headers: {
        accept: "application/json",
        ...(init.body === undefined ? {} : { "content-type": "application/json" }),
        ...init.headers,
      },
      cache: "no-store",
    });

    const contentType = upstream.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return Response.json(
        {
          error: {
            code: "api_unavailable",
            message: "FigureChain API returned a non-JSON response",
            details: {},
          },
        },
        { status: 502 },
      );
    }

    const body = await upstream.text();
    return new Response(body, {
      status: upstream.status,
      headers: {
        "content-type": "application/json",
      },
    });
  } catch {
    return Response.json(
      {
        error: {
          code: "api_unavailable",
          message: "FigureChain API is unavailable",
          details: {},
        },
      },
      { status: 502 },
    );
  }
}
