"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type ItemDetail } from "@/lib/api";
import { getViewer } from "@/lib/viewer-registry";

export default function ItemDetailPage() {
  const params = useParams();
  const itemId = params.itemId as string;
  const [data, setData] = useState<ItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getItem(itemId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [itemId]);

  if (loading) return <p className="text-slate-500">Loading…</p>;
  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return null;

  const viewer = getViewer(data.item.type);
  const assetsMap = new Map(data.assets.map((a) => [a.id, a]));

  return (
    <div className="max-w-4xl">
      <div className="mb-4">
        <Link href="/datasets" className="text-sm text-slate-500 hover:text-slate-700">
          ← Datasets
        </Link>
      </div>
      <h1 className="text-2xl font-semibold text-slate-800 mb-2">
        {data.item.title ?? data.item.type}
      </h1>
      {data.item.summary && (
        <p className="text-slate-500 mb-4">{data.item.summary}</p>
      )}
      {viewer ? (
        <viewer.Component
          item={data.item}
          assets={assetsMap}
          annotations={data.annotations}
          timeline_events={data.timeline_events}
          caption_segments={data.caption_segments}
        />
      ) : (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
          <p className="text-amber-400">No viewer for type &quot;{data.item.type}&quot;</p>
          <pre className="mt-2 text-sm overflow-auto text-slate-600">{JSON.stringify(data.item.payload, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}
