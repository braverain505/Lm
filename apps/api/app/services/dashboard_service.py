"""Dashboard aggregation service.

Every query is scoped to ``school_id`` resolved from the authenticated
membership (tenant isolation is enforced by the router's ``get_school_context``
dependency and reinforced here by filtering on ``school_id``).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from statistics import mean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import (
    AcademicSession,
    AttendanceSummary,
    AuditLog,
    ClassArm,
    Result,
    ResultEvent,
    School,
    Staff,
    Student,
    StudentAttendance,
    StudentEnrollment,
    StudentFeeBalance,
    Subject,
    Term,
    User,
)
from ..models.crosscut import AiUsage
from .results_service import readiness_for_term


def _current_session(db: Session, school_id: uuid.UUID) -> AcademicSession | None:
    return db.scalar(
        select(AcademicSession).where(
            AcademicSession.school_id == school_id, AcademicSession.is_current.is_(True)
        )
    )


def _current_term(db: Session, school_id: uuid.UUID, session_id: uuid.UUID | None) -> Term | None:
    q = select(Term).where(Term.school_id == school_id)
    if session_id:
        q = q.where(Term.academic_session_id == session_id)
    return db.scalar(q.order_by(Term.is_current.desc(), Term.term_no))


def _avg_score(db: Session, school_id: uuid.UUID, *, term_id: uuid.UUID) -> tuple[float | None, float | None, int]:
    """Overall average score, pass rate (>=50) and count for a term."""
    totals = list(
        db.scalars(
            select(Result.total).where(
                Result.school_id == school_id,
                Result.term_id == term_id,
                Result.total.is_not(None),
                Result.status.in_(["submitted", "verified", "approved", "published"]),
            )
        )
    )
    if not totals:
        return None, None, 0
    vals = [float(t) for t in totals]
    avg = round(mean(vals), 1)
    passed = sum(1 for v in vals if v >= 50)
    return avg, round(passed / len(vals) * 100, 1), len(vals)


def kpis(db: Session, school_id: uuid.UUID, *, term_id: uuid.UUID | None) -> dict:
    students = db.scalar(
        select(func.count()).select_from(Student).where(
            Student.school_id == school_id, Student.is_deleted.is_(False)
        )
    )
    staff = db.scalar(
        select(func.count()).select_from(Staff).where(
            Staff.school_id == school_id, Staff.is_deleted.is_(False)
        )
    )
    teachers = db.scalar(
        select(func.count()).select_from(Staff).where(
            Staff.school_id == school_id,
            Staff.membership_type == "teaching",
            Staff.is_deleted.is_(False),
        )
    )
    classes = db.scalar(select(func.count()).select_from(ClassArm).where(ClassArm.school_id == school_id))
    subjects = db.scalar(select(func.count()).select_from(Subject).where(Subject.school_id == school_id))

    att_total = db.scalar(
        select(func.count()).select_from(StudentAttendance).where(StudentAttendance.school_id == school_id)
    ) or 0
    att_present = db.scalar(
        select(func.count()).select_from(StudentAttendance).where(
            StudentAttendance.school_id == school_id,
            StudentAttendance.status == "present",
        )
    ) or 0
    attendance_rate = round(att_present / att_total * 100, 1) if att_total else None

    fee_currency = "NGN"
    outstanding = db.scalar(
        select(func.coalesce(func.sum(StudentFeeBalance.total_unpaid), 0)).where(
            StudentFeeBalance.school_id == school_id
        )
    )
    outstanding = float(outstanding or 0)
    school = db.get(School, school_id)
    if school is not None and school.currency:
        fee_currency = school.currency

    # Readiness (overall %) from the term readiness matrix.
    readiness_overall: float | None = None
    submitted = 0
    pending = 0
    if term_id:
        rows = readiness_for_term(db, school_id, term_id)
        if rows:
            readiness_overall = round(
                sum(r["entered_pct"] for r in rows) / len(rows), 1
            )
            submitted = sum(r["submitted"] for r in rows)
            pending = sum(r["pending"] for r in rows)

    session = _current_session(db, school_id)
    term = _current_term(db, school_id, session.id if session else None)

    return {
        "students": students or 0,
        "teachers": teachers or 0,
        "staff": staff or 0,
        "classes": classes or 0,
        "subjects": subjects or 0,
        "attendance_rate": attendance_rate,
        "outstanding_fees": outstanding,
        "fee_currency": fee_currency,
        "readiness_overall": readiness_overall,
        "readiness_submitted": submitted,
        "readiness_pending": pending,
        "session_name": session.name if session else None,
        "term_name": term.name if term else None,
        "term_id": term.id if term else None,
    }


def performance(
    db: Session, school_id: uuid.UUID, term_id: uuid.UUID | None = None
) -> dict:
    terms = list(
        db.scalars(
            select(Term)
            .where(Term.school_id == school_id)
            .order_by(Term.term_no)
        )
    )
    by_term = []
    for t in terms:
        avg, pr, cnt = _avg_score(db, school_id, term_id=t.id)
        by_term.append(
            {
                "term_name": t.name,
                "avg_score": avg,
                "pass_rate": pr,
                "count": cnt,
            }
        )

    # Class performance: per arm over the selected term (or the latest term
    # with data when no term is requested).
    by_class = []
    term_ids = [t.id for t in terms]
    if term_ids:
        if term_id is not None:
            latest_term = term_id
        else:
            # Prefer the term with the most scored results, then the current
            # term, then the latest by term order.
            top = db.execute(
                select(Result.term_id, func.count(Result.id))
                .where(Result.school_id == school_id)
                .group_by(Result.term_id)
                .order_by(func.count(Result.id).desc())
                .limit(1)
            ).first()
            current = db.scalar(
                select(Term).where(Term.school_id == school_id, Term.is_current.is_(True))
            )
            latest_term = (
                (top[0] if top else None)
                or (current.id if current else None)
                or term_ids[-1]
            )
        arms = list(
            db.scalars(
                select(ClassArm)
                .where(ClassArm.school_id == school_id)
                .order_by(ClassArm.full_name)
            )
        )
        for arm in arms:
            totals = list(
                db.scalars(
                    select(Result.total).where(
                        Result.school_id == school_id,
                        Result.class_arm_id == arm.id,
                        Result.term_id == latest_term,
                        Result.total.is_not(None),
                        Result.status.in_(["submitted", "verified", "approved", "published"]),
                    )
                )
            )
            if not totals:
                continue
            vals = [float(v) for v in totals]
            passed = sum(1 for v in vals if v >= 50)
            by_class.append(
                {
                    "arm_name": arm.full_name,
                    "avg_score": round(mean(vals), 1),
                    "pass_rate": round(passed / len(vals) * 100, 1),
                    "count": len(vals),
                }
            )

    return {"by_term": by_term, "by_class": by_class}


def distribution(db: Session, school_id: uuid.UUID) -> dict:
    rows = db.execute(
        select(ClassArm.full_name, func.count(StudentEnrollment.id))
        .join(StudentEnrollment, StudentEnrollment.class_arm_id == ClassArm.id)
        .where(ClassArm.school_id == school_id, StudentEnrollment.is_current.is_(True))
        .group_by(ClassArm.full_name)
        .order_by(ClassArm.full_name)
    ).all()
    total = sum(r[1] for r in rows)
    slices = [
        {
            "level_name": name,
            "level_code": name,
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0,
        }
        for name, count in rows
    ]
    return {"total": total, "slices": slices}


def _attendance_overview(
    db: Session, school_id: uuid.UUID, start: date | None, end: date | None
) -> dict:
    q = select(
        StudentAttendance.status, func.count(StudentAttendance.id)
    ).where(StudentAttendance.school_id == school_id)
    if start:
        q = q.where(StudentAttendance.date >= start.isoformat())
    if end:
        q = q.where(StudentAttendance.date <= end.isoformat())
    q = q.group_by(StudentAttendance.status)
    counts = {status: cnt for status, cnt in db.execute(q).all()}
    present = counts.get("present", 0)
    absent = counts.get("absent", 0)
    late = counts.get("late", 0)
    excused = counts.get("excused", 0)
    total = present + absent + late + excused
    return {
        "present": present,
        "absent": absent,
        "late": late,
        "excused": excused,
        "total": total,
        "rate": round(present / total * 100, 1) if total else None,
    }


def attendance(db: Session, school_id: uuid.UUID) -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    return {
        "today": _attendance_overview(db, school_id, today, today),
        "week": _attendance_overview(db, school_id, week_start, today),
        "month": _attendance_overview(db, school_id, month_start, today),
    }


def activity(db: Session, school_id: uuid.UUID, limit: int = 10) -> list[dict]:
    """Recent cross-domain activity for the school."""
    items: list[dict] = []

    # Result transitions
    actor_ids = set(
        db.scalars(
            select(ResultEvent.actor_id).where(ResultEvent.school_id == school_id)
        ).all()
    )
    users = {u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(actor_ids)))} if actor_ids else {}
    for ev in db.scalars(
        select(ResultEvent)
        .where(ResultEvent.school_id == school_id)
        .order_by(ResultEvent.created_at.desc())
        .limit(limit)
    ):
        items.append(
            {
                "id": f"r-{ev.id}",
                "kind": "result",
                "title": f"Result {ev.action}",
                "detail": f"{ev.from_status or '—'} → {ev.to_status or '—'}",
                "actor_name": users.get(ev.actor_id, "Staff"),
                "created_at": ev.created_at,
                "href": "/results",
            }
        )

    # Audit log
    for log in db.scalars(
        select(AuditLog)
        .where(AuditLog.school_id == school_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ):
        kind_map = {
            "login": "other", "logout": "other", "create": "student",
            "update": "staff", "delete": "other", "submit": "result",
            "approve": "result", "publish": "result", "reject": "result",
        }
        items.append(
            {
                "id": f"a-{log.id}",
                "kind": kind_map.get(log.action, "other"),
                "title": f"{log.action.capitalize()} {log.entity_type}",
                "detail": log.details,
                "actor_name": "User",
                "created_at": log.created_at,
                "href": None,
            }
        )

    # AI usage
    for usage in db.scalars(
        select(AiUsage)
        .where(AiUsage.school_id == school_id)
        .order_by(AiUsage.created_at.desc())
        .limit(limit)
    ):
        items.append(
            {
                "id": f"ai-{usage.id}",
                "kind": "ai",
                "title": f"AI {usage.feature.replace('_', ' ')}",
                "detail": f"{usage.model or 'generated'}",
                "actor_name": "Lumo AI",
                "created_at": usage.created_at,
                "href": "/copilot",
            }
        )

    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items[:limit]


def tasks(
    db: Session, school_id: uuid.UUID, *, term_id: uuid.UUID | None, can_fees: bool = False
) -> list[dict]:
    out: list[dict] = []

    if term_id:
        rows = readiness_for_term(db, school_id, term_id)
        pending = sum(r["pending"] for r in rows)
        submitted = sum(r["submitted"] for r in rows)
        total_cells = len(rows)
        if pending:
            out.append(
                {
                    "id": "results-pending",
                    "title": "Score entry outstanding",
                    "detail": "Result submissions still need scores entered",
                    "count": pending,
                    "href": "/readiness",
                    "kind": "results",
                }
            )
        if submitted and total_cells:
            out.append(
                {
                    "id": "results-review",
                    "title": "Result submissions to review",
                    "detail": "Submitted results awaiting verification/approval",
                    "count": submitted,
                    "href": "/approvals",
                    "kind": "results",
                }
            )

    # Outstanding fees (students with a positive unpaid balance). Accounting is
    # the Accountant's domain — never surface finance activity to other roles.
    if can_fees:
        unpaid = db.scalar(
            select(func.count()).select_from(StudentFeeBalance).where(
                StudentFeeBalance.school_id == school_id,
                StudentFeeBalance.total_unpaid > 0,
            )
        )
        if unpaid:
            out.append(
                {
                    "id": "fees-outstanding",
                    "title": "Fee balances outstanding",
                    "detail": "Students with unpaid fee balances",
                    "count": unpaid,
                    "href": "/billing",
                    "kind": "finance",
                }
            )

    # Low attendance (summary rows under 85%)
    low_att = db.scalar(
        select(func.count()).select_from(AttendanceSummary).where(
            AttendanceSummary.school_id == school_id,
            AttendanceSummary.percentage < 85,
            AttendanceSummary.percentage > 0,
        )
    )
    if low_att:
        out.append(
            {
                "id": "attendance-low",
                "title": "Students with low attendance",
                "detail": "Students below 85% attendance this month",
                "count": low_att,
                "href": "/attendance",
                "kind": "attendance",
            }
        )

    return out


def insights(db: Session, school_id: uuid.UUID, *, term_id: uuid.UUID | None) -> list[dict]:
    """Rule-based AI academic insights derived from real school data."""
    items: list[dict] = []

    # Result readiness signal
    if term_id:
        rows = readiness_for_term(db, school_id, term_id)
        if rows:
            overall = round(sum(r["entered_pct"] for r in rows) / len(rows), 1)
            worst = min(rows, key=lambda r: r["entered_pct"])
            if overall >= 90:
                items.append(
                    {
                        "id": "ins-1",
                        "title": "Strong result readiness",
                        "body": f"Result readiness is at {overall}% — most score entry is complete.",
                        "kind": "readiness",
                        "tone": "positive",
                        "confidence": 0.9,
                        "href": "/readiness",
                    }
                )
            elif worst:
                items.append(
                    {
                        "id": "ins-2",
                        "title": "Score entry lagging",
                        "body": (
                            f"{worst['subject_name']} in {worst['arm_name']} is at "
                            f"{worst['entered_pct']}% entry with {worst['pending']} students still pending."
                        ),
                        "kind": "readiness",
                        "tone": "warning",
                        "confidence": 0.85,
                        "href": "/readiness",
                    }
                )
            if rows and overall < 100:
                items.append(
                    {
                        "id": "ins-3",
                        "title": "Completion needed before publishing",
                        "body": (
                            f"{sum(r['pending'] for r in rows)} scores across all classes "
                            f"still need to be entered before report cards can finalize."
                        ),
                        "kind": "readiness",
                        "tone": "info",
                        "confidence": 0.9,
                        "href": "/readiness",
                    }
                )

    # Attendance signal
    att = _attendance_overview(db, school_id, None, None)
    if att["total"]:
        if att["rate"] is not None and att["rate"] < 90:
            items.append(
                {
                    "id": "ins-4",
                    "title": "Attendance below target",
                    "body": f"Overall attendance is {att['rate']}% — below the 90% target.",
                    "kind": "attendance",
                    "tone": "warning",
                    "confidence": 0.8,
                    "href": "/attendance",
                }
            )
        elif att["late"]:
            items.append(
                {
                    "id": "ins-5",
                    "title": "Late arrivals",
                    "body": f"{att['late']} late arrivals recorded — consider reviewing arrival policy.",
                    "kind": "attendance",
                    "tone": "info",
                    "confidence": 0.7,
                    "href": "/attendance",
                }
            )

    # Class performance signal
    perf = performance(db, school_id)
    if perf["by_class"]:
        weakest = min(perf["by_class"], key=lambda c: c["avg_score"] or 0)
        if weakest["avg_score"] is not None and weakest["avg_score"] < 55:
            items.append(
                {
                    "id": "ins-6",
                    "title": "Class needing support",
                    "body": (
                        f"{weakest['arm_name']} averages {weakest['avg_score']}% — consider "
                        f"an intervention plan."
                    ),
                    "kind": "academic",
                    "tone": "warning",
                    "confidence": 0.75,
                    "href": "/results",
                }
            )

    return {"insights": items[:6]}