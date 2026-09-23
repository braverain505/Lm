# Clearis Production Security Guide

**IMPORTANT:** This document outlines critical security measures that MUST be implemented before deploying Clearis to production.

---

## ✅ COMPLETED FIXES

### 1. Hardcoded Credentials (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/seed.py`
- **Change:** Credentials now use environment variables with production warnings

**Action Required:**
```bash
# Set these in production environment
export SEED_ADMIN_PASSWORD="<strong-password>"
export SEED_PLATFORM_PASSWORD="<strong-password>"
```

### 2. JWT Secret Validation (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/config.py`
- **Change:** Added `validate_production_config()` method that enforces 32+ byte secrets

**Action Required:**
```bash
# Generate a strong JWT secret
openssl rand -hex 32

# Set in .env for production
JWT_SECRET=<generated-secret>
COOKIE_SECURE=true
DEV_EMAIL=false
DEBUG=false
```

### 3. CORS Middleware (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/main.py`
- **Change:** CORS middleware now configured with settings.cors_origins

**Action Required:**
```bash
# Set allowed origins in .env
CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
```

### 4. Production Config Validation (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/config.py`, `apps/api/app/main.py`
- **Change:** Application validates config on startup, refuses to start with weak settings in production

### 5. Security Headers (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/main.py`
- **Change:** Added security headers middleware (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, CSP)

### 6. Health Check with DB Connectivity (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/main.py`
- **Change:** `/api/health` now tests database connection

### 7. Database Connection Pool (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/core/database.py`
- **Changes:**
  - pool_size: 10 → 20
  - max_overflow: 20 → 40
  - Added 30s query timeout
  - Added 30s pool timeout

### 8. File Upload Path Traversal (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/services/storage_service.py`
- **Change:** Hardened path validation with URL decoding and double-check

### 9. Production Logging (FIXED)
- **Status:** ✅ Fixed
- **File:** `apps/api/app/main.py`
- **Change:** Structured logging with request IDs

---

## ⚠️ CRITICAL - MUST IMPLEMENT BEFORE PRODUCTION

### 10. Rate Limiting (NOT IMPLEMENTED)
**Risk:** Brute force attacks on login, password reset, and API endpoints

**Implementation Required:**

Add to `apps/api/pyproject.toml`:
```toml
dependencies = [
    # ... existing deps
    "slowapi>=0.1.9",
]
```

Create `apps/api/app/core/rate_limit.py`:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

Update `apps/api/app/main.py`:
```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from .core.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

Add to critical endpoints in `apps/api/app/routers/auth.py`:
```python
from ..core.rate_limit import limiter

@router.post("/login")
@limiter.limit("5/15minutes")  # 5 attempts per 15 minutes
def login(request: Request, ...):
    ...

@router.post("/password-reset-request")
@limiter.limit("3/hour")  # 3 requests per hour
def password_reset_request(request: Request, ...):
    ...
```

**Estimated Time:** 2-3 hours

---

### 11. CSRF Protection (NOT IMPLEMENTED)
**Risk:** Cross-Site Request Forgery attacks on state-changing operations

**Implementation Required:**

Add to `apps/api/pyproject.toml`:
```toml
dependencies = [
    # ... existing deps
    "fastapi-csrf-protect>=0.3.4",
]
```

Create `apps/api/app/core/csrf.py`:
```python
from fastapi_csrf_protect import CsrfProtect
from pydantic import BaseModel

class CsrfSettings(BaseModel):
    secret_key: str = "your-csrf-secret-key"
    cookie_samesite: str = "lax"

@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()
```

Update routers to validate CSRF tokens on POST/PUT/DELETE/PATCH operations.

**Estimated Time:** 4-6 hours

---

### 12. Input Sanitization for XSS (NOT IMPLEMENTED)
**Risk:** Cross-Site Scripting via user input (student names, comments, school names)

**Implementation Required:**

Add to `apps/api/pyproject.toml`:
```toml
dependencies = [
    # ... existing deps
    "nh3>=0.2.14",  # HTML sanitizer
]
```

Create `apps/api/app/core/sanitize.py`:
```python
import nh3

def sanitize_html(text: str | None) -> str | None:
    """Remove all HTML tags and dangerous content."""
    if text is None:
        return None
    return nh3.clean(text, tags=set(), attributes={})

def sanitize_text_input(text: str | None) -> str | None:
    """Sanitize user text input (names, descriptions, comments)."""
    if text is None:
        return None
    # Remove HTML tags
    cleaned = nh3.clean(text, tags=set(), attributes={})
    # Strip leading/trailing whitespace
    return cleaned.strip()
```

Apply to all Pydantic models that accept user input:
```python
from pydantic import field_validator
from ..core.sanitize import sanitize_text_input

class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    # ... other fields

    @field_validator('first_name', 'last_name')
    def sanitize_names(cls, v):
        return sanitize_text_input(v)
