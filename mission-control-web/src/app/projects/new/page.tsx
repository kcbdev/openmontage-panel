"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/lib/toast";
import { BriefInput } from "@/components/launch/BriefInput";
import { DurationSlider } from "@/components/launch/DurationSlider";
import { CostDial } from "@/components/launch/CostDial";
import { PipelinePicker } from "@/components/launch/PipelinePicker";
import {
  StudioForm,
  defaultStudioParams,
  type StudioParams,
} from "@/components/launch/StudioForm";

export default function LaunchConsole() {
  const router = useRouter();
  const [brief, setBrief] = useState("");
  const [duration, setDuration] = useState(45);
  const [costTier, setCostTier] = useState("balanced");
  const [pipelineType, setPipelineType] = useState("animated-explainer");
  const [studioMode, setStudioMode] = useState(false);
  const [studioParams, setStudioParams] = useState<StudioParams>(defaultStudioParams());
  const [launching, setLaunching] = useState(false);
  const { addToast } = useToast();

  async function handleLaunch() {
    if (!brief.trim()) return;
    setLaunching(true);
    try {
      const body: Record<string, unknown> = {
        name: brief.slice(0, 60),
        pipeline_type: pipelineType,
        duration_target_seconds: duration,
      };
      if (studioMode) {
        body.studio_params = {
          render_runtime: studioParams.render_runtime === "auto" ? null : studioParams.render_runtime,
          footage_mode: studioParams.footage_mode,
          providers: Object.fromEntries(
            Object.entries(studioParams.providers).filter(([, v]) => v)
          ),
          model_routing: Object.fromEntries(
            Object.entries(studioParams.model_routing).filter(([, v]) => v)
          ),
          style_playbook: studioParams.style_playbook || null,
          budget_cap: studioParams.budget_cap || null,
        };
      }
      const res = await apiClient.createProject(body as Parameters<typeof apiClient.createProject>[0]);
      addToast("success", "Project launched");
      router.push(`/projects/${res.project_id}/run/${res.run_id}`);
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Launch failed");
      setLaunching(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">New Launch</h1>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={studioMode}
            onChange={(e) => setStudioMode(e.target.checked)}
            className="accent-blue-600"
          />
          Studio mode
        </label>
      </div>

      <PipelinePicker value={pipelineType} onChange={setPipelineType} />
      <BriefInput value={brief} onChange={setBrief} />
      <DurationSlider value={duration} onChange={setDuration} />
      <CostDial value={costTier} onChange={setCostTier} />

      {studioMode && (
        <StudioForm params={studioParams} onChange={setStudioParams} />
      )}

      <button
        onClick={handleLaunch}
        disabled={!brief.trim() || launching}
        className="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {launching ? "Launching..." : "Launch"}
      </button>
    </div>
  );
}
