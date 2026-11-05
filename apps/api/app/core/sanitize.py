"""Input sanitization utilities for preventing XSS attacks.

Both helpers strip markup. They do not entity-encode the result — escaping is
the job of whatever renders the value, and every renderer here already does it
(React text nodes, ``escape()`` in the email templates). Escaping on write only
stores ``Dan&#x27;azumi`` where the user typed ``Dan'azumi``.
"""
import re


def sanitize_html(text: str | None) -> str | None:
    """Remove all HTML tags.

    Used for fields that should not contain any HTML at all.
    """
    if text is None:
        return None
    return re.sub(r"<[^>]+>", "", text)


def sanitize_text_input(text: str | None) -> str | None:
    """Strip markup from user text without entity-encoding it.

    Removes HTML tags and trims the result. It deliberately does *not*
    ``html.escape``: escaping belongs at the point of output, not at rest.
    Every sink for these fields already escapes — React renders them as text,
    and the email templates call ``escape()`` on each interpolation — so
    escaping on write only corrupts the stored value. It did exactly that: a
    pupil named ``Dan'azumi`` was stored as ``Dan&#x27;azumi`` and then
    displayed verbatim, and each re-save escaped the ampersand again.
    """
    if text is None:
        return None
    cleaned = re.sub(r"<[^>]*>", "", text).strip()
    return cleaned or None
