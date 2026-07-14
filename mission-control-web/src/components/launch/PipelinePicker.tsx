"use client";

import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";

interface Pipeline {
  id: string;
  name: string;
  description: string;
  best_for: string;
  category: string;
  stability: string;
  stage_count: number;
}

export function PipelinePicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const { data: pipelines, error } = useSWR<Pipeline[]>(
    "pipelines",
    () => apiClient.getPipelines() as Promise<Pipeline[]>,
  );

  if (error) return <div className="text-red-500 text-sm">Failed to load pipelines</div>;
  if (!pipelines)
    return <div className="text-gray-400 text-sm">Loading pipelines...</div>;

  return (
    <Card>
      <CardContent className="pt-4">
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Pipeline
        </label>
        <div className="grid grid-cols-3 gap-3">
          {pipelines.map((p) => (
            <button
              key={p.id}
              onClick={() => onChange(p.id)}
              className={`border rounded-lg p-3 text-left text-sm transition-colors ${
                value === p.id
                  ? "border-blue-500 bg-blue-50"
                  : "border-gray-200 bg-white hover:border-gray-300"
              }`}
            >
              <p className="font-medium text-gray-900">{p.name || p.id}</p>
              {p.description && (
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                  {p.description}
                </p>
              )}
              {p.best_for && (
                <span className="inline-block mt-2 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {p.best_for}
                </span>
              )}
              <span className="inline-block mt-2 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded ml-1">
                {p.stage_count} stages
              </span>
            </button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
