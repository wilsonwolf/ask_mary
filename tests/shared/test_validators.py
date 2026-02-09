"""Tests for shared input validators."""

from src.shared.validators import (
    is_dnc_blocked,
    validate_channel,
    validate_dob_year,
    validate_phone,
    validate_zip_code,
)


class TestValidatePhone:
    """Phone number validation."""

    def test_valid_us_phone(self) -> None:
        """Standard US phone number passes."""
        assert validate_phone("+15035551234") is True

    def test_valid_ten_digit(self) -> None:
        """10-digit phone number passes."""
        assert validate_phone("5035551234") is True

    def test_rejects_too_short(self) -> None:
        """Phone with fewer than 10 digits fails."""
        assert validate_phone("12345") is False

    def test_rejects_empty(self) -> None:
        """Empty string fails."""
        assert validate_phone("") is False

    def test_strips_formatting(self) -> None:
        """Formatted phone number passes."""
        assert validate_phone("(503) 555-1234") is True


class TestValidateZipCode:
    """ZIP code validation."""

    def test_valid_5_digit(self) -> None:
        """Standard 5-digit ZIP passes."""
        assert validate_zip_code("97201") is True

    def test_rejects_too_short(self) -> None:
        """4-digit ZIP fails."""
        assert validate_zip_code("9720") is False

    def test_rejects_letters(self) -> None:
        """Non-numeric ZIP fails."""
        assert validate_zip_code("9720A") is False


class TestValidateDobYear:
    """DOB year validation."""

    def test_valid_year(self) -> None:
        """Reasonable birth year passes."""
        assert validate_dob_year(1985) is True

    def test_rejects_future_year(self) -> None:
        """Future year fails."""
        assert validate_dob_year(2030) is False

    def test_rejects_too_old(self) -> None:
        """Year before 1900 fails."""
        assert validate_dob_year(1899) is False


class TestIsDncBlocked:
    """DNC flag checking."""

    def test_blocked_on_all(self) -> None:
        """DNC all_channels blocks any channel."""
        flags = {"all_channels": True}
        assert is_dnc_blocked(flags, "voice") is True

    def test_blocked_on_specific_channel(self) -> None:
        """DNC on specific channel blocks that channel."""
        flags = {"voice": True}
        assert is_dnc_blocked(flags, "voice") is True

    def test_not_blocked_different_channel(self) -> None:
        """DNC on voice does not block SMS."""
        flags = {"voice": True}
        assert is_dnc_blocked(flags, "sms") is False

    def test_not_blocked_empty_flags(self) -> None:
        """Empty DNC flags block nothing."""
        assert is_dnc_blocked({}, "voice") is False

    def test_not_blocked_none_flags(self) -> None:
        """None DNC flags block nothing."""
        assert is_dnc_blocked(None, "voice") is False


class TestValidateChannel:
    """Channel validation."""

    def test_valid_channels(self) -> None:
        """All defined channels pass."""
        for ch in ("voice", "sms", "whatsapp"):
            assert validate_channel(ch) is True

    def test_rejects_unknown(self) -> None:
        """Unknown channel fails."""
        assert validate_channel("pigeon") is False
