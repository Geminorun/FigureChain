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
