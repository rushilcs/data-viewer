"use client";

type Props = {
  prompt?: string;
  metadata?: Record<string, unknown>;
};

export function MetadataPanel({ prompt, metadata }: Props) {
  if (!prompt && (!metadata || Object.keys(metadata).length === 0)) return null;
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 p-4 mt-4">
      {prompt && (
        <div className="mb-2">
          <span className="text-sm font-medium text-zinc-400">Prompt</span>
          <p className="text-zinc-200 mt-1 whitespace-pre-wrap break-words">{prompt}</p>
        </div>
      )}
      {metadata && Object.keys(metadata).length > 0 && (
        <div>
          <span className="text-sm font-medium text-zinc-400">Metadata</span>
          <pre className="text-sm text-zinc-300 mt-1 overflow-auto max-h-40 bg-zinc-900/80 p-2 rounded border border-zinc-700">
            {JSON.stringify(metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