```

**Estimated Time:** 6-8 hours (requires updating all input schemas)

---

## 🔶 HIGH PRIORITY - IMPLEMENT WITHIN FIRST MONTH

### 13. Password Reset Token Expiry (NOT IMPLEMENTED)
**Risk:** Password reset tokens never expire server-side

**Implementation:**
- Add `expires_at` column to `PasswordResetToken` model
- Set expiry to 1 hour from creation
- Validate expiry when token is used
- Clean up expired tokens with scheduled job

**Estimated Time:** 2-3 hours

---

### 14. Email Service Integration — DONE
**Was:** password resets returned tokens in the API response (DEV_EMAIL=true).

Implemented in `apps/api/app/services/email_service.py`. There are two
transports, chosen by `EMAIL_TRANSPORT` (`auto` by default): **SMTP**
(`smtplib` + `email`, stdlib) — how the platform's own mail leaves, from the
Clearis inbox — and **Resend's HTTP API** (no vendor SDK, just `httpx`), for a
deployment with a verified sending domain. Sends the router makes are unchanged
either way. Four messages are wired up:

| Message | Trigger | Sender |
|---|---|---|
| Guardian payment receipt | `POST /api/fees/payments/{id}/receipt/email` | `fees` router |
| New-school welcome + guide PDF | `POST /api/auth/register-school` | `auth` router, after commit |
| New-school notice (internal) | same request, right after the welcome email | `auth` router, to `OWNER_ALERT_EMAIL` |
| Password reset link | `POST /api/auth/passwords/reset` | `auth` router, after commit |

**Required env vars for a working production deployment:**

| Var | Why |
|---|---|
| `SMTP_HOST` / `SMTP_USER` / `SMTP_PASSWORD` | The Clearis mailbox the onboarding mail leaves from. With Gmail, `SMTP_PASSWORD` is a **16-character App Password** (create it after enabling 2-Step Verification) — the account's normal password is rejected. Gmail's daily sending limit applies: a free account handles a few hundred recipients a day, not thousands of onboarding emails. |
| `RESEND_API_KEY` | The other transport, and the `auto` fallback. Needs a sending domain you own with SPF/DKIM records; it **cannot** send from a `gmail.com` address. |
| `EMAIL_TRANSPORT` | `auto` (default) picks SMTP when the three vars above are set, then Resend. Pin `smtp` or `resend` when both are configured, so a leftover account cannot silently win. **On a host that blocks outbound SMTP (Render free web services block ports 25/465/587) pin `resend`:** `auto` prefers a configured SMTP block and would fail on every send with `[Errno 101] Network is unreachable`. |
| `OWNER_ALERT_EMAIL` | Where the internal "a new school registered" notice goes. Blank disables it. |
| `WEB_BASE_URL` | Public origin of the web app. Reset links and the welcome email's sign-in/dashboard buttons are built from it. Defaults to `http://localhost:3000`, which is **wrong in production** — set it or every reset email links to localhost. |
| `EMAIL_FROM` / `EMAIL_REPLY_TO` | Resend-only: verified sender, and where replies land. Defaults to `Clearis <no-reply@clearis.site>`. Must be on the domain verified with Resend; a reply-to of your real inbox keeps the "just reply to this email" promise true without a mailbox on that domain. |
| `DEV_EMAIL=false` | Already enforced by `validate_production_config()`. |

With no transport configured, production sends raise `503
ERR_EMAIL_NOT_CONFIGURED`. Degradation stays explicit: no transport + dev logs
the message and reports `dev_skipped`; no transport + production raises; a
provider error raises. A reset that was never delivered must not look delivered
— the alternative is a user waiting on mail that is not coming.

The registration welcome email is the one exception: it swallows failures and
logs them, because the workspace has already committed by then and a mail outage
must not fail a signup. The internal new-school notice behaves the same way, and
reports whether the welcome email actually went out — an onboarding mail that
never arrived is otherwise invisible, leaving a new school waiting on
credentials nobody sent.

**Remaining to do:** the welcome email contains the admin's initial password in
plain text, which is only available at registration time. If that is not
acceptable, switch it to a one-time set-password link.

---

### 15. Database Indexes (NOT IMPLEMENTED)
**Risk:** Poor query performance under load

**Implementation:**
Create Alembic migration `apps/api/alembic/versions/xxx_add_performance_indexes.py`:
```python
def upgrade():
    op.create_index('ix_student_admission_no', 'student', ['admission_no'], unique=True)
    op.create_index('ix_membership_user_school', 'school_membership', ['user_id', 'school_id'])
    op.create_index('ix_result_term_arm_subject', 'result', ['term_id', 'class_arm_id', 'subject_id'])
    op.create_index('ix_score_enrollment', 'score', ['student_enrollment_id'])
    op.create_index('ix_attendance_student_date', 'student_attendance', ['student_id', 'date'])
```

**Estimated Time:** 2 hours

---

### 16. Monitoring & Error Tracking (NOT IMPLEMENTED)
**Risk:** No visibility into production errors and performance

**Recommended:**
- **Sentry** for error tracking
- **Datadog/New Relic** for APM
- **Prometheus + Grafana** for metrics

**Sentry Implementation:**
```bash
pip install sentry-sdk
```

