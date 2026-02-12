"use client";

import { useState } from "react";
import type { UploadedAsset } from "@/lib/upload-constants";
import type { WizardManifestItem } from "@/app/upload/[datasetId]/page";
import { SCHEMA_ITEM_TYPES } from "@/lib/schema-item-types";
import { ItemEditor } from "./ItemEditor";

const DEFAULT_PAYLOAD: Record<string, Record<string, unknown>> = {
  image_pair_compare: {
    left_asset_id: "",
    right_asset_id: "",
    prompt: "",
    metadata: {},
  },
  image_ranked_gallery: {
    asset_ids: [],
    prompt: "",
    rankings: { method: "full_rank", data: { order: [], annotator_count: 1 } },
    metadata: {},
  },
  video_with_timeline: {
    video_asset_id: "",
    metadata: {},
  },
  audio_with_captions: {
    audio_asset_id: "",
    metadata: {},
  },
};

const DEFAULT_ANNOTATIONS: Record<string, { schema: string; data: unknown }[]> = {
  video_with_timeline: [{ schema: "timeline_v1", data: { events: [] } }],
  audio_with_captions: [{ schema: "captions_v1", data: { segments: [] } }],
};

type Props = {
  datasetId: string;
  uploadedAssets: UploadedAsset[];
  items: WizardManifestItem[];
  setItems: (items: WizardManifestItem[] | ((prev: WizardManifestItem[]) => WizardManifestItem[])) => void;
  onNext: () => void;
};

export function UploadWizardStep3({
  uploadedAssets,
  items,
  setItems,
  onNext,
}: Props) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(
    items.length > 0 ? 0 : null
  );

  const addItem = (type: string) => {
    const payload = { ...(DEFAULT_PAYLOAD[type] ?? {}) };
    const annotations = DEFAULT_ANNOTATIONS[type] ?? [];
    const newItem: WizardManifestItem = {
      type,
      title: `${type.replace(/_/g, " ")} ${items.length + 1}`,
      payload,
      annotations: annotations.length ? annotations : undefined,
    };
    setItems((prev) => [...prev, newItem]);
    setSelectedIndex(items.length);
  };

  const removeItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
    setSelectedIndex(
      selectedIndex === null
        ? null
        : selectedIndex >= items.length - 1
          ? Math.max(0, items.length - 2)
          : selectedIndex
    );
  };

  const moveItem = (from: number, dir: number) => {
    const to = from + dir;
    if (to < 0 || to >= items.length) return;
    setItems((prev) => {
      const next = [...prev];
      [next[from], next[to]] = [next[to], next[from]];
      return next;
    });
    if (selectedIndex === from) setSelectedIndex(to);
    else if (selectedIndex === to) setSelectedIndex(from);
  };

  const updateItem = (index: number, item: WizardManifestItem) => {
    setItems((prev) => prev.map((it, i) => (i === index ? item : it)));
  };

  const selectedItem = selectedIndex !== null ? items[selectedIndex] : null;

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Left: item list */}
      <div className="lg:w-56 shrink-0 space-y-2">
        <p className="text-sm font-medium text-zinc-400">Items</p>
        <div className="flex flex-wrap gap-2 mb-2">
          {SCHEMA_ITEM_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              onClick={() => addItem(type)}
              className="rounded border border-zinc-600 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-800"
            >
              + {type.replace(/_/g, " ")}
            </button>
          ))}
        </div>
        <ul className="space-y-1">
          {items.map((it, i) => (
            <li key={i} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setSelectedIndex(i)}
                className={`flex-1 text-left rounded px-2 py-1.5 text-sm truncate ${
                  selectedIndex === i
                    ? "bg-emerald-500/20 text-emerald-400"
                    : "text-zinc-400 hover:bg-zinc-800"
                }`}
              >
                {it.title ?? it.type}
              </button>
              <button
                type="button"
                onClick={() => moveItem(i, -1)}
                disabled={i === 0}
                className="text-zinc-500 hover:text-zinc-300 disabled:opacity-30"
                title="Move up"
              >
                ↑
              </button>
              <button
                type="button"
                onClick={() => moveItem(i, 1)}
                disabled={i === items.length - 1}
                className="text-zinc-500 hover:text-zinc-300 disabled:opacity-30"
                title="Move down"
              >
                ↓
              </button>
              <button
                type="button"
                onClick={() => removeItem(i)}
                className="text-zinc-500 hover:text-red-400"
                title="Remove"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        {items.length === 0 && (
          <p className="text-sm text-zinc-500">Add an item to get started.</p>
        )}
      </div>

      {/* Main: editor + preview */}
      <div className="flex-1 min-w-0">
        {selectedItem ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-1">Title</label>
              <input
                type="text"
                value={selectedItem.title ?? ""}
                onChange={(e) => {
                  const idx = selectedIndex!;
                  updateItem(idx, { ...selectedItem, title: e.target.value || undefined });
                }}
                className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-400 mb-1">Summary (optional)</label>
              <input
                type="text"
                value={selectedItem.summary ?? ""}
                onChange={(e) => {
                  const idx = selectedIndex!;
                  updateItem(idx, { ...selectedItem, summary: e.target.value || undefined });
                }}
                className="w-full max-w-md rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100"
              />
            </div>
            <ItemEditor
              item={selectedItem}
              onChange={(updated) => updateItem(selectedIndex!, updated)}
              uploadedAssets={uploadedAssets}
            />
          </div>
        ) : (
          <p className="text-zinc-500">Select or add an item to edit.</p>
        )}

        <div className="mt-8 pt-6 border-t border-zinc-800">
          <button
            type="button"
            onClick={onNext}
            className="rounded-lg border border-zinc-600 px-4 py-2.5 text-zinc-300 hover:bg-zinc-800/80"
          >
            Next: Review & Publish →
          </button>
        </div>
      </div>
    </div>
  );
}
