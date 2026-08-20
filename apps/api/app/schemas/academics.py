"""Academic structure schemas."""
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict


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


class ArmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    academic_session_id: uuid.UUID
    name: str
    full_name: str


class ArmCreate(BaseModel):
    session_id: uuid.UUID
    name: str
    campus_id: uuid.UUID | None = None


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