"use client";

import { Suspense, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, ApiError, setCsrfToken } from "@/lib/api";

function friendlyMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 400) return "Check your input and try again.";
    if (err.status === 422) return "Invalid or duplicate email.";
    if (typeof err.message === "string" && err.message.length < 100) return err.message;
    return "Sign up failed. Please try again.";
  }
  return "Something went wrong. Please try again.";
}

function AcceptInviteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tokenFromUrl = searchParams.get("token") ?? "";

  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (tokenFromUrl) setToken(tokenFromUrl);
  }, [tokenFromUrl]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    setLoading(true);
    try {
      const data = await api.signup(email.trim(), password);
      setCsrfToken(data.csrf_token);
      router.push("/datasets");
      router.refresh();
    } catch (err) {
      setError(friendlyMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a0b] flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-6 shadow-xl backdrop-blur">
          <h1 className="text-xl font-semibold text-zinc-100">Accept invite / Sign up</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Create an account to access shared datasets.
          </p>
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {error && (
              <p className="rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-400 border border-red-500/20">
                {error}
              </p>
            )}
            {tokenFromUrl && (
              <p className="rounded-lg bg-emerald-500/10 px-3 py-2 text-sm text-emerald-400 border border-emerald-500/20">
                Invite link detected. Enter your details below.
              </p>
            )}
            <div>
              <label htmlFor="token" className="block text-sm font-medium text-zinc-400 mb-1">
                Invite token (optional)
              </label>
              <input
                id="token"
                type="text"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-800/80 px-3 py-2 text-zinc-100 placeholder-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                placeholder="Paste token if you have one"
              />
            </div>
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-zinc-400 mb-1">
                Email *
              </label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full rounded-lg border border-zinc-700 bg-zinc-800/80 px-3 py-2.5 text-zinc-100 placeholder-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-zinc-400 mb-1">
                Password *
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-800/80 px-3 py-2.5 text-zinc-100 placeholder-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
                placeholder="At least 8 characters"
              />
            </div>
            <div>
              <label htmlFor="confirm" className="block text-sm font-medium text-zinc-400 mb-1">
                Confirm password *
              </label>
              <input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                minLength={8}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-800/80 px-3 py-2.5 text-zinc-100 placeholder-zinc-500 focus:border-emerald-500/50 focus:outline-none focus:ring-1 focus:ring-emerald-500/50"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-emerald-500/90 py-2.5 font-medium text-zinc-900 shadow-lg shadow-emerald-500/20 transition hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Creating account…" : "Create account"}
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-zinc-500">
            Already have an account?{" "}
            <Link href="/login" className="text-emerald-400 hover:text-emerald-300 underline">
              Sign in
            </Link>
          </p>
        </div>
        <p className="mt-4 text-center">
          <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-400">
            ← Back to home
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#0a0a0b] flex items-center justify-center px-4">
        <p className="text-zinc-500">Loading…</p>
      </div>
    }>
      <AcceptInviteForm />
    </Suspense>
  );
}
