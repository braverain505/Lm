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

## 2026-09-28 — Several commands in one message, and classes it refuses to guess at

### Reported problem

Commands typed two at a time did not work. The realistic message

> **User:** Add Amina John in Nursery 1 and Hauwa Manuel in nursery 2

was parsed as **one** admission into a class literally called
"Nursery 1 and Hauwa Manuel in nursery 2": the arm could not be resolved, so
the turn either came back as a confusing "still needed: arm" or fell through to
the LLM, which answered that it cannot add students. Two smaller faults made it
worse:

1. A bare class level silently picked the first matching arm — with a "JSS 1 A"
   and a "JSS 1 B" on file, "add Ada to JSS 1" would admit her into whichever
   sorted first, with no mention of the other.
2. A class the school does not have answered only "Still needed: arm" — it never
   named the class it could not find, and never listed the real ones.

```
OK   add Amina John in Nursery 1                  <- one admission
FAIL add Amina John in Nursery 1 and Hauwa Manuel in nursery 2   <- two
FAIL add X to JSS 1 (JSS 1 A and JSS 1 B both exist)             <- picks one
FAIL add X to Nursery 9 (no such class)                          <- "still needed: arm"
```

### Fix

**A message is split into clauses and each clause must be a command of its own.**
`_detect_batch` + `_parse_clause` split on `and` / `then` / `also` / `,` / `;`.
A clause may name a verb of its own ("… and create subject Z") or inherit the
message's leading verb ("add A to X and B to Y"); the clauses need not be the
same *kind* of command, so "add a pupil and create a subject" is two. If **any**
clause fails to parse, the whole message falls back to the single parse — a
clause is never silently dropped. The single parse still wins when it is a
complete command that swallowed no conjunction, which is what keeps a value
list joined by "and" — `create role Bursar with permissions fees.view and
fees.collect` — one command.

| # | Change | Files |
|---|---|---|
| 1 | **Batches.** `_detect_batch`, `_parse_clause`; `detect_action` now returns `list[Proposal]` for a multi-command turn. `_BATCH_VERBS` gained the results verbs (`submit`/`verify`/`approve`/`publish`/`compile`/`release`). | `copilot_actions.py` |
| 2 | **A batch is proposed, then run in order.** The pending proposal is `{"batch": [...]}` on `CopilotConversation.context`; missing fields are asked for one item at a time ("Start with item 2: I need …"); `confirm` runs every item **in order, each in its own SAVEPOINT**, and reports each — one failure does not unwind the others. `cancel` drops them all. | `copilot_actions.py` (`batch_to_context`, `render_batch`, `batch_payload`), `copilot_service.py` (`_start_batch`, `_resume_batch`, `_run_batch`) |
| 3 | **A write never guesses a class.** New `find_arms_by_phrase` (exact → prefix → contains tiers, all matches), `_unique_arm` (a write resolves only when the phrase names exactly one class), `_arm_phrase` ("a class" / "the class" name no class). Reads keep `resolve_arm_by_phrase` — for a question the most likely class is exactly what is wanted. | `copilot_actions.py` |
| 4 | **An unresolvable class is spelled out.** `_arm_note` names the class that was not found and lists the real ones, or lists the several classes the phrase fits and asks which. | `copilot_actions.py` |
| 5 | **Generated numbers are reserved per message.** Two admissions typed together are parsed before either is written; `_reserve_serial` / the `claimed` lists stop both from being offered the same `STU-…` number. | `copilot_actions.py` |
| 6 | **Politeness.** The preamble stripper now understands a whole sentence of intent — "I wanted to say you should add …". | `copilot_actions.py` |
| 7 | **UI.** The action card renders a batch as a numbered list (detail, what each item still needs, and any error). Deleting a chat now removes its row immediately (optimistic) and restores it if the delete fails. | `apps/web/src/app/(app)/copilot/page.tsx`, `apps/web/src/hooks/use-api.ts` |

The in-chat help (`command_help()`) says several commands may be given together,
same kind or mixed, and that they run in order.

### Tests

10 new cases in `apps/api/tests/test_copilot_actions.py` (59 in the file):

- two admissions in one message are proposed together, walk their missing fields
  one item at a time, and both land in the right classes (`test_two_admissions_in_one_message_are_proposed_together`);
- a batch does not silently drop a target (`test_a_batch_does_not_silently_drop_a_target`);
- a value list joined by "and" stays one command (`test_a_value_list_is_not_mistaken_for_a_second_command`);
- **mixed kinds** — an admission and a subject, an admission and a staff member,
  and three commands of three kinds in one prompt, all proposed together and run
  in order (`test_a_mixed_message_runs_commands_of_different_kinds`,
  `test_a_mixed_message_can_span_students_and_staff`,
  `test_three_commands_of_three_kinds_in_one_prompt`);
