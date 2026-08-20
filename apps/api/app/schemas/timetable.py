"""Timetable and class scheduling schemas."""

from datetime import time, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, validator


class TimeSlotOut(BaseModel):
    """A time slot within the school day."""
    start: time = Field(..., description="Slot start time")
    end: time = Field(..., description="Slot end time")
    label: str = Field(..., description="Human-readable label (e.g. 'Period 1', '9:00-9:35')")

    class Config:
        from_attributes = True


class ScheduleEntryOut(BaseModel):
    """A single schedule entry."""
    id: Optional[UUID] = Field(None, description="Schedule entry ID")
    class_arm_id: UUID = Field(..., description="Class arm ID")
    class_arm_name: str = Field(..., description="Class arm name (e.g. JSS 1A)")
    subject_id: UUID = Field(..., description="Subject ID")
    subject_name: str = Field(..., description="Subject name")
    teacher_id: Optional[UUID] = Field(None, description="Teacher/staff ID")
    teacher_name: Optional[str] = Field(None, description="Teacher full name")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    period_start: time = Field(..., description="Period start time")
    period_end: time = Field(..., description="Period end time")
    room: Optional[str] = Field(None, description="Room assignment, if any")

    class Config:
        from_attributes = True


class ScheduleGenerateIn(BaseModel):
    """Input for schedule generation."""
    academic_session_id: UUID = Field(..., description="Academic session ID")
    force_regenerate: bool = Field(
        False, description="Whether to ignore existing schedule and regenerate"
    )
    include_rooms: bool = Field(
        False, description="Whether to attempt room assignments"
    )


class ScheduleGenerateOut(BaseModel):
    """Output from schedule generation."""
    school_id: UUID = Field(..., description="School ID")
    academic_session_id: UUID = Field(..., description="Academic session ID")
    entries: List[ScheduleEntryOut] = Field(default_factory=list, description="Schedule entries")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    warnings: List[str] = Field(default_factory=list, description="Generation warnings")
    message: str = Field(..., description="Status message")


class ScheduleConflictOut(BaseModel):
    """A schedule conflict."""
    type: str = Field(..., description="Conflict type (teacher_double_booking, class_arm_double_booking)")
    detail: str = Field(..., description="Human-readable conflict detail")
    suggestions: List[str] = Field(default_factory=list, description="Suggested resolutions")

    class Config:
        from_attributes = True


class ScheduleValidateIn(BaseModel):
    """Input for schedule validation."""
    entries: List[ScheduleEntryOut] = Field(..., description="Schedule entries to validate")


class ScheduleValidateOut(BaseModel):
    """Output from schedule validation."""
    is_valid: bool = Field(..., description="Whether the schedule is valid")
    conflicts: List[ScheduleConflictOut] = Field(default_factory=list, description="List of conflicts found")
    suggestions: List[str] = Field(default_factory=list, description="General suggestions for improvement")


class RoomAssignmentIn(BaseModel):
    """Input for room assignment."""
    entry_id: UUID = Field(..., description="Schedule entry ID to assign room to")
    room_name: str = Field(..., description="Room name/identifier")
    capacity: int = Field(..., ge=1, description="Room capacity")


class RoomAssignmentOut(BaseModel):
    """Output from room assignment."""
    entry_id: UUID = Field(..., description="Schedule entry ID")
    room_name: str = Field(..., description="Assigned room name")
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class DayScheduleOut(BaseModel):
    """Schedule for a single day."""
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week")
    day_name: str = Field(..., description="Day name (Monday, Tuesday, etc.)")
    entries: List[ScheduleEntryOut] = Field(default_factory=list, description="Schedule entries for this day")
    total_periods: int = Field(default=0, description="Total periods scheduled")


class WeekScheduleOut(BaseModel):
    """Complete weekly schedule."""
    school_id: UUID = Field(..., description="School ID")
    academic_session_id: UUID = Field(..., description="Academic session ID")
    week_start: str = Field(..., description="Week start date (YYYY-MM-DD)")
    days: List[DayScheduleOut] = Field(default_factory=list, description="Daily schedules")
    total_entries: int = Field(default=0, description="Total scheduled periods")