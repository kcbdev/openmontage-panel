"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { ThumbsUp, RotateCcw, XCircle, ShieldAlert } from "lucide-react";

const ROLE_RANK: Record<string, number> = { viewer: 0, editor: 1, owner: 2 };

export function GateActionBar({
  runId,
  stage,
  requiredRole,
  onResolved,
}: {
  runId: string;
  stage: string;
  requiredRole?: string | null;
  onResolved: () => void;
}) {
  const { user } = useAuth();
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);

  const userRole = user?.role || "viewer";
  const canAct = !requiredRole || (ROLE_RANK[userRole] ?? 0) >= (ROLE_RANK[requiredRole] ?? 999);

  async function respond(decision: string) {
    setLoading(true);
    try {
      await apiClient.resumeRun(runId, { decision, revision_notes: notes });
      onResolved();
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="border-t pt-4 space-y-3">
      <div className="flex items-center gap-2">
        <p className="text-sm font-medium text-gray-700">
          Review {stage.replace("_", " ")}
        </p>
        {requiredRole && !canAct && (
          <span className="inline-flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
            <ShieldAlert className="w-3 h-3" />
            requires {requiredRole}
          </span>
        )}
      </div>
      <div className="flex gap-3 items-start">
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Revision notes (optional)..."
          className="flex-1 border rounded px-3 py-2 text-sm resize-none h-20"
          disabled={loading}
        />
        <div className="flex flex-col gap-2">
          <button
            onClick={() => respond("approve")}
            disabled={loading || !canAct}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            <ThumbsUp className="w-4 h-4" />
            Approve
          </button>
          <button
            onClick={() => respond("revise")}
            disabled={loading || !notes.trim() || !canAct}
            className="inline-flex items-center gap-2 px-4 py-2 border border-gray-200 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50"
          >
            <RotateCcw className="w-4 h-4" />
            Revise
          </button>
          <button
            onClick={() => respond("reject")}
            disabled={loading || !canAct}
            className="inline-flex items-center gap-2 px-4 py-2 text-red-500 rounded-lg text-sm font-medium hover:bg-red-50 disabled:opacity-50"
          >
            <XCircle className="w-4 h-4" />
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}
