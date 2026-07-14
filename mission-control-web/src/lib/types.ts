export type ProjectStatus =
  | "draft"
  | "provisioning"
  | "awaiting_checkpoint"
  | "awaiting_approval"
  | "anomaly"
  | "done";

export type PipelineType = string;

export interface Project {
  id: string;
  name: string;
  pipeline_type: PipelineType;
  status: ProjectStatus;
  render_runtime: string | null;
  style_playbook: string | null;
  platform_profile: string | null;
  duration_target_seconds: number | null;
  run_id: string | null;
  created_at: string | null;
}

export interface Run {
  id: string;
  project_id: string;
  engine_container_id: string | null;
  engine_version: string;
  status: string;
  current_stage: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface StageCheckpoint {
  id: string;
  stage: string;
  checkpoint: Record<string, unknown>;
  decision_log: Record<string, unknown> | null;
  created_at: string | null;
}

export interface ApprovalGate {
  id: string;
  stage: string;
  gate_type: string;
  payload: Record<string, unknown> | null;
  required_role?: string | null;
  created_at: string | null;
}

export interface SceneArtifact {
  id: string;
  scene_number: number;
  stage: string;
  thumbnail_url: string;
  cost: number;
  provider_used: string;
  is_locked: boolean;
}

export interface AuthUser {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
}

export interface AssetData {
  id: string;
  run_id: string;
  stage: string;
  type: string;
  storage_path: string | null;
  provider_used: string | null;
  cost: number | null;
  is_locked: boolean;
  created_at: string | null;
  scene_number: number | null;
  thumbnail_url: string | null;
}

export interface LedgerEntry {
  id: string;
  project_id: string;
  run_id: string;
  action: string;
  estimated_cost: number | null;
  actual_cost: number | null;
  mode: string;
  created_at: string | null;
}

export interface BudgetSummary {
  cap: number;
  total_spent: number;
  total_reserved: number;
  remaining: number;
  projects: {
    project_id: string;
    name: string;
    spent: number;
    reserved: number;
    entries_count: number;
  }[];
}

export interface BoardState {
  status: string;
  current_stage: string | null;
  next_stage: string | null;
  next_needs_approval: boolean;
  completed: { stage: string; status: string; cost: number }[];
}

export interface RunState {
  run_id: string;
  status: string;
  current_stage: string | null;
  anomaly_reason: string | null;
  last_checkpoint: {
    stage: string;
    checkpoint: Record<string, unknown>;
    cost_snapshot: Record<string, unknown> | null;
  } | null;
  board_state: BoardState;
}
