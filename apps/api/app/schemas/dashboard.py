"""Dashboard aggregation schemas — all tenant-scoped to the active school."""
import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardKpis(BaseModel):
    students: int
    teachers: int
    staff: int
    classes: int
    subjects: int
    attendance_rate: float | None
    outstanding_fees: float
    fee_currency: str
    readiness_overall: float | None
    readiness_submitted: int
    readiness_pending: int
    session_name: str | None
    term_name: str | None
    term_id: uuid.UUID | None


class PerformancePoint(BaseModel):
    term_name: str
    avg_score: float | None
    pass_rate: float | None
    count: int


class ClassPerformanceRow(BaseModel):
    arm_name: str
    avg_score: float | None
    pass_rate: float | None
    count: int


class PerformanceOut(BaseModel):
    by_term: list[PerformancePoint]
    by_class: list[ClassPerformanceRow]


class DistributionSlice(BaseModel):
    level_name: str
    level_code: str
    count: int
    pct: float


class DistributionOut(BaseModel):
    total: int
    slices: list[DistributionSlice]


class AttendanceOverview(BaseModel):
    present: int
    absent: int
    late: int
    excused: int
    total: int
    rate: float | None


class AttendanceOut(BaseModel):
    today: AttendanceOverview
    week: AttendanceOverview
    month: AttendanceOverview


class ActivityItem(BaseModel):
    id: str
    kind: str  # "result" | "student" | "staff" | "payment" | "ai" | "attendance" | "other"
    title: str
    detail: str | None
    actor_name: str
    created_at: datetime
    href: str | None = None


class TaskItem(BaseModel):
    id: str
    title: str
    detail: str
    count: int
    href: str
    kind: str  # "results" | "finance" | "students" | "attendance"


class InsightItem(BaseModel):
    id: str
    title: str
    body: str
    kind: str
    tone: str  # "positive" | "warning" | "info"
    confidence: float
    href: str | None = None


class InsightsOut(BaseModel):
    insights: list[InsightItem]


class DashboardSummary(BaseModel):
    kpis: DashboardKpis
    performance: PerformanceOut
    distribution: DistributionOut
    attendance: AttendanceOut
    activity: list[ActivityItem]
    tasks: list[TaskItem]
    insights: InsightsOut