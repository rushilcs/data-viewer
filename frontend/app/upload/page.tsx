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

  if (loading) return <p className="text-slate-500">Loading…</p>;
  if (error) return <p className="text-red-600">{error}</p>;

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h1 className="text-2xl font-semibold text-slate-800">Upload</h1>
        <Link
          href="/upload/new"
          className="shrink-0 rounded-xl bg-teal-500 px-4 py-2.5 font-medium text-white shadow-md hover:bg-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-400 focus:ring-offset-2 transition"
        >
          Create dataset
        </Link>
      </div>
      <p className="text-slate-500 mb-4">Draft datasets you can continue editing and then publish.</p>
      {datasets.length === 0 ? (
        <p className="text-slate-500">
          No draft datasets. Create one to start the upload wizard.
        </p>
      ) : (
        <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-3 text-sm font-medium text-slate-600">Name</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-600">Created</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-600">Status</th>
                <th className="px-4 py-3 text-sm font-medium text-slate-600"></th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((ds) => (
                <tr key={ds.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-800">{ds.name}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">
                    {new Date(ds.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
                      {ds.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/upload/${ds.id}`}
                      className="text-sm font-medium text-teal-600 hover:text-teal-500 rounded-lg px-2 py-1 hover:bg-teal-50"
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
