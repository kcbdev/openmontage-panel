"use client";

import useSWR from "swr";
import { useState } from "react";
import { apiClient } from "@/lib/api-client";
import { ProjectCard } from "@/components/fleet/ProjectCard";
import { FilterBar } from "@/components/fleet/FilterBar";
import { EmptyState } from "@/components/shared/EmptyState";
import type { ProjectStatus } from "@/lib/types";

export default function FleetView() {
  const [filter, setFilter] = useState<string>("all");
  const { data: projects, isLoading } = useSWR(
    "projects",
    () => apiClient.getProjects(),
    { refreshInterval: 5000 }
  );

  const filtered =
    filter === "all"
      ? projects
      : projects?.filter((p) => p.status === filter);

  if (isLoading) {
    return <div className="text-sm text-gray-400 py-12 text-center">Loading...</div>;
  }

  if (!projects || projects.length === 0) {
    return <EmptyState />;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Projects</h1>
        <span className="text-sm text-gray-400">{projects.length} project{projects.length !== 1 ? "s" : ""}</span>
      </div>
      <FilterBar value={filter} onChange={setFilter} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {filtered?.map((p) => (
          <ProjectCard key={p.id} project={p} />
        ))}
      </div>
    </div>
  );
}
