"use client";

import { Lock, Unlock, Image } from "lucide-react";
import type { SceneArtifact } from "@/lib/types";

export function SceneCard({
  scene,
  onLockToggle,
}: {
  scene: SceneArtifact;
  onLockToggle: (sceneId: string) => void;
}) {
  return (
    <div className="border rounded-lg overflow-hidden group">
      <div className="aspect-video bg-gray-100 flex items-center justify-center relative">
        <Image className="w-8 h-8 text-gray-300" />
        <span className="absolute bottom-1 left-1 bg-black/60 text-white text-[10px] px-1.5 py-0.5 rounded">
          Scene {scene.scene_number}
        </span>
      </div>
      <div className="p-2 space-y-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium text-gray-500 uppercase">
            {scene.provider_used}
          </span>
          <button
            onClick={() => onLockToggle(scene.id)}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            title={scene.is_locked ? "Unlock scene" : "Lock scene"}
          >
            {scene.is_locked ? (
              <Lock className="w-3.5 h-3.5 text-amber-500" />
            ) : (
              <Unlock className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
        <p className="text-xs text-gray-600">${scene.cost.toFixed(4)}</p>
      </div>
    </div>
  );
}
