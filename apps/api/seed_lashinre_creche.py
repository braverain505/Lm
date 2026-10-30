"""Add the Creche register handed in for La'ashinre Divine Academy.

One-off data load, in the same spirit as ``seed_lashinre_classes.py``. Run it
from ``apps/api``:

    DATABASE_URL='postgresql://user:pass@host/db' python seed_lashinre_creche.py --dry-run
    DATABASE_URL='postgresql://user:pass@host/db' python seed_lashinre_creche.py --yes

It finds the school by name and its current session, then:

  * ensures the teacher exists as teaching staff (continuing the school's
    ``<CODE>-T-###`` sequence);
  * ensures the "Creche" class exists in the session, with that teacher
    attached as its form teacher;
  * creates every pupil on the register who is not there yet and enrols them.

The teacher was written "MR. MUSTAPHA JANET JENNIFER"; the honorific is
dropped and the name is stored title case, like the other registers. The
register gives no sex for the pupils, so it is inferred from the names
(``--gender-report`` prints the result; correct any in the app). ``other``
means the name matched nothing. Names are stored in the order they were
written and split at the first and last token, so a full name reads exactly as
the register does.

Admission numbers continue the school's ``<CODE>-S-###`` sequence. It is
idempotent: a pupil or teacher already present is kept as they are, and a pupil
already enrolled in another class this session is left there with a warning.
Nothing is committed on ``--dry-run``.
"""
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import SessionLocal
from app.models import (
    AcademicSession,
    ClassArm,
    School,
    Staff,
    Student,
    StudentEnrollment,
)
from app.services import academics_service, people_service

SCHOOL_NAME = "La'ashinre Divine Academy, Jalingo"
CLASS_NAME = "Creche"
TEACHER_NAME = "Mustapha Janet Jennifer"
MAX_STUDENT_NUMBER = 900


@dataclass(frozen=True)
class Pupil:
    first: str
    middle: str | None
    last: str

    @property
    def key(self) -> str:
        return _key(" ".join(p for p in (self.first, self.middle, self.last) if p))


# The register in the order it was given: (first, middle, last).
PUPILS: tuple[Pupil, ...] = (
    Pupil("Maiwada", None, "Biliyaminu"),
    Pupil("Adzufeh", "Joy", "Atsah"),
    Pupil("Godwin", "Chidiebube", "Michael"),
    Pupil("Godwin", "Chinemere", "Michele"),
    Pupil("Benjamin", None, "Godwin"),
    Pupil("Samaila", None, "Ketura"),
    Pupil("Ezekiel", None, "Keziah"),
    Pupil("Bakari", None, "Nkotto"),
    Pupil("Isaac", None, "Purity"),
    Pupil("Dauda", "Wusa", "Lovely"),
    Pupil("Rufai", None, "Murtala"),
    Pupil("Nuru", "Musa", "Idris"),
    Pupil("Bakanza", None, "Joseph"),
    Pupil("Saminu", "Mading", "Kodanakwa"),
    Pupil("Orajiaka", "Munachimse", "Rebecca"),
)

FEMALE_NAMES = {
    "abigail", "aisha", "alheri", "amina", "anita", "anna", "annah",
    "appreciate", "beatrice", "blessing", "christabel", "clara", "comfort",
    "confidence", "debby", "deborah", "delight", "dorathy", "doris",
    "esther", "eunice", "favour", "fidausi", "glory", "godiya", "grace",
    "hajara", "hope", "isadora", "jecintha", "joan", "joy", "joyce",
    "ketura", "keziah", "lovely", "magdalene", "mary", "mercy", "michele",
    "miracle", "mufida", "munachimse", "nancy", "patience", "peace",
    "pheemila", "precious", "purity", "rebecca", "rejoice", "remember",
    "samantha", "saratu", "sylvia", "tabitha", "testimony", "theresa",
    "umaima", "victoria",
}
MALE_NAMES = {
    "aaron", "abednego", "abubakar", "abraham", "alpha", "amos", "ananias",
    "andrew", "bakanza", "benedict", "barnabas", "benjamin", "biliyaminu",
    "bright", "calistus", "clement", "cyprian", "daniel", "danladi", "david",
    "demian", "denison", "elijah", "emmanuel", "enoch", "ezekiel", "ezra",
    "geoffrey", "george", "godfrey", "godwin", "ibrahim", "idagu", "idris",
    "isaac", "ishaya", "isiyaka", "ismaila", "israel", "jason", "jeremiah",
    "jerry", "jethro", "joel", "john", "jonah", "joseph", "joshua", "justus",
    "kelvin", "lazarus", "markus", "mathias", "michael", "moses", "murtala",
    "musa", "nuhu", "nuru", "obadiah", "patrick", "paul", "peter", "philip",
    "philemon", "prosper", "rashid", "richard", "rufai", "samaila", "samuel",
    "saminu", "seth", "sila", "simon", "solomon", "stephen", "suleiman",
    "sylvanus", "thomson", "timothy", "titus", "victor", "wisdom", "sarki",
}


