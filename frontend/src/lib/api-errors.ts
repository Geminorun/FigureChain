import type { ErrorBody, ErrorResponse } from "@/lib/figure-chain-types";

export type DisplayableError = ErrorBody;

export function isDisplayableError(value: unknown): value is DisplayableError {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { code?: unknown }).code === "string" &&
    typeof (value as { message?: unknown }).message === "string"
  );
}

export function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== "object" || value === null || !("error" in value)) {
    return false;
  }
  const error = (value as { error: unknown }).error;
  return isDisplayableError(error);
}

export function parseErrorResponse(value: unknown): DisplayableError {
  if (isDisplayableError(value)) {
    return {
      code: value.code,
      message: value.message,
      details: value.details ?? {},
    };
  }
  if (isErrorResponse(value)) {
    return {
      code: value.error.code,
      message: value.error.message,
      details: value.error.details ?? {},
    };
  }
  return {
    code: "unknown_error",
    message: "请求失败",
    details: {},
  };
}

export function errorMessageForCode(code: string): string {
  const messages: Record<string, string> = {
    person_not_found: "人物不存在或已变更，请重新搜索选择",
    person_ambiguous: "人物名称存在歧义，请从候选人物中明确选择",
    same_person_endpoint: "起点和终点不能是同一人",
    graph_not_synced: "图投影尚未同步，请先同步 Neo4j 图数据",
    dependency_unavailable: "依赖服务不可用，请稍后重试",
    configuration_error: "服务配置不可用",
    invalid_request: "请求参数不正确",
    encounter_not_found: "证据记录不存在或已变更",
    api_unavailable: "FigureChain API 不可用",
  };
  return messages[code] ?? "请求失败";
}
