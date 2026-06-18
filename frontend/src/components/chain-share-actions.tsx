"use client";

import { Download, Link2, Share2 } from "lucide-react";
import { useState } from "react";

import { ErrorCallout } from "@/components/error-callout";
import { useChainShare } from "@/hooks/use-chain-share";
import type {
  ChainShareCreateResponse,
  MarkdownExportResponse,
  MultiPathChainResponse,
  MultiPathItem,
} from "@/lib/figure-chain-types";

type ChainShareActionsProps = {
  path: MultiPathItem;
  result: MultiPathChainResponse;
};

export function ChainShareActions({ path, result }: ChainShareActionsProps) {
  const share = useChainShare();
  const [createdShare, setCreatedShare] = useState<ChainShareCreateResponse | null>(null);
  const [markdown, setMarkdown] = useState<MarkdownExportResponse | null>(null);
  const exportFailed = share.error !== null && createdShare !== null && markdown === null;

  async function handleCreateShare() {
    try {
      const response = await share.createShare({
        source_person_id: result.source_person_id,
        target_person_id: result.target_person_id,
        chain_hash: path.chain_hash,
        path_payload: {
          length: path.length,
          people: path.people,
          edges: path.edges,
        },
        filters_applied: result.filters_applied,
        include_ai_explanation: false,
        include_rag_context: false,
        created_by: null,
      });
      setCreatedShare(response);
      setMarkdown(null);
    } catch {
      setCreatedShare(null);
      setMarkdown(null);
    }
  }

  async function handleExportMarkdown() {
    if (!createdShare) {
      return;
    }
    try {
      const response = await share.exportMarkdown({
        share_slug: createdShare.share_slug,
        format: "markdown",
      });
      setMarkdown(response);
    } catch {
      setMarkdown(null);
    }
  }

  async function handleCopyLink() {
    if (!createdShare || typeof navigator === "undefined" || !navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(createdShare.url_path);
  }

  async function handleCopyMarkdown() {
    if (!markdown || typeof navigator === "undefined" || !navigator.clipboard) {
      return;
    }
    await navigator.clipboard.writeText(markdown.content);
  }

  function handleDownloadMarkdown() {
    if (!markdown || typeof document === "undefined") {
      return;
    }
    const blob = new Blob([markdown.content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = markdown.filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="space-y-3 rounded border border-stone-200 bg-stone-50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          className="inline-flex min-h-10 items-center gap-2 rounded bg-stone-950 px-3 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-300"
          disabled={share.isLoading}
          type="button"
          onClick={handleCreateShare}
        >
          <Share2 aria-hidden="true" className="h-4 w-4" />
          创建分享链接
        </button>
        <button
          className="inline-flex min-h-10 items-center gap-2 rounded border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-100 disabled:cursor-not-allowed disabled:text-stone-400"
          disabled={!createdShare}
          type="button"
          onClick={handleCopyLink}
        >
          <Link2 aria-hidden="true" className="h-4 w-4" />
          复制链接
        </button>
        <button
          className="inline-flex min-h-10 items-center gap-2 rounded border border-stone-300 px-3 py-2 text-sm text-stone-700 hover:bg-stone-100 disabled:cursor-not-allowed disabled:text-stone-400"
          disabled={!createdShare || share.isLoading}
          type="button"
          onClick={handleExportMarkdown}
        >
          <Download aria-hidden="true" className="h-4 w-4" />
          导出 Markdown
        </button>
      </div>

      {createdShare ? (
        <p className="break-all rounded border border-stone-200 bg-white p-2 font-mono text-sm text-stone-800">
          {createdShare.url_path}
        </p>
      ) : null}

      {share.error ? <ErrorCallout error={share.error} /> : null}

      {markdown ? (
        <div className="space-y-2">
          <p className="text-sm font-medium text-stone-800">{markdown.filename}</p>
          <textarea
            aria-label="Markdown 内容"
            className="min-h-32 w-full rounded border border-stone-300 p-2 font-mono text-xs text-stone-800"
            readOnly
            value={markdown.content}
          />
        </div>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button
          className="min-h-10 rounded border border-stone-300 px-3 py-2 text-sm text-stone-700 disabled:cursor-not-allowed disabled:text-stone-400"
          disabled={!markdown || exportFailed}
          type="button"
          onClick={handleCopyMarkdown}
        >
          复制 Markdown
        </button>
        <button
          className="min-h-10 rounded border border-stone-300 px-3 py-2 text-sm text-stone-700 disabled:cursor-not-allowed disabled:text-stone-400"
          disabled={!markdown || exportFailed}
          type="button"
          onClick={handleDownloadMarkdown}
        >
          下载 Markdown
        </button>
      </div>
    </section>
  );
}
