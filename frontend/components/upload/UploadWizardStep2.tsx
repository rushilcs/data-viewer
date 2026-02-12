"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { UploadedAsset } from "@/lib/upload-constants";
import {
  fileKind,
  isAllowedContentType,
  maxByteSizeForKind,
} from "@/lib/upload-constants";

type FileRow = {
  file: File;
  assetId: string | null;
  progress: number;
  status: "pending" | "uploading" | "done" | "error";
  error?: string;
};

const MAX_RETRIES = 2;
const BACKOFF_BASE_MS = 1000;

async function uploadWithRetry(
  uploadUrl: string,
  file: File,
  onProgress: (p: number) => void
): Promise<void> {
  let lastError: Error | null = null;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    if (attempt > 0) {
      const delay = BACKOFF_BASE_MS * Math.pow(2, attempt - 1);
      await new Promise((r) => setTimeout(r, delay));
    }
    try {
      const xhr = new XMLHttpRequest();
      await new Promise<void>((resolve, reject) => {
        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) onProgress((e.loaded / e.total) * 100);
        });
        xhr.addEventListener("load", () => {
          if (xhr.status >= 200 && xhr.status < 300) resolve();
          else reject(new Error(`Upload failed: ${xhr.status}`));
        });
        xhr.addEventListener("error", () => reject(new Error("Network error")));
        xhr.open("PUT", uploadUrl);
        const csrf = typeof window !== "undefined" ? sessionStorage.getItem("csrf_token") : null;
        if (csrf) xhr.setRequestHeader("X-CSRF-Token", csrf);
        xhr.send(file);
      });
      return;
    } catch (e) {
      lastError = e instanceof Error ? e : new Error("Upload failed");
    }
  }
  throw lastError;
}

type Props = {
  datasetId: string;
  uploadedAssets: UploadedAsset[];
  onAddAsset: (a: UploadedAsset) => void;
  onRemoveAsset: (assetId: string) => void;
  onNext: () => void;
};

