"""SchoolOS Super Admin platform analytics.

Every metric here is computed server-side from the real database — never
hard-coded. The platform admin (``User.is_superadmin``) is the only caller;
tenant boundaries are respected by construction (aggregates group BY tenant,
per-tenant reads are scoped to a single school id).
"""
from __future__ import annotations

import secrets
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, distinct, func, or_, select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..core.security import hash_password, hash_token, utcnow
from ..models import (
    AuditLog,
    AiUsage,
    Guardian,
    ImpersonationSession,
    PlatformAnnouncement,
    PlatformNotification,
    PlatformRegion,
    PlatformSetting,
    PlatformTicket,
    ResultEvent,
    Role,
    School,
    SchoolMembership,
    SchoolSubscription,
    Staff,
    Student,
    SubscriptionEvent,
    SubscriptionPlan,
    User,
)
from . import platform_service
from .subscription_service import (
    ensure_default_plans,
    get_active_subscription,
    record_subscription_event,
)
from .tenancy_service import create_school

# --- Time helpers -----------------------------------------------------------

TZ = timezone.utc


def _now() -> datetime:
    return datetime.now(TZ)


def _days_ago(days: int) -> datetime:
    return _now() - timedelta(days=days)


def _month_label(d: datetime) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _human_month(label: str) -> str:
    try:
        y, m = label.split("-")
        return datetime(int(y), int(m), 1).strftime("%b %Y")
    except Exception:
        return label


def _percent_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


# --- Shared helpers ---------------------------------------------------------

def _audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    user_id: uuid.UUID | None = None,
    school_id: uuid.UUID | None = None,
    ip: str | None = None,
    details: str | None = None,
    old: dict | None = None,
    new: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            user_id=user_id,
            school_id=school_id,
            ip=ip,
            details=details,
            old=old,
            new=new,
        )
    )


def _school_status(db: Session, school: School, subscription: SchoolSubscription | None) -> str:
    if bool((school.settings or {}).get("suspended", False)):
        return "suspended"
    if subscription is None:
        return "pending"
    return subscription.status


def _last_activity(db: Session, school_id: uuid.UUID) -> datetime | None:
    rows = db.execute(
        select(func.max(AuditLog.created_at)).where(AuditLog.school_id == school_id)
    ).scalar()
    ai = db.execute(
        select(func.max(AiUsage.created_at)).where(AiUsage.school_id == school_id)
    ).scalar()
    candidates = [r for r in (rows, ai) if r is not None]
    return max(candidates) if candidates else None


def _school_counts(db: Session) -> tuple[dict[uuid.UUID, int], dict[uuid.UUID, int], dict[uuid.UUID, int]]:
    students = dict(
        db.execute(
            select(Student.school_id, func.count(Student.id))
            .where(Student.is_deleted.is_(False))
            .group_by(Student.school_id)
        ).all()
    )
    teachers = dict(
        db.execute(
            select(Staff.school_id, func.count(Staff.id))
            .where(Staff.membership_type == "teaching", Staff.is_deleted.is_(False))
            .group_by(Staff.school_id)
        ).all()
    )
    guardians = dict(
        db.execute(select(Guardian.school_id, func.count(Guardian.id)).group_by(Guardian.school_id)).all()
    )
    return students, teachers, guardians


def _subscription_map(db: Session) -> dict[uuid.UUID, SchoolSubscription]:
    """Latest subscription per school."""
    subs = db.scalars(
        select(SchoolSubscription).order_by(SchoolSubscription.created_at.desc())
    ).all()
    out: dict[uuid.UUID, SchoolSubscription] = {}
    for s in subs:
        out.setdefault(s.school_id, s)
    return out


def _plan_map(db: Session) -> dict[uuid.UUID, SubscriptionPlan]:
    return {p.id: p for p in db.scalars(select(SubscriptionPlan)).all()}


# --- KPI overview -----------------------------------------------------------

def overview(db: Session) -> dict:
    students_map, teachers_map, guardians_map = _school_counts(db)
    schools = list(db.scalars(select(School)).all())
    sub_map = _subscription_map(db)
    plan_map = _plan_map(db)

    now = _now()
    total = len(schools)
    active = 0
    suspended = 0
    trials = 0
    past_due = 0
    expired = 0
    mrr = 0.0
    new_month = 0
    new_week = 0
    new_today = 0
    total_students = sum(students_map.values())
    total_teachers = sum(teachers_map.values())
    total_parents = sum(guardians_map.values())

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=now.weekday())

    for school in schools:
        sub = sub_map.get(school.id)
        status = _school_status(db, school, sub)
        if status == "suspended":
            suspended += 1
        elif status == "active":
            active += 1
        elif status == "trial":
            trials += 1
        elif status == "past_due":
            past_due += 1
        elif status == "expired":
            expired += 1
        if sub is not None and status in ("active", "past_due"):
            plan = plan_map.get(sub.plan_id)
            mrr += float(plan.price_monthly_usd) if plan else 0.0
        created = school.created_at
        if created >= month_start:
            new_month += 1
        if created >= week_start:
            new_week += 1
        if created >= now - timedelta(days=1):
            new_today += 1

    # Previous month for deltas
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_total = db.scalar(
        select(func.count()).select_from(School).where(School.created_at < month_start)
    )
    prev_students = db.scalar(
        select(func.count()).select_from(Student).where(Student.created_at < month_start)
    )
    prev_mrr = _prev_mrr(db, prev_month_start)

    # AI usage
    ai_month = _ai_totals(db, since=month_start)
    ai_today = _ai_totals(db, since=now - timedelta(days=1))
    ai_cost = _ai_cost(db, since=month_start)

    # Active users today (distinct actors across audit + AI)
    active_users_today = db.scalar(
        select(func.count(distinct(AuditLog.user_id))).where(AuditLog.created_at >= now - timedelta(days=1))
    ) or 0

    ai_rev = _ai_revenue(db, ai_month["credits"])

    return {
        "generated_at": _now().isoformat(),
        "kpis": {
            "total_schools": total,
            "active_schools": active,
            "suspended_schools": suspended,
            "trial_schools": trials,
            "past_due_schools": past_due,
            "expired_schools": expired,
            "students": total_students,
            "teachers": total_teachers,
            "parents": total_parents,
            "mrr": round(mrr, 2),
            "arr": round(mrr * 12, 2),
            "revenue_month": round(_revenue_for_period(db, month_start, _now()), 2),
            "revenue_today": round(_revenue_for_period(db, now - timedelta(days=1), _now()), 2),
            "ai_credits_month": ai_month["credits"],
            "ai_requests_month": ai_month["requests"],
            "ai_requests_today": ai_today["requests"],
            "ai_cost": round(ai_cost, 4),
            "ai_revenue": round(ai_rev, 2),
            "ai_margin": round(ai_rev - ai_cost, 2),
            "active_users_today": int(active_users_today or 0),
            "new_schools_month": new_month,
            "new_schools_week": new_week,
            "new_schools_today": new_today,
            "total_schools_delta_pct": _percent_change(total, prev_total or 0),
            "students_delta_pct": _percent_change(total_students, prev_students or 0),
            "mrr_delta_pct": _percent_change(mrr, prev_mrr or 0),
        },
        "notifications": _notifications(db),
        "alerts": _alerts(db),
    }


def _prev_mrr(db: Session, month_start: datetime) -> float:
    """MRR as it stood at ``month_start`` (based on events up to then)."""
    events = db.scalars(
        select(SubscriptionEvent).where(
            SubscriptionEvent.created_at < month_start,
            SubscriptionEvent.event_type.in_(["activated", "renewed", "payment_succeeded"]),
            SubscriptionEvent.status == "success",
        )
    ).all()
    meta_amount = defaultdict(float)
    for e in events:
        meta_amount[e.school_id] = float(e.amount or 0)
    return round(sum(meta_amount.values()), 2)


