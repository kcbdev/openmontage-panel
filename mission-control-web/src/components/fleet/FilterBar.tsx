import type { ProjectStatus } from "@/lib/types";

const STATUS_OPTIONS: { value: ProjectStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "provisioning", label: "Starting" },
  { value: "awaiting_checkpoint", label: "Running" },
  { value: "awaiting_approval", label: "Awaiting you" },
  { value: "anomaly", label: "Anomaly" },
  { value: "done", label: "Archived" },
];

export function FilterBar({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex gap-2">
      {STATUS_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`text-sm px-3 py-1 rounded-full border transition-colors ${
            value === opt.value
              ? "bg-blue-100 border-blue-500 text-blue-700"
              : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
