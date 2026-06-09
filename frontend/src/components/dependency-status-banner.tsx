import type { ReadyResponse } from "@/lib/figure-chain-types";

type DependencyStatusBannerProps = {
  ready: ReadyResponse | null;
};

export function DependencyStatusBanner({ ready }: DependencyStatusBannerProps) {
  if (ready === null || ready.status === "ready") {
    return null;
  }

  const failed = Object.entries(ready.dependencies)
    .filter(([, item]) => item.status === "error")
    .map(([name, item]) => `${name}: ${item.message ?? "unavailable"}`);

  return (
    <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
      <p className="font-medium">部分依赖不可用</p>
      <p className="mt-1">{failed.join("；")}</p>
    </div>
  );
}
