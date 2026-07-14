import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemberList } from "../MemberList";
import { ToastProvider } from "@/lib/toast";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    token: "mock-token",
    user: { id: "u1", role: "owner" },
  }),
}));

vi.mock("swr", () => ({
  default: (key: string) => {
    if (key === "members") {
      return {
        data: [
          { id: "u1", email: "admin@test.com", role: "owner", invited_by: null, created_at: null },
          { id: "u2", email: "editor@test.com", role: "editor", invited_by: "u1", created_at: null },
        ],
        mutate: vi.fn(),
      };
    }
    return { data: null, mutate: vi.fn() };
  },
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    inviteMember: vi.fn().mockResolvedValue({ id: "u3", email: "new@test.com", role: "editor", temp_password: "abc123" }),
    removeMember: vi.fn().mockResolvedValue({ status: "removed" }),
    getMembers: vi.fn(),
    login: vi.fn(),
  },
}));

import { apiClient } from "@/lib/api-client";

function renderList() {
  return render(
    <ToastProvider>
      <MemberList />
    </ToastProvider>
  );
}

describe("MemberList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders members with roles", () => {
    renderList();
    expect(screen.getByText("admin@test.com")).toBeInTheDocument();
    expect(screen.getByText("editor@test.com")).toBeInTheDocument();
  });

  it("shows owner badge for owner role", () => {
    renderList();
    expect(screen.getByText("owner").closest("span")).toBeInTheDocument();
  });

  it("calls inviteMember on invite form submit", async () => {
    const user = userEvent.setup();
    renderList();

    const input = screen.getByPlaceholderText("email@example.com");
    await user.type(input, "new@test.com");
    await user.click(screen.getByRole("button", { name: /invite/i }));

    expect(apiClient.inviteMember).toHaveBeenCalledWith("new@test.com");
  });

  it("shows temp password after invite", async () => {
    const user = userEvent.setup();
    renderList();

    const input = screen.getByPlaceholderText("email@example.com");
    await user.type(input, "new@test.com");
    await user.click(screen.getByRole("button", { name: /invite/i }));

    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it("calls removeMember on remove click", async () => {
    const user = userEvent.setup();
    renderList();

    const removeButtons = screen.getAllByText("remove");
    await user.click(removeButtons[0]);

    expect(apiClient.removeMember).toHaveBeenCalledWith("u2");
  });

  it("does not show remove button for current user", () => {
    renderList();
    expect(screen.getAllByText("remove")).toHaveLength(1);
  });
});
