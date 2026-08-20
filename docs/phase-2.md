# SchoolOS — Phase 2: Result approval workflow → report cards → public portal → AI remarks → AI lessons & questions

**Status:** built and verified through **seven slices** — the approval workflow,
report cards, the public PIN result portal, metered AI result remarks, metered
AI lesson plans + question banks (all behind `results.comment`), and the
**school copilot** (gated `ai.copilot`). Backend suite green (**73 passed**),
web production build clean (19 routes incl. `/portal`, `/lesson-plans`,
`/question-banks`, `/copilot`), and every slice exercised end-to-end through the
HTTP API and live dev DB.

---

## 1. What was built

The first slice of Phase 2: the **review funnel** a school runs results through
before they reach parents — a strict, permission-gated, append-only state
machine on top of the Phase 1 results engine.

| Piece | What it does |
| --- | --- |
| **State machine** | `draft → submitted → verified → approved → published`, with rejection at each checked stage bouncing rows back to `draft`. Enforced in `results_service` (`_transition`), journaled to `result_events`. |
| **Verify** | `POST /api/results/verify` — moves every **submitted** result of one arm×subject×term to `verified`. `ERR_CONFLICT` (409) if nothing is at the submitted stage. |
| **Approve** | `POST /api/results/approve` — moves **verified** → approved, stamping `approved_at`/`approved_by` on every row. |
| **Publish** | `POST /api/results/publish` — moves **approved** → published, freezing `published_snapshot` (total, grade letter/point, remark, position, per-component scores) so report cards and the future portal render immutable totals. |
| **Reject** | `POST /api/results/reject` — an approver bounces **submitted/verified/approved** rows back to draft with a required `reason`, clearing `submitted_at` and unlocking score re-entry by the assigned teacher. |
| **Workbench** | `GET /api/results/workbench?term_id=…` — per arm×subject, where each stage of the funnel stands: `enrolled / entered / draft / submitted / verified / approved / rejected / published`. Rows are self-contained: each carries `arm_id`, `term_id`, `subject_id` so the UI can act on a row without threading query state. |
| **Audit** | Every transition appends a `ResultEvent` (actor, action, from/to, note, timestamp) — append-only, the same journal Phase 1 used for submit. |

## 1b. Web workbench UI

`/approvals` (linked from the sidebar and the Results hub) is the approvers'
screen: a term picker, one card per class arm, and a row per subject showing
live stage pills (`draft / submitted / verified / approved / bounced /
published`) plus the next step as a one-click button. Reject opens an inline
reason field (required, `ERR_VALIDATION` if empty) that bounces the row back
to draft. A teacher's submit entry point stays on the score grid ("Submit
verified"). The React Query hooks `useWorkbench` / `useResultAction` refresh
the workbench, readiness, and scorecard queries after every action so stage
counts stay consistent across screens.

## 2. Permission model

New catalog permissions in `app/core/permissions.py`, provisioned into the
role templates (academics-committee → verify/approve/comment, principal →
publish):

- `results.verify` — verify submitted results
- `results.approve` — approve verified results; also the gate for **reject**
  (an approver bounces work back)
- `results.publish` — publish approved results
- `results.comment` — reserved for principal/head-of-academics remarks
  (report-card notes, Phase 2 slice 2)

The founding admin is a super admin and bypasses all gates (`is_superadmin`),
so the demo account can drive the whole funnel.

## 3. State machine rules

- **Transitions are set-based**: one call moves *every* result of an
  arm×subject×term from the required source state. Rows not at the source
  state are left untouched; if the call moved nothing it returns
  `ERR_CONFLICT` (409) instead of silently succeeding.
- **Draft is the only editable state.** `save_scores` refuses any cell whose
  result has left draft (`ERR_RESULT_LOCKED`). Rejection is how a review
  unlocks re-entry.
- **Enrollments without scores stay draft** through submit, so the readiness
  dashboard keeps showing them as pending; they never block the funnel.
- **Published is terminal.** Snapshot freezing means later re-grading can't
  silently change a published report; any correction path is a new slice of
  the roadmap.

