"""Seed the database: WAEC grade scale + a fully-wired demo school.

Run after migrations:  python -m app.seed

Idempotent — safe to run repeatedly (skips anything already present).
Creates:
  * Global WAEC 9-point grade scale + bands.
  * Demo school "Brightfield Academy" with its own campus + role set.
  * Demo admin user (admin@brightfield.edu / Brightfield#2026) + membership.
  * 2025/2026 session, 3 terms, JSS1/SSS1 levels with A/B arms.
  * Course subjects, two teachers, six enrolled students.
  * Assessment components (CA1 20%, CA2 40%, Exam 40%) for First Term.
"""
from __future__ import annotations

import os
import random
import uuid
import warnings
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.database import SessionLocal
from .core.security import hash_password
from .models import (
    AcademicSession,
    AiUsage,
    AssessmentComponent,
    AttendanceSummary,
    AuditLog,
    ClassArm,
    FeeStructure,
    GradeBand,
    GradeScale,
    PlatformAnnouncement,
    PlatformNotification,
    PlatformRegion,
    PlatformSetting,
    PlatformTicket,
    Role,
    School,
    SchoolMembership,
    SchoolSubscription,
    Score,
    SubscriptionEvent,
    SubscriptionPlan,
    Staff,
    Student,
    StudentAttendance,
    StudentEnrollment,
    SubjectAssignment,
    Term,
    User,
)
from .schemas.fees import FeeStructureIn
from .services.academics_service import (
    add_offering,
    assign_subject,
    create_arm,
    create_session,
    create_subject,
    create_term,
)
from .services.fees_service import (
    create_fee_structure,
    create_invoice,
    get_student_fee_balance,
    record_payment,
)
from .services.people_service import (
    create_staff,
    create_staff_account,
    create_student,
    enroll_student,
)
from .services.platform_service import create_school_admin
from .services.results_service import save_scores, submit_arm_subject
from .services.subscription_service import (
    ensure_default_plans,
    get_active_subscription,
)
from .services.tenancy_service import create_school, provision_school_roles, sync_role_templates

DEMO_SCHOOL_SLUG = "brightfield-academy"
ADMIN_EMAIL = "admin@brightfield.edu"
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "Brightfield#2026")

# Warn if using default credentials in non-development environments
if ADMIN_PASSWORD == "Brightfield#2026" and not os.getenv("DEBUG", "").lower() == "true":
    warnings.warn(
        "WARNING: Using default seed password in production! "
        "Set SEED_ADMIN_PASSWORD environment variable.",
        RuntimeWarning,
        stacklevel=2,
    )

WAEC_BANDS = [
    ("A1", 90.0, 100.0, 1.0, "Excellent"),
    ("B2", 80.0, 89.99, 2.0, "Very Good"),
    ("B3", 70.0, 79.99, 3.0, "Good"),
    ("C4", 60.0, 69.99, 4.0, "Credit"),
    ("C5", 55.0, 59.99, 5.0, "Credit"),
    ("C6", 50.0, 54.99, 6.0, "Credit"),
    ("D7", 45.0, 49.99, 7.0, "Pass"),
    ("E8", 40.0, 44.99, 8.0, "Pass"),
    ("F9", 0.0, 39.99, 9.0, "Fail"),
]

SUBJECTS = [
    ("English Language", "ENG"),
    ("Mathematics", "MTH"),
    ("Basic Science", "BSC"),
    ("Basic Technology", "BTD"),
    ("Civic Education", "CIV"),
    ("Computer Science", "CSC"),
]


def seed_grade_scale(db, school_id) -> GradeScale:
    """Provision the school's default WAEC 9-point scale (A1 90–100 … F9 0–39).

    Grade lookup in the results engine resolves a scale by ``school_id`` +
    ``is_default``, so each tenant gets its own copy of the bands. Idempotent.
    """
    scale = db.scalar(
        select(GradeScale).where(
            GradeScale.school_id == school_id, GradeScale.is_default.is_(True)
        )
    )
    if scale is None:
        scale = GradeScale(school_id=school_id, name="WAEC", is_default=True)
        db.add(scale)
        db.flush()
        for letter, lo, hi, point, remark in WAEC_BANDS:
            db.add(
                GradeBand(
                    school_id=school_id,
                    grade_scale_id=scale.id,
                    letter=letter,
                    min_score=lo,
                    max_score=hi,
                    point=point,
                    remark=remark,
                )
            )
        db.flush()
    return scale


