# School Copilot — Progress Log

A running, dated log of work on the school copilot so progress is easy to track.
For the *design* of the copilot and the report-card designer, see
[`COPILOT_AND_REPORT_CARD_DESIGNER.md`](./COPILOT_AND_REPORT_CARD_DESIGNER.md).

---

## 2026-09-24 — Admin commands actually fire; chat UX (delete + messenger look)

### Reported problem

In the running app, an admin command typed naturally did not work and the
copilot answered as if it could not do it at all:

> **User:** I want you to add Godiya Markus to nursery 2
> **Copilot:** I'm sorry, but I don't have the ability to add a student to a class…

…and the follow-up "can you give me the names of those students?" returned
nothing. Two separate causes:

1. **Command detection missed the phrasing.** `_ADMIT_HEAD` in
   `copilot_actions.py` only accepted `please / can you / could you / i want to /
   i'd like to`. The sentence "I want **you** to add …" matched none of them, so
   the turn was never seen as a command — it fell through to the LLM, which
   correctly said it cannot write. The bare "add Genesis John to Nursery 1" form
   worked, which is why the tests were green.

   Evidence (before the fix):
   ```
   OK   add Godiya Markus to nursery 2
   FAIL I want you to add Godiya Markus to nursery 2      <- the reported bug
   OK   please add Godiya Markus to nursery 2
   OK   can you add Godiya Markus to nursery 2
   ```

2. **A stale deployment is also possible.** If the running instance predates the
   admin-command work it will show the same "I can't do that" answer for *every*
   command shape. **Redeploy** after this change (see "Deploying" below).

### What changed

| # | Change | Files |
|---|---|---|
| 1 | **Polite preamble is stripped before parsing.** New `_POLITE` / `_strip_polite`; `detect_action` strips once up front so every detector sees the bare command. Handles `I want you to…`, `I want to…`, `I'd like you to…`, `I'd love to…`, `I would like you to…`, `kindly…`, `help me…`, `go ahead and…`, `let's…`, `please…`, `can/could/would/will you…`. | `apps/api/app/services/copilot_actions.py` |
| 2 | **Delete a chat from history.** `DELETE /copilot/conversations/{id}` (204; tenant-checked, messages cascade). Rail + chat-header trash buttons with a confirm. | `services/copilot_service.py` (`delete_conversation`), `routers/copilot.py`, `packages/shared/src/client.ts`, `apps/web/src/hooks/use-api.ts`, `apps/web/src/app/(app)/copilot/page.tsx` |
| 3 | **The intent label is gone from the UI.** Assistant bubbles now show just the time, not `intent class_roster · 05:37`. | `apps/web/src/app/(app)/copilot/page.tsx` |
| 4 | **Messenger-style chat window.** One rounded frame: a "Chats" sidebar (avatar, title, time, hover-trash), a chat header (bot avatar, title, status line, delete), bubbles left/right with tails, auto-scroll to the newest message, and a pill composer with a circular send button. On phones the sidebar collapses and a thread picker + New button appear in the header. | `apps/web/src/app/(app)/copilot/page.tsx` |
| 5 | **Tests.** Natural phrasing (propose → supply gender → confirm → enrolled), contracted politeness on a move, polite-phrasing subject creation, delete removes thread + messages, unknown thread is a 404. | `apps/api/tests/test_copilot_actions.py` |

### Verification (all green)

```
# API — 300 tests
cd apps/api && DATABASE_URL=... DEBUG=true COOKIE_SECURE=false ../../.venv/bin/python -m pytest -q -p no:warnings

# Web — 70 tests
cd apps/web && npm test

# Web typecheck
cd apps/web && npx tsc --noEmit
```

Plus a **live end-to-end run** against the real HTTP API (scratch database,
`DEBUG=true`), reproducing the exact reported sentence:

| Turn | Input | Result |
|---|---|---|
| 1 | `I want you to add Godiya Markus to nursery 2` | `intent=admit_student`, `source=command`, `status=pending`, `missing=[gender]`, class `Nursery 2` |
| 2 | `male` | `status=pending`, `missing=[]`, admission no `STU-2026-001` |
| 3 | `confirm` | `status=done` — student row + current enrolment to `Nursery 2` |
| — | — | `audit_logs`: `create` / `student` / "Admitted via the school copilot chat command" |
| 4 | `DELETE /copilot/conversations/{id}` | `204`, then `404`; `copilot_messages` for it = `0` |

### Deploying

