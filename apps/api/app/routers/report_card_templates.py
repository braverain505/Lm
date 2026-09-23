"""Report card designs: the drag-and-drop builder's backing store.

Every route is tenant-scoped through ``get_school_context``, so a design is
read and written inside exactly one school.

Reading is open to any member of the school (``ActiveSchool``): a design is a
document *layout*, not student data, and a teacher opening a card has to draw it.
Writing — create, edit, set default, duplicate, delete — needs
``school.manage``, which is the school admin's/principal's capability: picking
what a report card looks like is an administrative decision, and the Exam Office
prints cards rather than redesigning them.
"""
import uuid

from fastapi import APIRouter, Depends, Response

from ..core.deps import ActiveSchool, DbSession, require_permission
from ..core.permissions import SCHOOL_MANAGE
from ..schemas.report_card import (
    ReportCardTemplateBrief,
    ReportCardTemplateIn,
    ReportCardTemplateOut,
    ReportCardTemplatePatch,
)
from ..services import report_card_service

router = APIRouter(prefix="/report-card-templates", tags=["report-cards"])


@router.get("", response_model=list[ReportCardTemplateOut])
def list_templates(db: DbSession, ctx: ActiveSchool):
    """Every design this school has saved, default first."""
    return [
        ReportCardTemplateOut.model_validate(row)
        for row in report_card_service.list_templates(db, ctx.school.id)
    ]


@router.get("/default", response_model=ReportCardTemplateBrief)
def default_design(db: DbSession, ctx: ActiveSchool):
    """The design to draw on this school's report cards.

    Always answers: a school that has saved no design gets the built-in card
    with ``builtin: true``, so a renderer never has to invent a fallback of its
    own.
    """
    row = report_card_service.resolve_default(db, ctx.school.id)
    layout = report_card_service.default_layout(db, ctx.school.id)
    if row is None:
        return ReportCardTemplateBrief(
            template_id=None,
            name="Clearis default card",
            theme=layout.get("theme", "classic"),
            layout=layout,
            builtin=True,
        )
    return ReportCardTemplateBrief(
        template_id=row.id,
        name=row.name,
        theme=layout.get("theme", "classic"),
        layout=layout,
        builtin=False,
    )


@router.post("", response_model=ReportCardTemplateOut, status_code=201)
def create_template(
    payload: ReportCardTemplateIn,
    db: DbSession,
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Save a new design. The school's first design becomes its default."""
    row = report_card_service.create_template(
        db, ctx.school.id, payload, actor_id=ctx.user.id
    )
    db.commit()
    return ReportCardTemplateOut.model_validate(row)


@router.get("/{template_id}", response_model=ReportCardTemplateOut)
def get_template(template_id: uuid.UUID, db: DbSession, ctx: ActiveSchool):
    row = report_card_service.get_template(db, ctx.school.id, template_id)
    return ReportCardTemplateOut.model_validate(row)


@router.patch("/{template_id}", response_model=ReportCardTemplateOut)
def update_template(
    template_id: uuid.UUID,
    payload: ReportCardTemplatePatch,
    db: DbSession,
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Rename a design, save a new layout, or mark it the default."""
    row = report_card_service.update_template(
        db, ctx.school.id, template_id, payload, actor_id=ctx.user.id
    )
    db.commit()
    return ReportCardTemplateOut.model_validate(row)


@router.post("/{template_id}/default", response_model=ReportCardTemplateOut)
def set_default(
    template_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Make this the card the school prints."""
    row = report_card_service.set_default(
        db, ctx.school.id, template_id, actor_id=ctx.user.id
    )
    db.commit()
    return ReportCardTemplateOut.model_validate(row)


@router.post("/{template_id}/duplicate", response_model=ReportCardTemplateOut, status_code=201)
def duplicate_template(
    template_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Copy a design under a free name."""
    row = report_card_service.duplicate_template(
        db, ctx.school.id, template_id, actor_id=ctx.user.id
    )
    db.commit()
    return ReportCardTemplateOut.model_validate(row)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: uuid.UUID,
    db: DbSession,
    ctx=Depends(require_permission(SCHOOL_MANAGE)),
):
    """Delete a design. Deleting the default promotes the next-most-recent one."""
    report_card_service.delete_template(
        db, ctx.school.id, template_id, actor_id=ctx.user.id
    )
    db.commit()
    return Response(status_code=204)
