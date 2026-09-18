"""Transactional email for the account lifecycle: the getting-started PDF, the
welcome message sent when a school registers, and the reset link that makes
"forgot password" actually reach the user.

The suite never talks to the provider — ``conftest`` clears ``RESEND_API_KEY``
and each test patches ``email_service.send_email`` when it wants to inspect an
outgoing message.
"""
from __future__ import annotations

import base64

import pytest

from app.config import settings
from app.core.errors import EmailNotConfiguredError
from app.services import email_service

from .conftest import register_school


@pytest.fixture()
def sent(monkeypatch) -> list[dict]:
    """Intercept outgoing email. Returns the outbox (one dict per message)."""
    outbox: list[dict] = []

    def fake_send(
        *,
        to: str,
        subject: str,
        html: str,
        text: str | None = None,
        reply_to: str | None = None,
        attachments: list[dict] | None = None,
    ) -> email_service.EmailResult:
        outbox.append(
            {
                "to": to,
                "subject": subject,
                "html": html,
                "text": text,
                "attachments": attachments or [],
            }
        )
        return email_service.EmailResult(delivered=True, provider_id="test-message")

    monkeypatch.setattr(email_service, "send_email", fake_send)
    return outbox


# --- The guide document -------------------------------------------------------


def test_setup_guide_pdf_is_a_real_document():
    pdf = email_service.build_setup_guide_pdf(
        school_name="Brightfield Academy",
        admin_email="jane@school.edu",
        sign_in_url="https://app.clearis.test/login",
    )
    assert pdf.startswith(b"%PDF")
    # Comfortably bigger than a stub page: the guide carries the setup steps
    # plus the role table.
    assert len(pdf) > 3000


def test_welcome_email_carries_credentials_and_the_guide():
    subject, html, text, attachments = email_service.build_welcome_email(
        school_name="Brightfield Academy",
        admin_full_name="Jane Doe",
        admin_email="jane@school.edu",
        password="Str0ng!Pass",
    )
    assert "Brightfield Academy" in subject
    # The username and the password the admin needs to sign in.
    assert "jane@school.edu" in html
    assert "Str0ng!Pass" in html
    assert "jane@school.edu" in text and "Str0ng!Pass" in text
    # ...and the guide is attached, not merely mentioned by name.
    assert attachments[0]["filename"] == "Clearis-Getting-Started.pdf"
    assert base64.b64decode(attachments[0]["content"]).startswith(b"%PDF")
    assert "Getting-Started.pdf" in html


def test_welcome_email_points_at_the_dashboard_and_the_setup_work():
    _, html, text, _ = email_service.build_welcome_email(
        school_name="Brightfield Academy",
        admin_full_name="Jane Doe",
        admin_email="jane@school.edu",
        password="Str0ng!Pass",
    )
    assert f"{settings.web_base_url}/dashboard" in html
    assert f"{settings.web_base_url}/login" in html
    # The four things the admin is actually being asked to do next.
    for keyword in ("session", "classes", "subjects", "teachers", "students"):
        assert keyword in text.lower(), keyword


# --- Registration sends the welcome email -------------------------------------


def test_registering_a_school_emails_the_admin_their_credentials(client, sent):
    register_school(
        client,
        name="Brightfield Academy",
        email="jane@school.edu",
        password="Str0ng!Pass",
    )

    assert len(sent) == 1, "registration must send exactly one onboarding email"
    mail = sent[0]
    assert mail["to"] == "jane@school.edu"
    assert "Brightfield Academy" in mail["subject"]
    assert "jane@school.edu" in mail["html"]
    assert "Str0ng!Pass" in mail["html"]
    assert mail["attachments"][0]["filename"] == "Clearis-Getting-Started.pdf"


def test_welcome_email_failure_does_not_fail_the_registration(client, monkeypatch):
    """The workspace is already committed by the time we send, so a dead mail
    provider must not turn a successful signup into an error page."""

    def boom(**kwargs):
        raise EmailNotConfiguredError()

    monkeypatch.setattr(email_service, "send_email", boom)

    data = register_school(client, email="offline@test.edu")

    assert data["access_token"]
    assert client.get("/api/auth/me").status_code == 200


# --- Forgot password ----------------------------------------------------------


def test_password_reset_emails_a_link_containing_the_token(client, sent):
    register_school(client, email="reset@test.edu")
    sent.clear()

    r = client.post("/api/auth/passwords/reset", json={"email": "reset@test.edu"})
    assert r.status_code == 200, r.text

    # Dev mode still returns the token so the flow is testable without a key.
    token = r.json()["reset_token"]
    assert token

    assert len(sent) == 1
    mail = sent[0]
    assert mail["to"] == "reset@test.edu"
    assert f"{settings.web_base_url}/reset-password?token={token}" in mail["html"]
    assert f"{settings.web_base_url}/reset-password?token={token}" in mail["text"]


def test_password_reset_sends_nothing_for_an_unknown_address(client, sent):
    r = client.post("/api/auth/passwords/reset", json={"email": "nobody@test.edu"})
    assert r.status_code == 200
    assert r.json()["reset_token"] is None
    assert sent == [], "an unknown address must not generate mail"


def test_reset_request_surfaces_a_missing_provider_instead_of_faking_a_send(
    client, monkeypatch
):
    """Production with no provider must fail loudly. The response is the same
    neutral line either way, so a link that was never delivered would otherwise
    look delivered and leave the user waiting for mail that is not coming."""
    register_school(client, email="prod@test.edu")
    monkeypatch.setattr(settings, "dev_email", False)

    r = client.post("/api/auth/passwords/reset", json={"email": "prod@test.edu"})

    assert r.status_code == 503
    assert r.json()["error"]["code"] == "ERR_EMAIL_NOT_CONFIGURED"


# --- Provider degradation rules ----------------------------------------------


def test_send_email_reports_a_dev_skip_rather_than_claiming_delivery(monkeypatch):
    monkeypatch.setattr(settings, "dev_email", True)

    result = email_service.send_email(
        to="jane@school.edu", subject="Test", html="<p>Hello</p>"
    )

    assert result.delivered is False
    assert result.dev_skipped is True


def test_send_email_refuses_in_production_without_a_key(monkeypatch):
    monkeypatch.setattr(settings, "dev_email", False)

    with pytest.raises(EmailNotConfiguredError):
        email_service.send_email(
            to="jane@school.edu", subject="Test", html="<p>Hello</p>"
        )
