"""Timetable and class scheduling API endpoints."""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from ..core.deps import DbSession, require_permission
from ..core.errors import NotFoundError
from ..core.permissions import TIMETABLE_MANAGE, TIMETABLE_VIEW
from ..models import AcademicSession
from ..schemas.timetable import (
    DayScheduleOut,
    ScheduleConflictOut,
    ScheduleEntryOut,
    ScheduleGenerateIn,
    ScheduleGenerateOut,
    ScheduleValidateIn,
    ScheduleValidateOut,
    TimeSlotOut,
    WeekScheduleOut,
)
from ..services.timetable_service import (
    generate_draft_schedule,
    get_time_slots,
    get_weekly_schedule,
    validate_schedule,
)


router = APIRouter(prefix="/timetable", tags=["timetable"])


@router.get("/time-slots", response_model=list[TimeSlotOut])
def get_time_slots_endpoint(
    ctx=Depends(require_permission(TIMETABLE_VIEW)),
):
    """The school-day slot template (8 periods of 35 min with 5-min breaks)."""
    return get_time_slots()


@router.post("/generate", response_model=ScheduleGenerateOut)
def generate_schedule_endpoint(
    payload: ScheduleGenerateIn,
    db: DbSession,
    ctx=Depends(require_permission(TIMETABLE_MANAGE)),
):
    """Generate a deterministic draft weekly timetable for a session."""
    result = generate_draft_schedule(
        db,
        school_id=ctx.school.id,
        academic_session_id=payload.academic_session_id,
        include_rooms=payload.include_rooms,
    )
    db.commit()
    return result


@router.post("/validate", response_model=ScheduleValidateOut)
def validate_schedule_endpoint(
    payload: ScheduleValidateIn,
    db: DbSession,
    ctx=Depends(require_permission(TIMETABLE_VIEW)),
):
    """Validate a set of schedule entries for teacher/class double-bookings."""
    conflicts = validate_schedule(
        db,
        school_id=ctx.school.id,
        entries=[e.model_dump() for e in payload.entries],
    )
    return ScheduleValidateOut(
        is_valid=len(conflicts) == 0,
        conflicts=[ScheduleConflictOut(**c) for c in conflicts],
        suggestions=[
            "Assign unplaced subjects to other free periods of the week",
            "Verify teacher availability sits within the school day",
        ],
    )


@router.get("/week/{class_arm_id}", response_model=WeekScheduleOut)
def get_weekly_schedule_endpoint(
    class_arm_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(TIMETABLE_VIEW)),
    academic_session_id: Optional[uuid.UUID] = Query(None, description="Academic session ID"),
):
    """The weekly schedule for one class arm."""
    from ..models import AcademicSession

    if academic_session_id is None:
        session = db.scalar(
            select(AcademicSession).where(
                AcademicSession.school_id == ctx.school.id,
                AcademicSession.is_current == True,
            )
        )
        if session is None:
            raise NotFoundError("No current academic session found")
        academic_session_id = session.id

    return get_weekly_schedule(
        db,
        school_id=ctx.school.id,
        class_arm_id=class_arm_id,
        academic_session_id=academic_session_id,
    )