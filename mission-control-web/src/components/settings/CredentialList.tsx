"use client";

import { useState } from "react";
import useSWR from "swr";
import { Card, CardContent } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/lib/toast";

export function CredentialList() {
  const { token } = useAuth();
  const { data: creds, mutate, error } = useSWR(
    token ? "credentials" : null,
    () => apiClient.getCredentials(),
    { revalidateOnFocus: false }
  );
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [saving, setSaving] = useState(false);
  const { addToast } = useToast();

  async function addCredential() {
    if (!newKey || !newValue) return;
    setSaving(true);
    try {
      await apiClient.upsertCredential(newKey, newValue);
      addToast("success", `Credential "${newKey}" saved`);
      setNewKey("");
      setNewValue("");
      mutate();
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Failed to save credential");
    }
    setSaving(false);
  }

  async function testCredential(key: string) {
    try {
      await apiClient.testCredential(key);
      addToast("success", `Credential "${key}" verified`);
      mutate();
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Credential test failed");
    }
  }

  async function deleteCredential(key: string) {
    try {
      await apiClient.deleteCredential(key);
      addToast("success", `Credential "${key}" deleted`);
      mutate();
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Failed to delete credential");
    }
  }

  return (
    <Card>
      <CardContent className="pt-4 space-y-4">
        <h2 className="text-sm font-medium text-gray-700">Provider Credentials</h2>

        {error && <p className="text-xs text-red-500">Failed to load credentials</p>}

        {creds && creds.length === 0 && (
          <p className="text-xs text-gray-400">No credentials stored.</p>
        )}

        {creds && creds.length > 0 && (
          <div className="space-y-2">
            {creds.map((c) => (
              <div key={c.key} className="flex items-center justify-between py-1 border-b border-gray-100">
                <div>
                  <span className="text-sm font-mono">{c.key}</span>
                  {c.last_verified_at && (
                    <span className="ml-2 text-xs text-green-600">verified</span>
                  )}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => testCredential(c.key)}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    test
                  </button>
                  <button
                    onClick={() => deleteCredential(c.key)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex gap-2 pt-2 border-t border-gray-200">
          <input
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="e.g. FAL_KEY"
            className="h-7 flex-1 rounded border border-input px-2 text-xs"
          />
          <input
            type="password"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="value"
            className="h-7 flex-1 rounded border border-input px-2 text-xs"
          />
          <button
            onClick={addCredential}
            disabled={!newKey || !newValue || saving}
            className="h-7 px-3 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </CardContent>
    </Card>
  );
}
