# Phase 6 — Library, Remix & Mission Profiles
### Detailed Implementation Guide

**Prerequisite:** Phase 5 acceptance tests pass (isolation, role gating, concurrency).

---

## 6.1 Mission Archive detail view

```python
# api/routers/projects.py
@router.get("/{project_id}")
def get_project_detail(project_id: str, tenant: Tenant = Depends(get_current_tenant)):
    project = tenant_scoped_query(Project, tenant).filter_by(id=project_id).first_or_404()
    runs = db.query(Run).filter_by(project_id=project_id).order_by(Run.started_at.desc()).all()
    return {
        "project": project,
        "versions": [{"run_id": r.id, "status": r.status, "started_at": r.started_at,
                      "total_cost": sum_run_cost(r.id)} for r in runs],
    }

@router.get("/{project_id}/assets")
def get_project_assets(project_id: str, stage: Optional[str] = None, type: Optional[str] = None):
    q = db.query(Asset).join(Run).filter(Run.project_id == project_id)
    if stage: q = q.filter(Asset.stage == stage)
    if type: q = q.filter(Asset.type == type)
    return q.all()
```

```tsx
// app/projects/[id]/page.tsx
export default function MissionArchive({ params }: { params: { id: string } }) {
  const { data } = useSWR(`/api/projects/${params.id}`, fetcher);
  const [filter, setFilter] = useState<{stage?: string; type?: string}>({});
  const { data: assets } = useSWR(`/api/projects/${params.id}/assets?${qs(filter)}`, fetcher);

  return (
    <div className="p-8">
      <div className="flex justify-between items-center">
        <h1>{data?.project.name}</h1>
        <div className="flex gap-2">
          <button onClick={() => remix(params.id)} className="btn-secondary">Remix</button>
          <a href={`/api/projects/${params.id}/download`} className="btn-primary">Download</a>
        </div>
      </div>
      <VersionSelector versions={data?.versions} />
      <AssetGrid assets={assets} onFilter={setFilter} />
      <DecisionAuditTable projectId={params.id} />
    </div>
  );
}
```

---

## 6.2 Remix

```python
# api/routers/projects.py
@router.post("/{project_id}/remix")
def remix_project(project_id: str, overrides: RemixOverrides, tenant: Tenant = Depends(get_current_tenant)):
    source = tenant_scoped_query(Project, tenant).filter_by(id=project_id).first_or_404()
    latest_params = db.query(ProjectParams).filter_by(project_id=source.id)\
        .order_by(ProjectParams.version.desc()).first()

    new_params = {**latest_params.params_json, **overrides.dict(exclude_unset=True)}
    new_project = Project(
        tenant_id=tenant.id, owner_id=source.owner_id,
        name=overrides.name or f"{source.name} (remix)",
        pipeline_type=source.pipeline_type,
        parent_project_id=source.id,
        render_runtime=new_params.get("render_runtime"),
        style_playbook=new_params.get("style_playbook"),
        platform_profile=new_params.get("platform_profile"),
    )
    db.add(new_project); db.commit()
    db.add(ProjectParams(project_id=new_project.id, version=1, params_json=new_params))
    db.commit()
    return {"project_id": new_project.id}
```

```tsx
// Launch Console — remix pre-fill path
// app/projects/new/page.tsx
export default function LaunchConsole({ searchParams }: { searchParams: { remix_from?: string } }) {
  const { data: sourceParams } = useSWR(
    searchParams.remix_from ? `/api/projects/${searchParams.remix_from}/params` : null, fetcher
  );
  const [params, setParams] = useState(sourceParams ?? defaultParams());
  // brief field blanked even when remixing, per Journey 8 — everything else pre-filled
  useEffect(() => {
    if (sourceParams) setParams({ ...sourceParams, brief: '' });
  }, [sourceParams]);
  ...
}
```

`parent_project_id` on `Project` was already added in the schema — Phase 6 is the first phase that reads/writes it.

---

## 6.3 Mission Profiles (templates)

```python
# api/models/core.py
class MissionProfile(Base):
    __tablename__ = "mission_profiles"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))
    name = Column(String)
    params_json = Column(JSON)
    style_playbook = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

```python
# api/routers/mission_profiles.py
@router.post("/mission-profiles")
def save_profile(payload: ProfileCreate, tenant: Tenant = Depends(get_current_tenant)):
    profile = MissionProfile(tenant_id=tenant.id, name=payload.name,
                              params_json=payload.params_json, style_playbook=payload.style_playbook)
    db.add(profile); db.commit()
    return profile

@router.get("/mission-profiles")
def list_profiles(tenant: Tenant = Depends(get_current_tenant)):
    return tenant_scoped_query(MissionProfile, tenant).all()
```

```tsx
// components/launch/SaveAsProfileButton.tsx — appears on Mission Archive
export function SaveAsProfileButton({ projectId, currentParams }: Props) {
  const [name, setName] = useState('');
  async function save() {
    await apiClient.saveMissionProfile({ name, params_json: currentParams });
  }
  return (
    <Dialog>
      <input value={name} onChange={e => setName(e.target.value)} placeholder="Profile name (e.g. Client X house style)" />
      <button onClick={save}>Save as Mission Profile</button>
    </Dialog>
  );
}
```

```tsx
// Launch Console — profile picker as an alternative starting point to a blank Studio form
<ProfilePicker onSelect={profile => setParams(profile.params_json)} />
```

## 6.4 Style playbook cloning

```python
# api/routers/styles.py
@router.post("/styles/clone")
def clone_playbook(payload: StyleCloneRequest, tenant: Tenant = Depends(get_current_tenant)):
    source_yaml = load_builtin_playbook(payload.source_id)   # from styles/*.yaml in the engine image
    cloned = TenantStylePlaybook(
        tenant_id=tenant.id, name=payload.new_name,
        yaml_content=merge_overrides(source_yaml, payload.overrides),
    )
    db.add(cloned); db.commit()
    return cloned
```

```python
# api/models/core.py
class TenantStylePlaybook(Base):
    __tablename__ = "tenant_style_playbooks"
    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID, ForeignKey("tenants.id"))
    name = Column(String)
    yaml_content = Column(String)   # valid styles/*.yaml content, mounted into the engine container at provision time
```

At `provision()`, if `project.style_playbook` references a tenant-custom playbook rather than a built-in, write its YAML into the container's `styles/` directory before the Driver starts — this is the one place Mission Control writes *into* the engine's filesystem rather than only reading from it, and it's additive (a new file), never a modification of an existing one.

---

## Phase 6 acceptance tests

1. **Remix:** find a completed project, remix with one changed parameter (cost tier), confirm the new project's `parent_project_id` links correctly and Launch Console pre-fills everything except the brief.
2. **Mission Profile:** save a Studio-mode parameter set as a named profile, start a new unrelated project, select that profile, confirm every field pre-fills correctly.
3. **Style clone:** clone a built-in playbook with one overridden color value, launch a project using the clone, confirm the rendered output reflects the override and the decision log correctly attributes the style choice to the tenant-custom playbook, not the built-in.
