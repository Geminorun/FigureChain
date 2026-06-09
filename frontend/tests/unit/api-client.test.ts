import { afterEach, describe, expect, it, vi } from "vitest";
import type { NextRequest } from "next/server";

import { POST as shortestChainRoute } from "../../app/api/figure-chain/chains/shortest/route";
import { GET as encounterRoute } from "../../app/api/figure-chain/encounters/[encounterId]/route";
import { GET as healthReadyRoute } from "../../app/api/figure-chain/health/ready/route";
import { GET as peopleSearchRoute } from "../../app/api/figure-chain/people/search/route";
import { forwardToFigureChain, getFigureChainApiBaseUrl } from "@/lib/api-client";

describe("api-client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.FIGURE_CHAIN_API_BASE_URL;
  });

  it("uses local FastAPI as the default base URL", () => {
    expect(getFigureChainApiBaseUrl()).toBe("http://127.0.0.1:8000");
  });

  it("trims trailing slashes from configured base URL", () => {
    process.env.FIGURE_CHAIN_API_BASE_URL = "http://example.test///";
    expect(getFigureChainApiBaseUrl()).toBe("http://example.test");
  });

  it("forwards upstream JSON responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "ready" }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    const response = await forwardToFigureChain("/health/ready");

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ status: "ready" });
  });

  it("returns api_unavailable when FastAPI cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connect failed")));

    const response = await forwardToFigureChain("/health/ready");

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      error: {
        code: "api_unavailable",
        message: "FigureChain API is unavailable",
        details: {},
      },
    });
  });

  it("preserves upstream error status and body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "graph_not_synced",
              message: "endpoint person is not projected to Neo4j",
              details: {},
            },
          }),
          {
            status: 409,
            headers: { "content-type": "application/json" },
          },
        ),
      ),
    );

    const response = await forwardToFigureChain("/api/v1/chains/shortest", {
      method: "POST",
      body: JSON.stringify({}),
    });

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({
      error: {
        code: "graph_not_synced",
        message: "endpoint person is not projected to Neo4j",
        details: {},
      },
    });
  });

  it("health route forwards readiness", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ready" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const response = await healthReadyRoute();

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/health/ready",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("people route forwards only supported query parameters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await peopleSearchRoute(
      new Request("http://localhost/api/figure-chain/people/search?q=許幾&limit=5&extra=1"),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/people/search?q=%E8%A8%B1%E5%B9%BE&limit=5",
      expect.any(Object),
    );
  });

  it("shortest chain route forwards the raw JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "no_path", path: null }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const body = JSON.stringify({ source: { person_id: "a" }, target: { person_id: "b" } });

    await shortestChainRoute(
      new Request("http://localhost/api/figure-chain/chains/shortest", {
        method: "POST",
        body,
      }),
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/chains/shortest",
      expect.objectContaining({ body, method: "POST" }),
    );
  });

  it("encounter route encodes ids before forwarding", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ encounter_id: "id with spaces" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await encounterRoute(
      new Request("http://localhost/api/figure-chain/encounters/id") as NextRequest,
      {
        params: Promise.resolve({ encounterId: "id with spaces" }),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/encounters/id%20with%20spaces",
      expect.any(Object),
    );
  });
});
