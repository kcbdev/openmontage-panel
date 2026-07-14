# Phase 4 — Studio Mode & Full Pipeline Rollout
### Detailed Implementation Guide

**Prerequisite:** Phase 3 acceptance tests pass (scoped regen + anomaly recovery).

---

## 4.1 Manifest-driven pipeline picker

The core claim to validate first: adding pipelines 2-12 should require **zero graph code changes**, only data.

```python
# api/routers/pipelines.py
import yaml
from pathlib import Path

PIPELINE_DEFS_DIR = Path("/engine-repo/pipeline_defs")

@router.get("/pipelines")
def list_pipelines():
    pipelines = []
    for f in PIPELINE_DEFS_DIR.glob("*.yaml"):
        manifest = yaml.safe_load(f.read_text())
        pipelines.append({
            "id": manifest["pipeline_id"],
            "name": manifest["display_name"],
            "description": manifest["description"],
            "best_for": manifest.get("best_for", ""),
            "stages": manifest["stages"],
        })
    return pipelines
```

This reads directly from the pinned engine image's own `pipeline_defs/` — mount it read-only into the API container at build time, or bake a copy into the API image tagged to match `PINNED_ENGINE_TAG`. No pipeline metadata is hand-maintained in Mission Control.

```tsx
// components/launch/PipelinePicker.tsx
export function PipelinePicker({ value, onChange }: PipelinePickerProps) {
  const { data: pipelines } = useSWR('/api/pipelines', fetcher);
  return (
    <div className="grid grid-cols-3 gap-3">
      {pipelines?.map((p: Pipeline) => (
        <button key={p.id} onClick={() => onChange(p.id)}
          className={`border rounded-lg p-3 text-left ${value === p.id ? 'border-blue-500' : ''}`}>
          <p className="font-medium">{p.name}</p>
          <p className="text-xs text-gray-500">{p.best_for}</p>
        </button>
      ))}
    </div>
  );
}
```

**Validation task:** launch one project per pipeline (all 12), confirm each completes through its gates using the *exact same* supervisor graph from Phase 1 — if any pipeline requires a graph-level special case, that's a signal the abstraction leaked somewhere and needs fixing before continuing.

---

## 4.2 Studio mode form

```tsx
// components/launch/StudioForm.tsx
export function StudioForm({ pipeline }: { pipeline: Pipeline }) {
  const { data: providerMenu } = useSWR('/api/providers/menu', fetcher); // mirrors registry.provider_menu()
  const [params, setParams] = useState<StudioParams>(defaultParamsFor(pipeline));

  return (
    <div className="space-y-4">
      <Field label="Render runtime">
        <RadioGroup value={params.render_runtime} onChange={v => setParams({...params, render_runtime: v})}
          options={['auto', 'remotion', 'hyperframes']} />
      </Field>
      <Field label="Footage mode">
        <RadioGroup value={params.footage_mode} onChange={v => setParams({...params, footage_mode: v})}
          options={['ai_generated', 'real_footage_only', 'hybrid']} />
      </Field>
      <Field label="Video generation provider">
        <ProviderSelect capability="video_gen" providers={providerMenu?.video_gen}
          value={params.providers.video_gen} onChange={v => setProvider('video_gen', v)} />
      </Field>
      <Field label="Narration provider">
        <ProviderSelect capability="tts" providers={providerMenu?.tts}
          value={params.providers.tts} onChange={v => setProvider('tts', v)} />
      </Field>
      <Field label="Music provider">
        <ProviderSelect capability="music" providers={providerMenu?.music}
          value={params.providers.music} onChange={v => setProvider('music', v)} />
      </Field>
      <Field label="Model routing per stage">
        <ModelRoutingConfig
          stages={["research", "proposal", "script", "scene_plan", "assets", "edit"]}
          defaults={{
            research: "anthropic/claude-3.5-haiku",
            proposal: "anthropic/claude-sonnet-4",
            script: "anthropic/claude-sonnet-4",
            scene_plan: "openai/gpt-4o",
            assets: "openai/gpt-4o",
            edit: "anthropic/claude-3.5-haiku",
          }}
          value={params.model_routing}
          onChange={v => setParams({...params, model_routing: v})}
        />
      </Field>
      <Field label="Style playbook">
        <StylePlaybookPicker value={params.style_playbook} onChange={v => setParams({...params, style_playbook: v})} />
      </Field>
      <Field label="Budget cap (this project)">
        <NumberInput value={params.budget_cap} onChange={v => setParams({...params, budget_cap: v})} />
      </Field>
    </div>
  );
}
```

```python
# api/routers/providers.py
@router.get("/providers/menu")
def provider_menu():
    """
    Mirrors registry.provider_menu() from the engine — call it once at
    engine image build time, cache the output as static JSON shipped
    with the API image, refresh on engine version upgrade.
    """
    return load_cached_provider_menu(PINNED_ENGINE_TAG)
```

