# Phase 5 — Multi-Tenancy & Team Roles
### Detailed Implementation Guide

**Prerequisite:** Phase 4 acceptance tests pass (all 12 pipelines, Studio mode, credentials, budget).

---

## 5.1 Auth

```python
# api/auth/session.py
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_jwt(token)
    user = db.query(User).get(payload["sub"])
    if not user:
        raise HTTPException(401)
    return user

def get_current_tenant(user: User = Depends(get_current_user)) -> Tenant:
    return db.query(Tenant).get(user.tenant_id)
```

Use a standard JWT session (access + refresh token) — no need for anything exotic; this is a self-hosted single-tenant-per-deploy-instance-by-default product (per the product doc's business model), so multi-tenancy here is primarily for **teams within one deployed instance**, not thousands of unrelated customers sharing one deploy.

```python
# api/models/core.py
class User(Base):
    __tablename__ = "users"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))
    email = Column(String, unique=True)
    hashed_password = Column(String)
    role = Column(String, default="editor")   # owner | editor | viewer
```

## 5.2 Row-level tenant scoping

Enforce at the query layer, not just the API layer — every model query goes through a scoped session helper:

```python
# api/db/scoped_session.py
def tenant_scoped_query(model, tenant: Tenant):
    return db.query(model).filter(model.tenant_id == tenant.id)

# usage in every router:
@router.get("/projects")
def list_projects(tenant: Tenant = Depends(get_current_tenant)):
    return tenant_scoped_query(Project, tenant).all()
```

For tables without a direct `tenant_id` (e.g. `stage_checkpoints`, keyed via `run_id → project_id → tenant_id`), scope via a join, not a second denormalized tenant column, to avoid drift:

```python
def tenant_scoped_checkpoints(run_id: str, tenant: Tenant):
    return db.query(StageCheckpoint).join(Run).join(Project)\
        .filter(Project.tenant_id == tenant.id, Run.id == run_id).all()
```

## 5.3 Role-gated approval

```python
# api/models/core.py — extend Tenant
class Tenant(Base):
    ...
    gate_role_requirements = Column(JSON, default=lambda: {"publish": "owner"})
```

```python
# api/routers/runs.py
@router.post("/{run_id}/resume")
def resume_run(run_id: str, decision: GateDecision, user: User = Depends(get_current_user)):
    gate = get_pending_gate(run_id)
    tenant = get_tenant_for_run(run_id)
    required_role = tenant.gate_role_requirements.get(gate.gate_type)
    if required_role and not role_satisfies(user.role, required_role):
        raise HTTPException(403, f"This gate requires {required_role} approval")
    write_gate_response(gate.id, decision.dict())
    gate.resolved_by = user.id
    db.commit()
    supervisor_graphs[run_id].resume_from_interrupt()
    return {"status": "resumed"}

ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}
def role_satisfies(user_role: str, required_role: str) -> bool:
    return ROLE_RANK[user_role] >= ROLE_RANK[required_role]
```

```tsx
// components/deck/GateActionBar.tsx — extend from Phase 2
export function GateActionBar({ runId, gate, currentUserRole }: Props) {
  const canApprove = roleSatisfies(currentUserRole, gate.required_role);
  if (!canApprove) {
    return <p className="text-sm text-gray-500">Waiting on {gate.required_role} approval — {gate.assigned_to_label}</p>;
  }
  return <StandardGateActions runId={runId} gate={gate} />;
}
```

## 5.4 Team management UI

```tsx
// app/settings/team/page.tsx
export default function TeamSettings() {
  const { data: users, mutate } = useSWR('/api/team', fetcher);
  async function invite(email: string, role: string) {
    await apiClient.inviteUser({ email, role });
    mutate();
  }
  return (
    <div>
      <InviteForm onInvite={invite} />
      <table>
        <tbody>
          {users?.map((u: User) => (
            <tr key={u.id}>
              <td>{u.email}</td>
              <td><RoleSelect value={u.role} onChange={r => apiClient.updateUserRole(u.id, r)} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 5.5 Per-tenant storage isolation audit

```python
# api/storage/paths.py
def asset_storage_path(tenant_id: str, project_id: str, run_id: str, stage: str, filename: str) -> str:
    return f"tenant-{tenant_id}/project-{project_id}/run-{run_id}/{stage}/{filename}"

# CRITICAL: every write to MinIO must go through this function — no
# direct bucket writes elsewhere in the codebase. Add a lint/CI check
# that greps for raw minio_client.put_object calls outside storage/paths.py.
```

**Audit task:** write a test that creates two tenants, launches a project on each, and asserts that tenant A's API token cannot list or fetch any object under `tenant-{B}/` via any endpoint — including the asset-serving proxy, not just the DB-backed list endpoints.

## 5.6 Concurrent-run governance

```python
# api/graph/nodes.py
def provision(state: SupervisorState) -> SupervisorState:
    tenant = get_tenant(state["project_id"])
    active_count = count_active_runs(tenant.id)
    if active_count >= tenant.max_concurrent_runs:
        enqueue_run(state["run_id"])
        return {**state, "status": "queued"}
    container_id = spawn_engine_container(...)
    return {**state, "container_id": container_id, "status": "running"}
```

```tsx
// components/fleet/ProjectCard.tsx — extend from Phase 2
{project.status === 'queued' && (
  <span className="text-xs text-gray-500">Queued — position {project.queue_position}</span>
)}
```

---

## Phase 5 acceptance tests

1. **Isolation:** two tenants, simultaneous runs, automated test confirms zero cross-tenant data access at API and storage layers.
2. **Role gating:** editor launches and drives a project through script/scene_plan/assets gates; publish gate correctly blocks the editor and requires an owner login to approve; decision log records `resolved_by` correctly for both users.
3. **Concurrency cap:** set `max_concurrent_runs=1`, launch two projects back to back, confirm the second queues and later launches automatically once the first archives.
