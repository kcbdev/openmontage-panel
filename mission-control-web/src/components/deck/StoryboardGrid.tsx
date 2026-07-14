"use client";

import { useState, useCallback, useEffect } from "react";
import { Layout, RefreshCw, ThumbsUp } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/lib/toast";
import { SceneCard } from "./SceneCard";
import type { ApprovalGate, SceneArtifact } from "@/lib/types";

function extractArtifacts(gate: ApprovalGate): SceneArtifact[] {
  const raw = gate.payload?.artifacts;
  if (Array.isArray(raw)) {
    return raw as SceneArtifact[];
  }
  return [];
}

export function StoryboardGrid({
  gate,
  runId,
  onResolved,
}: {
  gate: ApprovalGate;
  runId: string;
  onResolved?: () => void;
}) {
  const [scenes, setScenes] = useState<SceneArtifact[]>(() => extractArtifacts(gate));
  const [loading, setLoading] = useState(false);
  const { addToast } = useToast();

  const handleLockToggle = useCallback(async (sceneId: string) => {
    try {
      const result = await apiClient.toggleAssetLock(runId, sceneId);
      setScenes((prev) =>
        prev.map((s) =>
          s.id === sceneId ? { ...s, is_locked: result.is_locked } : s
        )
      );
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Failed to toggle lock");
    }
  }, [runId, addToast]);

  const handleRegenerate = useCallback(async () => {
    setLoading(true);
    try {
      const lockedIds = scenes.filter((s) => s.is_locked).map((s) => s.id);
      await apiClient.resumeRun(runId, {
        decision: "approve",
        scope: { locked_scene_ids: lockedIds, regenerate_scenes: [] },
      });
      addToast("success", "Regeneration started");
      onResolved?.();
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Failed to regenerate");
    } finally {
      setLoading(false);
    }
  }, [runId, scenes, onResolved, addToast]);

  useEffect(() => {
    setScenes(extractArtifacts(gate));
  }, [gate]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layout className="w-5 h-5 text-gray-500" />
          <h3 className="text-lg font-medium">Storyboard / Scene Plan</h3>
        </div>
        {scenes.length > 0 && (
          <div className="flex gap-2">
            <button
              onClick={handleRegenerate}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Regenerate Unlocked
            </button>
            <button
              onClick={async () => {
                try {
                  await apiClient.resumeRun(runId, { decision: "approve" });
                  addToast("success", "Approved");
                  onResolved?.();
                } catch (e) {
                  addToast("error", e instanceof Error ? e.message : "Failed to approve");
                }
              }}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <ThumbsUp className="w-3.5 h-3.5" />
              Approve
            </button>
          </div>
        )}
      </div>

      {scenes.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {scenes.map((scene) => (
            <SceneCard
              key={scene.id}
              scene={scene}
              onLockToggle={handleLockToggle}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-gray-600">
          {gate.payload?.summary
            ? String(gate.payload.summary)
            : "Awaiting storyboard content..."}
        </p>
      )}
    </div>
  );
}


