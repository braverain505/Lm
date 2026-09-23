"""Transactional email (receipts, school onboarding, password resets).

Two transports, selected by ``EMAIL_TRANSPORT`` (``auto`` by default):

* **SMTP** (:mod:`smtplib`, stdlib) — how the platform's own mail leaves. The
  new school's welcome message and the internal new-school notice both go out
  from the Clearis inbox, which is a Gmail account with an App Password. That
  needs no vendor account and no verified domain.
* **Resend's HTTP API** — for a deployment that has a verified domain and a
  key. Talks to the provider over ``httpx`` — already a runtime dependency and
  already used for the Groq client — instead of pulling in a vendor SDK, so
  enabling receipts-by-email needs a key and nothing else installed. SMTP needs
  no dependency at all: everything it uses ships with Python.

On a host that blocks outbound SMTP (Render's free web services block ports
25, 465 and 587) the SMTP transport cannot work at all — the connection never
leaves the machine and fails as ``OSError`` / ``[Errno 101] Network is
unreachable``. Nothing about the account or its App Password is at fault and no
setting changes it. Pin ``EMAIL_TRANSPORT=resend`` there: the HTTP transport is
plain HTTPS on 443 and is unaffected.

Degradation is explicit, never silent:

* **No transport configured, development** (``dev_email=True``): the email is
  logged and reported as ``delivered=False, dev_skipped=True`` so local work
  keeps moving.
* **No transport configured, production**: :class:`EmailNotConfiguredError`
  (503). A receipt that was never sent must not look sent.
* **Provider error**: :class:`EmailSendError` (502) with the provider's message.

The HTML is written with inline styles and tables because email clients strip
stylesheets; it mirrors the printed receipt so a guardian sees the same document.

The onboarding guide is a PDF (``reportlab``) rather than a link, so a new school
admin keeps the setup steps even when the app is unreachable.
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from html import escape
from io import BytesIO
from urllib.parse import quote

import httpx
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import settings
from ..core.errors import APIError, ERR_EMAIL_SEND_FAILED, EmailNotConfiguredError

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"

CURRENCY_SYMBOLS: dict[str, str] = {
    "NGN": "₦",
    "USD": "$",
    "GBP": "£",
    "EUR": "€",
}


class EmailSendError(APIError):
    """The provider accepted the request but refused to send."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(502, ERR_EMAIL_SEND_FAILED, message, details)


@dataclass
class EmailResult:
    delivered: bool
    provider_id: str | None = None
    dev_skipped: bool = False


def _transport() -> str | None:
    """Which transport can send right now: ``"smtp"``, ``"resend"`` or ``None``.

    ``EMAIL_TRANSPORT`` pins one; ``auto`` prefers SMTP when it is fully
    configured, then Resend. SMTP counts as configured only with a host, a user
    *and* a password: a half-filled block would otherwise be chosen over a
    working Resend key and fail on every send.
    """
    smtp_ready = bool(
        settings.smtp_host and settings.smtp_user and settings.smtp_password
    )
    choice = settings.email_transport
    if choice == "smtp":
        return "smtp" if smtp_ready else None
    if choice == "resend":
        return "resend" if settings.resend_api_key else None
    if smtp_ready:
        return "smtp"
    return "resend" if settings.resend_api_key else None


def is_configured() -> bool:
    return _transport() is not None


def money(amount: float | None, currency: str = "NGN") -> str:
    symbol = CURRENCY_SYMBOLS.get((currency or "NGN").upper(), "")
    value = float(amount or 0)
    return f"{symbol}{value:,.2f}"


