const ADMIN_SECTIONS = [
  {
    href: "/admin/operations",
    title: "操作历史",
    description: "查看后台维护动作、图同步和 AI 任务的本地审计记录。",
  },
  {
    href: "/admin/graph",
    title: "图同步",
    description: "后续用于触发重建、增量同步和查看投影状态。",
  },
  {
    href: "/admin/review",
    title: "候选审核",
    description: "后续用于进入候选审核和证据扩展工作流。",
  },
  {
    href: "/admin/diagnostics",
    title: "运行诊断",
    description: "后续用于查看 PostgreSQL、Neo4j、Redis 和 AI provider 状态。",
  },
];

export default function AdminHomePage() {
  return (
    <section className="space-y-4">
      <div className="border-b border-stone-200 pb-4">
        <p className="text-sm font-medium text-amber-700">后台概览</p>
        <h2 className="mt-1 text-xl font-semibold text-stone-950">
          本地维护入口
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-stone-600">
          当前后台面向本机维护使用，优先承载可审计的操作入口和运行状态检查。
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {ADMIN_SECTIONS.map((section) => (
          <a
            className="rounded border border-stone-200 bg-white p-4 hover:bg-stone-50"
            href={section.href}
            key={section.href}
          >
            <h3 className="font-semibold text-stone-950">{section.title}</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              {section.description}
            </p>
          </a>
        ))}
      </div>
    </section>
  );
}
