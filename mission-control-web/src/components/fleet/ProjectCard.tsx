import Link from "next/link";
import type { Project } from "@/lib/types";
import { StatusLight } from "./StatusLight";

export function ProjectCard({ project }: { project: Project }) {
  const runId = project.run_id || project.id;
  return (
    <Link
      href={`/projects/${project.id}/run/${runId}`}
      className="block border rounded-lg p-4 hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="font-medium truncate">{project.name}</h3>
        <StatusLight status={project.status} />
      </div>
      <p className="text-xs text-gray-500 mb-1">{project.pipeline_type}</p>
      <p className="text-xs text-gray-400">
        {project.created_at
          ? new Date(project.created_at).toLocaleDateString()
          : ""}
      </p>
    </Link>
  );
}
