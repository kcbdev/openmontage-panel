import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProfileList } from "../ProfileList";
import { ToastProvider } from "@/lib/toast";
import type { ReactNode } from "react";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({ token: "mock-token", user: { id: "u1", role: "owner" } }),
}));

vi.mock("swr", () => ({
  default: (key: string) => {
    if (key === "profiles") {
      return {
        data: [
          { id: "p1", name: "Pro A", pipeline_type: "animated-explainer", params: null, created_at: null },
          { id: "p2", name: "Pro B", pipeline_type: "text-to-video", params: null, created_at: null },
        ],
        mutate: vi.fn(),
      };
    }
    return { data: null, mutate: vi.fn() };
  },
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    createProfile: vi.fn().mockResolvedValue({ id: "new", name: "New Profile", pipeline_type: "animated-explainer" }),
    deleteProfile: vi.fn().mockResolvedValue({ status: "deleted" }),
    listProfiles: vi.fn(),
  },
}));

import { apiClient } from "@/lib/api-client";

function renderList() {
  return render(
    <ToastProvider>
      <ProfileList />
    </ToastProvider>
  );
}

describe("ProfileList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders existing profiles", () => {
    renderList();
    expect(screen.getByText("Pro A")).toBeInTheDocument();
    expect(screen.getByText("Pro B")).toBeInTheDocument();
  });

  it("calls createProfile on form submit", async () => {
    const user = userEvent.setup();
    renderList();

    const input = screen.getByPlaceholderText("Profile name");
    await user.type(input, "New Profile");
    await user.click(screen.getByRole("button", { name: /save/i }));

    expect(apiClient.createProfile).toHaveBeenCalledWith({
      name: "New Profile",
      pipeline_type: "animated-explainer",
    });
  });

  it("calls deleteProfile on delete click", async () => {
    const user = userEvent.setup();
    renderList();

    const deleteButtons = screen.getAllByText("delete");
    await user.click(deleteButtons[0]);

    expect(apiClient.deleteProfile).toHaveBeenCalledWith("p1");
  });
});
