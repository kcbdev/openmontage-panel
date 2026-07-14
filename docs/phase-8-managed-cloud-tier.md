# Phase 8 — Managed Cloud Tier (Optional)
### Detailed Implementation Guide

**Prerequisite:** Phase 7 shipped, real customers running self-hosted instances, AGPL posture for a hosted resale confirmed (revisit the Phase 0 §0.1 memo specifically for this scenario — hosting a multi-tenant service is a materially different posture than a customer running their own instance, and needs its own explicit sign-off).

**Do not start this phase speculatively.** It exists to be picked up only once Phase 7 has demonstrated demand and the licensing question has a clean answer for this specific model.

---

## 8.1 Compute cost modeling

Before pricing anything, instrument real cost per render across the pipelines already validated in Phase 4:

```python
# api/analytics/cost_model.py
def compute_actual_infra_cost(run_id: str) -> dict:
    run = get_run(run_id)
    container_seconds = (run.finished_at - run.started_at).total_seconds()
    compute_cost = container_seconds * HETZNER_PER_SECOND_RATE[run.container_size]
    provider_cost = sum(a.cost for a in get_run_assets(run_id))  # already tracked via budget_ledger
    storage_cost = estimate_storage_cost(get_run_assets(run_id))
    return {
        "compute": compute_cost,
        "provider_api": provider_cost,
        "storage": storage_cost,
        "total": compute_cost + provider_cost + storage_cost,
    }
```

Run this against a sample of real Phase 4-7 usage data (your own dogfooding, plus any early Phase 7 customer aggregate stats, anonymized) before setting managed-tier pricing — don't price from a spreadsheet guess.

## 8.2 Multi-tenant hosted deployment topology

This reuses the exact stack from Phase 7's Coolify template, operated by you instead of the customer, with hardening specific to running many unrelated tenants on shared infrastructure:

```yaml
# managed-cloud/docker-compose.prod.yml — extends the Phase 7 template
services:
  mission-control-api:
    deploy:
      replicas: 3   # horizontal scaling, was single-instance in Phase 7
    environment:
      RATE_LIMIT_PER_TENANT: "10/hour"   # new — wasn't needed for single-tenant self-hosted

  postgres:
    # move to managed Postgres (e.g. Hetzner + pgBackRest, or a managed provider)
    # rather than the single-container Phase 7 setup — durability matters more
    # when you're operationally responsible for multiple customers' data

  engine-pool:
    # pre-warmed pool of engine containers instead of cold spawn-per-run,
    # to keep managed-tier latency competitive — this is new infrastructure
    # not present in the self-hosted template
```

Key operational differences from Phase 7 that need explicit engineering, not just more servers:
- **Tenant resource fairness** — one tenant's heavy usage must not starve another's; enforce the `max_concurrent_runs` cap from Phase 5 more strictly, add per-tenant rate limiting at the API gateway.
- **Cross-tenant blast radius** — the Phase 5 storage isolation audit needs to be re-run under adversarial assumptions (a compromised tenant credential should not expose other tenants), not just correctness-tested.
- **Engine container pool warmth** — cold-starting a container per run (fine for one self-hosted customer) becomes a real latency cost at managed-tier scale; consider a warm pool with per-run credential/config injection at pickup time rather than at container boot.

## 8.3 Billing

```python
# api/billing/usage.py
def compute_monthly_bill(tenant_id: str, period: DateRange) -> Bill:
    runs = get_completed_runs(tenant_id, period)
    line_items = [
        {"run_id": r.id, "project_name": r.project.name, "cost": compute_actual_infra_cost(r.id)["total"]}
        for r in runs
    ]
    subtotal = sum(li["cost"] for li in line_items)
    margin_adjusted = subtotal * MANAGED_TIER_MARGIN_MULTIPLIER
    return Bill(tenant_id=tenant_id, period=period, line_items=line_items, total=margin_adjusted)
```

This is a direct extension of data you already collect in `budget_ledger` from Phase 1 onward — billing is a reporting layer on existing data, not new tracking infrastructure. Integrate with Stripe (or a regional equivalent) for actual invoicing once the model above is validated against a few months of real usage data.

## 8.4 What NOT to build in this phase

- Don't build a self-serve signup flow before validating the licensing posture — early managed-tier customers should be manually onboarded so you retain the ability to change terms/pricing quickly if the legal answer shifts.
- Don't over-invest in the warm-pool infrastructure (§8.2) until cold-start latency is confirmed to be an actual complaint from real usage — it's real engineering effort that Phase 7's simpler cold-spawn model may be sufficient for longer than expected.

---

## Phase 8 "exit criteria" — deliberately loose

This phase doesn't have a fixed acceptance test the way Phases 0-7 do, because it shouldn't be scoped in detail until there's real signal to scope it against. Treat the sections above as a checklist to work through once that signal exists, not a sprint plan to execute on a fixed timeline.
