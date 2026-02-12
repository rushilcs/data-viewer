"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRequireAuth } from "@/lib/auth";
import { api } from "@/lib/api";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useRequireAuth();
  const pathname = usePathname();

  async function handleLogout() {
    await api.logout();
    window.location.href = "/login";
  }

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0b]">
        <p className="text-zinc-500">Loading…</p>
      </div>
    );
  }

  const canUpload = user.role === "admin" || user.role === "publisher";

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0b] text-zinc-100">
      <header className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <nav className="flex items-center gap-6">
            <Link
              href="/datasets"
              className={`font-medium transition ${
                pathname?.startsWith("/datasets") && !pathname?.startsWith("/datasets/new")
                  ? "text-emerald-400"
                  : "text-zinc-300 hover:text-zinc-100"
              }`}
            >
              Datasets
            </Link>
            {canUpload && (
              <Link
                href="/upload"
                className={`font-medium transition ${
                  pathname?.startsWith("/upload")
                    ? "text-emerald-400"
                    : "text-zinc-300 hover:text-zinc-100"
                }`}
              >
                Upload
              </Link>
            )}
          </nav>
          <div className="flex items-center gap-4">
            <span className="text-sm text-zinc-500">{user.org_name}</span>
            <span className="text-sm text-zinc-400">{user.email}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="text-sm text-zinc-500 hover:text-zinc-300 transition"
            >
              Log out
            </button>
          </div>
        </div>
      </header>
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 py-6">{children}</main>
    </div>
  );
}