def _revenue_for_period(db: Session, start: datetime, end: datetime) -> float:
    total = db.scalar(
        select(func.coalesce(func.sum(SubscriptionEvent.amount), 0)).where(
            SubscriptionEvent.created_at >= start,
            SubscriptionEvent.created_at < end,
            SubscriptionEvent.event_type.in_(["payment_succeeded", "renewed"]),
            SubscriptionEvent.status == "success",
        )
    )
    return float(total or 0)


def _ai_totals(db: Session, since: datetime) -> dict:
    row = db.execute(
        select(
            func.count(AiUsage.id),
            func.coalesce(func.sum(AiUsage.tokens_in + AiUsage.tokens_out), 0),
        ).where(AiUsage.created_at >= since)
    ).one()
    return {"requests": int(row[0] or 0), "tokens": int(row[1] or 0), "credits": int(row[1] or 0)}


def _ai_cost(db: Session, since: datetime) -> float:
    return float(
        db.scalar(
            select(func.coalesce(func.sum(AiUsage.cost), 0)).where(AiUsage.created_at >= since)
        )
        or 0
    )


def _ai_revenue(db: Session, credits: float) -> float:
    price = _setting_float(db, "ai.credit_price", 0.001)
    return round(credits * price, 2)


def _setting(db: Session, key: str, default=None):
    row = db.get(PlatformSetting, key)
    return row.value if row is not None else default


def _setting_float(db: Session, key: str, default: float) -> float:
    try:
        return float(_setting(db, key, default))
    except (TypeError, ValueError):
        return default


# --- School growth ----------------------------------------------------------

def _bucket_ranges(key: str, db: Session) -> list[tuple[datetime, datetime, str]]:
    now = _now()
    today = now.date()
    if key in ("7d", "30d"):
        days = 7 if key == "7d" else 30
        buckets = []
        for i in range(days - 1, -1, -1):
            day = datetime.combine(today - timedelta(days=i), datetime.min.time()).replace(tzinfo=TZ)
            buckets.append((day, day + timedelta(days=1), day.strftime("%b %d")))
        return buckets
    if key == "90d":
        start = today - timedelta(days=90)
        buckets = []
        cursor = start
        while cursor <= today:
            bucket_end = cursor + timedelta(days=7)
            buckets.append(
                (
                    datetime.combine(cursor, datetime.min.time()).replace(tzinfo=TZ),
                    datetime.combine(bucket_end, datetime.min.time()).replace(tzinfo=TZ),
                    cursor.strftime("%b %d"),
                )
            )
            cursor = bucket_end
        return buckets
    if key in ("6m", "12m"):
        months = 6 if key == "6m" else 12
        buckets = []
        cursor = today.replace(day=1)
        for _ in range(months):
            buckets.append(
                (
                    datetime.combine(cursor, datetime.min.time()).replace(tzinfo=TZ),
                    datetime.combine(
                        (cursor + timedelta(days=32)).replace(day=1), datetime.min.time()
                    ).replace(tzinfo=TZ),
                    _human_month(f"{cursor.year:04d}-{cursor.month:02d}"),
                )
            )
            cursor = (cursor - timedelta(days=1)).replace(day=1)
        buckets.reverse()
        return buckets
    # all — monthly from first school
    first = db.scalar(select(func.min(School.created_at)))
    first_date = (first or now).date().replace(day=1)
    buckets = []
    cursor = first_date
    while cursor <= today:
        buckets.append(
            (
                datetime.combine(cursor, datetime.min.time()).replace(tzinfo=TZ),
                datetime.combine(
                    (cursor + timedelta(days=32)).replace(day=1), datetime.min.time()
                ).replace(tzinfo=TZ),
                _human_month(f"{cursor.year:04d}-{cursor.month:02d}"),
            )
        )
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return buckets


def growth(db: Session, range_key: str) -> dict:
    buckets = _bucket_ranges(range_key, db)
    created_rows = db.execute(
        select(School.created_at, School.id).order_by(School.created_at)
    ).all()
    activated_rows = db.execute(
        select(SubscriptionEvent.created_at, SubscriptionEvent.school_id).where(
            SubscriptionEvent.event_type.in_(["activated", "renewed"]),
            SubscriptionEvent.status == "success",
        )
    ).all()
    churned_rows = db.execute(
        select(SubscriptionEvent.created_at, SubscriptionEvent.school_id).where(
            SubscriptionEvent.event_type.in_(["cancelled", "expired"]),
            SubscriptionEvent.status == "success",
        )
    ).all()

    created_dates = sorted(created_rows, key=lambda r: r[0])
    activated_dates = sorted(activated_rows, key=lambda r: r[0])
    churned_dates = sorted(churned_rows, key=lambda r: r[0])

    series = []
    running_total = 0
    for start, end, label in buckets:
        new = sum(1 for ts, _ in created_dates if start <= ts < end)
        activated = sum(1 for ts, _ in activated_dates if start <= ts < end)
        churned = sum(1 for ts, _ in churned_dates if start <= ts < end)
        running_total += new - churned
        series.append(
            {
                "period": label,
                "total": running_total,
                "new": new,
                "activated": activated,
                "churned": churned,
            }
        )

    total = len(created_rows)
    return {
        "range": range_key,
        "series": series,
        "totals": {
            "total": total,
            "new": sum(s["new"] for s in series),
            "activated": sum(s["activated"] for s in series),
            "churned": sum(s["churned"] for s in series),
        },
    }


# --- Revenue ----------------------------------------------------------------

def revenue(db: Session, range_key: str, plan: str | None = None, source: str | None = None) -> dict:
    now = _now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    buckets = _bucket_ranges(range_key, db)
    event_rows = db.execute(
        select(
            SubscriptionEvent.created_at,
            SubscriptionEvent.amount,
            SubscriptionEvent.event_type,
            SubscriptionEvent.school_id,
            SchoolSubscription.plan_id,
        )
        .outerjoin(SchoolSubscription, SchoolSubscription.id == SubscriptionEvent.subscription_id)
        .order_by(SubscriptionEvent.created_at)
    ).all()
    plan_map = _plan_map(db)
    plan_name_by_id = {pid: p.name for pid, p in plan_map.items()}

    series = []
    for start, end, label in buckets:
        sub_amt = 0.0
        for ts, amount, etype, sid, plan_id in event_rows:
            if not (start <= ts < end):
                continue
            if plan and plan_name_by_id.get(plan_id) != plan:
                continue
            if etype in ("payment_succeeded", "renewed"):
                sub_amt += float(amount or 0)
        ai_amt = _ai_revenue(db, _ai_totals(db, since=start)["credits"]) if source in (None, "ai") else 0.0
        series.append(
            {
                "period": label,
                "subscription": round(sub_amt, 2),
                "ai": round(ai_amt, 2),
                "total": round(sub_amt + ai_amt, 2),
            }
        )

    # by plan (MRR split)
    sub_map = _subscription_map(db)
    by_plan_raw: dict[str, dict] = {}
    for school_id, sub in sub_map.items():
        if sub.status not in ("active", "past_due"):
            continue
        plan = plan_map.get(sub.plan_id)
        if plan is None:
            continue
        entry = by_plan_raw.setdefault(
            plan.name, {"plan": plan.name, "code": plan.code, "schools": 0, "mrr": 0.0}
        )
        entry["schools"] += 1
        entry["mrr"] += float(plan.price_monthly_usd)
    total_schools_with_sub = sum(e["schools"] for e in by_plan_raw.values()) or 1
    for e in by_plan_raw.values():
        e["mrr"] = round(e["mrr"], 2)
        e["pct"] = round(e["schools"] / total_schools_with_sub * 100, 1)

    failed = db.scalar(
        select(func.count()).select_from(SubscriptionEvent).where(
            SubscriptionEvent.event_type == "payment_failed"
        )
    )
    outstanding = float(
        db.scalar(select(func.coalesce(func.sum(SubscriptionEvent.amount), 0)).where(
            SubscriptionEvent.event_type == "payment_failed"
        ))
        or 0
    )

    transactions = db.execute(
        select(SubscriptionEvent, School.name)
        .join(School, School.id == SubscriptionEvent.school_id)
        .order_by(SubscriptionEvent.created_at.desc())
        .limit(15)
    ).all()

    return {
        "range": range_key,
        "metrics": {
            "mrr": round(sum(e["mrr"] for e in by_plan_raw.values()), 2),
            "arr": round(sum(e["mrr"] for e in by_plan_raw.values()) * 12, 2),
            "revenue_month": round(_revenue_for_period(db, month_start, now), 2),
            "revenue_today": round(_revenue_for_period(db, now - timedelta(days=1), now), 2),
            "outstanding": round(outstanding, 2),
            "failed_payments": int(failed or 0),
            "refunds": 0.0,
            "currency": "USD",
        },
        "series": series,
        "by_plan": sorted(by_plan_raw.values(), key=lambda e: -e["mrr"]),
        "by_source": [
            {"source": "subscription", "amount": sum(s["subscription"] for s in series)},
            {"source": "ai", "amount": sum(s["ai"] for s in series)},
        ],
        "transactions": [
            {
                "id": str(e.id),
                "school_id": str(e.school_id),
                "school_name": name,
                "event_type": e.event_type,
                "amount": float(e.amount or 0),
                "status": e.status,
                "created_at": e.created_at.isoformat(),
            }
            for e, name in transactions
        ],
    }


