# SchoolOS — Phase 1: Core Academic vertical slice

**Status:** built, code-audited, and **runtime-verified** — backend suite green
(17 tests), live API E2E smoke 7/7, cross-school isolation confirmed on a running
instance. Web app boots on :3000 and proxies `/api/*` to the API. See
"Verification results" below for the concrete run output.

---

## 1. What was built

Phase 1 is the **Core Academic vertical slice**: a real, multi-tenant foundation
with a working results engine — not a CRUD demo. It includes:

| Area | What you get |
| --- | --- |
| **Multi-tenancy** | Shared-schema tenancy: one Postgres DB, `school_id` on every tenant table, app-layer mandatory scoping. Global users + per-school `school_memberships`. Neutral `ERR_NOT_MEMBER` 404 on cross-school access. |
| **Auth** | Register school → founding super admin, login/logout/me/refresh. Short-lived JWT (15 min, `sub` only) + rotating single-use hashed refresh tokens in `httpOnly` cookies (`schoolos_session`, `schoolos_refresh`). Refresh-reuse detection revokes the whole family. |
| **RBAC** | Global permission catalog (`permissions.code`), school-scoped roles provisioned from templates, role-permission editor, `require_permission(...)` FastAPI dependency. Super admin bypasses. The frontend is never trusted for authorization. |
| **Academics** | Sessions (one current per school), terms, school-configured class levels (JSS 1…custom), arms with `full_name`, subjects, subject offerings (level×subject), teacher assignments (arm×subject→teacher). |
| **People** | Staff (teachers + non-teaching), students (soft delete), per-session student enrollments (status: active/graduated/withdrawn/on_hold), guardians + student–guardian links with `is_primary`. |
| **Results engine** | Assessment components with **effective resolution** (school-wide default → level → arm overrides) and weight validation (must sum to 100 → `ERR_WEIGHT_SUM`), score entry with clamping (`ERR_SCORE_OVER_MAX`, `ERR_SCORE_NEGATIVE`), weighted 0–100 totals, WAEC grade-band mapping, draft → submitted state lock (`ERR_RESULT_LOCKED`), and a **readiness dashboard** (per arm×subject: enrolled / entered / submitted / pending, entered %). |
| **Audit trail** | `result_events` append-only journal records every score/summit/state action with actor + timestamps. `audit_logs` table reserved for broad cross-cutting auditing. |
| **Web app** | Premium app shell (theme toggle, role-aware sidebar with section placeholders), onboarding-ready pages: dashboard, students, teachers, classes, results hub + **phone-friendly score grid**, readiness page, login/register. TanStack Query + shared zod-typed API client. |
| **Deploy** | `docker-compose.prod.yml` + Dockerfiles + nginx (single-origin reverse proxy) + migrate scripts — full reference for production bring-up. |

**Deferred by design** (schema reserved, nav placeholder "coming Phase 2", **no
fake implementations**): result approval workflow, report cards, AI features
(result comments, lesson plan, question generation, copilot) complete with the
`ai_usage` billing table, fees/Paystack-Flutterwave, payroll, inventory, library,
attendance, timetables, hostel, transport, CBT, parent/student portals,
notifications, subscriptions/credits.

## 2. Architecture decisions worth knowing

* **Shared schema + app-layer tenancy.** Queries are scoped in services by the
  resolved `school_id` — never by trusting the client. RLS is a documented
  future hardening step.
* **JWT carries only `sub`.** No tenant/role claims — the server resolves
  membership + permissions on every request, so grants/revokes are immediate and
  a stolen token cannot be replayed against another tenant.
* **Tenant context dependency.** `get_school_context` reads `X-School-Id`,
  resolves the membership, returns a neutral 404 for non-members, 403 for
  suspended membership. `require_permissions(...)` composes on top.
* **Results recompute is deterministic.** Totals & grades are derived state
  recomputed on every score save; `Result.status` guards transition draft→
  submitted; `published_snapshot` freezes totals for later report cards.
* **Single commit point.** Routers commit once at the end of a request; service
  functions only `flush()`. Tests run in rollback-per-test transactions.

## 3. Files created/modified

### Backend (`apps/api/`)
- `app/main.py` — app + router wiring, `/api/health`
- `app/config.py` — pydantic-settings
- `app/core/{database, deps, errors, security, permissions, pagination}.py`
- `app/models/{base, academic, people, identity, results, crosscut, auth_tokens, enums, school}.py`
- `app/schemas/{auth, academics, people, rbac, results}.py`
- `app/services/{tenancy, auth, rbac, academics, people, results, __init__}.py`
- `app/routers/{auth, schools, roles, academics, students, staff, results}.py`
- `app/seed.py` — WAEC scale + Brightfield demo
- `tests/{conftest, test_auth, test_tenancy, test_results}.py`
- `alembic/versions/0001_baseline.py`, `alembic/env.py`, `alembic.ini`

### Shared (`packages/shared/`)
- `src/contracts.ts` (zod), `src/client.ts`, `src/index.ts`