## 4. Files changed

- `app/core/permissions.py` — 4 new permission codes + catalog + role templates
- `app/services/results_service.py` — `_transition`, `verify_arm_subject`,
  `approve_arm_subject`, `publish_arm_subject`, `reject_arm_subject`,
  `_build_published_snapshot`, `workbench_for_term` (rows carry `term_id`);
  fixed a stray docstring fragment that had left the module un-importable
- `app/schemas/results.py` — `SubjectActionRequest`, `RejectRequest`,
  `WorkbenchRow` (+ `term_id`)
- `app/routers/results.py` — `POST /verify|approve|publish|reject`,
  `GET /workbench`
- `tests/test_results.py` — 6 new tests (pipeline, approver stamp + publish
  freeze, reject → draft + journal + re-entry, reject requires reason,
  reject-of-draft conflict, workbench stage counts incl. `term_id`)
- `packages/shared/src/contracts.ts` — `WorkbenchRowSchema` + `term_id`
- `packages/shared/src/client.ts` — `fetchWorkbench`, `reviewResults`
  (`ResultAction`), `api` exports
- `apps/web/src/hooks/use-api.ts` — `useWorkbench`, `useResultAction`
- `apps/web/src/app/(app)/approvals/page.tsx` — the workbench UI
- `apps/web/src/components/app-shell.tsx` — `/approvals` nav item
- `apps/web/src/app/(app)/results/page.tsx` — Approvals card linking the hub

No migration: `approved_at`/`approved_by`/`published_at`/`published_snapshot`
were already on the `results` model (baseline migration uses
`Base.metadata.create_all`).

## 5. Verification results

| Check | Result |
| --- | --- |
| `pytest -q` (`schoolos_test`) | **28 passed** (23 approval-phase + 5 report-card), 0 failed |
| `npm run build` (`apps/web`) | clean — `/approvals` + `/reports` routes included |
| Verify-before-approve | 409 `ERR_CONFLICT` |
| Double-verify / double-publish | 409 `ERR_CONFLICT` — nothing silently lost |
| Approve stamping | `approved_at` + `approved_by` set on all rows |
| Publish snapshot | every row has frozen `total/grade_letter/position/components` |
| Reject | rows back in `draft`, `submitted_at` cleared, event `note = reason`, scorecard editable again |
| Workbench | `enrolled=3, entered=2, draft=3 → submit → submitted=2, draft=1` (unscored student stays pending) |
| Report index | 3 students listed, `subjects_published=0` → all `1`, `total=60.0` after Mathematics published |
| Report card | renders only published subjects from snapshots (`total=60, C4/Credit`), excludes approved-but-unpublished English |
| Report 404 | student with no published results → `ERR_NOT_FOUND` |

## 6. Report cards (Phase 2 slice 2)

The printed artifact the approval funnel feeds: **`GET /api/results/report-card?student_id=&term_id=`**
renders one student's term report **only from `published_snapshot`** — a published result is
immutable, so a printed card can never silently disagree with the school's records. A sibling
endpoint **`GET /api/results/report-index?arm_id=&term_id=`** lists every enrollment in the arm
with how many subjects have cards ready (drive the "pick a student" UI and show who is pending).

| Field | Meaning |
| --- | --- |
| `subjects` | Per published subject: snapshot total, `grade_letter`, `grade_point`, `remark`, per-subject `position`, and each component's score as frozen at publish. Ordered by subject name. |
| `summary.total` | Sum of published subject totals |
| `summary.average` | Mean of published subject totals; graded through the session's scale (`_grade_for`) |
| `summary.class_rank` / `class_size` | Standing over classmates who have ≥1 published subject (aggregate total, strict desc ranking) |

Behavior notes:
- Subjects still in review are **absent**, not blank — a card shows exactly what has been
  approved and published.
