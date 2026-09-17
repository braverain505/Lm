"""Permission catalog constants and default role templates.

Codes are stable strings used in ``permissions`` (global catalog), in
``role_permissions`` (per school), and by the ``require_permission`` dependency.
Changing semantics of a code is a migration; never rename casually.
"""
from __future__ import annotations

# --- AI -----------------------------------------------------------------------
AI_COPILOT = "ai.copilot"  # school copilot: free-form Q&A over school data

# --- Results ----------------------------------------------------------------
RESULTS_VIEW = "results.view"
RESULTS_ENTER = "results.enter"   # data-scoped: teachers need a subject_assignment
RESULTS_SUBMIT = "results.submit"
RESULTS_VERIFY = "results.verify"
RESULTS_APPROVE = "results.approve"
RESULTS_PUBLISH = "results.publish"
RESULTS_COMMENT = "results.comment"  # principal / head-of-academics remarks
# Report cards are the Exam Office's document, not every teacher's. Generating
# and printing them renders every subject a student took, so it is deliberately
# separate from ``results.view`` (which teachers hold in order to open their own
# scoresheets). Granting this code is what turns a user into a card processor.
RESULTS_REPORT_CARD = "results.report_card"

# --- Students --------------------------------------------------------------
STUDENTS_VIEW = "students.view"
STUDENTS_CREATE = "students.create"
STUDENTS_EDIT = "students.edit"
STUDENTS_DELETE = "students.delete"
STUDENTS_ENROLL = "students.enroll"

# --- Staff / teachers --------------------------------------------------------
STAFF_VIEW = "staff.view"
STAFF_CREATE = "staff.create"
STAFF_EDIT = "staff.edit"

# --- Academics (structure) ----------------------------------------------------
ACADEMICS_VIEW = "academics.view"
ACADEMICS_MANAGE = "academics.manage"

# --- Roles & permissions -------------------------------------------------------
ROLES_MANAGE = "roles.manage"

# --- School settings -------------------------------------------------------------
SCHOOL_MANAGE = "school.manage"
CAMPUS_MANAGE = "campus.manage"

# --- Finance / billing --------------------------------------------------------------
FEES_VIEW = "fees.view"
FEES_COLLECT = "fees.collect"
FEES_CREATE = "fees.create"
FEES_EDIT = "fees.edit"
FEES_PAY = "fees.pay"
BILLING_VIEW = "billing.view"
PAYROLL_VIEW = "payroll.view"
PAYROLL_MANAGE = "payroll.manage"

# --- Accounting (the accountant's ledger) -------------------------------------
ACCOUNTING_VIEW = "accounting.view"
ACCOUNTING_EXPENSES = "accounting.expenses"    # record/approve/pay expenses + petty cash
ACCOUNTING_AMEND = "accounting.amend"          # discounts/waivers, credit notes, refunds
ACCOUNTING_RECONCILE = "accounting.reconcile"  # cashbook + bank statement reconciliation
ACCOUNTING_REPORTS = "accounting.reports"      # income & expenditure and collection reports

# Accounting is the Accountant's domain: finance codes must never leak onto the
# general school-admin roles. Keep this set in sync with the finance codes above.
FINANCE_PERMISSIONS: frozenset[str] = frozenset({
    FEES_VIEW, FEES_COLLECT, FEES_CREATE, FEES_EDIT, FEES_PAY,
    BILLING_VIEW, PAYROLL_VIEW, PAYROLL_MANAGE,
    ACCOUNTING_VIEW, ACCOUNTING_EXPENSES, ACCOUNTING_AMEND,
    ACCOUNTING_RECONCILE, ACCOUNTING_REPORTS,
})