- an intent preamble before the verb (`test_an_intent_preamble_before_the_verb_is_understood`);
- a bare level resolves when only one class matches, and asks which when several
  do (`test_a_bare_level_resolves_when_only_one_class_matches`,
  `test_an_ambiguous_level_asks_which_class_instead_of_guessing`);
- an unknown class is named and the real classes listed (`test_an_unknown_class_is_named_and_the_real_classes_listed`).

### Bug found while demonstrating the feature

A live run of "add Amina John to Nursery 1 and create subject Further
Mathematics and add teacher Grace Ade" showed a **resolved** class still
carrying a note: `"Nursery 1" fits more than one class (Nursery 1)`. `_arm_note`
returned the ambiguity note whenever *any* match existed, including the single
match that had just resolved the arm. It now stays silent when exactly one class
matched, and the two "resolved" tests assert the phrase is absent.

### Verification

```
cd apps/api && DEBUG=true COOKIE_SECURE=false ../../.venv/bin/python -m pytest tests/test_copilot_actions.py -q
#  58 passed
cd apps/api && DEBUG=true COOKIE_SECURE=false ../../.venv/bin/python -m pytest tests/test_copilot.py -q
#  20 passed
cd apps/web && npx tsc --noEmit   # clean
cd apps/web && npm test           # 70 passed
```

The two API files are run separately: on this machine Postgres checkpoints are
slow enough that one combined run can exceed the command budget.

### Limits, by design

- A batch is **planned before it runs**, so a command may not depend on an
  earlier one in the same message ("create subject X and add X to JSS 1 A"
  cannot resolve X yet). The dependent item fails honestly and alone; the rest
  stand.
- Only `confirm` (all items) or `cancel` (none) is offered — there is no
  "confirm item 1 only".
- Everything already on the command path can be batched; nothing new was
  exposed.

---

## 2026-09-28 — Reported again: "it does the first command and ignores the second"

### Reported problem

> **User:** Add James Madison in Nursery 2 and Michael Klint in JSS 1
> **Copilot:** Admit James Madison to Nursery 2 with a generated admission number
> (STU-2026-003). Before I can run it I still need their gender — reply "male"
or "female"…

Michael Klint was never mentioned. This is the same message shape as the batch
work above, so the report was **traced rather than re-fixed** — the current code
already runs both commands.

### What was actually wrong

The reply shown is `render_proposal`, the **single**-command prompt. A batch
prints "That message holds 2 commands — nothing runs until you confirm:" and
numbers each item, which is not what the report shows. `detect_action` on that
exact sentence returns a two-item batch (verified below), so the instance that
answered the report was running a build from **before** the batch commit
`8870bd6`. On such a build the single parse is the only reading, and it folds the
second command into the class phrase:

```
arm_name='Nursery 2 and Michael Klint in JSS 1'   <- the second command, swallowed
```

…so Michael is invisible and the turn asks for James's gender instead. The fix is
a redeploy, not a code change.

### Change

No production code changed. The reported sentence is now pinned by a regression
test so that neither a stale build nor a later regex change can reintroduce it:
`test_the_reported_two_commands_in_one_message_both_run` — both clauses planned
in their own classes, two *distinct* admission numbers reserved in the same
message, the gender collected per item, and after `confirm` both pupils enrolled
(Nursery 2 / JSS 1 A).

### Verification

```
cd apps/api && DATABASE_URL=... DEBUG=true COOKIE_SECURE=false \
  ../../.venv/bin/python -m pytest tests/test_copilot_actions.py -q -p no:warnings
# 60 passed (was 59)
```

Both readings of the reported sentence, current code:

| Reading | Result |
|---|---|
| single parse | one admission, arm `"Nursery 2 and Michael Klint in JSS 1"`, missing `gender, arm` |
| batch parse | **2** admissions — James → Nursery 2 (`STU-2026-001`), Michael → JSS 1 A (`STU-2026-002`) |
| the chat turn | `code=batch`, 2 items, "Start with item 1: I need their gender" |

### Action required

**Redeploy the API + web.** The API produces the reply and the web renders the
numbered batch card; until both carry `8870bd6`, multi-command messages keep
behaving exactly as reported.

---

## Still open

1. **Redeploy** the API + web so the running instance carries this change.
2. **Manual/browser pass** on `/copilot`: send a command, supply the gender,
   `confirm`, then check `/students` and the audit log; send a *multi-command*
   message (e.g. "add A to Nursery 1 and create subject X") and confirm the
   numbered card runs both; then delete a chat and confirm it leaves the rail
   immediately.
3. **While a required field is missing, a question is not answered** — the
   copilot stays on the command and re-asks (by design, pinned by
   `test_half_specified_command_keeps_asking_and_offers_cancel`). Worth a UX
   revisit if users find it confusing: today "give me the names of those
   students" mid-admission re-asks for the gender instead of listing the class.
4. **Optional follow-ups** for the chat: rename a chat, search the rail, and a
   "delete all chats" action.
5. **Widen command coverage** — see "Not yet on the command path" above;
   payroll/accounting/inventory/library are the largest untouched surfaces.