def seed_demo_school(db: Session) -> None:
    existing = db.scalar(select(School).where(School.slug == DEMO_SCHOOL_SLUG))
    if existing is not None:
        # Re-running the seed on an old database: backfill role permissions that
        # later phases added to the templates (keeps the demo school current),
        # and provision any new system roles.
        provision_school_roles(db, existing.id)
        sync_role_templates(db, existing.id)
        db.flush()
        return

    school = create_school(
        db, name="Brightfield Academy", school_type="secondary", slug=DEMO_SCHOOL_SLUG
    )

    # --- Demo admin -----------------------------------------------------------
    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    if admin is None:
        admin = User(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            full_name="Demo Admin",
        )
        db.add(admin)
        db.flush()
    super_role = db.scalar(
        select(Role).where(Role.school_id == school.id, Role.code == "super_admin")
    )
    if super_role is None:
        raise RuntimeError("super_admin role missing — provision roles first")
    if not db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.user_id == admin.id,
            SchoolMembership.school_id == school.id,
        )
    ):
        db.add(
            SchoolMembership(user_id=admin.id, school_id=school.id, role_id=super_role.id)
        )
        db.flush()

    # --- Session + terms --------------------------------------------------------
    scale = seed_grade_scale(db, school.id)
    session = create_session(
        db, school.id,
        name="2025/2026", start_date=date(2025, 9, 15), end_date=date(2026, 7, 24),
        is_current=True, grade_scale_id=scale.id,
    )
    term1 = create_term(db, school.id, session_id=session.id, term_no=1, name="First Term")
    create_term(db, school.id, session_id=session.id, term_no=2, name="Second Term")
    create_term(db, school.id, session_id=session.id, term_no=3, name="Third Term")
    term1.is_current = True
    db.flush()

    # --- Subjects + classes ----------------------------------------------------
    subjects = {
        name: create_subject(db, school.id, name=name, code=code)
        for name, code in SUBJECTS
    }

    # --- Classes + offerings ----------------------------------------------------
    arms = {}
    for name in ("JSS 1A", "JSS 1B", "SSS 1A", "SSS 1B"):
        arm = create_arm(db, school.id, session_id=session.id, name=name)
        arms[name] = arm
        for sub in subjects.values():
            add_offering(db, school.id, arm_id=arm.id, subject_id=sub.id)
    db.flush()

    # --- Teachers ----------------------------------------------------------------
    teachers = []
    for staff_no, name in [("TGH-001", "Ada Obi"), ("TGH-002", "Musa Ibrahim")]:
        teachers.append(
            create_staff(db, school.id, staff_no=staff_no, full_name=name, membership_type="teaching")
        )
    db.flush()

    # --- Students (enrolled into JSS 1A) ------------------------------------------
    demo_students = [
        ("Aisha", "Bello", "STU-001", "female"),
        ("David", "Okafor", "STU-002", "male"),
        ("Tolu", "Coker", "STU-003", "female"),
        ("Ibrahim", "Yusuf", "STU-004", "male"),
        ("Ngozi", "Umeh", "STU-005", "female"),
    ]
    jss1a = arms["JSS 1A"]
    for first, last, admission, gender in demo_students:
        student = create_student(
            db, school.id,
            admission_no=admission, first_name=first, last_name=last, gender=gender,
            state="Lagos" if admission in ("STU-002", "STU-003") else "Anambra",
        )
        enroll_student(
            db, school.id, student_id=student.id,
            arm_id=jss1a.id, session_id=session.id, enrolled_at=date(2025, 9, 1),
        )
    db.flush()

    # --- Assignments ---------------------------------------------------------------
    assign_subject(
        db, school.id,
        arm_id=jss1a.id, subject_id=subjects["English Language"].id, teacher_id=teachers[0].id,
    )
    assign_subject(
        db, school.id,
        arm_id=jss1a.id, subject_id=subjects["Mathematics"].id, teacher_id=teachers[1].id,
    )

    # --- Assessment components (First Term, school-wide) ---------------------------
    # Weights must sum to 100: CA1 20 + CA2 40 + Exam 40.
    for name, weight, sort_order in [("CA1", 20, 0), ("CA2", 40, 1), ("Exam", 40, 2)]:
        db.add(
            AssessmentComponent(
                school_id=school.id,
                term_id=term1.id,
                name=name,
                max_score=100.0,
                weight=weight,
                sort_order=sort_order,
                is_active=True,
            )
        )
    db.flush()


def _demo_admin(db: Session, school_id) -> User:
    """Return the demo school's super admin (created by the main seed)."""
    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    if admin is None:
        raise RuntimeError("demo admin missing — run the base seed first")
    return admin


def _demo_term(db: Session, school_id) -> Term:
    term = db.scalar(
        select(Term).where(Term.school_id == school_id, Term.is_current.is_(True))
    )
    if term is None:
        term = db.scalar(
            select(Term).where(Term.school_id == school_id).order_by(Term.term_no)
        )
    if term is None:
        raise RuntimeError("no term found for demo school")
    return term