def _key(value: str) -> str:
    """Fold a name for comparison: case, punctuation and padding stop mattering."""
    return " ".join(re.findall(r"[a-z0-9']+", value.lower()))


def _school_key(value: str) -> str:
    """Compare school names ignoring case, spaces and punctuation."""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _full_name(pupil: Pupil) -> str:
    return " ".join(p for p in (pupil.first, pupil.middle, pupil.last) if p)


def _infer_gender(pupil: Pupil) -> str:
    """Best guess from the register's names; "other" when nothing matches."""
    tokens = {token.strip(".'").lower() for token in _full_name(pupil).split(" ")}
    if tokens & FEMALE_NAMES:
        return "female"
    if tokens & MALE_NAMES:
        return "male"
    return "other"


def _masked_url() -> str:
    url = settings.database_url
    if "@" not in url:
        return url
    scheme, rest = url.split("://", 1) if "://" in url else ("", url)
    credentials, host = rest.rsplit("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host}" if scheme else f"{user}:***@{host}"


def _code(name: str) -> str:
    """A short, upper-case code for a school name: 'El Gibbor' -> 'ELG'."""
    initials = "".join(part[0] for part in re.split(r"[^A-Za-z0-9]+", name) if part)
    return (initials or name)[:3].upper()


def _next_free(used: set[str], prefix: str) -> str:
    number = 1
    while f"{prefix}{number:03d}" in used:
        number += 1
        if number > MAX_STUDENT_NUMBER:
            raise SystemExit(f"No free number left under {prefix}.")
    value = f"{prefix}{number:03d}"
    used.add(value)
    return value


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


def _ensure_teacher(db: Session, school: School, name: str) -> Staff:
    existing = list(
        db.scalars(
            select(Staff).where(
                Staff.school_id == school.id, Staff.is_deleted.is_(False)
            )
        )
    )
    for staff in existing:
        if _key(staff.full_name) == _key(name):
            print(f"  = teacher  {staff.full_name} ({staff.staff_no}) — kept")
            return staff
    used = set(db.scalars(select(Staff.staff_no).where(Staff.school_id == school.id)))
    staff_no = _next_free(used, f"{_code(school.name)}-T-")
    staff = people_service.create_staff(
        db,
        school.id,
        staff_no=staff_no,
        full_name=name,
        membership_type="teaching",
    )
    print(f"  + teacher  {staff.full_name} ({staff_no})")
    return staff


def _ensure_class(
    db: Session, school: School, session: AcademicSession, teacher: Staff
) -> ClassArm:
    arm = db.scalar(
        select(ClassArm).where(
            ClassArm.school_id == school.id,
            ClassArm.academic_session_id == session.id,
            func.lower(func.trim(ClassArm.name)) == CLASS_NAME.lower(),
        )
    )
    if arm is not None:
        if arm.class_teacher_id is None:
            arm.class_teacher_id = teacher.id
            db.flush()
            print(f"  = class    {arm.full_name} — form teacher attached")
        elif arm.class_teacher_id != teacher.id:
            current = db.get(Staff, arm.class_teacher_id)
            print(
                f"! class    {arm.full_name} keeps its form teacher "
                f"{current.full_name if current else arm.class_teacher_id} — "
                f"{teacher.full_name} not attached"
            )
        else:
            print(f"  = class    {arm.full_name} — kept")
        return arm
    arm = academics_service.create_arm(
        db,
        school.id,
        session_id=session.id,
        name=CLASS_NAME,
        class_teacher_id=teacher.id,
    )
    print(f"  + class    {CLASS_NAME} (form teacher {teacher.full_name})")
    return arm


def _load_pupils(
    db: Session, school: School, session: AcademicSession, arm: ClassArm
) -> tuple[int, int, list[tuple[str, str]], list[str]]:
    existing = list(
        db.scalars(
            select(Student).where(
                Student.school_id == school.id, Student.is_deleted.is_(False)
            )
        )
    )
    by_name: dict[str, list[Student]] = defaultdict(list)
    for student in existing:
        by_name[_key(student.full_name)].append(student)

    used_numbers = set(
        db.scalars(select(Student.admission_no).where(Student.school_id == school.id))
    )
    prefix = f"{_code(school.name)}-S-"
    consumed: Counter[str] = Counter()
    created = 0
    newly_enrolled = 0
    warnings: list[str] = []
    gender_report: list[tuple[str, str]] = []

    for pupil in PUPILS:
        written = _full_name(pupil)
        key = pupil.key
        seen = consumed[key]
        matches = by_name[key]
        if seen < len(matches):
            student = matches[seen]
            print(f"  = pupil    {student.full_name} ({student.admission_no}) — kept")
        else:
            admission_no = _next_free(used_numbers, prefix)
            student = people_service.create_student(
                db,
                school.id,
                admission_no=admission_no,
                first_name=pupil.first,
                middle_name=pupil.middle,
                last_name=pupil.last,
                gender=_infer_gender(pupil),
            )
            by_name[key].append(student)
            created += 1
            print(f"  + pupil    {written} ({admission_no})")
            gender_report.append((written, student.gender))
        consumed[key] += 1

        enrollment = db.scalar(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id == student.id,
                StudentEnrollment.academic_session_id == session.id,
            )
        )
        if enrollment is None:
            people_service.enroll_student(
                db,
                school.id,
                student_id=student.id,
                arm_id=arm.id,
                session_id=session.id,
            )
            newly_enrolled += 1
        elif enrollment.class_arm_id != arm.id:
            current_arm = db.get(ClassArm, enrollment.class_arm_id)
            warnings.append(
                f"{student.full_name} is already in "
                f"{current_arm.full_name if current_arm else 'another class'} this "
                f"session — left there."
            )

    return created, newly_enrolled, gender_report, warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add La'ashinre Divine Academy's Creche register."
    )
    parser.add_argument("--school", default=SCHOOL_NAME, help="school name to target")
    parser.add_argument("--class", dest="class_name", default=CLASS_NAME, help="class to load")
    parser.add_argument("--teacher", default=TEACHER_NAME, help="form teacher to attach")
    parser.add_argument(
        "--session", default=None, help="academic session name (default: current)"
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()

    print(f"Database: {_masked_url()}")

    db = SessionLocal()
    try:
        school = _find_school(db, args.school)
        print(f"School:   {school.name} ({school.id})")
        session = _find_session(db, school.id, args.session)
        print(f"Session:  {session.name}{' (current)' if session.is_current else ''}\n")

        teacher = _ensure_teacher(db, school, args.teacher)
        arm = _ensure_class(db, school, session, teacher)
        created, enrolled, gender_report, warnings = _load_pupils(
            db, school, session, arm
        )

        print("\nSummary")
        print(f"  pupils:    {created} new")
        print(f"  enrolled:  {enrolled} newly enrolled")

        if gender_report:
            print("\nSex inferred from names (correct any in the app):")
            for full_name, gender in gender_report:
                print(f"  {full_name:<32} {gender}")

        if warnings:
            print("\nPupils left where they were:")
            for line in warnings:
                print(f"  - {line}")

        if not created and not enrolled:
            print("\nNothing to do.")

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
