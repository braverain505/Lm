"""People schemas: staff, students, enrollments, guardians."""
import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field

from ..core.validators import sanitize_string_field


class StaffOut(BaseModel):
    id: uuid.UUID
    staff_no: str
    membership_type: str
    full_name: str
    gender: str | None
    phone: str | None
    email: str | None
    joined_date: date | None
    employment_status: str
    has_account: bool = False
    account_email: str | None = None
    account_role_id: uuid.UUID | None = None
    account_role_name: str | None = None


class StaffCreate(BaseModel):
    staff_no: str
    membership_type: str = "teaching"
    full_name: str
    gender: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    joined_date: date | None = None

    _sanitize = sanitize_string_field('full_name', 'staff_no', 'phone')


class StaffUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    employment_status: str | None = None


class StaffAccountCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role_id: uuid.UUID


class StaffAccountUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    role_id: uuid.UUID | None = None


class StaffAccountOut(BaseModel):
    staff_id: uuid.UUID
    email: str
    role_id: uuid.UUID
    role_code: str
    role_name: str


class ArmSummary(BaseModel):
    id: uuid.UUID
    full_name: str


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    admission_no: str
    first_name: str
    last_name: str
    middle_name: str | None
    gender: str
    date_of_birth: date | None
    photo_url: str | None
    state: str | None
    lga: str | None
    blood_group: str | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.middle_name or ''} {self.last_name}".replace(
            "  ", " "
        )


class StudentDetail(StudentOut):
    current_arm: ArmSummary | None = None
    guardians: list[dict] = []


class StudentCreate(BaseModel):
    admission_no: str
    first_name: str
    last_name: str
    middle_name: str | None = None
    gender: str
    date_of_birth: date | None = None
    state: str | None = None
    lga: str | None = None
    blood_group: str | None = None
    medical_notes: str | None = None
    previous_school: str | None = None
    address: str | None = None
    photo_url: str | None = None

    _sanitize = sanitize_string_field('first_name', 'last_name', 'middle_name', 'admission_no', 'medical_notes', 'previous_school', 'address')


class UploadOut(BaseModel):
    photo_url: str


class StudentUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    phone: str | None = None
    address: str | None = None
    state: str | None = None
    lga: str | None = None
    blood_group: str | None = None
    medical_notes: str | None = None
    photo_url: str | None = None

    _sanitize = sanitize_string_field('first_name', 'last_name', 'middle_name', 'phone', 'address', 'medical_notes')


class EnrollmentCreate(BaseModel):
    student_id: uuid.UUID
    arm_id: uuid.UUID
    session_id: uuid.UUID
    enrolled_at: date | None = None


class TargetArmPair(BaseModel):
    """Map one source class to its target class in the new session."""

    from_arm_id: uuid.UUID
    to_arm_id: uuid.UUID


class PromotionRequest(BaseModel):
    from_session_id: uuid.UUID
    to_session_id: uuid.UUID
    target_arms: list[TargetArmPair]
    student_ids: list[uuid.UUID] | None = None


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    class_arm_id: uuid.UUID
    academic_session_id: uuid.UUID
    status: str
    is_current: bool


class ClassChangeRequest(BaseModel):
    session_id: uuid.UUID
    target_arm_id: uuid.UUID


class GuardianOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    phone: str | None
    email: str | None
    occupation: str | None


class GuardianCreate(BaseModel):
    full_name: str
    phone: str | None = None
    email: EmailStr | None = None
    occupation: str | None = None
    address: str | None = None


class GuardianLink(BaseModel):
    guardian_id: uuid.UUID
    relationship: str = Field(default="guardian")
    is_primary: bool = False