# --- Student roster scope -------------------------------------------------------
# Who may see the *whole* school's student roster. Anyone holding
# ``students.view`` without one of these capabilities is teaching staff: their
# view stops at the class arms they are assigned to teach, so a teacher cannot
# browse (or search) the rest of the school.
#
# Deliberately a capability set rather than a list of role codes: a school's
# custom roles then inherit the right scope from what they can actually do, and
# a role we have never seen fails *closed* (scoped) instead of open.
#
#  * students.create/edit/delete/enroll — the admissions office and admins.
#  * staff.view — principal, VPs, secretary, librarian: roster-wide by office.
#  * results.verify/approve/publish — the results supervisors and the exam
#    office, whose work spans every class in the school.
ROSTER_WIDE_PERMISSIONS: frozenset[str] = frozenset({
    STUDENTS_CREATE, STUDENTS_EDIT, STUDENTS_DELETE, STUDENTS_ENROLL,
    STAFF_VIEW,
    RESULTS_VERIFY, RESULTS_APPROVE, RESULTS_PUBLISH,
})

# --- Inventory ----------------------------------------------------------------------
INVENTORY_VIEW = "inventory.view"
INVENTORY_MANAGE = "inventory.manage"  # create/edit items, stock adjustments, categories

# --- Library ------------------------------------------------------------------------
LIBRARY_VIEW = "library.view"
LIBRARY_MANAGE = "library.manage"  # add/edit books and manage borrowings

# --- Users / memberships -----------------------------------------------------------
USERS_MANAGE = "users.manage"

# --- Legacy data imports (Phase 3) ---------------------------------------------------
IMPORTS_VIEW = "imports.view"
IMPORTS_CREATE = "imports.create"  # upload, map, run, re-import
IMPORTS_FIX = "imports.fix"  # edit pre-import row fixes

# --- Attendance / timetables --------------------------------------------------------
ATTENDANCE_VIEW = "attendance.view"
ATTENDANCE_MANAGE = "attendance.manage"
ATTENDANCE_MARK = "attendance.mark"
ATTENDANCE_REPORT = "attendance.report"
TIMETABLE_VIEW = "timetable.view"
TIMETABLE_MANAGE = "timetable.manage"
COMMUNICATION_SEND = "communication.send"

