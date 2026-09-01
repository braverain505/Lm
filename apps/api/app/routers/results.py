"""Results: components, scorecard, score entry, submission, approval workflow."""
import uuid

from fastapi import APIRouter, Depends

from ..core.deps import ActiveSchool, DbSession, ensure_ai, require_permission
from ..core.errors import ConflictError, NotFoundError, PermissionDeniedError
from ..core.permissions import (
    ACADEMICS_MANAGE,
    RESULTS_APPROVE,
    RESULTS_COMMENT,
    RESULTS_ENTER,
    RESULTS_PUBLISH,
    RESULTS_SUBMIT,
    RESULTS_VERIFY,
    RESULTS_VIEW,
)
from ..models import AssessmentComponent, CommentBankEntry, ResultComment
from ..schemas.results import (
    CommentBankCreate,
    CommentBankEntryOut,
    CommentBankUpdate,
    CommentGenerateRequest,
    CommentSaveRequest,
    ComponentCreate,
    ComponentOut,
    ComponentUpdate,
    ReadyRow,
    RejectRequest,
    ReportCard,
    ReportIndexRow,
    ResultCommentOut,
    PsychomotorRowIn,
    PsychomotorSaveRequest,
    ScoreSaveRequest,
    SubjectActionRequest,
    SubjectSubmitRequest,
    WorkbenchRow,
)
from ..services import ai_service, comment_bank_service, results_service
from ..services.academics_service import get_arm, get_term, require_active_term

router = APIRouter(prefix="/results", tags=["results"])


def _require_active_term(db, school_id, term_id) -> None:
    """Block every results write until the admin has activated both the term
    and its session. Read endpoints stay available so admins can still review."""
    require_active_term(db, school_id, term_id)


def _component(c: AssessmentComponent) -> ComponentOut:
    return ComponentOut(
        id=c.id,
        term_id=c.term_id,
        class_arm_id=c.class_arm_id,
        name=c.name,
        max_score=float(c.max_score),
        weight=float(c.weight),
        sort_order=c.sort_order,
    )


# --- Assessment components ------------------------------------------------------
@router.get("/components", response_model=list[ComponentOut])
def list_components(
    ctx: ActiveSchool,
    db: DbSession,
    term_id: uuid.UUID,
    arm_id: uuid.UUID | None = None,
):
    comps = results_service.ensure_default_components(db, ctx.school.id, term_id)
    db.commit()
    comps = results_service.effective_components(
        db, ctx.school.id, term_id, class_arm_id=arm_id
    )
    return [_component(c) for c in comps]


@router.post("/components", response_model=ComponentOut, status_code=201)
def create_component(
    payload: ComponentCreate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    comp = AssessmentComponent(
        school_id=ctx.school.id,
        term_id=payload.term_id,
        class_arm_id=payload.class_arm_id,
        name=payload.name,
        max_score=payload.max_score,
        weight=payload.weight,
        sort_order=payload.sort_order,
    )
    db.add(comp)
    db.commit()
    return _component(comp)


@router.patch("/components/{component_id}", response_model=ComponentOut)
def update_component(
    component_id: uuid.UUID,
    payload: ComponentUpdate,
    db: DbSession,
    ctx=Depends(require_permission(ACADEMICS_MANAGE)),
):
    comp = db.get(AssessmentComponent, component_id)
    if comp is None or comp.school_id != ctx.school.id:
        raise NotFoundError("Component not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(comp, key, value)
    db.commit()
    return _component(comp)


# --- Scorecard ------------------------------------------------------------------
@router.get("/scorecard")
def get_scorecard(
    db: DbSession,
    arm_id: uuid.UUID,
    subject_id: uuid.UUID,
    term_id: uuid.UUID,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    result = results_service.scorecard(
        db, ctx.school.id, arm_id=arm_id, subject_id=subject_id, term_id=term_id
    )
    db.commit()
    return result


@router.put("/scorecard")
def save_scorecard(
    payload: ScoreSaveRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_ENTER)),
):
    entries = [
        {
            "student_enrollment_id": e.student_enrollment_id,
            "scores": [
                {"assessment_component_id": c.assessment_component_id, "score": c.score}
                for c in e.scores
            ],
        }
        for e in payload.entries
    ]
    _require_active_term(db, ctx.school.id, payload.term_id)
    result = results_service.save_scores(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
        term_id=payload.term_id, entries=entries, actor_id=ctx.user.id,
        permission_codes=ctx.permission_codes, is_superadmin=ctx.user.is_superadmin,
    )
    db.commit()
    return result


@router.post("/submit")
def submit(
    payload: SubjectSubmitRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_SUBMIT)),
):
    _require_active_term(db, ctx.school.id, payload.term_id)
    count = results_service.submit_arm_subject(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
        term_id=payload.term_id, actor_id=ctx.user.id,
        permission_codes=ctx.permission_codes, is_superadmin=ctx.user.is_superadmin,
    )
    db.commit()
    return {"submitted": count}# --- Compile (one-click finalize) ------------------------------------------------
