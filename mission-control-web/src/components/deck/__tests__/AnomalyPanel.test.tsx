import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "@/lib/toast";
import { AnomalyPanel } from "../AnomalyPanel";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    retryRun: vi.fn(),
  },
}));

import { apiClient } from "@/lib/api-client";

function renderPanel(anomalyReason: string | null = "Something went wrong") {
  const onRecovered = vi.fn();
  const utils = render(
    <ToastProvider>
      <AnomalyPanel
        runId="run-1"
        anomalyReason={anomalyReason}
        onRecovered={onRecovered}
      />
    </ToastProvider>
  );
  return { ...utils, onRecovered };
}

describe("AnomalyPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders anomaly reason", () => {
    renderPanel("GPU out of memory");
    expect(screen.getByText("Pipeline Anomaly")).toBeInTheDocument();
    expect(screen.getByText("GPU out of memory")).toBeInTheDocument();
  });

  it("renders fallback message when reason is null", () => {
    renderPanel(null);
    expect(screen.getByText(/unknown error/i)).toBeInTheDocument();
  });

  it("calls retryRun and onRecovered on Retry click", async () => {
    const user = userEvent.setup();
    const { onRecovered } = renderPanel();
    vi.mocked(apiClient.retryRun).mockResolvedValue({ run_id: "run-1", status: "awaiting_checkpoint", decision: "approve" });

    await user.click(screen.getByText("Retry"));

    expect(apiClient.retryRun).toHaveBeenCalledWith("run-1", { provider_override: undefined });
    expect(onRecovered).toHaveBeenCalled();
  });

  it("shows error toast when retry fails", async () => {
    const user = userEvent.setup();
    renderPanel();
    vi.mocked(apiClient.retryRun).mockRejectedValue(new Error("provider unavailable"));

    await user.click(screen.getByText("Retry"));

    expect(apiClient.retryRun).toHaveBeenCalled();
  });

  it("renders three retry buttons", () => {
    renderPanel();
    expect(screen.getByText("Retry")).toBeInTheDocument();
    expect(screen.getByText("Try Different Provider")).toBeInTheDocument();
    expect(screen.getByText("Roll Back & Retry")).toBeInTheDocument();
  });
});
