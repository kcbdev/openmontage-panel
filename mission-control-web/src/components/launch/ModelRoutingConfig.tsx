"use client";

const STAGES = ["research", "proposal", "script", "scene_plan", "assets", "edit"];

const MODELS = [
  "anthropic/claude-sonnet-4",
  "anthropic/claude-3.5-haiku",
  "openai/gpt-4o",
  "openai/gpt-4o-mini",
  "google/gemini-2.0-flash",
  "google/gemini-2.5-pro",
];

export function ModelRoutingConfig({
  value,
  onChange,
}: {
  value: Record<string, string>;
  onChange: (v: Record<string, string>) => void;
}) {
  function setStage(stage: string, model: string) {
    onChange({ ...value, [stage]: model || "" });
  }

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        Model routing per stage
      </label>
      <div className="grid grid-cols-2 gap-2">
        {STAGES.map((stage) => (
          <div key={stage} className="flex items-center gap-2">
            <span className="text-xs text-gray-500 w-20 capitalize">{stage}</span>
            <select
              value={value[stage] || ""}
              onChange={(e) => setStage(stage, e.target.value)}
              className="h-7 flex-1 min-w-0 rounded-lg border border-input bg-transparent px-2 text-xs transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <option value="">default</option>
              {MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
    </div>
  );
}
