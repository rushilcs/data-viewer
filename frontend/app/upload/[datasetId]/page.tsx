"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import {
  fileKind,
  isAllowedContentType,
  maxByteSizeForKind,
  type UploadedAsset,
} from "@/lib/upload-constants";
import { SCHEMA_ITEM_TYPES } from "@/lib/schema-item-types";
import { UploadWizardStep2 } from "@/components/upload/UploadWizardStep2";
import { UploadWizardStep3 } from "@/components/upload/UploadWizardStep3";
import { UploadWizardStep4 } from "@/components/upload/UploadWizardStep4";

export type WizardManifestItem = {
  type: string;
  title?: string;
  summary?: string;
  payload: Record<string, unknown>;
  annotations?: { schema: string; data: unknown }[];
};

type Step = 2 | 3 | 4;

const STEPS: { n: Step; label: string }[] = [
  { n: 2, label: "Upload assets" },
  { n: 3, label: "Create items" },
  { n: 4, label: "Review & Publish" },
];

export default function UploadWizardPage() {
  const params = useParams();
  const router = useRouter();
  const datasetId = params.datasetId as string;

  const [dataset, setDataset] = useState<{ name: string; status: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<Step>(2);
  const [uploadedAssets, setUploadedAssets] = useState<UploadedAsset[]>([]);
  const [items, setItems] = useState<WizardManifestItem[]>([]);
  const [publishSuccess, setPublishSuccess] = useState(false);

  useEffect(() => {
    api
      .getDataset(datasetId)
      .then((d) => setDataset(d))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load dataset"))
      .finally(() => setLoading(false));
  }, [datasetId]);

  useEffect(() => {
    if (dataset && dataset.status !== "draft") {
      setError("Dataset is not a draft.");
    }
  }, [dataset]);

  const addAsset = useCallback((a: UploadedAsset) => {
    setUploadedAssets((prev) => [...prev, a]);
  }, []);

  const removeAsset = useCallback((assetId: string) => {
    setUploadedAssets((prev) => prev.filter((a) => a.asset_id !== assetId));
    setItems((prev) =>
      prev.map((it) => {
        const pl = it.payload as Record<string, unknown>;
        const nextPayload = { ...pl };
        let changed = false;
        if (pl.left_asset_id === assetId || pl.right_asset_id === assetId) {
          nextPayload.left_asset_id = pl.left_asset_id === assetId ? "" : pl.left_asset_id;
          nextPayload.right_asset_id = pl.right_asset_id === assetId ? "" : pl.right_asset_id;
          changed = true;
        }
        if (Array.isArray(pl.asset_ids)) {
          nextPayload.asset_ids = (pl.asset_ids as string[]).filter((id) => id !== assetId);
          const rankings = pl.rankings as { method?: string; data?: { order?: string[]; scores?: Record<string, number>; annotator_count?: number } } | undefined;
          if (rankings?.data) {
            const data = { ...rankings.data };
            if (Array.isArray(data.order))
              data.order = data.order.filter((id: string) => id !== assetId);
            if (data.scores && typeof data.scores === "object") {
              const s = { ...data.scores };
              delete s[assetId];
              data.scores = s;
            }
            nextPayload.rankings = { ...rankings, data };
          }
          changed = true;
        }
        if (pl.video_asset_id === assetId || pl.audio_asset_id === assetId || pl.poster_image_asset_id === assetId) {
          if (pl.video_asset_id === assetId) nextPayload.video_asset_id = "";
          if (pl.audio_asset_id === assetId) nextPayload.audio_asset_id = "";
          if (pl.poster_image_asset_id === assetId) nextPayload.poster_image_asset_id = "";
          changed = true;
        }
        return changed ? { ...it, payload: nextPayload } : it;
      })
    );
  }, []);

  if (loading || !dataset) return <p className="text-zinc-500">Loading…</p>;
  if (error && dataset?.status !== "draft") return <p className="text-red-400">{error}</p>;
  if (dataset.status !== "draft") {
    return (
      <div>
        <p className="text-zinc-500">This dataset is already published.</p>
        <Link href="/upload" className="mt-2 inline-block text-emerald-400 hover:underline">
          ← Back to Upload
        </Link>
      </div>
    );
  }

  if (publishSuccess) {
    router.push(`/datasets/${datasetId}`);
    return (
      <p className="text-zinc-400">
        Published. Redirecting to dataset…
      </p>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <Link href="/upload" className="text-sm text-zinc-500 hover:text-zinc-400">
          ← Upload
        </Link>
      </div>
      <h1 className="text-2xl font-semibold text-zinc-100 mb-2">{dataset.name}</h1>
      <p className="text-zinc-500 mb-6">Draft — complete the steps below to publish.</p>

      {/* Step indicator */}
      <nav className="flex gap-4 mb-8 border-b border-zinc-800 pb-4">
        {STEPS.map(({ n, label }) => (
          <button
            key={n}
            type="button"
            onClick={() => setStep(n)}
            className={`font-medium transition ${
              step === n ? "text-emerald-400" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {n}. {label}
          </button>
        ))}
      </nav>

      {step === 2 && (
        <UploadWizardStep2
          datasetId={datasetId}
          uploadedAssets={uploadedAssets}
          onAddAsset={addAsset}
          onRemoveAsset={removeAsset}
          onNext={() => setStep(3)}
        />
      )}
      {step === 3 && (
        <UploadWizardStep3
          datasetId={datasetId}
          uploadedAssets={uploadedAssets}
          items={items}
          setItems={setItems}
          onNext={() => setStep(4)}
        />
      )}
      {step === 4 && (
        <UploadWizardStep4
          datasetId={datasetId}
          datasetName={dataset.name}
          items={items}
          onSuccess={() => setPublishSuccess(true)}
        />
      )}
    </div>
  );
}
