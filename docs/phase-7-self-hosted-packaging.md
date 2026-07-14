# Phase 7 — Self-Hosted Packaging & Docs
### Detailed Implementation Guide

**Prerequisite:** Phases 0-6 complete and their acceptance tests passing. This is the phase that turns the working system into a sellable artifact.

---

## 7.1 Coolify one-click deploy template

```yaml
# coolify-template/docker-compose.yml
version: "3.9"
services:
  mission-control-web:
    image: ghcr.io/yourorg/mission-control-web:${MC_VERSION:-latest}
    environment:
      NEXT_PUBLIC_API_URL: ${API_URL}
    depends_on: [mission-control-api]

  mission-control-api:
    image: ghcr.io/yourorg/mission-control-api:${MC_VERSION:-latest}
    environment:
      DB_URL: postgresql://postgres:${POSTGRES_PASSWORD}@postgres/mission_control
      REDIS_URL: redis://redis:6379
      MINIO_URL: http://minio:9000
      MINIO_ACCESS_KEY: ${MINIO_ROOT_USER}
      MINIO_SECRET_KEY: ${MINIO_ROOT_PASSWORD}
      ENGINE_IMAGE: ghcr.io/yourorg/openmontage-engine:${ENGINE_VERSION:-pinned}
      JWT_SECRET: ${JWT_SECRET}
      FERNET_KEY: ${FERNET_KEY}
    depends_on: [postgres, redis, minio]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock   # to spawn engine containers

  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: [postgres-data:/var/lib/postgresql/data]

  redis:
    image: redis:7
    volumes: [redis-data:/data]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ROOT_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    volumes: [minio-data:/data]

volumes:
  postgres-data:
  redis-data:
  minio-data:
```

Coolify-specific: register this as a Coolify "Service" template with a `.coolify/template.yaml` defining the required environment variables as prompted fields (`POSTGRES_PASSWORD`, `MINIO_ROOT_PASSWORD`, `JWT_SECRET`, `FERNET_KEY` auto-generated on deploy; `ENGINE_VERSION` defaulted to the current pinned tag).

**Resource defaults, documented explicitly:**
- `mission-control-api` + `mission-control-web`: 1 vCPU / 1GB RAM combined is sufficient — these stay small regardless of load (per the implementation guide's cost model, only engine containers scale)
- Each spawned `openmontage-engine` container: 2 vCPU / 4GB RAM minimum, more if local GPU generation is enabled
- Recommend a Hetzner CPX31 (4 vCPU/8GB) as the minimum viable single-tenant instance size in the docs

## 7.2 First-run wizard (implements Journey 1 exactly)

```tsx
// app/onboarding/page.tsx
const STEPS = ['account', 'credentials', 'budget', 'done'];

export default function OnboardingWizard() {
  const [step, setStep] = useState(0);
  return (
    <div className="max-w-lg mx-auto p-8">
      <ProgressDots steps={STEPS} current={step} />
      {STEPS[step] === 'account' && <CreateOwnerAccountStep onNext={() => setStep(1)} />}
      {STEPS[step] === 'credentials' && <CredentialsStep onNext={() => setStep(2)} onSkip={() => setStep(2)} />}
      {STEPS[step] === 'budget' && <BudgetDefaultsStep onNext={() => setStep(3)} />}
      {STEPS[step] === 'done' && <RedirectToFleetView />}
    </div>
  );
}
```

```python
# api/routers/onboarding.py
@router.get("/onboarding/status")
def onboarding_status():
    # gates the wizard — redirects straight to Fleet View if already onboarded
    return {"needs_onboarding": db.query(User).count() == 0}
```

## 7.3 Engine version management UI

```python
# api/routers/engine.py
@router.get("/engine/version")
def current_engine_version():
    return {"pinned_tag": PINNED_ENGINE_TAG, "commit": ENGINE_PINNED_COMMIT}

@router.post("/engine/upgrade")
def upgrade_engine(payload: EngineUpgradeRequest, user: User = Depends(require_owner)):
    # explicit, logged action — never silent, never automatic
    validate_new_tag_passes_contract_tests(payload.new_tag)
    update_config(PINNED_ENGINE_TAG=payload.new_tag)
    log_admin_action(user.id, "engine_upgrade", {"from": PINNED_ENGINE_TAG, "to": payload.new_tag})
    return {"status": "upgraded", "new_tag": payload.new_tag}
```

```tsx
// app/settings/engine/page.tsx
export default function EngineSettings() {
  const { data } = useSWR('/api/engine/version', fetcher);
  return (
    <div>
      <p>Current engine version: <code>{data?.pinned_tag}</code></p>
      <p className="text-sm text-gray-500">Commit: {data?.commit}</p>
      <UpgradeEngineButton current={data?.pinned_tag} />
    </div>
  );
}
```

## 7.4 Documentation set

Write these as actual files shipped in the repo, not just internal notes:

```
docs/
├── setup-guide.md              # Coolify deploy walkthrough, screenshots
├── credential-configuration.md  # per-provider key acquisition + setup, mirrors docs/PROVIDERS.md from engine
├── budget-governance.md         # explains observe/warn/cap, thresholds, ledger
├── troubleshooting.md           # common anomaly_reason strings and fixes
├── upgrading.md                 # engine version upgrade procedure + rollback
└── api-reference.md             # generated from FastAPI's OpenAPI schema
```

`credential-configuration.md` should map directly onto the engine's own `docs/PROVIDERS.md` — don't re-document pricing/free-tier details that already exist there, link to it and add only the Mission Control-specific "where to paste this key" instructions.

## 7.5 Support / managed-hosting service package

This is sales collateral as much as engineering, but define the operational runbook now:

```
docs/managed-hosting-runbook.md
├── Standard SLA response times
├── Monitoring setup (Coolify's built-in + optional external uptime check)
├── Backup procedure (Postgres dump + MinIO sync schedule)
├── Engine upgrade cadence and customer communication template
└── Incident response checklist
```

---

## Phase 7 acceptance test

**The real test:** hand the Coolify template URL and the `docs/setup-guide.md` to someone who has not touched the codebase, with no other communication. Confirm they can:
1. Deploy the stack from the template alone
2. Complete the first-run wizard
3. Complete Journey 2 (first video, Guided mode) unaided

If any step requires you to explain something not in the docs, that's a docs gap — fix the docs, not just answer the question, and re-test with a different person before calling this phase done.
