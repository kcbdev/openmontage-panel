"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/lib/toast";

export function MemberList() {
  const { user, token } = useAuth();
  const { data: members, mutate } = useSWR(
    token ? "members" : null,
    () => apiClient.getMembers(),
    { revalidateOnFocus: false }
  );
  const [email, setEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState("");
  const [tempPassword, setTempPassword] = useState("");
  const { addToast } = useToast();

  const isOwner = user?.role === "owner";

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setInviting(true);
    setInviteError("");
    setTempPassword("");
    try {
      const res = await apiClient.inviteMember(email);
      setTempPassword(res.temp_password);
      addToast("success", `Invite sent to ${email}`);
      setEmail("");
      mutate();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to invite";
      setInviteError(msg);
      addToast("error", msg);
    }
    setInviting(false);
  }

  async function handleRemove(memberId: string) {
    try {
      await apiClient.removeMember(memberId);
      addToast("success", "Member removed");
      mutate();
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Failed to remove member");
    }
  }

  return (
    <Card>
      <CardContent className="pt-4 space-y-4">
        <h2 className="text-sm font-medium text-gray-700">Team Members</h2>

        {members && members.length === 0 && (
          <p className="text-xs text-gray-400">No members.</p>
        )}

        {members && members.length > 0 && (
          <div className="space-y-2">
            {members.map((m) => (
              <div key={m.id} className="flex items-center justify-between py-1 border-b border-gray-100">
                <div className="flex items-center gap-2">
                  <span className="text-sm">{m.email}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                    m.role === "owner" ? "bg-purple-100 text-purple-700" : "bg-gray-100 text-gray-600"
                  }`}>
                    {m.role}
                  </span>
                </div>
                {isOwner && m.id !== user?.id && (
                  <button
                    onClick={() => handleRemove(m.id)}
                    className="text-xs text-red-500 hover:underline"
                  >
                    remove
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {isOwner && (
          <form onSubmit={handleInvite} className="space-y-2 pt-2 border-t border-gray-200">
            <div className="flex gap-2">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@example.com"
                className="h-7 flex-1 rounded border border-input px-2 text-xs"
                required
              />
              <button
                type="submit"
                disabled={inviting || !email}
                className="h-7 px-3 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {inviting ? "..." : "Invite"}
              </button>
            </div>
            {inviteError && <p className="text-xs text-red-500">{inviteError}</p>}
            {tempPassword && (
              <p className="text-xs text-green-600 break-all">
                Temp password: <code className="font-mono bg-green-50 px-1">{tempPassword}</code>
              </p>
            )}
          </form>
        )}
      </CardContent>
    </Card>
  );
}