### Web (`apps/web/`)
- `src/app/{layout.tsx, page.tsx, globals.css}`; `(app)/` pages: dashboard,
  students, teachers, classes, results, results/score, readiness; `login/`,
  `register/`
- `src/components/app-shell.tsx`, `components/ui/*` (button, card, input, label,
  badge, skeleton, loader)
- `src/hooks/use-api.ts`, `src/providers/{providers, auth, query, theme}.tsx`
- `next.config.mjs` (rewrite `/api/*` → API), `tailwind.config.ts`, `tsconfig.json`

### Deploy & scripts
- `deploy/docker-compose.prod.yml`, `deploy/nginx.conf`, `apps/api/Dockerfile`,
  `apps/web/Dockerfile`
- `scripts/dev-db.sh`, `scripts/migrate.sh`
- `README.md`, `.env.example` × 2, `docs/phase-1.md` (this file)

## 4. How to run

### Backend

```bash
cd ~/schoolos
bash scripts/dev-db.sh                 # create role + schoolos_dev / schoolos_test
cd apps/api
python3 -m venv ../../.venv
../../.venv/bin/pip install -e ".[dev]"
cp .env.example .env                   # review DATABASE_URL etc.
bash ../scripts/migrate.sh seed        # alembic upgrade head + seed WAEC demo school
../../.venv/bin/uvicorn app.main:app --reload --port 8000
# Swagger: http://127.0.0.1:8000/api/docs
```

**Demo login:** `admin@brightfield.edu` / `Brightfield#2026`

### Web (new terminal)

```bash
cd apps/web
cp .env.example .env.local             # API_URL points at the backend
npm install                            # from repo root: npm install --workspaces
npm run dev                            # http://127.0.0.1:3000
```

The browser rides a single origin: `/api/*` is rewritten to the FastAPI service
server-side, so the httpOnly cookies flow with no CORS.

### Tests

```bash
cd apps/api
DATABASE_URL=postgresql+psycopg2://schoolos:schoolos@localhost:5432/schoolos_test \
  ../../.venv/bin/python -m pytest -q
```

The 15+ tests cover: register/login/refresh/logout, duplicate email, wrong
password, `ERR_AUTH_FAILED`, the **tenant canary** (School B can't see School A —
list, direct id, write, suspended membership), grade-boundary (82→B2, 50→C6,
12→F9), score over max, negative score, weight-sum validation, submit lock, and
readiness counts.

## 5. How to smoke-test manually

1. `bash scripts/dev-db.sh && cd apps/api && bash ../scripts/migrate.sh seed`
2. Start uvicorn + web (as above).
3. Log in as the demo admin.
4. Dashboard shows session "2025/2026", JSS1 + SSS1 arms, 5 students, 2 teachers.
5. Open **Results → pick arm JSS 1A → Mathematics** — a 3-student grid with
   CA1 20 / CA2 40 / Exam 40 columns (school-wide components).
6. Type some scores → totals + WAEC grades appear immediately (e.g. all 90 →
   A1); submit → grid locks.
7. **Readiness** shows 5 enrolled / entered counts for English + Mathematics.
8. Cross-school: register a *second* school in another browser, open it, ask for
   Brightfield's session UUID → neutral 404, no data.

## 6. Next phase (Phase 2) — preview

Result **approval workflow** (verify → approve → publish with the rejection
path and an email-signed journal), **report cards** (printed from
`published_snapshot`), **AI features** (result comments, lesson plans, question
generation, school copilot behind the same permission layer + `ai_usage`
metering), and a **public PIN-check** result portal.

## 7. Verification results

| Check | Result |
| --- | --- |
| `pytest -q` (`schoolos_test`) | **17 passed** — auth/refresh/logout, tenancy canary (list/direct-id/write/suspended), grade boundaries, weight-sum, score clamp, submit lock, readiness. |
| Live API boot (`schoolos_dev`, migrated + seeded) | `GET /api/health` → 200; demo login → `200` + JWT + `user.status = active`. |
| E2E smoke (`scripts/smoke-e2e.sh`) | **7/7 passed**: health, demo login, sessions, arms, 5 students, **cross-school isolation (2nd school → 1st school session = neutral `ERR_NOT_FOUND` 404)**, readiness (24 arm×subject rows, 5 enrolled / 0 entered / 5 pending). |
| Web dev server (`next dev` on :3000) | Boots on `http://127.0.0.1:3000`; `/api/*` rewrite proxies to :8000. |

To reproduce: follow "How to run" above, then

```bash
cd apps/api && DATABASE_URL=...schoolos_test ../../.venv/bin/python -m pytest -q   # 17 passed
bash ~/schoolos/scripts/smoke-e2e.sh                                               # 7 passed, 0 failed
```

> Note: the login 401 seen mid-session was a stale uvicorn process pointed at the
> pytest database (left empty by teardown). Restarting the API pinned to
> `schoolos_dev` (`DATABASE_URL=postgresql+psycopg2://schoolos:schoolos@localhost:5432/schoolos_dev`)
> resolved it — a reminder to always start the dev server from `apps/api` with
> the `dev` database in scope.