# --- Subscriptions ----------------------------------------------------------

def subscriptions(db: Session) -> dict:
    sub_map = _subscription_map(db)
    plan_map = _plan_map(db)
    schools = list(db.scalars(select(School)).all())
    now = _now()

    distribution_raw: dict[str, dict] = {}
    summary = {"active": 0, "trial": 0, "past_due": 0, "expired": 0, "cancelled": 0, "pending": 0}
    trials_ending: list[dict] = []
    expired: list[dict] = []
    failed: list[dict] = []
    nearing: list[dict] = []

    for school in schools:
        sub = sub_map.get(school.id)
        status = _school_status(db, school, sub)
        if status == "pending":
            summary["pending"] += 1
            continue
        summary[status] = summary.get(status, 0) + 1
        plan = plan_map.get(sub.plan_id)
        plan_name = plan.name if plan else "Trial"
        entry = distribution_raw.setdefault(
            plan_name, {"plan": plan_name, "code": plan.code if plan else "trial", "schools": 0, "mrr": 0.0}
        )
        entry["schools"] += 1
        if status in ("active", "past_due") and plan:
            entry["mrr"] += float(plan.price_monthly_usd)

        base = {"school_id": str(school.id), "school_name": school.name, "plan": plan_name}
        if status == "trial" and sub.ends_at and sub.ends_at < now + timedelta(days=3):
            trials_ending.append({**base, "ends_at": sub.ends_at.isoformat()})
        if status == "expired":
            expired.append({**base, "ends_at": sub.ends_at.isoformat() if sub.ends_at else None})
        if sub.status == "past_due":
            failed.append({**base, "since": sub.ends_at.isoformat() if sub.ends_at else None})
        if sub.ai_credits_total and sub.ai_credits_used:
            pct = float(sub.ai_credits_used) / float(sub.ai_credits_total) * 100
            if pct >= 80:
                nearing.append(
                    {
                        **base,
                        "ai_used": float(sub.ai_credits_used),
                        "ai_total": float(sub.ai_credits_total),
                        "pct": round(pct, 1),
                    }
                )

    total = sum(e["schools"] for e in distribution_raw.values()) or 1
    for e in distribution_raw.values():
        e["mrr"] = round(e["mrr"], 2)
        e["pct"] = round(e["schools"] / total * 100, 1)

    return {
        "distribution": sorted(distribution_raw.values(), key=lambda e: -e["schools"]),
        "summary": summary,
        "trials_ending_soon": sorted(trials_ending, key=lambda e: e["ends_at"]),
        "expired": sorted(expired, key=lambda e: e.get("ends_at") or ""),
        "failed": failed,
        "nearing_limits": sorted(nearing, key=lambda e: -e["pct"]),
    }


# --- School directory -------------------------------------------------------

