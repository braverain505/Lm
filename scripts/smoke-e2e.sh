#!/usr/bin/env bash
# Clearis Phase 1 E2E smoke against the running API (:8000).
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

echo "== 7. School result code -> the parents' way into a report card =="
# Every results write is refused until an admin activates BOTH the session and
# the term it belongs to; the seed leaves the current session current-but-not-open
# so the demo school can be walked through the real activation flow.
read -r cur_session < <(python3 -c "
import json
sessions = json.load(open('/tmp/smoke-sessions.json'))
print(next((s for s in sessions if s['is_current']), sessions[0])['id'])
")
term_id=$(curl -s -b "$JAR" \
  "$API/api/academics/sessions/$cur_session/terms" -H "X-School-Id: $sid" \
  | python3 -c "
import sys, json
terms = json.load(sys.stdin)
print(next((t for t in terms if t['is_current']), terms[0])['id'])
")
c=$(curl -s -b "$JAR" -o /tmp/smoke-act-session.json -w "%{http_code}" -X POST \
  "$API/api/academics/sessions/$cur_session/activate" -H "X-School-Id: $sid")
check "activate session" 200 "$c"
c=$(curl -s -b "$JAR" -o /tmp/smoke-act-term.json -w "%{http_code}" -X POST \
  "$API/api/academics/terms/$term_id/activate" -H "X-School-Id: $sid")
check "activate term" 200 "$c"

# The code is the Exam Office's document opener, so it needs results.report_card.
c=$(curl -s -b "$JAR" -o /tmp/smoke-pin-pre.json -w "%{http_code}" \
  "$API/api/results/portal-pin" -H "X-School-Id: $sid"); check "portal-pin read" 200 "$c"

# Publish one arm x subject so the portal has a card to open. The seed leaves
# results submitted, not published.
c=$(curl -s -b "$JAR" -o /tmp/smoke-workbench.json -w "%{http_code}" \
  "$API/api/results/workbench?term_id=$term_id" -H "X-School-Id: $sid")
check "workbench" 200 "$c"
read -r arm_id subject_id < <(python3 -c "
import json
rows = [r for r in json.load(open('/tmp/smoke-workbench.json')) if r['submitted']]
print(rows[0]['arm_id'], rows[0]['subject_id']) if rows else print(' ', end='')
")
if [ -n "$arm_id" ]; then
  for stage in verify approve publish; do
    c=$(curl -s -b "$JAR" -o "/tmp/smoke-$stage.json" -w "%{http_code}" \
      -X POST "$API/api/results/$stage" -H "X-School-Id: $sid" \
      -H 'Content-Type: application/json' \
      -d "{\"arm_id\":\"$arm_id\",\"subject_id\":\"$subject_id\",\"term_id\":\"$term_id\"}")
    check "results/$stage" 200 "$c"
  done
else
  echo "  (no submitted arm x subject to publish — the unlock checks will be skipped)"
fi

c=$(curl -s -b "$JAR" -o /tmp/smoke-pin.json -w "%{http_code}" -X POST \
  "$API/api/results/portal-pin" -H "X-School-Id: $sid"); check "portal-pin issue" 200 "$c"
code=$(python3 -c "import json; print(json.load(open('/tmp/smoke-pin.json'))['code'])")
prefix=$(python3 -c "import json; print(json.load(open('/tmp/smoke-pin.json'))['prefix'])")
echo "  school result code: $code   (initials: $prefix)"

# A parent holding the code, looking for their child's card.
adm=""
if [ -n "$arm_id" ]; then
  adm=$(curl -s -b "$JAR" \
    "$API/api/results/report-index?arm_id=$arm_id&term_id=$term_id" \
    -H "X-School-Id: $sid" | python3 -c "
import sys, json
rows = [r for r in json.load(sys.stdin) if r['subjects_published']]
print(rows[0]['admission_no'] if rows else '')
")
fi

if [ -n "$adm" ]; then
  # The dash is optional and case does not matter — the code is typed by hand.
  dashless=$(python3 -c "print('$code'.replace('-', '').lower())")
  c=$(curl -s -o /tmp/smoke-check.json -w "%{http_code}" -X POST "$API/api/public/result-check" \
    -H 'Content-Type: application/json' \
    -d "{\"pin\":\"$dashless\",\"admission_no\":\"$adm\"}")
  check "result-check (code without its dash)" 200 "$c"
  token=$(python3 -c "import json; print(json.load(open('/tmp/smoke-check.json'))['token'])")
  python3 -c "
import json
out = json.load(open('/tmp/smoke-check.json'))
print('  unlocked:', out['student']['full_name'], out['student']['admission_no'], 'at', out['school']['name'])
"

  c=$(curl -s -o /tmp/smoke-terms.json -w "%{http_code}" \
    "$API/api/public/terms?token=$token"); check "public terms" 200 "$c"
  c=$(curl -s -o /tmp/smoke-card.json -w "%{http_code}" \
    "$API/api/public/report-card?token=$token&term_id=$term_id"); check "public report-card" 200 "$c"
  python3 -c "
import json
card = json.load(open('/tmp/smoke-card.json'))
print('  card:', card['student']['full_name'], '| average', card['summary']['average'],
      '| grade', card['summary']['grade_letter'], '| subjects', len(card['subjects']))
"
else
  echo "  (no published card in this term — skipping the unlock assertions)"
fi

# The wrong door is the same door: unknown codes, codes from another school and
# unknown admission numbers all answer one uniform 404.
c=$(curl -s -o /tmp/smoke-bad.json -w "%{http_code}" -X POST "$API/api/public/result-check" \
  -H 'Content-Type: application/json' \
  -d '{"pin":"ZZZZ-99999","admission_no":"no-such-student"}')
check "unknown code -> uniform 404" 404 "$c"

# The office's kill switch: withdraw the code and it is dead at the public door.
c=$(curl -s -b "$JAR" -o /tmp/smoke-pin-del.json -w "%{http_code}" -X DELETE \
  "$API/api/results/portal-pin" -H "X-School-Id: $sid"); check "portal-pin withdraw" 200 "$c"
c=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/api/public/result-check" \
  -H 'Content-Type: application/json' \
  -d "{\"pin\":\"$code\",\"admission_no\":\"${adm:-no-such-student}\"}")
check "withdrawn code -> 404" 404 "$c"

# Re-issue so the demo school is left with a working code for the next run.
c=$(curl -s -b "$JAR" -o /tmp/smoke-pin2.json -w "%{http_code}" -X POST \
  "$API/api/results/portal-pin" -H "X-School-Id: $sid"); check "portal-pin re-issue" 200 "$c"

c=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/api/public/result-check" \
  -H 'Content-Type: application/json' \
  -d "{\"pin\":\"$code\",\"admission_no\":\"${adm:-no-such-student}\"}")
check "rotated-away code -> 404" 404 "$c"

echo
echo "== RESULT: $pass passed, $fail failed =="
rm -f "$JAR" "$JAR2"
[ "$fail" -eq 0 ]