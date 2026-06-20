import { Suspense } from "react";

import { AdminOperationsPage } from "@/components/admin-operations-page";

export default function OperationsPage() {
  return (
    <Suspense fallback={<p className="text-sm text-stone-600">正在加载操作历史...</p>}>
      <AdminOperationsPage />
    </Suspense>
  );
}