`ProviderSelect` groups options exactly as `tools/` is grouped (video/audio/graphics/enhancement/analysis/avatar/subtitle) — this mirrors the mental model already established in the implementation guide, not an arbitrary new taxonomy.

---

## 4.3 Manual provider override in the supervisor graph

```python
# api/graph/nodes.py
def provision(state: SupervisorState) -> SupervisorState:
    env_overrides = {}
    if state.get("studio_params", {}).get("providers"):
        # written into the engine container's environment / task_context
        # so the Driver's tool calls pass these as forced selections
        # instead of letting the scorer auto-pick
        env_overrides["FORCED_PROVIDERS"] = json.dumps(state["studio_params"]["providers"])
    container_id = spawn_engine_container(
        pipeline_type=state["pipeline_type"], run_id=state["run_id"], env=env_overrides,
    )
    return {**state, "container_id": container_id, "status": "running"}
```

The Driver reads `FORCED_PROVIDERS` and passes it through as pre-selected `task_context` to the relevant tool calls — the scorer still runs (for the decision log's "alternatives considered" record) but its top pick is overridden by the forced value, which itself gets logged as a manual override rather than an auto-selection.

Alongside `FORCED_PROVIDERS`, the `provision()` node also writes `MODEL_ROUTING` (JSON map of `stage → model_name`) into the container environment. The Driver reads this at each stage entry and selects the model string for the OpenRouter chat completion call. If a stage is not present in the map, the built-in defaults from §2.5 of the architecture doc apply.

```python
if state.get("studio_params", {}).get("model_routing"):
    env_overrides["MODEL_ROUTING"] = json.dumps(state["studio_params"]["model_routing"])
```

---

## 4.4 Credential vault (Ground Systems)

```python
# api/models/core.py
class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))
    provider_key = Column(String)   # e.g. 'FAL_KEY', 'ELEVENLABS_API_KEY'
    encrypted_value = Column(String)
    last_verified_at = Column(DateTime, nullable=True)
```

```python
# api/routers/credentials.py
from cryptography.fernet import Fernet

@router.post("/credentials")
def upsert_credential(payload: CredentialUpsert):
    encrypted = fernet.encrypt(payload.value.encode())
    cred = ProviderCredential(tenant_id=current_tenant(), provider_key=payload.key, encrypted_value=encrypted)
    db.merge(cred); db.commit()
    return {"status": "saved"}

@router.post("/credentials/{key}/test")
def test_credential(key: str):
    value = decrypt_credential(current_tenant(), key)
    result = PROVIDER_TEST_FUNCTIONS[key](value)   # lightweight ping per provider
    if result.ok:
        db.query(ProviderCredential).filter_by(tenant_id=current_tenant(), provider_key=key)\
            .update({"last_verified_at": datetime.utcnow()})
        db.commit()
    return {"ok": result.ok, "message": result.message}
```

At `provision()` time, decrypt the tenant's credentials and inject them as the container's `.env` — this is a literal mapping onto the engine's existing `.env.example` structure, no new credential schema invented on the engine side.

---

## 4.5 Budget console

```python
# api/routers/budget.py
@router.put("/tenants/{tenant_id}/budget")
def update_budget_defaults(tenant_id: str, payload: BudgetDefaults):
    db.query(Tenant).filter_by(id=tenant_id).update({
        "budget_cap_default": payload.cap,
        "budget_mode_default": payload.mode,   # observe | warn | cap — matches engine's own modes verbatim
    })
    db.commit()
```

```tsx
// components/settings/BudgetConsole.tsx
export function BudgetConsole() {
  const { data, mutate } = useSWR('/api/tenant/budget', fetcher);
  return (
    <div className="space-y-4">
      <Field label="Default cap"><NumberInput value={data?.cap} onChange={...} prefix="$" /></Field>
      <Field label="Mode">
        <RadioGroup options={['observe', 'warn', 'cap']} value={data?.mode} onChange={...} />
      </Field>
      <Field label="Per-action approval threshold">
        <NumberInput value={data?.threshold} onChange={...} prefix="$" />
      </Field>
      <LiveLedgerTable tenantId={data?.tenant_id} />
    </div>
  );
}
```

---

## Phase 4 acceptance tests

1. **Manifest-driven claim:** launch one project per all 12 pipelines, zero graph-level special-casing required — flag and fix any exception.
2. **Manual override trace:** launch one project in Studio mode with every provider manually pinned; confirm the decision trail explicitly marks each as `manual_override` (not `auto_selected`) with the pinned value recorded.
3. **Credential vault:** add/test/remove a credential, confirm a subsequent run picks it up without restarting the API service.
4. **Budget enforcement:** set `mode=cap` at a low threshold, confirm a run that would exceed it pauses with a budget-gate decision rather than silently overspending.
