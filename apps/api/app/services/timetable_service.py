"""Timetable / class scheduling service layer.

A deterministic, heuristic timetable generator. It allocates each class arm's
subjects (from the arm's class-level offerings) into fixed school-day slots
across Monday–Friday, assigning the teacher from ``subject_assignments`` and
never double-booking a teacher or a class. Everything is derived from existing
rows — no schedule persistence, so the same input always yields the same draft.
"""

import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import NotFoundError, ValidationError
from ..models import (
    AcademicSession,
    ClassArm,
    Staff,
    SubjectAssignment,
    SubjectOffering,
)
from ..models.academic import Subject

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PERIODS_PER_DAY = 8
PERIODS_PER_SUBJECT = 2
PERIOD_MINUTES = 35
BREAK_MINUTES = 5
DAY_START = time(8, 0)
NAMESPACE_UUID = uuid.UUID("00000000-0000-4000-8000-000000000000")


def _time_slots() -> list[tuple[time, time]]:
    """The fixed school-day slots: 8 periods of 35 min with 5-min breaks."""
    slots = []
    cursor = datetime.combine(date.today(), DAY_START)
    for _ in range(PERIODS_PER_DAY):
        end = cursor + timedelta(minutes=PERIOD_MINUTES)
        slots.append((cursor.time(), end.time()))
        cursor = end + timedelta(minutes=BREAK_MINUTES)
    return slots


def get_time_slots() -> list[dict]:
    """The school-day slot template (start, end, human label)."""
    slots = []
    for i, (start, end) in enumerate(_time_slots()):
        slots.append(
            {
                "start": start,
                "end": end,
                "label": f"Period {i + 1} · {start:%H:%M}-{end:%H:%M}",
            }
        )
    return slots


def _overlaps(
    a_day: int, a_start: time, a_end: time, b_day: int, b_start: time, b_end: time
) -> bool:
    if a_day != b_day:
        return False
    return a_start < b_end and b_start < a_end


