import type { StageCheckpoint } from "@/lib/types";
import { CheckCircle, Clock } from "lucide-react";

export function DecisionTrailPanel({
  checkpoints,
}: {
  checkpoints: StageCheckpoint[];
}) {
  if (checkpoints.length === 0) {
    return (
      <div className="text-sm text-gray-400 text-center py-8">
        No checkpoints yet
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {checkpoints.map((cp) => (
        <div key={cp.id} className="flex items-start gap-3 text-sm">
          <div className="mt-0.5">
            {cp.decision_log ? (
              <CheckCircle className="w-4 h-4 text-blue-500" />
            ) : (
              <Clock className="w-4 h-4 text-gray-300" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium text-gray-700 capitalize">
              {cp.stage.replace("_", " ")}
            </p>
            <p className="text-xs text-gray-400 truncate">
              {cp.checkpoint?.summary
                ? String(cp.checkpoint.summary).slice(0, 80)
                : ""}
            </p>
            {cp.created_at && (
              <p className="text-xs text-gray-400 mt-0.5">
                {new Date(cp.created_at).toLocaleTimeString()}
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
