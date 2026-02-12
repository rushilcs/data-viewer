"use client";

import { useCallback, useState } from "react";
import type { UploadedAsset } from "@/lib/upload-constants";
import type { WizardManifestItem } from "@/app/upload/[datasetId]/page";
import { SCHEMA_ITEM_TYPES } from "@/lib/schema-item-types";
import { WizardPreview } from "./WizardPreview";

type Props = {
  item: WizardManifestItem;
  onChange: (item: WizardManifestItem) => void;
  uploadedAssets: UploadedAsset[];
};

function parseJsonOrNull(s: string): Record<string, unknown> | null {
  try {
    const v = JSON.parse(s || "{}");
    return typeof v === "object" && v !== null ? v : null;
  } catch {
    return null;
  }
}

export function ItemEditor({ item, onChange, uploadedAssets }: Props) {
  const [metaError, setMetaError] = useState<string | null>(null);
  const images = uploadedAssets.filter((a) => a.kind === "image");
  const videos = uploadedAssets.filter((a) => a.kind === "video");
  const audios = uploadedAssets.filter((a) => a.kind === "audio");

  const updatePayload = useCallback(
    (updates: Partial<WizardManifestItem["payload"]>) => {
      onChange({ ...item, payload: { ...item.payload, ...updates } });
    },
    [item, onChange]
  );

  const setMetadataJson = useCallback(
    (raw: string) => {
      const parsed = parseJsonOrNull(raw);
      if (parsed === null && raw.trim()) {
        setMetaError("Invalid JSON");
        return;
      }
      setMetaError(null);
      updatePayload({ metadata: parsed ?? {} });
    },
    [updatePayload]
  );

  const metadataStr =
    typeof item.payload.metadata === "object" && item.payload.metadata !== null
      ? JSON.stringify(item.payload.metadata, null, 2)
      : "{}";

  if (item.type === "image_pair_compare") {
    const pl = item.payload as {
      left_asset_id?: string;
      right_asset_id?: string;
      prompt?: string;
      metadata?: Record<string, unknown>;
    };
    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Left image *</label>
            <select
              value={pl.left_asset_id ?? ""}
              onChange={(e) => updatePayload({ left_asset_id: e.target.value })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
            >
              <option value="">Select…</option>
              {images.map((a) => (
                <option key={a.asset_id} value={a.asset_id}>
                  {a.filename}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Right image *</label>
            <select
              value={pl.right_asset_id ?? ""}
              onChange={(e) => updatePayload({ right_asset_id: e.target.value })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
            >
              <option value="">Select…</option>
              {images.map((a) => (
                <option key={a.asset_id} value={a.asset_id}>
                  {a.filename}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Prompt *</label>
            <textarea
              value={pl.prompt ?? ""}
              onChange={(e) => updatePayload({ prompt: e.target.value })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
              rows={3}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Metadata (JSON)</label>
            <textarea
              value={metadataStr}
              onChange={(e) => setMetadataJson(e.target.value)}
              className={`w-full rounded-lg border bg-zinc-800 px-3 py-2 font-mono text-sm text-zinc-100 ${
                metaError ? "border-red-500" : "border-zinc-700"
              }`}
              rows={4}
            />
            {metaError && <p className="text-red-400 text-sm mt-1">{metaError}</p>}
          </div>
        </div>
        <div>
          <WizardPreview item={item} uploadedAssets={uploadedAssets} />
        </div>
      </div>
    );
  }

  if (item.type === "image_ranked_gallery") {
    const pl = item.payload as {
      asset_ids?: string[];
      prompt?: string;
      rankings?: { method?: string; data?: { order?: string[]; scores?: Record<string, number> } };
      metadata?: Record<string, unknown>;
    };
    const method = pl.rankings?.method ?? "full_rank";
    const selectedIds = pl.asset_ids ?? [];
    const order = pl.rankings?.data?.order ?? selectedIds;
    const scores = pl.rankings?.data?.scores ?? {};

    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Images * (min 2)</label>
            <div className="flex flex-wrap gap-2">
              {images.map((a) => {
                const checked = selectedIds.includes(a.asset_id);
                return (
                  <label key={a.asset_id} className="flex items-center gap-2 rounded border border-zinc-700 px-3 py-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(e) => {
                        const next = e.target.checked
                          ? [...selectedIds, a.asset_id]
                          : selectedIds.filter((id) => id !== a.asset_id);
                        updatePayload({ asset_ids: next });
                        if (method === "full_rank") {
                          const nextOrder = e.target.checked
                            ? [...order, a.asset_id]
                            : order.filter((id) => id !== a.asset_id);
                          updatePayload({
                            rankings: {
                              method: "full_rank",
                              data: { order: nextOrder, annotator_count: 1 },
                            },
                          });
                        } else {
                          const nextScores = { ...scores };
                          if (e.target.checked) nextScores[a.asset_id] = 0;
                          else delete nextScores[a.asset_id];
                          updatePayload({
                            rankings: {
                              method: "scores",
                              data: { ...pl.rankings?.data, scores: nextScores, scale: "0-1" },
                            },
                          });
                        }
                      }}
                    />
                    <span className="text-sm text-zinc-300">{a.filename}</span>
                  </label>
                );
              })}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Prompt *</label>
            <textarea
              value={pl.prompt ?? ""}
              onChange={(e) => updatePayload({ prompt: e.target.value })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
              rows={2}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Ranking method</label>
            <select
              value={method}
              onChange={(e) => {
                const m = e.target.value as "full_rank" | "scores";
                if (m === "full_rank")
                  updatePayload({
                    rankings: { method: "full_rank", data: { order: selectedIds, annotator_count: 1 } },
                  });
                else
                  updatePayload({
                    rankings: {
                      method: "scores",
                      data: { scores: Object.fromEntries(selectedIds.map((id) => [id, 0])), scale: "0-1" },
                    },
                  });
              }}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
            >
              <option value="full_rank">Full rank (drag order)</option>
              <option value="scores">Scores</option>
            </select>
          </div>
          {method === "scores" && selectedIds.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-1">Scores</label>
              <div className="space-y-2">
                {selectedIds.map((id) => (
                  <div key={id} className="flex items-center gap-2">
                    <span className="text-sm text-zinc-500 w-32 truncate">{id.slice(0, 8)}…</span>
                    <input
                      type="number"
                      step={0.01}
                      value={scores[id] ?? 0}
                      onChange={(e) =>
                        updatePayload({
                          rankings: {
                            method: "scores",
                            data: {
                              ...pl.rankings?.data,
                              scores: { ...scores, [id]: parseFloat(e.target.value) || 0 },
                              scale: "0-1",
                            },
                          },
                        })
                      }
                      className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-zinc-100"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Metadata (JSON)</label>
            <textarea
              value={metadataStr}
              onChange={(e) => setMetadataJson(e.target.value)}
              className={`w-full rounded-lg border bg-zinc-800 px-3 py-2 font-mono text-sm ${
                metaError ? "border-red-500" : "border-zinc-700"
              }`}
              rows={3}
            />
            {metaError && <p className="text-red-400 text-sm mt-1">{metaError}</p>}
          </div>
        </div>
        <div>
          <WizardPreview item={item} uploadedAssets={uploadedAssets} />
        </div>
      </div>
    );
  }

  if (item.type === "video_with_timeline") {
    const pl = item.payload as {
      video_asset_id?: string;
      poster_image_asset_id?: string;
      metadata?: Record<string, unknown>;
    };
    const timelineData = (item.annotations ?? []).find((a) => a.schema === "timeline_v1")?.data as {
      events?: Array<{ track?: string; t_start?: number; t_end?: number; label?: string; metadata?: unknown }>;
    };
    const events = timelineData?.events ?? [];

    const setEvents = (next: typeof events) => {
      const ann = item.annotations ?? [];
      const rest = ann.filter((a) => a.schema !== "timeline_v1");
      onChange({
        ...item,
        annotations: [...rest, { schema: "timeline_v1", data: { events: next } }],
      });
    };

    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Video *</label>
            <select
              value={pl.video_asset_id ?? ""}
              onChange={(e) => updatePayload({ video_asset_id: e.target.value })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
            >
              <option value="">Select…</option>
              {videos.map((a) => (
                <option key={a.asset_id} value={a.asset_id}>
                  {a.filename}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Timeline events</label>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {events.map((ev, i) => (
                <div key={i} className="flex flex-wrap gap-2 items-center rounded border border-zinc-700 p-2">
                  <input
                    placeholder="Track"
                    value={ev.track ?? ""}
                    onChange={(e) => {
                      const next = [...events];
                      next[i] = { ...next[i], track: e.target.value };
                      setEvents(next);
                    }}
                    className="w-24 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                  />
                  <input
                    type="number"
                    step={0.1}
                    placeholder="Start"
                    value={ev.t_start ?? ""}
                    onChange={(e) => {
                      const next = [...events];
                      next[i] = { ...next[i], t_start: parseFloat(e.target.value) || 0 };
                      setEvents(next);
                    }}
                    className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                  />
                  <input
                    type="number"
                    step={0.1}
                    placeholder="End"
                    value={ev.t_end ?? ""}
                    onChange={(e) => {
                      const next = [...events];
                      const v = e.target.value;
                      next[i] = { ...next[i], t_end: v === "" ? undefined : parseFloat(v) };
                      setEvents(next);
                    }}
                    className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                  />
                  <input
                    placeholder="Label"
                    value={ev.label ?? ""}
                    onChange={(e) => {
                      const next = [...events];
                      next[i] = { ...next[i], label: e.target.value };
                      setEvents(next);
                    }}
                    className="flex-1 min-w-[80px] rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                  />
                  <button
                    type="button"
                    onClick={() => setEvents(events.filter((_, j) => j !== i))}
                    className="text-red-400 text-sm"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setEvents([...events, { t_start: 0, track: "default", label: "" }])}
              className="mt-2 text-sm text-emerald-400 hover:underline"
            >
              + Add event
            </button>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Metadata (JSON)</label>
            <textarea
              value={metadataStr}
              onChange={(e) => setMetadataJson(e.target.value)}
              className={`w-full rounded-lg border bg-zinc-800 px-3 py-2 font-mono text-sm ${
                metaError ? "border-red-500" : "border-zinc-700"
              }`}
              rows={3}
            />
            {metaError && <p className="text-red-400 text-sm mt-1">{metaError}</p>}
          </div>
        </div>
        <div>
          <WizardPreview item={item} uploadedAssets={uploadedAssets} />
        </div>
      </div>
    );
  }

  if (item.type === "audio_with_captions") {
    const pl = item.payload as { audio_asset_id?: string; metadata?: Record<string, unknown> };
    const captionsData = (item.annotations ?? []).find((a) => a.schema === "captions_v1")?.data as {
      segments?: Array<{ t_start?: number; t_end?: number; text?: string }>;
    };
    const segments = captionsData?.segments ?? [];

    const setSegments = (
      next: Array<{ t_start?: number; t_end?: number; text?: string }>
    ) => {
      const ann = item.annotations ?? [];
      const rest = ann.filter((a) => a.schema !== "captions_v1");
      onChange({
        ...item,
        annotations: [...rest, { schema: "captions_v1", data: { segments: next } }],
      });
    };

    return (
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Audio *</label>
            <select
              value={pl.audio_asset_id ?? ""}
              onChange={(e) => updatePayload({ audio_asset_id: e.target.value })}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
            >
              <option value="">Select…</option>
              {audios.map((a) => (
                <option key={a.asset_id} value={a.asset_id}>
                  {a.filename}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Caption segments</label>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {segments.map((seg, i) => (
                <div key={i} className="flex flex-wrap gap-2 items-center rounded border border-zinc-700 p-2">
                  <input
                    type="number"
                    step={0.1}
                    placeholder="Start"
                    value={seg.t_start ?? ""}
                    onChange={(e) => {
                      const next = [...segments];
                      next[i] = { ...next[i], t_start: parseFloat(e.target.value) || 0 };
                      setSegments(next);
                    }}
                    className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                  />
                  <input
                    type="number"
                    step={0.1}
                    placeholder="End"
                    value={seg.t_end ?? ""}
                    onChange={(e) => {
                      const next = [...segments];
                      const v = e.target.value;
                      next[i] = { ...next[i], t_end: v === "" ? undefined : parseFloat(v) };
                      setSegments(next);
                    }}
                    className="w-20 rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                  />
                  <input
                    placeholder="Text"
                    value={seg.text ?? ""}
                    onChange={(e) => {
                      const next = [...segments];
                      next[i] = { ...next[i], text: e.target.value };
                      setSegments(next);
                    }}
                    className="flex-1 min-w-[100px] rounded border border-zinc-700 bg-zinc-800 px-2 py-1 text-sm text-zinc-100"
                  />
                  <button
                    type="button"
                    onClick={() => setSegments(segments.filter((_, j) => j !== i))}
                    className="text-red-400 text-sm"
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setSegments([...segments, { t_start: 0, text: "" }])}
              className="mt-2 text-sm text-emerald-400 hover:underline"
            >
              + Add segment
            </button>
          </div>
          <div>
            <label className="block text-sm font-medium text-zinc-400 mb-1">Metadata (JSON)</label>
            <textarea
              value={metadataStr}
              onChange={(e) => setMetadataJson(e.target.value)}
              className={`w-full rounded-lg border bg-zinc-800 px-3 py-2 font-mono text-sm ${
                metaError ? "border-red-500" : "border-zinc-700"
              }`}
              rows={3}
            />
            {metaError && <p className="text-red-400 text-sm mt-1">{metaError}</p>}
          </div>
        </div>
        <div>
          <WizardPreview item={item} uploadedAssets={uploadedAssets} />
        </div>
      </div>
    );
  }

  return (
    <div className="text-zinc-500">
      Unknown type &quot;{item.type}&quot;. Choose one of: {SCHEMA_ITEM_TYPES.join(", ")}.
    </div>
  );
}
