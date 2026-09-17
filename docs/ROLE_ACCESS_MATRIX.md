# Role Access Matrix — Results, Report Cards & Sessions

What each role can do, what was changed to get there, and what has actually been
verified. Companion to `docs/PRODUCTION_SECURITY.md`.

---

## 1. How access is decided

Three layers, in order. The frontend is **never** the control.

| Layer | Question | Where |
|---|---|---|
| Identity | Who are you? | `get_current_user` — reloads the user row every request; the JWT carries only `sub` |
| Tenant + role | Which school, and what role there? | `get_school_context` — resolves the `X-School-Id` membership server-side |
| Permission / role gate | May you do this? | `require_permission(code)` / `require_role(...)` on every route |

Two platform-level bypasses exist and are intentional: `User.is_superadmin`
(Clearis staff) and an active impersonation session resolving to the school
admin. Platform admins are blocked from platform routes while impersonating.

Two extra gates stack **on top of** permissions, because "what may you do" is
not the same question as "who are you":

* `require_accountant` — the ledger is the school Accountant's alone.
* `results.report_card` — report cards are the Exam Office's document (§2).

---

## 2. The results desk — what changed

### Report cards are the Exam Office's document

Report cards render **every subject a student takes**, so they were never a
teacher's document. They are now gated by a dedicated permission,
`results.report_card`, instead of the `results.view` that every teacher holds.

Granted to (via role templates): **Exam Officer, Principal, VP Academics,
Director, school Super Admin**. Not granted to Teacher, Homeroom Teacher, Head
Teacher, Academic Coordinator, Secretary, Accountant, Bursar, Librarian.

Endpoints now demanding `results.report_card`:

```
GET /api/results/report-index        GET /api/results/cumulative
GET /api/results/report-card         GET /api/results/broadsheet
GET /api/results/report-cards        GET /api/results/best-in-subjects
```

