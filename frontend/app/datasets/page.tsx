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

  if (loading) return <p className="text-slate-500">Loading datasets…</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <h1 className="text-2xl font-semibold text-slate-800">Datasets</h1>
        {canCreate && (
          <Link
            href="/upload/new"
            className="shrink-0 px-4 py-2 rounded-xl bg-teal-500 text-white font-medium shadow-md hover:bg-teal-600 transition"
          >
            Create dataset
          </Link>
        )}
      </div>
      {datasets.length === 0 ? (
        <p className="text-slate-500">
          No datasets yet.
          {canCreate && " Create one in Upload to get started."}
        </p>
      ) : (
        <ul className="space-y-2">
          {datasets.map((ds) => (
            <li key={ds.id}>
              <Link
                href={`/datasets/${ds.id}`}
                className="block p-4 rounded-2xl border border-slate-200 bg-white hover:border-teal-200 hover:bg-teal-50/50 text-slate-800 shadow-sm transition"
              >
                <span className="font-medium">{ds.name}</span>
                {ds.description && (
                  <p className="text-sm text-slate-500 mt-1">{ds.description}</p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
