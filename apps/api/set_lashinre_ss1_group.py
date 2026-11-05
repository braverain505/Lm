"""Put La'ashinre Divine Academy's three SS 1 classes in one class group.

SS 1 Science, SS 1 Arts and SS 1 Commercial are separate classes — a pupil has
no stream field, so the stream lives in the class they are enrolled in — but the
school ranks them as one year group: "there should be positions in the entire
SS 1 and not based on science, arts or commercial."

Clearis expresses that with ``class_arms.group_name``: classes sharing a group
in the same session are ranked together, each pupil on the subjects they
actually offer. This script sets ``group_name = 'SS 1'`` on those three classes
and touches nothing else.

Run it from ``apps/api``:

    python set_lashinre_ss1_group.py --dry-run
    python set_lashinre_ss1_group.py --yes

It is idempotent: a class already in the right group is left alone, and the
exit code is 0 whether or not anything changed.
"""
from __future__ import annotations

import argparse
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal
from app.models import AcademicSession, ClassArm, School

GROUP_NAME = "SS 1"
CLASS_NAMES = ("SS 1 Science", "SS 1 Arts", "SS 1 Commercial")


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


def _find_school(db: Session, name: str) -> School:
    wanted = _school_key(name)
    matches = [s for s in db.scalars(select(School)) if _school_key(s.name) == wanted]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(repr(s.name) for s in matches)
        raise SystemExit(f"Several schools match {name!r}: {names}. Use --school exactly.")
    known = ", ".join(sorted(s.name for s in db.scalars(select(School))))
    raise SystemExit(f"School {name!r} not found here. Schools: {known or 'none'}.")


def _find_session(db: Session, school_id, name: str | None) -> AcademicSession:
    query = select(AcademicSession).where(AcademicSession.school_id == school_id)
    if name:
        session = db.scalar(
            query.where(func.lower(AcademicSession.name) == name.strip().lower())
        )
        if session is None:
            raise SystemExit(f"Session {name!r} not found for this school.")
        return session
    current = db.scalar(query.where(AcademicSession.is_current.is_(True)))
    if current is None:
        latest = db.scalar(query.order_by(AcademicSession.name.desc()))
        if latest is None:
            raise SystemExit("This school has no academic session.")
        print(f"! No session is flagged current — using the latest, {latest.name}.")
        return latest
    return current


def _find_arm(db: Session, school_id, session_id, name: str) -> ClassArm:
    """Case- and spacing-insensitive, because a class may have been typed as
    "SS1 Science" by hand."""
    wanted = re.sub(r"\s+", " ", name).strip().lower()
    arms = list(
        db.scalars(
            select(ClassArm).where(
                ClassArm.school_id == school_id,
                ClassArm.academic_session_id == session_id,
            )
        )
    )
    for arm in arms:
        if re.sub(r"\s+", " ", arm.name).strip().lower() == wanted:
            return arm
    known = ", ".join(sorted(repr(a.name) for a in arms)) or "none"
    raise SystemExit(f"Class {name!r} not found in this session. Classes: {known}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--school", default="La'ashinre Divine Academy, Jalingo")
    parser.add_argument("--session", default=None, help="defaults to the current session")
    parser.add_argument("--group", default=GROUP_NAME)
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    group = " ".join(args.group.split())
    if not group:
        raise SystemExit("--group cannot be blank")

    print(f"Database: {_masked_url()}")

    db = SessionLocal()
    try:
        school = _find_school(db, args.school)
        print(f"School:   {school.name} ({school.id})")
        session = _find_session(db, school.id, args.session)
        print(f"Session:  {session.name}{' (current)' if session.is_current else ''}")
        print(f"Group:    {group!r}\n")

        changed = 0
        for name in CLASS_NAMES:
            arm = _find_arm(db, school.id, session.id, name)
            before = arm.group_name
            if before == group:
                print(f"  = {arm.full_name:<18} already in {group!r}")
                continue
            print(f"  * {arm.full_name:<18} {before!r} -> {group!r}")
            arm.group_name = group
            changed += 1

        if not changed:
            print("\nNothing to do — every class is already in the group.")
            db.rollback()
            return

        print(f"\n{changed} class(es) will join {group!r}.")

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