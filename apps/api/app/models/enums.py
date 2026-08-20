"""Shared enums (stored as VARCHAR via native_enum=False for migration simplicity)."""
from enum import Enum


class SchoolType(str, Enum):
    CRECHE = "creche"
    NURSERY = "nursery"
    KINDERGARTEN = "kindergarten"
    PRIMARY = "primary"
    JUNIOR_SECONDARY = "junior_secondary"
    SENIOR_SECONDARY = "senior_secondary"
    SIXTH_FORM = "sixth_form"
    VOCATIONAL = "vocational"
    CUSTOM = "custom"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    LOCKED = "locked"


class MembershipStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INVITED = "invited"


class EmploymentStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    TERMINATED = "terminated"
    RESIGNED = "resigned"


class StaffType(str, Enum):
    TEACHING = "teaching"
    NON_TEACHING = "non_teaching"


class EnrollmentStatus(str, Enum):
    ACTIVE = "active"
    GRADUATED = "graduated"
    WITHDRAWN = "withdrawn"
    ON_HOLD = "on_hold"
    TRANSFERRED = "transferred"


class GuardianRelationship(str, Enum):
    FATHER = "father"
    MOTHER = "mother"
    GUARDIAN = "guardian"
    SIBLING = "sibling"
    SPONSOR = "sponsor"
    OTHER = "other"


class SessionStatus(str, Enum):
    PLANNED = "planned"
    OPEN = "open"
    CLOSED = "closed"


class TermStatus(str, Enum):
    PLANNED = "planned"
    OPEN = "open"
    CLOSED = "closed"


# Result lifecycle: draft -> submitted -> verified -> approved -> published
# (rejected allows a reviewer to bounce a submission back to draft for re-entry).
class ResultStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class SubscriptionStatus(str, Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class NotificationChannel(str, Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class PaymentStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIAL = "partial"
    PAID = "paid"
    WRITE_OFF = "write_off"
    EXPIRED = "expired"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    BANK_TRANSFER = "bank_transfer"
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    POS = "pos"
    OTHER = "other"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    PARTIAL = "partial"
    PAID = "paid"
    WRITE_OFF = "write_off"
    EXPIRED = "expired"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class AuditAction(str, Enum):
    # Used for the coarse-grained audit trail (append-only).
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    SUBMIT = "submit"
    APPROVE = "approve"
    PUBLISH = "publish"
    REJECT = "reject"
    OTHER = "other"