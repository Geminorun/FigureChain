import { AlertCircle } from "lucide-react";

import { errorMessageForCode, type DisplayableError } from "@/lib/api-errors";

type ErrorCalloutProps = {
  error: DisplayableError;
};

export function ErrorCallout({ error }: ErrorCalloutProps) {
  return (
    <div
      className="flex gap-3 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-900"
      role="alert"
    >
      <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="space-y-1">
        <p className="font-medium">{errorMessageForCode(error.code)}</p>
        <p className="text-red-800">{error.message}</p>
      </div>
    </div>
  );
}
