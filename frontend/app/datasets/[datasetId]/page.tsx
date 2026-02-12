"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api, type PaginatedItems, type ItemTypeCounts } from "@/lib/api";

function fileKind(type: string): string {
  if (type.startsWith("image/")) return "image";
  if (type.startsWith("video/")) return "video";
  if (type.startsWith("audio/")) return "audio";
  return "other";
}

const DEBOUNCE_MS = 300;
const DEFAULT_LIMIT = 25;

type DraftIngestUIProps = {
  datasetId: string;
  append?: boolean;
  selectedFiles: File[];
  setSelectedFiles: (f: File[]) => void;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  uploadResults: { filename: string; asset_id: string }[];
  setUploadResults: (r: { filename: string; asset_id: string }[]) => void;
  uploadStatus: "idle" | "uploading" | "done" | "error";
  setUploadStatus: (s: "idle" | "uploading" | "done" | "error") => void;
  uploadError: string | null;
  setUploadError: (e: string | null) => void;
  manifestText: string;
  setManifestText: (t: string) => void;
  publishLoading: boolean;
  setPublishLoading: (v: boolean) => void;
  publishError: string | null;
  setPublishError: (e: string | null) => void;
  publishSuccess: boolean;
  setPublishSuccess: (v: boolean) => void;
  onPublishSuccess: () => void;
};