Endpoints that stay on `results.view` (the teacher's own scoresheet path):

```
GET /api/results/scorecard   GET /api/results/readiness   GET /api/results/workbench
GET /api/results/grade-bands GET /api/results/psychomotor
```

Existing schools need no manual step: `sync_all_school_role_templates` runs at
startup and reconciles every tenant's **system** roles with the templates. A
school that built a **custom** role and wants it to print cards must grant
`results.report_card` to that role in Settings → Roles.

### A teacher reads only their own score grids

`results.view` alone no longer opens an arbitrary grid. On top of the
permission, a non-supervisor must be the **assigned teacher** of that
arm × subject — the same gate that already governed writes, now applied to
reads:

```
GET /api/results/scorecard   → 403 ERR_ASSIGNMENT when not assigned
GET /api/results/readiness   → rows filtered to their assignments
GET /api/results/workbench   → rows filtered to their assignments
```

Supervisors (anyone holding `results.verify` / `results.approve` /
`results.publish`) and platform admins are unrestricted, as before.

### The Exam Office runs the pipeline end to end

The Exam Officer template now carries **`results.approve`** alongside verify and
publish. That matters because report cards render *published* results: without
approve, the office could only print cards for cells somebody else had signed
off, and the one-click `/results/compile` (verify → approve → publish) — which
requires all three — was refused outright.

Entering and submitting marks stays with the teacher; the exam office takes the
cell from there. The office does **not** hold `results.enter`/`results.submit`,
so it cannot alter the marks it is adjudicating.

### A teacher sees only their own classes' students

A teacher's roster is the classes they teach. Everyone holding `students.view`
without a roster-wide capability is bounded by their `SubjectAssignment`:

```
GET /api/students                      → only students in their arms
GET /api/students/{id}                 → 404 for a pupil outside their arms
GET /api/students/arms/{arm}/enrollments → 404 for a class they do not teach
GET /api/students/{id}/enrollments     → 404 as above
GET /api/students/{id}/guardians       → 404 as above
```

Out of scope is a **neutral 404**, the same answer the tenancy layer gives for
another school's rows — a teacher learns nothing about whether that pupil
exists. The scope is resolved from `SubjectAssignment` server-side and can never
be widened by the request.

`ROSTER_WIDE_PERMISSIONS` in `app/core/permissions.py` defines the boundary. It
is a *capability* set, not a list of role codes, so a school's custom roles
inherit the right scope from what they can do and an unknown role fails
**closed** (scoped) rather than open. In the shipped templates it scopes exactly
`teacher` and `homeroom_teacher`; admins, principal/VPs, head teacher, academic
coordinator, exam officer, admission officer, secretary and librarian all keep
the whole roster because their work spans the school.

### Psychomotor has its own page

The psychomotor/affective record is the **class teacher's** to keep, and it used
to live inside the Report Cards page — which is the Exam Office's desk, so the
people who needed to write it could not reach it. It now lives at
`/results/psychomotor`, reachable by anyone holding `results.enter` (exactly the
roles the API authorizes, plus a student's homeroom teacher). The printed card
still displays it; the Report Cards page no longer edits it.

---

## 3. Session isolation (the cross-user leak)

**Symptom reported:** sign out as an admin, sign in as a normal user in the same
tab → the admin's dashboard renders with the new user's name; a hard refresh
fixes it.

**Cause:** sign-out was a *client-side route change*, and the React Query cache
was never cleared. Cached responses are keyed by school, not by person, so the
next user of the same tab (and same school) read the previous user's cached
dashboard payload — which refreshed itself only when the cache went stale or the
page was reloaded. Logout never dropped it.

**Fix, in three parts:**

1. `AuthProvider.signOut()` — revokes the session, clears the query cache, then
   does a **full document navigation** to `/login`. A route change cannot
   guarantee a clean client; a fresh document can.
2. `AuthProvider` clears the whole query cache whenever the **identity changes**
   (`adoptIdentity`, keyed on `user.id`). This covers every other path where the
   person behind the tab changes — impersonation enter/exit, signing in as
   somebody else, a session that expires and is replaced.
3. Login, register and password-reset now land with
   `window.location.replace(...)` instead of `router.replace(...)`, so a new
   identity never starts inside the previous one's client state.

All five sign-out entry points (nav panel, legacy sidebar, platform header,
platform sidebar, profile menu) now call the one `signOut()`.

---

## 4. Actions each role can perform

Generated from `ROLE_TEMPLATES` in `app/core/permissions.py`. "Per school"
means the role is scoped to the school in `X-School-Id`; a user holds **exactly
one** role per school.

### Results desk

| Action | Permission | Roles that hold it |
|---|---|---|
| Open a scoresheet (own classes only) | `results.view` | Super Admin, Director, Principal, VP Academics, Head Teacher, Academic Coordinator, **Exam Officer**, Teacher, Homeroom Teacher, Secretary |
| Enter / edit scores | `results.enter` | Super Admin, Director, Teacher, Homeroom Teacher |
| Submit scores for review | `results.submit` | Super Admin, Director, Teacher, Homeroom Teacher |
| Verify submitted results | `results.verify` | Super Admin, Director, Principal, VP Academics, Head Teacher, Academic Coordinator, **Exam Officer** |
| Approve verified results | `results.approve` | Super Admin, Director, Principal, VP Academics, Head Teacher, **Exam Officer** |
| Publish approved results | `results.publish` | Super Admin, Director, Principal, **Exam Officer** |
| One-click compile (verify → approve → publish) | all three above | Super Admin, Director, Principal, **Exam Officer** |
| Write result remarks | `results.comment` | Super Admin, Director, Principal, VP Academics, Homeroom Teacher |
| **View / print report cards, broadsheet, cumulative, best-in-subjects** | `results.report_card` | **Exam Officer**, Principal, VP Academics, Director, Super Admin |
| View readiness board | `results.view` | as "open a scoresheet" (scoped for teachers) |
| Process Results workbench | `results.verify` | as "verify submitted results" |
| Manage assessment components | `academics.manage` | Super Admin, Director, Principal, VP Academics, Academic Coordinator |

### Everything else

| Area | Permission | Roles |
|---|---|---|
| Students | `students.view` / `.create` / `.edit` / `.delete` / `.enroll` | Super Admin & Director: all. Principal, VP Academics, VP Admin, Head Teacher, Academic Coordinator, Exam Officer, Teacher, Homeroom Teacher, Secretary, Librarian, Admission Officer: view. Admission Officer: view + create + enroll. **Teacher and Homeroom Teacher see only the students in the classes they teach** (§2). |
| Staff | `staff.view` / `.create` / `.edit` | Super Admin & Director: all. Principal, VP Academics, VP Admin, Academic Coordinator, Secretary, Librarian: view. |
| School settings | `school.manage` | Super Admin, Director, Principal, VP Admin, Bursar |
| Campuses | `campus.manage` | Super Admin, Director, Principal, VP Admin (not Bursar) |
| Roles & permissions | `roles.manage` | Super Admin, Director |
| Users (invite / accounts) | `users.manage` | Super Admin, Director, Principal, VP Admin |
| Academics structure | `academics.view` / `.manage` | Super Admin & Director: both. Principal, VP Academics, Academic Coordinator: both. VP Admin, Teacher, Homeroom Teacher, Exam Officer, Secretary: view. |
| Attendance | `.view` / `.mark` / `.manage` / `.report` | Super Admin & Director: all. Teacher, Homeroom Teacher, VP Admin, VP Academics: view + mark + report. Principal, Head Teacher, Academic Coordinator: view + report. |
| Timetable | `timetable.view` / `.manage` | Super Admin & Director: both. Principal, VP Academics, VP Admin, Academic Coordinator: both. Teacher, Homeroom Teacher, Head Teacher, Exam Officer: view. |
| Fees & billing | `fees.*`, `billing.view` | Accountant, Bursar |
| Accounting ledger, expenses, reconciliation, reports | `accounting.*` **+ role gate** | Accountant **only** |
| Payroll | `payroll.view` / `.manage` | Accountant, Bursar |
| Inventory | `inventory.view` / `.manage` | Super Admin, Director, Principal, VP Admin |
| Library | `library.view` / `.manage` | Super Admin, Director, Principal, VP Admin, Secretary, Librarian |
| Imports | `imports.view` / `.create` / `.fix` | Full: Super Admin, Director, Principal, VP Academics, VP Admin, Head Teacher, Academic Coordinator, Admission Officer. View only: Secretary |
| Communication | `communication.send` | Super Admin, Director, Secretary |
| AI copilot | `ai.copilot` | Super Admin, Director, Principal, VP Academics, Head Teacher, Academic Coordinator |
| AI lesson plans & question banks | `results.comment` + `ai.copilot` + premium | Super Admin, Director, Principal, VP Academics (Head Teacher and Academic Coordinator have `ai.copilot` but **not** `results.comment`) |
| Parent / Student | — | read-only public PIN portal only |

---

## 5. Loopholes found

### Fixed

1. **Report cards were open to every `results.view` holder.** A teacher,
   homeroom teacher, secretary, head teacher or academic coordinator could call
   `/api/results/report-card`, `/report-cards`, `/broadsheet` or `/cumulative`
   directly and read **every subject of every student** in any class. Now gated
   on `results.report_card`.
2. **Teachers could read any class's scoresheet.** `PUT /scorecard` was
   assignment-gated; `GET /scorecard` was not, so a teacher could read another
   teacher's subject marks for any arm. Now enforced on read.
3. **The readiness board and workbench leaked school-wide rows to teachers.**
   The UI filtered them; the API returned them. Now filtered server-side.
4. **Cross-user data leak in the browser** (the reported symptom) — see §3.
5. **Report-card links were shown to people who cannot use them**: the teacher's
   nav, the accountant's dashboard quick links, and the dashboard quick actions.
6. **The school owner could not see Results or Readiness at all.** Their role
   code is `super_admin`, but those nav entries whitelisted a role code `admin`
   that no role template defines, so `matchesPerm` never matched. Fixed in the
   results section of `nav-config.ts`.
7. **The Exam Officer had no route to the workbench** despite holding
   `results.verify`/`results.publish`, so the role could not drive the pipeline
   its permissions describe. `exam_officer` (and the other `results.verify`
   holders) are now in the Process Results nav.
8. **The Exam Officer could not finish the pipeline.** The template granted
   verify and publish but not `results.approve`, so `/results/approve`,
   `/results/reject` and one-click `/results/compile` returned 403 — while
   report cards render only *published* results. `results.approve` is now on the
   role, so the office owns results end to end (§2). It still holds neither
   `results.enter` nor `results.submit`: entering marks stays with the teacher.
9. **A teacher could read the whole school's student roster.** `students.view`
   was unscoped, so `GET /api/students` returned every pupil in the school —
   and single profiles, class rosters and guardians could be read by id. Now
   bounded by the caller's `SubjectAssignment` for anyone without a roster-wide
   capability (§2), with a neutral 404 outside it.
10. **The psychomotor editor was unreachable for the people who write it** —
    it lived on the exam-office-only Report Cards page. It now has its own page
    at `/results/psychomotor`, gated on `results.enter` (§2).

### Open — recommendations, deliberately not changed

1. **The workbench UI is permission-blind.** It offers Approve/Publish buttons
   based on row state, not on the caller's permissions — so a VP Academics
   (who lacks `results.publish`) is shown Publish and gets the API's 403. The
   API is still the control; this is a UX gap, pre-existing.
2. **Aggregate figures reach teachers.** Because they hold `results.view` /
   `students.view`, the dashboard shows school-wide `readiness_overall` and the
   gender/region distribution. Aggregate only — no per-student, per-class marks.
   Decide whether teachers should see school-wide numbers at all.
3. **The notification bell is hardcoded mock data** for every user
   (`components/notifications.tsx`, `MOCK_NOTIFICATIONS`). Not a leak, but not
   production data either.
4. **Dead code:** `components/dashboard/admin-dashboard.tsx` is never imported
   and still contains a `/reports` shortcut. Safe to delete.
5. **Query keys are scoped by school, not by user.** The cache clear on identity
   change is the safeguard. If a *persistent* cache (localStorage/IndexedDB) is
   ever added, keys must include the user id, or the leak returns across
   reloads.
6. **One role per membership.** "The principal is also the exam officer" is
   achieved through the `results.report_card` permission, not by holding two
   roles — a membership has exactly one. Granting the principal role the
   permission (already done) or editing the role in Settings are the mechanisms.

---

## 6. Verification status

### Ran and passed

* Backend suite: **214 tests, all passing** —
  `cd apps/api && DEBUG=true ../../.venv/bin/python -m pytest -q`
  (the suite needs `DEBUG=true` locally; the default config correctly fails
  production validation on the dev JWT secret, which is a pre-existing
  environment gotcha, not a test failure.)
* `tests/test_result_access.py` (9 tests, all passing):
  * a teacher gets `403 ERR_PERMISSION_DENIED` from all six report-card
    endpoints and does not carry `results.report_card`;
  * an Exam Officer carries the permission and renders `report-index`,
    `report-card`, `report-cards` and `broadsheet` against published results;
  * an Exam Officer **compiles a cell all the way to a published report card**
    in one action, and verifies → approves → publishes stepwise;
  * an Exam Officer **cannot enter marks** (`ERR_PERMISSION_DENIED`) — entering
    stays with the teacher;
  * Principal and VP Academics carry the report-card permission;
  * Head Teacher and Secretary do not;
  * a teacher is refused a grid they are not assigned to (`ERR_ASSIGNMENT`),
    sees an **empty** readiness board and workbench, then succeeds on the same
    grid after the admin assigns them — and still cannot open report cards;
  * a supervisor is not restricted.
* `tests/test_student_scope.py` (2 tests, all passing):
  * a teacher with no assignment gets an **empty** roster, then exactly their
    own class's students once assigned; another class's pupils are a neutral
    `ERR_NOT_FOUND` on the profile, the class roster, the enrollment history and
    the guardians list; their own pupils stay readable;
  * a homeroom teacher is scoped the same way, while secretary, exam officer and
    principal all keep the whole roster.
* Frontend typecheck: clean — `apps/web && ../../node_modules/.bin/tsc --noEmit`.

### Verified by reading the code, not by a test

* `director`, `vp_admin`, `academic_coordinator`, `accountant`, `bursar`,
  `admission_officer`, `librarian`, `parent`, `student` — their report-card and
  roster access follows from the same template + `require_permission` mechanism
  tested for the roles above, but no test asserts each one individually. The
  roster split is asserted for `teacher`, `homeroom_teacher`, `secretary`,
  `exam_officer` and `principal`.
* The sign-out / cache-clear behaviour is TypeScript-clean and reasoned through
  (identity keyed on `user.id`, full navigation on sign-out), but **has not been
  exercised in a browser here** — there is no running web app in this
  environment. Worth a manual pass: sign in as an admin, sign out, sign in as a
  teacher in the same tab, and confirm the teacher dashboard appears with no
  flash of admin data.
* The new `/results/psychomotor` page is typechecked and mirrors the API's own
  rule (`results.enter` or the student's homeroom teacher), but was not clicked
  through in a browser.

### Deliberately left alone

* The workbench UI's permission-blind buttons (open finding 1) and the aggregate
  dashboard figures (open finding 2).
* `results.enter` / `results.submit` stay **off** the Exam Officer role, so the
  office adjudicates marks it cannot alter. If your policy is that the exam
  office also enters marks, add both codes to the template in
  `app/core/permissions.py`.
* Custom (non-system) roles are never touched by `sync_role_templates`, so a
  school that built one has to grant it `results.report_card` in Settings →
  Roles to let it print cards.
