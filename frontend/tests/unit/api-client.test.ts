import { afterEach, describe, expect, it, vi } from "vitest";

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
});