def seed_demo_data(db: Session, school_id: uuid.UUID) -> None:
    """Populate the demo school with realistic (but clearly demo) records so the
    premium dashboard has real data to render: extra enrollments, scores across
    every assignment, one submitted result set, and ~3 weeks of attendance.

    Idempotent — re-running the seed never duplicates rows.
    """
    school = db.get(School, school_id)
    if school is None:
        return
    admin = _demo_admin(db, school_id)
    term = _demo_term(db, school_id)
    academic_session = db.scalar(
        select(AcademicSession).where(
            AcademicSession.school_id == school_id, AcademicSession.is_current.is_(True)
        )
    )

    # ---- Extra enrollments (SSS 1A) so the distribution chart has depth ------
    extra_students = [
        ("Chidi", "Eze", "STU-006", "male"),
        ("Fatima", "Bello", "STU-007", "female"),
        ("Kelechi", "Obi", "STU-008", "female"),
    ]
    sss1a = db.scalar(
        select(ClassArm).where(
            ClassArm.school_id == school_id,
            ClassArm.full_name == "SSS 1A",
        )
    )
    if sss1a is not None and academic_session is not None:
        for first, last, admission, gender in extra_students:
            existing = db.scalar(select(Student).where(Student.admission_no == admission))
            if existing is not None:
                continue
            student = create_student(
                db, school_id,
                admission_no=admission, first_name=first, last_name=last, gender=gender,
                state="Lagos",
            )
            enroll_student(
                db, school_id, student_id=student.id,
                arm_id=sss1a.id, session_id=academic_session.id, enrolled_at=date.today(),
            )
    db.flush()

    # ---- Scores for every assignment in the current term ----------------------
    has_scores = db.scalar(
        select(Score.id)
        .join(StudentEnrollment, StudentEnrollment.id == Score.student_enrollment_id)
        .where(StudentEnrollment.school_id == school_id)
        .limit(1)
    )
    if has_scores is None:
        components = list(
            db.scalars(
                select(AssessmentComponent)
                .where(
                    AssessmentComponent.school_id == school_id,
                    AssessmentComponent.term_id == term.id,
                    AssessmentComponent.is_active.is_(True),
                )
                .order_by(AssessmentComponent.sort_order)
            )
        )
        rng = random.Random(2026)  # deterministic demo data
        assignments = list(
            db.scalars(select(SubjectAssignment).where(SubjectAssignment.school_id == school_id))
        )
        enrollments = list(
            db.scalars(
                select(StudentEnrollment)
                .where(
                    StudentEnrollment.school_id == school_id,
                    StudentEnrollment.is_current.is_(True),
                )
            )
        )
        by_student = {env.student_id: env for env in enrollments}
        ability: dict[uuid.UUID, float] = {}
        for i, env in enumerate(enrollments):
            ability[env.student_id] = 0.55 + (i % 4) * 0.11 + rng.uniform(-0.02, 0.03)

        for idx, assignment in enumerate(assignments):
            entries = []
            for student_id, env in by_student.items():
                if env.class_arm_id != assignment.class_arm_id:
                    continue
                base = ability[student_id]
                subject_jitter = rng.uniform(-0.06, 0.06)
                scores = []
                for comp in components:
                    score = round(
                        max(0.0, min(100.0, (base + subject_jitter) * 100 + rng.uniform(-9, 9))), 1
                    )
                    scores.append({"assessment_component_id": comp.id, "score": score})
                entries.append({"student_enrollment_id": env.id, "scores": scores})
            if not entries:
                continue
            save_scores(
                db, school_id,
                arm_id=assignment.class_arm_id,
                subject_id=assignment.subject_id,
                term_id=term.id,
                entries=entries,
                actor_id=admin.id,
                is_superadmin=True,
            )
            # Submit roughly half the assignments so the approval queue and
            # readiness states show a realistic mix.
            if idx % 2 == 0:
                submit_arm_subject(
                    db, school_id,
                    arm_id=assignment.class_arm_id,
                    subject_id=assignment.subject_id,
                    term_id=term.id,
                    actor_id=admin.id,
                    is_superadmin=True,
                )
        db.flush()

    # ---- Attendance: ~3 weeks of school days for every enrolled student ------
    enrollments = list(
        db.scalars(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.school_id == school_id,
                StudentEnrollment.is_current.is_(True),
            )
        )
    )
    month = date.today().strftime("%Y-%m")
    days: list[date] = []
    cursor = date.today()
    while len(days) < 18:
        if cursor.weekday() < 5:  # school runs Mon–Fri
            days.append(cursor)
        cursor -= timedelta(days=1)
    rng = random.Random(2026)
    for env in enrollments:
        already = db.scalar(
            select(StudentAttendance.id)
            .where(StudentAttendance.student_id == env.student_id)
            .limit(1)
        )
        if already is not None:
            continue
        present = absent = late = 0
        for day in days:
            roll = rng.random()
            status = "present"
            if roll < 0.05:
                status = "absent"
                absent += 1
            elif roll < 0.11:
                status = "late"
                late += 1
            else:
                present += 1
            db.add(
                StudentAttendance(
                    school_id=school_id,
                    student_id=env.student_id,
                    date=day.isoformat(),
                    status=status,
                    marked_by=admin.id,
                    notes="demo data",
                )
            )
        total = present + absent + late
        db.add(
            AttendanceSummary(
                school_id=school_id,
                student_id=env.student_id,
                academic_session_id=academic_session.id if academic_session else None,
                month=month,
                total_days=total,
                present_days=present,
                absent_days=absent,
                late_days=late,
                excused_days=0,
                percentage=round(present / total * 100, 2) if total else 0.0,
            )
        )
    db.flush()

    # ---- Demo logins so the teacher + accountant dashboards are reachable -----
    sync_role_templates(db, school_id)  # grants ROLE_TEACHER the academics.view perm
    teacher_role = db.scalar(
        select(Role).where(Role.school_id == school_id, Role.code == "teacher")
    )
    accountant_role = db.scalar(
        select(Role).where(Role.school_id == school_id, Role.code == "accountant")
    )
    if teacher_role is not None:
        ada = db.scalar(
            select(Staff).where(Staff.school_id == school_id, Staff.staff_no == "TGH-001")
        )
        if ada is not None and ada.user_id is None:
            create_staff_account(
                db, school_id, ada.id,
                email="ada.obi@brightfield.edu",
                password="Teacher#2026",
                role_id=teacher_role.id,
            )
    if accountant_role is not None:
        acc = db.scalar(
            select(Staff).where(Staff.school_id == school_id, Staff.full_name == "Blessing Adeyemi")
        )
        if acc is None:
            acc = create_staff(
                db, school_id,
                staff_no="TGH-003", full_name="Blessing Adeyemi",
                membership_type="non_teaching",
            )
        if acc.user_id is None:
            create_staff_account(
                db, school_id, acc.id,
                email="accountant@brightfield.edu",
                password="Accountant#2026",
                role_id=accountant_role.id,
            )
    db.flush()

    # ---- Fee structures + invoices so the accountant dashboard has data -------
    has_structures = db.scalar(
        select(FeeStructure.id).where(FeeStructure.school_id == school_id).limit(1)
    )
    student_ids = list(
        {
            env.student_id
            for env in db.scalars(
                select(StudentEnrollment).where(
                    StudentEnrollment.school_id == school_id,
                    StudentEnrollment.is_current.is_(True),
                )
            )
        }
    )
    if has_structures is None:
        tuition = create_fee_structure(
            db, school_id,
            data=FeeStructureIn(
                name="Tuition (First Term)", description="Termly tuition fee",
                fee_type="tuition", amount=120_000, currency="NGN",
                billing_frequency="term", applicable_to="all",
                is_mandatory=True, allow_override=False,
            ),
            created_by=admin.id,
        )
        exam = create_fee_structure(
            db, school_id,
            data=FeeStructureIn(
                name="Examination Fee", description="CA + terminal exam charge",
                fee_type="examination", amount=15_000, currency="NGN",
                billing_frequency="term", applicable_to="all",
                is_mandatory=False, allow_override=False,
            ),
            created_by=admin.id,
        )
        db.flush()

        rng2 = random.Random(7)
        for i, student_id in enumerate(student_ids):
            inv_t = create_invoice(
                db, school_id=school_id, student_id=student_id,
                fee_structure_id=tuition.id, term_id=term.id,
                batch_number=f"BATCH-2026-{i + 1:02d}", issued_by=admin.id,
            )
            inv_e = create_invoice(
                db, school_id=school_id, student_id=student_id,
                fee_structure_id=exam.id, term_id=term.id,
                batch_number=f"BATCH-2026E-{i + 1:02d}", issued_by=admin.id,
            )
            if i == 0:
                # One student pays in full today → fills "Payments recorded today".
                record_payment(
                    db, invoice_id=inv_t.id, student_id=student_id,
                    amount=float(inv_t.total_amount), payment_method="bank_transfer",
                    school_id=school_id, recorded_by=admin.id,
                )
                record_payment(
                    db, invoice_id=inv_e.id, student_id=student_id,
                    amount=float(inv_e.total_amount), payment_method="bank_transfer",
                    school_id=school_id, recorded_by=admin.id,
                )
            elif rng2.random() < 0.4:
                # Fully paid a while ago.
                record_payment(
                    db, invoice_id=inv_t.id, student_id=student_id,
                    amount=float(inv_t.total_amount), payment_method="bank_transfer",
                    school_id=school_id, recorded_by=admin.id,
                )
                record_payment(
                    db, invoice_id=inv_e.id, student_id=student_id,
                    amount=float(inv_e.total_amount), payment_method="bank_transfer",
                    school_id=school_id, recorded_by=admin.id,
                )
                past = (date.today() - timedelta(days=int(rng2.uniform(4, 18)))).isoformat()
                inv_t.paid_date = past
                inv_e.paid_date = past
            elif rng2.random() < 0.5:
                # Partial payment on tuition only.
                record_payment(
                    db, invoice_id=inv_t.id, student_id=student_id,
                    amount=float(inv_t.total_amount) * 0.5, payment_method="cash",
                    school_id=school_id, recorded_by=admin.id,
                )
            # Remaining students stay outstanding.
        db.flush()

    # Denormalized balances so the accountant dashboard's outstanding KPI
    # reflects the seeded invoices. Upsert-style and idempotent.
    for student_id in student_ids:
        get_student_fee_balance(db, student_id, school_id)
    db.flush()


