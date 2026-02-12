"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type DatasetSummary } from "@/lib/api";

export default function UploadLandingPage() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listDatasets()
      .then((list) => setDatasets(list.filter((d) => d.status === "draft")))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-zinc-500">Loading…</p>;
  if (error) return <p className="text-red-400">{error}</p>;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-semibold text-zinc-100">Upload</h1>
        <Link
          href="/upload/new"
          className="shrink-0 rounded-lg bg-emerald-500/90 px-4 py-2.5 font-medium text-zinc-900 shadow-lg shadow-emerald-500/20 hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-zinc-900"
        >
          Create dataset
        </Link>
      </div>
      <p className="text-zinc-500 mb-4">Draft datasets you can continue editing and then publish.</p>
      {datasets.length === 0 ? (
        <p className="text-zinc-500">
          No draft datasets. Create one to start the upload wizard.
        </p>
      ) : (
        <div className="rounded-xl border border-zinc-800 overflow-hidden">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-zinc-800 bg-zinc-900/50">
                <th className="px-4 py-3 text-sm font-medium text-zinc-400">Name</th>
                <th className="px-4 py-3 text-sm font-medium text-zinc-400">Created</th>
                <th className="px-4 py-3 text-sm font-medium text-zinc-400">Status</th>
                <th className="px-4 py-3 text-sm font-medium text-zinc-400"></th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((ds) => (
                <tr key={ds.id} className="border-b border-zinc-800/80 hover:bg-zinc-800/30">
                  <td className="px-4 py-3 font-medium text-zinc-100">{ds.name}</td>
                  <td className="px-4 py-3 text-sm text-zinc-500">
                    {new Date(ds.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-amber-500/20 px-2.5 py-0.5 text-xs font-medium text-amber-400">
                      {ds.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/upload/${ds.id}`}
                      className="text-sm font-medium text-emerald-400 hover:text-emerald-300"
                    >
                      Continue →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
