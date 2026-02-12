"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

export default function NewDatasetPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [tagsStr, setTagsStr] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setLoading(true);
    try {
      const tags = tagsStr.trim() ? tagsStr.split(/[\s,]+/).filter(Boolean) : undefined;
      const out = await api.createDatasetIngest({
        name: name.trim(),
        description: description.trim() || undefined,
        tags: tags?.length ? tags : undefined,
      });
      router.push(`/datasets/${out.dataset_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create dataset");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <Link href="/datasets" className="text-sm text-slate-600 hover:text-slate-800">
          ← Datasets
        </Link>
      </div>
      <h1 className="text-2xl font-semibold text-slate-800 mb-4">Create dataset</h1>
      <form onSubmit={handleSubmit} className="max-w-md space-y-4">
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-slate-700 mb-1">
            Name *
          </label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2 text-slate-900"
            placeholder="My dataset"
            required
          />
        </div>
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-slate-700 mb-1">
            Description
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2 text-slate-900"
            placeholder="Optional description"
            rows={2}
          />
        </div>
        <div>
          <label htmlFor="tags" className="block text-sm font-medium text-slate-700 mb-1">
            Tags (comma or space separated)
          </label>
          <input
            id="tags"
            type="text"
            value={tagsStr}
            onChange={(e) => setTagsStr(e.target.value)}
            className="w-full border border-slate-300 rounded px-3 py-2 text-slate-900"
            placeholder="demo, test"
          />
        </div>
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 rounded bg-slate-800 text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {loading ? "Creating…" : "Create draft"}
          </button>
          <Link
            href="/datasets"
            className="px-4 py-2 rounded border border-slate-300 text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