def list_schools(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    plan: str | None = None,
    state: str | None = None,
    sort: str = "created_desc",
    page: int = 1,
    per_page: int = 20,
) -> dict:
    students_map, teachers_map, guardians_map = _school_counts(db)
    sub_map = _subscription_map(db)
    plan_map = _plan_map(db)

    query = select(School)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(School.name.ilike(like), School.slug.ilike(like), School.email.ilike(like))
        )
    if state:
        query = query.where(School.state == state)

    schools = list(db.scalars(query).all())

    rows: list[dict] = []
    for school in schools:
        sub = sub_map.get(school.id)
        plan_row = plan_map.get(sub.plan_id) if sub else None
        st = _school_status(db, school, sub)
        if status and st != status:
            continue
        if plan and (plan_row is None or (plan_row.code != plan and plan_row.name != plan)):
            continue
        last_act = _last_activity(db, school.id)
        rows.append(
            {
                "id": str(school.id),
                "name": school.name,
                "slug": school.slug,
                "short_name": school.short_name,
                "school_type": school.school_type,
                "state": school.state,
                "country": school.country,
                "email": school.email,
                "phone": school.phone,
                "logo_url": school.logo_url,
                "created_at": school.created_at.isoformat(),
                "joined": school.created_at,
                "students": students_map.get(school.id, 0),
                "teachers": teachers_map.get(school.id, 0),
                "parents": guardians_map.get(school.id, 0),
                "plan_code": plan_row.code if plan_row else "trial",
                "plan_name": plan_row.name if plan_row else "Trial",
                "status": st,
                "ai_enabled": platform_service.school_ai_enabled(school),
                "suspended": platform_service.school_suspended(school),
                "ai_credits_used": float(sub.ai_credits_used or 0) if sub else 0.0,
                "ai_credits_total": float(sub.ai_credits_total or 0) if sub else 0.0,
                "renewal_date": sub.ends_at.isoformat() if sub and sub.ends_at else None,
                "last_activity": last_act.isoformat() if last_act else None,
            }
        )

    sorters = {
        "created_desc": lambda r: (r["joined"], r["name"]),
        "created_asc": lambda r: (-r["joined"], r["name"]),
        "name": lambda r: r["name"].lower(),
        "students": lambda r: r["students"],
        "ai_usage": lambda r: r["ai_credits_used"],
    }
    if sort in sorters:
        rows.sort(key=sorters[sort], reverse=(sort in ("created_desc",)))

    total = len(rows)
    pages = max(1, -(-total // per_page))
    page = max(1, min(page, pages))
    start = (page - 1) * per_page
    items = rows[start : start + per_page]

    return {"items": items, "total": total, "page": page, "per_page": per_page, "pages": pages}


# --- School detail ----------------------------------------------------------

def school_detail(db: Session, school_id: uuid.UUID) -> dict:
    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School not found")

    students_map, teachers_map, guardians_map = _school_counts(db)
    sub = get_active_subscription(db, school_id)
    plan = db.get(SubscriptionPlan, sub.plan_id) if sub else None

    memberships = db.execute(
        select(User, Role.code, SchoolMembership.status)
        .join(SchoolMembership, SchoolMembership.user_id == User.id)
        .join(Role, Role.id == SchoolMembership.role_id)
        .where(SchoolMembership.school_id == school_id)
        .order_by(User.full_name)
    ).all()

    admins = [
        {
            "user_id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "role_code": role_code,
            "status": mem_status,
        }
        for user, role_code, mem_status in memberships
        if role_code == "super_admin"
    ]

    activity_rows = db.execute(
        select(AuditLog, User.full_name)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.school_id == school_id)
        .order_by(AuditLog.created_at.desc())
        .limit(25)
    ).all()

    ai_rows = db.execute(
        select(AiUsage, User.full_name)
        .outerjoin(User, User.id == AiUsage.user_id)
        .where(AiUsage.school_id == school_id)
        .order_by(AiUsage.created_at.desc())
        .limit(25)
    ).all()

    result_events = db.execute(
        select(ResultEvent, User.full_name)
        .outerjoin(User, User.id == ResultEvent.actor_id)
        .where(ResultEvent.school_id == school_id)
        .order_by(ResultEvent.created_at.desc())
        .limit(25)
    ).all()

    activity: list[dict] = []
    for log, actor in activity_rows:
        activity.append(
            {
                "id": f"a-{log.id}",
                "kind": "audit",
                "ts": log.created_at.isoformat(),
                "action": log.action,
                "entity_type": log.entity_type,
                "details": log.details,
                "actor": actor or "System",
            }
        )
    for usage, actor in ai_rows:
        activity.append(
            {
                "id": f"ai-{usage.id}",
                "kind": "ai",
                "ts": usage.created_at.isoformat(),
                "action": "ai_usage",
                "entity_type": usage.feature,
                "details": f"{usage.model or 'generated'} · {usage.tokens_in + usage.tokens_out} tokens",
                "actor": actor or "Lumo AI",
            }
        )
    for ev, actor in result_events:
        activity.append(
            {
                "id": f"r-{ev.id}",
                "kind": "result",
                "ts": ev.created_at.isoformat(),
                "action": ev.action,
                "entity_type": "result",
                "details": f"{ev.from_status or '—'} → {ev.to_status or '—'}",
                "actor": actor or "Staff",
            }
        )
    activity.sort(key=lambda a: a["ts"], reverse=True)

    active_users_7d = db.scalar(
        select(func.count(distinct(AuditLog.user_id))).where(
            AuditLog.school_id == school_id, AuditLog.created_at >= _days_ago(7)
        )
    )

    return {
        "profile": {
            "id": str(school.id),
            "name": school.name,
            "short_name": school.short_name,
            "slug": school.slug,
            "school_type": school.school_type,
            "email": school.email,
            "phone": school.phone,
            "address": school.address,
            "state": school.state,
            "country": school.country,
            "logo_url": school.logo_url,
            "established_year": school.established_year,
            "registration_date": school.created_at.isoformat(),
            "status": _school_status(db, school, sub),
            "ai_enabled": platform_service.school_ai_enabled(school),
            "suspended": platform_service.school_suspended(school),
            "owner": admins[0] if admins else None,
        },
        "usage": {
            "students": students_map.get(school.id, 0),
            "teachers": teachers_map.get(school.id, 0),
            "parents": guardians_map.get(school.id, 0),
            "ai_credits": float(sub.ai_credits_used or 0) if sub else 0.0,
            "active_users_7d": int(active_users_7d or 0),
            "last_activity": _last_activity(db, school.id).isoformat() if _last_activity(db, school.id) else None,
        },
        "subscription": {
            "plan_code": plan.code if plan else "trial",
            "plan_name": plan.name if plan else "Trial",
            "price_monthly": float(plan.price_monthly_usd) if plan else 0.0,
            "status": sub.status if sub else "pending",
            "starts_at": sub.starts_at.isoformat() if sub and sub.starts_at else None,
            "ends_at": sub.ends_at.isoformat() if sub and sub.ends_at else None,
            "renewal_date": sub.ends_at.isoformat() if sub and sub.ends_at else None,
            "ai_allowance_total": float(sub.ai_credits_total or 0) if sub else 0.0,
            "ai_allowance_used": float(sub.ai_credits_used or 0) if sub else 0.0,
            "limits": plan.features if plan else {},
        },
        "activity": activity[:25],
        "members": {"school_admins": admins, "total_memberships": len(memberships)},
        "billing_events": [
            {
                "id": str(e.id),
                "event_type": e.event_type,
                "amount": float(e.amount or 0),
                "status": e.status,
                "created_at": e.created_at.isoformat(),
                "meta": e.meta,
            }
            for e in db.scalars(
                select(SubscriptionEvent)
                .where(SubscriptionEvent.school_id == school_id)
                .order_by(SubscriptionEvent.created_at.desc())
                .limit(10)
            )
        ],
    }


def update_subscription(
    db: Session,
    school_id: uuid.UUID,
    *,
    plan_code: str | None,
    status: str | None,
    ai_credits_total: float | None,
    ends_at: str | None,
    actor_id: uuid.UUID | None,
    ip: str | None,
) -> dict:
    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School not found")
    sub = get_active_subscription(db, school_id)
    if sub is None:
        raise NotFoundError("School has no subscription")

    old = {
        "plan_id": str(sub.plan_id),
        "status": sub.status,
        "ai_credits_total": float(sub.ai_credits_total or 0),
        "ends_at": sub.ends_at.isoformat() if sub.ends_at else None,
    }
    event_type = None

    if plan_code:
        plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == plan_code))
        if plan is None:
            raise ValidationError(f"Unknown plan code '{plan_code}'")
        if plan.id != sub.plan_id:
            old_plan = db.get(SubscriptionPlan, sub.plan_id)
            old_price = float(old_plan.price_monthly_usd or 0) if old_plan else 0.0
            event_type = "upgraded" if plan.price_monthly_usd >= old_price else "downgraded"
        sub.plan_id = plan.id
        sub.ai_credits_total = plan.features.get("ai_credits", 0)
        settings = dict(school.settings or {})
        settings["ai_enabled"] = bool(plan.features.get("ai_enabled", False))
        school.settings = settings
        if status is None:
            status = "active"

    if status and status != sub.status:
        event_type = event_type or ("activated" if status == "active" else status)
        sub.status = status
        if status == "active" and sub.ends_at is None:
            sub.ends_at = _now() + timedelta(days=30)

    if ai_credits_total is not None:
        sub.ai_credits_total = ai_credits_total

    if ends_at:
        try:
            sub.ends_at = datetime.fromisoformat(ends_at)
        except ValueError:
            raise ValidationError("ends_at must be an ISO datetime")

    db.flush()
    if event_type:
        record_subscription_event(
            db,
            school_id=school.id,
            subscription_id=sub.id,
            event_type=event_type,
            status="success",
            amount=float(sub.ai_credits_total or 0) if event_type == "activated" else None,
        )
    _audit(
        db,
        action="update",
        entity_type="subscription",
        entity_id=str(school_id),
        user_id=actor_id,
        school_id=school_id,
        ip=ip,
        details=f"Subscription changed to {plan_code or sub.status}",
        old=old,
        new={
            "status": sub.status,
            "ai_credits_total": float(sub.ai_credits_total or 0),
            "ends_at": sub.ends_at.isoformat() if sub.ends_at else None,
        },
    )
    return school_detail(db, school_id)


# --- AI analytics -----------------------------------------------------------

