# SchoolOS — Multi-Tenant School Management SaaS

A production-grade, multi-tenant school management platform. Shared-schema
multi-tenancy (one Postgres database, `school_id` on every tenant table, app-layer
scoping), global identity + per-school roles, and a rigorous result-processing
workflow with an append-only audit journal.

**Current phase: 3 — Finance & attendance** (fee structures, invoices,
payments, student balances; student/staff attendance with monthly summaries;
stateless deterministic timetable generation + weekly view), built on the
Phase 1 core (auth/tenancy/RBAC, students/teachers,
sessions/terms/classes/subjects, score entry + grade computation, readiness
dashboard) and Phase 2 (results approval workflow, report cards, public PIN
portal, metered AI remarks, lesson plans, question banks, school copilot).
Payroll, inventory, library, and the rest of the roadmap remain designed and
schema-reserved for later phases. See `docs/phase-1.md`, `docs/phase-2.md`,
and `docs/phase-3.md`.

## Monorepo layout

```
schoolos/
├── apps/
│   ├── api/                 # FastAPI + SQLAlchemy 2.0 + Alembic + pytest
│   │   ├── app/
│   │   │   ├── main.py      # app entry point, router wiring
│   │   │   ├── config.py    # pydantic-settings (env / .env)
│   │   │   ├── core/        # deps (auth/tenant/permissions), security, errors
│   │   │   ├── models/      # all tables (Base.metadata)
│   │   │   ├── schemas/     # Pydantic v2 request/response contracts
│   │   │   ├── services/    # business logic (results_service is the engine)
│   │   │   ├── routers/     # thin HTTP adapters
│   │   │   └── seed.py      # WAEC scale + demo school
│   │   ├── alembic/         # baseline migration + env
│   │   └── tests/           # tenancy canary, auth, results engine
│   └── web/                 # Next.js 15 App Router + Tailwind + shadcn/ui (Phase 1.5)
├── packages/shared/         # shared zod schemas/TS types (Phase 1.5)
├── deploy/                  # docker-compose.prod.yml, Dockerfiles (supplied for later)
├── scripts/                 # dev-db.sh, migrate.sh
└── README.md
```

## Quick start (backend)

```bash
# 1. Create the Postgres role + databases once
bash scripts/dev-db.sh

# 2. Create a venv and install the API
cd apps/api
python3 -m venv ../../.venv
../../.venv/bin/pip install -e ".[dev]"

# 3. Migrate + seed demo school (Brightfield Academy)
bash ../../scripts/migrate.sh seed

# 4. Run the API
../../.venv/bin/uvicorn app.main:app --reload --port 8000
# Docs: http://127.0.0.1:8000/api/docs
```

**Demo login** (from the seed): `admin@brightfield.edu` / `Brightfield#2026`

## Test

```bash
cd apps/api
export DATABASE_URL=postgresql+psycopg2://schoolos:schoolos@localhost:5432/schoolos_test
../../.venv/bin/python -m pytest -q
```

The suite includes the **tenant isolation canary** — school B must never see
school A's data (neutral `ERR_NOT_MEMBER` 404), grade-boundary checks against the
seeded WAEC scale, score clamping/validation, and the result submit lock.

## API conventions

* Every error is a JSON envelope: `{"error": {"code": "ERR_...", "message": ..., "details": ...}}`.
* Auth: short-lived JWT access token + rotating, single-use, hashed refresh
  token held in `httpOnly` cookies. The JWT carries only `sub` — never tenant or
  role claims.
* Every tenant request sends `X-School-Id: <uuid>`; the backend resolves the
  caller's membership and permission set server-side on every call. The frontend
  is never trusted with authorization.
* Business logic lives in `app/services`; routers only validate + serialize.

## Phase roadmap (all future items are TODO by design — no fake implementations)

Phase 2 (complete): the result approval workflow (verify → approve → publish →
reject + workbench), report cards (printed from published snapshots), the
public PIN result portal (published-only cards via admission no + PIN), metered
AI remarks, lesson plans and question banks (all data-grounded, behind
`results.comment`, each generation metered into `ai_usage`), and the school
copilot — a free-form Q&A over the school's own records, gated on `ai.copilot`,
answers grounded in real rows (published-only for performance questions), every
turn metered into `ai_usage`/`usage_meters` — are built, see `docs/phase-2.md`.
Phase 3 (partial — complete slice): fee structures, invoices, payments and
student balances; student/staff attendance with monthly summaries; stateless
deterministic timetable generation with a weekly view — all permission-gated
and tenant-scoped, see `docs/phase-3.md`. Remaining Phase 3: accounting
integrations (Paystack/Flutterwave), payroll, inventory, library.
Phase 4: lessons, hostel, transport, CBT, analytics,
parent/student portals, notifications, subscriptions & AI credits.