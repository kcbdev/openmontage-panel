# Phase 2 — Mission Control MVP UI (Single Pipeline)
### Detailed Implementation Guide

**Prerequisite:** Phase 1 acceptance test passes via curl.

---

## 2.1 Frontend structure

```
mission-control-web/
├── app/
│   ├── projects/
│   │   ├── page.tsx              # Fleet View
│   │   ├── new/page.tsx          # Launch Console (Guided)
│   │   └── [id]/run/[runId]/page.tsx  # Command Deck
│   ├── layout.tsx
│   └── api/                      # Next.js route handlers proxying to FastAPI
├── components/
│   ├── fleet/
│   │   ├── ProjectCard.tsx
│   │   ├── StatusLight.tsx
│   │   └── FilterBar.tsx
│   ├── launch/
│   │   ├── BriefInput.tsx
│   │   ├── CostDial.tsx
│   │   └── DurationSlider.tsx
│   ├── deck/
│   │   ├── StageTracker.tsx
│   │   ├── ScreenplayView.tsx
│   │   ├── StoryboardGrid.tsx
│   │   ├── GateActionBar.tsx
│   │   ├── CostMeter.tsx
│   │   └── DecisionTrailPanel.tsx
│   └── shared/
│       └── EmptyState.tsx
├── lib/
│   ├── api-client.ts
│   └── websocket.ts
└── styles/
```

Stack: Next.js 15, Tailwind, shadcn/ui components for the base primitives (cards, dialogs, buttons), lucide-react for icons — matches your existing frontend defaults.

---

## 2.2 Fleet View

```tsx
// components/fleet/StatusLight.tsx
const STATUS_MAP: Record<string, { color: string; label: string }> = {
  provisioning: { color: "bg-gray-400", label: "Starting" },
  running:      { color: "bg-green-500", label: "Nominal" },
  paused_decision: { color: "bg-yellow-500", label: "Awaiting you" },
  anomaly:      { color: "bg-red-500", label: "Anomaly" },
  done:         { color: "bg-gray-300", label: "Archived" },
};

export function StatusLight({ status }: { status: string }) {
  const s = STATUS_MAP[status] ?? STATUS_MAP.provisioning;
  return (
    <span className="flex items-center gap-2">
      <span className={`w-2.5 h-2.5 rounded-full ${s.color}`} />
      <span className="text-sm text-gray-600">{s.label}</span>
    </span>
  );
}
```

```tsx
// app/projects/page.tsx
export default async function FleetView() {
  const projects = await apiClient.getProjects();
  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-semibold">Mission Control</h1>
        <Link href="/projects/new" className="btn-primary">+ New Launch</Link>
      </div>
      {projects.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-4 gap-4">
          {projects.map(p => <ProjectCard key={p.id} project={p} />)}
        </div>
      )}
    </div>
  );
}
```

Polling for MVP: `useSWR('/api/projects', fetcher, { refreshInterval: 5000 })` — swap for WebSocket in §2.5 once functional.

---

## 2.3 Launch Console (Guided only)

```tsx
// app/projects/new/page.tsx
'use client';
export default function LaunchConsole() {
  const [brief, setBrief] = useState('');
  const [duration, setDuration] = useState(45);
  const [costTier, setCostTier] = useState<'free'|'balanced'|'premium'>('balanced');
  const [estimate, setEstimate] = useState<number|null>(null);

  async function handleEstimate() {
    const res = await apiClient.estimateProject({ brief, duration, costTier });
    setEstimate(res.estimated_cost);
  }

  async function handleLaunch() {
    const res = await apiClient.createProject({
      pipeline_type: 'animated-explainer',   // hardcoded for Phase 2
      name: brief.slice(0, 60),
      duration_target_seconds: duration,
      params_json: { brief, cost_tier: costTier },
    });
    router.push(`/projects/${res.project_id}/run/${res.run_id}`);
  }

  return (
    <div className="max-w-xl mx-auto p-8 space-y-6">
      <textarea value={brief} onChange={e => setBrief(e.target.value)}
        placeholder="What's the video about?" onBlur={handleEstimate} />
      <DurationSlider value={duration} onChange={setDuration} />
      <CostDial value={costTier} onChange={setCostTier} />
      {estimate !== null && (
        <p className="text-sm text-gray-500">Estimated cost: ${estimate.toFixed(2)}</p>
      )}
      <button onClick={handleLaunch} className="btn-primary w-full">Launch</button>
    </div>
  );
}
```

