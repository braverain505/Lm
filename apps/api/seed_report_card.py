"""One-off demo seeding for the premium report card (dev DB only)."""
import uuid
from datetime import date

from sqlalchemy import select, func

from app.config import settings
from app.core.database import SessionLocal
from app.models import (
    AcademicSession,
    ClassArm,
    PsychomotorAssessment,
    ResultComment,
    School,
    Staff,
    StudentAttendance,
    StudentEnrollment,
    Term,
    User,
)

SCHOOL_ID = uuid.UUID("5460081c-927d-4289-b731-b32dd5c28857")
SESSION_ID = uuid.UUID("5aee48c7-3c91-41d1-997b-b0812e28a2bd")
ARM_ID = uuid.UUID("f89f0e9a-18ec-4ec3-b0fe-cc4e59c8398f")
TERM_FIRST = uuid.UUID("96588117-91ca-42ab-bebe-8c7c0c5f18eb")
TERM_SECOND = uuid.UUID("37efeeb3-ec54-42b2-8aa6-010fd7bd996b")
TERM_THIRD = uuid.UUID("4bd7c1a8-46f5-4e74-a4b5-bc9cd800edc5")

PSYCHO_AREAS = [
    "Handwriting",
    "Art & Craft",
    "Physical Education",
    "Practical Science",
    "ICT Skills",
    "Music",
    "Life Skills",
]
LEVELS = ["Excellent", "Very Good", "Good", "Fair", "Poor"]


def main() -> None:
    db = SessionLocal()
    try:
        school = db.get(School, SCHOOL_ID)
        if school is not None:
            settings_ = dict(school.settings or {})
            settings_.setdefault("motto", "Knowledge, Character and Service")
            school.settings = settings_
            print("motto ->", settings_["motto"])

        # Term dates so attendance + next-term logic resolve.
        term_dates = {
            TERM_FIRST: (date(2025, 9, 15), date(2025, 12, 19)),
            TERM_SECOND: (date(2026, 1, 5), date(2026, 4, 3)),
            TERM_THIRD: (date(2026, 4, 20), date(2026, 7, 24)),
        }
        for tid, (sd, ed) in term_dates.items():
            t = db.get(Term, tid)
            if t is not None:
                t.start_date = sd
                t.end_date = ed
                print("term dates", t.name, sd, ed)

        # Homeroom teacher for JSS 1 A.
        arm = db.get(ClassArm, ARM_ID)
        teacher = db.scalar(select(Staff).where(Staff.school_id == SCHOOL_ID).limit(1))
        if arm is not None and teacher is not None:
            arm.class_teacher_id = teacher.id
            print("homeroom teacher ->", teacher.full_name)

        enrollments = list(
            db.scalars(
                select(StudentEnrollment).where(
                    StudentEnrollment.school_id == SCHOOL_ID,
                    StudentEnrollment.academic_session_id == SESSION_ID,
                    StudentEnrollment.class_arm_id == ARM_ID,
                )
            )
        )
        print("enrollments in arm:", len(enrollments))

        # Psychomotor rows (7 areas) per enrollment for the First Term.
        for env in enrollments:
            existing = db.scalar(
                select(func.count())
                .select_from(PsychomotorAssessment)
                .where(
                    PsychomotorAssessment.school_id == SCHOOL_ID,
                    PsychomotorAssessment.student_enrollment_id == env.id,
                    PsychomotorAssessment.term_id == TERM_FIRST,
                )
            )
            if existing:
                print("psycho exists for", env.id)
                continue
            for i, area in enumerate(PSYCHO_AREAS):
                db.add(
                    PsychomotorAssessment(
                        school_id=SCHOOL_ID,
                        student_enrollment_id=env.id,
                        term_id=TERM_FIRST,
                        learning_area=area,
                        achievement_level=LEVELS[i % len(LEVELS)],
                        sort_order=i,
                    )
                )
            print("seeded psycho for", env.id)

        # Attendance for Tolu across the First Term window (93% present).
        env = db.scalar(
            select(StudentEnrollment).where(
                StudentEnrollment.student_id
                == uuid.UUID("66f12434-9712-4f76-a6f4-d8c3991143bd"),
                StudentEnrollment.academic_session_id == SESSION_ID,
            )
        )
        if env is not None:
            existing = db.scalar(
                select(func.count())
                .select_from(StudentAttendance)
                .where(
                    StudentAttendance.school_id == SCHOOL_ID,
                    StudentAttendance.student_id == env.student_id,
                )
            )
            if not existing:
                from datetime import timedelta

                d = date(2025, 9, 15)
                end = date(2025, 12, 19)
                marked_by = db.scalar(select(User).limit(1))
                import random

                random.seed(7)
                while d <= end:
                    if d.weekday() < 5:  # weekdays only
                        status = (
                            "absent" if random.random() < 0.07 else "present"
                        )
                        db.add(
                            StudentAttendance(
                                school_id=SCHOOL_ID,
                                student_id=env.student_id,
                                date=d.isoformat(),
                                status=status,
                                marked_by=marked_by.id,
                            )
                        )
                    d += timedelta(days=1)
                print("seeded attendance for Tolu")

        # Principal comment for Tolu.
        existing_comment = db.scalar(
            select(ResultComment).where(
                ResultComment.school_id == SCHOOL_ID,
                ResultComment.student_enrollment_id == env.id,
                ResultComment.term_id == TERM_FIRST,
            )
        )
        if existing_comment is None and env is not None:
            db.add(
                ResultComment(
                    school_id=SCHOOL_ID,
                    student_enrollment_id=env.id,
                    term_id=TERM_FIRST,
                    body=(
                        "Tolu is a diligent and well-mannered student whose steady "
                        "improvement across all core subjects is a credit to his effort "
                        "and focus. We encourage him to keep this momentum in the "
                        "coming term."
                    ),
                    provider="seed",
                    model=None,
                    revision=1,
                    generated_by=None,
                )
            )
            print("seeded principal comment for Tolu")

        db.commit()
        print("DONE")
    finally:
        db.close()


if __name__ == "__main__":
    main()