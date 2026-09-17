# School result code — the parents' way into their child's report card

Status: **implemented and verified — full API suite, production web build and
the migration chain all green; not yet committed/pushed** (paused on 2026-09-17 —
see [Remaining work](#remaining-work)).

## 1. What it is

Every school can issue **one result code** — a shareable access code that carries
the school's initials:

```
Green Valley Grammar School  →  GVGS-7K42Q
Test Academy                 →  TA-9K3MP
Clearis                      →  CLE-K6TQ2
```

A parent opens the login screen, picks **Check result**, and types that code plus
their child's admission number. They get the child's **published** report card,
which they can read, print, or download as a PDF.

It sits next to the two flows that already existed on `/login` (sign in, register
a school), so nobody has to guess which door is theirs.

## 2. Why a *school* code when per-student PINs already exist

The per-student PIN (`StudentPin`, Phase 2 slice 3) is the narrow option: one
secret per child. The school code is the **broad** option, and it is what schools
actually operate in practice — the exam office prints one code on the results
notice and broadcasts it to every family, instead of minting and tracking
hundreds of PINs.

The trade-off is explicit and is the reason the API is built the way it is:

| | Per-student PIN | School result code |
| --- | --- | --- |
| Secret holder | one family | the whole school |
| Distribute | one at a time | print / broadcast |
| Re-readable by the office | no (hash only) | **yes** (stored as issued) |
| What it leaks if it escapes | one child's published card | nothing on its own |

A leaked school code reveals **nothing by itself**: it only names *which school*
is being asked. The admission number still has to match a real student, and the
report card service still refuses anything that is not published. Both routes
are kept — a school that prefers per-family secrets can use `/portal` and ignore
the code entirely.

## 3. How it works

### The code

- Shape `<INITIALS>-<BLOCK>`; the block is 5 characters drawn from
  `ABCDEFGHJKMNPQRSTUVWXYZ23456789`.
- `0/O`, `1/I/L` and `5/S` are **excluded on purpose** — the code is read off a
  chalkboard or a WhatsApp message and typed by hand.
- Initials are derived from `short_name`, else `name`:
  `Green Valley Grammar School` → `GVGS`, `University of Lagos` → `UL`
  (stopwords dropped), `Clearis` → `CLE`, `St. Mary's College` → `SMC`
  (a possessive is not an initial). A single-token `short_name` is already an
  abbreviation and is used as-is. Nothing usable → `SCH`.
- Input is normalised: case, surrounding spaces and *the dash itself* are
  optional (`gvs 7k42q` == `GVS7K42Q` == `GVS-7K42Q`).

### Issuing it

`GET|POST|DELETE /api/results/portal-pin`, all gated on **`results.report_card`**
— the report card is the Exam Office's document, so the code that opens it is
too. (Deliberately *not* a new permission code; a school admin who does not hold
it will not see the card in Settings.)

- `GET` → the live code, or `null` when none was ever issued.
- `POST` → issues a new code and **revokes** the live one. The old row survives
  with `revoked_at` set, so the audit trail of which code was live when is kept.
- `DELETE` → withdraws the code; parents cannot check results until a new one is
  issued. 404 when there is nothing live to withdraw.

Rotation is why uniqueness is a **partial** unique index
(`uq_school_result_pin_one … WHERE revoked_at IS NULL`) rather than a plain
constraint on `school_id` — the same technique as `uq_student_pin_one`.

### Checking in

`POST /api/public/result-check` — `{pin, admission_no}` → the same short-lived
portal JWT the PIN flow issues (`scope=portal`, `sub`=student, `school`=school,
30 min) plus student **and school** summaries. The code itself identifies the
tenant, so there is no school dropdown to find.

Two supporting public routes:

- `GET /api/public/terms?token=` → the terms this student has **published**
  results in, newest first. Drives the term picker so a parent can re-open an
  earlier report, not just the latest. Scoped by the token, so it tells a caller
  who has not already proven the code + admission number exactly nothing.
- `GET /api/public/report-card?token=&term_id=` — unchanged, shared by both flows.

### Security model

- **Stored as issued, not hashed** — and that is a deliberate departure from
  `StudentPin`. This code is a *shared, distributable* credential: the exam
  office prints it, and has to be able to **re-read and reprint** it. A
  per-person secret gets hashed; a broadcast code whose whole purpose is
  redistribution does not gain anything from it. It is only ever used to narrow
  a lookup to one school.
- **No per-code lockout.** A counter on a code shared by a whole school would let
  one attacker lock every parent out of their own result. Brute force is answered
  by the per-IP rate limit (`10/minute` on `/result-check`, `5/minute` on
  `/pin-check`) and by the fact that a correct code alone reveals nothing.
- **Uniform failure.** Unknown code, rotated code, blank code, unknown admission
  number, and a *different school's* code all answer the identical
  `ERR_NOT_FOUND` / `"Invalid portal credentials"` — the endpoint cannot be used
  to enumerate schools, students, or live codes.
- **Published-only, by construction.** The public card renders through the same
  `report_card` service the staff route uses.
- Usage is stamped on the code (`use_count`, `last_used_at`) so the office can
  see whether it is being used at all.

## 4. What was built

### API

| File | Change |
| --- | --- |
| `app/models/portal.py` | `SchoolResultPin` (`code`, `prefix`, `created_by`, `last_used_at`, `use_count`, `revoked_at`; partial-unique live row) |
| `app/models/__init__.py` | export it |
| `alembic/versions/0013_school_result_pins.py` | new table, created from model metadata (idempotent `create_all`, like 0010/0012) |
| `app/services/portal_service.py` | `school_initials`, `normalize_school_code`, `issue_school_pin`, `current_school_pin`, `revoke_school_pin`, `resolve_school_pin`, `published_terms` (and `latest_published_term_id` refactored onto it) |
| `app/schemas/portal.py` | `SchoolPinOut`, `SchoolPinCheck`, `PinTermBrief`; `PinCheckOut` now carries `school` |
| `app/routers/results.py` | `GET`/`POST`/`DELETE /results/portal-pin` behind `results.report_card` |
| `app/routers/portal.py` | `POST /public/result-check`, `GET /public/terms`; both `PinCheckOut` responses now include the school |

### Shared package

- `contracts.ts` — `SchoolPinOutSchema`, `PinTermBriefSchema`; `PinCheckOutSchema`
  gained `school`.
- `client.ts` — `schoolResultCheck`, `publicTerms`, `fetchSchoolResultPin`,
  `generateSchoolResultPin`, `revokeSchoolResultPin` (+ exports).

### Web

| File | Change |
| --- | --- |
| `app/login/page.tsx` | **redesigned** — one card, a three-way switcher: **Check result** / **Sign in** / **Register a school** (sliding `layoutId` pill, glow + grid backdrop, animated panels). The result panel formats the code as you type and hands the token to `/check-result`. The register panel is a short pitch with a CTA into `/register`. |
| `app/check-result/page.tsx` | **new premium public viewer** — identity banner built from the session (school crest, student, class), four stat tiles (average, position, attendance, subjects), a term picker, the full `ReportCardDocument`, **Download PDF** (`downloadPdf`) and **Print**, plus a clean "no published result yet" state and a bounce back to `/login` when there is no session. |
| `lib/portal-session.ts` | **new** — the portal token lives in **sessionStorage** (not the URL, not localStorage), so a result link cannot be pasted into a chat later and keep working, and closing the tab ends the session. |
| `app/(app)/settings/page.tsx` | **new "Results portal code" card** (only for holders of `results.report_card`): the live code in large monospace with copy-to-clipboard, use count / last used, **Regenerate** and **Withdraw** (both confirmed), and an empty state with **Generate result code**. |
| `scripts/smoke-e2e.sh` | section 7 — the live, headless walk of the parent flow (code issue → check-in → terms → card → uniform 404 → withdraw → re-issue). |
| `scripts/migrate.sh` | the venv probe now looks at the repo root first (`../../.venv`), then the old `apps/.venv`; the documented `bash scripts/migrate.sh seed` was silently falling back to system `python3` and failing with *No module named alembic*. |
| `hooks/use-api.ts` | `useSchoolResultPin`, `useGenerateSchoolResultPin`, `useRevokeSchoolResultPin` |

## 5. Verification

```
cd apps/api && DEBUG=true ../../.venv/bin/python -m pytest tests/test_portal.py -q
# 22 passed   (11 pre-existing + 11 new)
cd apps/web && npx tsc --noEmit
# clean
```

### Full API suite

The whole suite was run against `clearis_test` in three file groups (a single
invocation runs ~6 minutes, past the runner's per-command limit):

| Group | Files | Tests |
| --- | --- | --- |
| portal + results + permissions | `test_portal` 22, `test_results` 21, `test_result_access` 9, `test_student_scope` 2, `test_tenancy` 4 | **58 passed** |
| auth + finance + attendance | `test_auth` 9, `test_accounting` 16, `test_fees` 17, `test_attendance` 8, `test_timetable` 8, `test_promotion` 4, `test_imports` 16 | **78 passed** |
| AI + platform + ops | `test_ai_comments` 6, `test_copilot` 13, `test_lesson_plans` 7, `test_question_banks` 8, `test_platform` 8, `test_superadmin` 9, `test_staff_accounts` 6, `test_inventory` 11, `test_library` 10, `test_payroll` 11 | **89 passed** |

**225 passed, 0 failed, 0 errors** — every file in `apps/api/tests`, nothing
skipped or deselected.

### Web build

```
cd apps/web && npm run build
#   Creating an optimized production build ...
# ✓ Compiled successfully in 95s
#   Skipping linting            (as configured; typecheck below still runs)
#   Checking validity of types ...
#   Generating static pages (53/53)
#   ƒ /api/proxy/[...path]   125 B
#   ○ /check-result        7.05 kB
#   ○ /login               6.96 kB
#   exit 0
```

TypeScript is re-checked in isolation as well:

```
cd apps/web && npx tsc --noEmit
# clean
```

No `SIGBUS` — the crash recorded in `DASHBOARD_REDESIGN_STATUS.md` does not
reproduce on this checkout.

### Live smoke (headless)

`scripts/smoke-e2e.sh` grew a section 7 that walks the whole parent flow against
a running API — migrate + seed the dev database, `uvicorn` on :8000, then:

```
== 7. School result code -> the parents' way into a report card ==
  ok   activate session (200)
  ok   activate term (200)
  ok   portal-pin read (200)          # null before anything is issued
  ok   workbench (200)
  ok   results/verify (200)           # publish one arm x subject so
  ok   results/approve (200)          #   there is a card to open
  ok   results/publish (200)
  ok   portal-pin issue (200)
  school result code: BA-BDYPR   (initials: BA)
  ok   result-check (code without its dash) (200)
  unlocked: Ngozi Umeh STU-005 at Brightfield Academy
  ok   public terms (200)
  ok   public report-card (200)
  card: Ngozi Umeh | average 66.64 | grade C4 | subjects 1
  ok   unknown code -> uniform 404 (404)
  ok   portal-pin withdraw (200)
  ok   withdrawn code -> 404 (404)
  ok   portal-pin re-issue (200)
  ok   rotated-away code -> 404 (404)

== RESULT: 23 passed, 0 failed ==
```

This is the API half of the manual pass, on the real dev database rather than a
TestClient. It also leaves the demo school usable by hand: an activated session +
First Term, one published arm x subject, and a live result code.

### Migration chain

`alembic upgrade head` against an empty database walks
`0010_squashed_baseline → 0011_login_lockout_columns → 0012_accounting_ledger →
0013_school_result_pins`, and the table lands as designed, including the partial
unique index that makes rotation possible:

```
uq_school_result_pin_one  UNIQUE (school_id) WHERE revoked_at IS NULL
```

New tests (`tests/test_portal.py`):

| Test | Pins |
| --- | --- |
| `test_initials_read_naturally_from_the_school_name` | stopwords, possessives, single-word names, `short_name` precedence, `SCH` fallback |
| `test_issue_code_requires_results_report_card` | 401 unauthenticated; a **teacher** (has `results.view`/`enter`) is 403 |
| `test_code_is_null_until_issued_then_carries_school_initials` | `null` before issue; `GVGS-XXXXX` shape, no ambiguous glyphs; reads back |
| `test_rotation_revokes_the_previous_code` | new code differs, old row revoked-but-kept, live row is the new one |
| `test_withdraw_code_removes_parent_access` | `DELETE` returns `active=false`, `GET` is `null`, and the withdrawn code is dead at the public door |
| `test_withdraw_without_a_live_code_is_404` | nothing live to withdraw |
| `test_result_check_unlocks_published_card` | code + admission no → token; `/public/terms` scoped to the token; card total 60.0; `use_count`/`last_used_at` stamped |
| `test_result_check_accepts_the_code_without_its_dash` | `GVS7K42Q`, lowercase, and padded input all work |
| `test_result_check_generic_404_on_every_failure` | unknown code / unknown student / rotated code → one identical 404; blank → 422 |
| `test_result_check_case_insensitive_code_does_not_leak_schools` | *another* school's code does not unlock this school's student |
| `test_terms_requires_a_valid_portal_token` | bad token → 404 |

## 6. Remaining work

1. ✅ **Full API suite** — 225 passed, 0 failed (see [Verification](#5-verification)).
2. ✅ **Web build** — compiled successfully; `/login` and `/check-result` emitted.
3. ✅ **Migration chain** — `0013_school_result_pins` applies from an empty database.
4. ✅ **Live smoke** of the parent flow against a running API — 23/23 (see
   [Verification](#5-verification)); the dev database is migrated, seeded and
   left with a working result code.
5. ⏳ **Browser pass** on `/login` (all three tabs) and `/check-result` (download +
   print) — the only step that still needs a real browser; no Chrome is available
   in this environment.
6. ⏳ **Commit and push** to `origin/main`.

Note: the API tests must run with `DEBUG=true` in the environment.
`app/config.py` otherwise runs its production validation and fails on the dev JWT
secret — pre-existing, breaks the *entire* suite, and documented at the end of
`docs/ROLE_ACCESS_MATRIX.md`.

## 7. Product notes / possible follow-ups

- **Enumeration is possible by design.** With one code per school, anyone holding
  it can try admission numbers against it. That is the same exposure as a
  real-world "result checker" scratch card, and it is the trade the school makes
  by using the broad code instead of per-student PINs. If a school wants both,
  the enforcement point is `resolve_school_pin` (require a per-student PIN *in
  addition to* the school code).
- The PDF is generated **client-side** from the rendered card (`html2canvas-pro`
  + `jspdf`, `lib/pdf.ts`) — no server-side rendering, no new storage.
- The report template used on `/check-result` comes from
  `getSelectedTemplate()`, i.e. `localStorage`. A parent's device has no stored
  choice, so they always get `classic`. Moving the school's template into
  `schools.settings` would fix that for everyone, staff and parents alike.
