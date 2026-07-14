# Phase 3 — Scene-Level Control & Anomaly Recovery
### Detailed Implementation Guide

**Prerequisite:** Phase 2 acceptance test passes with a real test subject.

---

## 3.1 Scoped regeneration — data model changes

Already present in the schema (`assets.is_locked`) — this phase wires it end to end.

```python
# api/models/core.py — no new tables, just use the existing flag
# Asset.is_locked already defined in Phase 1
```

## 3.2 Storyboard UI — lock & regenerate

```tsx
// components/deck/SceneCard.tsx
export function SceneCard({ scene, runId }: { scene: SceneAsset; runId: string }) {
  const [locked, setLocked] = useState(scene.is_locked);
  const [providerOverride, setProviderOverride] = useState<string | null>(null);

  return (
    <div className="border rounded-lg p-2 space-y-2">
      <img src={scene.thumbnail_url} className="w-full aspect-video object-cover rounded" />
      <div className="flex justify-between text-xs text-gray-500">
        <span>${scene.cost.toFixed(2)}</span>
        <span>{scene.provider_used}</span>
      </div>
      <div className="flex gap-1">
        <button
          onClick={() => { setLocked(!locked); apiClient.setAssetLock(scene.id, !locked); }}
          className={`text-xs px-2 py-1 rounded ${locked ? 'bg-blue-100' : 'bg-gray-100'}`}
        >
          {locked ? '🔒 Locked' : 'Lock'}
        </button>
        {!locked && (
          <ProviderQuickSelect
            capability="video_gen"
            value={providerOverride}
            onChange={setProviderOverride}
          />
        )}
      </div>
    </div>
  );
}
```

```tsx
// components/deck/StoryboardGrid.tsx
export function StoryboardGrid({ scenes, runId }: { scenes: SceneAsset[]; runId: string }) {
  async function regenerateUnlocked() {
    const locked = scenes.filter(s => s.is_locked).map(s => s.id);
    const regenerate = scenes.filter(s => !s.is_locked).map(s => ({
      id: s.id,
      provider_override: s.provider_override ?? null,
    }));
    await apiClient.resumeRun(runId, {
      decision: 'revise',
      scope: { locked_scene_ids: locked, regenerate_scene_ids: regenerate },
    });
  }
  return (
    <div>
      <div className="grid grid-cols-4 gap-3">
        {scenes.map(s => <SceneCard key={s.id} scene={s} runId={runId} />)}
      </div>
      <div className="flex gap-3 mt-4">
        <button onClick={regenerateUnlocked} className="btn-secondary">Regenerate unlocked scenes</button>
        <button onClick={() => apiClient.resumeRun(runId, { decision: 'approve' })} className="btn-primary">
          Approve storyboard
        </button>
      </div>
    </div>
  );
}
```

## 3.3 Backend — scoped resume payload

```python
# api/routers/runs.py
class GateDecision(BaseModel):
    decision: Literal["approve", "revise", "reject"]
    revision_notes: Optional[str] = None
    scope: Optional[SceneScope] = None   # new in Phase 3

class SceneScope(BaseModel):
    locked_scene_ids: list[str]
    regenerate_scene_ids: list[SceneOverride]

class SceneOverride(BaseModel):
    id: str
    provider_override: Optional[str] = None

@router.post("/{run_id}/resume")
def resume_run(run_id: str, decision: GateDecision):
    gate = get_pending_gate(run_id)
    payload = decision.dict()
    if decision.scope:
        # this is the richer pending_decision.json contract from the
        # implementation guide §5 — written verbatim for the Driver to read
        payload["scope"] = decision.scope.dict()
    write_gate_response(gate.id, payload)
    supervisor_graphs[run_id].resume_from_interrupt()
    return {"status": "resumed"}
```

The Driver-side contract (inside the engine container, from the Phase 0 spike, now hardened):
```python
# engine/driver/resume_handler.py — lives alongside the Driver, not in the engine repo itself
def handle_scoped_resume(decision_response: dict, stage_context: dict):
    if "scope" not in decision_response:
        return standard_resume(decision_response)
    locked = set(decision_response["scope"]["locked_scene_ids"])
    for scene in decision_response["scope"]["regenerate_scene_ids"]:
        override = scene.get("provider_override")
        # calls the same tool (e.g. tools/video/*) the engine would call
        # normally at this stage, scoped to one scene_id, with an optional
        # provider override passed through task_context
        regenerate_scene(scene["id"], provider_override=override)
    # locked scenes are skipped entirely — no tool call, no cost incurred
```

