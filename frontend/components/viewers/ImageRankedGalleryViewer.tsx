"use client";

import { useState } from "react";
import { AssetLoader } from "@/components/AssetLoader";
import type { ViewerProps } from "@/lib/viewer-registry";

export function ImageRankedGalleryViewer({ item, assets }: ViewerProps) {
  const payload = item.payload as {
    asset_ids: string[];
    prompt?: string;
    rankings?: { method: string; data?: { order?: string[]; scores?: Record<string, number>; annotator_count?: number }; scale?: string };
    metadata?: Record<string, unknown>;
  };
  const assetIds = payload.asset_ids ?? [];
  const rankings = payload.rankings;
  const [modalUrl, setModalUrl] = useState<string | null>(null);

  const order = rankings?.method === "full_rank" ? rankings.data?.order : null;
  const scores = rankings?.method === "scores" ? rankings.data?.scores : null;

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 gap-4">
        {assetIds.map((id, index) => {
          const rank = order ? order.indexOf(id) + 1 : null;
          const score = scores?.[id];
          return (
            <div
              key={id}
              className="border border-zinc-700 rounded-lg overflow-hidden bg-zinc-800/50 min-h-[120px] flex flex-col items-center justify-center cursor-pointer"
              onClick={() => {}}
            >
              <AssetLoader assetId={id}>
                {(url, loading, retry) =>
                  loading ? (
                    <span className="text-zinc-500 text-sm">Loading…</span>
                  ) : url ? (
                    <img
                      src={url}
                      alt={`Rank ${index + 1}`}
                      className="max-w-full max-h-48 object-contain w-full"
                      onClick={() => setModalUrl(url)}
                      onError={retry}
                    />
                  ) : (
                    <span className="text-zinc-500 text-sm">Failed</span>
                  )
                }
              </AssetLoader>
              <div className="flex items-center gap-2 mt-1">
                {(rank != null || score != null) && (
                  <span className="inline-flex items-center rounded bg-zinc-600 px-2 py-0.5 text-xs font-medium text-zinc-200">
                    {rank != null ? `#${rank}` : score != null ? `Score: ${score}` : ""}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="lg:w-72 shrink-0 rounded-lg border border-zinc-700 bg-zinc-800/50 p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">Ranking summary</h3>
        <p className="text-zinc-500 text-sm mb-2">Method: {rankings?.method ?? "—"}</p>
        {order && (
          <ol className="list-decimal list-inside text-sm text-zinc-300 space-y-1">
            {order.map((aid, i) => (
              <li key={aid}>Rank {i + 1}: {aid.slice(0, 8)}…</li>
            ))}
          </ol>
        )}
        {scores && (
          <ul className="text-sm text-zinc-300 space-y-1">
            {Object.entries(scores).map(([aid, s]) => (
              <li key={aid}>{aid.slice(0, 8)}…: {s}</li>
            ))}
          </ul>
        )}
        {payload.prompt && <p className="text-zinc-500 text-sm mt-2">{payload.prompt}</p>}
      </div>
      {modalUrl && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4" onClick={() => setModalUrl(null)}>
          <img src={modalUrl} alt="Full size" className="max-w-full max-h-full object-contain" onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </div>
  );
}
