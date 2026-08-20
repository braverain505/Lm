"""SaaS subscription lifecycle: global plans and per-school subscriptions.

These are the *platform* billing primitives (what the owner sells), distinct
from the tenant-internal fee structures/invoices used by schools to bill their
own families. Every school gets a subscription at onboarding (default: trial);
the Super Admin upgrades/downgrades schools and records billing events.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import SchoolSubscription, SubscriptionEvent, SubscriptionPlan

TRIAL_DAYS = 14

PLAN_DEFINITIONS = [
    {
        "code": "starter",
        "name": "Starter",
        "description": "Core school management for small schools.",
        "price_monthly_usd": 0,
        "price_yearly_usd": 0,
        "features": {
            "ai_enabled": False,
            "ai_credits": 0,
            "storage_gb": 5,
            "students": 200,
            "teachers": 20,
        },
        "sort_order": 10,
    },
    {
        "code": "professional",
        "name": "Professional",
        "description": "Full management plus premium AI for growing schools.",
        "price_monthly_usd": 49,
        "price_yearly_usd": 470,
        "features": {
            "ai_enabled": True,
            "ai_credits": 2000,
            "storage_gb": 50,
            "students": 1000,
            "teachers": 100,
        },
        "sort_order": 20,
    },
    {
        "code": "enterprise",
        "name": "Enterprise",
        "description": "Unlimited everything, dedicated support.",
        "price_monthly_usd": 199,
        "price_yearly_usd": 1910,
        "features": {
            "ai_enabled": True,
            "ai_credits": 20000,
            "storage_gb": 500,
            "students": 0,  # 0 = unlimited
            "teachers": 0,  # 0 = unlimited
        },
        "sort_order": 30,
    },
]


def ensure_default_plans(db: Session) -> None:
    """Idempotently create the global product plans."""
    existing = {p.code: p for p in db.scalars(select(SubscriptionPlan)).all()}
    for definition in PLAN_DEFINITIONS:
        plan = existing.get(definition["code"])
        if plan is None:
            db.add(SubscriptionPlan(**definition))
        else:
            plan.name = definition["name"]
            plan.description = definition["description"]
            plan.price_monthly_usd = definition["price_monthly_usd"]
            plan.price_yearly_usd = definition["price_yearly_usd"]
            plan.features = definition["features"]
            plan.sort_order = definition["sort_order"]
            plan.is_active = True
    db.flush()


def default_trial_plan(db: Session) -> SubscriptionPlan:
    """The plan used for a brand-new school before it subscribes."""
    plan = db.scalar(
        select(SubscriptionPlan).where(SubscriptionPlan.code == "trial")
    )
    if plan is None:
        plan = SubscriptionPlan(
            code="trial",
            name="Trial",
            description="14-day evaluation of the full platform.",
            price_monthly_usd=0,
            price_yearly_usd=0,
            features={
                "ai_enabled": True,
                "ai_credits": 500,
                "storage_gb": 5,
                "students": 0,
                "teachers": 0,
            },
            is_active=True,
            sort_order=5,
        )
        db.add(plan)
        db.flush()
    return plan


def get_active_subscription(db: Session, school_id: uuid.UUID) -> SchoolSubscription | None:
    return db.scalar(
        select(SchoolSubscription)
        .where(SchoolSubscription.school_id == school_id)
        .order_by(SchoolSubscription.created_at.desc())
    )


def provision_subscription(
    db: Session,
    school_id: uuid.UUID,
    *,
    plan: SubscriptionPlan | None = None,
    status: str = "trial",
    ends_at: datetime | None = None,
) -> SchoolSubscription:
    """Give a school its first subscription (default: 14-day trial). Idempotent —
    a school with an existing subscription is left untouched."""
    existing = get_active_subscription(db, school_id)
    if existing is not None:
        return existing

    if plan is None:
        plan = default_trial_plan(db)
    now = datetime.now().astimezone()
    subscription = SchoolSubscription(
        school_id=school_id,
        plan_id=plan.id,
        status=status,
        starts_at=now,
        ends_at=ends_at or (now + timedelta(days=TRIAL_DAYS)),
        ai_credits_total=plan.features.get("ai_credits", 0),
        ai_credits_used=0,
    )
    db.add(subscription)
    db.flush()
    db.add(
        SubscriptionEvent(
            school_id=school_id,
            subscription_id=subscription.id,
            event_type="trial_started" if status == "trial" else "activated",
            status="success",
            meta={"plan": plan.code, "days": TRIAL_DAYS},
        )
    )
    return subscription


def record_subscription_event(
    db: Session,
    *,
    school_id: uuid.UUID,
    subscription_id: uuid.UUID | None,
    event_type: str,
    status: str = "success",
    amount: float | None = None,
    meta: dict | None = None,
) -> SubscriptionEvent:
    event = SubscriptionEvent(
        school_id=school_id,
        subscription_id=subscription_id,
        event_type=event_type,
        status=status,
        amount=amount,
        meta=meta or {},
    )
    db.add(event)
    db.flush()
    return event


__all__ = [
    "ensure_default_plans",
    "default_trial_plan",
    "get_active_subscription",
    "provision_subscription",
    "record_subscription_event",
    "PLAN_DEFINITIONS",
    "TRIAL_DAYS",
]