# Full catalog used for seeding.
PERMISSION_CATALOG: list[tuple[str, str, str]] = [
    (RESULTS_VIEW, "results", "View result records and readiness dashboards"),
    (RESULTS_ENTER, "results", "Enter scores for assigned subjects/classes"),
    (RESULTS_SUBMIT, "results", "Submit result entries for verification"),
    (RESULTS_VERIFY, "results", "Verify submitted results"),
    (RESULTS_APPROVE, "results", "Approve verified results"),
    (RESULTS_PUBLISH, "results", "Publish approved results to parents/students"),
    (RESULTS_COMMENT, "results", "Write principal/head-of-academics remarks on results"),
    (RESULTS_REPORT_CARD, "results", "View and print student report cards (exam office)"),
    (AI_COPILOT, "ai", "Use the school AI copilot (Q&A over school data)"),
    (STUDENTS_VIEW, "students", "View student profiles"),
    (STUDENTS_CREATE, "students", "Create student records"),
    (STUDENTS_EDIT, "students", "Edit student records"),
    (STUDENTS_DELETE, "students", "Delete/soft-delete student records"),
    (STUDENTS_ENROLL, "students", "Enroll students into classes"),
    (STAFF_VIEW, "staff", "View staff records"),
    (STAFF_CREATE, "staff", "Create staff records"),
    (STAFF_EDIT, "staff", "Edit staff records"),
    (ACADEMICS_VIEW, "academics", "View sessions, terms, classes, subjects"),
    (ACADEMICS_MANAGE, "academics", "Create/edit academic structure"),
    (ROLES_MANAGE, "roles", "Manage roles and their permissions"),
    (SCHOOL_MANAGE, "school", "Manage school profile and settings"),
    (CAMPUS_MANAGE, "school", "Manage campuses"),
    (FEES_VIEW, "finance", "View fees and payments"),
    (FEES_COLLECT, "finance", "Collect fee payments"),
    (FEES_CREATE, "finance", "Create fee structures and invoices"),
    (FEES_EDIT, "finance", "Edit fee structures"),
    (FEES_PAY, "finance", "Record fee payments"),
    (BILLING_VIEW, "finance", "View billing and subscription"),
    (PAYROLL_VIEW, "finance", "View payroll structures, pay runs, and payslips"),
    (PAYROLL_MANAGE, "finance", "Create/edit payroll structures and run payroll"),
    (ACCOUNTING_VIEW, "accounting", "View the ledger, cashbook, debtors and accounting dashboard"),
    (ACCOUNTING_EXPENSES, "accounting", "Record, approve and pay school expenses and petty cash"),
    (ACCOUNTING_AMEND, "accounting", "Apply discounts/waivers and issue credit notes and refunds"),
    (ACCOUNTING_RECONCILE, "accounting", "Reconcile the cashbook against bank statements"),
    (ACCOUNTING_REPORTS, "accounting", "View income & expenditure and fee collection reports"),
    (INVENTORY_VIEW, "inventory", "View inventory items and stock levels"),
    (INVENTORY_MANAGE, "inventory", "Create/edit inventory items and adjust stock"),
    (LIBRARY_VIEW, "library", "View library catalogue and borrowing records"),
    (LIBRARY_MANAGE, "library", "Add/edit library books and manage borrowings"),
    (USERS_MANAGE, "users", "Invite and manage school users"),
    (ATTENDANCE_VIEW, "attendance", "View attendance"),
    (ATTENDANCE_MANAGE, "attendance", "Manage attendance"),
    (ATTENDANCE_MARK, "attendance", "Mark attendance for students and staff"),
    (ATTENDANCE_REPORT, "attendance", "View attendance summaries and reports"),
    (TIMETABLE_VIEW, "timetable", "View timetables and time slots"),
    (TIMETABLE_MANAGE, "timetable", "Generate and validate timetables"),
    (COMMUNICATION_SEND, "communication", "Send announcements/notifications"),
    (IMPORTS_VIEW, "imports", "View import history, batches, and row status"),
    (IMPORTS_CREATE, "imports", "Upload and run legacy data imports"),
    (IMPORTS_FIX, "imports", "Edit pre-import row fixes"),
]


# --- Default role templates ------------------------------------------------------
# Each school is provisioned with these roles on creation; admins can later edit
# them or add custom roles. A role template maps role code -> list of permission
# codes. Keep system roles stable in code.
ROLE_SUPER_ADMIN = "super_admin"
ROLE_DIRECTOR = "director"
ROLE_PRINCIPAL = "principal"
ROLE_VP_ACADEMICS = "vp_academics"
ROLE_VP_ADMIN = "vp_admin"
ROLE_HEAD_TEACHER = "head_teacher"
ROLE_ACAD_COORDINATOR = "academic_coordinator"
ROLE_EXAM_OFFICER = "exam_officer"
ROLE_TEACHER = "teacher"
ROLE_HOMEROOM_TEACHER = "homeroom_teacher"
ROLE_ACCOUNTANT = "accountant"
ROLE_BURSAR = "bursar"
ROLE_LIBRARIAN = "librarian"
ROLE_ADMISSION_OFFICER = "admission_officer"
ROLE_SECRETARY = "secretary"
ROLE_PARENT = "parent"
ROLE_STUDENT = "student"

# Accounting (the ledger, expenses, reconciliation, reports) belongs to the
# school's Accountant alone. This is enforced on the accounting routes *in
# addition to* permissions, so handing a bursar — or any admin — the finance
# permissions still does not open the books. Roles are school-scoped, so an
# accountant is the accountant of one school, with their own login.
ACCOUNTING_ROLES: frozenset[str] = frozenset({ROLE_ACCOUNTANT})

