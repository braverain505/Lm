"""Academic structure schemas."""
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    start_date: date | None
    end_date: date | None
    status: str
    is_current: bool


class SessionCreate(BaseModel):
    name: str
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False


class SessionUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    status: str | None = None


class TermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    academic_session_id: uuid.UUID
    term_no: int
    name: str
    start_date: date | None
    end_date: date | None
    status: str
    is_current: bool


class TermCreate(BaseModel):
    session_id: uuid.UUID
    term_no: int
    name: str
    start_date: date | None = None
    end_date: date | None = None


class TermReopenRequest(BaseModel):
    """Reopening is an explicit, audited correction: the school must say why."""

    reason: str = Field(min_length=3, max_length=500)


class TermReopenOut(BaseModel):
    term: TermOut
    archive_id: uuid.UUID | None = None
    archive_version: int | None = None
    results_reset: int


class ArmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    academic_session_id: uuid.UUID
    name: str
    full_name: str
    # Classes that share this are ranked as one class group in results ("SS 1"
    # over its Science/Arts/Commercial arms). Null = the class stands alone.
    group_name: str | None = None
    # "nursery" | "primary" | "secondary" | null. Which part of the school the
    # class belongs to, so a school that runs its sections differently gives
    # each its own scoresheet and report card.
    section: str | None = None
    # True when the *caller* is this arm's homeroom (class) teacher. Not
    # derivable from their subject assignments — a class teacher need not teach
    # a subject in their own class — so it is answered here, and the pages that
    # are the class teacher's own (remarks, psychomotor) scope to it.
    is_class_teacher: bool = False


class ArmCreate(BaseModel):
    session_id: uuid.UUID
    name: str
    campus_id: uuid.UUID | None = None
    group_name: str | None = None
    # Left null, the class name is read for a suggestion (JSS/SS -> secondary,
    # Basic/Primary -> primary, Nursery/KG -> nursery).
    section: str | None = None


class ArmUpdate(BaseModel):
    """Every field optional: the caller sends only what it is changing, and
    ``group_name: null`` is a real instruction — it clears the group."""

    name: str | None = None
    group_name: str | None = None
    section: str | None = None


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    is_active: bool
    is_core: bool = False


class SubjectCreate(BaseModel):
    name: str
    code: str


class SubjectUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    is_active: bool | None = None
    is_core: bool | None = None


class OfferingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    class_arm_id: uuid.UUID
    subject_id: uuid.UUID


class OfferingCreate(BaseModel):
    arm_id: uuid.UUID
    subject_id: uuid.UUID


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    class_arm_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID


class AssignmentCreate(BaseModel):
    arm_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID