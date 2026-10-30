# Reopening a closed term, the result archive, and the final-term average

Status: **implemented and verified** — API tests, web typecheck and the web test
suite are green; the migration chain applies from an empty database. The web
production build could not run in this environment because Next.js tries to
fetch the Inter font from Google Fonts (no network); that is unrelated to these
changes.

This document covers three related school requests:

1. A school must be able to **reopen a closed term**, correct a result and
   compile the term again.
2. Previous report cards must be **archived per school**, so the document a
   parent already received is never lost when a correction overwrites the live
   rows.
3. Some schools want the **third-term report card to show the average of the
   first, second and third term averages**. This is per-school academic policy,
   not a platform-wide rule.

---

## 1. Reopening a closed term

### The rule

Closing a term is the school's sign-off, so reopening is a separate, explicit
action. It is never a side effect of activating a term or editing scores.

`POST /api/academics/terms/{term_id}/reopen` (permission `academics.manage`)

```json
{ "reason": "Aisha's CA score was entered under the wrong student" }
```

The reason is required (3–500 characters) and is:

- stored on the archive row (when a legacy term has no archive yet), and
- journaled as a `ResultEvent(action="reopen")` against every result the reopen
  unlocks.

### What it does, in order

1. Rejects anything that is not `closed`. An open term is not "reopened"; it is
   already editable.
2. Reuses the archive closing already wrote, or archives the published cards
   first if this term was closed before archiving existed. No duplicate version
   is stored for a normal correction cycle.
3. Sends every result in the term from `published` / `approved` / `verified` /
   `submitted` back to `draft`, clearing `published_snapshot`, `published_at`,
   `approved_at`, `approved_by` and `submitted_at`. **Score cells are not
   touched**, so the grid opens on the values the school entered.
4. Opens the term and its session again, and makes them the current term/session
   (only one term per session is left open). Results writes require both, exactly
   as when the term was first activated.
5. Returns:

```json
{
  "term": { "id": "...", "name": "First Term", "status": "open", "is_current": true },
  "archive_id": "...",
  "archive_version": 1,
  "results_reset": 3
}
```

The school then edits the score in the normal score grid and runs
`submit → verify → approve → publish` (or the one-click `compile`) as usual.
The term can be closed again afterwards; closing archives the newly published
cards as the next version.

### Web

`School Settings → Academic sessions & terms`: a closed term now shows a
**Reopen** button. It prompts for the reason, reopens the term, points the app at
that session/term, and reports how many results went back to draft. The close
confirmation no longer claims the action is permanent.

---

## 2. Per-school result archive

### Why it exists

Live results are derived rows. Correcting a term necessarily overwrites them.
Without a frozen copy, the report card a parent holds could not be reproduced
after the correction. The archive keeps the **document**, not a re-query: it
stores the full card payload — subjects, totals, grades, positions, comments,
psychomotor rows, attendance, and the report-card layout that was live at the
time.

### When a version is written

- **When a term closes** — every completed term gets an archive version. This
  makes the archive the school's complete record, not just a list of corrections.
- **Before a legacy term is reopened** — a term closed before this feature (or
  one whose cards were never published) has no row yet, so reopening writes one.
- A reopen does **not** create a duplicate when close already archived the same
  cards. A term that is reopened, corrected, republished and closed again gets
  the next version (v2, v3, …).

A term with no published results writes no row: there is no document to keep.

### Data model

`term_result_archives` (migration `0016_term_result_archives`):

| Column | Meaning |
| --- | --- |
| `school_id` | Tenant scope; every query is filtered by it. |
| `term_id` / `academic_session_id` | Nullable, `ON DELETE SET NULL` — an archive outlives the structure it describes; the payload still names the term/session. |
| `version` | Counts up within the term; unique per `(school_id, term_id)`. |
| `reason` | Why this version was frozen (term closed / correction reason). |
| `archived_by` / `archived_at` | Who and when. |
| `student_count` / `class_count` | For the archive list. |
| `payload` | JSONB: `layout`, `students` (full report-card payloads), `term`, `session`, `archived_at`, `archived_by_name`. |