The API and web must both be redeployed for this to take effect in the running
app; the command layer is API-side and the chat window is web-side.

---

## 2026-09-28 — The copilot runs the whole admin desk, not just admissions

### Reported problem

> **User:** move a student to another class
> **Copilot:** I don't have information about that…

`_detect_change_class` in `copilot_actions.py` required the pupil's name to sit
*immediately* before `to`/`into`:

```
(?:move|transfer|change)\s+(?P<name>.+?)\s+(?:to|into)\s+(?P<arm>.+?)\s*$
```

Any natural wording missed it, so the turn was never seen as a command: it fell
through to the LLM, which correctly said it cannot write. That is why a *bare*
"move Genesis John to Nursery 2" worked while the reported phrasing did not.

```
OK   move Genesis John to Nursery 2
FAIL move Genesis John from Nursery 1 to Nursery 2   <- a "from" clause
FAIL move Genesis John's class to Nursery 2          <- possessive
FAIL change the student Genesis John into Nursery 2  <- "the student"
```

### Fix

The regex now tolerates an optional `from …` clause, a leading `the`, and the
verbs `shift` / `promote` / `demote`; the scaffolding (`the`, `student`, `'s
class`) is stripped from the name phrase before it is resolved. A student who is
**not found** — or **ambiguous** — is answered inside the command layer ("I
couldn't find a student called …", or the list of matches), so a failed move can
never come back as the LLM's "I don't have that information".

| Change | Detail |
|---|---|
| `_detect_change_class` regex | optional `from …`; `(?:the\s+)?`; verbs `shift/promote/demote` |
| Name cleaning | strips `student`/`pupil`/`the` and `'s class`/`'s arm`/`'s section` |
| Not-found / ambiguous | honest `DirectReply` (candidates listed), never the LLM |

### Coverage: the whole admin desk

Enumerating the ~138 write endpoints in the API showed the command layer covered
admissions and a little academics only. Executors mirroring the admin endpoints
were added so the chat can now drive **30 commands** across the six domains the
school actually runs on. Every one still follows the three rules above — the
LLM is never on the command path, nothing writes without a `confirm`, and the
caller's real permissions are re-checked at propose time *and* at execution.

| Domain | Example you can type | Code | Needs |
|---|---|---|---|
| **Students & admissions** | `add Genesis John to Nursery 1` | `admit_student` | `students.create` + `students.enroll` |
| | `enrol Aisha Bello in Nursery 1` | `enroll_student` | `students.enroll` |
| | `move Genesis John to Nursery 2` | `change_class` | `students.enroll` |
| | `rename Aisha Bello to Aisha Okafor` | `update_student` | `students.edit` |
| | `remove student Tolu Coker` | `remove_student` | `students.delete` |
| | `promote JSS 1 A to JSS 2 A` | `promote_class` | `students.enroll` |
| | `add guardian Mary Bello for Aisha Bello` | `add_guardian` | `students.edit` |
| **Staff & logins** | `add teacher Grace Ade` | `add_staff` | `staff.create` |
| | `create a login for Grace Ade as teacher` | `create_staff_account` | `users.manage` |
| **Academic structure** | `create subject Further Mathematics` | `create_subject` | `academics.manage` |
| | `create class Nursery 3` | `create_class_arm` | `academics.manage` |
| | `create session 2027/2028` | `create_session` | `academics.manage` |
| | `create second term in 2025/2026` | `create_term` | `academics.manage` |
| | `activate session 2026/2027` | `activate_session` | `academics.manage` |
| | `activate first term` / `close first term` | `activate_term` / `close_term` | `academics.manage` |
| | `add Mathematics to JSS 1 A` | `add_offering` | `academics.manage` |
| | `assign Grace Ade to Mathematics in JSS 1 A` | `assign_teacher` | `academics.manage` |
| **Attendance** | `mark JSS 1 A present today` | `mark_attendance` | `attendance.mark` |
| **Results** | `submit / verify / approve / publish / compile results for JSS 1 A` | `*_results` | the matching results permission |
| **Users, roles & school setup** | `create role Bursar with permissions fees.view, fees.collect` | `create_role` | `roles.manage` |
| | `rename the school to Brightfield Academy` | `update_school` | `school.manage` |
| | `add campus Ikeja` | `add_campus` | `campus.manage` |
| **Finance** | `create a fee structure called School Fees of 50000` | `create_fee_structure` | `fees.create` |
| | `raise an invoice for Aisha Bello for School Fees` | `create_invoice` | `fees.create` |
| | `record a payment of 50000 from Aisha Bello` | `record_payment` | `fees.pay` |

`command_help()` — served in chat when a user asks "help" / "what can you do" —
renders these examples straight from `COMMAND_EXAMPLES`, so the help text can
never drift from the code. `create_staff_account` shows its one-time temporary
password **once**, in the confirmation reply; it is never stored in clear.

### Bugs found and fixed while adding the commands

| # | Bug | Fix |
|---|---|---|
| 1 | A role command that *named* `results.*` permissions (`create role X with permissions results.verify`) was caught by the results detector and read as a results run. | `_detect_results_action` bails out when the sentence names `role`/`permission`/`login`/`account`/`campus`; `create_role` no longer fires on its own permission list. |
| 2 | `create role Bursar with permissions …` kept the word `with` in the parsed role name. | `with` added to the stripped stop-word regex. |
| 3 | A confirmed finance command 500'd a chat turn: a `Decimal` amount reached the `audit_logs` JSONB insert (`Object of type Decimal is not JSON serializable`). | New `_json_safe()` (Decimal → float, UUID → str, recursive) applied in `_audit()`; the fee-structure executor also emits `float(amount)`. |
| 4 | `test_add_a_campus` read the wrong row — registration seeds a "Main Campus", so an unfiltered `select(...)` picked that instead of the new campus. | Test asserts on `Campus.name == "Ikeja"`. |

### Tests

23 new cases in `apps/api/tests/test_copilot_actions.py` (49 in the file):

- the reported move bug (`test_move_student_with_from_clause_works`,
  `test_move_student_possessive_class_phrasing`,
  `test_move_unknown_student_never_reaches_the_llm`);
- students (`enrol` without duplicating, `remove` soft-deletes, rename, gender
  change, promote a class, add a guardian);
- academics (activate a session, activate + close a term, add a subject to a
  class, assign a teacher);
- attendance (mark a whole class present, mark one pupil absent);
- roles/users/school setup (create a role with permissions, create a staff login
  and show the password once, rename the school, add a campus);
- finance (structure → invoice → payment end-to-end, an honest refusal when the
  pupil has no invoice, and permission denials for finance and attendance).

### Verification

```
cd apps/api && DATABASE_URL=... DEBUG=true COOKIE_SECURE=false \
  ../../.venv/bin/python -m pytest tests/test_copilot.py tests/test_copilot_actions.py -q -p no:warnings
# 69 passed (test_copilot 20 + test_copilot_actions 49), exit 0
```

The wider API suite is 323 tests; on this machine Postgres checkpoints are slow
enough that a single full-suite run exceeds the command budget, so it was
verified in the two-file batch above plus the earlier baseline.

### Not yet on the command path

Honest gaps, by design rather than oversight — the biggest remaining admin
surfaces are:

- **Whole modules** never exposed to chat: payroll, accounting, inventory,
  library, lesson plans, question banks, bulk CSV imports, file uploads, and the
  report-card designer (`report_card_templates`).
- **Results:** per-subject score entry (`results.enter`) and comments/remarks —
  the chat drives the submit→publish *pipeline* only.
- **Edits/deletes** of academic structure (edit/delete a subject, delete an arm,
  session or term, remove a teacher assignment, generate the timetable).
- **Staff lifecycle** beyond creation: edit, deactivate/reactivate, reset a
  staff password.
- **Users & roles** beyond creation: edit a role's permissions, deactivate a
  login, superadmin actions (impersonation, plan changes, platform settings).
- **School setup** beyond name + campus: logo, contact details, school-wide
  settings.
- **Finance** beyond the three: edit a fee structure, toggle its status, email a
  receipt, refunds, expenses.

---

## Still open

1. **Redeploy** the API + web so the running instance carries this change.
2. **Manual/browser pass** on `/copilot`: send a command, supply the gender,
   `confirm`, then check `/students` and the audit log; then delete a chat and
   confirm it leaves the rail.
3. **While a required field is missing, a question is not answered** — the
   copilot stays on the command and re-asks (by design, pinned by
   `test_half_specified_command_keeps_asking_and_offers_cancel`). Worth a UX
   revisit if users find it confusing: today "give me the names of those
   students" mid-admission re-asks for the gender instead of listing the class.
4. **Optional follow-ups** for the chat: rename a chat, search the rail, and a
   "delete all chats" action.
5. **Widen command coverage** — see "Not yet on the command path" above;
   payroll/accounting/inventory/library are the largest untouched surfaces.
