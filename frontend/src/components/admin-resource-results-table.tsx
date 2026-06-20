import Link from "next/link";

import type { AdminResourceColumn } from "@/lib/figure-chain-types";

type AdminResourceResultsTableProps = {
  columns: AdminResourceColumn[];
  rows: Record<string, unknown>[];
};

function linkForValue(link: string | null, value: unknown): string | null {
  if (link === null || value === null || value === undefined) {
    return null;
  }
  const encoded = encodeURIComponent(String(value));
  const routes: Record<string, string> = {
    person: `/people/${encoded}`,
    encounter: `/encounters/${encoded}`,
    "candidate:relationship": `/admin/review?kind=relationship&candidate_id=${encoded}`,
    "candidate:kinship": `/admin/review?kind=kinship&candidate_id=${encoded}`,
    source_ref: `/source-refs/${encoded}`,
    source_work: `/source-works/${encoded}`,
    ai_job: `/admin/jobs?job_id=${encoded}`,
    graph_projection_batch: `/admin/graph?batch_id=${encoded}`,
    admin_operation: `/admin/operations?operation_id=${encoded}`,
  };
  return routes[link] ?? null;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "无";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export function AdminResourceResultsTable({
  columns,
  rows,
}: AdminResourceResultsTableProps) {
  if (rows.length === 0) {
    return (
      <div className="rounded border border-dashed border-stone-300 bg-stone-50 p-4 text-sm text-stone-600">
        当前查询没有返回记录。
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-stone-200 bg-white">
      <table className="min-w-full table-fixed divide-y divide-stone-200 text-left text-sm">
        <thead className="bg-stone-100 text-xs font-semibold text-stone-600">
          <tr>
            {columns.map((column) => (
              <th className="w-56 px-3 py-2" key={column.key}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {rows.map((row, rowIndex) => (
            <tr className="align-top" key={rowIndex}>
              {columns.map((column) => {
                const value = row[column.key];
                const text = formatValue(value);
                const href = linkForValue(column.link, value);
                return (
                  <td className="px-3 py-2 text-stone-800" key={column.key}>
                    {href ? (
                      <Link
                        className="font-mono text-xs text-amber-800 underline-offset-2 hover:underline"
                        href={href}
                      >
                        {text}
                      </Link>
                    ) : (
                      <span className="break-words font-mono text-xs">{text}</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
