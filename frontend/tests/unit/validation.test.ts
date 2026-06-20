import { describe, expect, it } from "vitest";

import { canSubmitChain, getChainValidationMessage, validateChainPathShape } from "@/lib/validation";
import { oneHopPath, xuJi } from "@/test/fixtures";

describe("validation", () => {
  it("requires both endpoints before submitting", () => {
    expect(canSubmitChain(null, null, 12, false)).toBe(false);
    expect(getChainValidationMessage(null, null, 12)).toBe("请选择起点人物");
  });

  it("rejects same person endpoints", () => {
    expect(canSubmitChain(xuJi, xuJi, 12, false)).toBe(false);
    expect(getChainValidationMessage(xuJi, xuJi, 12)).toBe("起点和终点不能是同一人");
  });

  it("rejects invalid max depth", () => {
    expect(canSubmitChain(xuJi, { ...xuJi, person_id: "other" }, 21, false)).toBe(false);
    expect(getChainValidationMessage(xuJi, { ...xuJi, person_id: "other" }, 0)).toBe(
      "最大路径深度必须在 1 到 20 之间",
    );
  });

  it("validates path shape", () => {
    expect(validateChainPathShape(oneHopPath)).toEqual({ ok: true });
    expect(
      validateChainPathShape({
        ...oneHopPath,
        people: oneHopPath.people.slice(0, 1),
      }),
    ).toEqual({
      ok: false,
      message: "路径数据异常：人物数量必须等于边数量加一",
    });
  });
});
