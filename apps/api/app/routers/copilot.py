"""School copilot: free-form Q&A over a school's own data, plus admin commands.

All routes are gated on ``ai.copilot`` (leadership tool, provisioned into the
director/principal/vp-academics/head-teacher/academic-coordinator templates).
POST asks and gets conversation history; GET /intents serves the catalog the UI
renders as suggested-question chips.

POST /ask also accepts *admin commands* ("add Genesis John to Nursery 1"). The
route only proves you may use the copilot: the caller's full permission set is
passed through to the service, where each command names the permission it needs
(``students.create``, ``academics.manage``, ``results.publish``, …) and is
re-checked before it runs. A user with ``ai.copilot`` but no admission rights is
answered with an honest refusal, not a write.
"""
import uuid

from fastapi import APIRouter, Depends

from ..core.deps import DbSession, ensure_ai, require_permission
from ..core.errors import NotFoundError
from ..core.permissions import AI_COPILOT
from ..schemas.copilot import (
    AskResponse,
    ConversationDetail,
    ConversationOut,
    CopilotAsk,
    IntentOut,
    MessageOut,
)
from ..services import copilot_service

router = APIRouter(prefix="/copilot", tags=["copilot"])


def _conv_out(row) -> ConversationOut:
    return ConversationOut(
        id=row.id,
        title=row.title,
        term_id=row.term_id,
        created_at=row.created_at,
    )


def _msg_out(row) -> MessageOut:
    return MessageOut(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        intent=row.intent,
        answer_payload=row.answer_payload,
        created_at=row.created_at,
    )


@router.post("/ask", response_model=AskResponse, status_code=201)
def ask(
    payload: CopilotAsk,
    db: DbSession,
    ctx=Depends(require_permission(AI_COPILOT)),
    _ai=Depends(ensure_ai),
):
    """Ask the copilot a question, or give it an admin command to run.

    Appends to a conversation or starts one, meters the assistant turn into
    ``ai_usage``, and returns the answer. Commands come back as a proposal to
    confirm, or as the result of one already confirmed.
    """
    conversation, message = copilot_service.ask_copilot(
        db,
        ctx.school.id,
        question=payload.question,
        conversation_id=str(payload.conversation_id) if payload.conversation_id else None,
        term_id=payload.term_id,
        actor_id=ctx.user.id,
        permission_codes=ctx.permission_codes,
        is_superadmin=ctx.user.is_superadmin,
    )
    db.commit()
    return AskResponse(
        conversation=_conv_out(conversation),
        message=_msg_out(message),
    )


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: DbSession,
    ctx=Depends(require_permission(AI_COPILOT)),
    _ai=Depends(ensure_ai),
):
    """The school's copilot threads, newest first (used for the chat rail)."""
    return [_conv_out(c) for c in copilot_service.get_conversations(db, ctx.school.id)]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(AI_COPILOT)),
    _ai=Depends(ensure_ai),
):
    """One thread with its full message history."""
    conversation = copilot_service.get_conversation(db, ctx.school.id, str(conversation_id))
    messages = copilot_service.conversation_messages(db, conversation)
    return ConversationDetail(
        **_conv_out(conversation).model_dump(),
        messages=[_msg_out(m) for m in messages],
    )


@router.get("/intents", response_model=list[IntentOut])
def intents(
    db: DbSession,
    ctx=Depends(require_permission(AI_COPILOT)),
    _ai=Depends(ensure_ai),
):
    """What the copilot can answer — the UI renders these as example chips."""
    return copilot_service.intents_catalog()