function DraftIngestUI({
  datasetId,
  append = false,
  selectedFiles,
  setSelectedFiles,
  fileInputRef,
  uploadResults,
  setUploadResults,
  uploadStatus,
  setUploadStatus,
  uploadError,
  setUploadError,
  manifestText,
  setManifestText,
  publishLoading,
  setPublishLoading,
  publishError,
  setPublishError,
  publishSuccess,
  setPublishSuccess,
  onPublishSuccess,
}: DraftIngestUIProps) {
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles(files);
    setUploadError(null);
    setUploadStatus("idle");
    setUploadResults([]);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setUploadError(null);
    setUploadStatus("uploading");
    try {
      const files = selectedFiles.map((f) => ({
        filename: f.name,
        kind: fileKind(f.type),
        content_type: f.type || "application/octet-stream",
        byte_size: f.size,
      }));
      const urls = await api.requestUploadUrls(datasetId, files);
      const results: { filename: string; asset_id: string }[] = [];
      for (let i = 0; i < urls.length; i++) {
        await api.uploadFileToUrl(urls[i].upload_url, selectedFiles[i]);
        results.push({ filename: selectedFiles[i].name, asset_id: urls[i].asset_id });
      }
      setUploadResults(results);
      setUploadStatus("done");
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "Upload failed");
      setUploadStatus("error");
    }
  };

  const fillManifestTemplate = () => {
    const imageIds = uploadResults.filter((r) => r.filename.match(/\.(jpg|jpeg|png|gif|webp)$/i)).map((r) => r.asset_id);
    const videoIds = uploadResults.filter((r) => r.filename.match(/\.(mp4|webm|mov)$/i)).map((r) => r.asset_id);
    const audioIds = uploadResults.filter((r) => r.filename.match(/\.(mp3|wav|ogg|m4a)$/i)).map((r) => r.asset_id);
    const items: Array<{ type: string; title?: string; summary?: string; payload: Record<string, unknown>; annotations?: unknown[] }> = [];
    if (imageIds.length >= 2) {
      items.push({
        type: "image_pair_compare",
        title: "Image pair",
        summary: "Left vs right",
        payload: {
          left_asset_id: imageIds[0],
          right_asset_id: imageIds[1],
          prompt: "Compare these images",
          metadata: {},
        },
        annotations: [],
      });
    }
    if (imageIds.length >= 2) {
      items.push({
        type: "image_ranked_gallery",
        title: "Image gallery",
        payload: {
          asset_ids: imageIds,
          prompt: "Rank these images",
          rankings: { method: "full_rank", data: { order: imageIds, annotator_count: 1 } },
        },
        annotations: [],
      });
    }
    videoIds.forEach((id, i) => {
      items.push({
        type: "video_with_timeline",
        title: `Video ${i + 1}`,
        payload: { video_asset_id: id, metadata: {} },
        annotations: [{ schema: "timeline_v1", data: { events: [] } }],
      });
    });
    audioIds.forEach((id, i) => {
      items.push({
        type: "audio_with_captions",
        title: `Audio ${i + 1}`,
        payload: { audio_asset_id: id, metadata: { language: "en-US" } },
        annotations: [{ schema: "captions_v1", data: { segments: [] } }],
      });
    });
    if (items.length === 0 && uploadResults.length > 0) {
      items.push({
        type: "image_pair_compare",
        title: "Placeholder",
        payload: {
          left_asset_id: uploadResults[0].asset_id,
          right_asset_id: uploadResults[uploadResults.length > 1 ? 1 : 0].asset_id,
          prompt: "Edit manifest as needed",
          metadata: {},
        },
        annotations: [],
      });
    }
    setManifestText(JSON.stringify({ items }, null, 2));
  };

  const handlePublish = async () => {
    setPublishError(null);
    setPublishSuccess(false);
    let parsed: { items: unknown[] };
    try {
      parsed = JSON.parse(manifestText || "{}");
    } catch {
      setPublishError("Invalid JSON in manifest");
      return;
    }
    if (!Array.isArray(parsed.items)) {
      setPublishError("Manifest must have an 'items' array");
      return;
    }
    const items = parsed.items as Parameters<typeof api.publishDataset>[1]["items"];
    setPublishLoading(true);
    try {
      if (append) {
        await api.appendDataset(datasetId, { items });
      } else {
        await api.publishDataset(datasetId, { items });
      }
      setPublishSuccess(true);
      onPublishSuccess();
    } catch (e) {
      setPublishError(e instanceof Error ? e.message : append ? "Append failed" : "Publish failed");
    } finally {
      setPublishLoading(false);
    }
  };

  return (
    <div className="mt-6 p-6 rounded-lg border border-slate-200 bg-slate-50 space-y-6">
      <h2 className="text-lg font-medium text-slate-800">{append ? "Add more data" : "Ingest &amp; publish"}</h2>

      <div>
        <p className="text-sm text-slate-600 mb-2">1. Upload files</p>
        <input
          ref={fileInputRef as React.RefObject<HTMLInputElement>}
          type="file"
          multiple
          onChange={handleFileChange}
          className="block w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-slate-200 file:text-slate-800"
        />
        {selectedFiles.length > 0 && (
          <p className="mt-2 text-sm text-slate-600">
            {selectedFiles.length} file(s) selected.{" "}
            {uploadStatus === "idle" && <button type="button" onClick={handleUpload} className="text-slate-800 underline font-medium">Upload</button>}
            {uploadStatus === "uploading" && "Uploading…"}
          </p>
        )}
        {uploadError && <p className="mt-2 text-sm text-red-600">{uploadError}</p>}
        {uploadStatus === "done" && uploadResults.length > 0 && (
          <div className="mt-2 text-sm">
            <p className="font-medium text-slate-700 mb-1">Uploaded (filename → asset_id):</p>
            <pre className="bg-white p-2 rounded border border-slate-200 overflow-x-auto text-xs">
              {uploadResults.map((r) => `${r.filename} → ${r.asset_id}`).join("\n")}
            </pre>
          </div>
        )}
      </div>

      <div>
        <p className="text-sm text-slate-600 mb-2">2. Manifest (JSON with <code className="bg-white px-1 rounded">items</code> array)</p>
        <div className="flex gap-2 mb-2">
          <button
            type="button"
            onClick={fillManifestTemplate}
            disabled={uploadResults.length === 0}
            className="px-3 py-1.5 rounded border border-slate-300 text-slate-700 hover:bg-slate-100 disabled:opacity-50 text-sm"
          >
            Fill template from uploads
          </button>
        </div>
        <textarea
          value={manifestText}
          onChange={(e) => setManifestText(e.target.value)}
          placeholder='{"items": [...]}'
          className="w-full h-48 font-mono text-sm border border-slate-300 rounded px-3 py-2 text-slate-900 bg-white"
          spellCheck={false}
        />
      </div>

      <div>
        <p className="text-sm text-slate-600 mb-2">3. {append ? "Append" : "Publish"}</p>
        <button
          type="button"
          onClick={handlePublish}
          disabled={publishLoading || !manifestText.trim()}
          className="px-4 py-2 rounded bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {publishLoading ? (append ? "Appending…" : "Publishing…") : append ? "Append items" : "Publish dataset"}
        </button>
        {publishError && <p className="mt-2 text-sm text-red-600">{publishError}</p>}
        {publishSuccess && <p className="mt-2 text-sm text-green-600">{append ? "Appended. Refreshing…" : "Published. Refreshing…"}</p>}
      </div>
    </div>
  );
}

