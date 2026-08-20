"""Lesson plans: deterministic AI lesson plans behind the same gates as result
comments (POST ``results.comment``; GET ``results.view``)."""
import uuid

from fastapi import APIRouter, Depends

from ..core.deps import DbSession, ensure_ai, require_permission
from ..core.errors import NotFoundError
from ..core.permissions import RESULTS_COMMENT, RESULTS_VIEW
from ..models import LessonPlan
from ..schemas.lesson_plans import LessonPlanCreate, LessonPlanOut
from ..services import ai_service

router = APIRouter(prefix="/lesson-plans", tags=["lesson-plans"])


def _plan_out(row: LessonPlan) -> LessonPlanOut:
    return LessonPlanOut(
        id=row.id,
        term_id=row.term_id,
        subject_id=row.subject_id,
        class_arm_id=row.class_arm_id,
        topic=row.topic,
        plan=row.plan,
        provider=row.provider,
        model=row.model,
        revision=row.revision,
        generated_at=row.generated_at,
    )


@router.get("", response_model=LessonPlanOut)
def get_lesson_plan(
    term_id: uuid.UUID,
    subject_id: uuid.UUID,
    class_arm_id: uuid.UUID,
    topic: str,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_VIEW)),
    _ai=Depends(ensure_ai),
):
    """The stored plan for one cell (None → 404)."""
    row = ai_service.get_lesson_plan(
        db, ctx.school.id,
        term_id=term_id, subject_id=subject_id,
        class_arm_id=class_arm_id, topic=topic,
    )
    if row is None:
        raise NotFoundError("No lesson plan saved for this subject/class/topic yet")
    return _plan_out(row)


@router.post("", response_model=LessonPlanOut, status_code=201)
def generate_lesson_plan(
    payload: LessonPlanCreate,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_COMMENT)),
    _ai=Depends(ensure_ai),
):
    """Compose + save a lesson plan for subject × class × term × topic,
    metering the generation into ``ai_usage``. Regeneration bumps revision."""
    row = ai_service.generate_lesson_plan(
        db, ctx.school.id,
        term_id=payload.term_id, subject_id=payload.subject_id,
        class_arm_id=payload.class_arm_id, topic=payload.topic,
        periods=payload.periods, actor_id=ctx.user.id,
    )
    db.commit()
    return _plan_out(row)