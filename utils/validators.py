"""Validation utilities for TruthLens backend."""

import re
from typing import Any, Dict, List, Optional


def validate_required_fields(data: Dict, fields: List[str]) -> Optional[str]:
    """Validate that required fields are present and non-empty.

    Args:
        data: The request JSON data dict.
        fields: List of field names that must be present and non-empty.

    Returns:
        Error message string if validation fails, None if valid.
    """
    for field in fields:
        value = data.get(field)
        if not value or not str(value).strip():
            return f"Field '{field}' is required and must not be empty."
    return None


def validate_email_format(email: str) -> Optional[str]:
    """Validate email format using a standard regex.

    Args:
        email: The email address string to validate.

    Returns:
        Error message string if invalid, None if valid.
    """
    if not email or not isinstance(email, str):
        return "Email address must be a valid string."

    # Normalize: strip and lowercase
    email = email.strip().lower()

    # RFC 5322 compliant email regex (simplified)
    pattern = r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)$"
    if not re.match(pattern, email):
        return "Please enter a valid email address."

    # Reasonable field length check
    if len(email) > 254:
        return "Email address is too long (maximum 254 characters)."

    return None


def validate_password_policy(password: str) -> Optional[str]:
    """Validate password against policy requirements.

    Policy:
    - Must be at least 8 characters long
    - Should contain at least 1 number
    - Should contain at least 1 uppercase letter

    Args:
        password: The password string to validate.

    Returns:
        Error message string if invalid, None if valid.
    """
    if not password or not isinstance(password, str):
        return "Password must be a string."

    if len(password) < 8:
        return "Password must be at least 8 characters long."

    if not re.search(r"\d", password):
        return "Password must contain at least 1 number."

    if not re.search(r"[A-Z]", password):
        return "Password must contain at least 1 uppercase letter."

    return None


def validate_url(url: str) -> Optional[str]:
    """Validate that a string is a safe HTTP/HTTPS URL.

    Args:
        url: The URL string to validate.

    Returns:
        Error message string if invalid, None if valid.
    """
    if not url or not isinstance(url, str):
        return "URL must be a valid string."

    # Check basic URL format
    try:
        parsed = urlparse(url)
    except Exception:
        return "URL must start with http:// or https://."

    if parsed.scheme not in ("http", "https"):
        return "URL must start with http:// or https://."

    if not parsed.hostname:
        return "URL must include a valid hostname."

    # Additional SSRF checks can be done via is_safe_url in article_extractor

    return None


def validate_text_input(
    text: str,
    min_length: int = 1,
    max_length: int = 10000,
) -> Optional[str]:
    """Validate text input length constraints.

    Args:
        text: The text string to validate.
        min_length: Minimum required length.
        max_length: Maximum allowed length.

    Returns:
        Error message string if invalid, None if valid.
    """
    if text is None:
        return "Input text must be a string."

    if len(text) < min_length:
        return f"Input text must be at least {min_length} character(s)."

    if len(text) > max_length:
        return f"Input text must not exceed {max_length} character(s)."

    return None


def sanitize_input(value: str) -> str:
    """Sanitize a string value by stripping whitespace.

    Args:
        value: The string to sanitize.

    Returns:
        The stripped string.
    """
    return value.strip() if value else ""


def format_error_response(
    message: str,
    errors: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Format a standardized error response dict.

    Args:
        message: The main error message.
        errors: Optional dict of field-specific error messages.

    Returns:
        A dict formatted for API error responses.
    """
    response = {"message": message, "errors": errors or {}}
    return response


def format_success_response(
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Format a standardized success response dict.

    Args:
        message: The success message.
        data: Optional data dict to include.

    Returns:
        A dict formatted for API success responses.
    """
    response = {"success": True, "message": message, "data": data or {}}
    return response