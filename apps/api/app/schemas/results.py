"""Results schemas: components, score entry, scorecard, submission, readiness."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class ComponentCreate(BaseModel):
    term_id: uuid.UUID
    class_arm_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=60)
    max_score: float = Field(gt=0)
    weight: float = Field(gt=0)
    sort_order: int = 0


class ComponentOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    term_id: uuid.UUID
    class_arm_id: uuid.UUID | None
    name: str
    max_score: float
    weight: float
    sort_order: int


class ComponentUpdate(BaseModel):
    name: str | None = None
    max_score: float | None = Field(default=None, gt=0)
    weight: float | None = Field(default=None, gt=0)
    is_active: bool | None = None


class ScoreCell(BaseModel):
    assessment_component_id: uuid.UUID
    score: float | None = None


class ScoreEntry(BaseModel):
    student_enrollment_id: uuid.UUID
    scores: list[ScoreCell] = []


class ScoreSaveRequest(BaseModel):
    arm_id: uuid.UUID
    subject_id: uuid.UUID
    term_id: uuid.UUID
    entries: list[ScoreEntry]


class SubjectSubmitRequest(BaseModel):
    arm_id: uuid.UUID
    subject_id: uuid.UUID
    term_id: uuid.UUID


class SubjectActionRequest(BaseModel):
    """Identifies one arm x subject x term cell for a workflow transition."""

    arm_id: uuid.UUID
    subject_id: uuid.UUID
    term_id: uuid.UUID


class RejectRequest(SubjectActionRequest):
    """Bounce an in-flight result (submitted/verified/approved) back to draft."""

    reason: str = Field(min_length=1, max_length=500)


class WorkbenchRow(BaseModel):
    arm_id: uuid.UUID
    term_id: uuid.UUID
    arm_name: str
    subject_id: uuid.UUID
    subject_name: str
    enrolled: int
    entered: int
    draft: int
    submitted: int
    verified: int
    approved: int
    rejected: int
    published: int


class ReadyRow(BaseModel):
    arm_id: uuid.UUID
    arm_name: str
    subject_id: uuid.UUID
    subject_name: str
    student_count: int
    entered: int
    submitted: int
    pending: int
    entered_pct: float

class ReportSubjectRow(BaseModel):
    """One published subject line on a report card. Values come from the
    frozen ``published_snapshot`` so totals/grades can't drift after print."""

    subject_id: uuid.UUID
    subject_name: str
    total: float | None
    grade_letter: str | None
    grade_point: float | None
    remark: str | None
    position: int | None
    components: list[dict]
    is_core: bool = False


class ReportSummary(BaseModel):
    subjects_published: int
    total: float | None
    average: float | None
    grade_letter: str | None
    remark: str | None
    class_rank: int | None
    class_size: int


class ReportStudent(BaseModel):
    student_id: uuid.UUID
    admission_no: str
    full_name: str
    gender: str
    photo_url: str | None = None
    date_of_birth: date | None = None


class ReportRef(BaseModel):
    id: uuid.UUID
    name: str


class ReportArmRef(BaseModel):
    id: uuid.UUID
    full_name: str


class ReportSchoolRef(BaseModel):
    name: str
    short_name: str | None = None
    motto: str | None = None
    logo_url: str | None = None


class PsychomotorRow(BaseModel):
    learning_area: str
    achievement_level: str


class PsychomotorRowIn(BaseModel):
    learning_area: str = Field(min_length=1, max_length=80)
    achievement_level: str = Field(min_length=1, max_length=24)


class PsychomotorSaveRequest(BaseModel):
    """Replace the psychomotor rows for one student × term (configurable
    learning areas and achievement levels)."""

    student_id: uuid.UUID
    term_id: uuid.UUID
    rows: list[PsychomotorRowIn] = []


class GradingKeyRow(BaseModel):
    letter: str
    min_score: float
    max_score: float
    remark: str | None = None


class ReportComments(BaseModel):
    principal: str | None = None
    vice_principal: str | None = None
    homeroom: str | None = None


class BestInSubjectRow(BaseModel):
    """One core subject where the student is (co-)best in their arm, per term."""

    subject_id: uuid.UUID
    subject_name: str
    top_score: float
    is_best: bool
    tied: bool
    co_leaders: list[str] = []


class ReportCard(BaseModel):
    school: ReportSchoolRef
    student: ReportStudent
    enrollment_id: uuid.UUID
    term: ReportRef
    session: ReportRef
    class_arm: ReportArmRef
    academic_year: str
    report_date: date
    subjects: list[ReportSubjectRow]
    psychomotor: list[PsychomotorRow] = []
    psychomotor_average: str | None = None
    conduct: str | None = None
    attendance_pct: float | None = None
    homeroom_teacher: str | None = None
    next_term_date: date | None = None
    next_term_label: str | None = None
    grading_key: list[GradingKeyRow] = []
    comments: ReportComments
    summary: ReportSummary
    best_in_subjects: list[BestInSubjectRow] = []
    can_comment: bool = False
    can_manage_psychomotor: bool = False


class ReportIndexRow(BaseModel):
    student_id: uuid.UUID
    enrollment_id: uuid.UUID
    admission_no: str
    full_name: str
    subjects_published: int
    total: float | None


class ResultCommentOut(BaseModel):
    """One stored comment for a student × term, for one role
    (principal / vice_principal / homeroom)."""

    student_id: uuid.UUID
    term_id: uuid.UUID
    role: str
    body: str
    provider: str
    model: str | None
    revision: int
    generated_at: datetime


class CommentSaveRequest(BaseModel):
    """Persist a manually written/edited comment for a role. ``role`` is
    validated against the three report roles."""

    term_id: uuid.UUID
    role: str = Field(default="principal", pattern="^(principal|vice_principal|homeroom)$")
    body: str = Field(min_length=1, max_length=2000)


class CommentGenerateRequest(BaseModel):
    """Trigger AI generation for a role. ``focus`` steers the narrative
    (e.g. effort, performance, improvement); ``tone`` picks the register."""

    term_id: uuid.UUID
    role: str = Field(default="principal", pattern="^(principal|vice_principal|homeroom)$")
    focus: str | None = Field(default=None, max_length=200)
    tone: str = Field(default="professional", pattern="^(professional|warm|concise)$")


class CommentBankEntryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    comment_text: str
    category: str
    sentiment: str
    applicable_domain: str | None
    is_active: bool
    created_at: datetime


class CommentBankCreate(BaseModel):
    comment_text: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=32)
    sentiment: str = Field(default="positive", pattern="^(positive|neutral|negative)$")
    applicable_domain: str | None = Field(default=None, max_length=40)


class CommentBankUpdate(BaseModel):
    comment_text: str | None = Field(default=None, min_length=1, max_length=2000)
    category: str | None = Field(default=None, min_length=1, max_length=32)
    sentiment: str | None = Field(default=None, pattern="^(positive|neutral|negative)$")
    applicable_domain: str | None = Field(default=None, max_length=40)
    is_active: bool | None = None
