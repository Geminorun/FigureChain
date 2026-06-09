import { describe, expect, it } from "vitest";

import { errorMessageForCode, parseErrorResponse } from "@/lib/api-errors";

describe("api-errors", () => {
  it("parses FastAPI error responses", () => {
    expect(
      parseErrorResponse({
        error: {
          code: "dependency_unavailable",
          message: "Neo4j is unavailable",
          details: {},
        },
      }),
    ).toEqual({
      code: "dependency_unavailable",
      message: "Neo4j is unavailable",
      details: {},
    });
  });

  it("falls back for unknown error shapes", () => {
    expect(parseErrorResponse({ nope: true })).toEqual({
      code: "unknown_error",
      message: "请求失败",
      details: {},
    });
  });

  it("keeps already parsed displayable errors", () => {
    expect(
      parseErrorResponse({
        code: "graph_not_synced",
        message: "endpoint person is not projected to Neo4j",
        details: {},
      }),
    ).toEqual({
      code: "graph_not_synced",
      message: "endpoint person is not projected to Neo4j",
      details: {},
    });
  });

  it("returns user-facing messages for known codes", () => {
    expect(errorMessageForCode("same_person_endpoint")).toBe("起点和终点不能是同一人");
    expect(errorMessageForCode("graph_not_synced")).toBe(
      "图投影尚未同步，请先同步 Neo4j 图数据",
    );
    expect(errorMessageForCode("custom")).toBe("请求失败");
  });
});