@router.post("/compile")
def compile_results(
    payload: SubjectSubmitRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_ENTER)),
):
    """One-click compile: submit → verify → approve → publish for one arm ×
    subject × term. The admin clicks this to finalize results and generate
    report cards."""
    _require_active_term(db, ctx.school.id, payload.term_id)
    result = results_service.compile_arm_subject(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
        term_id=payload.term_id, actor_id=ctx.user.id,
        permission_codes=ctx.permission_codes, is_superadmin=ctx.user.is_superadmin,
    )
    db.commit()
    return result


# --- Approval workflow -------------------------------------------------------------
def _run_transition(source: str, key: str, count: int, verb: str) -> dict:
    if count == 0:
        raise ConflictError(
            f"No {source} results to {verb} for this arm/subject/term"
        )
    return {key: count}

@router.post("/verify")
def verify(
    payload: SubjectActionRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_VERIFY)),
):
    _require_active_term(db, ctx.school.id, payload.term_id)
    count = results_service.verify_arm_subject(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
        term_id=payload.term_id, actor_id=ctx.user.id,
    )
    db.commit()
    return _run_transition("submitted", "verified", count, "verify")


@router.post("/approve")
def approve(
    payload: SubjectActionRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_APPROVE)),
):
    _require_active_term(db, ctx.school.id, payload.term_id)
    count = results_service.approve_arm_subject(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
        term_id=payload.term_id, actor_id=ctx.user.id,
    )
    db.commit()
    return _run_transition("verified", "approved", count, "approve")


@router.post("/publish")
def publish(
    payload: SubjectActionRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_PUBLISH)),
):
    _require_active_term(db, ctx.school.id, payload.term_id)
    count = results_service.publish_arm_subject(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
        term_id=payload.term_id, actor_id=ctx.user.id,
    )
    db.commit()
    return _run_transition("approved", "published", count, "publish")


@router.post("/reject")
def reject(
    payload: RejectRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_APPROVE)),
):
    """An approver bounces in-flight results back to draft with a reason,
    unlocking re-entry by the assigned teacher."""
    _require_active_term(db, ctx.school.id, payload.term_id)
    count = results_service.reject_arm_subject(
        db, ctx.school.id,
        arm_id=payload.arm_id, subject_id=payload.subject_id,
        term_id=payload.term_id, actor_id=ctx.user.id,
        reason=payload.reason,
    )
    db.commit()
    if count == 0:
        raise ConflictError(
            "No submitted/verified/approved results to reject for this arm/subject/term"
        )
    return {"rejected": count}


