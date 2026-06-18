import { ReviewWorkspace } from "@/components/review-workspace";

export default function ReviewPage() {
  return (
    <main className="min-h-screen bg-stone-100 px-4 py-6 text-stone-950 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <header>
          <h1 className="text-2xl font-semibold tracking-normal text-stone-950">
            候选审核工作台
          </h1>
          <p className="mt-2 max-w-3xl text-sm text-stone-600">
            查看候选证据、生成 AI 辅助建议，并执行人工审核动作。
          </p>
        </header>
        <ReviewWorkspace />
      </div>
    </main>
  );
}
