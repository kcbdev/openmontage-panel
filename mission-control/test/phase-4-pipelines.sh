#!/usr/bin/env bash
# Phase 4 acceptance: pipeline picker + studio mode + credentials + budget
set -euo pipefail
BASE=${1:-http://localhost:8000}
PASS=0 FAIL=0

pass() { PASS=$((PASS+1)); echo "  PASS: $*"; }
fail() { FAIL=$((FAIL+1)); echo "  FAIL: $*"; }

echo "=== Phase 4: Pipeline Picker ==="

# 1. List pipelines — expect at least 12
PIPELINES=$(curl -sf "$BASE/pipelines") || { fail "GET /pipelines"; exit 1; }
COUNT=$(echo "$PIPELINES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))")
[ "$COUNT" -ge 12 ] && pass "Found $COUNT pipelines (>=12)" || fail "Expected >=12 pipelines, got $COUNT"

# 2. Each pipeline has required fields
python3 -c "
import sys, json
data = json.load(sys.stdin)
for p in data:
    assert 'id' in p, f'missing id in {p}'
    assert 'stages' in p, f'missing stages in {p}'
    assert len(p['stages']) > 0, f'empty stages in {p[\"id\"]}'
print('ok')
" <<< "$PIPELINES" && pass "All pipelines have valid structure" || fail "Pipeline structure check failed"

# 3. Get a specific pipeline detail
DETAIL=$(curl -sf "$BASE/pipelines/animated-explainer") || { fail "GET /pipelines/animated-explainer"; }
echo "$DETAIL" | python3 -c "
import sys, json
p = json.load(sys.stdin)
assert p.get('name') == 'animated-explainer'
assert len(p.get('stages', [])) >= 6
print('ok')
" && pass "Pipeline detail endpoint works" || fail "Pipeline detail check failed"

echo ""
echo "=== Phase 4: Provider Menu ==="
MENU=$(curl -sf "$BASE/providers/menu") || { fail "GET /providers/menu"; }
python3 -c "
import sys, json
m = json.load(sys.stdin)
for key in ['video_generation', 'tts', 'music_generation', 'image_generation']:
    assert key in m, f'missing provider category {key}'
    assert 'available' in m[key], f'missing available in {key}'
print('ok')
" <<< "$MENU" && pass "Provider menu has all required categories" || fail "Provider menu structure check failed"

echo ""
echo "=== Phase 4: Credential Vault ==="
# 1. Get current tenant
TENANT=$(curl -sf "$BASE/tenant") || { fail "GET /tenant"; }
TENANT_ID=$(echo "$TENANT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id') or '')")
if [ -z "$TENANT_ID" ]; then
  fail "No tenant found — create a project first"
else
  pass "Tenant ID: $TENANT_ID"

  # 2. Add a credential
  curl -sf -X POST "$BASE/credentials?tenant_id=$TENANT_ID" \
    -H "Content-Type: application/json" \
    -d '{"key":"TEST_KEY","value":"test_value_123"}' > /dev/null \
    && pass "POST /credentials — created" || fail "POST /credentials failed"

  # 3. List credentials
  CREDS=$(curl -sf "$BASE/credentials?tenant_id=$TENANT_ID")
  echo "$CREDS" | python3 -c "
import sys, json
creds = json.load(sys.stdin)
keys = [c['key'] for c in creds]
assert 'TEST_KEY' in keys, f'TEST_KEY not found in {keys}'
print('ok')
" && pass "Credential listed" || fail "Credential not found in list"

  # 4. Test credential
  curl -sf -X POST "$BASE/credentials/TEST_KEY/test?tenant_id=$TENANT_ID" > /dev/null \
    && pass "POST /credentials/TEST_KEY/test" || fail "Credential test failed"

  # 5. Delete credential
  curl -sf -X DELETE "$BASE/credentials/TEST_KEY?tenant_id=$TENANT_ID" > /dev/null \
    && pass "DELETE /credentials/TEST_KEY" || fail "Credential delete failed"
fi

echo ""
echo "=== Phase 4: Budget Console ==="
if [ -z "${TENANT_ID:-}" ]; then
  fail "Skipping budget test — no tenant"
else
  # 1. Get budget
  BUDGET=$(curl -sf "$BASE/tenants/$TENANT_ID/budget") || { fail "GET /tenants/$TENANT_ID/budget"; }
  echo "$BUDGET" | python3 -c "
import sys, json
b = json.load(sys.stdin)
assert 'cap' in b
assert 'mode' in b
print('ok')
" && pass "GET budget" || fail "Budget response invalid"

  # 2. Update budget
  curl -sf -X PUT "$BASE/tenants/$TENANT_ID/budget" \
    -H "Content-Type: application/json" \
    -d '{"cap":25.0,"mode":"cap"}' > /dev/null \
    && pass "PUT budget" || fail "Budget update failed"

  # 3. Verify update persisted
  BUDGET2=$(curl -sf "$BASE/tenants/$TENANT_ID/budget")
  echo "$BUDGET2" | python3 -c "
import sys, json
b = json.load(sys.stdin)
assert b['cap'] == 25.0, f'expected cap 25.0, got {b[\"cap\"]}'
assert b['mode'] == 'cap', f'expected mode cap, got {b[\"mode\"]}'
print('ok')
" && pass "Budget update persisted" || fail "Budget update not persisted"
fi

echo ""
echo "=== Phase 4: Studio Mode Launch ==="
# Create a project with studio_params
RESULT=$(curl -sf -X POST "$BASE/projects" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "phase-4-test",
    "pipeline_type": "animated-explainer",
    "duration_target_seconds": 30,
    "studio_params": {
      "render_runtime": "remotion",
      "footage_mode": "ai_generated",
      "providers": {"video_gen": "veo_video", "tts": "openai_tts"},
      "model_routing": {"research": "anthropic/claude-3.5-haiku", "script": "anthropic/claude-sonnet-4"},
      "style_playbook": "clean-professional",
      "budget_cap": 5.0
    }
  }') || { fail "POST /projects with studio_params"; }
echo "$RESULT" | python3 -c "
import sys, json
r = json.load(sys.stdin)
assert 'project_id' in r
assert 'run_id' in r
print('project_id:', r['project_id'])
print('run_id:', r['run_id'])
print('ok')
" && pass "Studio mode project created" || fail "Studio mode project creation failed"

echo ""
echo "=== Summary: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