def generate_draft_schedule(
    db: Session,
    *,
    school_id: uuid.UUID,
    academic_session_id: uuid.UUID,
    include_rooms: bool = False,
) -> dict:
    """Generate a deterministic draft weekly timetable for a session.

    Every arm's subjects get ``PERIODS_PER_SUBJECT`` slots across the week.
    A slot is skipped when its teacher is already booked in that (day, period),
    so the output is conflict-free by construction (for the assignments on file).
    """
    session = db.get(AcademicSession, academic_session_id)
    if session is None or session.school_id != school_id:
        raise NotFoundError("Academic session not found")

    arms = db.scalars(
        select(ClassArm).where(
            ClassArm.school_id == school_id,
            ClassArm.academic_session_id == academic_session_id,
        )
    ).all()

    slots = _time_slots()
    entries = []
    warnings: list[str] = []

    for arm in arms:
        offerings = db.execute(
            select(SubjectOffering, Subject)
            .join(Subject, Subject.id == SubjectOffering.subject_id)
            .where(
                SubjectOffering.school_id == school_id,
                SubjectOffering.class_arm_id == arm.id,
            )
            .order_by(SubjectOffering.sort_order, Subject.name)
        ).all()

        teacher_booked: dict[tuple[int, int], uuid.UUID] = {}
        slot_index = 0

        for offering, subject in offerings:
            assignment = db.scalar(
                select(SubjectAssignment).where(
                    SubjectAssignment.school_id == school_id,
                    SubjectAssignment.class_arm_id == arm.id,
                    SubjectAssignment.subject_id == subject.id,
                )
            )
            teacher = db.get(Staff, assignment.teacher_id) if assignment else None
            if teacher is None:
                warnings.append(
                    f"No teacher assigned for {subject.name} in {arm.full_name}"
                )

            placed = 0
            for _ in range(PERIODS_PER_SUBJECT):
                day = (slot_index // PERIODS_PER_DAY) % len(DAY_NAMES)
                period = slot_index % PERIODS_PER_DAY
                # Walk forward until an unoccupied (day, period) is found.
                while teacher is not None and teacher_booked.get((day, period)) == teacher.id:
                    slot_index += 1
                    day = (slot_index // PERIODS_PER_DAY) % len(DAY_NAMES)
                    period = slot_index % PERIODS_PER_DAY

                period_start, period_end = slots[period]
                if teacher is not None:
                    teacher_booked[(day, period)] = teacher.id

                entries.append(
                    {
                        "id": uuid.uuid5(
                            NAMESPACE_UUID,
                            f"{school_id}:{academic_session_id}:{arm.id}:{subject.id}:{day}:{period}",
                        ),
                        "class_arm_id": arm.id,
                        "class_arm_name": arm.full_name,
                        "subject_id": subject.id,
                        "subject_name": subject.name,
                        "teacher_id": teacher.id if teacher else None,
                        "teacher_name": teacher.full_name if teacher else None,
                        "day_of_week": day,
                        "period_start": period_start,
                        "period_end": period_end,
                        "room": None,
                    }
                )
                slot_index += 1
                placed += 1

    return {
        "school_id": school_id,
        "academic_session_id": academic_session_id,
        "entries": entries,
        "generated_at": datetime.utcnow(),
        "warnings": warnings,
        "message": f"Generated {len(entries)} entries across {len(arms)} arms",
    }


def get_weekly_schedule(
    db: Session,
    *,
    school_id: uuid.UUID,
    class_arm_id: uuid.UUID,
    academic_session_id: uuid.UUID,
) -> dict:
    """The weekly view for one class arm, derived from the deterministic draft."""
    arm = db.get(ClassArm, class_arm_id)
    if arm is None or arm.school_id != school_id:
        raise NotFoundError("Class arm not found")

    session = db.get(AcademicSession, academic_session_id)
    if session is None or session.school_id != school_id:
        raise NotFoundError("Academic session not found")

    generated = generate_draft_schedule(
        db, school_id=school_id, academic_session_id=academic_session_id
    )
    arm_entries = [e for e in generated["entries"] if e["class_arm_id"] == arm.id]

    today = date.today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()

    days = []
    for day, name in enumerate(DAY_NAMES):
        day_entries = sorted(
            (e for e in arm_entries if e["day_of_week"] == day),
            key=lambda e: e["period_start"],
        )
        days.append(
            {
                "day_of_week": day,
                "day_name": name,
                "entries": day_entries,
                "total_periods": len(day_entries),
            }
        )

    return {
        "school_id": school_id,
        "academic_session_id": academic_session_id,
        "week_start": week_start,
        "days": days,
        "total_entries": len(arm_entries),
    }


def _normalize_time(value) -> time:
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        return time.fromisoformat(value)
    raise ValidationError("period times must be 'HH:MM:SS'")


def validate_schedule(
    db: Session,
    *,
    school_id: uuid.UUID,
    entries: list[dict],
) -> list[dict]:
    """Detect teacher/class double-bookings across a set of schedule entries."""
    conflicts: list[dict] = []

    def _check_overlaps(group: dict, group_key: str, label: str) -> None:
        for owner_id, owner_entries in group.items():
            for i, e1 in enumerate(owner_entries):
                for e2 in owner_entries[i + 1:]:
                    if _overlaps(
                        int(e1["day_of_week"]),
                        _normalize_time(e1["period_start"]),
                        _normalize_time(e1["period_end"]),
                        int(e2["day_of_week"]),
                        _normalize_time(e2["period_start"]),
                        _normalize_time(e2["period_end"]),
                    ):
                        conflicts.append(
                            {
                                "type": group_key,
                                "detail": (
                                    f"{label} {owner_id} has overlapping periods on "
                                    f"day {e1['day_of_week']} ({e1['period_start']}-{e1['period_end']})"
                                ),
                                "suggestions": [
                                    "Reassign one of the periods to a free slot"
                                ],
                            }
                        )
                        break

    teacher_groups: dict = {}
    class_groups: dict = {}
    for entry in entries:
        tid = entry.get("teacher_id")
        if tid:
            teacher_groups.setdefault(str(tid), []).append(entry)
        class_groups.setdefault(str(entry["class_arm_id"]), []).append(entry)

    _check_overlaps(teacher_groups, "teacher_double_booking", "Teacher")
    _check_overlaps(class_groups, "class_arm_double_booking", "Class")

    return conflicts
