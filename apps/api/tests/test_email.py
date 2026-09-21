"""Transactional email for the account lifecycle: the getting-started PDF, the
welcome message sent when a school registers, the internal new-school notice,
and the reset link that makes "forgot password" actually reach the user.

The suite never talks to the provider — ``conftest`` clears the mail
credentials (both transports, so ``EMAIL_TRANSPORT=auto`` cannot pick up an
SMTP account from .env). Tests either patch ``email_service.send_email`` to
inspect an outgoing message, or patch ``smtplib.SMTP`` to inspect what the SMTP
transport would put on the wire.
"""
from __future__ import annotations

import base64
import smtplib

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


def _only_to(outbox: list[dict], address: str) -> dict:
    """The single message addressed to ``address`` — fails if there are 0 or 2."""
    matches = [mail for mail in outbox if mail["to"] == address]
    assert len(matches) == 1, f"expected exactly one message to {address}, got {len(matches)}"
    return matches[0]


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

    # Registration sends two messages: the admin's onboarding mail, and an
    # internal notice to the platform owner.
    mail = _only_to(sent, "jane@school.edu")
    assert "Brightfield Academy" in mail["subject"]
    assert "jane@school.edu" in mail["html"]
    assert "Str0ng!Pass" in mail["html"]
    assert mail["attachments"][0]["filename"] == "Clearis-Getting-Started.pdf"


# --- The internal new-school notice -------------------------------------------


def test_registration_alerts_the_platform_owner(client, sent):
    register_school(
        client,
        name="Brightfield Academy",
        email="jane@school.edu",
        password="Str0ng!Pass",
    )

    assert settings.owner_alert_email, "the notice needs somewhere to go"
    alert = _only_to(sent, settings.owner_alert_email)
    assert "Brightfield Academy" in alert["subject"]
    assert "jane@school.edu" in alert["html"]
    # It is an internal notice, not the onboarding mail: it carries no password
    # and no guide, so a credential never sits in the owner's inbox.
    assert "Str0ng!Pass" not in alert["html"]
    assert "Str0ng!Pass" not in alert["text"]
    assert alert["attachments"] == []


def test_new_school_alert_carries_the_registration_details():
    subject, html, text = email_service.build_new_school_alert(
        school_name="Brightfield Academy",
        school_type="secondary",
        admin_full_name="Jane Doe",
        admin_email="jane@school.edu",
        location="12 Broad Street, Lagos, NG",
        phone="08012345678",
        website="https://brightfield.test",
        established_year=1998,
    )

    assert "Brightfield Academy" in subject
    for keyword in ("jane@school.edu", "Lagos", "08012345678", "1998"):
        assert keyword in html, keyword
        assert keyword in text, keyword


def test_new_school_alert_flags_an_onboarding_email_that_never_went_out():
    """The welcome mail is the one delivery worth acting on: if it did not go,
    the school is sitting there waiting for credentials nobody sent."""
    _, html, text = email_service.build_new_school_alert(
        school_name="Brightfield Academy",
        school_type="secondary",
        admin_full_name="Jane Doe",
        admin_email="jane@school.edu",
        welcome_email_sent=False,
    )
    assert "not delivered" in html.lower()
    assert "not delivered" in text.lower()

    _, html, text = email_service.build_new_school_alert(
        school_name="Brightfield Academy",
        school_type="secondary",
        admin_full_name="Jane Doe",
        admin_email="jane@school.edu",
        welcome_email_sent=True,
    )
    assert "not delivered" not in html.lower()
    assert "not delivered" not in text.lower()


def test_no_owner_alert_is_built_when_it_is_switched_off(monkeypatch):
    monkeypatch.setattr(settings, "owner_alert_email", "")

    assert (
        email_service.send_new_school_alert(
            school_name="Brightfield Academy",
            school_type="secondary",
            admin_full_name="Jane Doe",
            admin_email="jane@school.edu",
        )
        is None
    )


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


# --- The SMTP transport -------------------------------------------------------


class _FakeSMTP:
    """Stands in for ``smtplib.SMTP``: records the conversation, opens no socket."""

    instances: list["_FakeSMTP"] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.credentials: tuple[str, str] | None = None
        self.message = None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        return 250, b"ok"

    def starttls(self):
        self.started_tls = True
        return 220, b"ready"

    def login(self, user, password):
        self.credentials = (user, password)

    def send_message(self, message):
        self.message = message


