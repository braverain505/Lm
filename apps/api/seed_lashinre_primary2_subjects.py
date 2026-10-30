"""Add La'ashinre Divine Academy's Primary 2 subject list and assign it to the
class teacher.

One-off data load, in the same spirit as ``seed_lashinre_nursery2_subjects.py``.
Run it from ``apps/api``:

    DATABASE_URL='postgresql://user:pass@host/db' python seed_lashinre_primary2_subjects.py --dry-run
    DATABASE_URL='postgresql://user:pass@host/db' python seed_lashinre_primary2_subjects.py --yes

For the given class it:

  * creates each subject the school does not have yet (matching on the name, so
    a subject entered by hand earlier is reused rather than duplicated) and
    gives it a free code when the preferred one is already in use;
  * offers it at Primary 2, in the list's order;
  * assigns the class teacher — David Godiya, already attached to Primary 2 —
    to teach it. Pass ``--teacher`` to name someone else.

It is idempotent: subjects, offerings and assignments already there are kept,
and an assignment held by another teacher is moved to the class teacher unless
``--keep-other-teachers`` is passed. Nothing is committed on ``--dry-run``.
"""
from __future__ import annotations

import argparse
import re

from sqlalchemy import func, select

from app.config import settings
from app.core.database import SessionLocal
from app.models import (
    AcademicSession,
    ClassArm,
    School,
    Staff,
    Subject,
    SubjectAssignment,
    SubjectOffering,
)
from app.services import academics_service

SCHOOL_NAME = "La'ashinre Divine Academy, Jalingo"
CLASS_NAME = "Primary 2"

# The list as it was handed in: (name, preferred code).
SUBJECTS: tuple[tuple[str, str], ...] = (
    ("English Studies", "ENG"),
    ("Mathematics", "MTH"),
    ("Social and Citizenship Studies", "SCS"),
    ("Nigerian History", "NHS"),
    ("Christian Religious Studies", "CRS"),
    ("Physical and Health Education", "PHE"),
    ("Cultural and Creative Art", "CCA"),
    ("Basic Science and Technology", "BST"),
    ("Handwriting", "HWR"),
)


