# SchoolOS — Phase 3: Fees & billing → attendance → timetable scheduling

**Status:** built and verified. The three leftover roadmap rows — **finances,
attendance and scheduling** — are now real modules behind their own permission
codes, with an explicit migration (`0003_fees_attendance`), role-template
backfill, a typed web surface, and integration tests exercised end-to-end
through the HTTP API. Backend suite **117 passed**; web production build clean.

---

## 1. What was built

The previously scaffolded `fees`, `attendance`, `timetable` routers/services/schemas
were unfinished: several 500s on real use (e.g. `PaymentIn` had no `student_id`
but the router read `payload.student_id`; `school_id` was never set on
attendance rows whose columns are NOT NULL), and the timetable generator didn't
run (a `scalars()` on a two-entity select). Each slice was made to work, then
locked in with tests.

| Piece | What it does |
| --- | --- |
| **Fee structures** | `GET/POST /api/fees/structures`, `PUT /{id}`, `POST /{id}/toggle-status`. Create rejects duplicate names (`ERR_VALIDATION` 422); `specific_class`/`specific_arm` scopes are validated against the school's own levels/arms (cross-school ref → `ERR_NOT_FOUND` 404); inactive structures are hidden by default. |
| **Invoices** | `POST /api/fees/invoices` (student must belong to the school, structure owned by the school; duplicate invoice+term re-sends the existing one), `GET /api/fees/invoices` (filters `student_id`/`status`, paginated), `GET /invoices/{id}`. Amounts come from the fee structure; `issue_date`/`due_date` derive from billing frequency. |
| **Payments** | `POST /api/fees/payments` — the payload's `student_id` is optional and defaults to the invoice's student; invoice status advances `draft → partial → paid` (partial when covered < total, `paid_date` stamped on full payment). `GET /payments/{id}` is school-scoped 404. |
| **Student balance** | `GET /api/fees/balances/{student_id}` — computed `total_owed` (non-paid/written-off invoices), `total_paid` (payments), `total_unpaid = owed − paid`, current invoice, month period; upserted per student × month. |
| **Attendance** | `POST /mark/student`, `POST /mark/staff` (upsert per person+date), `GET /student/{id}` & `GET /staff/{id}` (date-range/status filters), `GET /summary/{id}` (monthly counts + percentage, current session default), `GET /staff/summary/{id}`. Records carry `school_id`; ownership checks are 404. |
| **Timetable** | Stateless deterministic generator. `GET /api/timetable/time-slots` (8 × 35-min periods + 5-min breaks from 08:00), `POST /generate` (every arm's subjects × 2 periods across Mon–Fri, teacher never double-booked, uuid5 entry ids — same input ⇒ same output), `GET /week/{arm_id}` (5-day weekly view, current-session default), `POST /validate` (teacher/class double-booking detection). |

## 2. New permission codes

`FEES_VIEW / FEES_CREATE / FEES_EDIT / FEES_PAY`, `ATTENDANCE_VIEW /
ATTENDANCE_MARK / ATTENDANCE_REPORT`, `TIMETABLE_VIEW / TIMETABLE_MANAGE`
added to `core.permissions.py` with `PERMISSION_CATALOG` entries. Role templates:
- **Principal** — fees view + billing, attendance view/report, timetable view/manage.
- **VP Academics / VP Administration** — attendance mark/report/view, timetable view/manage; VP Admin also fees create/edit/pay.
- **Head Teacher, Acad Coordinator** — attendance view/mark/report, timetable view.
- **Teacher** — attendance view/mark/report, timetable view (no management).
- **Accountant / Bursar** — fees view/collect (+ create/edit/pay where granted); deliberately no attendance/timetable.
- **Director / Super Admin** — all new codes.

Existing schools are reconciled by `sync_role_templates` on seed (no manual
migration of permission rows).

## 3. Data layer

`0003_fees_attendance` (down_revision `0002_import_mgmt`) creates
`fee_structures`, `invoices`, `payments`, `student_fee_balances`,
`student_attendance`, `staff_attendance`, `attendance_summaries` — all
tenant-scoped (`school_id` NOT NULL, indexed), FKs and unique constraints
matching the models. Timetables need no tables (stateless). `Student.invoices`
/ `Student.payments` relationships complete the mapper so `back_populates`
resolves.

## 4. Web

Shared contracts (`packages/shared`) now mirror the new Pydantic schemas —
`ScheduleGenerateIn {academic_session_id, force_regenerate, include_rooms}`,
`WeekScheduleOut`, fee/invoice/payment/balance, attendance record/summary
schemas — and the client exposes `fetchTimeSlots`, `generateSchedule`,
`fetchWeeklySchedule`, `validateSchedule`. The routes replace the stale
`/timetable/time-slots?term_id=…`-style scaffold (which pointed at a
non-existent endpoint and a missing `ClassArmBrief` / `useTimetable`). `/timetable`
now renders the weekly grid from `/timetable/week/{arm_id}` with a generate
button and the day-structure legend.

## 5. Fixes the tests surfaced

- `PaymentIn.student_id` required in the router but absent from the schema → added (optional, service defaults from the invoice).
- `record_student_attendance` / `record_staff_attendance` / `AttendanceSummary` never set `school_id` (NOT NULL) → threaded through service + router.
- `_due_days()` returns a bare `int` added to a `date` → wrapped in `timedelta`.
- `list_invoices` called `.all()` on a `Select` → `db.scalars(...)`.
- Period maths used `dt_mod.timedelta` → `timedelta`.
- `scalars(select(A, B))` returns only `A` → `db.execute(...).all()` for the offering×subject join.

## 6. Verification

- `pytest -q` → **117 passed** (26 new across `test_fees.py`, `test_attendance.py`, `test_timetable.py`), covering structure CRUD + duplicate name, invoice lifecycle (`draft → partial → paid`), balances, cross-school isolation (404 on read/toggle/generate), permission gates (teacher→fees 403, accountant→attendance 403, teacher→generate 403), attendance upsert + month summary counts, and deterministic conflict-free timetable generation.
- `alembic upgrade head` on the dev DB (0002 → 0003) then re-ran `python -m app.seed` to reconcile role permissions.
- `npm run build` clean — `/timetable` renders the weekly schedule grid.