def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    reply_to: str | None = None,
    attachments: list[dict] | None = None,
) -> EmailResult:
    """Send one transactional email. See the module docstring for degradation.

    ``attachments`` is passed through to the provider as-is; use
    :func:`pdf_attachment` to build one.
    """
    to = (to or "").strip()
    if not to:
        raise APIError(422, "ERR_VALIDATION", "A recipient email address is required")

    transport = _transport()
    if transport is None:
        if settings.dev_email:
            logger.info(
                "[dev-email] suppressed email to %s (subject=%r). "
                "Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD (or RESEND_API_KEY) to "
                "actually send.",
                to,
                subject,
            )
            return EmailResult(delivered=False, dev_skipped=True)
        raise EmailNotConfiguredError()

    if transport == "smtp":
        return _send_via_smtp(
            to=to,
            subject=subject,
            html=html,
            text=text,
            reply_to=reply_to,
            attachments=attachments,
        )

    payload: dict = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
    if attachments:
        payload["attachments"] = attachments
    reply = reply_to or settings.email_reply_to
    if reply:
        payload["reply_to"] = reply

    try:
        with httpx.Client(timeout=settings.email_timeout_seconds) as client:
            resp = client.post(
                RESEND_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {settings.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.TimeoutException as exc:
        logger.warning("Email send timed out (to=%s)", to)
        raise EmailSendError("The email provider timed out. Try again.") from exc
    except httpx.HTTPError as exc:
        logger.warning("Email send failed: %s", exc)
        raise EmailSendError("Could not reach the email provider.") from exc

    if resp.status_code >= 400:
        # The provider's body is safe to surface (it describes *our* request, not
        # anyone's data), but log it rather than echoing it into the API error.
        logger.warning(
            "Email provider returned HTTP %s: %s", resp.status_code, resp.text[:300]
        )
        raise EmailSendError(
            "The email provider rejected the message.",
            {"status": resp.status_code},
        )

    try:
        provider_id = resp.json().get("id")
    except ValueError:
        provider_id = None
    logger.info("Email sent to %s (provider id=%s)", to, provider_id)
    return EmailResult(delivered=True, provider_id=provider_id)


def _smtp_from_header() -> str:
    """``Clearis <clearisinfo@gmail.com>`` unless SMTP_FROM overrides it.

    Gmail only lets an authenticated account send as itself or a verified
    alias, so the default is the account we log in as.
    """
    return (settings.smtp_from or "").strip() or settings.smtp_user


def _send_via_smtp(
    *,
    to: str,
    subject: str,
    html: str,
    text: str | None,
    reply_to: str | None,
    attachments: list[dict] | None,
) -> EmailResult:
    """Send one message over SMTP, with the same failure contract as Resend."""
    message = EmailMessage()
    message["From"] = _smtp_from_header()
    message["To"] = to
    message["Subject"] = subject
    reply = reply_to or settings.email_reply_to
    if reply:
        # Where a recipient's reply lands. The onboarding mail leaves from the
        # Clearis inbox, so this is what makes "just reply to this email" true.
        message["Reply-To"] = reply
    message_id = make_msgid()
    message["Message-ID"] = message_id
    message.set_content(text or "This message needs an HTML-capable email client.")
    message.add_alternative(html, subtype="html")

    for attachment in attachments or []:
        filename = attachment.get("filename") or "attachment"
        # Resend payloads carry base64; SMTP wants the bytes themselves.
        content = base64.b64decode(attachment.get("content") or "")
        guessed, _ = mimetypes.guess_type(filename)
        maintype, _, subtype = (guessed or "application/octet-stream").partition(
            "/"
        )
        message.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype or "octet-stream",
            filename=filename,
        )

    # Google displays App Passwords in groups of four; the spaces are not part
    # of the password, and pasting it with them is the usual reason login fails.
    password = settings.smtp_password.replace(" ", "")
    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as client:
            client.ehlo()
            if settings.smtp_starttls:
                client.starttls()
                client.ehlo()
            client.login(settings.smtp_user, password)
            client.send_message(message)
    except smtplib.SMTPAuthenticationError as exc:
        # Worth naming precisely: this one is almost always the App Password.
        logger.warning("SMTP authentication failed for %s", settings.smtp_user)
        raise EmailSendError(
            "The mail account rejected its credentials. Check SMTP_USER and the "
            "App Password in SMTP_PASSWORD.",
            {"provider": "smtp", "status": exc.smtp_code},
        ) from exc
    except smtplib.SMTPRecipientsRefused as exc:
        logger.warning("SMTP refused every recipient for %s", to)
        raise EmailSendError(
            "The mail provider refused the recipient.",
            {"provider": "smtp", "status": exc.smtp_code},
        ) from exc
    except smtplib.SMTPException as exc:
        logger.warning("SMTP send failed: %s", exc)
        raise EmailSendError(
            "The mail provider rejected the message.", {"provider": "smtp"}
        ) from exc
    except OSError as exc:
        logger.warning("SMTP connection failed: %s", exc)
        raise EmailSendError("Could not reach the mail provider.") from exc

    logger.info("Email sent to %s over SMTP (message id=%s)", to, message_id)
    return EmailResult(delivered=True, provider_id=message_id)


def pdf_attachment(filename: str, content: bytes) -> dict:
    """Wrap raw PDF bytes as an attachment payload (base64, Resend-shaped).

    The SMTP path decodes the same shape, so callers never care which
    transport ends up sending the message.
    """
    return {
        "filename": filename,
        "content": base64.b64encode(content).decode("ascii"),
    }


# ──────────────────────────────────────────────────────────────────────
# Receipt email body
# ──────────────────────────────────────────────────────────────────────


def _row(label: str, value: str, *, strong: bool = False) -> str:
    weight = "600" if strong else "400"
    return (
        f'<tr>'
        f'<td style="padding:6px 0;color:#64748b;font-size:13px;">{escape(label)}</td>'
        f'<td style="padding:6px 0;text-align:right;font-size:13px;font-weight:{weight};'
        f'color:#0f172a;">{escape(value)}</td>'
        f"</tr>"
    )


def build_receipt_email(receipt: dict) -> tuple[str, str, str]:
    """Render (subject, html, text) for a receipt payload from the fees service."""
    school = receipt.get("school") or {}
    student = receipt.get("student") or {}
    currency = school.get("currency") or "NGN"
    school_name = school.get("name") or "School"
    receipt_no = receipt.get("receipt_number") or "—"
    balance = float(receipt.get("balance_due") or 0)

    subject = f"Payment receipt {receipt_no} — {school_name}"

    payments = receipt.get("invoice_payments") or []
    payment_rows = "".join(
        "<tr>"
        f'<td style="padding:6px 8px;border-top:1px solid #e2e8f0;font-size:12px;">'
        f'{escape(str(p.get("receipt_number") or "—"))}</td>'
        f'<td style="padding:6px 8px;border-top:1px solid #e2e8f0;font-size:12px;">'
        f'{escape(str(p.get("payment_date") or "—"))}</td>'
        f'<td style="padding:6px 8px;border-top:1px solid #e2e8f0;font-size:12px;'
        f'text-transform:capitalize;">{escape(str(p.get("payment_method") or ""))}</td>'
        f'<td style="padding:6px 8px;border-top:1px solid #e2e8f0;font-size:12px;'
        f'text-align:right;">{escape(money(p.get("amount"), currency))}</td>'
        "</tr>"
        for p in payments
    )

    contact_bits = " · ".join(
        escape(str(v)) for v in (school.get("phone"), school.get("email")) if v
    )

    html = f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f1f5f9;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:12px;border:1px solid #e2e8f0;">
      <tr>
        <td style="padding:24px 28px;border-bottom:1px solid #e2e8f0;">
          <div style="font-size:18px;font-weight:700;color:#0f172a;">{escape(str(school_name))}</div>
          <div style="font-size:12px;color:#64748b;margin-top:4px;">{escape(str(school.get("address") or ""))}</div>
          {f'<div style="font-size:12px;color:#64748b;">{contact_bits}</div>' if contact_bits else ''}
        </td>
      </tr>
      <tr>
        <td style="padding:24px 28px;">
          <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;">Official receipt</div>
          <div style="font-size:26px;font-weight:700;color:#0f172a;margin-top:4px;">
            {escape(money(receipt.get("amount_paid"), currency))}
          </div>
          <div style="font-size:13px;color:#64748b;margin-top:4px;">
            Receipt no. <strong style="color:#0f172a;">{escape(str(receipt_no))}</strong>
            {f' · {escape(str(receipt.get("payment_date") or ""))}' if receipt.get("payment_date") else ''}
          </div>

          <table role="presentation" width="100%" style="margin-top:20px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;">
            <tr>
              <td style="padding:14px 16px;">
                <div style="font-size:11px;text-transform:uppercase;color:#64748b;">Student</div>
                <div style="font-size:14px;font-weight:600;color:#0f172a;">{escape(str(student.get("full_name") or ""))}</div>
                <div style="font-size:12px;color:#64748b;">{escape(str(student.get("admission_no") or ""))}</div>
              </td>
              <td style="padding:14px 16px;">
                <div style="font-size:11px;text-transform:uppercase;color:#64748b;">Invoice</div>
                <div style="font-size:13px;font-weight:600;color:#0f172a;font-family:ui-monospace,Menlo,monospace;">{escape(str(receipt.get("invoice_reference") or ""))}</div>
                <div style="font-size:12px;color:#64748b;">{escape(str(receipt.get("fee_structure_name") or "Fee"))}</div>
              </td>
            </tr>
          </table>

          <div style="font-size:11px;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;margin:22px 0 6px;">Payments received</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            <tr>
              <th align="left" style="font-size:11px;color:#94a3b8;font-weight:600;padding:0 8px 6px;">Receipt no.</th>
              <th align="left" style="font-size:11px;color:#94a3b8;font-weight:600;padding:0 8px 6px;">Date</th>
              <th align="left" style="font-size:11px;color:#94a3b8;font-weight:600;padding:0 8px 6px;">Method</th>
              <th align="right" style="font-size:11px;color:#94a3b8;font-weight:600;padding:0 8px 6px;">Amount</th>
            </tr>
            {payment_rows or '<tr><td colspan="4" style="padding:10px 8px;font-size:12px;color:#94a3b8;">No payments recorded on this invoice.</td></tr>'}
          </table>

          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:22px;border-top:1px solid #e2e8f0;">
            {_row("Amount paid", money(receipt.get("paid_total"), currency))}
            {_row("Invoice total", money(receipt.get("invoice_total"), currency))}
            {_row("Balance due", money(receipt.get("balance_due"), currency), strong=True)}
          </table>
          <div style="font-size:12px;color:{'#dc2626' if balance > 0 else '#16a34a'};margin-top:6px;">
            {'Outstanding balance of ' + escape(money(balance, currency)) + ' remains on this invoice.' if balance > 0 else 'This invoice is fully settled. Thank you.'}
          </div>
        </td>
      </tr>
      <tr>
        <td style="padding:18px 28px;border-top:1px solid #e2e8f0;font-size:11px;color:#94a3b8;text-align:center;">
          Generated by Clearis on behalf of {escape(str(school_name))}.
        </td>
      </tr>
    </table>
  </body>
</html>"""

    text = "\n".join(
        [
            f"{school_name} — Official receipt",
            f"Receipt no.: {receipt_no}",
            f"Date: {receipt.get('payment_date') or ''}",
            f"Student: {student.get('full_name')} ({student.get('admission_no')})",
            f"Invoice: {receipt.get('invoice_reference')}",
            f"Amount paid: {money(receipt.get('paid_total'), currency)}",
            f"Invoice total: {money(receipt.get('invoice_total'), currency)}",
            f"Balance due: {money(receipt.get('balance_due'), currency)}",
            "",
            "Generated by Clearis.",
        ]
    )

    return subject, html, text


# ──────────────────────────────────────────────────────────────────────
# Shared frame for the plain announcement emails (welcome, password reset)
# ──────────────────────────────────────────────────────────────────────

BRAND_COLOR = "#1659e9"  # matches --primary in the web app
MUTED = "#64748b"
BORDER = "#e2e8f0"


def _email_shell(*, eyebrow: str, heading: str, body_html: str, footer: str) -> str:
    """One card, one column — inline styles because clients strip stylesheets."""
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#f1f5f9;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;border:1px solid {BORDER};">
      <tr>
        <td style="padding:22px 28px;border-bottom:1px solid {BORDER};">
          <span style="font-size:16px;font-weight:700;color:#0f172a;">Clearis</span>
        </td>
      </tr>
      <tr>
        <td style="padding:26px 28px;">
          <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:{MUTED};">{escape(eyebrow)}</div>
          <div style="font-size:22px;font-weight:700;color:#0f172a;margin-top:6px;line-height:1.3;">{escape(heading)}</div>
          {body_html}
        </td>
      </tr>
      <tr>
        <td style="padding:18px 28px;border-top:1px solid {BORDER};font-size:11px;color:#94a3b8;text-align:center;">
          {footer}
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _button(label: str, url: str) -> str:
    return (
        f'<a href="{escape(url, quote=True)}" style="display:inline-block;margin-top:22px;'
        f'padding:12px 22px;background:{BRAND_COLOR};color:#ffffff;text-decoration:none;'
        f'border-radius:8px;font-size:14px;font-weight:600;">{escape(label)}</a>'
    )


def _paragraph(html_text: str) -> str:
    return f'<p style="margin:14px 0 0;font-size:13.5px;line-height:1.65;color:#334155;">{html_text}</p>'


def _bullets(items: list[str]) -> str:
    rows = "".join(
        f'<li style="margin:6px 0;">{item}</li>' for item in items
    )
    return (
        '<ul style="margin:14px 0 0;padding-left:20px;font-size:13.5px;line-height:1.6;color:#334155;">'
        f"{rows}</ul>"
    )


# ──────────────────────────────────────────────────────────────────────
# Onboarding guide (PDF attachment for the welcome email)
# ──────────────────────────────────────────────────────────────────────

# (step title, what to do). Ordered: each step needs the previous one to exist.
SETUP_STEPS: list[tuple[str, str]] = [
    (
        "Open your dashboard",
        "Sign in with the details above. Everything below happens inside your own "
        "workspace — other schools cannot see any of it.",
    ),
    (
        "Create your academic session and term",
        "Add the current session (for example 2026/2027) and its terms. Results, "
        "fees, timetables and report cards are all scoped to a term, so this has to "
        "come first.",
    ),
    (
        "Create your classes",
        'One entry per class arm you actually teach — "JSS 1A", "JSS 1B", "SS 2 '
        'Science". Each arm becomes the home for its students and its subjects.',
    ),
    (
        "Add your subjects",
        "Add each subject once, then attach it to the class arms that take it.",
    ),
    (
        "Add your teachers",
        "Invite each staff member with their email address. They set their own "
        "password from the invitation, so you never share one.",
    ),
    (
        "Assign a role to each person",
        "Access comes from the role, not the individual. Change someone's role "
        "later and their permissions follow — you never rebuild the account.",
    ),
    (
        "Add your students",
        "Import a spreadsheet or add students one by one, then place each one in "
        "their class arm for the term.",
    ),
    (
        "Set up fees and grading",
        "Create the fee structure per class, record payments against invoices, and "
        "set the grading scale your report cards should use.",
    ),
]

# (role, what it is for) — mirrors ROLE_TEMPLATES in app/core/permissions.py.
ROLE_GUIDE: list[tuple[str, str]] = [
    ("School Admin", "You. Full control of the workspace, including roles and settings."),
    ("Director", "School-wide oversight of academics, staff, fees and reporting."),
    ("Principal", "Approves results, manages academics and staff, prints report cards."),
    ("VP Academics", "Manages the academic structure and the results pipeline."),
    ("VP Admin", "Runs the administrative side: staff accounts, campuses, settings."),
    ("Head Teacher", "Supervises teaching, verifies results, keeps the whole roster."),
    ("Academic Coordinator", "Builds and maintains the subject and class structure."),
    ("Exam Officer", "Owns results end to end: verify, approve, publish, print cards."),
    ("Teacher", "Enters scores for the classes they are assigned. Sees only those."),
    ("Homeroom Teacher", "A teacher who also keeps attendance and remarks for their arm."),
    ("Accountant", "The ledger: receipts, expenses, reconciliation and payroll."),
    ("Bursar", "Invoices and payments, plus a read of the accounts."),
    ("Librarian", "Catalogues and lends library stock."),
    ("Admission Officer", "Adds and enrols new students."),
    ("Secretary", "Reads records and sends school-wide communication."),
    ("Parent", "Read-only result access through the school's result portal code."),
    ("Student", "Read-only access through the result portal."),
]


def build_setup_guide_pdf(
    *, school_name: str, admin_email: str, sign_in_url: str
) -> bytes:
    """Render the 'Getting started' document attached to the welcome email.

    Returns raw PDF bytes; callers wrap it with :func:`pdf_attachment`.
    """
    title = ParagraphStyle(
        "GuideTitle",
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=colors.HexColor("#0f172a"),
    )
    lede = ParagraphStyle(
        "GuideLede",
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#475569"),
        spaceBefore=4,
    )
    heading = ParagraphStyle(
        "GuideHeading",
        fontName="Helvetica-Bold",
        fontSize=11.5,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=16,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "GuideBody",
        fontName="Helvetica",
        fontSize=9.8,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=2,
    )
    step_title = ParagraphStyle(
        "GuideStepTitle",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
    )

    story: list = [
        Paragraph("Getting started with Clearis", title),
        Paragraph(escape(school_name), lede),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor(BORDER)),
        Paragraph("Your account", heading),
        Paragraph(f"<b>Username (your email):</b> {escape(admin_email)}", body),
        Paragraph(f"<b>Sign in at:</b> {escape(sign_in_url)}", body),
        Paragraph("Set up your school", heading),
        Paragraph(
            "Work through these in order — each one builds on the one before it.",
            body,
        ),
    ]

    story.append(
        ListFlowable(
            [
                ListItem(
                    [
                        Paragraph(escape(step), step_title),
                        Paragraph(escape(detail), body),
                    ],
                    leftIndent=16,
                )
                for step, detail in SETUP_STEPS
            ],
            bulletType="1",
            bulletFontName="Helvetica-Bold",
            bulletFontSize=9.5,
            bulletColor=colors.HexColor(MUTED),
            leftIndent=16,
            bulletDedent=16,
            spaceBefore=4,
        )
    )

    story.append(Paragraph("Roles at a glance", heading))
    story.append(
        Paragraph(
            "Pick the role that matches the job when you invite someone. "
            "Permissions come from the role, so this is the only access decision "
            "you have to make.",
            body,
        )
    )
    table_data = [
        [
            Paragraph(f"<b>{escape(role)}</b>", body),
            Paragraph(escape(purpose), body),
        ]
        for role, purpose in ROLE_GUIDE
    ]
    table = Table(table_data, colWidths=[46 * mm, 128 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#f1f5f9")),
            ]
        )
    )
    story.append(table)

    story.append(Paragraph("Where to find help", heading))
    story.append(
        Paragraph(
            "Reply to this email and it reaches a person. Inside the app, the "
            "AI copilot answers questions about your own data, and every list "
            "screen has an import option for bringing existing records across.",
            body,
        )
    )
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(BORDER)))
    story.append(
        Paragraph(
            f'<font color="{MUTED}" size="8">Generated by Clearis for '
            f"{escape(school_name)}.</font>",
            body,
        )
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Getting started with Clearis — {school_name}",
        author="Clearis",
    )
    doc.build(story)
    return buffer.getvalue()


# ──────────────────────────────────────────────────────────────────────
# Welcome email (sent once, when a school finishes registering)
# ──────────────────────────────────────────────────────────────────────

NEXT_STEPS_SUMMARY = [
    "Create your academic session and current term.",
    "Add your classes and the subjects each one takes.",
    "Invite your teachers and give each one the role that matches their job.",
    "Add your students and place them in their class arms.",
]


def build_welcome_email(
    *, school_name: str, admin_full_name: str, admin_email: str, password: str
) -> tuple[str, str, str, list[dict]]:
    """Render (subject, html, text, attachments) for a new school admin."""
    sign_in_url = f"{settings.web_base_url}/login"
    dashboard_url = f"{settings.web_base_url}/dashboard"
    first_name = (admin_full_name or "there").strip().split(" ")[0] or "there"
    guide_name = "Clearis-Getting-Started.pdf"

    subject = f"Your {school_name} workspace on Clearis is ready"

    credentials = (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:18px;background:#f8fafc;border:1px solid '
        f'{BORDER};border-radius:10px;">'
        '<tr><td style="padding:16px 18px;">'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:0.08em;color:{MUTED};">Your sign-in details</div>'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;">'
        '<tr>'
        f'<td style="padding:4px 0;font-size:13px;color:{MUTED};">Username</td>'
        '<td style="padding:4px 0;text-align:right;font-size:13px;font-weight:600;color:#0f172a;'
        f'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">{escape(admin_email)}</td>'
        '</tr><tr>'
        f'<td style="padding:4px 0;font-size:13px;color:{MUTED};">Password</td>'
        '<td style="padding:4px 0;text-align:right;font-size:13px;font-weight:600;color:#0f172a;'
        f'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;">{escape(password)}</td>'
        '</tr></table></td></tr></table>'
    )

    body_html = "".join(
        [
            _paragraph(
                f"Welcome, {escape(first_name)}. Your school workspace for "
                f"<b>{escape(school_name)}</b> has been created, and this account "
                "is the owner of it."
            ),
            credentials,
            _paragraph(
                "Next, open your dashboard and set the school up. Everything on "
                "Clearis — results, fees, attendance, report cards — is built on "
                "the structure you create here:"
            ),
            _bullets([escape(item) for item in NEXT_STEPS_SUMMARY]),
            _button("Open your dashboard", dashboard_url),
            _paragraph(
                f"We have attached <b>{escape(guide_name)}</b> — a step-by-step "
                "guide to the setup order and what each staff role can do. Keep "
                "it with this email."
            ),
            _paragraph(
                f'<span style="color:{MUTED};font-size:12.5px;">For your security, '
                "change this password from Settings once you have signed in. "
                "Nobody at Clearis will ever ask you for it.</span>"
            ),
        ]
    )

    html = _email_shell(
        eyebrow="Welcome aboard",
        heading=f"{school_name} is ready",
        body_html=body_html,
        footer=(
            "You are receiving this because a Clearis workspace was registered "
            f"with this address.<br />Sign in at {escape(sign_in_url)}"
        ),
    )

    text = "\n".join(
        [
            f"Welcome, {first_name}.",
            f"Your Clearis workspace for {school_name} has been created.",
            "",
            "Your sign-in details",
            f"  Username: {admin_email}",
            f"  Password: {password}",
            f"  Sign in:  {sign_in_url}",
            "",
            "What to do next:",
            *[f"  - {item}" for item in NEXT_STEPS_SUMMARY],
            "",
            f"We have attached {guide_name} with the full setup guide.",
            "Change your password from Settings once you have signed in.",
        ]
    )

    attachments = [
        pdf_attachment(
            guide_name,
            build_setup_guide_pdf(
                school_name=school_name,
                admin_email=admin_email,
                sign_in_url=sign_in_url,
            ),
        )
    ]
    return subject, html, text, attachments


def send_school_welcome_email(
    *,
    school_name: str,
    admin_full_name: str,
    admin_email: str,
    password: str,
) -> EmailResult | None:
    """Send the onboarding email to a newly registered school admin.

    Never raises: the registration has already committed by this point, so a
    mail outage must not turn a successful signup into an error page. Failures
    are logged loudly so they can be re-sent.
    """
    try:
        subject, html, text, attachments = build_welcome_email(
            school_name=school_name,
            admin_full_name=admin_full_name,
            admin_email=admin_email,
            password=password,
        )
        return send_email(
            to=admin_email,
            subject=subject,
            html=html,
            text=text,
            attachments=attachments,
        )
    except APIError as exc:
        logger.error(
            "Welcome email for %s (%s) was not sent: %s — re-send manually.",
            admin_email,
            school_name,
            exc.message,
        )
    except Exception:  # pragma: no cover - defensive; rendering should not fail
        logger.exception(
            "Unexpected error building the welcome email for %s (%s).",
            admin_email,
            school_name,
        )
    return None


# ──────────────────────────────────────────────────────────────────────
# New-school notice (internal — the platform owner, never the school)
# ──────────────────────────────────────────────────────────────────────


def _detail(label: str, value: str) -> str:
    """One label/value row of the alert's details table."""
    return (
        "<tr>"
        f'<td style="padding:4px 0;font-size:13px;color:{MUTED};">{escape(label)}</td>'
        '<td style="padding:4px 0;text-align:right;font-size:13px;font-weight:600;'
        f'color:#0f172a;">{escape(value)}</td>'
        "</tr>"
    )


def build_new_school_alert(
    *,
    school_name: str,
    school_type: str,
    admin_full_name: str,
    admin_email: str,
    location: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    established_year: int | None = None,
    welcome_email_sent: bool = True,
) -> tuple[str, str, str]:
    """Render (subject, html, text) for "a school just registered".

    Deliberately carries no password: the welcome email is where the admin's
    credentials belong, and an internal alert would otherwise leave a working
    password sitting in an inbox long after the school changed it.
    """
    subject = f"New school registered: {school_name}"

    rows = "".join(
        _detail(label, value)
        for label, value in (
            ("School", school_name),
            ("Type", school_type),
            ("Admin", admin_full_name),
            ("Admin email", admin_email),
            ("Location", location or "—"),
            ("Phone", phone or "—"),
            ("Website", website or "—"),
            ("Established", str(established_year) if established_year else "—"),
        )
    )

    body_html = "".join(
        [
            _paragraph(
                f"<b>{escape(school_name)}</b> has just registered a Clearis "
                "workspace and is being set up by the admin below."
            ),
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            'style="margin-top:18px;background:#f8fafc;border:1px solid '
            f'{BORDER};border-radius:10px;"><tr><td style="padding:16px 18px;">'
            f'<table role="presentation" width="100%" cellpadding="0" '
            f'cellspacing="0">{rows}</table></td></tr></table>',
            _paragraph(
                f'<span style="color:{MUTED};font-size:12.5px;">'
                + (
                    "The welcome email with their sign-in details reached them."
                    if welcome_email_sent
                    else "<b>Their welcome email was not delivered</b> — worth "
                    "following up so they do not wait on credentials that "
                    "never arrived."
                )
                + "</span>"
            ),
            _button("Open the platform admin", f"{settings.web_base_url}/admin"),
        ]
    )

    html = _email_shell(
        eyebrow="New registration",
        heading=school_name,
        body_html=body_html,
        footer="An internal notice from Clearis. Not sent to the school.",
    )

    text = "\n".join(
        [
            f"New school registered: {school_name}",
            "",
            f"  Type:        {school_type}",
            f"  Admin:       {admin_full_name} <{admin_email}>",
            f"  Location:    {location or '—'}",
            f"  Phone:       {phone or '—'}",
            f"  Website:     {website or '—'}",
            f"  Established: {established_year or '—'}",
            "",
            (
                "The welcome email with their sign-in details reached them."
                if welcome_email_sent
                else "Their welcome email was NOT delivered — follow up."
            ),
        ]
    )
    return subject, html, text


def send_new_school_alert(
    *,
    school_name: str,
    school_type: str,
    admin_full_name: str,
    admin_email: str,
    location: str | None = None,
    phone: str | None = None,
    website: str | None = None,
    established_year: int | None = None,
    welcome_email_sent: bool = True,
) -> EmailResult | None:
    """Tell the platform owner that a school registered.

    Never raises, for the same reason as the welcome email: the workspace is
    already committed by this point, so a mail outage must not turn a
    successful signup into an error page. Returns ``None`` when no alert
    address is configured.
    """
    recipient = (settings.owner_alert_email or "").strip()
    if not recipient:
        return None
    try:
        subject, html, text = build_new_school_alert(
            school_name=school_name,
            school_type=school_type,
            admin_full_name=admin_full_name,
            admin_email=admin_email,
            location=location,
            phone=phone,
            website=website,
            established_year=established_year,
            welcome_email_sent=welcome_email_sent,
        )
        return send_email(to=recipient, subject=subject, html=html, text=text)
    except APIError as exc:
        logger.error(
            "New-school alert for %s was not sent: %s", school_name, exc.message
        )
    except Exception:  # pragma: no cover - defensive; rendering should not fail
        logger.exception("Unexpected error building the new-school alert for %s.", school_name)
    return None


# ──────────────────────────────────────────────────────────────────────
# Password reset email
# ──────────────────────────────────────────────────────────────────────


def build_password_reset_email(full_name: str | None, reset_url: str) -> tuple[str, str, str]:
    """Render (subject, html, text) for a password-reset link."""
    first_name = (full_name or "there").strip().split(" ")[0] or "there"
    subject = "Reset your Clearis password"

    body_html = "".join(
        [
            _paragraph(
                f"Hello {escape(first_name)}, we received a request to reset the "
                "password on your Clearis account."
            ),
            _button("Choose a new password", reset_url),
            _paragraph(
                f'<span style="color:{MUTED};font-size:12.5px;">This link works once '
                "and expires in one hour. If you did not ask for it, you can ignore "
                "this email — your current password still works.</span>"
            ),
            _paragraph(
                f'<span style="color:{MUTED};font-size:12.5px;">Button not working? '
                f"Paste this into your browser:<br /><br />"
                f'<span style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace;'
                f'word-break:break-all;">{escape(reset_url)}</span></span>'
            ),
        ]
    )

    html = _email_shell(
        eyebrow="Password reset",
        heading="Choose a new password",
        body_html=body_html,
        footer="Clearis never emails you a password. Reset links are single-use.",
    )

    text = "\n".join(
        [
            f"Hello {first_name},",
            "We received a request to reset the password on your Clearis account.",
            "",
            f"Choose a new password: {reset_url}",
            "",
            "This link works once and expires in one hour.",
            "If you did not ask for it, ignore this email — your password still works.",
        ]
    )
    return subject, html, text


def send_password_reset_email(
    *, to: str, full_name: str | None, token: str
) -> EmailResult:
    """Send the reset link.

    Deliberately does **not** swallow provider failures: the API answers with the
    same neutral message either way, so a reset that was never delivered would
    otherwise look delivered and leave the user waiting for a mail that is not
    coming. See the module docstring for the degradation rules.
    """
    reset_url = f"{settings.web_base_url}/reset-password?token={quote(token)}"
    subject, html, text = build_password_reset_email(full_name, reset_url)
    return send_email(to=to, subject=subject, html=html, text=text)
