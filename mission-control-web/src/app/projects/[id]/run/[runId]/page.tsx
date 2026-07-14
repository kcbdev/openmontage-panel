"use client";

import { use } from "react";
import useSWR from "swr";
import { apiClient } from "@/lib/api-client";
import { useRunStream } from "@/lib/websocket";
import { useAuth } from "@/lib/auth-context";
import { StageTracker, LiveProgressView } from "@/components/deck/StageTracker";
import { GateActionBar } from "@/components/deck/GateActionBar";
import { CostMeter } from "@/components/deck/CostMeter";
import { DecisionTrailPanel } from "@/components/deck/DecisionTrailPanel";
import { AnomalyPanel } from "@/components/deck/AnomalyPanel";
import { StoryboardGrid } from "@/components/deck/StoryboardGrid";
import {
  ProposalView,
  ScreenplayView,
  PublishPreview,
} from "@/components/deck/GateViews";
import type { ApprovalGate, StageCheckpoint } from "@/lib/types";
import { Loader2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export default function CommandDeck({
  params,
}: {
  params: Promise<{ id: string; runId: string }>;
}) {
  const { runId } = use(params);
  const { token } = useAuth();

  const { state: liveState, connected } = useRunStream(runId, token);

  const { data: fallbackState, mutate: refreshState } = useSWR(
    `run-state-${runId}`,
    () => apiClient.getRunState(runId),
    { refreshInterval: connected ? 0 : 3000 }
  );

  const { data: gates, mutate: refreshGates } = useSWR(
    `gates-${runId}`,
    () => apiClient.getPendingGates(runId),
    { refreshInterval: 2000 }
  );

  const { data: checkpoints } = useSWR(
    `checkpoints-${runId}`,
    () => apiClient.getCheckpoints(runId),
    { refreshInterval: 5000 }
  );

  const state = liveState || fallbackState || null;
  const pendingGate: ApprovalGate | null =
    gates && gates.length > 0 ? gates[0] : null;

  function handleResolved() {
    refreshState();
    refreshGates();
  }

  function renderGateBody(gate: ApprovalGate) {
    switch (gate.stage) {
      case "proposal":
        return <ProposalView gate={gate} />;
      case "script":
        return <ScreenplayView gate={gate} />;
      case "storyboard":
      case "scene_plan":
      case "assets":
        return (
          <StoryboardGrid
            gate={gate}
            runId={runId}
            onResolved={handleResolved}
          />
        );
      case "publish":
        return <PublishPreview gate={gate} />;
      default:
        return (
          <p className="text-sm text-gray-500">
            Review {gate.stage.replace("_", " ")}
          </p>
        );
    }
  }

  if (!state) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
      </div>
    );
  }

  const costSnapshot = state.last_checkpoint?.cost_snapshot;
  const currentCost =
    costSnapshot && typeof costSnapshot.total_cost === "number"
      ? costSnapshot.total_cost
      : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Command Deck</h1>
          <p className="text-sm text-gray-500">
            Run {runId.slice(0, 8)} &middot; {state.status.replace(/_/g, " ")}
          </p>
          {state.anomaly_reason && (
            <p className="text-xs text-red-500 mt-1">
              {state.anomaly_reason}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-500" : "bg-gray-300"}`} />
          <span className="text-xs text-gray-400">
            {connected ? "Live" : "Polling"}
          </span>
        </div>
      </div>

      <Card>
        <CardContent className="pt-6">
          <StageTracker currentStage={state.current_stage} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {state.status === "anomaly" ? (
            <AnomalyPanel
              runId={runId}
              anomalyReason={state.anomaly_reason}
              onRecovered={handleResolved}
            />
          ) : pendingGate ? (
            <Card>
              <CardContent className="pt-6 space-y-4">
                {renderGateBody(pendingGate)}
                <Separator />
                <GateActionBar
                  runId={runId}
                  stage={pendingGate.stage}
                  requiredRole={pendingGate.required_role}
                  onResolved={handleResolved}
                />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <LiveProgressView currentStage={state.current_stage} />
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card>
            <CardContent className="pt-4 space-y-3">
              <CostMeter current={currentCost} />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3">
                Decision Trail
              </h3>
              <DecisionTrailPanel checkpoints={checkpoints ?? []} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
