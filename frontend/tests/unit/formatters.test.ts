import { describe, expect, it } from "vitest";

import {
  formatExternalIds,
  formatLifeYears,
  formatMaybeText,
  formatReviewedAt,
} from "@/lib/formatters";

describe("formatters", () => {
  it("formats life years with unknown values", () => {
    expect(formatLifeYears(1054, 1115)).toBe("1054-1115");
    expect(formatLifeYears(1054, null)).toBe("1054-?");
    expect(formatLifeYears(null, 1115)).toBe("?-1115");
    expect(formatLifeYears(null, null)).toBe("生卒年不详");
  });

  it("formats external ids", () => {
    expect(formatExternalIds(["780", "wikidata:Q1"])).toBe("780, wikidata:Q1");
    expect(formatExternalIds([])).toBe("无外部 ID");
  });

  it("formats empty text consistently", () => {
    expect(formatMaybeText("11905")).toBe("11905");
    expect(formatMaybeText("")).toBe("未记录");
    expect(formatMaybeText(null)).toBe("未记录");
  });

  it("formats ISO timestamps without throwing", () => {
    expect(formatReviewedAt("2026-06-09T00:00:00Z")).toContain("2026");
    expect(formatReviewedAt("bad-date")).toBe("bad-date");
  });
});