PLATFORM_ADMIN_EMAIL = "admin@lumo.app"
PLATFORM_ADMIN_PASSWORD = os.getenv("SEED_PLATFORM_PASSWORD", "Lumo#2026")

# Warn if using default platform credentials in non-development environments
if PLATFORM_ADMIN_PASSWORD == "Lumo#2026" and not os.getenv("DEBUG", "").lower() == "true":
    warnings.warn(
        "WARNING: Using default platform seed password in production! "
        "Set SEED_PLATFORM_PASSWORD environment variable.",
        RuntimeWarning,
        stacklevel=2,
    )


# --- Super Admin demo data --------------------------------------------------
# Clearly demo/sample data for the platform command center. Every school created
# here is a fictional tenant so the owner can explore the dashboard with real
# shapes and trends before real customers sign up.

NIGERIA_STATES = [
    "Abuja (FCT)", "Lagos", "Kano", "Rivers", "Kaduna", "Oyo", "Enugu",
    "Plateau", "Ogun", "Anambra", "Bauchi", "Imo",
]

PLATFORM_DEMO_SCHOOLS = [
    {
        "name": "Oasis International School",
        "slug": "oasis-international",
        "school_type": "secondary",
        "state": "Lagos",
        "established_year": 2010,
        "admin_full_name": "Amaka Eze",
        "admin_email": "admin@oasis.edu.ng",
        "plan": "enterprise",
        "status": "active",
        "students": 34,
        "created_days_ago": 420,
    },
    {
        "name": "EIS Jalingo",
        "slug": "eis-jalingo",
        "school_type": "secondary",
        "state": "Plateau",
        "established_year": 2014,
        "admin_full_name": "Musa Ibrahim",
        "admin_email": "admin@eisjalingo.ng",
        "plan": "professional",
        "status": "active",
        "students": 22,
        "created_days_ago": 360,
    },
    {
        "name": "Royal College Kaduna",
        "slug": "royal-college-kaduna",
        "school_type": "secondary",
        "state": "Kaduna",
        "established_year": 2018,
        "admin_full_name": "Hauwa Suleiman",
        "admin_email": "admin@royalcollege.ng",
        "plan": "professional",
        "status": "active",
        "students": 18,
        "created_days_ago": 300,
    },
    {
        "name": "Greenfield Montessori",
        "slug": "greenfield-montessori",
        "school_type": "primary",
        "state": "Ogun",
        "established_year": 2016,
        "admin_full_name": "Tunde Bakare",
        "admin_email": "admin@greenfield.edu.ng",
        "plan": "starter",
        "status": "active",
        "students": 15,
        "created_days_ago": 210,
    },
    {
        "name": "Gateway Comprehensive",
        "slug": "gateway-comprehensive",
        "school_type": "secondary",
        "state": "Rivers",
        "established_year": 2019,
        "admin_full_name": "Blessing George",
        "admin_email": "admin@gatewaycomp.ng",
        "plan": "starter",
        "status": "past_due",
        "students": 11,
        "created_days_ago": 150,
    },
    {
        "name": "Harmony Private Academy",
        "slug": "harmony-private-academy",
        "school_type": "secondary",
        "state": "Anambra",
        "established_year": 2022,
        "admin_full_name": "Chioma Nwosu",
        "admin_email": "admin@harmonyacademy.ng",
        "plan": "professional",
        "status": "trial",
        "students": 7,
        "created_days_ago": 9,
    },
    {
        "name": "Summit Hill College",
        "slug": "summit-hill-college",
        "school_type": "secondary",
        "state": "Enugu",
        "established_year": 2023,
        "admin_full_name": "Ifeanyi Okonkwo",
        "admin_email": "admin@summithill.ng",
        "plan": "starter",
        "status": "expired",
        "students": 0,
        "created_days_ago": 200,
    },
    {
        "name": "Apex Foundation School",
        "slug": "apex-foundation",
        "school_type": "primary",
        "state": "Bauchi",
        "established_year": 2021,
        "admin_full_name": "Fatima Bello",
        "admin_email": "admin@apexfoundation.ng",
        "plan": "professional",
        "status": "trial",
        "students": 5,
        "created_days_ago": 5,
    },
]

