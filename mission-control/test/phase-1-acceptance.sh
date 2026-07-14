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
  -d '{"name":"acceptance-test","pipeline_type":"animated-explainer","duration_target_seconds":45}')
PROJECT_ID=$(echo "$CREATE" | jq -r '.project_id')
RUN_ID=$(echo "$CREATE" | jq -r '.run_id')
STATUS=$(echo "$CREATE" | jq -r '.status')
echo "  project: $PROJECT_ID  run: $RUN_ID  status: $STATUS"
check "create project returns provisioning" "provisioning" "$STATUS"

step "2. Wait for first checkpoint to appear"
for i in $(seq 1 30); do
  CPS=$(curl -s "$BASE/runs/$RUN_ID/checkpoints")
  COUNT=$(echo "$CPS" | jq 'length')
  if [[ "$COUNT" -gt 0 ]]; then
    echo "  checkpoint appeared after ${i}s (count=$COUNT)"
    break
  fi
  sleep 2
done
check "checkpoints exist after wait" "1" "$COUNT"

step "3. List projects"
LIST=$(curl -s "$BASE/projects")
PROJ_COUNT=$(echo "$LIST" | jq 'length')
echo "  projects: $PROJ_COUNT"
check "at least 1 project" "1" "$PROJ_COUNT"

step "4. Get project detail"
DETAIL=$(curl -s "$BASE/projects/$PROJECT_ID")
DETAIL_NAME=$(echo "$DETAIL" | jq -r '.name')
check "project name matches" "acceptance-test" "$DETAIL_NAME"

step "5. Wait for pending gate"
for i in $(seq 1 60); do
  GATES=$(curl -s "$BASE/runs/$RUN_ID/gates/pending")
  GATE_COUNT=$(echo "$GATES" | jq 'length')
  if [[ "$GATE_COUNT" -gt 0 ]]; then
    GATE_STAGE=$(echo "$GATES" | jq -r '.[0].stage')
    echo "  gate at stage=$GATE_STAGE after ${i}s"
    break
  fi
  sleep 2
done
check "pending gate appeared" "1" "$GATE_COUNT"

step "6. Resume run — approve"
RESUME=$(curl -s -X POST "$BASE/runs/$RUN_ID/resume" \
  -H 'Content-Type: application/json' \
  -d '{"decision":"approve"}')
RESUME_STATUS=$(echo "$RESUME" | jq -r '.status')
echo "  after resume: $RESUME_STATUS"
check "resume returns acknowledged" "awaiting_checkpoint" "$RESUME_STATUS"

step "7. Resume through remaining gates"
for i in 2 3 4 5; do
  for j in $(seq 1 30); do
    GATES=$(curl -s "$BASE/runs/$RUN_ID/gates/pending")
    GATE_COUNT=$(echo "$GATES" | jq 'length')
    if [[ "$GATE_COUNT" -gt 0 ]]; then
      GATE_STAGE=$(echo "$GATES" | jq -r '.[0].stage')
      echo "  gate #$i stage=$GATE_STAGE — approving"
      curl -s -X POST "$BASE/runs/$RUN_ID/resume" \
        -H 'Content-Type: application/json' \
        -d '{"decision":"approve"}' > /dev/null
      break
    fi
    if [[ "$j" -eq 30 ]]; then
      echo "  no more gates after $((i-1)) approvals — checking if done"
    fi
    sleep 2
  done
done

step "8. Wait for run to complete"
for i in $(seq 1 30); do
  STATE=$(curl -s "$BASE/runs/$RUN_ID/state")
  FINAL_STATUS=$(echo "$STATE" | jq -r '.status')
  echo "  status=$FINAL_STATUS  stage=$(echo "$STATE" | jq -r '.current_stage // "?"')"
  if [[ "$FINAL_STATUS" == "done" ]]; then
    break
  fi
  sleep 3
done
check "run completes with status done" "done" "$FINAL_STATUS"

step "9. Final checkpoint count"
FINAL_CPS=$(curl -s "$BASE/runs/$RUN_ID/checkpoints" | jq 'length')
echo "  total checkpoints: $FINAL_CPS"
check "at least 8 stages archived" "8" "$FINAL_CPS"

echo ""
echo "================================"
green "PASSED: $PASS"
if [[ "$FAIL" -gt 0 ]]; then
  red "FAILED: $FAIL"
  exit 1
fi
echo "================================"