- `404 ERR_NOT_FOUND` when the student has no published results (or isn't enrolled in the
  term's session) — the UI shows "no published results yet".
- Web: `/reports` (sidebar "Report cards" + Results hub card) — term/arm pickers, a student
  grid showing publish coverage, and a print-friendly card with dynamic component columns
  (union across subjects, e.g. CA1 | CA2 | Exam) and a print button (`window.print`).

## 7. Verification results (slice 3, portal)

| Check | Result |
| --- | --- |
| Full suite `pytest -q` (`schoolos_test`) | **39 passed** — 28 approval+report-card + 11 portal, 0 failed |
| `npm run build` (`apps/web`) | clean — `/portal` route included (16 routes) |
| Live E2E (throwaway school, real dev DB) | register → score → publish → set PIN → PIN-check → public report card `total=67.0`, all checks green |
| Non-enumeration | wrong PIN / unknown admission / unknown school each → identical `ERR_NOT_FOUND` "Invalid portal credentials" |
| Token hygiene | malformed token, normal (user-scope) access token, and expired portal token all → 404; portal scope required |
| PIN rotation | second set revokes the old live row (kept for audit), old PIN no longer resolves |
| Published-only | public card renders subjects **only** from `published_snapshot`; nothing in review appears |

## 8. Public result portal (Phase 2 slice 3)

A **PIN-gated, published-only** read portal for students & parents — no login, no tenant header.
It is deliberately narrow and defensive:

- **`GET /api/public/schools`** — schools that run the portal (a plain public catalog).
- **`POST /api/public/pin-check`** — `{school_slug, admission_no, pin}` → a short-lived JWT
  (`scope=portal`, `sub`=student, `school`=school, 30-min expiry) plus a student summary.
  Every failure mode (unknown school, unknown admission no, wrong PIN) answers the **same**
  generic `ERR_NOT_FOUND` so the endpoint cannot be used to enumerate students or their PINs.
- **`GET /api/public/report-card?token=&term_id=`** — the student's latest published card
  (or a given term). Decodes the portal token, then renders through the same `report_card`
  service the staff route uses — so it is **published data only, by construction**.

PINs are **never stored in plaintext**: `pin_hash` is SHA-256 of
`school_id:student_id:pin` (implicit salt), compared with `hmac.compare_digest`.
Rotation **replaces** the live row — the old row is kept with `revoked_at` for audit, and the
DB enforces *one live PIN per student* with a partial unique index
(`uq_student_pin_one … WHERE revoked_at IS NULL`) rather than a plain unique constraint,
which would have blocked keeping audit history.

Web:
- `/portal` (public, linked from `/login`) — school dropdown + admission no + PIN form,
  then a print-friendly published report card (`window.print`).
- Admin **Set PIN** control per student on `/students` (`students.edit`), 4–6 digit
  input, live-PIN revocation on rotation.

New/changed files this slice:
- `app/models/portal.py` (`StudentPin`, partial-unique live rows), `app/models/__init__.py`
- `app/core/security.py` — `create_portal_token` / `decode_portal_token` (`scope=portal`)
- `app/services/portal_service.py` — `set_student_pin`, `resolve_pin`,
  `latest_published_term_id`, `report_card_for_portal`
- `app/schemas/portal.py`, `app/routers/portal.py` (`/public/*`), `app/routers/students.py`
  (`PUT /students/{id}/pin`), `app/main.py`
- `tests/test_portal.py` — 11 tests (permission gate, rotation+audit rows, digits-only,
  generic 404s, revoked PIN, bad/expired/wrong-scope tokens, published-only card,
  live `last_used_at`, public schools)
- `packages/shared/src/contracts.ts` + `client.ts` — `publicSchools`/`pinCheck`/
  `publicReportCard`/`setStudentPin`, `SchoolBrief`/`PinCheckOut`/`PinSetOut` schemas
- `apps/web/src/hooks/use-api.ts` — `useSetStudentPin`
- `apps/web/src/app/portal/page.tsx` (new public page), `apps/web/src/app/(app)/students/page.tsx`
  (Set PIN control), `apps/web/src/app/login/page.tsx` (portal link)

DB: `student_pins` is additive; alembic uses `Base.metadata.create_all`, so the table
was created on the dev DB with `Base.metadata.create_all(tables=[StudentPin.__table__])`.

## 9. AI result comments (Phase 2 slice 4) — `results.comment` + `ai_usage` metering

The last Phase 2 roadmap item's first half: **AI-written principal remarks on
published report cards**, gated on the already-provisioned `results.comment`
permission and metered for real into the already-provisioned `ai_usage` /
`usage_meters` tables.

What was built:

| Piece | What it does |
| --- | --- |
| **`result_comments`** | One stored remark per (school, term, student enrollment) — `body`, `provider`, `model`, `revision` (bumped on regeneration), `generated_by`, `generated_at`, unique `(school_id, term_id, student_enrollment_id)`. |
| **`ai_service.generate_result_comment`** | Gated by `results.comment`. Reads the student's *published* report card (frozen snapshots only — the same `report_card` service the portal uses), composes a personalized narrative, upserts the comment row (`revision += 1` on regeneration), then **meters**: one `AiUsage` row (feature `ai.result.comment`, provider/model, tokens-in/out estimates, cost, latency) + one monthly `UsageMeter` bump (`ai.result.comment`, period `YYYY-MM`). |
| **`ai_service.get_result_comment`** | Read the stored remark (`results.view`); 404 when never generated. |
| **Routes** | `POST /api/results/{student_id}/comment?term_id=` (results.comment) → generate/regenerate; `GET /api/results/{student_id}/comment?term_id=` (results.view) → read. |
| **Engine honesty** | The engine is local + deterministic + data-grounded: it quotes actual subject names, totals, and class standing — no invented sentences, no fake API calls. The metering seam is exercised for real, so wiring a paid model provider later only swaps the composition function; permissions, storage, and telemetry stay. |

Web: on `/reports`, once a card is loaded a **Principal's remark** block (hidden
from print) offers a **Generate/Regenerate comment** button — visible only to
members whose active role carries `results.comment`. The remark reads from the
deterministic engine, so the same published card always yields the same prose.