AI_FEATURE_CODES = ["ai.result.comment", "ai.lesson.plan", "ai.question.bank", "ai.copilot"]
AI_MODELS = ["gpt-4o-mini", "gpt-4o"]
GIRL_NAMES = ["Aisha", "Zainab", "Chidera", "Mary", "Blessing", "Halima", "Ese", "Ngozi"]
BOY_NAMES = ["Ibrahim", "Chukwuemeka", "Tunde", "Musa", "Kelechi", "Emeka", "Samuel", "Yusuf"]


def seed_platform_regions(db: Session) -> None:
    """Nigeria state catalog (idempotent). Extend to other countries freely."""
    existing = {(r.country_code, r.state_code) for r in db.scalars(select(PlatformRegion)).all()}
    if existing:
        return
    for order, state in enumerate(NIGERIA_STATES):
        db.add(
            PlatformRegion(
                country_code="NG",
                country_name="Nigeria",
                state_code=state.upper()[:24],
                state_name=state,
                sort_order=order,
            )
        )
    db.flush()


def seed_platform_settings(db: Session) -> None:
    """Platform-wide defaults (idempotent)."""
    defaults = {
        "ai.credit_price": {"value": 0.001},
        "ai.default_model": {"value": "gpt-4o-mini"},
        "platform.owner_email": {"value": PLATFORM_ADMIN_EMAIL},
        "platform.currency": {"value": "USD"},
        "platform.billing_enabled": {"value": True},
        "platform.maintenance_mode": {"value": False},
        "platform.storage_used_pct": {"value": 42},
        "platform.uptime_pct": {"value": 99.98},
    }
    for key, data in defaults.items():
        if db.get(PlatformSetting, key) is None:
            db.add(PlatformSetting(key=key, value=data["value"]))
    db.flush()