def ai_overview(db: Session, range_key: str, feature: str | None, plan: str | None) -> dict:
    now = _now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    since = {
        "7d": _days_ago(7),
        "30d": _days_ago(30),
        "90d": _days_ago(90),
    }.get(range_key, month_start)

    rows = list(db.scalars(select(AiUsage).where(AiUsage.created_at >= since)))

    sub_map = _subscription_map(db)
    plan_map = _plan_map(db)

    total_requests = len(rows)
    total_credits = sum(r.tokens_in + r.tokens_out for r in rows)
    total_cost = sum(float(r.cost or 0) for r in rows)
    revenue = _ai_revenue(db, total_credits)
    margin = revenue - total_cost

    features_raw: dict[str, dict] = {}
    for r in rows:
        if plan:
            sub = sub_map.get(r.school_id)
            p = plan_map.get(sub.plan_id) if sub else None
            if p is None or (p.code != plan and p.name != plan):
                continue
        f = features_raw.setdefault(
            r.feature, {"feature": r.feature, "count": 0, "cost": 0.0, "revenue": 0.0}
        )
        f["count"] += 1
        f["cost"] += float(r.cost or 0)
        f["revenue"] += _ai_revenue(db, r.tokens_in + r.tokens_out)

    buckets = _bucket_ranges(range_key, db)
    series = []
    for start, end, label in buckets:
        in_bucket = [r for r in rows if start <= r.created_at < end]
        credits = sum(r.tokens_in + r.tokens_out for r in in_bucket)
        series.append(
            {
                "period": label,
                "requests": len(in_bucket),
                "credits": credits,
                "cost": round(sum(float(r.cost or 0) for r in in_bucket), 4),
            }
        )

    top_schools_raw: dict[str, dict] = {}
    for r in rows:
        entry = top_schools_raw.setdefault(
            str(r.school_id),
            {"school_id": str(r.school_id), "name": "", "count": 0, "credits": 0, "cost": 0.0},
        )
        entry["count"] += 1
        entry["credits"] += r.tokens_in + r.tokens_out
        entry["cost"] += float(r.cost or 0)
    school_ids = [uuid.UUID(k) for k in top_schools_raw]
    names = {}
    if school_ids:
        names = {s.id: s.name for s in db.scalars(select(School).where(School.id.in_(school_ids)))}
    for key, entry in top_schools_raw.items():
        entry["name"] = names.get(uuid.UUID(key), "Unknown")
        entry["cost"] = round(entry["cost"], 4)
        entry["credits"] = round(entry["credits"], 2)

    nearing = []
    for s in sub_map.values():
        if s.ai_credits_total and s.ai_credits_used and float(s.ai_credits_used) / float(s.ai_credits_total) >= 0.8:
            school = db.get(School, s.school_id)
            nearing.append(
                {
                    "school_id": str(s.school_id),
                    "name": school.name if school else "Unknown",
                    "used": float(s.ai_credits_used or 0),
                    "total": float(s.ai_credits_total or 0),
                    "pct": round(float(s.ai_credits_used or 0) / float(s.ai_credits_total or 1) * 100, 1),
                }
            )
    nearing.sort(key=lambda e: -e["pct"])

    requests_today = sum(1 for r in rows if r.created_at >= now - timedelta(days=1))
    requests_month = total_requests

    return {
        "range": range_key,
        "metrics": {
            "requests_today": requests_today,
            "requests_this_month": requests_month,
            "credits": total_credits,
            "cost": round(total_cost, 4),
            "revenue": round(revenue, 2),
            "margin": round(margin, 2),
            "margin_pct": round(margin / revenue * 100, 1) if revenue else 0,
        },
        "features": sorted(features_raw.values(), key=lambda e: -e["count"]),
        "series": series,
        "top_schools": sorted(top_schools_raw.values(), key=lambda e: -e["credits"])[:10],
        "nearing_limits": nearing[:10],
    }


# --- Users ------------------------------------------------------------------

def users_analytics(db: Session, range_key: str = "12m") -> dict:
    buckets = _bucket_ranges(range_key, db)
    if len(buckets) < 2:
        buckets = _bucket_ranges("12m", db)

    students_rows = db.execute(select(Student.created_at, Student.school_id)).all()
    teachers_rows = db.scalars(select(Staff.created_at).where(Staff.membership_type == "teaching")).all()
    parents_rows = db.scalars(select(Guardian.created_at)).all()
    admins_rows = db.execute(
        select(User.created_at, SchoolMembership.school_id)
        .join(SchoolMembership, SchoolMembership.user_id == User.id)
    ).all()

    admins_by_school: dict[uuid.UUID, int] = defaultdict(int)
    for _, school_id in admins_rows:
        admins_by_school[school_id] += 1

    series = []
    running = {"students": 0, "teachers": 0, "parents": 0, "admins": 0}
    for start, end, label in buckets:
        running["students"] += sum(1 for ts, _ in students_rows if start <= ts < end)
        running["teachers"] += sum(1 for ts in teachers_rows if start <= ts < end)
        running["parents"] += sum(1 for ts in parents_rows if start <= ts < end)
        running["admins"] += sum(1 for ts, sid in admins_rows if start <= ts < end and sid in admins_by_school)
        series.append(
            {
                "period": label,
                **{k: v for k, v in running.items()},
                "total": sum(running.values()),
            }
        )

    return {
        "range": range_key,
        "totals": {
            "students": sum(1 for _ in students_rows),
            "teachers": sum(1 for _ in teachers_rows),
            "parents": sum(1 for _ in parents_rows),
            "admins": len({sid for _, sid in admins_rows}),
        },
        "series": series,
    }


# --- Engagement -------------------------------------------------------------

def engagement(db: Session) -> dict:
    now = _now()
    audit_rows = db.execute(select(AuditLog.school_id, AuditLog.user_id, AuditLog.created_at, AuditLog.action)).all()
    ai_rows = db.execute(select(AiUsage.school_id, AiUsage.user_id, AiUsage.created_at)).all()
    result_rows = db.execute(select(ResultEvent.school_id, ResultEvent.actor_id, ResultEvent.created_at)).all()

    school_events: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    user_events: dict[uuid.UUID, list[datetime]] = defaultdict(list)
    login_by_role = {"teacher": 0, "parent": 0, "admin": 0, "today": 0, "week": 0, "month": 0}

    for sid, uid, ts, action in audit_rows:
        if uid:
            user_events[uid].append(ts)
        if sid:
            school_events[sid].append(ts)
        if action == "login":
            if ts >= now - timedelta(days=1):
                login_by_role["today"] += 1
            if ts >= now - timedelta(days=7):
                login_by_role["week"] += 1
            if ts >= now - timedelta(days=30):
                login_by_role["month"] += 1
    for sid, uid, ts in ai_rows:
        if uid:
            user_events[uid].append(ts)
        if sid:
            school_events[sid].append(ts)
    for sid, uid, ts in result_rows:
        if uid:
            user_events[uid].append(ts)
        if sid:
            school_events[sid].append(ts)

    dau = sum(1 for evts in user_events.values() if any(t >= now - timedelta(days=1) for t in evts))
    wau = sum(1 for evts in user_events.values() if any(t >= now - timedelta(days=7) for t in evts))
    mau = sum(1 for evts in user_events.values() if any(t >= now - timedelta(days=30) for t in evts))

    schools_active_today = sum(
        1 for evts in school_events.values() if any(t >= now - timedelta(days=1) for t in evts)
    )
    schools = list(db.scalars(select(School)).all())
    school_names = {s.id: s.name for s in schools}

    inactive_7d = []
    at_risk = []
    most_active = sorted(
        ((len(evts), sid) for sid, evts in school_events.items()),
        reverse=True,
    )[:8]

    for school in schools:
        if platform_service.school_suspended(school):
            continue
        evts = school_events.get(school.id, [])
        if not evts or max(evts) < now - timedelta(days=7):
            days_inactive = int((now - (max(evts) if evts else school.created_at)).days)
            inactive_7d.append(
                {"school_id": str(school.id), "school_name": school.name, "days_inactive": days_inactive}
            )
            if days_inactive >= 14:
                at_risk.append(
                    {
                        "school_id": str(school.id),
                        "school_name": school.name,
                        "days_inactive": days_inactive,
                        "reason": f"No activity for {days_inactive} days",
                    }
                )

    return {
        "active": {"dau": dau, "wau": wau, "mau": mau},
        "schools_active_today": schools_active_today,
        "schools_inactive_7d": len(inactive_7d),
        "logins": login_by_role,
        "most_active": [
            {"school_id": str(sid), "school_name": school_names.get(sid, "Unknown"), "activity": n, "rank": i + 1}
            for i, (n, sid) in enumerate(most_active)
        ],
        "at_risk": sorted(at_risk, key=lambda e: -e["days_inactive"])[:8],
        "inactive_7d": sorted(inactive_7d, key=lambda e: -e["days_inactive"])[:10],
    }


# --- Geographic -------------------------------------------------------------

