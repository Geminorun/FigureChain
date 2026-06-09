export default function Home() {
  return (
    <main className="min-h-dvh bg-stone-50 text-stone-950">
      <section className="mx-auto flex min-h-dvh w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-2 border-b border-stone-200 pb-4">
          <p className="text-sm font-medium text-amber-700">FigureChain</p>
          <h1 className="text-2xl font-semibold tracking-normal text-stone-950">
            人物链查找
          </h1>
        </header>
        <div className="rounded border border-dashed border-stone-300 bg-white p-6 text-sm text-stone-600">
          查链工作台将在后续任务中接入人物搜索、最短路径和证据详情。
        </div>
      </section>
    </main>
  );
}