def seed_platform_school(
    db: Session,
    definition: dict,
    platform_admin: User,
    plan_by_code: dict[str, SubscriptionPlan],
) -> School:
    """Create one fictional demo tenant: school, admin account, students,
    subscription state, and billing events. Idempotent by slug."""
    school = db.scalar(select(School).where(School.slug == definition["slug"]))
    if school is None:
        school = create_school(
            db,
            name=definition["name"],
            school_type=definition["school_type"],
            slug=definition["slug"],
        )
        school.state = definition["state"]
        school.country = "NG"
        school.established_year = definition["established_year"]
        school.phone = "0800 000 0000"
        school.email = definition["admin_email"]
        school.created_at = datetime.utcnow() - timedelta(days=definition["created_days_ago"])
        db.flush()
        create_school_admin(
            db,
            school.id,
            full_name=definition["admin_full_name"],
            email=definition["admin_email"],
            password="School#2026",
        )
    else:
        school.state = definition["state"]

    # Subscriptions: real plan for paying/trial schools; expired school left on
    # the default trial plan (its trial simply lapsed). ``create_school`` already
    # provisioned a trial, so we update that row in place (idempotent by slug).
    plan = plan_by_code.get(definition["plan"])
    status = definition["status"]
    sub = get_active_subscription(db, school.id)
    has_events = (
        db.scalar(select(SubscriptionEvent.id).where(SubscriptionEvent.school_id == school.id).limit(1))
        is not None
    )
    if plan is not None and status in ("active", "past_due", "trial", "expired") and sub is not None:
        sub.plan_id = plan.id
        sub.status = status
        sub.ai_credits_total = plan.features.get("ai_credits", 0)
        sub.ends_at = datetime.utcnow() + (
            timedelta(days=14) if status == "trial" else timedelta(days=30)
        )
        if status == "expired":
            sub.ends_at = datetime.utcnow() - timedelta(days=15)
        db.flush()
        if not has_events:
            if status in ("active", "past_due"):
                # Monthly billing history so the revenue chart has shape.
                for months_back in range(1, 9):
                    if months_back > definition["created_days_ago"] // 30:
                        break
                    event_date = datetime.utcnow() - timedelta(days=months_back * 30)
                    db.add(
                        SubscriptionEvent(
                            school_id=school.id,
                            subscription_id=sub.id,
                            event_type="payment_succeeded",
                            status="success",
                            amount=float(plan.price_monthly_usd),
                            created_at=event_date,
                            meta={"plan": plan.code, "period": event_date.strftime("%Y-%m")},
                        )
                    )
            if status == "past_due":
                db.add(
                    SubscriptionEvent(
                        school_id=school.id,
                        subscription_id=sub.id,
                        event_type="payment_failed",
                        status="failed",
                        amount=float(plan.price_monthly_usd),
                        meta={"plan": plan.code},
                    )
                )
            if status == "trial":
                db.add(
                    SubscriptionEvent(
                        school_id=school.id,
                        subscription_id=sub.id,
                        event_type="trial_started",
                        status="success",
                        amount=0,
                        meta={"plan": "trial", "days": 14},
                    )
                )
    db.flush()

    # A handful of students so headcount KPIs are meaningful.
    rng = random.Random(hash(definition["slug"]) % 2**32)
    use_girls = rng.random() < 0.5
    first_names = GIRL_NAMES if use_girls else BOY_NAMES
    gender = "F" if use_girls else "M"
    existing_admissions = set(
        db.scalars(select(Student.admission_no).where(Student.school_id == school.id)).all()
    )
    for i in range(definition["students"]):
        admission_no = f"{definition['slug'][:3].upper()}-2026-{i + 1:03d}"
        if admission_no in existing_admissions:
            continue
        existing_admissions.add(admission_no)
        db.add(
            Student(
                school_id=school.id,
                admission_no=admission_no,
                first_name=first_names[i % len(first_names)],
                last_name="Demo",
                gender=gender,
                date_of_birth=date(2011, 1, 1) - timedelta(days=i),
                state=definition["state"],
                lga=definition["state"],
            )
        )
    db.flush()
    return school


