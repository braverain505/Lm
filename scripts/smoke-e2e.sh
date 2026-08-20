#!/usr/bin/env bash
# SchoolOS Phase 1 E2E smoke against the running API (:8000).
# Usage: bash scripts/smoke-e2e.sh
set -u
API="${API:-http://127.0.0.1:8000}"
JAR=$(mktemp)
pass=0; fail=0

check() { # name expected_code actual_code
  if [ "$2" = "$3" ]; then
    echo "  ok   $1 ($3)"
    pass=$((pass+1))
  else
    echo "  FAIL $1 (expected $2 got $3)"
    fail=$((fail+1))
  fi
}

echo "== 1. Health =="
c=$(curl -s -o /dev/null -w "%{http_code}" "$API/api/health"); check "health" 200 "$c"

echo "== 2. Demo login (Brightfield demo school) =="
c=$(curl -s -c "$JAR" -o /tmp/smoke-login.json -w "%{http_code}" \
  -X POST "$API/api/auth/login" -H 'Content-Type: application/json' \
  -d '{"email":"admin@brightfield.edu","password":"Brightfield#2026"}'); check "login" 200 "$c"

sid=$(curl -s -b "$JAR" "$API/api/auth/me" | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['memberships'][0]['school_id'])")
echo "  active school id: $sid"

echo "== 3. Session + arms =="
c=$(curl -s -b "$JAR" -o /tmp/smoke-sessions.json -w "%{http_code}" \
  "$API/api/academics/sessions" -H "X-School-Id: $sid"); check "sessions" 200 "$c"
session_id=$(python3 -c "import json; print(json.load(open('/tmp/smoke-sessions.json'))[0]['id'])")
c=$(curl -s -b "$JAR" -o /tmp/smoke-arms.json -w "%{http_code}" \
  "$API/api/academics/sessions/$session_id/arms" -H "X-School-Id: $sid"); check "arms" 200 "$c"

echo "== 4. Students =="
c=$(curl -s -b "$JAR" -o /tmp/smoke-students.json -w "%{http_code}" \
  "$API/api/students" -H "X-School-Id: $sid"); check "students" 200 "$c"
n=$(python3 -c "import json; print(len(json.load(open('/tmp/smoke-students.json'))))")
echo "  student count: $n"

echo "== 5. Cross-school isolation (register 2nd school, target 1st resource) =="
JAR2=$(mktemp)
# Unique name + email per run so the smoke is idempotent — re-runs must not
# trip the duplicate-email or duplicate-school-name guards left by earlier runs.
smoke2_suffix="$(date +%s)"
smoke2_email="smoke2-${smoke2_suffix}@two-school.edu"
curl -s -c "$JAR2" -o /tmp/smoke-reg2.json -X POST "$API/api/auth/register-school" \
  -H 'Content-Type: application/json' \
  -d "{\"school_name\":\"Smoke School Two ${smoke2_suffix}\",\"school_type\":\"secondary\",\"admin_email\":\"$smoke2_email\",\"admin_full_name\":\"Smoke Admin\",\"password\":\"Str0ng!Pass\"}" >/dev/null
sid2=$(curl -s -b "$JAR2" "$API/api/auth/me" | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['memberships'][0]['school_id'])")
target=$(python3 -c "import json; print(json.load(open('/tmp/smoke-sessions.json'))[0]['id'])")
c=$(curl -s -b "$JAR2" -o /tmp/smoke-x.json -w "%{http_code}" \
  "$API/api/academics/sessions/$target" -H "X-School-Id: $sid2"); check "cross-school 404" 404 "$c"
code=$(python3 -c "import json; print(json.load(open('/tmp/smoke-x.json'))['error']['code'])")
echo "  cross-school code: $code"

echo "== 6. Readiness =="
term_id=$(curl -s -b "$JAR" "$API/api/academics/sessions/$session_id/terms" -H "X-School-Id: $sid" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
c=$(curl -s -b "$JAR" -o /tmp/smoke-readiness.json -w "%{http_code}" \
  "$API/api/results/readiness?term_id=$term_id" -H "X-School-Id: $sid"); check "readiness" 200 "$c"
python3 -c "
import json
rows=json.load(open('/tmp/smoke-readiness.json'))
print('  readiness rows:', len(rows))
[print('   ', r['arm_name'], r['subject_name'], 'enrolled', r['student_count'], 'entered', r['entered'], 'pending', r['pending']) for r in rows[:4]]
"

echo
echo "== RESULT: $pass passed, $fail failed =="
rm -f "$JAR" "$JAR2"
[ "$fail" -eq 0 ]