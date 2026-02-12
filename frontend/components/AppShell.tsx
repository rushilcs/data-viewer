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
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <p className="text-slate-500">Loading…</p>
      </div>
    );
  }

  const canUpload = user.role === "admin" || user.role === "publisher";

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <header className="border-b border-slate-200 bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <nav className="flex items-center gap-6">
            <Link
              href="/datasets"
              className={`font-medium transition rounded-lg px-2 py-1 ${
                pathname?.startsWith("/datasets") && !pathname?.startsWith("/datasets/new")
                  ? "text-teal-600 bg-teal-50"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Datasets
            </Link>
            {canUpload && (
              <Link
                href="/upload"
                className={`font-medium transition rounded-lg px-2 py-1 ${
                  pathname?.startsWith("/upload")
                    ? "text-teal-600 bg-teal-50"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                }`}
              >
                Upload
              </Link>
            )}
          </nav>
          <div className="flex items-center gap-4">
            <span className="text-sm text-slate-500">{user.org_name}</span>
            <span className="text-sm text-slate-600">{user.email}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="text-sm text-slate-500 hover:text-slate-700 transition rounded-lg px-2 py-1 hover:bg-slate-100"
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