`cost_tier` maps to a budget preset on the backend: `free` forces `budget_mode='cap'` at `$0.00` with `provider_override` restricted to free-tier providers (Piper, Pexels/Pixabay/Unsplash/Archive.org, Remotion) — implement this as a lookup table in `api/graph/nodes.py`, not new engine logic.

---

## 2.4 Command Deck

```tsx
// components/deck/StageTracker.tsx
const STAGES = ["research", "proposal", "script", "scene_plan", "assets", "edit", "compose"];

export function StageTracker({ currentStage }: { currentStage: string }) {
  const idx = STAGES.indexOf(currentStage);
  return (
    <div className="flex items-center gap-2">
      {STAGES.map((s, i) => (
        <div key={s} className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${i <= idx ? 'bg-blue-500' : 'bg-gray-200'}`} />
          <span className="text-xs">{s}</span>
          {i < STAGES.length - 1 && <div className="w-6 h-px bg-gray-200" />}
        </div>
      ))}
    </div>
  );
}
```

```tsx
// components/deck/GateActionBar.tsx
export function GateActionBar({ runId, gate }: { runId: string; gate: ApprovalGate }) {
  const [notes, setNotes] = useState('');
  async function respond(decision: 'approve' | 'revise' | 'reject') {
    await apiClient.resumeRun(runId, { decision, revision_notes: notes });
  }
  return (
    <div className="flex gap-3 items-center border-t pt-4">
      <button onClick={() => respond('approve')} className="btn-primary">Approve</button>
      <input value={notes} onChange={e => setNotes(e.target.value)}
        placeholder="Revision notes..." className="flex-1 border rounded px-2 py-1" />
      <button onClick={() => respond('revise')} className="btn-secondary">Request Revision</button>
      <button onClick={() => respond('reject')} className="btn-ghost text-red-500">Reject</button>
    </div>
  );
}
```

```tsx
// app/projects/[id]/run/[runId]/page.tsx — gate-type-conditional rendering
function CommandDeckBody({ run, gate }: { run: Run; gate: ApprovalGate | null }) {
  if (!gate) return <LiveProgressView run={run} />;
  switch (gate.gate_type) {
    case 'proposal': return <ProposalView payload={gate.payload_json} />;
    case 'script': return <ScreenplayView payload={gate.payload_json} />;
    case 'scene_plan':
    case 'assets': return <StoryboardGrid payload={gate.payload_json} lockable={false} />; // lock/regen deferred to Phase 3
    case 'publish': return <PublishPreview payload={gate.payload_json} />;
  }
}
```

---

## 2.5 Live updates (polling → WebSocket)

```python
# api/routers/runs.py
from fastapi import WebSocket

@router.websocket("/{run_id}/stream")
async def stream_run(websocket: WebSocket, run_id: str):
    await websocket.accept()
    async for event in subscribe_run_events(run_id):  # Redis pub/sub, published by the bridge watcher
        await websocket.send_json(event)
```

```tsx
// lib/websocket.ts
export function useRunStream(runId: string) {
  const [state, setState] = useState<RunState | null>(null);
  useEffect(() => {
    const ws = new WebSocket(`${WS_BASE}/runs/${runId}/stream`);
    ws.onmessage = (e) => setState(JSON.parse(e.data));
    return () => ws.close();
  }, [runId]);
  return state;
}
```

Swap `useSWR` polling for `useRunStream` once this passes a manual test — keep polling as a fallback if the WebSocket drops.

---

## Phase 2 acceptance test

Manual, with a non-technical test subject if possible:
1. Open Fleet View (empty state).
2. Click "New Launch," type a one-sentence brief, accept defaults, click Launch.
3. Watch the Command Deck progress through research → proposal (first gate).
4. Approve each gate as it appears, including the storyboard grid at scene_plan/assets (approve-only is fine for this phase).
5. Confirm a finished video is playable at the publish gate and downloadable after approval.

**Exit criteria:** the test subject completes the above with zero explanation beyond "make a video about X" — no engineering assistance, no reading documentation.