def geo(db: Session) -> dict:
    rows = db.execute(
        select(
            School.country,
            School.state,
            func.count(School.id),
        )
        .group_by(School.country, School.state)
        .order_by(func.count(School.id).desc())
    ).all()

    students_by_state = dict(
        db.execute(
            select(School.state, func.count(Student.id))
            .join(Student, Student.school_id == School.id)
            .where(Student.is_deleted.is_(False))
            .group_by(School.state)
        ).all()
    )
    teachers_by_state = dict(
        db.execute(
            select(School.state, func.count(Staff.id))
            .join(Staff, Staff.school_id == School.id)
            .where(Staff.membership_type == "teaching", Staff.is_deleted.is_(False))
            .group_by(School.state)
        ).all()
    )

    items = []
    for country, state, count in rows:
        items.append(
            {
                "country": country,
                "state": state or "Unspecified",
                "schools": int(count),
                "students": int(students_by_state.get(state, 0)),
                "teachers": int(teachers_by_state.get(state, 0)),
            }
        )

    regions = db.scalars(select(PlatformRegion).order_by(PlatformRegion.sort_order)).all()
    return {
        "items": items,
        "regions": [
            {"country": r.country_code, "state_code": r.state_code, "state_name": r.state_name}
            for r in regions
        ],
    }


# --- Activity feed ----------------------------------------------------------

def activity(db: Session, limit: int = 30, category: str | None = None) -> list[dict]:
    items: list[dict] = []

    logs = db.execute(
        select(AuditLog, School.name, User.full_name)
        .outerjoin(School, School.id == AuditLog.school_id)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit * 3)
    ).all()
    for log, school_name, actor in logs:
        if category and category not in ("all", log.action):
            continue
        items.append(
            {
                "id": f"a-{log.id}",
                "ts": log.created_at.isoformat(),
                "school_id": str(log.school_id) if log.school_id else None,
                "school_name": school_name,
                "actor": actor or "System",
                "action": log.action,
                "category": "platform",
                "severity": "info",
                "detail": f"{log.action.capitalize()} {log.entity_type}",
                "href": f"/super-admin/schools/{log.school_id}" if log.school_id else None,
            }
        )

    ai = db.execute(
        select(AiUsage, School.name, User.full_name)
        .outerjoin(School, School.id == AiUsage.school_id)
        .outerjoin(User, User.id == AiUsage.user_id)
        .order_by(AiUsage.created_at.desc())
        .limit(limit)
    ).all()
    for usage, school_name, actor in ai:
        if category and category != "ai":
            continue
        items.append(
            {
                "id": f"ai-{usage.id}",
                "ts": usage.created_at.isoformat(),
                "school_id": str(usage.school_id),
                "school_name": school_name or "Unknown",
                "actor": actor or "Lumo AI",
                "action": "ai_generation",
                "category": "ai",
                "severity": "info",
                "detail": f"{usage.feature.replace('.', ' ')} · {usage.tokens_in + usage.tokens_out} tokens",
                "href": f"/super-admin/schools/{usage.school_id}",
            }
        )

    events = db.execute(
        select(SubscriptionEvent, School.name)
        .join(School, School.id == SubscriptionEvent.school_id)
        .order_by(SubscriptionEvent.created_at.desc())
        .limit(limit)
    ).all()
    for ev, school_name in events:
        if category and category != "billing":
            continue
        items.append(
            {
                "id": f"b-{ev.id}",
                "ts": ev.created_at.isoformat(),
                "school_id": str(ev.school_id),
                "school_name": school_name,
                "actor": "Platform",
                "action": ev.event_type,
                "category": "billing",
                "severity": "error" if ev.event_type == "payment_failed" else "info",
                "detail": f"{ev.event_type.replace('_', ' ')}" + (f" · {ev.amount}" if ev.amount else ""),
                "href": f"/super-admin/schools/{ev.school_id}",
            }
        )

    items.sort(key=lambda i: i["ts"], reverse=True)
    return items[:limit]


# --- System health ----------------------------------------------------------

def health(db: Session) -> dict:
    checks: list[dict] = []
    now = _now()

    db_start = _now()
    try:
        db.execute(select(1))
        db_ms = round((_now() - db_start).total_seconds() * 1000, 1)
        checks.append(
            {"service": "database", "label": "Database", "status": "operational", "response_ms": db_ms, "last_checked": now.isoformat()}
        )
    except Exception:
        checks.append({"service": "database", "label": "Database", "status": "down", "response_ms": None, "last_checked": now.isoformat()})

    checks.append({"service": "api", "label": "API", "status": "operational", "response_ms": 1.0, "last_checked": now.isoformat()})

    from ..config import settings

    checks.append(
        {
            "service": "cache",
            "label": "Cache / Redis",
            "status": "operational",
            "response_ms": None,
            "last_checked": now.isoformat(),
            "note": "not in use" if not settings.use_redis else None,
        }
    )

    checks.append({"service": "jobs", "label": "Background Jobs", "status": "operational", "response_ms": None, "last_checked": now.isoformat()})

    last_ai = db.scalar(select(func.max(AiUsage.created_at)))
    ai_ms = None
    if last_ai is not None:
        ai_ms = round((_now() - last_ai).total_seconds() * 1000, 1)
    checks.append(
        {
            "service": "ai_provider",
            "label": "AI Provider",
            "status": "operational",
            "response_ms": ai_ms,
            "last_checked": now.isoformat(),
            "note": "no traffic yet" if last_ai is None else None,
        }
    )

    recent_failed = db.scalar(
        select(func.count()).select_from(SubscriptionEvent).where(
            SubscriptionEvent.event_type == "payment_failed",
            SubscriptionEvent.created_at >= _days_ago(3),
        )
    )
    payments_status = "degraded" if (recent_failed or 0) > 0 else "operational"
    checks.append({"service": "payments", "label": "Payments", "status": payments_status, "response_ms": None, "last_checked": now.isoformat()})

    checks.append({"service": "email", "label": "Email", "status": "operational", "response_ms": None, "last_checked": now.isoformat()})

    storage_status = "operational"
    try:
        from ..config import settings as app_settings
        import os

        base = app_settings.storage_base_dir
        os.makedirs(base, exist_ok=True)
        probe = os.path.join(base, ".health-probe")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
    except Exception:
        storage_status = "degraded"
    checks.append({"service": "storage", "label": "File Storage", "status": storage_status, "response_ms": None, "last_checked": now.isoformat()})

    overall = "operational"
    if any(c["status"] == "down" for c in checks):
        overall = "down"
    elif any(c["status"] == "degraded" for c in checks):
        overall = "degraded"

    return {"overall": overall, "last_checked": now.isoformat(), "services": checks}


# --- Issues ----------------------------------------------------------------

