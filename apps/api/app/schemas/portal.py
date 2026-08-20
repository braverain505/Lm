"""Result portal schemas: PIN setup + the public check-in flow."""
import uuid

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


class PinCheck(BaseModel):
    school_slug: str = Field(min_length=1)
    admission_no: str = Field(min_length=1)
    pin: str = Field(min_length=4, max_length=6)


class PinStudentBrief(BaseModel):
    student_id: uuid.UUID
    admission_no: str
    full_name: str


class PinCheckOut(BaseModel):
    token: str
    expires_minutes: int = 30
    student: PinStudentBrief