Verification:
- Backend suite now **45 passed** (6 new AI-comment tests: permission gate 401/403,
  comment + metering write, subject-name grounding, revision bump + re-meter on
  regeneration, 404 without published results, 404 on missing GET).
- `npm run build` clean.
- Live E2E on the dev DB: register → score 85 → publish → generate
  (`"Mathematics (85)"` cited by name) → GET → regenerate (rev 1→2, same body) →
  exactly 2 `ai_usage` rows + `usage_meters` count 2.

## 10. AI lesson plans (Phase 2 slice 5) — same metering seam as remarks

The AI features now span **result remarks** (slice 4) and **lesson plans**
(this slice) on the identical seam: gated by `results.comment`,
local + deterministic + data-grounded, and every generation metered one-for-one
into `ai_usage` + the monthly `usage_meters` rollup. No fake LLM calls; wiring a
real provider later only swaps the composition function and keeps
permissions/storage/telemetry.

What was built:

| Piece | What it does |
| --- | --- |
| **`lesson_plans`** | One stored plan per (school, term, subject, class level, topic) — `plan` JSONB, `provider`, `model`, `revision` (bumped on regeneration), `generated_by`, `generated_at`. Unique `(school_id, term_id, subject_id, class_level_id, topic)` so regenerate upserts the same cell. |
| **`ai_service.generate_lesson_plan`** | Gated by `results.comment`. Validates the subject/class/term belong to the school (404 `ERR_NOT_FOUND` otherwise), composes a plan grounded in the real subject/class/term names + topic + period count, upserts the cell row (`revision += 1` on regeneration), then meters exactly once (`ai.lesson.plan`, `schoolos-lesson-v1`). |
| **`_compose_lesson_plan`** | Deterministic, strand-shaped: a small `_SUBJECT_STRANDS` table chooses the working vocabulary (math → *calculate/solve*, science → *investigate/predict*, language → *read/write/explain*, humanities → *describe/discuss*) so every subject renders through its own voice — pinned by a test that a maths topic and a Civic Education topic never share wording. Output is a directly usable lesson: title, objectives, materials/aids, 4-phase procedure (Introduction 10 → Development → Evaluation 10 → Conclusion 5, times derived from `periods × 40 min`), homework, differentiation teacher-note. |
| **`ai_service.get_lesson_plan`** | Read the saved plan (`results.view`); 404 when never generated. |
| **Routes** | `GET/POST /api/lesson-plans` — GET by `term_id+subject_id+class_level_id+topic`, POST with the same cell + `periods` (1–10). |

