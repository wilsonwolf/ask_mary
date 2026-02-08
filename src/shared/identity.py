"""Participant identity utilities including mary_id generation."""

import hashlib
import hmac
import re
from datetime import date


def canonicalize_name(name: str) -> str:
    """Normalize a name for consistent hashing.

    Args:
        name: Raw name input.

    Returns:
        Lowercased, stripped, single-spaced name.
    """
    return re.sub(r"\s+", " ", name.strip().lower())


def canonicalize_phone(phone: str) -> str:
    """Extract digits only from a phone number.

    Args:
        phone: Raw phone input (may contain +, -, spaces, parens).

    Returns:
        Digits-only string.
    """
    return re.sub(r"\D", "", phone)


def generate_mary_id(
    first_name: str,
    last_name: str,
    dob: date,
    phone: str,
    pepper: str,
) -> str:
    """Generate a deterministic participant identifier.

    Uses HMAC-SHA256 with canonicalized inputs and a secret pepper
    to produce a collision-resistant, non-reversible identifier.

    Args:
        first_name: Participant first name.
        last_name: Participant last name.
        dob: Date of birth.
        phone: Phone number (any format).
        pepper: Secret pepper from MARY_ID_PEPPER env var.

    Returns:
        64-character hex string (HMAC-SHA256 digest).

    Raises:
        ValueError: If pepper is empty.
    """
    if not pepper:
        raise ValueError("MARY_ID_PEPPER must be set for participant ID generation")

    canonical = "|".join([
        canonicalize_name(first_name),
        canonicalize_name(last_name),
        dob.isoformat(),
        canonicalize_phone(phone),
    ])

    return hmac.new(
        key=pepper.encode("utf-8"),
        msg=canonical.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
