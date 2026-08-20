"""School copilot: conversations + messages for free-form Q&A over a school's
own data.

A conversation is the unit of a chat: it carries an optional ``term_id`` scope
(results questions resolve against the conversation's term) and is created by a
user. Messages belong to exactly one conversation; assistant messages carry the
recognized ``intent`` and an ``answer_payload`` (the real data facts behind the
answer, so the UI can render cards/tables without re-querying).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TenantScopedBase, utcnow


class CopilotConversation(TenantScopedBase, Base):
    """A school copilot chat thread. ``term_id`` pins the results scope (default
    = the school's current term when left null)."""

    __tablename__ = "copilot_conversations"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    term_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("terms.id", ondelete="SET NULL")
    )
    # Last-resolved Q&A slots (arm/subject/level/student ids) so follow-ups
    # like "what about English?" or "how many boys?" carry prior context.
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    messages: Mapped[list["CopilotMessage"]] = relationship(  # noqa: F821
        back_populates="conversation", cascade="all, delete-orphan"
    )


class CopilotMessage(TenantScopedBase, Base):
    """One turn in a conversation: a user question or the assistant's answer.

    Assistant rows carry ``intent`` (the recognized intent code, or
    ``"unknown"``) and ``answer_payload`` — the real numbers behind the answer.
    """

    __tablename__ = "copilot_messages"
    __table_args__ = (
        Index("ix_copilot_message_conv", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(12), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str | None] = mapped_column(String(48))
    answer_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    conversation: Mapped[CopilotConversation] = relationship(
        back_populates="messages"
    )


# Re-export for Base.metadata completeness.
__all__ = ["CopilotConversation", "CopilotMessage"]
