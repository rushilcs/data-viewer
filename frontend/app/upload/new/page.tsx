"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

export default function UploadNewPage() {
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
      setError("Name is required.");
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
      router.push(`/upload/${out.dataset_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create dataset.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="mb-4">
        <Link href="/upload" className="text-sm text-zinc-500 hover:text-zinc-400">
          ← Upload
        </Link>
      </div>
      <h1 className="text-2xl font-semibold text-zinc-100 mb-4">Create dataset</h1>
      <p className="text-zinc-500 mb-6">Step 1: Set name, description, and tags. Then you’ll upload assets and build items.</p>
      <form onSubmit={handleSubmit} className="max-w-md space-y-4">
        {error && (
          <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400 border border-red-500/20">
            {error}
          </p>
        )}
        <div>
          <label htmlFor="name" className="block text-sm font-medium text-zinc-400 mb-1">
            Name *
          </label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800/80 px-3 py-2.5 text-zinc-100 placeholder-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
            placeholder="My dataset"
            required
          />
        </div>
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-zinc-400 mb-1">
            Description
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800/80 px-3 py-2.5 text-zinc-100 placeholder-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
            placeholder="Optional description"
            rows={2}
          />
        </div>
        <div>
          <label htmlFor="tags" className="block text-sm font-medium text-zinc-400 mb-1">
            Tags (comma or space separated)
          </label>
          <input
            id="tags"
            type="text"
            value={tagsStr}
            onChange={(e) => setTagsStr(e.target.value)}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800/80 px-3 py-2.5 text-zinc-100 placeholder-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
            placeholder="demo, test"
          />
        </div>
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-emerald-500/90 px-4 py-2.5 font-medium text-zinc-900 hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-50"
          >
            {loading ? "Creating…" : "Create draft"}
          </button>
          <Link
            href="/upload"
            className="rounded-lg border border-zinc-600 px-4 py-2.5 text-zinc-300 hover:bg-zinc-800/80"
          >
            Cancel
          </Link>
        </div>
      </form>
    </div>
  );
}
