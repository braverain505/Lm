"""People: staff, students, enrollments, guardians."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..core import security
from ..core.errors import ConflictError, NotFoundError, ValidationError
from ..models import (
    AcademicSession,
    ClassArm,
    Guardian,
    Role,
    SchoolMembership,
    Staff,
    Student,
    StudentEnrollment,
    StudentGuardian,
    SubjectAssignment,
    User,
)
from ..schemas.people import StaffOut
from .academics_service import get_arm, get_session


# --- Staff --------------------------------------------------------------------
def list_staff(db: Session, school_id: uuid.UUID, membership_type: str | None = None) -> list[Staff]:
    stmt = select(Staff).where(
        Staff.school_id == school_id, Staff.is_deleted.is_(False)
    )
    if membership_type:
        stmt = stmt.where(Staff.membership_type == membership_type)
    return list(db.scalars(stmt.order_by(Staff.full_name)))


def serialize_staff_list(
    db: Session, school_id: uuid.UUID, rows: list[Staff]
) -> list[StaffOut]:
    """Attach login/account info (email + role in this school) to staff rows."""
    user_ids = [s.user_id for s in rows if s.user_id is not None]
    users: dict = {}
    memberships: dict = {}
    roles: dict = {}
    if user_ids:
        users = {
            u.id: u
            for u in db.scalars(select(User).where(User.id.in_(user_ids)))
        }
        memberships = {
            m.user_id: m
            for m in db.scalars(
                select(SchoolMembership).where(
                    SchoolMembership.user_id.in_(user_ids),
                    SchoolMembership.school_id == school_id,
                )
            )
        }
        role_ids = [m.role_id for m in memberships.values()]
        if role_ids:
            roles = {
                r.id: r
                for r in db.scalars(select(Role).where(Role.id.in_(role_ids)))
            }
    out: list[StaffOut] = []
    for s in rows:
        user = users.get(s.user_id) if s.user_id is not None else None
        membership = memberships.get(s.user_id) if s.user_id is not None else None
        role = roles.get(membership.role_id) if membership is not None else None
        out.append(
            StaffOut(
                id=s.id,
                staff_no=s.staff_no,
                membership_type=s.membership_type,
                full_name=s.full_name,
                gender=s.gender,
                phone=s.phone,
                email=s.email,
                joined_date=s.joined_date,
                employment_status=s.employment_status,
                has_account=s.user_id is not None,
                account_email=user.email if user is not None else None,
                account_role_id=membership.role_id if membership is not None else None,
                account_role_name=role.name if role is not None else None,
            )
        )
    return out


def staff_to_out(db: Session, school_id: uuid.UUID, staff: Staff) -> StaffOut:
    return serialize_staff_list(db, school_id, [staff])[0]


def get_staff(db: Session, school_id: uuid.UUID, staff_id: uuid.UUID) -> Staff:
    s = db.get(Staff, staff_id)
    if s is None or s.school_id != school_id or s.is_deleted:
        raise NotFoundError("Staff record not found")
    return s


def create_staff(
    db: Session,
    school_id: uuid.UUID,
    *,
    staff_no: str,
    full_name: str,
    membership_type: str = "teaching",
    gender: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    joined_date: date | None = None,
    user_id: uuid.UUID | None = None,
) -> Staff:
    if db.scalar(
        select(Staff.id).where(Staff.school_id == school_id, Staff.staff_no == staff_no)
    ):
        raise ConflictError("Staff number already in use")
    staff = Staff(
        school_id=school_id,
        staff_no=staff_no,
        full_name=full_name,
        membership_type=membership_type,
        gender=gender,
        phone=phone,
        email=email,
        joined_date=joined_date,
        user_id=user_id,
    )
    db.add(staff)
    db.flush()
    return staff


def update_staff(
    db: Session,
    school_id: uuid.UUID,
    staff_id: uuid.UUID,
    **fields,
) -> Staff:
    staff = get_staff(db, school_id, staff_id)
    for key, value in fields.items():
        if value is not None and hasattr(staff, key):
            setattr(staff, key, value)
    db.flush()
    return staff


def create_staff_account(
    db: Session,
    school_id: uuid.UUID,
    staff_id: uuid.UUID,
    *,
    email: str,
    password: str,
    role_id: uuid.UUID,
) -> tuple[Staff, Role]:
    """Create a login account (global user + school membership) for a staff
    member and link it to their Staff record so they can sign in.

    Returns the staff record and the school-scoped role that was assigned."""
    staff = get_staff(db, school_id, staff_id)
    if staff.user_id is not None:
        raise ConflictError("This staff member already has an account")
    email = email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise ConflictError("An account with this email already exists")
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    role = db.get(Role, role_id)
    if role is None or role.school_id != school_id:
        raise NotFoundError("Role not found")

    user = User(
        email=email,
        password_hash=security.hash_password(password),
        full_name=staff.full_name,
    )
    db.add(user)
    db.flush()
    db.add(
        SchoolMembership(user_id=user.id, school_id=school_id, role_id=role.id)
    )
    staff.user_id = user.id
    db.flush()
    return staff, role


def update_staff_account(
    db: Session,
    school_id: uuid.UUID,
    staff_id: uuid.UUID,
    *,
    email: str | None = None,
    password: str | None = None,
    role_id: uuid.UUID | None = None,
) -> tuple[Staff, Role]:
    """Change a staff member's login: email, password, and/or role.

    At least one field must be provided. Raises if the staff member has no
    login yet (use create_staff_account instead)."""
    staff = get_staff(db, school_id, staff_id)
    if staff.user_id is None:
        raise NotFoundError("This staff member does not have a login yet")

    user = db.get(User, staff.user_id)
    if user is None or user.status != "active":
        raise NotFoundError("This staff member does not have a login yet")

    if email is not None:
        email = email.strip().lower()
        if db.scalar(
            select(User.id).where(User.email == email, User.id != staff.user_id)
        ):
            raise ConflictError("An account with this email already exists")
        user.email = email

    if password is not None:
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters")
        user.password_hash = security.hash_password(password)

    membership = db.scalar(
        select(SchoolMembership).where(
            SchoolMembership.user_id == staff.user_id,
            SchoolMembership.school_id == school_id,
        )
    )
    role = membership.role if membership is not None else None
    if role_id is not None:
        role = db.get(Role, role_id)
        if role is None or role.school_id != school_id:
            raise NotFoundError("Role not found")
        if membership is not None:
            membership.role_id = role.id
    if role is None:
        raise NotFoundError("Role not found")

    db.flush()
    return staff, role


def delete_staff(db: Session, school_id: uuid.UUID, staff_id: uuid.UUID) -> None:
    """Soft-delete a staff member: remove them from the staff list, drop any
    subject assignments they teach, and revoke their login for this school."""
    staff = get_staff(db, school_id, staff_id)
    db.execute(
        delete(SubjectAssignment).where(
            SubjectAssignment.school_id == school_id,
            SubjectAssignment.teacher_id == staff.id,
        )
    )
    if staff.user_id is not None:
        db.execute(
            delete(SchoolMembership).where(
                SchoolMembership.user_id == staff.user_id,
                SchoolMembership.school_id == school_id,
            )
        )
        orphaned = db.scalar(
            select(SchoolMembership.id).where(
                SchoolMembership.user_id == staff.user_id
            )
        )
        if orphaned is None:
            db.execute(delete(User).where(User.id == staff.user_id))
        staff.user_id = None
    staff.is_deleted = True
    db.flush()


# --- Students -------------------------------------------------------------------
def list_students(
    db: Session, school_id: uuid.UUID, *, arm_id: uuid.UUID | None = None, q: str | None = None
) -> list[Student]:
    stmt = (
        select(Student)
        .where(Student.school_id == school_id, Student.is_deleted.is_(False))
    )
    if arm_id is not None:
        stmt = stmt.join(StudentEnrollment).where(
            StudentEnrollment.class_arm_id == arm_id,
            StudentEnrollment.is_current.is_(True),
            StudentEnrollment.status == "active",
        )
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            (Student.first_name.ilike(like)) | (Student.last_name.ilike(like))
            | (Student.admission_no.ilike(like))
        )
    return list(db.scalars(stmt.order_by(Student.last_name, Student.first_name)))


def get_student(db: Session, school_id: uuid.UUID, student_id: uuid.UUID) -> Student:
    s = db.get(Student, student_id)
    if s is None or s.school_id != school_id or s.is_deleted:
        raise NotFoundError("Student not found")
    return s


def create_student(
    db: Session,
    school_id: uuid.UUID,
    *,
    admission_no: str,
    first_name: str,
    last_name: str,
    gender: str,
    date_of_birth: date | None = None,
    middle_name: str | None = None,
    address: str | None = None,
    state: str | None = None,
    lga: str | None = None,
    blood_group: str | None = None,
    medical_notes: str | None = None,
    previous_school: str | None = None,
    photo_url: str | None = None,
    user_id: uuid.UUID | None = None,
) -> Student:
    if db.scalar(
        select(Student.id).where(
            Student.school_id == school_id, Student.admission_no == admission_no
        )
    ):
        raise ConflictError("Admission number already in use")
    student = Student(
        school_id=school_id,
        admission_no=admission_no,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        gender=gender,
        date_of_birth=date_of_birth,
        address=address,
        state=state,
        lga=lga,
        blood_group=blood_group,
        medical_notes=medical_notes,
        previous_school=previous_school,
        photo_url=photo_url,
        user_id=user_id,
    )
    db.add(student)
    db.flush()
    return student


def update_student(db: Session, school_id: uuid.UUID, student_id: uuid.UUID, **fields) -> Student:
    student = get_student(db, school_id, student_id)
    for key, value in fields.items():
        if value is not None and hasattr(student, key):
            setattr(student, key, value)
    db.flush()
    return student


def delete_student(db: Session, school_id: uuid.UUID, student_id: uuid.UUID) -> None:
    student = get_student(db, school_id, student_id)
    student.is_deleted = True
    db.flush()


# --- Enrollments -----------------------------------------------------------------
def enroll_student(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    arm_id: uuid.UUID,
    session_id: uuid.UUID,
    campus_id: uuid.UUID | None = None,
    enrolled_at: date | None = None,
) -> StudentEnrollment:
    get_student(db, school_id, student_id)
    get_arm(db, school_id, arm_id)
    existing = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.academic_session_id == session_id,
        )
    )
    if existing is not None:
        existing.class_arm_id = arm_id
        existing.status = "active"
        existing.is_current = True
        existing.enrolled_at = enrolled_at or date.today()
        db.flush()
        return existing
    enrollment = StudentEnrollment(
        school_id=school_id,
        student_id=student_id,
        class_arm_id=arm_id,
        academic_session_id=session_id,
        campus_id=campus_id,
        enrolled_at=enrolled_at or date.today(),
        status="active",
        is_current=True,
    )
    db.add(enrollment)
    db.flush()
    return enrollment


def list_enrollments(
    db: Session, school_id: uuid.UUID, arm_id: uuid.UUID
) -> list[StudentEnrollment]:
    get_arm(db, school_id, arm_id)
    return list(
        db.scalars(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.school_id == school_id,
                StudentEnrollment.class_arm_id == arm_id,
                StudentEnrollment.is_current.is_(True),
                StudentEnrollment.status == "active",
            )
            .order_by(StudentEnrollment.student_id)
        )
    )


def set_enrollment_status(
    db: Session,
    school_id: uuid.UUID,
    enrollment_id: uuid.UUID,
    *,
    status: str,
    is_current: bool | None = None,
) -> StudentEnrollment:
    enrollment = db.get(StudentEnrollment, enrollment_id)
    if enrollment is None or enrollment.school_id != school_id:
        raise NotFoundError("Enrollment not found")
    enrollment.status = status
    if is_current is not None:
        enrollment.is_current = is_current
    db.flush()
    return enrollment


def promote_students(
    db: Session,
    school_id: uuid.UUID,
    *,
    from_session_id: uuid.UUID,
    to_session_id: uuid.UUID,
    target_arms: list[dict],
    student_ids: list[uuid.UUID] | None = None,
) -> dict:
    """Advance currently-enrolled students from one session into the next.

    ``target_arms`` is a per-source-class mapping: each entry has a
    ``from_arm_id`` (a class in ``from_session``) and a ``to_arm_id`` (the
    class in ``to_session`` that its students should be moved to). Students in
    a source class without a mapping are skipped. The old enrollment is closed
    (``is_current=False, status='completed'``) and a fresh one is
    created/updated in the target session.

    Returns ``{"promoted": int, "skipped": list[str]}`` — skipped students are
    those whose source class has no target mapped in the target session.
    """
    from_session = get_session(db, school_id, from_session_id)
    to_session = get_session(db, school_id, to_session_id)

    if not target_arms:
        raise ValidationError("At least one source class → target class mapping is required")

    mapping: dict[uuid.UUID, uuid.UUID] = {}
    for pair in target_arms:
        src_id = pair.get("from_arm_id")
        dst_id = pair.get("to_arm_id")
        if src_id is None or dst_id is None:
            continue
        get_arm(db, school_id, src_id)
        dst = get_arm(db, school_id, dst_id)
        if dst.academic_session_id != to_session.id:
            raise ValidationError("Every target class must belong to the target session")
        mapping[uuid.UUID(str(src_id))] = uuid.UUID(str(dst_id))

    stmt = select(StudentEnrollment).where(
        StudentEnrollment.school_id == school_id,
        StudentEnrollment.academic_session_id == from_session.id,
        StudentEnrollment.is_current.is_(True),
        StudentEnrollment.status == "active",
    )
    if student_ids:
        stmt = stmt.where(StudentEnrollment.student_id.in_(student_ids))
    enrollments = list(db.scalars(stmt))

    promoted = 0
    skipped: list[str] = []
    for enrollment in enrollments:
        target_id = mapping.get(enrollment.class_arm_id)
        if target_id is None:
            skipped.append(str(enrollment.student_id))
            continue
        # Close the old enrollment.
        enrollment.is_current = False
        enrollment.status = "completed"
        # Upsert the new one.
        enroll_student(
            db,
            school_id,
            student_id=enrollment.student_id,
            arm_id=target_id,
            session_id=to_session.id,
        )
        promoted += 1

    db.flush()
    return {"promoted": promoted, "skipped": skipped}


def change_student_class(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    session_id: uuid.UUID,
    target_arm_id: uuid.UUID,
) -> dict:
    """Move a student to a specific class within the same session.

    The admin chooses the exact target class (the "class a student will be
    promoted or demoted to" is picked manually). Returns the new arm summary.
    """
    get_student(db, school_id, student_id)
    get_session(db, school_id, session_id)
    target_arm = get_arm(db, school_id, target_arm_id)
    if target_arm.academic_session_id != session_id:
        raise ValidationError("The target class must belong to the selected session")

    enrollment = db.scalar(
        select(StudentEnrollment).where(
            StudentEnrollment.school_id == school_id,
            StudentEnrollment.student_id == student_id,
            StudentEnrollment.academic_session_id == session_id,
            StudentEnrollment.is_current.is_(True),
            StudentEnrollment.status == "active",
        )
    )
    if enrollment is None:
        raise ValidationError("This student is not enrolled in the selected session")

    enroll_student(
        db, school_id,
        student_id=student_id, arm_id=target_arm.id, session_id=session_id,
    )
    db.flush()
    return {
        "arm_id": str(target_arm.id),
        "arm_name": target_arm.full_name,
    }


def enrollment_summary(
    db: Session, school_id: uuid.UUID, student_id: uuid.UUID
) -> list[dict]:
    """Chronological enrollment history for one student, with arm names."""
    get_student(db, school_id, student_id)
    rows = list(
        db.scalars(
            select(StudentEnrollment)
            .where(
                StudentEnrollment.school_id == school_id,
                StudentEnrollment.student_id == student_id,
            )
            .order_by(StudentEnrollment.academic_session_id)
        )
    )
    out = []
    for e in rows:
        arm = db.get(ClassArm, e.class_arm_id)
        out.append(
            {
                "enrollment_id": str(e.id),
                "session_id": str(e.academic_session_id),
                "arm_id": str(e.class_arm_id),
                "arm_name": arm.full_name if arm else "",
                "status": e.status,
                "is_current": e.is_current,
            }
        )
    return out


# --- Guardians --------------------------------------------------------------------
def list_guardians(db: Session, school_id: uuid.UUID, student_id: uuid.UUID) -> list[dict]:
    get_student(db, school_id, student_id)
    rows = db.execute(
        select(Guardian, StudentGuardian)
        .join(StudentGuardian, StudentGuardian.guardian_id == Guardian.id)
        .where(StudentGuardian.student_id == student_id)
    ).all()
    return [
        {
            "guardian": g,
            "relationship": sg.guardian_relationship,  # plain VARCHAR column (see models/people.py)
            "is_primary": sg.is_primary,
            "link_id": str(sg.id),
        }
        for g, sg in rows
    ]


def create_guardian(
    db: Session,
    school_id: uuid.UUID,
    *,
    full_name: str,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    occupation: str | None = None,
    user_id: uuid.UUID | None = None,
) -> Guardian:
    guardian = Guardian(
        school_id=school_id,
        full_name=full_name,
        phone=phone,
        email=email,
        address=address,
        occupation=occupation,
        user_id=user_id,
    )
    db.add(guardian)
    db.flush()
    return guardian


def link_guardian(
    db: Session,
    school_id: uuid.UUID,
    *,
    student_id: uuid.UUID,
    guardian_id: uuid.UUID,
    relationship: str,
    is_primary: bool = False,
) -> StudentGuardian:
    get_student(db, school_id, student_id)
    guardian = db.get(Guardian, guardian_id)
    if guardian is None or guardian.school_id != school_id:
        raise NotFoundError("Guardian not found")
    if db.scalar(
        select(StudentGuardian.id).where(
            StudentGuardian.student_id == student_id,
            StudentGuardian.guardian_id == guardian_id,
        )
    ):
        raise ConflictError("This guardian is already linked to the student")
    link = StudentGuardian(
        school_id=school_id,
        student_id=student_id,
        guardian_id=guardian_id,
        guardian_relationship=relationship,
        is_primary=is_primary,
    )
    db.add(link)
    db.flush()
    return link


def unlink_guardian(db: Session, school_id: uuid.UUID, link_id: uuid.UUID) -> None:
    link = db.get(StudentGuardian, link_id)
    if link is None or link.school_id != school_id:
        raise NotFoundError("Guardian link not found")
    db.delete(link)
    db.flush()