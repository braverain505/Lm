"""Transactional email (receipts to guardians) via Resend's HTTP API.

Deliberately talks to the provider over ``httpx`` — already a runtime dependency
and already used for the Groq client — instead of pulling in a vendor SDK, so
enabling receipts-by-email needs a key and nothing else installed.

Degradation is explicit, never silent:

* **No key, development** (``dev_email=True``): the email is logged and reported
  as ``delivered=False, dev_skipped=True`` so local work keeps moving.
* **No key, production**: :class:`EmailNotConfiguredError` (503). A receipt that
  was never sent must not look sent.
* **Provider error**: :class:`EmailSendError` (502) with the provider's message.

The HTML is written with inline styles and tables because email clients strip
stylesheets; it mirrors the printed receipt so a guardian sees the same document.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from html import escape

import httpx

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


def is_configured() -> bool:
    return bool(settings.resend_api_key)


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
) -> EmailResult:
    """Send one transactional email. See the module docstring for degradation."""
    to = (to or "").strip()
    if not to:
        raise APIError(422, "ERR_VALIDATION", "A recipient email address is required")

    if not is_configured():
        if settings.dev_email:
            logger.info(
                "[dev-email] suppressed email to %s (subject=%r). "
                "Set RESEND_API_KEY to actually send.",
                to,
                subject,
            )
            return EmailResult(delivered=False, dev_skipped=True)
        raise EmailNotConfiguredError()

    payload: dict = {
        "from": settings.email_from,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if text:
        payload["text"] = text
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
    logger.info("Receipt email sent to %s (provider id=%s)", to, provider_id)
    return EmailResult(delivered=True, provider_id=provider_id)


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
