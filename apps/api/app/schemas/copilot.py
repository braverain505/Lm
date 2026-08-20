"""Copilot schemas: free-form Q&A over a school's own data (Phase 2 final slice)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CopilotAsk(BaseModel):
    """One turn. ``conversation_id`` resumes a thread; without it a new
    conversation is created. ``term_id`` sets (or overrides) the results scope
    on a fresh conversation."""

    question: str = Field(min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None
    term_id: uuid.UUID | None = None


class IntentOut(BaseModel):
    """One thing the copilot can answer (rendered as a suggested-question chip)."""

    id: str
    name: str
    examples: list[str]


class MessageOut(BaseModel):
    """One turn in a conversation: user or assistant. Assistant rows carry the
    recognized ``intent`` and the grounded ``answer_payload``."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    intent: str | None = None
    answer_payload: dict | None = None
    created_at: datetime


class ConversationOut(BaseModel):
    """A copilot thread (without its messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    term_id: uuid.UUID | None = None
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class AskResponse(BaseModel):
    """The result of POST /copilot/ask: the (possibly new) conversation and the
    assistant's answer message."""

    conversation: ConversationOut
    message: MessageOut