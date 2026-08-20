"""Question banks: deterministic AI practice questions behind the same gates as
lesson plans (POST ``results.comment``; GET ``results.view``)."""
import uuid

from fastapi import APIRouter, Depends

from ..core.deps import DbSession, ensure_ai, require_permission
from ..core.errors import NotFoundError
from ..core.permissions import RESULTS_COMMENT, RESULTS_VIEW
from ..models import QuestionBank
from ..schemas.question_banks import QuestionBankCreate, QuestionBankOut
from ..services import ai_service

router = APIRouter(prefix="/question-banks", tags=["question-banks"])


def _bank_out(row: QuestionBank) -> QuestionBankOut:
    return QuestionBankOut(
        id=row.id,
        term_id=row.term_id,
        subject_id=row.subject_id,
        class_arm_id=row.class_arm_id,
        topic=row.topic,
        bank=row.bank,
        provider=row.provider,
        model=row.model,
        revision=row.revision,
        generated_at=row.generated_at,
    )


@router.get("", response_model=QuestionBankOut)
def get_question_bank(
    term_id: uuid.UUID,
    subject_id: uuid.UUID,
    class_arm_id: uuid.UUID,
    topic: str,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_VIEW)),
    _ai=Depends(ensure_ai),
):
    """The stored bank for one cell (None → 404)."""
    row = ai_service.get_question_bank(
        db, ctx.school.id,
        term_id=term_id, subject_id=subject_id,
        class_arm_id=class_arm_id, topic=topic,
    )
    if row is None:
        raise NotFoundError("No question bank saved for this subject/class/topic yet")
    return _bank_out(row)


@router.post("", response_model=QuestionBankOut, status_code=201)
def generate_question_bank(
    payload: QuestionBankCreate,
    db: DbSession,
    ctx=Depends(require_permission(RESULTS_COMMENT)),
    _ai=Depends(ensure_ai),
):
    """Compose + save a question bank for subject × class × term × topic,
    metering the generation into ``ai_usage``. Regeneration bumps revision."""
    row = ai_service.generate_question_bank(
        db, ctx.school.id,
        term_id=payload.term_id, subject_id=payload.subject_id,
        class_arm_id=payload.class_arm_id, topic=payload.topic,
        count=payload.count, actor_id=ctx.user.id,
    )
    db.commit()
    return _bank_out(row)