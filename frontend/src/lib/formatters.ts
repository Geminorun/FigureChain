export function formatLifeYears(
  birthYear: number | null,
  deathYear: number | null,
): string {
  if (birthYear === null && deathYear === null) {
    return "生卒年不详";
  }
  return `${birthYear ?? "?"}-${deathYear ?? "?"}`;
}

export function formatExternalIds(externalIds: string[]): string {
  return externalIds.length > 0 ? externalIds.join(", ") : "无外部 ID";
}

export function formatMaybeText(value: string | null | undefined): string {
  const trimmed = value?.trim();
  return trimmed ? trimmed : "未记录";
}

export function formatEncounterKind(value: string): string {
  const labels: Record<string, string> = {
    direct_interaction: "直接接触",
    family_contact: "家族接触",
    manual_contact: "人工确认接触",
    co_presence: "同场出现",
  };
  return labels[value] ?? value;
}

export function formatCertaintyLevel(value: string): string {
  const labels: Record<string, string> = {
    high: "高可信度",
    medium: "中可信度",
    low: "低可信度",
  };
  return labels[value] ?? value;
}

export function formatReviewedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}