ROLE_TEMPLATES: dict[str, dict] = {
    ROLE_SUPER_ADMIN: {
        "name": "Super Admin",
        "is_system": True,
        "permissions": [
            code for code, _, _ in PERMISSION_CATALOG
            if code not in FINANCE_PERMISSIONS
        ],
    },
    ROLE_DIRECTOR: {
        "name": "Director",
        "is_system": True,
        "permissions": [
            code for code, _, _ in PERMISSION_CATALOG
            if code not in FINANCE_PERMISSIONS
        ],
    },
    ROLE_PRINCIPAL: {
        "name": "Principal",
        "is_system": True,
        "permissions": [
            RESULTS_VIEW, RESULTS_VERIFY, RESULTS_APPROVE, RESULTS_PUBLISH,
            RESULTS_COMMENT, RESULTS_REPORT_CARD, AI_COPILOT,
            STUDENTS_VIEW, STAFF_VIEW, ACADEMICS_VIEW, ACADEMICS_MANAGE,
            SCHOOL_MANAGE, CAMPUS_MANAGE, USERS_MANAGE, ATTENDANCE_VIEW,
            ATTENDANCE_REPORT, TIMETABLE_VIEW, TIMETABLE_MANAGE,
            INVENTORY_VIEW, INVENTORY_MANAGE,
            LIBRARY_VIEW, LIBRARY_MANAGE,
            IMPORTS_VIEW, IMPORTS_CREATE, IMPORTS_FIX,
        ],
    },
    ROLE_VP_ACADEMICS: {
        "name": "Vice Principal Academics",
        "is_system": True,
        "permissions": [
            RESULTS_VIEW, RESULTS_VERIFY, RESULTS_APPROVE, RESULTS_COMMENT,
            RESULTS_REPORT_CARD, AI_COPILOT,
            STUDENTS_VIEW, STAFF_VIEW, ACADEMICS_VIEW, ACADEMICS_MANAGE,
            ATTENDANCE_VIEW, ATTENDANCE_MARK, ATTENDANCE_REPORT,
            TIMETABLE_VIEW, TIMETABLE_MANAGE,
            IMPORTS_VIEW, IMPORTS_CREATE, IMPORTS_FIX,
        ],
    },
    ROLE_VP_ADMIN: {
        "name": "Vice Principal Administration",
        "is_system": True,
        "permissions": [
            STUDENTS_VIEW, STAFF_VIEW, USERS_MANAGE, SCHOOL_MANAGE,
            CAMPUS_MANAGE, ATTENDANCE_VIEW, ATTENDANCE_MARK, ATTENDANCE_REPORT,
            TIMETABLE_VIEW, TIMETABLE_MANAGE,
            INVENTORY_VIEW, INVENTORY_MANAGE,
            LIBRARY_VIEW, LIBRARY_MANAGE,
            IMPORTS_VIEW, IMPORTS_CREATE, IMPORTS_FIX,
        ],
    },
    ROLE_HEAD_TEACHER: {
        "name": "Head Teacher",
        "is_system": True,
        "permissions": [
            RESULTS_VIEW, RESULTS_VERIFY, RESULTS_APPROVE, AI_COPILOT,
            STUDENTS_VIEW, ACADEMICS_VIEW,
            ATTENDANCE_VIEW, ATTENDANCE_MARK, ATTENDANCE_REPORT, TIMETABLE_VIEW,
            IMPORTS_VIEW, IMPORTS_CREATE, IMPORTS_FIX,
        ],
    },
    ROLE_ACAD_COORDINATOR: {
        "name": "Academic Coordinator",
        "is_system": True,
        "permissions": [
            RESULTS_VIEW, RESULTS_VERIFY, AI_COPILOT, ACADEMICS_VIEW,
            ACADEMICS_MANAGE, STUDENTS_VIEW, STAFF_VIEW,
            ATTENDANCE_VIEW, ATTENDANCE_REPORT, TIMETABLE_VIEW, TIMETABLE_MANAGE,
            IMPORTS_VIEW, IMPORTS_CREATE, IMPORTS_FIX,
        ],
    },
    # The Exam Office runs the whole results pipeline: verify -> approve ->
    # publish, then print the cards those published snapshots produced. Holding
    # ``results.approve`` is what makes the one-click compile usable, and report
    # cards render *published* results — without it the office could only print
    # cards for cells somebody else had approved.
    ROLE_EXAM_OFFICER: {
        "name": "Exam Officer",
        "is_system": True,
        "permissions": [
            RESULTS_VIEW, RESULTS_VERIFY, RESULTS_APPROVE, RESULTS_PUBLISH,
            RESULTS_REPORT_CARD, ACADEMICS_VIEW, STUDENTS_VIEW,
        ],
    },
    ROLE_TEACHER: {
        "name": "Teacher",
        "is_system": True,
        "permissions": [
            RESULTS_VIEW, RESULTS_ENTER, RESULTS_SUBMIT, STUDENTS_VIEW,
            ATTENDANCE_VIEW, ATTENDANCE_MARK, ATTENDANCE_REPORT, TIMETABLE_VIEW,
            ACADEMICS_VIEW,
        ],
    },
    ROLE_HOMEROOM_TEACHER: {
        "name": "Homeroom Teacher",
        "is_system": True,
        "permissions": [
            RESULTS_VIEW, RESULTS_ENTER, RESULTS_SUBMIT, RESULTS_COMMENT,
            STUDENTS_VIEW, ATTENDANCE_VIEW, ATTENDANCE_MARK, ATTENDANCE_REPORT,
            TIMETABLE_VIEW, ACADEMICS_VIEW,
        ],
    },
    ROLE_ACCOUNTANT: {
        "name": "Accountant",
        "is_system": True,
        "permissions": [
            FEES_VIEW, FEES_COLLECT, FEES_CREATE, FEES_EDIT, FEES_PAY, BILLING_VIEW,
            PAYROLL_VIEW, PAYROLL_MANAGE,
            ACCOUNTING_VIEW, ACCOUNTING_EXPENSES, ACCOUNTING_AMEND,
            ACCOUNTING_RECONCILE, ACCOUNTING_REPORTS,
        ],
    },
    ROLE_BURSAR: {
        "name": "Bursar",
        "is_system": True,
        "permissions": [
            FEES_VIEW, FEES_COLLECT, FEES_CREATE, FEES_EDIT, FEES_PAY, BILLING_VIEW,
            PAYROLL_VIEW, PAYROLL_MANAGE,
            SCHOOL_MANAGE,
        ],
    },
    ROLE_ADMISSION_OFFICER: {
        "name": "Admission Officer",
        "is_system": True,
        "permissions": [
            STUDENTS_VIEW, STUDENTS_CREATE, STUDENTS_ENROLL,
            IMPORTS_VIEW, IMPORTS_CREATE, IMPORTS_FIX,
        ],
    },
    ROLE_SECRETARY: {
        "name": "Secretary",
        "is_system": True,
        "permissions": [
            STUDENTS_VIEW, STAFF_VIEW, ACADEMICS_VIEW, RESULTS_VIEW,
            LIBRARY_VIEW, LIBRARY_MANAGE,
            COMMUNICATION_SEND, IMPORTS_VIEW,
        ],
    },
    ROLE_LIBRARIAN: {
        "name": "Librarian",
        "is_system": True,
        "permissions": [
            STUDENTS_VIEW, STAFF_VIEW,
            LIBRARY_VIEW, LIBRARY_MANAGE,
        ],
    },
    ROLE_PARENT: {
        "name": "Parent",
        "is_system": True,
        "permissions": [],  # read-only portal grants resolved separately (Phase 2)
    },
    ROLE_STUDENT: {
        "name": "Student",
        "is_system": True,
        "permissions": [],
    },
}