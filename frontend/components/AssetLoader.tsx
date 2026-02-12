"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

const cache = new Map<
  string,
  { url: string; expiresAt: number }
>();

function getCachedUrl(assetId: string): string | null {
  const entry = cache.get(assetId);
  if (!entry) return null;
  if (Date.now() >= entry.expiresAt) {
    cache.delete(assetId);
    return null;
  }
  return entry.url;
}

function setCachedUrl(assetId: string, url: string, expiresAt: string) {
  const t = new Date(expiresAt).getTime();
  cache.set(assetId, { url, expiresAt: t - 5000 }); // use 5s before expiry
}

function clearCachedUrl(assetId: string) {
  cache.delete(assetId);
}

type Props = {
  assetId: string;
  children: (url: string | null, loading: boolean, retry: () => void) => React.ReactNode;
};

function fetchSignedUrl(assetId: string): Promise<string | null> {
  return api
    .getSignedUrl(assetId)
    .then((res) => {
      setCachedUrl(assetId, res.url, res.expires_at);
      return res.url;
    })
    .catch(() => null);
}

export function AssetLoader({ assetId, children }: Props) {
  const [url, setUrl] = useState<string | null>(() => getCachedUrl(assetId));
  const [loading, setLoading] = useState(!url);
  const retriedRef = useRef(false);

  const load = useCallback(() => {
    const cached = getCachedUrl(assetId);
    if (cached) {
      setUrl(cached);
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchSignedUrl(assetId).then((u) => {
      setUrl(u);
      setLoading(false);
    });
  }, [assetId]);

  useEffect(() => {
    load();
  }, [load]);

  const retry = useCallback(() => {
    if (retriedRef.current) return;
    retriedRef.current = true;
    clearCachedUrl(assetId);
    setLoading(true);
    fetchSignedUrl(assetId).then((u) => {
      setUrl(u);
      setLoading(false);
    });
  }, [assetId]);

  return <>{children(url, loading, retry)}</>;
}