def seed_platform_demo(db: Session, platform_admin: User) -> None:
    """Seed everything the Super Admin command center renders: regions, plans,
    demo schools, subscriptions + billing events, AI usage, support tickets,
    platform notifications, announcements, and the audit trail."""
    seed_platform_regions(db)
    seed_platform_settings(db)
    ensure_default_plans(db)

    plans = {p.code: p for p in db.scalars(select(SubscriptionPlan)).all()}
    schools: dict[str, School] = {}
    for definition in PLATFORM_DEMO_SCHOOLS:
        school = seed_platform_school(db, definition, platform_admin, plans)
        schools[definition["slug"]] = school

    # AI usage across the last 12 months for every demo tenant.
    rng = random.Random(2026)
    user_by_school: dict[uuid.UUID, uuid.UUID | None] = {}
    for school in schools.values():
        user_by_school[school.id] = db.scalar(
            select(SchoolMembership.user_id).where(SchoolMembership.school_id == school.id)
        )
    for school in schools.values():
        for _ in range(rng.randint(20, 60)):
            feature = AI_FEATURE_CODES[rng.randrange(len(AI_FEATURE_CODES))]
            tokens = rng.randint(200, 4000)
            created = datetime.utcnow() - timedelta(
                days=rng.uniform(0, 360), hours=rng.uniform(0, 12)
            )
            db.add(
                AiUsage(
                    school_id=school.id,
                    user_id=user_by_school.get(school.id),
                    feature=feature,
                    provider="openai",
                    model=AI_MODELS[rng.randrange(len(AI_MODELS))],
                    tokens_in=int(tokens * 0.4),
                    tokens_out=int(tokens * 0.6),
                    cost=round(tokens * 0.000004, 6),
                    latency_ms=rng.randint(400, 2500),
                    created_at=created,
                )
            )
    db.flush()

    # Support tickets.
    if db.scalar(select(PlatformTicket.id).limit(1)) is None:
        brightfield = db.scalar(select(School).where(School.slug == DEMO_SCHOOL_SLUG))
        brightfield_id = brightfield.id if brightfield else None
        tickets = [
            {
                "school_id": schools.get("oasis-international").id if "oasis-international" in schools else brightfield_id,
                "subject": "AI credits not resetting this month",
                "description": "Our credits meter still shows the previous month's usage.",
                "category": "billing",
                "severity": "high",
                "status": "in_progress",
                "created_by": platform_admin.id,
            },
            {
                "school_id": schools.get("greenfield-montessori").id if "greenfield-montessori" in schools else brightfield_id,
                "subject": "Cannot upload student list",
                "description": "The CSV import keeps failing on the phone column.",
                "category": "technical",
                "severity": "medium",
                "status": "open",
                "created_by": platform_admin.id,
            },
            {
                "school_id": schools.get("gateway-comprehensive").id if "gateway-comprehensive" in schools else brightfield_id,
                "subject": "Invoice PDF shows wrong term",
                "description": "Examination fee invoices print the previous term.",
                "category": "bug",
                "severity": "low",
                "status": "resolved",
                "created_by": platform_admin.id,
                "resolution_note": "Fixed in v0.2.1; regenerated the affected batch.",
            },
            {
                "school_id": None,
                "subject": "Feature request: bulk result publishing",
                "description": "Several schools want to publish all arms at once.",
                "category": "feature",
                "severity": "low",
                "status": "open",
                "created_by": platform_admin.id,
            },
        ]
        for t in tickets:
            db.add(PlatformTicket(**t))
    db.flush()

    # Platform notifications + announcements.
    if db.scalar(select(PlatformNotification.id).limit(1)) is None:
        for note in [
            {
                "title": "3 schools started trials this week",
                "body": "Two new trials plus one upgraded from an expired plan.",
                "severity": "info",
                "category": "growth",
            },
            {
                "title": "Gateway Comprehensive invoice failed",
                "body": "Payment failed; subscription is now past due.",
                "severity": "warning",
                "category": "billing",
            },
            {
                "title": "AI spend up 12% month over month",
                "body": "Driven by lesson-plan generation on the Enterprise plan.",
                "severity": "info",
                "category": "ai",
            },
        ]:
            db.add(PlatformNotification(**note))
    db.flush()

    if db.scalar(select(PlatformAnnouncement.id).limit(1)) is None:
        db.add(
            PlatformAnnouncement(
                title="Scheduled maintenance Sunday 02:00–03:00 WAT",
                body="The platform will be briefly unavailable for a storage upgrade.",
                audience="all_schools",
                severity="warning",
                created_by=platform_admin.id,
            )
        )
        db.add(
            PlatformAnnouncement(
                title="New: bulk result publishing is now available",
                body="Admins can publish every arm of a subject in one click.",
                audience="all_schools",
                severity="info",
                created_by=platform_admin.id,
            )
        )
    db.flush()

    # Audit trail so the audit log page isn't empty.
    if db.scalar(select(AuditLog.id).limit(1)) is None:
        for i, school in enumerate(list(schools.values()) + [db.scalar(select(School).where(School.slug == DEMO_SCHOOL_SLUG))]):
            if school is None:
                continue
            db.add(
                AuditLog(
                    school_id=school.id,
                    user_id=platform_admin.id,
                    action="create",
                    entity_type="school",
                    entity_id=str(school.id),
                    details=f"Registered {school.name}",
                )
            )
    db.flush()


