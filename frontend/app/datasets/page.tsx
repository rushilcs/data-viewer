"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api, type DatasetSummary } from "@/lib/api";

export default function DatasetsPage() {
  const { user } = useAuth();
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listDatasets()
      .then(setDatasets)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const canCreate = user && ["admin", "publisher"].includes(user.role);

  if (loading) return <p className="text-zinc-500">Loading datasets…</p>;
  if (error) return <p className="text-red-400">{error}</p>;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <h1 className="text-2xl font-semibold text-zinc-100">Datasets</h1>
        {canCreate && (
          <Link
            href="/upload/new"
            className="shrink-0 px-4 py-2 rounded-lg bg-emerald-500/90 text-zinc-900 font-medium hover:bg-emerald-500"
          >
            Create dataset
          </Link>
        )}
      </div>
      {datasets.length === 0 ? (
        <p className="text-zinc-500">
          No datasets yet.
          {canCreate && " Create one in Upload to get started."}
        </p>
      ) : (
        <ul className="space-y-2">
          {datasets.map((ds) => (
            <li key={ds.id}>
              <Link
                href={`/datasets/${ds.id}`}
                className="block p-4 rounded-lg border border-zinc-800 hover:bg-zinc-800/50 text-zinc-100"
              >
                <span className="font-medium">{ds.name}</span>
                {ds.description && (
                  <p className="text-sm text-zinc-500 mt-1">{ds.description}</p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
