"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/lib/toast";

export function ProfileList() {
  const { token } = useAuth();
  const { data: profiles, mutate } = useSWR(
    token ? "profiles" : null,
    () => apiClient.listProfiles(),
  );
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const { addToast } = useToast();

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name) return;
    setSaving(true);
    try {
      await apiClient.createProfile({ name, pipeline_type: "animated-explainer" });
      addToast("success", `Profile "${name}" created`);
      setName("");
      mutate();
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Failed to create profile");
    }
    setSaving(false);
  }

  async function handleDelete(id: string, profileName: string) {
    try {
      await apiClient.deleteProfile(id);
      addToast("success", `Profile "${profileName}" deleted`);
      mutate();
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Failed to delete profile");
    }
  }

  return (
    <Card>
      <CardContent className="pt-4 space-y-4">
        <h2 className="text-sm font-medium text-gray-700">Mission Profiles</h2>

        {profiles && profiles.length === 0 && (
          <p className="text-xs text-gray-400">No profiles saved.</p>
        )}

        {profiles && profiles.length > 0 && (
          <div className="space-y-2">
            {profiles.map((p) => (
              <div key={p.id} className="flex items-center justify-between py-1 border-b border-gray-100">
                <div>
                  <span className="text-sm">{p.name}</span>
                  <span className="ml-2 text-xs text-gray-400">{p.pipeline_type}</span>
                </div>
                  <button
                    onClick={() => handleDelete(p.id, p.name)}
                    className="text-xs text-red-500 hover:underline"
                  >
                    delete
                  </button>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleCreate} className="flex gap-2 pt-2 border-t border-gray-200">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Profile name"
            className="h-7 flex-1 rounded border border-input px-2 text-xs"
            required
          />
          <button
            type="submit"
            disabled={saving || !name}
            className="h-7 px-3 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50"
          >
            Save
          </button>
        </form>
      </CardContent>
    </Card>
  );
}
