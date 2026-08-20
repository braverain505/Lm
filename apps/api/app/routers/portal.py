"""Public result portal: PIN check + the published report card it unlocks.

Deliberately unauthenticated and narrow. The endpoint reads ONLY published
results (the report-card service enforces this), answers generic 404s on any
bad credential, and the token is a short-lived JWT scoped to a single student
at a single school.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from ..core.deps import DbSession
from ..core.errors import NotFoundError
from ..core.security import decode_portal_token
from ..models import School
from ..schemas.portal import PinCheck, PinCheckOut, SchoolBrief
from ..schemas.results import ReportCard
from ..services import portal_service

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/schools", response_model=list[SchoolBrief])
def public_schools(db: DbSession):
    """Schools that publish results through the PIN portal."""
    schools = db.scalars(select(School).order_by(School.name)).all()
    return [SchoolBrief(id=s.id, name=s.name, slug=s.slug) for s in schools]


@router.post("/pin-check", response_model=PinCheckOut)
def pin_check(body: PinCheck, db: DbSession):
    """Exchange admission no + PIN for a short-lived portal token."""
    school, student = portal_service.resolve_pin(
        db, school_slug=body.school_slug, admission_no=body.admission_no, pin=body.pin
    )
    return PinCheckOut(
        token=portal_service.portal_token(school, student),
        student={
            "student_id": str(student.id),
            "admission_no": student.admission_no,
            "full_name": student.full_name,
        },
    )


@router.get("/report-card", response_model=ReportCard)
def public_report_card(
    db: DbSession,
    token: str = Query(min_length=1),
    term_id: uuid.UUID | None = None,
):
    """Latest published report card for the student behind the token. Pass an
    explicit ``term_id`` to read an earlier published term."""
    payload = decode_portal_token(token)
    if payload is None:
        raise NotFoundError("Invalid portal token")
    school_id = uuid.UUID(payload["school"])
    student_id = uuid.UUID(payload["sub"])
    if term_id is None:
        term_id = portal_service.latest_published_term_id(
            db, school_id=school_id, student_id=student_id
        )
    card = portal_service.report_card_for_portal(
        db, student_id=student_id, school_id=school_id, term_id=term_id
    )
    return ReportCard(**card)