### API

Both endpoints require `results.report_card` — the archive is the Exam
Office's record, exactly like the live report cards.

- `GET /api/results/archives?term_id=&session_id=` → list rows (metadata only),
  newest first.
- `GET /api/results/archives/{archive_id}` → one row plus the frozen `payload`.

IDs are scoped by school, so another tenant's archive id is a 404.

### Web

`Result Generation → Result Archive` (`/reports/archive`):

- filters by session,
- lists each version with term, version, archive time/by, reason and card count,
- opens a version, picks a student, and renders the frozen
  `ReportCardDocument` with the **archived layout**,
- offers **Print this card**.

The archive is read-only by design; restoring an old version back into live
results was not part of the request and is intentionally not exposed.

---

## 3. Final-term combined average (third-term average case)

### Policy, not code

The switch lives on the school, in
`schools.settings["results_policy"]`:

```json
{ "combine_previous_terms": true, "final_term_no": 3 }
```

Default is **off**, `final_term_no = 3`. Only schools that ask for it see the
extra section, and each school chooses which term is final.

API (school-scoped):

- `GET /api/schools/me/results-policy` — `academics.view`
- `PATCH /api/schools/me/results-policy` — `school.manage`

```json
{ "combine_previous_terms": true, "final_term_no": 3 }
```

Web: `School Settings → Results policy`. Tick **Show the combined term average
on the final term's report card** and choose the final term.

### The computation

Only when the policy is on **and** the card's `term_no` equals
`final_term_no`:

- **Term average** = mean of that term's published subject totals (the same
  totals the card already prints).
- **Session average** = mean of the term averages that have published results.
  This is the school's stated rule: combine the first, second and third term
  averages.
- **Per-subject session average** = mean of that subject's totals across the
  terms it was published in.
- Terms with no published results are skipped rather than counted as zero.

Published `published_snapshot` values are the source, so a live card, a bulk PDF
and an archived card agree. The parent portal uses the same `report_card`
service, so parents see the same combined average.

### Where it appears on the card

- **Cognitive Domain** gains a `Session Avg` column beside the term `Total` when
  the block is present.
- **Performance Summary** gains a `Session Average — Combined Term Results`
  band: one tile per term with its average and subject count, plus a `Session`
  tile with the combined average.

Both are part of the printable/PDF card and the archived card. No new widget
type was added, so existing school card designs keep working unchanged; schools
that are not opted in print exactly what they printed before.

### Response shape

`GET /api/results/report-card` now includes (when applicable):

```json
"cumulative": {
  "final_term_no": 3,
  "terms": [
    { "term_id": "...", "term_name": "First Term", "term_no": 1,
      "average": 60.0, "subjects_published": 1 },
    { "term_id": "...", "term_name": "Second Term", "term_no": 2,
      "average": 70.0, "subjects_published": 1 },
    { "term_id": "...", "term_name": "Third Term", "term_no": 3,
      "average": 80.0, "subjects_published": 1 }
  ],
  "term_average": 80.0,
  "session_average": 70.0,
  "subjects": [
    { "subject_id": "...", "subject_name": "Mathematics",
      "terms": [ { "term_name": "First Term", "total": 60.0, "...": "..." } ],
      "average": 70.0 }
  ]
}
```

`cumulative` is `null` when the policy is off or the term is not the configured
final term.

---

## Files changed

### API

