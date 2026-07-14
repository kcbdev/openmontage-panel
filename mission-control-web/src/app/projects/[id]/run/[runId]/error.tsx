"use client";

import Link from "next/link";
import { use } from "react";

export default function RunError({
  error,
  reset,
  params,
}: {
  error: Error & { digest?: string };
  reset: () => void;
  params: Promise<{ id: string; runId: string }>;
}) {
  const { id } = use(params);

  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <h1 className="text-lg font-semibold text-gray-900">Run error</h1>
      <p className="text-sm text-gray-500 max-w-md text-center">
        {error.message || "An unexpected error occurred while loading this run."}
      </p>
      <div className="flex gap-3">
        <button
          onClick={reset}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700"
        >
          Try again
        </button>
        <Link
          href={`/projects/${id}`}
          className="px-4 py-2 border border-gray-300 text-sm rounded-lg hover:bg-gray-50"
        >
          Back to project
        </Link>
      </div>
    </div>
  );
}