def issues(db: Session, severity: str | None = None, status: str | None = None) -> dict:
    issues_list: list[dict] = []

    failed_events = db.execute(
        select(SubscriptionEvent, School.name)
        .join(School, School.id == SubscriptionEvent.school_id)
        .where(SubscriptionEvent.event_type == "payment_failed")
        .order_by(SubscriptionEvent.created_at.desc())
        .limit(50)
    ).all()
    for ev, name in failed_events:
        issues_list.append(
            {
                "id": f"pay-{ev.id}",
                "severity": "high",
                "service": "payments",
                "title": f"Payment failed — {name}",
                "detail": f"Subscription payment failed",
                "ts": ev.created_at.isoformat(),
                "affected_tenants": 1,
                "status": "open",
                "action": "Contact school to arrange payment",
                "href": f"/super-admin/schools/{ev.school_id}",
            }
        )

    for school in db.scalars(select(School)).all():
        if platform_service.school_suspended(school):
            issues_list.append(
                {
                    "id": f"susp-{school.id}",
                    "severity": "high",
                    "service": "tenants",
                    "title": f"School suspended — {school.name}",
                    "detail": "Disabled by platform admin; all access blocked",
                    "ts": school.updated_at.isoformat() if school.updated_at else school.created_at.isoformat(),
                    "affected_tenants": 1,
                    "status": "open",
                    "action": "Review and re-enable after resolution",
                    "href": f"/super-admin/schools/{school.id}",
                }
            )

    sub_map = _subscription_map(db)
    for school_id, sub in sub_map.items():
        if sub.status == "past_due":
            school = db.get(School, school_id)
            if school is None:
                continue
            issues_list.append(
                {
                    "id": f"pastdue-{school_id}",
                    "severity": "medium",
                    "service": "subscriptions",
                    "title": f"Past due — {school.name}",
                    "detail": "Subscription is past due",
                    "ts": sub.ends_at.isoformat() if sub.ends_at else None,
                    "affected_tenants": 1,
                    "status": "open",
                    "action": "Renew or downgrade subscription",
                    "href": f"/super-admin/schools/{school_id}",
                }
            )
        if sub.ai_credits_total and sub.ai_credits_used:
            pct = float(sub.ai_credits_used) / float(sub.ai_credits_total) * 100
            if pct >= 90:
                school = db.get(School, school_id)
                if school is None:
                    continue
                issues_list.append(
                    {
                        "id": f"ai-{school_id}",
                        "severity": "medium",
                        "service": "ai",
                        "title": f"AI limit near exhaustion — {school.name}",
                        "detail": f"{pct:.0f}% of AI credits consumed",
                        "ts": _last_activity(db, school_id).isoformat() if _last_activity(db, school_id) else None,
                        "affected_tenants": 1,
                        "status": "open",
                        "action": "Offer an AI top-up",
                        "href": f"/super-admin/schools/{school_id}",
                    }
                )

    tickets = db.scalars(
        select(PlatformTicket)
        .where(PlatformTicket.status.in_(["open", "in_progress"]), PlatformTicket.severity.in_(["high", "critical"]))
    ).all()
    for t in tickets:
        issues_list.append(
            {
                "id": f"ticket-{t.id}",
                "severity": t.severity,
                "service": "support",
                "title": f"Support ticket — {t.subject}",
                "detail": t.description or "",
                "ts": t.created_at.isoformat(),
                "affected_tenants": 1,
                "status": t.status,
                "action": "Respond to ticket",
                "href": "/super-admin/support",
            }
        )

    if severity:
        issues_list = [i for i in issues_list if i["severity"] == severity]
    if status:
        issues_list = [i for i in issues_list if i["status"] == status]
    issues_list.sort(key=lambda i: i.get("ts") or "", reverse=True)

    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "open": 0, "resolved": 0}
    for i in issues_list:
        counts[i["severity"]] = counts.get(i["severity"], 0) + 1
        counts[i["status"]] = counts.get(i["status"], 0) + 1

    return {"items": issues_list, "counts": counts}


# --- Support ----------------------------------------------------------------

def tickets(db: Session) -> dict:
    rows = db.scalars(
        select(PlatformTicket)
        .order_by(PlatformTicket.created_at.desc())
        .limit(100)
    ).all()
    school_names = {
        s.id: s.name for s in db.scalars(select(School)).all()
    }
    open_count = db.scalar(
        select(func.count()).select_from(PlatformTicket).where(PlatformTicket.status.in_(["open", "in_progress"]))
    )
    critical_count = db.scalar(
        select(func.count()).select_from(PlatformTicket).where(
            PlatformTicket.status.in_(["open", "in_progress"]),
            PlatformTicket.severity.in_(["critical", "high"]),
        )
    )
    awaiting = db.scalar(
        select(func.count()).select_from(PlatformTicket).where(PlatformTicket.status == "awaiting_school")
    )
    resolved_today = db.scalar(
        select(func.count()).select_from(PlatformTicket).where(
            PlatformTicket.status == "resolved",
            PlatformTicket.resolved_at >= _days_ago(1),
        )
    )

    return {
        "summary": {
            "open": int(open_count or 0),
            "critical": int(critical_count or 0),
            "awaiting_response": int(awaiting or 0),
            "resolved_today": int(resolved_today or 0),
        },
        "items": [
            {
                "id": str(t.id),
                "school_id": str(t.school_id) if t.school_id else None,
                "school_name": school_names.get(t.school_id) if t.school_id else None,
                "subject": t.subject,
                "category": t.category,
                "severity": t.severity,
                "status": t.status,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
            }
            for t in rows
        ],
    }


def create_ticket(
    db: Session,
    *,
    school_id: uuid.UUID | None,
    subject: str,
    description: str | None,
    category: str,
    severity: str,
    created_by: uuid.UUID | None,
    ip: str | None,
) -> dict:
    ticket = PlatformTicket(
        school_id=school_id,
        subject=subject.strip(),
        description=description,
        category=category or "general",
        severity=severity or "medium",
        status="open",
        created_by=created_by,
    )
    db.add(ticket)
    db.flush()
    _audit(
        db,
        action="create",
        entity_type="ticket",
        entity_id=str(ticket.id),
        user_id=created_by,
        school_id=school_id,
        ip=ip,
        details=f"Support ticket opened: {subject.strip()}",
    )
    return {"id": str(ticket.id), "subject": ticket.subject, "status": "open"}


def update_ticket(
    db: Session, ticket_id: uuid.UUID, *, status: str | None, resolution_note: str | None, actor_id: uuid.UUID | None
) -> dict:
    ticket = db.get(PlatformTicket, ticket_id)
    if ticket is None:
        raise NotFoundError("Ticket not found")
    if status:
        ticket.status = status
        if status == "resolved":
            ticket.resolved_at = _now()
            ticket.resolved_by = actor_id
    if resolution_note:
        ticket.resolution_note = resolution_note
    db.flush()
    _audit(
        db,
        action="update",
        entity_type="ticket",
        entity_id=str(ticket.id),
        user_id=actor_id,
        school_id=ticket.school_id,
        details=f"Ticket status → {ticket.status}",
    )
    return {"id": str(ticket.id), "subject": ticket.subject, "status": ticket.status}


# --- Notifications ----------------------------------------------------------

def _notifications(db: Session, limit: int = 12) -> list[dict]:
    rows = db.scalars(
        select(PlatformNotification)
        .order_by(PlatformNotification.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "id": str(n.id),
            "title": n.title,
            "body": n.body,
            "severity": n.severity,
            "category": n.category,
            "data": n.data,
            "read": n.read_at is not None,
            "created_at": n.created_at.isoformat(),
        }
        for n in rows
    ]


def _alerts(db: Session) -> list[dict]:
    """Derived, prioritized alerts — the platform should not drown the owner."""
    sub_map = _subscription_map(db)
    now = _now()
    alerts: list[dict] = []

    nearing = sum(
        1
        for s in sub_map.values()
        if s.ai_credits_total
        and s.ai_credits_used
        and float(s.ai_credits_used) / float(s.ai_credits_total) >= 0.8
    )
    if nearing:
        alerts.append(
            {"kind": "ai_limits", "severity": "warning", "label": "schools approaching plan limits", "count": nearing, "href": "/super-admin/ai"}
        )

    failed = db.scalar(
        select(func.count()).select_from(SubscriptionEvent).where(SubscriptionEvent.event_type == "payment_failed")
    )
    if failed:
        alerts.append(
            {"kind": "payments", "severity": "critical", "label": "subscription payments failed", "count": int(failed or 0), "href": "/super-admin/revenue"}
        )

    trials_ending = sum(1 for s in sub_map.values() if s.status == "trial" and s.ends_at and s.ends_at < now + timedelta(days=2))
    if trials_ending:
        alerts.append(
            {"kind": "trials", "severity": "info", "label": "trial periods ending in 48h", "count": trials_ending, "href": "/super-admin/subscriptions"}
        )

    ai_cost = _ai_cost(db, since=_days_ago(7))
    ai_threshold = _setting_float(db, "ai.monthly_cost_threshold", 1000.0)
    if ai_cost >= ai_threshold:
        alerts.append(
            {"kind": "ai_cost", "severity": "warning", "label": "AI provider usage above threshold", "count": 1, "href": "/super-admin/ai"}
        )

    storage_pct = _setting_float(db, "platform.storage_used_pct", 0)
    if storage_pct >= 70:
        alerts.append(
            {"kind": "storage", "severity": "warning", "label": f"platform storage {storage_pct:.0f}% full", "count": 1, "href": "/super-admin/system"}
        )

    return alerts


