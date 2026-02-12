"use client";

import { useCallback, useState } from "react";
import { AssetLoader } from "@/components/AssetLoader";
import { ImageLightbox } from "@/components/lightbox";
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
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxInitialIndex, setLightboxInitialIndex] = useState(0);
  const [lightboxImages, setLightboxImages] = useState<{ src: string; label?: string }[]>([]);

  const order = rankings?.method === "full_rank" ? rankings.data?.order : null;
  const scores = rankings?.method === "scores" ? rankings.data?.scores : null;

  const buildLightboxImages = useCallback(
    (clickedIndex: number, clickedUrl: string) =>
      assetIds.map((id, idx) => ({
        src: urls[id] || (idx === clickedIndex ? clickedUrl : ""),
        label: `#${(order?.indexOf(id) ?? idx) + 1}`,
      })),
    [assetIds, order, urls]
  );

  const openLightbox = useCallback(
    (index: number, clickedUrl: string) => {
      setLightboxImages(buildLightboxImages(index, clickedUrl));
      setLightboxInitialIndex(index);
      setLightboxOpen(true);
    },
    [buildLightboxImages]
  );

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      <div className="flex-1 grid grid-cols-2 sm:grid-cols-3 gap-4">
        {assetIds.map((id, index) => {
          const rank = order ? order.indexOf(id) + 1 : null;
          const score = scores?.[id];
          return (
            <div
              key={id}
              className="border border-slate-200 rounded-2xl overflow-hidden bg-white min-h-[120px] flex flex-col items-center justify-center cursor-pointer"
            >
              <AssetLoader assetId={id}>
                {(url, loading, retry) => {
                  if (url) setUrls((prev) => (prev[id] === url ? prev : { ...prev, [id]: url }));
                  return loading ? (
                    <span className="text-slate-500 text-sm">Loading…</span>
                  ) : url ? (
                    <img
                      src={url}
                      alt={`Rank ${index + 1}`}
                      className="max-w-full max-h-48 object-contain w-full"
                      onClick={() => openLightbox(index, url)}
                      onError={retry}
                    />
                  ) : (
                    <span className="text-slate-500 text-sm">Failed</span>
                  );
                }}
              </AssetLoader>
              <div className="flex items-center gap-2 mt-1">
                {(rank != null || score != null) && (
                  <span className="inline-flex items-center rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-700">
                    {rank != null ? `#${rank}` : score != null ? `Score: ${score}` : ""}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="lg:w-72 shrink-0 rounded-2xl border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-medium text-slate-600 mb-2">Ranking summary</h3>
        <p className="text-slate-500 text-sm mb-2">Method: {rankings?.method ?? "—"}</p>
        {order && (
          <ol className="list-decimal list-inside text-sm text-slate-600 space-y-1">
            {order.map((aid, i) => (
              <li key={aid}>Rank {i + 1}: {aid.slice(0, 8)}…</li>
            ))}
          </ol>
        )}
        {scores && (
          <ul className="text-sm text-slate-600 space-y-1">
            {Object.entries(scores).map(([aid, s]) => (
              <li key={aid}>{aid.slice(0, 8)}…: {s}</li>
            ))}
          </ul>
        )}
        {payload.prompt && <p className="text-slate-900 text-sm mt-2">{payload.prompt}</p>}
      </div>
      <ImageLightbox
        open={lightboxOpen}
        onClose={() => setLightboxOpen(false)}
        images={lightboxImages}
        initialIndex={lightboxInitialIndex}
        alt="Gallery image"
      />
    </div>
  );
}
