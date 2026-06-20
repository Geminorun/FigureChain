import { AdminReviewWorkspace } from "@/components/admin-review-workspace";

export default function AdminReviewPage() {
  return (
    <main className="min-h-screen bg-stone-100 px-4 py-6 text-stone-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <header>
          <h1 className="text-2xl font-semibold tracking-normal text-stone-950">
            后台审核工作台
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-stone-600">
            查看候选证据、生成 AI 辅助建议，并执行带操作留痕的后台审核动作。
          </p>
        </header>
        <AdminReviewWorkspace />
      </div>
    </main>
  );
}
