"""Tests for participant identity utilities."""

from datetime import date

import pytest

from src.shared.identity import (
    canonicalize_name,
    canonicalize_phone,
    generate_mary_id,
)

PEPPER = "test-pepper-do-not-use-in-production"


class TestCanonicalizeName:
    """Name canonicalization for consistent hashing."""

    def test_lowercases(self) -> None:
        assert canonicalize_name("John") == "john"

    def test_strips_whitespace(self) -> None:
        assert canonicalize_name("  John  ") == "john"

    def test_collapses_internal_spaces(self) -> None:
        assert canonicalize_name("Mary  Jane") == "mary jane"

    def test_handles_empty_string(self) -> None:
        assert canonicalize_name("") == ""


class TestCanonicalizePhone:
    """Phone canonicalization extracts digits only."""

    def test_strips_formatting(self) -> None:
        assert canonicalize_phone("+1 (555) 123-4567") == "15551234567"

    def test_digits_only_passthrough(self) -> None:
        assert canonicalize_phone("15551234567") == "15551234567"

    def test_handles_empty(self) -> None:
        assert canonicalize_phone("") == ""


class TestGenerateMaryId:
    """HMAC-SHA256 participant ID generation."""

    def test_deterministic(self) -> None:
        """Same inputs produce same output."""
        dob = date(1980, 6, 15)
        id1 = generate_mary_id("John", "Doe", dob, "+1-555-123-4567", PEPPER)
        id2 = generate_mary_id("John", "Doe", dob, "+1-555-123-4567", PEPPER)
        assert id1 == id2

    def test_case_insensitive(self) -> None:
        """Canonicalization makes names case-insensitive."""
        dob = date(1980, 6, 15)
        id1 = generate_mary_id("John", "Doe", dob, "5551234567", PEPPER)
        id2 = generate_mary_id("john", "doe", dob, "5551234567", PEPPER)
        assert id1 == id2

    def test_phone_format_insensitive(self) -> None:
        """Different phone formats produce same ID."""
        dob = date(1980, 6, 15)
        id1 = generate_mary_id("John", "Doe", dob, "+1 (555) 123-4567", PEPPER)
        id2 = generate_mary_id("John", "Doe", dob, "15551234567", PEPPER)
        assert id1 == id2

    def test_whitespace_insensitive(self) -> None:
        """Extra whitespace in names doesn't change ID."""
        dob = date(1980, 6, 15)
        id1 = generate_mary_id("John", "Doe", dob, "5551234567", PEPPER)
        id2 = generate_mary_id("  John  ", "  Doe  ", dob, "5551234567", PEPPER)
        assert id1 == id2

    def test_different_people_different_ids(self) -> None:
        """Different inputs produce different IDs."""
        dob = date(1980, 6, 15)
        id1 = generate_mary_id("John", "Doe", dob, "5551234567", PEPPER)
        id2 = generate_mary_id("Jane", "Doe", dob, "5551234567", PEPPER)
        assert id1 != id2

    def test_different_pepper_different_ids(self) -> None:
        """Different peppers produce different IDs."""
        dob = date(1980, 6, 15)
        id1 = generate_mary_id("John", "Doe", dob, "5551234567", "pepper-a")
        id2 = generate_mary_id("John", "Doe", dob, "5551234567", "pepper-b")
        assert id1 != id2

    def test_empty_pepper_raises(self) -> None:
        """Empty pepper is rejected."""
        with pytest.raises(ValueError, match="MARY_ID_PEPPER"):
            generate_mary_id("John", "Doe", date(1980, 6, 15), "555", "")

    def test_output_is_64_char_hex(self) -> None:
        """Output is a valid SHA-256 hex digest."""
        dob = date(1980, 6, 15)
        result = generate_mary_id("John", "Doe", dob, "5551234567", PEPPER)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)
