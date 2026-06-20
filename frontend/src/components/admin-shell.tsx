import Link from "next/link";
import type { ReactNode } from "react";

const NAV_ITEMS = [
  { href: "/admin", label: "概览" },
  { href: "/admin/data", label: "数据" },
  { href: "/admin/graph", label: "图同步" },
  { href: "/admin/jobs", label: "AI jobs" },
  { href: "/admin/review", label: "审核" },
  { href: "/admin/operations", label: "操作历史" },
  { href: "/admin/diagnostics", label: "诊断" },
];

export function AdminShell({ children }: { children: ReactNode }) {
  return (
    <main className="min-h-dvh bg-stone-50 text-stone-950">
      <section className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
        <header className="border-b border-stone-200 pb-4">
          <p className="text-sm font-medium text-amber-700">FigureChain Admin</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-normal text-stone-950">
            本地系统控制台
          </h1>
          <nav className="mt-4 flex flex-wrap gap-2 text-sm">
            {NAV_ITEMS.map((item) => (
              <Link
                className="rounded border border-stone-300 bg-white px-3 py-1.5 text-stone-800 hover:bg-stone-100"
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        {children}
      </section>
    </main>
  );
}
