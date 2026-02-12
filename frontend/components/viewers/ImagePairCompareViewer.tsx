"use client";

import { useState } from "react";
import { AssetLoader } from "@/components/AssetLoader";
import { MetadataPanel } from "@/components/MetadataPanel";
import type { ViewerProps } from "@/lib/viewer-registry";

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      type="button"
      onClick={copy}
      className="text-xs text-zinc-500 hover:text-zinc-300 border border-zinc-600 rounded px-2 py-1"
    >
      {copied ? "Copied" : `Copy ${label}`}
    </button>
  );
}

export function ImagePairCompareViewer({ item, assets }: ViewerProps) {
  const payload = item.payload as {
    left_asset_id: string;
    right_asset_id: string;
    prompt?: string;
    metadata?: Record<string, unknown>;
  };
  const leftId = payload.left_asset_id;
  const rightId = payload.right_asset_id;
  const [modalUrl, setModalUrl] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-zinc-700 rounded-lg overflow-hidden bg-zinc-800/50 min-h-[200px] flex items-center justify-center cursor-pointer" onClick={() => {}}>
          <AssetLoader assetId={leftId}>
            {(url, loading, retry) =>
              loading ? (
                <span className="text-zinc-500">Loading…</span>
              ) : url ? (
                <img
                  src={url}
                  alt="Left"
                  className="max-w-full max-h-[70vh] object-contain"
                  onClick={() => setModalUrl(url)}
                  onError={retry}
                />
              ) : (
                <span className="text-zinc-500">Failed to load</span>
              )
            }
          </AssetLoader>
        </div>
        <div className="border border-zinc-700 rounded-lg overflow-hidden bg-zinc-800/50 min-h-[200px] flex items-center justify-center cursor-pointer">
          <AssetLoader assetId={rightId}>
            {(url, loading, retry) =>
              loading ? (
                <span className="text-zinc-500">Loading…</span>
              ) : url ? (
                <img
                  src={url}
                  alt="Right"
                  className="max-w-full max-h-[70vh] object-contain"
                  onClick={() => setModalUrl(url)}
                  onError={retry}
                />
              ) : (
                <span className="text-zinc-500">Failed to load</span>
              )
            }
          </AssetLoader>
        </div>
      </div>
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4">
        {payload.prompt && (
          <div className="mb-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-zinc-400">Prompt</span>
              <CopyButton text={payload.prompt} label="prompt" />
            </div>
            <p className="text-zinc-200 mt-1 whitespace-pre-wrap break-words">{payload.prompt}</p>
          </div>
        )}
        {payload.metadata && Object.keys(payload.metadata).length > 0 && (
          <div>
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-zinc-400">Metadata</span>
              <CopyButton text={JSON.stringify(payload.metadata, null, 2)} label="metadata" />
            </div>
            <pre className="text-sm text-zinc-300 mt-1 overflow-auto max-h-40 bg-zinc-900/80 p-2 rounded border border-zinc-700">
              {JSON.stringify(payload.metadata, null, 2)}
            </pre>
          </div>
        )}
      </div>
      {modalUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
          onClick={() => setModalUrl(null)}
        >
          <img src={modalUrl} alt="Full size" className="max-w-full max-h-full object-contain" onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </div>
  );
}