def ensure_platform_admin(db: Session) -> User:
    """Lumo's own platform admin (``is_superadmin``) — the account that runs the
    global admin dashboard and flips premium AI on for paying schools."""
    admin = db.scalar(select(User).where(User.email == PLATFORM_ADMIN_EMAIL))
    if admin is None:
        admin = User(
            email=PLATFORM_ADMIN_EMAIL,
            password_hash=hash_password(PLATFORM_ADMIN_PASSWORD),
            full_name="Lumo Platform Admin",
            is_superadmin=True,
        )
        db.add(admin)
        db.flush()
    else:
        admin.is_superadmin = True
        if os.getenv("SEED_PLATFORM_PASSWORD"):
            admin.password_hash = hash_password(PLATFORM_ADMIN_PASSWORD)
    return admin


def main() -> None:
    db = SessionLocal()
    try:
        platform_admin = ensure_platform_admin(db)
        seed_platform_demo(db, platform_admin)
        seed_demo_school(db)
        school = db.scalar(
            select(School).where(School.slug == DEMO_SCHOOL_SLUG)
        )
        if school is not None:
            seed_demo_data(db, school.id)
        db.commit()
        print(f"Seeded WAEC grade scale + demo school '{DEMO_SCHOOL_SLUG}'")
        print(f"  Admin:      {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
        print("  Teacher:    ada.obi@brightfield.edu / Teacher#2026")
        print("  Accountant: accountant@brightfield.edu / Accountant#2026")
        print(f"  Platform:   {PLATFORM_ADMIN_EMAIL} / {PLATFORM_ADMIN_PASSWORD}")
        print(f"  Demo tenants: {len(PLATFORM_DEMO_SCHOOLS)} platform schools seeded")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()