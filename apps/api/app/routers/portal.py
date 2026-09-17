"""Public result portal: PIN check + the published report card it unlocks.

Deliberately unauthenticated and narrow. The endpoint reads ONLY published
results (the report-card service enforces this), answers generic 404s on any
bad credential, and the token is a short-lived JWT scoped to a single student
at a single school.

Two credentials open the same door:

* ``/result-check`` — the **school result code** (``GVS-7K42Q``) plus the
  child's admission number. The code names the school, the admission number
  names the child. This is the flow on the login screen.
* ``/pin-check`` — the older, narrower per-student PIN.
"""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from ..core.deps import DbSession
from ..core.errors import NotFoundError
from ..core.rate_limit import limiter
from ..core.security import decode_portal_token
from ..models import School
from ..schemas.portal import (
    PinCheck,
    PinCheckOut,
    PinTermBrief,
    SchoolBrief,
    SchoolPinCheck,
)
from ..schemas.results import ReportCard
from ..services import portal_service

router = APIRouter(prefix="/public", tags=["public"])


def _school_brief(school: School) -> SchoolBrief:
    return SchoolBrief(id=school.id, name=school.name, slug=school.slug)


def _student_brief(student) -> dict:
    return {
        "student_id": str(student.id),
        "admission_no": student.admission_no,
        "full_name": student.full_name,
    }


@router.get("/schools", response_model=list[SchoolBrief])
def public_schools(db: DbSession):
    """Schools that publish results through the PIN portal."""
    schools = db.scalars(select(School).order_by(School.name)).all()
    return [SchoolBrief(id=s.id, name=s.name, slug=s.slug) for s in schools]


@router.post("/result-check", response_model=PinCheckOut)
@limiter.limit("10/minute")  # the per-IP backstop to guess-the-code attempts
def result_check(body: SchoolPinCheck, request: Request, db: DbSession):
    """Exchange a school result code + admission no for a short-lived token.

    The code is the only thing that identifies the school, so parents do not
    have to find their school in a list — the initials in the code already say
    which school it is.
    """
    school, student = portal_service.resolve_school_pin(
        db, code=body.pin, admission_no=body.admission_no
    )
    return PinCheckOut(
        token=portal_service.portal_token(school, student),
        student=_student_brief(student),
        school=_school_brief(school),
    )


@router.post("/pin-check", response_model=PinCheckOut)
@limiter.limit("5/minute")  # Per-IP backstop to the per-student PIN lockout
def pin_check(body: PinCheck, request: Request, db: DbSession):
    """Exchange admission no + PIN for a short-lived portal token."""
    school, student = portal_service.resolve_pin(
        db, school_slug=body.school_slug, admission_no=body.admission_no, pin=body.pin
    )
    return PinCheckOut(
        token=portal_service.portal_token(school, student),
        student=_student_brief(student),
        school=_school_brief(school),
    )


@router.get("/terms", response_model=list[PinTermBrief])
def public_terms(db: DbSession, token: str = Query(min_length=1)):
    """Terms this student has published results in, newest first.

    Scoped by the portal token itself, so it leaks nothing to a caller who has
    not already proven the school code + admission number.
    """
    payload = decode_portal_token(token)
    if payload is None:
        raise NotFoundError("Invalid portal token")
    terms = portal_service.published_terms(
        db,
        school_id=uuid.UUID(payload["school"]),
        student_id=uuid.UUID(payload["sub"]),
    )
    return [
        PinTermBrief(id=t.id, name=t.name, session_name=t.session.name) for t in terms
    ]


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