def _key(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", value.lower()))


def _school_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _masked_url() -> str:
    url = settings.database_url
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1) if "://" in url else ("", url)
    credentials, host = rest.rsplit("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}" if scheme else f"{user}:***@{host}"


def _find_school(db, name: str) -> School:
    wanted = _school_key(name)
    matches = [s for s in db.scalars(select(School)) if _school_key(s.name) == wanted]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(repr(s.name) for s in matches)
        raise SystemExit(f"Several schools match {name!r}: {names}. Use --school exactly.")
    known = ", ".join(sorted(s.name for s in db.scalars(select(School))))
    raise SystemExit(f"School {name!r} not found here. Schools: {known or 'none'}.")


def _current_session(db, school_id) -> AcademicSession:
    session = db.scalar(
        select(AcademicSession).where(
            AcademicSession.school_id == school_id,
            AcademicSession.is_current.is_(True),
        )
    )
    if session is None:
        raise SystemExit("This school has no current academic session.")
    return session


def _find_arm(db, school_id, session_id, name: str) -> ClassArm:
    wanted = _school_key(name)
    arms = list(
        db.scalars(
            select(ClassArm).where(
                ClassArm.school_id == school_id,
                ClassArm.academic_session_id == session_id,
            )
        )
    )
    matches = [a for a in arms if _school_key(a.name) == wanted]
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(repr(a.name) for a in sorted(arms, key=lambda a: a.name))
    raise SystemExit(f"Class {name!r} not found this session. Classes: {available}")


def _class_teacher(db, school_id, arm: ClassArm) -> Staff | None:
    """The teacher already attached to the class, if any."""
    if arm.class_teacher_id is None:
        return None
    teacher = db.get(Staff, arm.class_teacher_id)
    if teacher is None or teacher.school_id != school_id or teacher.is_deleted:
        return None
    return teacher


def _find_teacher(db, school_id, name: str) -> Staff:
    staff = [
        s
        for s in db.scalars(
            select(Staff).where(Staff.school_id == school_id, Staff.is_deleted.is_(False))
        )
        if _key(s.full_name) == _key(name)
    ]
    if len(staff) == 1:
        return staff[0]
    raise SystemExit(f"Teacher {name!r} not found at this school.")


def _ensure_subject(db, school_id, name: str, code: str) -> Subject:
    subject = db.scalar(
        select(Subject).where(
            Subject.school_id == school_id, func.lower(Subject.name) == name.lower()
        )
    )
    if subject is not None:
        print(f"  = subject  {subject.name} ({subject.code}) — kept")
        return subject
    taken = db.scalar(
        select(Subject).where(Subject.school_id == school_id, Subject.code == code)
    )
    free_code = code
    suffix = 2
    while taken is not None:
        free_code = f"{code[:14]}{suffix}"
        suffix += 1
        taken = db.scalar(
            select(Subject).where(
                Subject.school_id == school_id, Subject.code == free_code
            )
        )
    if free_code != code:
        print(f"! subject  code {code} is already used — {name!r} gets {free_code}")
    subject = academics_service.create_subject(db, school_id, name=name, code=free_code)
    print(f"  + subject  {subject.name} ({subject.code})")
    return subject


def _ensure_offering(db, school_id, arm: ClassArm, subject: Subject, order: int):
    offering = db.scalar(
        select(SubjectOffering).where(
            SubjectOffering.class_arm_id == arm.id,
            SubjectOffering.subject_id == subject.id,
        )
    )
    if offering is not None:
        if offering.sort_order != order:
            offering.sort_order = order
            db.flush()
            print(f"  = offering {subject.name} — kept (re-ordered to {order})")
        else:
            print(f"  = offering {subject.name} — kept")
        return offering
    offering = SubjectOffering(
        school_id=school_id, class_arm_id=arm.id, subject_id=subject.id, sort_order=order
    )
    db.add(offering)
    db.flush()
    print(f"  + offering {subject.name} (order {order})")
    return offering


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add and assign La'ashinre Divine Academy's Primary 2 subjects."
    )
    parser.add_argument("--school", default=SCHOOL_NAME, help="school name to target")
    parser.add_argument("--class", dest="class_name", default=CLASS_NAME, help="class to load")
    parser.add_argument(
        "--teacher",
        default=None,
        help="teacher to assign (default: the class teacher on the class)",
    )
    parser.add_argument(
        "--keep-other-teachers",
        action="store_true",
        help="leave a subject alone when another teacher already teaches it",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    print(f"Database: {_masked_url()}")

    db = SessionLocal()
    try:
        school = _find_school(db, args.school)
        print(f"School:   {school.name} ({school.id})")
        session = _current_session(db, school.id)
        arm = _find_arm(db, school.id, session.id, args.class_name)
        print(f"Class:    {arm.full_name} ({session.name})")

        if args.teacher:
            teacher = _find_teacher(db, school.id, args.teacher)
        else:
            teacher = _class_teacher(db, school.id, arm)
            if teacher is None:
                raise SystemExit(
                    f"{arm.full_name} has no class teacher on file. "
                    f"Set one in the app, or pass --teacher."
                )
        print(f"Teacher:  {teacher.full_name} ({teacher.staff_no})"
              f"{'' if args.teacher else ' — class teacher'}\n")

        for order, (name, code) in enumerate(SUBJECTS, start=1):
            subject = _ensure_subject(db, school.id, name, code)
            _ensure_offering(db, school.id, arm, subject, order)
            assignment = db.scalar(
                select(SubjectAssignment).where(
                    SubjectAssignment.class_arm_id == arm.id,
                    SubjectAssignment.subject_id == subject.id,
                )
            )
            if assignment is not None and assignment.teacher_id == teacher.id:
                print(f"  = assigned {subject.name} — kept")
            elif assignment is not None and args.keep_other_teachers:
                other = db.get(Staff, assignment.teacher_id)
                print(
                    f"! assigned {subject.name} — left with "
                    f"{other.full_name if other else assignment.teacher_id}"
                )
            else:
                academics_service.assign_subject(
                    db,
                    school.id,
                    arm_id=arm.id,
                    subject_id=subject.id,
                    teacher_id=teacher.id,
                )
                print(f"  + assigned {subject.name} to {teacher.full_name}")

        if args.dry_run:
            db.rollback()
            print("\nDry run — nothing was written. Re-run without --dry-run to save.")
            return

        if not args.yes:
            answer = input(f"\nWrite this to {school.name}? Type 'yes' to continue: ")
            if answer.strip().lower() != "yes":
                db.rollback()
                print("Cancelled — nothing was written.")
                return

        db.commit()
        print("\nDone.")
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