export default function DatasetDetailPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const datasetId = params.datasetId as string;
  const { user } = useAuth();
  const [dataset, setDataset] = useState<{ name: string; description: string | null; status: string; tags: string[] | null } | null>(null);
  const [typeCounts, setTypeCounts] = useState<ItemTypeCounts | null>(null);
  const [page, setPage] = useState<PaginatedItems | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const typeParam = searchParams.get("type") ?? "";
  const qParam = searchParams.get("q") ?? "";
  const createdAfter = searchParams.get("created_after") ?? "";
  const createdBefore = searchParams.get("created_before") ?? "";
  const cursorParam = searchParams.get("cursor") ?? "";

  const [searchInput, setSearchInput] = useState(qParam);
  const [searchDebounce, setSearchDebounce] = useState(qParam);

  // Ingest UI (draft only)
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadResults, setUploadResults] = useState<{ filename: string; asset_id: string }[]>([]);
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [manifestText, setManifestText] = useState("");
  const [publishLoading, setPublishLoading] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishSuccess, setPublishSuccess] = useState(false);

  // Sharing (admin/publisher)
  const [shares, setShares] = useState<{ user_id: string | null; email: string; access_role: string; created_at: string; pending?: boolean }[]>([]);
  const [shareEmail, setShareEmail] = useState("");
  const [shareLoading, setShareLoading] = useState(false);
  const [shareError, setShareError] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => setSearchDebounce(searchInput), DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    const next = new URLSearchParams(searchParams.toString());
    if (searchDebounce.trim()) next.set("q", searchDebounce.trim());
    else next.delete("q");
    const nextStr = next.toString();
    const currentStr = searchParams.toString();
    if (nextStr !== currentStr) {
      const url = nextStr ? `${window.location.pathname}?${nextStr}` : window.location.pathname;
      window.history.replaceState(null, "", url);
    }
  }, [searchDebounce, searchParams]);

  const fetchItems = useCallback(
    async (cursor?: string, append = false) => {
      const limit = DEFAULT_LIMIT;
      const params: Parameters<typeof api.listDatasetItems>[1] = {
        limit,
        ...(typeParam && { type: typeParam }),
        ...(searchDebounce.trim() && { q: searchDebounce.trim() }),
        ...(createdAfter && { created_after: createdAfter }),
        ...(createdBefore && { created_before: createdBefore }),
        ...(cursor && { cursor }),
      };
      if (append) setLoadingMore(true);
      try {
        const result = await api.listDatasetItems(datasetId, params);
        if (append) {
          setPage((prev) =>
            prev ? { ...result, items: [...prev.items, ...result.items] } : result
          );
        } else {
          setPage(result);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load items");
      } finally {
        if (append) setLoadingMore(false);
      }
    },
    [datasetId, typeParam, searchDebounce, createdAfter, createdBefore]
  );

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.getDataset(datasetId),
      api.getItemTypeCounts(datasetId).catch(() => ({ counts: {} as Record<string, number>, total: 0 })),
    ])
      .then(([ds, counts]) => {
        setDataset(ds);
        setTypeCounts(counts);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed"))
      .finally(() => setLoading(false));
  }, [datasetId]);

  useEffect(() => {
    if (!dataset || dataset.status !== "published") return;
    fetchItems();
  }, [datasetId, typeParam, searchDebounce, createdAfter, createdBefore]);

  const canShare = user && ["admin", "publisher"].includes(user.role);
  useEffect(() => {
    if (!canShare || !datasetId) return;
    api.listDatasetShares(datasetId).then(setShares).catch(() => setShares([]));
  }, [canShare, datasetId]);

  const updateUrl = useCallback(
    (updates: Record<string, string>) => {
      const next = new URLSearchParams(searchParams.toString());
      Object.entries(updates).forEach(([k, v]) => {
        if (v) next.set(k, v);
        else next.delete(k);
      });
      next.delete("cursor");
      window.history.replaceState(null, "", `${window.location.pathname}?${next.toString()}`);
    },
    [searchParams]
  );

  if (loading && !page) return <p className="text-slate-600">Loading…</p>;
  if (error && !dataset) return <p className="text-red-600">{error}</p>;
  if (!dataset) return null;

  const canPublish = dataset.status === "draft" && user && ["admin", "publisher"].includes(user.role);
  const canAppend = dataset.status === "published" && user && ["admin", "publisher"].includes(user.role);

  const handleAddShare = async () => {
    if (!shareEmail.trim()) return;
    setShareError(null);
    setShareLoading(true);
    try {
      await api.addDatasetShare(datasetId, shareEmail.trim(), "viewer");
      setShareEmail("");
      const list = await api.listDatasetShares(datasetId);
      setShares(list);
    } catch (e) {
      setShareError(e instanceof Error ? e.message : "Failed to add share");
    } finally {
      setShareLoading(false);
    }
  };

  const handleRemoveShare = async (userId: string) => {
    try {
      await api.removeDatasetShare(datasetId, userId);
      setShares((prev) => prev.filter((s) => s.user_id !== userId));
    } catch {
      setShares((prev) => prev.filter((s) => s.user_id !== userId));
    }
  };

  const handleRemovePending = async (email: string) => {
    try {
      await api.removeDatasetSharePending(datasetId, email);
      setShares((prev) => prev.filter((s) => !(s.pending && s.email === email)));
    } catch {
      setShares((prev) => prev.filter((s) => !(s.pending && s.email === email)));
    }
  };

  return (
    <div>
      <div className="mb-4">
        <Link href="/datasets" className="text-sm text-slate-600 hover:text-slate-800">
          ← Datasets
        </Link>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">{dataset.name}</h1>
          {dataset.description && <p className="text-slate-600 mt-1">{dataset.description}</p>}
        </div>
      </div>

      {canShare && (
        <div className="mt-6 p-4 rounded-lg border border-slate-200 bg-slate-50 space-y-4">
          <h2 className="text-lg font-medium text-slate-800">Sharing</h2>
          <div>
            <p className="text-sm text-slate-600 mb-2">Users with access</p>
            {shares.length === 0 ? (
              <p className="text-sm text-slate-500">No one else has been granted access yet.</p>
            ) : (
              <ul className="space-y-2">
                {shares.map((s) => (
                  <li key={s.pending ? `pending-${s.email}` : s.user_id!} className="flex items-center justify-between gap-2 text-sm">
                    <span className="text-slate-800">{s.email}</span>
                    <span className="text-slate-500">
                      ({s.access_role})
                      {s.pending && <span className="ml-1 text-amber-600">(pending sign up)</span>}
                    </span>
                    <button
                      type="button"
                      onClick={() => s.pending ? handleRemovePending(s.email) : handleRemoveShare(s.user_id!)}
                      className="text-red-600 hover:underline"
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="flex flex-wrap gap-2 items-end">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Share with (email)</label>
              <input
                type="email"
                value={shareEmail}
                onChange={(e) => setShareEmail(e.target.value)}
                placeholder="user@example.com"
                className="border border-slate-300 rounded px-3 py-2 text-slate-900"
              />
            </div>
            <button
              type="button"
              onClick={handleAddShare}
              disabled={shareLoading || !shareEmail.trim()}
              className="px-4 py-2 rounded bg-slate-700 text-white text-sm hover:bg-slate-600 disabled:opacity-50"
            >
              {shareLoading ? "Adding…" : "Share"}
            </button>
          </div>
          {shareError && <p className="text-sm text-red-600">{shareError}</p>}
          <p className="text-xs text-slate-500">If they don’t have an account yet, they’ll see this dataset once they sign up with that email.</p>
        </div>
      )}

      {dataset.status === "draft" && canPublish && (
        <DraftIngestUI
          datasetId={datasetId}
          selectedFiles={selectedFiles}
          setSelectedFiles={setSelectedFiles}
          fileInputRef={fileInputRef}
          uploadResults={uploadResults}
          setUploadResults={setUploadResults}
          uploadStatus={uploadStatus}
          setUploadStatus={setUploadStatus}
          uploadError={uploadError}
          setUploadError={setUploadError}
          manifestText={manifestText}
          setManifestText={setManifestText}
          publishLoading={publishLoading}
          setPublishLoading={setPublishLoading}
          publishError={publishError}
          setPublishError={setPublishError}
          publishSuccess={publishSuccess}
          setPublishSuccess={setPublishSuccess}
          onPublishSuccess={() => {
            api.getDataset(datasetId).then(setDataset);
            setError(null);
          }}
        />
      )}

      {dataset.status === "published" && (
        <>
          <div className="mt-6 flex flex-wrap gap-4 items-end border-b border-slate-200 pb-4">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-slate-700 mb-1">Search</label>
              <input
                type="search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search title, summary, payload…"
                className="w-full border border-slate-300 rounded px-3 py-2 text-slate-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Type</label>
              <select
                value={typeParam}
                onChange={(e) => updateUrl({ type: e.target.value })}
                className="border border-slate-300 rounded px-3 py-2 text-slate-900 bg-white"
              >
                <option value="">All types</option>
                {typeCounts &&
                  Object.entries(typeCounts.counts).map(([t, count]) => (
                    <option key={t} value={t}>
                      {t} ({count})
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Created after</label>
              <input
                type="datetime-local"
                value={createdAfter}
                onChange={(e) => updateUrl({ created_after: e.target.value })}
                className="border border-slate-300 rounded px-3 py-2 text-slate-900"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Created before</label>
              <input
                type="datetime-local"
                value={createdBefore}
                onChange={(e) => updateUrl({ created_before: e.target.value })}
                className="border border-slate-300 rounded px-3 py-2 text-slate-900"
              />
            </div>
          </div>

          <h2 className="text-lg font-medium text-slate-800 mt-6 mb-2">
            Items {typeCounts != null ? `(${typeCounts.total})` : ""}
          </h2>
          {error && page && <p className="text-amber-600 text-sm">{error}</p>}
          {page?.items.length === 0 ? (
            <p className="text-slate-600">No items match the filters.</p>
          ) : (
            <ul className="space-y-2">
              {page?.items.map((item) => (
                <li key={item.id}>
                  <Link
                    href={`/items/${item.id}`}
                    className="block p-4 rounded-lg border border-slate-200 hover:bg-slate-50"
                  >
                    <span className="font-medium text-slate-800">{item.title ?? item.type}</span>
                    <span className="ml-2 text-sm text-slate-500">({item.type})</span>
                    {item.summary && <p className="text-sm text-slate-600 mt-1">{item.summary}</p>}
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {page?.has_more && page.next_cursor && (
            <button
              type="button"
              disabled={loadingMore}
              onClick={() => fetchItems(page.next_cursor ?? undefined, true)}
              className="mt-4 px-4 py-2 rounded border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {loadingMore ? "Loading…" : "Load more"}
            </button>
          )}
          {canAppend && (
            <DraftIngestUI
              datasetId={datasetId}
              append
              selectedFiles={selectedFiles}
              setSelectedFiles={setSelectedFiles}
              fileInputRef={fileInputRef}
              uploadResults={uploadResults}
              setUploadResults={setUploadResults}
              uploadStatus={uploadStatus}
              setUploadStatus={setUploadStatus}
              uploadError={uploadError}
              setUploadError={setUploadError}
              manifestText={manifestText}
              setManifestText={setManifestText}
              publishLoading={publishLoading}
              setPublishLoading={setPublishLoading}
              publishError={publishError}
              setPublishError={setPublishError}
              publishSuccess={publishSuccess}
              setPublishSuccess={setPublishSuccess}
              onPublishSuccess={() => {
                api.getDataset(datasetId).then(setDataset);
                setError(null);
                api.getItemTypeCounts(datasetId).then(setTypeCounts).catch(() => {});
                fetchItems();
              }}
            />
          )}
        </>
      )}
      {dataset.status === "draft" && !canPublish && <p className="text-slate-600 mt-4">Draft dataset — no items listed.</p>}
    </div>
  );
}
