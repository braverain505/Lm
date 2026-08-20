"""Input sanitization utilities for preventing XSS attacks.

Temporary implementation using html.escape until nh3 is installed.
For production, install nh3: pip install nh3
"""
import html
import re


def sanitize_html(text: str | None) -> str | None:
    """Remove all HTML tags and dangerous content.

    Used for rich text fields that should not contain any HTML.
    """
    if text is None:
        return None
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Escape any remaining special characters
    return html.escape(text)


def sanitize_text_input(text: str | None) -> str | None:
    """Sanitize user text input (names, descriptions, comments).

    Removes HTML tags, strips whitespace, and ensures safe storage.
    Use this for all user-provided text fields.
    """
    if text is None:
        return None
    # Remove HTML tags
    cleaned = re.sub(r'<[^>]+>', '', text)
    # Escape special characters
    cleaned = html.escape(cleaned)
    # Strip leading/trailing whitespace
    return cleaned.strip() if cleaned else None