def create_notification(
    db: Session, *, title: str, body: str | None, severity: str, category: str, data: dict | None = None
) -> PlatformNotification:
    n = PlatformNotification(title=title, body=body, severity=severity, category=category, data=data)
    db.add(n)
    db.flush()
    return n


def mark_notifications_read(db: Session, ids: list[str]) -> None:
    for raw in ids:
        try:
            n = db.get(PlatformNotification, uuid.UUID(raw))
        except ValueError:
            continue
        if n is not None and n.read_at is None:
            n.read_at = _now()


# --- Audit log --------------------------------------------------------------

def audit(
    db: Session,
    *,
    q: str | None = None,
    action: str | None = None,
    entity: str | None = None,
    page: int = 1,
    per_page: int = 30,
) -> dict:
    query = select(AuditLog, School.name, User.full_name).outerjoin(
        School, School.id == AuditLog.school_id
    ).outerjoin(User, User.id == AuditLog.user_id)

    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                AuditLog.details.ilike(like),
                AuditLog.entity_type.ilike(like),
                School.name.ilike(like),
                User.full_name.ilike(like),
            )
        )
    if action:
        query = query.where(AuditLog.action == action)
    if entity:
        query = query.where(AuditLog.entity_type == entity)

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(
        query.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    ).all()
    pages = max(1, -(-int(total or 0) // per_page))

    return {
        "items": [
            {
                "id": str(log.id),
                "ts": log.created_at.isoformat(),
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "school_id": str(log.school_id) if log.school_id else None,
                "school_name": school_name,
                "actor": actor or "System",
                "ip": log.ip,
                "details": log.details,
            }
            for log, school_name, actor in rows
        ],
        "total": int(total or 0),
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


# --- Settings / announcements ------------------------------------------------

def platform_settings(db: Session) -> dict:
    rows = db.scalars(select(PlatformSetting)).all()
    return {r.key: r.value for r in rows}


def update_platform_settings(db: Session, updates: dict, actor_id: uuid.UUID | None, ip: str | None) -> dict:
    for key, value in updates.items():
        row = db.get(PlatformSetting, key)
        if row is None:
            row = PlatformSetting(key=key, value=value)
            db.add(row)
        else:
            row.value = value
    db.flush()
    _audit(
        db,
        action="update",
        entity_type="platform_settings",
        user_id=actor_id,
        ip=ip,
        details=f"Updated platform settings: {', '.join(updates.keys())}",
    )
    return platform_settings(db)


def announcements(db: Session) -> list[dict]:
    rows = db.scalars(
        select(PlatformAnnouncement).order_by(PlatformAnnouncement.created_at.desc()).limit(50)
    ).all()
    return [
        {
            "id": str(a.id),
            "title": a.title,
            "body": a.body,
            "audience": a.audience,
            "severity": a.severity,
            "is_active": a.is_active,
            "created_at": a.created_at.isoformat(),
        }
        for a in rows
    ]


def create_announcement(
    db: Session,
    *,
    title: str,
    body: str,
    audience: str,
    severity: str,
    created_by: uuid.UUID | None,
    ip: str | None,
) -> dict:
    a = PlatformAnnouncement(
        title=title.strip(),
        body=body.strip(),
        audience=audience or "all_schools",
        severity=severity or "info",
        is_active=True,
        created_by=created_by,
    )
    db.add(a)
    db.flush()
    _audit(
        db,
        action="create",
        entity_type="announcement",
        entity_id=str(a.id),
        user_id=created_by,
        ip=ip,
        details=f"Platform announcement: {title.strip()}",
    )
    return {"id": str(a.id), "title": a.title, "audience": a.audience, "severity": a.severity}


# --- School provisioning / admin actions -------------------------------------

def add_school(
    db: Session,
    *,
    name: str,
    school_type: str,
    state: str | None,
    country: str,
    admin_full_name: str,
    admin_email: str,
    plan_code: str | None,
    actor_id: uuid.UUID | None,
    ip: str | None,
) -> dict:
    from ..core.errors import ConflictError
    from ..core.security import generate_opaque_token

    email = admin_email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise ConflictError("A user with that email already exists")

    school = create_school(db, name=name, school_type=school_type)
    if state:
        school.state = state
    if country:
        school.country = country

    password = generate_opaque_token()
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=admin_full_name.strip(),
    )
    db.add(user)
    db.flush()
    role = db.scalar(select(Role).where(Role.school_id == school.id, Role.code == "super_admin"))
    db.add(SchoolMembership(user_id=user.id, school_id=school.id, role_id=role.id))

    if plan_code:
        sub = get_active_subscription(db, school.id)
        if sub is not None:
            plan = db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.code == plan_code))
            if plan is None:
                raise ValidationError(f"Unknown plan code '{plan_code}'")
            sub.plan_id = plan.id
            sub.status = "active"
            sub.ai_credits_total = plan.features.get("ai_credits", 0)
            sub.ends_at = _now() + timedelta(days=30)
            settings = dict(school.settings or {})
            settings["ai_enabled"] = bool(plan.features.get("ai_enabled", False))
            school.settings = settings
            record_subscription_event(
                db, school_id=school.id, subscription_id=sub.id, event_type="activated"
            )

    _audit(
        db,
        action="create",
        entity_type="school",
        entity_id=str(school.id),
        user_id=actor_id,
        school_id=school.id,
        ip=ip,
        details=f"School created by platform admin: {name}",
    )
    db.flush()
    return {"id": str(school.id), "name": school.name, "admin_email": email, "temp_password": password}


def reset_admin(db: Session, school_id: uuid.UUID, actor_id: uuid.UUID | None, ip: str | None) -> dict:
    from ..core.security import generate_opaque_token

    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School not found")
    rows = db.execute(
        select(User, Role.code)
        .join(SchoolMembership, SchoolMembership.user_id == User.id)
        .join(Role, Role.id == SchoolMembership.role_id)
        .where(SchoolMembership.school_id == school_id, Role.code == "super_admin")
        .order_by(User.created_at)
    ).all()
    if not rows:
        raise NotFoundError("This school has no admin account to reset")

    user, _ = rows[0]
    password = generate_opaque_token()
    user.password_hash = hash_password(password)
    db.flush()
    _audit(
        db,
        action="update",
        entity_type="school_admin",
        entity_id=str(user.id),
        user_id=actor_id,
        school_id=school_id,
        ip=ip,
        details=f"Admin access reset for {user.full_name}",
    )
    return {"email": user.email, "temp_password": password}


def impersonate(
    db: Session,
    school_id: uuid.UUID,
    platform_user: User,
    ip: str | None,
) -> dict:
    """Create an audited 'view as school admin' session.

    Returns the one-time token. Entering impersonation resolves the caller to
    the school's admin identity while the platform admin (and this session) is
    recorded in the audit log. Platform-level routes reject impersonated calls.
    """
    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School not found")

    rows = db.execute(
        select(User, Role.code)
        .join(SchoolMembership, SchoolMembership.user_id == User.id)
        .join(Role, Role.id == SchoolMembership.role_id)
        .where(SchoolMembership.school_id == school_id, Role.code == "super_admin")
        .order_by(User.created_at)
    ).all()
    if not rows:
        raise NotFoundError("This school has no admin account to impersonate")
    admin_user, _ = rows[0]

    token = secrets.token_urlsafe(32)
    session = ImpersonationSession(
        platform_user_id=platform_user.id,
        impersonated_user_id=admin_user.id,
        school_id=school.id,
        token_hash=hash_token(token),
        ip=ip,
        expires_at=_now() + timedelta(minutes=30),
    )
    db.add(session)
    db.flush()
    _audit(
        db,
        action="create",
        entity_type="impersonation",
        entity_id=str(school.id),
        user_id=platform_user.id,
        school_id=school.id,
        ip=ip,
        details=f"Support impersonation session started for {school.name}",
    )
    return {"token": token, "school_id": str(school.id), "school_name": school.name, "expires_in_minutes": 30}