"use client";

import { Card, CardContent } from "@/components/ui/card";
import { ProviderSelect } from "./ProviderSelect";
import { ModelRoutingConfig } from "./ModelRoutingConfig";
import { StylePlaybookPicker } from "./StylePlaybookPicker";

export interface StudioParams {
  render_runtime: string;
  footage_mode: string;
  providers: Record<string, string>;
  model_routing: Record<string, string>;
  style_playbook: string;
  budget_cap: number;
}

export function defaultStudioParams(): StudioParams {
  return {
    render_runtime: "auto",
    footage_mode: "ai_generated",
    providers: {},
    model_routing: {},
    style_playbook: "",
    budget_cap: 0,
  };
}

export function StudioForm({
  params,
  onChange,
}: {
  params: StudioParams;
  onChange: (p: StudioParams) => void;
}) {
  function set<K extends keyof StudioParams>(key: K, val: StudioParams[K]) {
    onChange({ ...params, [key]: val });
  }

  function setProvider(key: string, val: string) {
    set("providers", { ...params.providers, [key]: val || "" });
  }

  const radioClass = (selected: boolean) =>
    `flex-1 border rounded-lg p-2 text-center text-xs transition-colors ${
      selected
        ? "border-blue-500 bg-blue-50 text-blue-700"
        : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
    }`;

  return (
    <Card>
      <CardContent className="pt-4 space-y-4">
        <label className="block text-sm font-medium text-gray-700">
          Studio Parameters
        </label>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Render runtime</label>
          <div className="flex gap-2">
            {["auto", "remotion", "hyperframes"].map((r) => (
              <button key={r} onClick={() => set("render_runtime", r)} className={radioClass(params.render_runtime === r)}>
                {r}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Footage mode</label>
          <div className="flex gap-2">
            {[
              { id: "ai_generated", label: "AI Generated" },
              { id: "real_footage_only", label: "Real footage" },
              { id: "hybrid", label: "Hybrid" },
            ].map((f) => (
              <button key={f.id} onClick={() => set("footage_mode", f.id)} className={radioClass(params.footage_mode === f.id)}>
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <ProviderSelect label="Video generation" capability="video_gen" value={params.providers.video_gen || ""} onChange={(v) => setProvider("video_gen", v)} />
          <ProviderSelect label="Image generation" capability="image_gen" value={params.providers.image_gen || ""} onChange={(v) => setProvider("image_gen", v)} />
          <ProviderSelect label="TTS / narration" capability="tts" value={params.providers.tts || ""} onChange={(v) => setProvider("tts", v)} />
          <ProviderSelect label="Music" capability="music" value={params.providers.music || ""} onChange={(v) => setProvider("music", v)} />
        </div>

        <ModelRoutingConfig value={params.model_routing} onChange={(v) => set("model_routing", v)} />

        <StylePlaybookPicker value={params.style_playbook} onChange={(v) => set("style_playbook", v)} />

        <div className="space-y-1">
          <label className="block text-sm font-medium text-gray-700">Budget cap (this project)</label>
          <div className="relative">
            <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-gray-400">$</span>
            <input
              type="number"
              min={0}
              step={0.5}
              value={params.budget_cap || ""}
              onChange={(e) => set("budget_cap", parseFloat(e.target.value) || 0)}
              placeholder="0.00"
              className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent pl-6 pr-2.5 py-1 text-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
