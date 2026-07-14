"use client";

const PLAYBOOKS = [
  { id: "clean-professional", label: "Clean Professional", desc: "Minimalist, corporate, polished" },
  { id: "flat-motion-graphics", label: "Flat Motion Graphics", desc: "Bold colors, animated shapes" },
  { id: "cinematic", label: "Cinematic", desc: "Dramatic lighting, film-grade" },
  { id: "minimalist-diagram", label: "Minimalist Diagram", desc: "Simple diagrams, monochrome" },
  { id: "hand-drawn", label: "Hand-drawn", desc: "Sketchy, illustrative, warm" },
];

export function StylePlaybookPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">Style playbook</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <option value="">default</option>
        {PLAYBOOKS.map((p) => (
          <option key={p.id} value={p.id}>
            {p.label} — {p.desc}
          </option>
        ))}
      </select>
    </div>
  );
}
