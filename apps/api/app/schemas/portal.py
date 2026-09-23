"""Result portal schemas: the school result code and the public check-in flow."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


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


class StudentResultCodeOut(BaseModel):
    """One row of the Exam Office's result-code manager.

    The code is returned in full (not masked) because the office that issues it
    is also the office that has to reprint it for a parents' meeting.
    """

    student_id: uuid.UUID
    student_name: str
    admission_no: str
    code: str | None = None
    prefix: str | None = None
    active: bool = False
    use_count: int = 0
    last_used_at: datetime | None = None
    created_at: datetime | None = None


class StudentResultCodeBulkOut(BaseModel):
    issued: int
    total: int


class SchoolPinCheck(BaseModel):
    """Public check-in with a result code.

    A per-student code names the child, so ``admission_no`` is optional and only
    consulted for the legacy school-wide code.
    """

    pin: str = Field(min_length=4, max_length=24)
    admission_no: str | None = Field(default=None, max_length=40)


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
    """What a correct result code unlocks.

    ``report_template`` carries the school's own report-card design (its layout
    document, ``{}`` when the school has never saved one) so the public portal
    draws the *same* card the exam office printed. It rides on this response
    rather than on each card because it is school-wide and therefore only worth
    sending once per session; a parent and the exam office must never see two
    different cards for one child.
    """

    token: str
    expires_minutes: int = 30
    student: PinStudentBrief
    school: SchoolBrief
    report_template: dict = Field(default_factory=dict)