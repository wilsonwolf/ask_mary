"""Tests for comms templates YAML files."""

from pathlib import Path

import yaml
from jinja2 import Template

TEMPLATES_DIR = Path(__file__).parent.parent / "comms_templates"

EXPECTED_TEMPLATES = [
    "disclosure.yaml",
    "prep_instructions.yaml",
    "confirmation_prompt.yaml",
    "day_of_checkin.yaml",
    "no_show_rescue.yaml",
    "protocol_change.yaml",
    "appointment_booked.yaml",
    "appointment_reminder.yaml",
    "unreachable_escalation.yaml",
    "consent_sms.yaml",
    "ineligible_close.yaml",
    "unreachable.yaml",
]


class TestCommsTemplates:
    """All comms templates are valid and renderable."""

    def test_all_templates_exist(self) -> None:
        """All expected template files exist."""
        for name in EXPECTED_TEMPLATES:
            path = TEMPLATES_DIR / name
            assert path.exists(), f"Missing template: {name}"

    def test_all_templates_loadable(self) -> None:
        """All templates parse as valid YAML."""
        for name in EXPECTED_TEMPLATES:
            path = TEMPLATES_DIR / name
            with open(path) as f:
                data = yaml.safe_load(f)
            assert isinstance(data, dict), f"{name} is not a YAML dict"

    def test_required_fields_present(self) -> None:
        """Each template has name, channel, and body fields."""
        for name in EXPECTED_TEMPLATES:
            path = TEMPLATES_DIR / name
            with open(path) as f:
                data = yaml.safe_load(f)
            assert "name" in data, f"{name} missing 'name'"
            assert "channel" in data, f"{name} missing 'channel'"
            assert "body" in data, f"{name} missing 'body'"

    def test_jinja2_renders(self) -> None:
        """Templates render with Jinja2 without errors."""
        for name in EXPECTED_TEMPLATES:
            path = TEMPLATES_DIR / name
            with open(path) as f:
                data = yaml.safe_load(f)
            template = Template(data["body"])
            # Render with empty vars — should not raise
            result = template.render(
                participant_name="Test User",
                trial_name="Test Trial",
                site_name="Test Site",
                appointment_date="2026-03-15",
                appointment_time="10:00 AM",
                coordinator_phone="+15035551234",
                prep_instructions="Bring ID",
            )
            assert isinstance(result, str)