Web: `/lesson-plans` (sidebar "Lesson plans", notebook icon). Term pills, class
level → subject (from actual offerings), topic and period inputs; one-click
**Generate plan** (or **Regenerate plan** when the cell already has one). The
generated plan renders as a printable card — overview badges, objectives,
materials, timed procedure, homework, differentiation note. The Generate button
is hidden for roles without `results.comment` (viewers see a note); the page
auto-loads the existing plan for whatever cell is currently selected.

Verification:
- Backend suite now **52 passed** (7 new tests in `test_lesson_plans.py`:
  POST gated 401/403 by `results.comment` while GET is `results.view`, plan +
  JSONB + metering write, strand wording pinned per subject, regeneration bumps
  revision 1→2 with identical content and re-meters, 404 for an unknown subject,
  404 GET for an ungenerated cell).
- `npm run build` clean — `/lesson-plans` route included. (One fix along the
  way: the page used `Badge variant="outline"`, which this project's shadcn
  Badge doesn't define — swapped to the existing `"muted"` variant.)

## 11. AI question banks (Phase 2 slice 6) — another cell on the metering seam

The AI line now spans three engines on the identical seam introduced in slice
4: **result remarks**, **lesson plans**, and this slice — **question banks**.
All gated by `results.comment` (POST) / `results.view` (GET), all local +
deterministic + data-grounded, and every generation metered one-for-one into
`ai_usage` + the monthly `usage_meters` rollup.

What was built:

| Piece | What it does |
| --- | --- |
| **`question_banks`** | One stored bank per (school, term, subject, class level, topic) — `bank` JSONB, `provider`, `model`, `revision` (bumped on regeneration), `generated_by`, `generated_at`. Unique `(school_id, term_id, subject_id, class_level_id, topic)` so regenerate upserts the same cell. |
| **`ai_service.generate_question_bank`** | Gated by `results.comment`. Validates the subject/class/term belong to the school (404 `ERR_NOT_FOUND` otherwise), composes a strand-shaped bank grounded in the real subject/class/term names + topic + question `count`, upserts the cell row (`revision += 1` on regeneration), then meters exactly once (`ai.question.bank`, `schoolos-question-v1`). |
| **`_compose_question_bank`** | Deterministic practice set: five templates (how to start work, which practice builds understanding, best supporting material, how to self-check, how to prepare for a short test) cycled to the requested count. Each item is a 4-option MCQ whose **correct answer is the strand's own statement, true by construction**, with the *other* strands' statements as distractors — so a maths bank never marks essay language correct and a humanities bank never marks calculating correct. The correct option is rotated deterministically (never a fixed letter) and every item carries a rationale. |
| **`ai_service.get_question_bank`** | Read the saved bank (`results.view`); 404 when never generated. |
| **Routes** | `GET/POST /api/question-banks` — GET by `term_id+subject_id+class_level_id+topic`, POST with the same cell + `count` (1–10). |

Web: `/question-banks` (sidebar "Question bank", help-circle icon). Identical
composer shape to `/lesson-plans` — term pills, class level → subject (from
actual offerings), topic and question-count inputs; one-click **Generate bank**
(or **Regenerate bank** when the cell has one). The bank renders as a printable
set of question cards with the flagged answer highlighted and its rationale.
Generate is hidden for roles without `results.comment`; the page auto-loads the
existing bank for the current cell.

Verification:
- Backend suite now **60 passed** (8 new tests in `test_question_banks.py`:
  POST gated 401/403 by `results.comment` while GET is `results.view`, bank +
  JSONB + metering write with full item shape, correct-answer strand wording
  pinned (math calculate/solve, humanities explain/discuss and never
  calculate), regeneration bumps revision 1→2 with identical content and
  re-meters, `count` respected, 404 for an unknown subject, 404 GET for an
  ungenerated cell).
- `npm run build` clean — `/question-banks` route included.

## 12. School copilot (Phase 2 slice 7) — free-form Q&A over the school's own data

The final Phase 2 roadmap item, and the end of the AI line: a conversational
**copilot** that answers questions about the school from its own records. Like
every engine before it, it honors "no fake implementations" — local,
deterministic, data-grounded, and metered one-for-one on the same seam.

What was built:

| Piece | What it does |
| --- | --- |
| **`copilot_conversations` / `copilot_messages`** | Two new school-scoped tables. A conversation carries an optional `term_id` scope (results questions resolve to it by default) and a small JSONB `context` of last-resolved slots (arm / subject / level / student); messages store `role` (user/assistant), `content`, `intent`, and `answer_payload` (the JSONB facts the UI renders as cards). |
| **Intent engine** (`copilot_service.ask_copilot`) | Tokenizes the question → matches one of nine intents by keyword groups → resolves named slots against the school's real rows → composes a grounded prose answer + a facts payload. Follow-ups ("what about English?", "how many boys?") resolve from the conversation's context. Gated `ai.copilot`. |
| **Published-only rule** | Performance intents — top performers, subject average, term summary, student report — read **exclusively** from `Result.status == PUBLISHED` frozen `published_snapshot`; a student who was never scored/published is never quoted. Entry-progress (readiness) reads live counts by design. |
| **Honest unknown** | A question no intent matches gets a plain "I couldn't understand… here's what I can answer" — never a fabricated number — and is still metered. |
| **Metering** | Every assistant turn writes exactly one `AiUsage` + one monthly `UsageMeter` bump under `ai.copilot` / `schoolos-copilot-v1` via `ai_service._meter_inc` — wiring a real LLM later only swaps the composition function. |
| **Routes** | `POST /api/copilot/ask` (creates/resumes a conversation, returns conversation + assistant message), `GET /api/copilot/conversations`, `GET /api/copilot/conversations/{id}` (detail incl. messages), `GET /api/copilot/intents` (drives suggested-question chips). All gated `ai.copilot`; cross-school conversation access is a neutral 404. |
| **Permission** | `ai.copilot` in `ROLE_TEMPLATES` for director, principal, vp_academics, head_teacher, academic_coordinator (the leadership roles that already hold `results.comment`); existing schools reconciled by `sync_role_templates` on seed. |

Web: `/copilot` (sidebar "Copilot", bot icon). A chat UI with a saved-conversation
rail, term-scope pills for new chats, suggested-question chips when a thread is
empty (from `/copilot/intents`), user/assistant bubbles, and payload cards —
count stats, a top-3 performers table, per-arm readiness bars. Asking is hidden
without `ai.copilot`; a footline states the engine (`schoolos-copilot-v1`,
deterministic, metered). The `useAskCopilot` mutation seeds the thread cache
from the ask response so a new answer renders instantly while a background
refetch confirms.

Verification:
- Backend suite now **73 passed** (13 new tests in `test_copilot.py`: ask and
  intents gated 401/403 by `ai.copilot`; overview/class-snapshot counts match
  the seeded world; top performers read published-only (an entered-but-
  unpublished student excluded); subject average = published mean; term summary
  requires a term scope then respects it; gendered follow-up resolves its arm
  from context; conversation history shape; unknown question answers honestly
  and still meters one `AiUsage` + one `UsageMeter` per turn; school B cannot
  read school A's thread — neutral 404).
- `npm run build` clean — `/copilot` route included.

## 13. Beyond Phase 2

Phase 2 is complete. Finances, attendance and scheduling stay on the broader
roadmap (`README.md`).