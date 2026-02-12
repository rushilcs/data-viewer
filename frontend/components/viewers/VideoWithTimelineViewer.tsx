"use client";

import { useState, useEffect } from "react";
import { AssetLoader } from "@/components/AssetLoader";
import { MetadataPanel } from "@/components/MetadataPanel";
import { MediaControls } from "@/components/MediaControls";
import type { ViewerProps } from "@/lib/viewer-registry";

export function VideoWithTimelineViewer({ item, annotations, timeline_events }: ViewerProps) {
  const payload = item.payload as {
    video_asset_id: string;
    poster_image_asset_id?: string;
    metadata?: Record<string, unknown>;
  };
  const videoId = payload.video_asset_id;
  const events = timeline_events ?? [];
  const [videoEl, setVideoEl] = useState<HTMLVideoElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);

  const byTrack = events.reduce<Record<string, typeof events>>((acc, ev) => {
    const t = ev.track ?? "default";
    if (!acc[t]) acc[t] = [];
    acc[t].push(ev);
    return acc;
  }, {});

  useEffect(() => {
    if (!videoEl) return;
    const onTimeUpdate = () => setCurrentTime(videoEl.currentTime);
    videoEl.addEventListener("timeupdate", onTimeUpdate);
    return () => videoEl.removeEventListener("timeupdate", onTimeUpdate);
  }, [videoEl]);

  const seek = (t: number) => {
    if (videoEl) {
      videoEl.currentTime = t;
      videoEl.play().catch(() => {});
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-zinc-700 overflow-hidden bg-zinc-900" data-media-container tabIndex={0}>
        <AssetLoader assetId={videoId}>
          {(url, loading, retry) =>
            loading ? (
              <div className="aspect-video flex items-center justify-center text-zinc-400">Loading video…</div>
            ) : url ? (
              <>
                <video
                  ref={setVideoEl}
                  className="w-full aspect-video"
                  src={url}
                  onError={retry}
                  playsInline
                >
                  Your browser does not support the video tag.
                </video>
                <div className="px-2 bg-zinc-800 border-t border-zinc-700">
                  <MediaControls element={videoEl} isVideo />
                </div>
              </>
            ) : (
              <div className="aspect-video flex items-center justify-center text-zinc-400">Failed to load video</div>
            )
          }
        </AssetLoader>
      </div>
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4">
        <h3 className="text-sm font-medium text-zinc-300 mb-2">Timeline (current: {currentTime.toFixed(1)}s)</h3>
        {Object.keys(byTrack).length === 0 ? (
          <p className="text-sm text-zinc-500">No events</p>
        ) : (
          <div className="space-y-3">
            {Object.entries(byTrack).map(([track, evs]) => (
              <div key={track}>
                <span className="text-xs font-medium text-zinc-500">{track}</span>
                <ul className="mt-1 space-y-1">
                  {evs.map((ev, i) => (
                    <li key={i}>
                      <button
                        type="button"
                        onClick={() => seek(ev.t_start)}
                        className="text-left w-full text-sm text-zinc-300 hover:bg-zinc-700 rounded px-2 py-1"
                      >
                        {ev.t_start.toFixed(1)}s{ev.t_end != null ? ` – ${ev.t_end.toFixed(1)}s` : ""} {ev.label ?? ""}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
      <MetadataPanel metadata={payload.metadata} />
    </div>
  );
}
