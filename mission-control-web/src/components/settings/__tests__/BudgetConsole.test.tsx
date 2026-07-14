import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BudgetConsole } from "../BudgetConsole";
import { ToastProvider } from "@/lib/toast";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "mock-token", user: { id: "u1", role: "owner" } }),
}));

const mockBudget = { tenant_id: "t1", cap: 50, mode: "warn" };
const mockSummary = {
  cap: 50,
  total_spent: 12,
  total_reserved: 5,
  remaining: 38,
  projects: [
    { project_id: "p1", name: "Project Alpha", spent: 8, reserved: 3, entries_count: 4 },
    { project_id: "p2", name: "Project Beta", spent: 4, reserved: 2, entries_count: 2 },
  ],
};
const mockLedger = {
  total: 3,
  offset: 0,
  limit: 25,
  entries: [
    { id: "e1", project_id: "p1", run_id: "r1", action: "scene_gen", estimated_cost: 1, actual_cost: 0.8, mode: "warn", created_at: null },
    { id: "e2", project_id: "p1", run_id: "r1", action: "reconcile", estimated_cost: null, actual_cost: 0.2, mode: "warn", created_at: null },
  ],
};

let swrKeyCalls: Record<string, unknown> = {};

vi.mock("swr", () => ({
  default: (key: string, fetcher: () => Promise<unknown>) => {
    swrKeyCalls[key] = true;
    const data =
      key === "budget" ? mockBudget :
      key === "budget-summary" ? mockSummary :
      key === "budget-ledger" ? mockLedger :
      null;
    return { data, mutate: vi.fn() };
  },
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    getBudget: vi.fn(),
    getBudgetSummary: vi.fn(),
    getLedger: vi.fn(),
    updateBudget: vi.fn(),
    login: vi.fn(),
  },
}));

import { apiClient } from "@/lib/api-client";

function renderConsole() {
  return render(
    <ToastProvider>
      <BudgetConsole />
    </ToastProvider>
  );
}

describe("BudgetConsole", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    swrKeyCalls = {};
  });

  it("renders budget defaults and summary", () => {
    renderConsole();
    expect(screen.getByText("Budget Defaults")).toBeInTheDocument();
    expect(screen.getByText("Spend by Project")).toBeInTheDocument();
    expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    expect(screen.getByText("Project Beta")).toBeInTheDocument();
  });

  it("renders ledger entries", () => {
    renderConsole();
    expect(screen.getByText("Ledger")).toBeInTheDocument();
    expect(screen.getByText("scene_gen")).toBeInTheDocument();
    expect(screen.getByText("reconcile")).toBeInTheDocument();
  });

  it("calls updateBudget on save", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.updateBudget).mockResolvedValue({ status: "updated" });
    renderConsole();

    const saveButton = screen.getByRole("button", { name: /save/i });
    await user.click(saveButton);

    expect(apiClient.updateBudget).toHaveBeenCalledWith({ cap: 50, mode: "warn" });
  });

  it("handles cap input change", async () => {
    const user = userEvent.setup();
    renderConsole();

    const capInput = screen.getByDisplayValue("50");
    await user.clear(capInput);
    await user.type(capInput, "100");

    const saveButton = screen.getByRole("button", { name: /save/i });
    await user.click(saveButton);

    expect(apiClient.updateBudget).toHaveBeenCalledWith({ cap: 100, mode: "warn" });
  });

  it("shows remaining budget", () => {
    renderConsole();
    expect(screen.getByText(/\$38.00 remaining/)).toBeInTheDocument();
  });
});
