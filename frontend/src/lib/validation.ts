import type { ChainPath, PersonSearchItem } from "@/lib/figure-chain-types";

export type ValidationResult =
  | { ok: true }
  | {
      ok: false;
      message: string;
    };

export function getChainValidationMessage(
  source: PersonSearchItem | null,
  target: PersonSearchItem | null,
  maxDepth: number,
): string | null {
  if (source === null) {
    return "请选择起点人物";
  }
  if (target === null) {
    return "请选择终点人物";
  }
  if (source.person_id === target.person_id) {
    return "起点和终点不能是同一人";
  }
  if (!Number.isInteger(maxDepth) || maxDepth < 1 || maxDepth > 20) {
    return "max_depth 必须在 1 到 20 之间";
  }
  return null;
}

export function canSubmitChain(
  source: PersonSearchItem | null,
  target: PersonSearchItem | null,
  maxDepth: number,
  isLoading: boolean,
): boolean {
  return !isLoading && getChainValidationMessage(source, target, maxDepth) === null;
}

export function validateChainPathShape(path: ChainPath): ValidationResult {
  if (path.people.length !== path.edges.length + 1) {
    return {
      ok: false,
      message: "路径数据异常：人物数量必须等于边数量加一",
    };
  }
  if (path.length !== path.edges.length) {
    return {
      ok: false,
      message: "路径数据异常：路径长度必须等于边数量",
    };
  }
  return { ok: true };
}
