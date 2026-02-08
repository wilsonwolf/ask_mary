"""Tests for shared comms template rendering utilities."""

import pytest

from src.shared.comms import list_templates, load_template, render_template


class TestLoadTemplate:
    """Template loading from YAML files."""

    def test_loads_disclosure(self) -> None:
        """Loads the disclosure template."""
        template = load_template("disclosure")
        assert template["name"] == "disclosure"
        assert "body" in template

    def test_raises_for_missing(self) -> None:
        """Raises FileNotFoundError for missing template."""
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent_template")


class TestRenderTemplate:
    """Jinja2 template rendering."""

    def test_renders_with_variables(self) -> None:
        """Renders template body with provided variables."""
        result = render_template(
            "appointment_booked",
            participant_name="Jane Doe",
            trial_name="Diabetes Study A",
            site_name="OHSU",
            appointment_date="2026-03-16",
            appointment_time="10:00 AM",
            coordinator_phone="+15035551234",
        )
        assert "Jane Doe" in result
        assert "Diabetes Study A" in result


class TestListTemplates:
    """Template listing."""

    def test_lists_all_templates(self) -> None:
        """Lists all available template names."""
        names = list_templates()
        assert "disclosure" in names
        assert "prep_instructions" in names
        assert len(names) >= 9
