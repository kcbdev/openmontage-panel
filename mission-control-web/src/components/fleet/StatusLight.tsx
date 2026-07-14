import type { ProjectStatus } from "@/lib/types";

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  provisioning: { color: "bg-gray-400", label: "Starting" },
  awaiting_checkpoint: { color: "bg-green-500", label: "Running" },
  awaiting_approval: { color: "bg-yellow-500", label: "Awaiting you" },
  anomaly: { color: "bg-red-500", label: "Anomaly" },
  done: { color: "bg-gray-300", label: "Archived" },
};

export function StatusLight({ status }: { status: ProjectStatus }) {
  const s = STATUS_MAP[status] ?? STATUS_MAP.provisioning;
  return (
    <span className="flex items-center gap-2">
      <span className={`w-2.5 h-2.5 rounded-full ${s.color}`} />
      <span className="text-sm text-gray-600">{s.label}</span>
    </span>
  );
}
