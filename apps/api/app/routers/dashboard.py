"""Dashboard aggregation endpoints — one consolidated, tenant-scoped source of
truth for the school dashboard widgets."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..core.deps import ActiveSchool, DbSession, get_school_context
from ..core.permissions import (
    AI_COPILOT,
    ATTENDANCE_REPORT,
    FEES_VIEW,
    RESULTS_VIEW,
    STUDENTS_VIEW,
)
from ..schemas.dashboard import (
    ActivityItem,
    AttendanceOut,
    DashboardKpis,
    DashboardSummary,
    DistributionOut,
    InsightsOut,
    PerformanceOut,
    TaskItem,
)
from ..services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    ctx: ActiveSchool,
    db: DbSession,
    term_id: str | None = Query(default=None),
):
    """Aggregated dashboard payload. Permission-gated fields are zeroed/omitted
    per the caller's permission set."""
    school_id = ctx.school.id
    perms = ctx.permission_codes
    can_results = RESULTS_VIEW in perms or ctx.user.is_superadmin
    can_students = STUDENTS_VIEW in perms or ctx.user.is_superadmin
    can_fees = FEES_VIEW in perms or ctx.user.is_superadmin
    can_attendance = ATTENDANCE_REPORT in perms or ctx.user.is_superadmin
    can_ai = AI_COPILOT in perms or ctx.user.is_superadmin

    resolved_term = term_id or None

    k = dashboard_service.kpis(db=db, school_id=school_id, term_id=resolved_term)
    if not can_results:
        k["readiness_overall"] = None
        k["readiness_submitted"] = 0
        k["readiness_pending"] = 0
    if not can_fees:
        k["outstanding_fees"] = 0.0

    perf = dashboard_service.performance(db=db, school_id=school_id, term_id=resolved_term) if can_results else {"by_term": [], "by_class": []}
    dist = dashboard_service.distribution(db=db, school_id=school_id) if can_students else {"total": 0, "slices": []}
    if can_attendance:
        att = dashboard_service.attendance(db=db, school_id=school_id)
    else:
        att = {
            "today": {"present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0, "rate": None},
            "week": {"present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0, "rate": None},
            "month": {"present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0, "rate": None},
        }
    act = dashboard_service.activity(db=db, school_id=school_id)
    tasks = dashboard_service.tasks(
        db=db, school_id=school_id, term_id=resolved_term, can_fees=can_fees
    )
    ins = dashboard_service.insights(db=db, school_id=school_id, term_id=resolved_term) if can_ai else {"insights": []}

    return DashboardSummary(
        kpis=DashboardKpis(**k),
        performance=PerformanceOut(**perf),
        distribution=DistributionOut(**dist),
        attendance=AttendanceOut(
            today=att["today"], week=att["week"], month=att["month"]
        ),
        activity=[ActivityItem(**a) for a in act],
        tasks=[TaskItem(**t) for t in tasks],
        insights=InsightsOut(insights=ins) if isinstance(ins, list) else InsightsOut(**ins),
    )