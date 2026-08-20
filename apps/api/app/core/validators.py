"""Pydantic validators for input sanitization.

Provides field validators to sanitize user input and prevent XSS attacks.
Use these validators on all user-facing text fields in Pydantic models.
"""
from pydantic import field_validator

from .sanitize import sanitize_text_input


def sanitize_string_field(*field_names):
    """Create a field validator that sanitizes string input.

    Usage:
        class MySchema(BaseModel):
            name: str
            description: str

            _sanitize = sanitize_string_field('name', 'description')
    """
    return field_validator(*field_names, mode='before')(
        lambda cls, v: sanitize_text_input(v) if isinstance(v, str) else v
    )
