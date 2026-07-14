"use client";

import { useState, useEffect } from "react";
import useSWR from "swr";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/lib/toast";
import type { LedgerEntry, BudgetSummary } from "@/lib/types";

function fmt(n: number | null | undefined) {
  if (n == null) return "-";
  return `$${n.toFixed(2)}`;
}

function shortId(id: string) {
  return id.slice(0, 8);
}

function SummaryBar({ summary }: { summary: BudgetSummary }) {
  const used = summary.total_spent + summary.total_reserved;
  const pct = summary.cap > 0 ? Math.min((used / summary.cap) * 100, 100) : 0;
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-gray-600">
        <span>
          Used: {fmt(used)} / Cap: {fmt(summary.cap)}
        </span>
        <span>{summary.remaining >= 0 ? `${fmt(summary.remaining)} remaining` : `${fmt(Math.abs(summary.remaining))} over cap`}</span>
      </div>
      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${pct > 90 ? "bg-red-500" : pct > 70 ? "bg-amber-500" : "bg-blue-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function LedgerRow({ e }: { e: LedgerEntry }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-2 min-w-0">
        <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${e.action === "reconcile" ? "bg-green-100 text-green-700" : e.action === "reserve" ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600"}`}>
          {e.action}
        </span>
        <span className="text-xs font-mono text-gray-400">{shortId(e.run_id)}</span>
        {e.created_at && (
          <span className="text-xs text-gray-400">
            {new Date(e.created_at).toLocaleDateString()}
          </span>
        )}
      </div>
      <span className="text-xs font-mono tabular-nums">
        {fmt(e.actual_cost ?? e.estimated_cost)}
      </span>
    </div>
  );
}

export function BudgetConsole() {
  const { token } = useAuth();
  const { data: budget, mutate } = useSWR(token ? "budget" : null, () => apiClient.getBudget(), {
    revalidateOnFocus: false,
  });
  const { data: summary } = useSWR(token ? "budget-summary" : null, () => apiClient.getBudgetSummary());
  const { data: ledger, mutate: mutateLedger } = useSWR(token ? "budget-ledger" : null, () => apiClient.getLedger(0, 25));
  const [cap, setCap] = useState(10);
  const [mode, setMode] = useState("warn");
  const [saving, setSaving] = useState(false);
  const [ledgerOffset, setLedgerOffset] = useState(0);
  const { addToast } = useToast();

  useEffect(() => {
    if (budget) {
      setCap(budget.cap);
      setMode(budget.mode);
    }
  }, [budget]);

  async function handleSave() {
    setSaving(true);
    try {
      await apiClient.updateBudget({ cap, mode });
      addToast("success", "Budget defaults saved");
      mutate();
    } catch (e) {
      addToast("error", e instanceof Error ? e.message : "Failed to save budget");
    }
    setSaving(false);
  }

  async function loadMore() {
    const next = ledgerOffset + 25;
    const more = await apiClient.getLedger(next, 25);
    if (more.entries.length > 0 && ledger) {
      mutateLedger({ ...ledger, entries: [...ledger.entries, ...more.entries] }, { revalidate: false });
    }
    setLedgerOffset(next);
  }

  const modeClass = (m: string) =>
    `flex-1 border rounded-lg p-2 text-center text-xs transition-colors ${
      mode === m
        ? "border-blue-500 bg-blue-50 text-blue-700"
        : "border-gray-200 bg-white text-gray-600 hover:border-gray-300"
    }`;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">Budget Defaults</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {summary && <SummaryBar summary={summary} />}

          <div className="space-y-1">
            <label className="block text-xs font-medium text-gray-600">Default cap</label>
            <div className="relative">
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-sm text-gray-400">$</span>
              <input
                type="number"
                min={0}
                step={0.5}
                value={cap}
                onChange={(e) => setCap(parseFloat(e.target.value) || 0)}
                className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent pl-6 pr-2.5 py-1 text-sm"
              />
            </div>
          </div>

          <div className="space-y-1">
            <label className="block text-xs font-medium text-gray-600">Mode</label>
            <div className="flex gap-2">
              {["observe", "warn", "cap"].map((m) => (
                <button key={m} onClick={() => setMode(m)} className={modeClass(m)}>
                  {m}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleSave}
            disabled={saving}
            className="h-7 px-3 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </CardContent>
      </Card>

      {summary && summary.projects.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-gray-700">Spend by Project</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {summary.projects.map((p) => {
              const pct = summary.cap > 0 ? (p.spent / summary.cap) * 100 : 0;
              return (
                <div key={p.project_id}>
                  <div className="flex items-center justify-between text-xs mb-0.5">
                    <span className="font-medium truncate">{p.name}</span>
                    <span className="tabular-nums">{fmt(p.spent)}</span>
                  </div>
                  <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                    <div className="h-full bg-blue-400 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">Ledger</CardTitle>
        </CardHeader>
        <CardContent>
          {!ledger || ledger.entries.length === 0 ? (
            <p className="text-xs text-gray-400">No ledger entries yet.</p>
          ) : (
            <div className="space-y-0">
              {ledger.entries.map((e) => (
                <LedgerRow key={e.id} e={e} />
              ))}
            </div>
          )}
          {ledger && ledger.total > ledger.entries.length && (
            <button
              onClick={loadMore}
              className="mt-3 text-xs text-blue-600 hover:underline"
            >
              Load more ({ledger.entries.length} of {ledger.total})
            </button>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
