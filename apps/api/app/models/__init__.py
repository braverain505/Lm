"""Import every model so ``Base.metadata`` is complete for migrations & tests."""
from .base import Base, TenantScopedBase, TimestampMixin, UUIDPkMixin  # noqa: F401
from .school import Campus, School  # noqa: F401
from .identity import (  # noqa: F401
    Permission,
    Role,
    RolePermission,
    SchoolMembership,
    User,
)
from .auth_tokens import (  # noqa: F401
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
)
from .academic import (  # noqa: F401
    AcademicSession,
    ClassArm,
    GradeBand,
    GradeScale,
    LessonPlan,
    QuestionBank,
    Subject,
    SubjectAssignment,
    SubjectOffering,
    Term,
)
from .people import (  # noqa: F401
    Guardian,
    Staff,
    Student,
    StudentEnrollment,
    StudentGuardian,
)
from .attendance import (  # noqa: F401
    AttendanceSummary,
    StaffAttendance,
    StudentAttendance,
)
from .fees import (  # noqa: F401
    FeeStructure,
    Invoice,
    Payment,
    StudentFeeBalance,
)
from .payroll import (  # noqa: F401
    PayRun,
    Payslip,
    SalaryStructure,
    StaffSalary,
)
from .inventory import (  # noqa: F401
    InventoryCategory,
    InventoryItem,
    StockMovement,
)
from .library import Book, Borrowing  # noqa: F401
from .results import (  # noqa: F401
    AssessmentComponent,
    CommentBankEntry,
    PsychomotorAssessment,
    Result,
    ResultComment,
    ResultEvent,
    Score,
)
from .portal import StudentPin  # noqa: F401
from .copilot import CopilotConversation, CopilotMessage  # noqa: F401
from .imports import ImportBatch, ImportRow  # noqa: F401
from .crosscut import (  # noqa: F401
    AiUsage,
    AuditLog,
    Notification,
    SchoolSubscription,
    SubscriptionPlan,
    UsageMeter,
)
from .platform import (  # noqa: F401
    ImpersonationSession,
    PlatformAnnouncement,
    PlatformNotification,
    PlatformRegion,
    PlatformSetting,
    PlatformTicket,
    SubscriptionEvent,
)

__all__ = [
    "Base",
    "TenantScopedBase",
    "TimestampMixin",
    "UUIDPkMixin",
    "School",
    "Campus",
    "User",
    "Role",
    "Permission",
    "RolePermission",
    "SchoolMembership",
    "RefreshToken",
    "PasswordResetToken",
    "EmailVerificationToken",
    "AcademicSession",
    "Term",
    "ClassArm",
    "Subject",
    "SubjectOffering",
    "SubjectAssignment",
    "LessonPlan",
    "QuestionBank",
    "GradeScale",
    "GradeBand",
    "Staff",
    "Student",
    "StudentEnrollment",
    "Guardian",
    "StudentGuardian",
    "FeeStructure",
    "Invoice",
    "Payment",
    "StudentFeeBalance",
    "SalaryStructure",
    "StaffSalary",
    "PayRun",
    "Payslip",
    "InventoryCategory",
    "InventoryItem",
    "StockMovement",
    "Book",
    "Borrowing",
    "StudentAttendance",
    "StaffAttendance",
    "AttendanceSummary",
    "AssessmentComponent",
    "Score",
    "Result",
    "ResultComment",
    "ResultEvent",
    "PsychomotorAssessment",
    "CommentBankEntry",
    "StudentPin",
    "CopilotConversation",
    "CopilotMessage",
    "ImportBatch",
    "ImportRow",
    "AiUsage",
    "AuditLog",
    "Notification",
    "SchoolSubscription",
    "SubscriptionPlan",
    "UsageMeter",
    "ImpersonationSession",
    "PlatformAnnouncement",
    "PlatformNotification",
    "PlatformRegion",
    "PlatformSetting",
    "PlatformTicket",
    "SubscriptionEvent",
]