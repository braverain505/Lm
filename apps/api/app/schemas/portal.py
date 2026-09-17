"""Result portal schemas: PIN setup, the school result code, and the public
check-in flow."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PinSet(BaseModel):
    pin: str = Field(min_length=4, max_length=6)


class PinSetOut(BaseModel):
    ok: bool = True
    student_id: uuid.UUID


class SchoolBrief(BaseModel):
    id: uuid.UUID
    name: str
    slug: str


class SchoolPinOut(BaseModel):
    """The school's live result code, as the exam office sees it.

    Returned in full (not masked) because the office that issues it is also the
    office that has to reprint it for next week's parents' meeting.
    """

    code: str
    prefix: str
    active: bool = True
    use_count: int = 0
    last_used_at: datetime | None = None
    created_at: datetime


class SchoolPinCheck(BaseModel):
    """Public check-in with the school code (``GVS-7K42Q``) + admission no."""

    pin: str = Field(min_length=4, max_length=24)
    admission_no: str = Field(min_length=1, max_length=40)


class PinCheck(BaseModel):
    school_slug: str = Field(min_length=1)
    admission_no: str = Field(min_length=1)
    pin: str = Field(min_length=4, max_length=6)


class PinStudentBrief(BaseModel):
    student_id: uuid.UUID
    admission_no: str
    full_name: str


class PinTermBrief(BaseModel):
    """A term the student has published results in — drives the portal's term
    picker so a parent can re-open an earlier report, not just the latest."""

    id: uuid.UUID
    name: str
    session_name: str


class PinCheckOut(BaseModel):
    token: str
    expires_minutes: int = 30
    student: PinStudentBrief
    school: SchoolBrief