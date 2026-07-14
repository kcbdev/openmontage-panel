import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StoryboardGrid } from "../StoryboardGrid";
import { ToastProvider } from "@/lib/toast";
import type { ApprovalGate, SceneArtifact } from "@/lib/types";

const mockScenes: SceneArtifact[] = [
  { id: "s1", scene_number: 1, stage: "storyboard", thumbnail_url: "/img1.png", cost: 0.5, provider_used: "openai", is_locked: false },
  { id: "s2", scene_number: 2, stage: "storyboard", thumbnail_url: "/img2.png", cost: 0.3, provider_used: "openai", is_locked: true },
];

const mockGate: ApprovalGate = {
  id: "g1",
  stage: "storyboard",
  gate_type: "scene_approval",
  payload: { artifacts: mockScenes },
  created_at: null,
};

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    toggleAssetLock: vi.fn().mockResolvedValue({ id: "s1", is_locked: true }),
    resumeRun: vi.fn().mockResolvedValue({ run_id: "run-1", status: "awaiting_checkpoint", decision: "approve" }),
  },
}));

vi.mock("../SceneCard", () => ({
  SceneCard: ({ scene, onLockToggle }: { scene: { id: string; scene_number: number }; onLockToggle: (id: string) => void }) => (
    <div data-testid="scene-card">
      <span>Scene {scene.scene_number}</span>
      <button onClick={() => onLockToggle(scene.id)}>Lock</button>
    </div>
  ),
}));

import { apiClient } from "@/lib/api-client";

function renderGrid(overrides?: { gate?: ApprovalGate }) {
  const onResolved = vi.fn();
  const utils = render(
    <ToastProvider>
      <StoryboardGrid
        gate={overrides?.gate ?? mockGate}
        runId="run-1"
        onResolved={onResolved}
      />
    </ToastProvider>
  );
  return { ...utils, onResolved };
}

describe("StoryboardGrid", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders scene count from gate artifacts", () => {
    renderGrid();
    expect(screen.getByText("Storyboard / Scene Plan")).toBeInTheDocument();
    expect(screen.getByText(/scene 1/i)).toBeInTheDocument();
    expect(screen.getByText(/scene 2/i)).toBeInTheDocument();
  });

  it("shows fallback text when no artifacts", () => {
    const emptyGate: ApprovalGate = {
      ...mockGate,
      payload: { summary: "Custom summary text" },
    };
    renderGrid({ gate: emptyGate });
    expect(screen.getByText("Custom summary text")).toBeInTheDocument();
  });

  it("calls toggleAssetLock on lock button", async () => {
    const user = userEvent.setup();
    renderGrid();

    const lockButtons = screen.getAllByText("Lock");
    await user.click(lockButtons[0]);
    expect(apiClient.toggleAssetLock).toHaveBeenCalledWith("run-1", "s1");
  });

  it("calls resumeRun on approve", async () => {
    const user = userEvent.setup();
    const { onResolved } = renderGrid();

    await user.click(screen.getByRole("button", { name: /approve/i }));

    expect(apiClient.resumeRun).toHaveBeenCalledWith("run-1", { decision: "approve" });
    expect(onResolved).toHaveBeenCalled();
  });

  it("calls resumeRun on regenerate", async () => {
    const user = userEvent.setup();
    const { onResolved } = renderGrid();

    await user.click(screen.getByRole("button", { name: /regenerate unlocked/i }));

    expect(apiClient.resumeRun).toHaveBeenCalledWith("run-1", {
      decision: "approve",
      scope: { locked_scene_ids: ["s2"], regenerate_scenes: [] },
    });
    expect(onResolved).toHaveBeenCalled();
  });
});