export function UploadWizardStep2({
  datasetId,
  uploadedAssets,
  onAddAsset,
  onRemoveAsset,
  onNext,
}: Props) {
  const [files, setFiles] = useState<FileRow[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const validateFile = useCallback((file: File): string | null => {
    const ct = file.type || "application/octet-stream";
    if (!isAllowedContentType(ct)) {
      return `Type ${ct} is not allowed.`;
    }
    const kind = fileKind(ct);
    const max = maxByteSizeForKind(kind);
    if (file.size <= 0 || file.size > max) {
      return `Size must be 1–${Math.round(max / 1024 / 1024)} MB for ${kind}.`;
    }
    return null;
  }, []);

  const addFiles = useCallback(
    (newFiles: FileList | File[]) => {
      const list = Array.from(newFiles);
      setValidationError(null);
      const rows: FileRow[] = list.map((file) => {
        const err = validateFile(file);
        return {
          file,
          assetId: null,
          progress: 0,
          status: err ? "error" : "pending",
          error: err ?? undefined,
        };
      });
      setFiles((prev) => [...prev, ...rows]);
    },
    [validateFile]
  );

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => {
      const row = prev[index];
      if (row.assetId) onRemoveAsset(row.assetId);
      return prev.filter((_, i) => i !== index);
    });
  }, [onRemoveAsset]);

  const startUpload = useCallback(async () => {
    const pending = files.filter((f) => f.status === "pending" && !f.error);
    if (pending.length === 0) return;
    setUploading(true);
    const fileList = pending.map((f) => ({
      filename: f.file.name,
      kind: fileKind(f.file.type || "application/octet-stream"),
      content_type: f.file.type || "application/octet-stream",
      byte_size: f.file.size,
    }));
    let urls: { asset_id: string; upload_url: string; storage_key: string }[];
    try {
      urls = await api.requestUploadUrls(datasetId, fileList);
    } catch (e) {
      setValidationError(e instanceof Error ? e.message : "Failed to get upload URLs.");
      setUploading(false);
      return;
    }
    const results: UploadedAsset[] = [];
    for (let i = 0; i < pending.length; i++) {
      const row = pending[i];
      const idx = files.indexOf(row);
      setFiles((prev) =>
        prev.map((p, j) => (j === idx ? { ...p, status: "uploading" as const, progress: 0 } : p))
      );
      try {
        await uploadWithRetry(urls[i].upload_url, row.file, (p) => {
          setFiles((prev) =>
            prev.map((x, j) => (j === idx ? { ...x, progress: p } : x))
          );
        });
        setFiles((prev) =>
          prev.map((x, j) =>
            j === idx
              ? {
                  ...x,
                  assetId: urls[i].asset_id,
                  progress: 100,
                  status: "done" as const,
                  error: undefined,
                }
              : x
          )
        );
        onAddAsset({
          asset_id: urls[i].asset_id,
          filename: row.file.name,
          kind: fileKind(row.file.type || "application/octet-stream"),
          content_type: row.file.type || "application/octet-stream",
          byte_size: row.file.size,
        });
        setFiles((prev) => prev.filter((_, j) => j !== idx));
      } catch (e) {
        setFiles((prev) =>
          prev.map((x, j) =>
            j === idx
              ? {
                  ...x,
                  status: "error" as const,
                  error: e instanceof Error ? e.message : "Upload failed",
                }
              : x
          )
        );
      }
    }
    setUploading(false);
  }, [datasetId, files, onAddAsset]);

  const hasPending = files.some((f) => f.status === "pending" && !f.error);

  return (
    <div className="space-y-6">
      <div
        className={`rounded-xl border-2 border-dashed p-8 text-center transition ${
          dragOver ? "border-emerald-500/50 bg-emerald-500/5" : "border-zinc-700 bg-zinc-800/30"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
        }}
      >
        <p className="text-zinc-400">Drag and drop files here, or click to select.</p>
        <input
          type="file"
          multiple
          className="mt-2 block w-full text-sm text-zinc-500 file:mr-4 file:rounded file:border-0 file:bg-emerald-500/20 file:px-4 file:py-2 file:text-emerald-400"
          onChange={(e) => e.target.files && addFiles(e.target.files)}
        />
      </div>

      {validationError && (
        <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400 border border-red-500/20">
          {validationError}
        </p>
      )}

      {(uploadedAssets.length > 0 || files.length > 0) && (
        <div className="rounded-xl border border-zinc-800 overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/50">
                <th className="px-4 py-3 text-sm font-medium text-zinc-400">File</th>
                <th className="px-4 py-3 text-sm font-medium text-zinc-400">Kind</th>
                <th className="px-4 py-3 text-sm font-medium text-zinc-400">Size</th>
                <th className="px-4 py-3 text-sm font-medium text-zinc-400">Status</th>
                <th className="px-4 py-3 text-sm font-medium text-zinc-400"></th>
              </tr>
            </thead>
            <tbody>
              {uploadedAssets.map((a) => (
                <tr key={a.asset_id} className="border-b border-zinc-800/80">
                  <td className="px-4 py-3 text-zinc-200">{a.filename}</td>
                  <td className="px-4 py-3 text-sm text-zinc-500">{a.kind}</td>
                  <td className="px-4 py-3 text-sm text-zinc-500">
                    {(a.byte_size / 1024).toFixed(1)} KB
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-emerald-400">Uploaded</span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => onRemoveAsset(a.asset_id)}
                      className="text-sm text-zinc-500 hover:text-red-400"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
              {files.map((row, i) => (
                <tr key={i} className="border-b border-zinc-800/80">
                  <td className="px-4 py-3 text-zinc-200">{row.file.name}</td>
                  <td className="px-4 py-3 text-sm text-zinc-500">
                    {fileKind(row.file.type || "application/octet-stream")}
                  </td>
                  <td className="px-4 py-3 text-sm text-zinc-500">
                    {(row.file.size / 1024).toFixed(1)} KB
                  </td>
                  <td className="px-4 py-3">
                    {row.status === "uploading" && (
                      <span className="text-sm text-zinc-400">
                        Uploading… {Math.round(row.progress)}%
                      </span>
                    )}
                    {row.status === "done" && (
                      <span className="text-sm text-emerald-400">Done</span>
                    )}
                    {row.status === "error" && (
                      <span className="text-sm text-red-400">{row.error}</span>
                    )}
                    {row.status === "pending" && !row.error && (
                      <span className="text-sm text-zinc-500">Pending</span>
                    )}
                    {row.error && row.status === "pending" && (
                      <span className="text-sm text-red-400">{row.error}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => removeFile(i)}
                      className="text-sm text-zinc-500 hover:text-red-400"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap gap-4">
        {hasPending && (
          <button
            type="button"
            disabled={uploading}
            onClick={startUpload}
            className="rounded-lg bg-emerald-500/90 px-4 py-2.5 font-medium text-zinc-900 hover:bg-emerald-500 disabled:opacity-50"
          >
            {uploading ? "Uploading…" : "Upload selected"}
          </button>
        )}
        <button
          type="button"
          onClick={onNext}
          className="rounded-lg border border-zinc-600 px-4 py-2.5 text-zinc-300 hover:bg-zinc-800/80"
        >
          Next: Create items →
        </button>
      </div>
    </div>
  );
}