@pytest.fixture()
def smtp(monkeypatch) -> list[_FakeSMTP]:
    """Configure the Gmail transport and capture what would go on the wire."""
    _FakeSMTP.instances = []
    monkeypatch.setattr(settings, "email_transport", "auto")
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "clearisinfo@gmail.com")
    monkeypatch.setattr(settings, "smtp_password", "abcd efgh ijkl mnop")
    monkeypatch.setattr(settings, "smtp_from", "")
    monkeypatch.setattr(settings, "email_reply_to", "clearisinfo@gmail.com")
    monkeypatch.setattr(email_service.smtplib, "SMTP", _FakeSMTP)
    return _FakeSMTP.instances


def test_send_email_goes_over_smtp_when_it_is_configured(smtp):
    result = email_service.send_email(
        to="jane@school.edu",
        subject="Hello",
        html="<p>Hello</p>",
        text="Hello",
        attachments=[email_service.pdf_attachment("guide.pdf", b"%PDF-1.4 test")],
    )

    assert result.delivered is True
    assert result.provider_id, "an SMTP send still needs an id to log and trace"

    client = smtp[0]
    assert (client.host, client.port) == ("smtp.gmail.com", 587)
    assert client.started_tls is True
    # Google displays the App Password in groups of four; the spaces are not
    # part of the password, and pasting it with them is the usual bad login.
    assert client.credentials == ("clearisinfo@gmail.com", "abcdefghijklmnop")

    message = client.message
    assert message["From"] == "clearisinfo@gmail.com"
    assert message["To"] == "jane@school.edu"
    assert message["Reply-To"] == "clearisinfo@gmail.com"

    # A whole message, not just the HTML part: both bodies and the PDF.
    kinds = {part.get_content_type() for part in message.walk()}
    assert {"text/plain", "text/html", "application/pdf"} <= kinds
    pdf = next(p for p in message.walk() if p.get_content_type() == "application/pdf")
    assert pdf.get_filename() == "guide.pdf"
    assert pdf.get_payload(decode=True).startswith(b"%PDF")


def test_smtp_from_can_carry_a_display_name(smtp, monkeypatch):
    monkeypatch.setattr(settings, "smtp_from", "Clearis <clearisinfo@gmail.com>")

    email_service.send_email(to="jane@school.edu", subject="Hi", html="<p>Hi</p>")

    assert smtp[0].message["From"] == "Clearis <clearisinfo@gmail.com>"


def test_smtp_rejects_a_bad_app_password_with_a_named_error(smtp, monkeypatch):
    """This failure is almost always the App Password, so the error says so
    instead of leaving a generic 502 to be debugged from the server logs."""

    class _Rejecting(_FakeSMTP):
        def login(self, user, password):
            raise smtplib.SMTPAuthenticationError(
                535, b"Username and Password not accepted"
            )

    monkeypatch.setattr(email_service.smtplib, "SMTP", _Rejecting)

    with pytest.raises(email_service.EmailSendError) as excinfo:
        email_service.send_email(to="jane@school.edu", subject="Hi", html="<p>Hi</p>")

    assert excinfo.value.status_code == 502
    assert "App Password" in excinfo.value.message


def test_auto_transport_prefers_smtp_and_falls_back_to_resend(monkeypatch):
    monkeypatch.setattr(settings, "email_transport", "auto")
    monkeypatch.setattr(settings, "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(settings, "smtp_user", "clearisinfo@gmail.com")
    monkeypatch.setattr(settings, "smtp_password", "app-password")
    monkeypatch.setattr(settings, "resend_api_key", "re_key")
    assert email_service._transport() == "smtp"

    # A half-filled SMTP block must not shadow a working Resend key.
    monkeypatch.setattr(settings, "smtp_password", "")
    assert email_service._transport() == "resend"

    monkeypatch.setattr(settings, "resend_api_key", "")
    assert email_service._transport() is None


def test_pinning_a_transport_without_credentials_is_not_configured(monkeypatch):
    """EMAIL_TRANSPORT=smtp with nothing to log in as has to fail loudly — it
    must not quietly fall through to Resend and send from another address."""
    monkeypatch.setattr(settings, "email_transport", "smtp")
    monkeypatch.setattr(settings, "dev_email", False)
    monkeypatch.setattr(settings, "resend_api_key", "re_key")

    assert email_service._transport() is None
    with pytest.raises(EmailNotConfiguredError):
        email_service.send_email(
            to="jane@school.edu", subject="Test", html="<p>Hello</p>"
        )
