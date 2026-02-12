"use client";

import { getViewer } from "@/lib/viewer-registry";
import type { ItemDetail } from "@/lib/api";
import type { UploadedAsset } from "@/lib/upload-constants";
import type { WizardManifestItem } from "@/app/upload/[datasetId]/page";

type Props = {
  item: WizardManifestItem;
  uploadedAssets: UploadedAsset[];
};

export function WizardPreview({ item, uploadedAssets }: Props) {
  const assetsMap = new Map(
    uploadedAssets.map((a) => [
      a.asset_id,
      {
        id: a.asset_id,
        kind: a.kind,
        content_type: a.content_type,
        byte_size: a.byte_size,
      },
    ])
  );
  const annotations = item.annotations ?? [];
  const timeline_events =
    item.type === "video_with_timeline"
      ? (annotations.find((a) => a.schema === "timeline_v1")?.data as { events?: unknown[] })?.events?.map(
          (ev: unknown) => {
            const e = ev as Record<string, unknown>;
            return {
              t_start: Number(e.t_start ?? e.start ?? 0),
              t_end: e.t_end != null || e.end != null ? Number(e.t_end ?? e.end) : undefined,
              label: e.label as string | undefined,
              metadata: e.metadata as Record<string, unknown> | undefined,
              track: e.track as string | undefined,
            };
          }
        ) ?? []
      : undefined;
  const caption_segments =
    item.type === "audio_with_captions"
      ? (annotations.find((a) => a.schema === "captions_v1")?.data as { segments?: unknown[] })?.segments?.map(
          (seg: unknown) => {
            const s = seg as Record<string, unknown>;
            return {
              t_start: Number(s.t_start ?? s.start ?? 0),
              t_end: s.t_end != null || s.end != null ? Number(s.t_end ?? s.end) : undefined,
              text: s.text as string | undefined,
            };
          }
        ) ?? []
      : undefined;

  const synthetic: ItemDetail = {
    item: {
      id: "preview",
      type: item.type,
      title: item.title ?? null,
      summary: item.summary ?? null,
      payload: item.payload,
      created_at: new Date().toISOString(),
    },
    assets: Array.from(assetsMap.values()),
    annotations,
    timeline_events,
    caption_segments,
  };

  const viewer = getViewer(item.type);
  if (!viewer) {
    return (
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 text-zinc-500">
        No preview for type &quot;{item.type}&quot;
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4">
      <p className="text-xs text-zinc-500 mb-2">Preview (signed URLs)</p>
      <viewer.Component
        item={synthetic.item}
        assets={assetsMap}
        annotations={synthetic.annotations}
        timeline_events={synthetic.timeline_events}
        caption_segments={synthetic.caption_segments}
      />
    </div>
  );
}
