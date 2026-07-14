import type { Project, StageCheckpoint, ApprovalGate, RunState, AssetData, AuthUser, LedgerEntry, BudgetSummary } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "/api";

let _token: string | null = null;

export function setAuthToken(token: string | null) {
  _token = token;
}

export function getAuthToken(): string | null {
  return _token;
}

function headers(): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (_token) h["Authorization"] = `Bearer ${_token}`;
  return h;
}

interface CreateResult {
  project_id: string;
  run_id: string;
  status: string;
}

interface ResumeResult {
  run_id: string;
  status: string;
  decision: string;
}

async function getJSON(path: string): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`, { headers: headers() });
  if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
  return res.json();
}

async function postJSON(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
  return res.json();
}

async function putJSON(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PUT ${path}: ${res.status}`);
  return res.json();
}

async function del(path: string): Promise<unknown> {
  const res = await fetch(`${BASE}${path}`, {
    method: "DELETE",
    headers: headers(),
  });
  if (!res.ok) throw new Error(`DELETE ${path}: ${res.status}`);
  return res.json();
}

interface EstimateResult {
  estimated_cost: number;
  currency: string;
  pipeline_type: string;
}

export const apiClient = {
  // Auth
  login(email: string, password: string): Promise<{ access_token: string; token_type: string; user: AuthUser }> {
    return postJSON("/auth/login", { email, password }) as Promise<{ access_token: string; token_type: string; user: AuthUser }>;
  },

  register(email: string, password: string): Promise<{ access_token: string; token_type: string; user: AuthUser }> {
    return postJSON("/auth/register", { email, password }) as Promise<{ access_token: string; token_type: string; user: AuthUser }>;
  },

  getMe(): Promise<AuthUser> {
    return getJSON("/auth/me") as Promise<AuthUser>;
  },

  // Tenant
  getTenant(): Promise<{ id: string; name: string }> {
    return getJSON("/tenant") as Promise<{ id: string; name: string }>;
  },

  getMembers(): Promise<{ id: string; email: string; role: string; invited_by: string | null; created_at: string | null }[]> {
    return getJSON("/tenant/members") as Promise<{ id: string; email: string; role: string; invited_by: string | null; created_at: string | null }[]>;
  },

  inviteMember(email: string): Promise<{ id: string; email: string; role: string; temp_password: string }> {
    return postJSON("/tenant/invite", { email }) as Promise<{ id: string; email: string; role: string; temp_password: string }>;
  },

  removeMember(memberId: string): Promise<{ status: string }> {
    return del(`/tenant/members/${memberId}`) as Promise<{ status: string }>;
  },

  // Budget
  getBudget(): Promise<{ tenant_id: string; cap: number; mode: string }> {
    return getJSON("/tenant/budget") as Promise<{ tenant_id: string; cap: number; mode: string }>;
  },

  updateBudget(body: { cap: number; mode: string }): Promise<{ status: string }> {
    return putJSON("/tenant/budget", body) as Promise<{ status: string }>;
  },

  getLedger(offset = 0, limit = 25): Promise<{ total: number; offset: number; limit: number; entries: LedgerEntry[] }> {
    return getJSON(`/tenant/budget/ledger?offset=${offset}&limit=${limit}`) as Promise<{ total: number; offset: number; limit: number; entries: LedgerEntry[] }>;
  },

  getBudgetSummary(): Promise<BudgetSummary> {
    return getJSON("/tenant/budget/summary") as Promise<BudgetSummary>;
  },

  syncLedger(entries: { project_id: string; run_id: string; action: string; estimated_cost?: number; actual_cost?: number; mode?: string }[]): Promise<{ status: string; count: number }> {
    return postJSON("/tenant/budget/ledger/sync", entries) as Promise<{ status: string; count: number }>;
  },

  // Credentials
  getCredentials(): Promise<{ key: string; last_verified_at: string | null }[]> {
    return getJSON("/credentials") as Promise<{ key: string; last_verified_at: string | null }[]>;
  },

  upsertCredential(key: string, value: string): Promise<{ status: string }> {
    return postJSON("/credentials", { key, value }) as Promise<{ status: string }>;
  },

  testCredential(key: string): Promise<{ ok: boolean; message: string }> {
    return postJSON(`/credentials/${key}/test`, {}) as Promise<{ ok: boolean; message: string }>;
  },

  deleteCredential(key: string): Promise<{ status: string }> {
    return del(`/credentials/${key}`) as Promise<{ status: string }>;
  },

  // Projects
  getProjects(): Promise<Project[]> {
    return getJSON("/projects") as Promise<Project[]>;
  },

  getProject(id: string): Promise<Project> {
    return getJSON(`/projects/${id}`) as Promise<Project>;
  },

  createProject(body: {
    name: string;
    pipeline_type?: string;
    duration_target_seconds?: number;
    studio_params?: Record<string, unknown>;
  }): Promise<CreateResult> {
    return postJSON("/projects", body) as Promise<CreateResult>;
  },

  resumeRun(
    runId: string,
    body: { decision: string; revision_notes?: string; scope?: unknown }
  ): Promise<ResumeResult> {
    return postJSON(`/runs/${runId}/resume`, body) as Promise<ResumeResult>;
  },

  getAssets(runId: string): Promise<AssetData[]> {
    return getJSON(`/runs/${runId}/assets`) as Promise<AssetData[]>;
  },

  toggleAssetLock(runId: string, assetId: string): Promise<{ id: string; is_locked: boolean }> {
    return postJSON(`/runs/${runId}/assets/${assetId}/lock`, {}) as Promise<{ id: string; is_locked: boolean }>;
  },

  retryRun(runId: string, body: { provider_override?: string; rollback_to_checkpoint_id?: string }): Promise<ResumeResult> {
    return postJSON(`/runs/${runId}/retry`, body) as Promise<ResumeResult>;
  },

  getCheckpoints(runId: string): Promise<StageCheckpoint[]> {
    return getJSON(`/runs/${runId}/checkpoints`) as Promise<StageCheckpoint[]>;
  },

  getRunState(runId: string): Promise<RunState> {
    return getJSON(`/runs/${runId}/state`) as Promise<RunState>;
  },

  getPendingGates(runId: string): Promise<ApprovalGate[]> {
    return getJSON(`/runs/${runId}/gates/pending`) as Promise<ApprovalGate[]>;
  },

  estimateProject(body: {
    brief: string;
    duration?: number;
    pipeline_type?: string;
    cost_tier?: string;
  }): Promise<EstimateResult> {
    return postJSON("/projects/estimate", body) as Promise<EstimateResult>;
  },

  // Pipelines & providers
  getPipelines(): Promise<unknown[]> {
    return getJSON("/pipelines") as Promise<unknown[]>;
  },

  getProviderMenu(): Promise<Record<string, unknown>> {
    return getJSON("/providers/menu") as Promise<Record<string, unknown>>;
  },

  // Archive & remix
  getProjectAssets(projectId: string, stage?: string, type?: string): Promise<AssetData[]> {
    const params = new URLSearchParams();
    if (stage) params.set("stage", stage);
    if (type) params.set("type", type);
    const qs = params.toString();
    return getJSON(`/projects/${projectId}/assets${qs ? "?" + qs : ""}`) as Promise<AssetData[]>;
  },

  downloadProject(projectId: string): Promise<unknown> {
    return getJSON(`/projects/${projectId}/download`) as Promise<unknown>;
  },

  remixProject(projectId: string, body: { name: string; pipeline_type?: string; duration_target_seconds?: number; studio_params?: Record<string, unknown> }): Promise<{ project_id: string; status: string }> {
    return postJSON(`/projects/${projectId}/remix`, body) as Promise<{ project_id: string; status: string }>;
  },

  // Mission profiles
  listProfiles(): Promise<{ id: string; name: string; pipeline_type: string; params: unknown; created_at: string | null }[]> {
    return getJSON("/mission-profiles") as Promise<{ id: string; name: string; pipeline_type: string; params: unknown; created_at: string | null }[]>;
  },

  createProfile(body: { name: string; pipeline_type?: string; params?: unknown }): Promise<{ id: string; name: string; pipeline_type: string }> {
    return postJSON("/mission-profiles", body) as Promise<{ id: string; name: string; pipeline_type: string }>;
  },

  deleteProfile(profileId: string): Promise<{ status: string }> {
    return del(`/mission-profiles/${profileId}`) as Promise<{ status: string }>;
  },

  cloneStyle(body: { name: string; source_playbook_id: string; yaml_content?: string }): Promise<{ id: string; name: string; source_playbook_id: string }> {
    return postJSON("/styles/clone", body) as Promise<{ id: string; name: string; source_playbook_id: string }>;
  },
};
