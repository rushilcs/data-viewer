"use client";

import { useEffect } from "react";
import { useRouter, notFound } from "next/navigation";
import AppShell from "@/components/AppShell";
import { useAuth } from "@/lib/auth";

export default function UploadLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
  }, [user, loading, router]);

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-500">Loading…</p>
      </div>
    );
  }
  if (user.role !== "admin" && user.role !== "publisher") {
    notFound();
  }

  return <AppShell>{children}</AppShell>;
}
