"use client";

import { use } from "react";
import useSWR from "swr";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

export default function ProjectArchivePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { token } = useAuth();

  const { data: project, isLoading } = useSWR(
    token ? `project-${id}` : null,
    () => apiClient.getProject(id),
  );

  const { data: assets } = useSWR(
    token ? `assets-${id}` : null,
    () => apiClient.getProjectAssets(id),
  );

  const { data: download } = useSWR(
    token ? `download-${id}` : null,
    () => apiClient.downloadProject(id),
  );

  if (isLoading) return <div className="text-sm text-gray-400 py-12 text-center">Loading...</div>;
  if (!project) return <div className="text-sm text-red-500 py-12 text-center">Project not found</div>;

  const runs = (download as any)?.runs ?? [];

  return (
    <div className="space-y-6 py-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <Link href="/projects" className="text-xs text-blue-600 hover:underline">&larr; Projects</Link>
          <h1 className="text-xl font-semibold mt-1">{project.name}</h1>
          <p className="text-xs text-gray-500 mt-1">
            {project.pipeline_type} &middot; {project.status}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href={`/projects/${id}/remix`}
            className="text-sm bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700"
          >
            Remix
          </Link>
        </div>
      </div>

      {/* Runs */}
      <section>
        <h2 className="text-sm font-medium text-gray-700 mb-2">Runs</h2>
        {runs.length === 0 && <p className="text-xs text-gray-400">No runs yet.</p>}
        <div className="space-y-2">
          {runs.map((r: any) => (
            <Link
              key={r.id}
              href={`/projects/${id}/run/${r.id}`}
              className="block border rounded-lg p-3 hover:shadow-sm transition-shadow"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-mono">{r.id.slice(0, 8)}...</span>
                <span className="text-xs text-gray-500">{r.status}</span>
              </div>
              {r.current_stage && (
                <p className="text-xs text-gray-400 mt-1">Stage: {r.current_stage}</p>
              )}
            </Link>
          ))}
        </div>
      </section>

      {/* Assets */}
      <section>
        <h2 className="text-sm font-medium text-gray-700 mb-2">Assets</h2>
        {!assets || assets.length === 0 ? (
          <p className="text-xs text-gray-400">No assets yet.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {assets.map((a) => (
              <div key={a.id} className="border rounded-lg p-3">
                {a.thumbnail_url && (
                  <img src={a.thumbnail_url} alt="" className="w-full h-24 object-cover rounded mb-2" />
                )}
                <p className="text-xs font-medium truncate">{a.type}</p>
                <p className="text-xs text-gray-400">{a.stage}{a.scene_number != null ? ` #${a.scene_number}` : ""}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