---

## 3.4 Anomaly detection

```python
# api/graph/nodes.py
def await_checkpoint(state: SupervisorState) -> SupervisorState:
    try:
        event = wait_for_next_event(state["container_id"], timeout=600)
    except TimeoutError:
        return {**state, "status": "anomaly", "anomaly_reason": "Generation stalled — no progress in 10 minutes"}
    except ContainerCrashError as e:
        return {**state, "status": "anomaly", "anomaly_reason": f"Engine process crashed: {e.summary}"}
    except ProviderAPIError as e:
        return {**state, "status": "anomaly", "anomaly_reason": f"{e.provider} timed out on {e.stage}"}
    ...
```

```python
# api/models/core.py — extend Run
class Run(Base):
    ...
    anomaly_reason = Column(String, nullable=True)
    last_good_checkpoint_id = Column(UUID, nullable=True)
```

## 3.5 Recovery actions UI

```tsx
// components/deck/AnomalyPanel.tsx
export function AnomalyPanel({ run }: { run: Run }) {
  return (
    <div className="border border-red-200 bg-red-50 rounded-lg p-4 space-y-3">
      <p className="font-medium text-red-700">Something went wrong</p>
      <p className="text-sm text-gray-600">{run.anomaly_reason}</p>
      <div className="flex gap-2">
        <button onClick={() => apiClient.retryRun(run.id, { same_provider: true })} className="btn-secondary">
          Retry
        </button>
        <button onClick={() => apiClient.retryRun(run.id, { same_provider: false })} className="btn-secondary">
          Retry with different provider
        </button>
        <button onClick={() => apiClient.rollbackRun(run.id, run.last_good_checkpoint_id)} className="btn-ghost">
          Roll back to last checkpoint
        </button>
      </div>
    </div>
  );
}
```

```python
# api/routers/runs.py
@router.post("/{run_id}/retry")
def retry_run(run_id: str, opts: RetryOptions):
    run = get_run(run_id)
    next_provider = None
    if not opts.same_provider:
        next_provider = get_next_best_scored_provider(run, exclude=run.last_failed_provider)
    resume_from_checkpoint(run.last_good_checkpoint_id, provider_override=next_provider)
    log_decision(run_id, decision_type="failure_recovery", chosen=next_provider or "retry_same",
                 reasoning=f"Recovered from: {run.anomaly_reason}")
    return {"status": "retrying"}
```

`get_next_best_scored_provider` reads the same `registry.support_envelope()` output already used for initial selection — no new scoring logic, just excludes the failed provider and re-ranks.

---

## 3.6 Decision trail panel (live)

```tsx
// components/deck/DecisionTrailPanel.tsx
export function DecisionTrailPanel({ runId }: { runId: string }) {
  const events = useRunStream(runId)?.decision_log ?? [];
  return (
    <div className="space-y-2 text-sm">
      {events.map(e => (
        <div key={e.id} className="flex items-start gap-2">
          <span>✓</span>
          <div>
            <p>{e.decision_type}: <strong>{e.chosen}</strong></p>
            <p className="text-xs text-gray-500">{e.reasoning}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
```

---

## Phase 3 acceptance tests

**Scoped regeneration:**
1. Launch a project, reach the `assets` gate with 6+ scenes.
2. Lock 4 scenes, regenerate 2 with a manually chosen provider override on one.
3. Confirm only the 2 unlocked scenes incur new cost in `budget_ledger`, and the 4 locked scenes' `storage_path` is unchanged.

**Anomaly recovery:**
1. Deliberately invalidate a provider API key mid-run (e.g. corrupt the credential before a generation call).
2. Confirm `runs.status` flips to `anomaly` with a legible `anomaly_reason`, not a raw exception.
3. Click "Retry with different provider," confirm the run resumes from the last good checkpoint and completes using the fallback provider.
4. Confirm the recovery action is visible in the decision trail afterward.