| File | Change |
| --- | --- |
| `app/models/results.py` | `TermResultArchive` model. |
| `app/models/__init__.py` | Export it. |
| `alembic/versions/0016_term_result_archives.py` | New table, created from model metadata (idempotent). |
| `app/services/results_service.py` | Results policy read/write; cumulative computation; report-card block; archive write/list/get; reopen reset. Score grids, the workbench, the report-card index and class standing now use **every enrollment in the arm**, not only the current roster, so a term reopened after promotion still lists its students. |
| `app/services/people_service.py` | `list_enrollments(..., include_inactive=True)` — the opt-out results work uses for historical terms. |
| `app/services/academics_service.py` | `close_term` archives published cards; `reopen_term` archives a legacy term, resets results, reopens the session/term. |
| `app/services/copilot_actions.py` | Copilot "close term" passes the actor. |
| `app/routers/academics.py` | `POST /terms/{id}/reopen`; close passes the actor. |
| `app/routers/results.py` | `GET /results/archives`, `GET /results/archives/{id}`. |
| `app/routers/schools.py` | `GET`/`PATCH /schools/me/results-policy`. |
| `app/schemas/academics.py` | Reopen request/response. |
| `app/schemas/results.py` | Cumulative and archive schemas; `ReportCard.cumulative`. |

### Shared contracts/client

- `TermReopenResultSchema`, `ResultsPolicySchema`, `TermArchiveSchema`,
  `TermArchiveDetailSchema`; `ReportCardSchema.cumulative`.
- `reopenTerm`, `fetchResultsPolicy`, `updateResultsPolicy`,
  `fetchTermArchives`, `fetchTermArchive` (+ `api.*` exports).

### Web

| File | Change |
| --- | --- |
| `app/(app)/settings/page.tsx` | Reopen button + reason prompt; Results policy card. |
| `app/(app)/reports/archive/page.tsx` | New archive browser and frozen-card viewer. |
| `components/report-card-document.tsx` | Session-average column and combined-term band. |
| `components/nav-config.ts` | Result Archive link + page metadata. |
| `hooks/use-api.ts` | Reopen/policy/archive hooks. |

### Tests

- `apps/api/tests/test_term_lifecycle.py` (new):
  - closing archives the cards; reopening reuses that archive, resets results,
    edits and recompiles, and the new card reflects the corrected score;
  - reopen rejects an open term and a too-short reason;
  - a term reopened after promotion still lists its three students in the score
    grid and report-card index, and still compiles/prints all three cards;
  - third-term cumulative average with three published terms (60/70/80 → term
    average 80, session average 70), and `null` when the policy is off or the
    term is not final.
- `apps/api/tests/test_results.py` etc. remain green.

## Verification run

```text
# new + regression API tests
tests/test_term_lifecycle.py tests/test_results.py tests/test_academics.py
tests/test_copilot_actions.py tests/test_copilot.py tests/test_promotion.py
tests/test_student_scope.py tests/test_tenancy.py tests/test_attendance.py
147 passed

tests/test_portal.py tests/test_result_access.py tests/test_report_card_templates.py
54 passed

# web
npx tsc --noEmit         clean
npm test                 8 files, 110 tests passed

# migration chain from an empty database
alembic upgrade head     0010 → … → 0016_term_result_archives
                         table, indexes and FKs verified with \d

# production build
npm run build            blocked by Next.js fetching the Inter font from
                         Google Fonts (no network in this environment); no
                         code/type error reported
```

## Operational notes

- **Archiving on close costs one card render per student.** It runs once per
  term close, not per score save, so closing a very large school's term is the
  slowest admin action in this feature. The schema does not change if that work
  is later moved to a background job. The payload is a JSONB document; the
  archive grows with terms × students, not with edits.
- **Historical terms use the whole class, not the current roster.** After
  promotion, old enrollments are `completed` and `is_current=False`. Score
  grids, the workbench, readiness, the report-card index and class standing now
  look at every enrollment in the term's class arm, so a reopened past term is
  usable rather than empty.
- **A policy change is not retroactive to archived cards.** An archive is the
  document as printed. Changing the policy affects future renders and future
  archives.
- **Reopening moves the school's current session/term back** to the reopened
  academic year. Activate the current term again when the correction is done.
- **No restore endpoint.** The archive is evidence; corrections are made by
  editing the reopened term, not by copying an old version forward.