Add to `apps/api/app/main.py`:
```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if not settings.debug:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment="production"
    )
```

**Estimated Time:** 2-4 hours

---

### 17. Audit Logging for Sensitive Operations (NOT IMPLEMENTED)
**Risk:** Missing audit trail for critical actions

**Actions to log:**
- Permission changes
- School suspension/reactivation
- Platform admin actions
- AI feature enable/disable
- Data exports
- Impersonation start/end

**Implementation:**
Extend existing `AuditLog` usage in services.

**Estimated Time:** 3-4 hours

---

### 18. API Versioning (NOT IMPLEMENTED)
**Risk:** Breaking changes affect all clients simultaneously

**Implementation:**
Update `apps/api/app/main.py`:
```python
API_PREFIX = "/api/v1"

for module in (auth, schools, ...):
    app.include_router(module.router, prefix=API_PREFIX)
```

Add deprecation warnings for future breaking changes.

**Estimated Time:** 1-2 hours

---

### 19. Request Timeout Middleware (NOT IMPLEMENTED)
**Risk:** Slow requests block workers

**Implementation:**
Add to `apps/api/app/main.py`:
```python
from fastapi import Request
import asyncio

@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    try:
        return await asyncio.wait_for(call_next(request), timeout=30.0)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=504,
            content={"error": {"code": "ERR_TIMEOUT", "message": "Request timeout"}}
        )
```

**Estimated Time:** 1 hour

---

### 20. Pagination Limit Enforcement (NOT IMPLEMENTED)
**Risk:** Resource exhaustion from large page sizes

**Implementation:**
Update `apps/api/app/core/pagination.py`:
```python
def paginate(query, page: int = 1, limit: int = 20):
    # Cap limit at 100
    limit = min(limit, 100)
    # ... rest of pagination logic
```

**Estimated Time:** 1 hour

---

## 🔷 MEDIUM PRIORITY - IMPLEMENT WITHIN 2-3 MONTHS

### 21. Redis Session Store (NOT IMPLEMENTED)
**Current:** Refresh tokens in PostgreSQL
**Issue:** Multi-instance deployment requires sticky sessions
**Solution:** Migrate to Redis for horizontal scaling

### 22. Database Backup Strategy (NOT IMPLEMENTED)
**Create:** `scripts/backup-db.sh`
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backup_${DATE}.sql.gz"
pg_dump $DATABASE_URL | gzip > /backups/$BACKUP_FILE
aws s3 cp /backups/$BACKUP_FILE s3://your-backup-bucket/
```

**Setup:** Daily cron job + test restore procedures

### 23. Docker Image Security Scanning
- Use official slim Python images
- Run Trivy/Snyk on CI/CD
- Implement image signing

---

## 📋 PRODUCTION DEPLOYMENT CHECKLIST

Before going live, ensure ALL of the following:

### Environment Configuration
- [ ] Strong JWT_SECRET set (32+ bytes)
- [ ] COOKIE_SECURE=true
- [ ] DEV_EMAIL=false  
- [ ] DEBUG=false
- [ ] CORS_ORIGINS set to production domains only
- [ ] Database URL uses connection pooling
- [ ] SEED_ADMIN_PASSWORD and SEED_PLATFORM_PASSWORD set

### Security Implementation
- [ ] Rate limiting implemented on auth endpoints
- [ ] CSRF protection enabled
- [ ] Input sanitization applied to all user input
- [ ] Security headers verified in production
- [ ] File upload limits enforced at server level (nginx/uvicorn)

### Infrastructure
- [ ] Monitoring (Sentry/Datadog) configured
- [ ] Database backups automated and tested
- [ ] Database indexes added
- [ ] Email configured: `SMTP_*` (App Password) or `RESEND_API_KEY`, plus `OWNER_ALERT_EMAIL`
- [ ] SSL/TLS certificates installed
- [ ] Health check endpoint monitored

### Testing
- [ ] Run full test suite: `pytest -v` (all 187 tests passing)
- [ ] Load testing completed
- [ ] Security audit performed
- [ ] Backup restore tested

### Documentation
- [ ] Incident response runbook created
- [ ] Deployment procedures documented
- [ ] Database migration rollback tested
- [ ] Team trained on production procedures

---

## 🚀 ESTIMATED TIME TO PRODUCTION-READY

**Critical fixes (must-have):**
- Rate limiting: 2-3 hours
- CSRF protection: 4-6 hours
- Input sanitization: 6-8 hours
- **Total: 12-17 hours**

**High priority (strongly recommended):**
- Email service: 4-6 hours
- Monitoring setup: 2-4 hours
- Database indexes: 2 hours
- Audit logging: 3-4 hours
- **Total: 11-16 hours**

**Grand Total: 23-33 hours (3-4 days of focused work)**

---

## 📞 SUPPORT CONTACTS

For security issues:
- Email: security@yourdomain.com
- PGP Key: [link to public key]

For production incidents:
- Slack: #incidents
- PagerDuty: [link]

---

**Last Updated:** 2026-08-19
**Review Schedule:** Monthly security audits required
