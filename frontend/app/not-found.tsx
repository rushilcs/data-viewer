import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#0a0a0b] flex flex-col items-center justify-center px-4 text-zinc-100">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="mt-2 text-zinc-500">The page you’re looking for doesn’t exist.</p>
      <Link
        href="/datasets"
        className="mt-6 text-emerald-400 hover:text-emerald-300 underline"
      >
        Go to Datasets
      </Link>
    </div>
  );
}
