import type { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { GET as getPersonRoute } from "../../app/api/figure-chain/people/[personId]/route";
import { GET as listPersonEncountersRoute } from "../../app/api/figure-chain/people/[personId]/encounters/route";
import { GET as getSourceRefRoute } from "../../app/api/figure-chain/source-refs/[sourceRefId]/route";
import { GET as getSourceWorkRoute } from "../../app/api/figure-chain/source-works/[sourceWorkId]/route";

function stubJsonFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("person evidence API routes", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("forwards person detail requests with encoded person ids", async () => {
    const fetchMock = stubJsonFetch();

    await getPersonRoute(
      new Request("http://localhost/api/figure-chain/people/id") as NextRequest,
      {
        params: Promise.resolve({ personId: "person id" }),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/people/person%20id",
      expect.any(Object),
    );
  });

  it("forwards person encounter filters and drops unsupported query keys", async () => {
    const fetchMock = stubJsonFetch();

    await listPersonEncountersRoute(
      new Request(
        "http://localhost/api/figure-chain/people/id/encounters?status=active&path_eligible=true&certainty_level=high&encounter_kind=direct_interaction&limit=20&offset=0&ignored=1",
      ) as NextRequest,
      {
        params: Promise.resolve({ personId: "person id" }),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/people/person%20id/encounters?status=active&path_eligible=true&certainty_level=high&encounter_kind=direct_interaction&limit=20&offset=0",
      expect.any(Object),
    );
  });

  it("forwards source work requests with encoded ids", async () => {
    const fetchMock = stubJsonFetch();

    await getSourceWorkRoute(
      new Request("http://localhost/api/figure-chain/source-works/id") as NextRequest,
      {
        params: Promise.resolve({ sourceWorkId: "source work" }),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/source-works/source%20work",
      expect.any(Object),
    );
  });

  it("forwards source ref requests with encoded ids", async () => {
    const fetchMock = stubJsonFetch();

    await getSourceRefRoute(
      new Request("http://localhost/api/figure-chain/source-refs/id") as NextRequest,
      {
        params: Promise.resolve({ sourceRefId: "source ref" }),
      },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/source-refs/source%20ref",
      expect.any(Object),
    );
  });
});
