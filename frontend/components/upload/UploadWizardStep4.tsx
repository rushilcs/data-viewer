"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { WizardManifestItem } from "@/app/upload/[datasetId]/page";

type Props = {
  datasetId: string;
  datasetName: string;
  items: WizardManifestItem[];
  onSuccess: () => void;
};

export function UploadWizardStep4({
  datasetId,
  datasetName,
  items,
  onSuccess,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  const typeCounts = items.reduce<Record<string, number>>((acc, it) => {
    acc[it.type] = (acc[it.type] ?? 0) + 1;
    return acc;
  }, {});

  const handlePublish = async () => {
    setError(null);
    setValidationErrors([]);
    const errs: string[] = [];
    if (items.length === 0) errs.push("Add at least one item.");
    items.forEach((it, i) => {
      if (!it.type) errs.push(`Item ${i + 1}: type is required.`);
      if (!it.payload || typeof it.payload !== "object")
        errs.push(`Item ${i + 1}: invalid payload.`);
    });
    if (errs.length > 0) {
      setValidationErrors(errs);
      return;
    }
    setLoading(true);
    try {
      const manifest = {
        items: items.map((it) => ({
          type: it.type,
          title: it.title ?? undefined,
          summary: it.summary ?? undefined,
          payload: it.payload,
          annotations: it.annotations ?? [],
        })),
      };
      await api.publishDataset(datasetId, manifest);
      onSuccess();
    } catch (e: unknown) {
      const msg =
        e && typeof e === "object" && "message" in e
          ? String((e as { message: unknown }).message)
          : "Publish failed.";
      setError(msg);
      if (e && typeof e === "object" && "status" in e && (e as { status: number }).status === 422) {
        try {
          const detail = (e as unknown as { message: string }).message;
          const parsed = typeof detail === "string" ? JSON.parse(detail) : detail;
          if (parsed?.errors && Array.isArray(parsed.errors)) {
            setValidationErrors(
              parsed.errors.map(
                (x: { path?: string; message?: string }) =>
                  `${x.path ?? "?"}: ${x.message ?? "validation error"}`
              )
            );
          } else {
            setValidationErrors([msg]);
          }
        } catch {
          setValidationErrors([msg]);
        }
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-6">
        <h2 className="text-lg font-medium text-zinc-200 mb-4">Summary</h2>
        <p className="text-zinc-400">
          <strong className="text-zinc-300">{datasetName}</strong> — {items.length} item
          {items.length !== 1 ? "s" : ""}.
        </p>
        {Object.keys(typeCounts).length > 0 && (
          <ul className="mt-2 text-sm text-zinc-500 list-disc list-inside">
            {Object.entries(typeCounts).map(([type, count]) => (
              <li key={type}>
                {type}: {count}
              </li>
            ))}
          </ul>
        )}
      </div>

      {validationErrors.length > 0 && (
        <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 px-4 py-3">
          <p className="text-sm font-medium text-amber-400 mb-1">Validation:</p>
          <ul className="text-sm text-amber-300 list-disc list-inside">
            {validationErrors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400 border border-red-500/20">
          {error}
        </p>
      )}

      <div className="flex gap-4">
        <button
          type="button"
          disabled={loading || items.length === 0}
          onClick={handlePublish}
          className="rounded-lg bg-emerald-500/90 px-6 py-2.5 font-medium text-zinc-900 hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-50"
        >
          {loading ? "Publishing…" : "Publish dataset"}
        </button>
      </div>
    </div>
  );
}
