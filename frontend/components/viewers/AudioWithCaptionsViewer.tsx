"use client";

import { useState, useEffect } from "react";
import { AssetLoader } from "@/components/AssetLoader";
import { MetadataPanel } from "@/components/MetadataPanel";
import { MediaControls } from "@/components/MediaControls";
import type { ViewerProps } from "@/lib/viewer-registry";

export function AudioWithCaptionsViewer({ item, caption_segments }: ViewerProps) {
  const payload = item.payload as {
    audio_asset_id: string;
    metadata?: Record<string, unknown>;
  };
  const audioId = payload.audio_asset_id;
  const segments = caption_segments ?? [];
  const [audioEl, setAudioEl] = useState<HTMLAudioElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);

  useEffect(() => {
    if (!audioEl) return;
    const onTimeUpdate = () => setCurrentTime(audioEl.currentTime);
    audioEl.addEventListener("timeupdate", onTimeUpdate);
    return () => audioEl.removeEventListener("timeupdate", onTimeUpdate);
  }, [audioEl]);

  const activeIndex = segments.findIndex(
    (s) => currentTime >= s.t_start && (s.t_end == null || currentTime <= (s.t_end ?? 0))
  );

  const seek = (t: number) => {
    if (audioEl) {
      audioEl.currentTime = t;
      audioEl.play().catch(() => {});
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4" data-media-container tabIndex={0}>
        <AssetLoader assetId={audioId}>
          {(url, loading, retry) =>
            loading ? (
              <p className="text-zinc-500">Loading audio…</p>
            ) : url ? (
              <>
                <audio ref={setAudioEl} className="w-full" src={url} onError={retry}>
                  Your browser does not support the audio tag.
                </audio>
                <MediaControls element={audioEl} />
              </>
            ) : (
              <p className="text-zinc-500">Failed to load audio</p>
            )
          }
        </AssetLoader>
      </div>
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">Captions</h3>
        {segments.length === 0 ? (
          <p className="text-sm text-zinc-500">No captions</p>
        ) : (
          <ul className="space-y-1">
            {segments.map((seg, i) => (
              <li
                key={i}
                className={`text-sm rounded px-2 py-1 cursor-pointer ${
                  i === activeIndex ? "bg-zinc-600 text-zinc-100 font-medium" : "text-zinc-300 hover:bg-zinc-700"
                }`}
                onClick={() => seek(seg.t_start)}
              >
                {seg.t_start != null && (
                  <span className="text-zinc-500 mr-2">[{seg.t_start.toFixed(1)}s{seg.t_end != null ? ` – ${seg.t_end.toFixed(1)}s` : ""}]</span>
                )}
                {seg.text ?? ""}
              </li>
            ))}
          </ul>
        )}
      </div>
      <MetadataPanel metadata={payload.metadata} />
    </div>
  );
}
