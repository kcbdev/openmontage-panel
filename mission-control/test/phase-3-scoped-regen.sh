#!/usr/bin/env bash
set -euo pipefail

BASE="${1:-http://localhost:8000}"
PASS=0
FAIL=0

green() { printf "\033[32m%s\033[0m\n" "$1"; }
red()   { printf "\033[31m%s\033[0m\n" "$1"; }
step()  { printf "\n=== %s ===\n" "$1"; }

check() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    green "  PASS: $label"
    ((PASS++))
  else
    red "  FAIL: $label (expected: $expected, got: $actual)"
    ((FAIL++))
  fi
}

step "1. Create project"
CREATE=$(curl -s -X POST "$BASE/projects" \
  -H 'Content-Type: application/json' \
  -d '{"name":"phase-3-scope-test","pipeline_type":"animated-explainer","duration_target_seconds":45}')
PROJECT_ID=$(echo "$CREATE" | jq -r '.project_id')
RUN_ID=$(echo "$CREATE" | jq -r '.run_id')
STATUS=$(echo "$CREATE" | jq -r '.status')
echo "  project: $PROJECT_ID  run: $RUN_ID  status: $STATUS"
check "create project returns provisioning" "provisioning" "$STATUS"

step "2. Approve gates until scene_plan or assets"
SCENE_GATE=""
for attempt in $(seq 1 20); do
  GATES=$(curl -s "$BASE/runs/$RUN_ID/gates/pending")
  GATE_COUNT=$(echo "$GATES" | jq 'length')
  if [[ "$GATE_COUNT" -gt 0 ]]; then
    GATE_STAGE=$(echo "$GATES" | jq -r '.[0].stage')
    echo "  gate found: $GATE_STAGE (attempt $attempt)"
    if [[ "$GATE_STAGE" == "scene_plan" || "$GATE_STAGE" == "assets" ]]; then
      SCENE_GATE="$GATE_STAGE"
      break
    fi
    # Approve the non-scene gate
    curl -s -X POST "$BASE/runs/$RUN_ID/resume" \
      -H 'Content-Type: application/json' \
      -d '{"decision":"approve"}' > /dev/null
    echo "  approved $GATE_STAGE"
  fi
  sleep 3
done

if [[ -z "$SCENE_GATE" ]]; then
  red "FAIL: never reached scene_plan or assets gate"
  exit 1
fi
echo "  reached scene gate: $SCENE_GATE"

step "3. Fetch scene assets"
ASSETS=$(curl -s "$BASE/runs/$RUN_ID/assets")
ASSET_COUNT=$(echo "$ASSETS" | jq 'length')
echo "  assets found: $ASSET_COUNT"
check "at least 4 scene assets" "true" "$(echo "$ASSETS" | jq 'length >= 4')"

if [[ "$ASSET_COUNT" -lt 4 ]]; then
  # Fallback: check gate payload for artifacts
  GATES=$(curl -s "$BASE/runs/$RUN_ID/gates/pending")
  echo "  checking gate payload for artifacts instead"
  ARTIFACT_COUNT=$(echo "$GATES" | jq '.[0].payload.artifacts | length // 0')
  echo "  artifacts in gate payload: $ARTIFACT_COUNT"
  check "artifacts in gate payload" "true" "$(echo "$GATES" | jq '.[0].payload.artifacts | length >= 4')"
fi

step "4. Extract asset IDs and lock half of them"
if [[ "$ASSET_COUNT" -ge 2 ]]; then
  # Grab all asset IDs
  ASSET_IDS=()
  while IFS= read -r id; do
    ASSET_IDS+=("$id")
  done < <(echo "$ASSETS" | jq -r '.[].id')

  HALF=$(( ${#ASSET_IDS[@]} / 2 ))
  LOCKED_IDS=()
  for ((i=0; i<HALF; i++)); do
    AID="${ASSET_IDS[$i]}"
    LOCK_RESULT=$(curl -s -X POST "$BASE/runs/$RUN_ID/assets/$AID/lock" \
      -H 'Content-Type: application/json' \
      -d '{}')
    LOCKED=$(echo "$LOCK_RESULT" | jq -r '.is_locked')
    if [[ "$LOCKED" == "true" ]]; then
      LOCKED_IDS+=("$AID")
    fi
    echo "  asset $AID locked: $LOCKED"
  done
  echo "  locked $HALF assets"
else
  red "FAIL: not enough assets to test locking"
  exit 1
fi

step "5. Resume with scope — regenerate unlocked only"
SCOPE_JSON=$(cat <<SCOPE
{
  "decision": "approve",
  "scope": {
    "locked_scene_ids": $(printf '%s\n' "${LOCKED_IDS[@]}" | jq -R . | jq -s .),
    "regenerate_scenes": []
  }
}
SCOPE
)

RESUME=$(curl -s -X POST "$BASE/runs/$RUN_ID/resume" \
  -H 'Content-Type: application/json' \
  -d "$SCOPE_JSON")
RESUME_STATUS=$(echo "$RESUME" | jq -r '.status')
echo "  resume status: $RESUME_STATUS"
check "scope resume acknowledged" "awaiting_checkpoint" "$RESUME_STATUS"

step "6. Wait for next checkpoint and verify assets"
for i in $(seq 1 30); do
  STATE=$(curl -s "$BASE/runs/$RUN_ID/state")
  STATUS=$(echo "$STATE" | jq -r '.status')
  if [[ "$STATUS" == "done" || "$STATUS" == "awaiting_approval" ]]; then
    echo "  run progressed (status=$STATUS)"
    break
  fi
  sleep 3
done

# Verify locked assets still exist
FINAL_ASSETS=$(curl -s "$BASE/runs/$RUN_ID/assets")
FINAL_COUNT=$(echo "$FINAL_ASSETS" | jq 'length')
echo "  final asset count: $FINAL_COUNT"

# Check that all originally locked assets are still present
ALL_LOCKED_PRESENT=true
for AID in "${LOCKED_IDS[@]}"; do
  FOUND=$(echo "$FINAL_ASSETS" | jq "map(select(.id == \"$AID\")) | length")
  if [[ "$FOUND" -eq 0 ]]; then
    echo "  WARNING: locked asset $AID missing from final list"
    ALL_LOCKED_PRESENT=false
  fi
done
check "all locked assets persist" "true" "$ALL_LOCKED_PRESENT"

echo ""
echo "================================"
green "PASSED: $PASS"
if [[ "$FAIL" -gt 0 ]]; then
  red "FAILED: $FAIL"
  exit 1
fi
echo "================================"
