import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4 text-slate-800">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="mt-2 text-slate-500">The page you’re looking for doesn’t exist.</p>
      <Link
        href="/datasets"
        className="mt-6 text-teal-600 hover:text-teal-500 font-medium"
      >
        Go to Datasets
      </Link>
    </div>
  );
}
