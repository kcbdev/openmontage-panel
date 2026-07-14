import Link from "next/link";

export function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4">
        <span className="text-2xl text-gray-400">+</span>
      </div>
      <h2 className="text-lg font-medium text-gray-700 mb-2">
        No projects yet
      </h2>
      <p className="text-sm text-gray-500 mb-6 max-w-xs">
        Launch your first video project — Mission Control will guide you through
        every stage.
      </p>
      <Link
        href="/projects/new"
        className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
      >
        + New Launch
      </Link>
    </div>
  );
}
