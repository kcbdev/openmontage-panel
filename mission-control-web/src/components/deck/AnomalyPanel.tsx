"use client";

import { useState } from "react";
import { AlertTriangle, RefreshCw, RotateCcw, Shuffle } from "lucide-react";
import { apiClient } from "@/lib/api-client";
import { useToast } from "@/lib/toast";

const FALLBACK_PROVIDERS = ["midjourney", "stable-diffusion", "kling", "pika"];

export function AnomalyPanel({
  runId,
  anomalyReason,
  onRecovered,
}: {
  runId: string;
  anomalyReason: string | null;
  onRecovered: () => void;
}) {
  const [retrying, setRetrying] = useState<string | null>(null);
  const [retryError, setRetryError] = useState("");
  const { addToast } = useToast();

  async function handleRetry(providerOverride?: string) {
    setRetrying(providerOverride ?? "same");
    setRetryError("");
    try {
      await apiClient.retryRun(runId, {
        provider_override: providerOverride,
      });
      addToast("success", "Retry succeeded");
      onRecovered();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to retry run";
      setRetryError(msg);
      addToast("error", msg);
    } finally {
      setRetrying(null);
    }
  }

  return (
    <div className="border-2 border-red-300 bg-red-50 rounded-lg p-6 space-y-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-6 h-6 text-red-500 shrink-0 mt-0.5" />
        <div>
          <h3 className="text-lg font-semibold text-red-700">
            Pipeline Anomaly
          </h3>
          <p className="text-sm text-red-600 mt-1">
            {anomalyReason ?? "An unknown error occurred during processing"}
          </p>
        </div>
      </div>

      {retryError && (
        <p className="text-xs text-red-600 bg-red-100 rounded px-2 py-1">{retryError}</p>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => handleRetry()}
          disabled={retrying !== null}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
        >
          <RefreshCw className="w-4 h-4" />
          {retrying === "same" ? "Retrying..." : "Retry"}
        </button>
        <button
          onClick={() => handleRetry(FALLBACK_PROVIDERS[Math.floor(Math.random() * FALLBACK_PROVIDERS.length)])}
          disabled={retrying !== null}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm border border-red-300 text-red-700 rounded-lg hover:bg-red-100 disabled:opacity-50"
        >
          <Shuffle className="w-4 h-4" />
          {retrying ? "Retrying..." : "Try Different Provider"}
        </button>
        <button
          onClick={() => handleRetry()}
          disabled={retrying !== null}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-sm border border-red-300 text-red-700 rounded-lg hover:bg-red-100 disabled:opacity-50"
        >
          <RotateCcw className="w-4 h-4" />
          Roll Back & Retry
        </button>
      </div>
    </div>
  );
}