# --- Readiness --------------------------------------------------------------------
@router.get("/readiness", response_model=list[ReadyRow])
def readiness(
    db: DbSession,
    term_id: uuid.UUID,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    rows = results_service.readiness_for_term(db, ctx.school.id, term_id)
    return [ReadyRow(**r) for r in rows]


# --- Approval workbench -------------------------------------------------------------
@router.get("/workbench", response_model=list[WorkbenchRow])
def workbench(
    db: DbSession,
    term_id: uuid.UUID,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """Per arm x subject, where each stage of the review funnel stands."""
    rows = results_service.workbench_for_term(db, ctx.school.id, term_id)
    return [WorkbenchRow(**r) for r in rows]


# --- Report cards --------------------------------------------------------------
@router.get("/report-index", response_model=list[ReportIndexRow])
def report_index(
    db: DbSession,
    arm_id: uuid.UUID,
    term_id: uuid.UUID,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """Which students in an arm have cards ready to print this term."""
    rows = results_service.report_index(
        db, ctx.school.id, arm_id=arm_id, term_id=term_id
    )
    return [ReportIndexRow(**r) for r in rows]


@router.get("/report-card", response_model=ReportCard)
def report_card(
    db: DbSession,
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """One student's printable term report, rendered only from published
    snapshots."""
    card = results_service.report_card(
        db, ctx.school.id, student_id=student_id, term_id=term_id
    )
    card["can_comment"] = results_service.can_comment_on(
        db,
        ctx.school.id,
        actor_user_id=ctx.user.id,
        has_comment_perm=RESULTS_COMMENT in ctx.permission_codes,
        student_id=student_id,
        term_id=term_id,
    )
    return ReportCard(**card)


@router.get("/report-cards", response_model=list[ReportCard])
def report_cards_bulk(
    db: DbSession,
    arm_id: uuid.UUID,
    term_id: uuid.UUID,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """Every student's printable card for an arm this term (published only)."""
    cards = results_service.report_cards_bulk(
        db, ctx.school.id, arm_id=arm_id, term_id=term_id
    )
    for card in cards:
        card["can_comment"] = results_service.can_comment_on(
            db,
            ctx.school.id,
            actor_user_id=ctx.user.id,
            has_comment_perm=RESULTS_COMMENT in ctx.permission_codes,
            student_id=uuid.UUID(card["student"]["student_id"]),
            term_id=term_id,
        )
    return [ReportCard(**c) for c in cards]


@router.get("/cumulative")
def cumulative(
    db: DbSession,
    student_id: uuid.UUID,
    session_id: uuid.UUID,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    return results_service.cumulative_for_session(
        db, ctx.school.id, student_id=student_id, session_id=session_id
    )


@router.get("/broadsheet")
def broadsheet(
    db: DbSession,
    arm_id: uuid.UUID,
    term_id: uuid.UUID,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """Return published report-card totals for every student in an arm."""
    return results_service.report_cards_bulk(
        db, ctx.school.id, arm_id=arm_id, term_id=term_id
    )


# --- AI result comments ---------------------------------------------------------
def _comment_out(row: ResultComment, student_id: uuid.UUID) -> ResultCommentOut:
    return ResultCommentOut(
        student_id=student_id,
        term_id=row.term_id,
        role=row.role,
        body=row.body,
        provider=row.provider,
        model=row.model,
        revision=row.revision,
        generated_at=row.generated_at,
    )


def _require_comment_access(db, ctx, student_id: uuid.UUID, term_id: uuid.UUID) -> None:
    """Result comments may be written only by principal / VP roles (hold the
    ``results.comment`` permission) or by the student's homeroom teacher."""
    allowed = results_service.can_comment_on(
        db,
        ctx.school.id,
        actor_user_id=ctx.user.id,
        has_comment_perm=RESULTS_COMMENT in ctx.permission_codes,
        student_id=student_id,
        term_id=term_id,
    )
    if not allowed:
        raise PermissionDeniedError(
            "Only the principal, vice principal or the student's homeroom "
            "teacher can write result comments"
        )


@router.get("/{student_id}/comment", response_model=ResultCommentOut)
def get_result_comment(
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    db: DbSession,
    role: str = "principal",
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """The stored remark for one student × term × role (None → 404)."""
    row = ai_service.get_result_comment(
        db, ctx.school.id, student_id=student_id, term_id=term_id, role=role
    )
    if row is None:
        raise NotFoundError("No result comment saved for this student/term/role yet")
    return _comment_out(row, student_id)


@router.post("/{student_id}/comment/preview")
def preview_result_comment(
    student_id: uuid.UUID,
    payload: CommentGenerateRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_VIEW)),
    _ai=Depends(ensure_ai),
):
    """Compose the AI draft for review WITHOUT saving or metering. The writer
    can iterate on role/tone/focus, then save (edited or as-is)."""
    _require_active_term(db, ctx.school.id, payload.term_id)
    _require_comment_access(db, ctx, student_id, payload.term_id)
    body = ai_service.preview_result_comment(
        db,
        ctx.school.id,
        student_id=student_id,
        term_id=payload.term_id,
        role=payload.role,
        focus=payload.focus,
        tone=payload.tone,
    )
    return {"body": body}


@router.post("/{student_id}/comment", response_model=ResultCommentOut, status_code=201)
def generate_result_comment(
    student_id: uuid.UUID,
    db: DbSession,
    term_id: uuid.UUID | None = None,
    payload: CommentGenerateRequest | None = None,
    ctx=Depends(require_permission(RESULTS_VIEW)),
    _ai=Depends(ensure_ai),
):
    """Compose + save one role's comment for a published report card,
    metering the generation into ``ai_usage``. Regeneration bumps revision.

    Accepts either a JSON body (``CommentGenerateRequest`` with role/focus/
    tone) or the legacy ``?term_id=`` query form (principal role, professional
    tone), so existing callers keep working."""
    tid = payload.term_id if payload is not None else term_id
    if tid is None:
        raise NotFoundError("term_id is required")
    _require_active_term(db, ctx.school.id, tid)
    _require_comment_access(db, ctx, student_id, tid)
    role = payload.role if payload is not None else "principal"
    focus = payload.focus if payload is not None else None
    tone = payload.tone if payload is not None else "professional"
    row = ai_service.generate_result_comment(
        db,
        ctx.school.id,
        student_id=student_id,
        term_id=tid,
        role=role,
        focus=focus,
        tone=tone,
        actor_id=ctx.user.id,
    )
    db.commit()
    return _comment_out(row, student_id)


@router.put("/{student_id}/comment", response_model=ResultCommentOut)
def save_result_comment(
    student_id: uuid.UUID,
    payload: CommentSaveRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """Save a manually written/edited comment for one role. Stores with
    ``provider=manual`` so consumers can tell authored text from AI output."""
    _require_active_term(db, ctx.school.id, payload.term_id)
    _require_comment_access(db, ctx, student_id, payload.term_id)
    row = ai_service.save_manual_comment(
        db,
        ctx.school.id,
        student_id=student_id,
        term_id=payload.term_id,
        role=payload.role,
        body=payload.body,
        actor_id=ctx.user.id,
    )
    db.commit()
    return _comment_out(row, student_id)


# --- Comment bank --------------------------------------------------------------
@router.get("/comment-bank", response_model=list[CommentBankEntryOut])
def list_comment_bank(
    db: DbSession,
    category: str | None = None,
    sentiment: str | None = None,
    search: str | None = None,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """Search the school's comment bank by category, sentiment or text."""
    rows = comment_bank_service.list_comment_bank(
        db,
        ctx.school.id,
        category=category,
        sentiment=sentiment,
        search=search,
    )
    return rows


@router.post("/comment-bank", response_model=CommentBankEntryOut, status_code=201)
def create_comment_bank_entry(
    payload: CommentBankCreate,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_COMMENT)),
):
    """Add a reusable phrase to the school's comment bank."""
    row = comment_bank_service.create_comment_bank_entry(
        db,
        ctx.school.id,
        comment_text=payload.comment_text,
        category=payload.category,
        sentiment=payload.sentiment,
        applicable_domain=payload.applicable_domain,
        actor_id=ctx.user.id,
    )
    db.commit()
    return row


@router.patch("/comment-bank/{entry_id}", response_model=CommentBankEntryOut)
def update_comment_bank_entry(
    entry_id: uuid.UUID,
    payload: CommentBankUpdate,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_COMMENT)),
):
    """Edit a bank entry, or deactivate it (``is_active=false``)."""
    row = comment_bank_service.update_comment_bank_entry(
        db,
        ctx.school.id,
        entry_id,
        comment_text=payload.comment_text,
        category=payload.category,
        sentiment=payload.sentiment,
        applicable_domain=payload.applicable_domain,
        is_active=payload.is_active,
    )
    db.commit()
    return row


@router.delete("/comment-bank/{entry_id}", response_model=CommentBankEntryOut)
def deactivate_comment_bank_entry(
    entry_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_COMMENT)),
):
    """Soft-delete a bank entry so it stops appearing in searches."""
    row = comment_bank_service.update_comment_bank_entry(
        db,
        ctx.school.id,
        entry_id,
        comment_text=None,
        category=None,
        sentiment=None,
        applicable_domain=None,
        is_active=False,
    )
    db.commit()
    return row


# --- Leadership overview -------------------------------------------------------
@router.get("/best-in-subjects")
def best_in_subjects(
    arm_id: uuid.UUID,
    term_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """Which students hold the top score in each core subject this term —
    the class-leadership view."""
    get_arm(db, ctx.school.id, arm_id)
    get_term(db, ctx.school.id, term_id)
    return results_service.best_in_subjects_overview(
        db, ctx.school.id, arm_id=arm_id, term_id=term_id
    )


@router.get("/grade-bands")
def grade_bands(
    term_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """The session's grading key (letter/min/max/remark), for live grade
    previews during score entry."""
    bands = results_service.grade_bands_for_term(db, ctx.school.id, term_id)
    return bands


# --- Psychomotor / affective ---------------------------------------------------
@router.get("/psychomotor")
def list_psychomotor(
    student_id: uuid.UUID,
    term_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_VIEW)),
):
    """The psychomotor/affective rows for one student × term."""
    return results_service.list_psychomotor(
        db, ctx.school.id, student_id=student_id, term_id=term_id
    )


@router.put("/psychomotor")
def save_psychomotor(
    payload: PsychomotorSaveRequest,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_ENTER)),
):
    """Replace a student's psychomotor rows for a term (configurable areas
    and achievement levels)."""
    _require_active_term(db, ctx.school.id, payload.term_id)
    rows = results_service.save_psychomotor(
        db,
        ctx.school.id,
        student_id=payload.student_id,
        term_id=payload.term_id,
        rows=[{"learning_area": r.learning_area, "achievement_level": r.achievement_level} for r in payload.rows],
        actor_id=ctx.user.id,
    )
    db.commit()
    return rows