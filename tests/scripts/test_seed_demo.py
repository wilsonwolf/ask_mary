"""Tests validating demo seed data is internally consistent.

These tests verify that the seed data works with every agent's
expectations — identity verification, screening criteria, geo
gate, transport address assembly, and outreach context.
"""

from datetime import date

from scripts.seed_demo import (
    CARDIOLOGY_TRIAL,
    DEMO_PARTICIPANT,
    DIABETES_TRIAL,
    EXTRA_PARTICIPANTS,
)


class TestDemoParticipantData:
    """Demo participant data consistency checks."""

    def test_phone_number_is_correct(self) -> None:
        """Demo participant has the designated phone number."""
        assert DEMO_PARTICIPANT["phone"] == "+16505077348"

    def test_dob_is_date_object(self) -> None:
        """DOB is a Python date (not string) for identity agent."""
        assert isinstance(DEMO_PARTICIPANT["date_of_birth"], date)

    def test_dob_year_is_reasonable(self) -> None:
        """DOB year is between 1900 and 2010 for identity verification."""
        year = DEMO_PARTICIPANT["date_of_birth"].year
        assert 1900 < year < 2010

    def test_has_zip_for_identity_verification(self) -> None:
        """ZIP code present and 5 digits for identity agent."""
        zip_code = DEMO_PARTICIPANT["address_zip"]
        assert len(zip_code) == 5
        assert zip_code.isdigit()

    def test_has_full_address_for_transport(self) -> None:
        """Full address fields present for transport agent."""
        assert DEMO_PARTICIPANT["address_street"]
        assert DEMO_PARTICIPANT["address_city"]
        assert DEMO_PARTICIPANT["address_state"]
        assert DEMO_PARTICIPANT["address_zip"]

    def test_distance_within_trial_max(self) -> None:
        """Participant is within diabetes trial max distance."""
        distance = DEMO_PARTICIPANT["distance_to_site_km"]
        max_km = DIABETES_TRIAL["max_distance_km"]
        assert distance <= max_km

    def test_age_within_inclusion_criteria(self) -> None:
        """Demo participant age falls within inclusion range."""
        dob = DEMO_PARTICIPANT["date_of_birth"]
        age = (date(2026, 2, 8) - dob).days // 365
        criteria = DIABETES_TRIAL["inclusion_criteria"]
        assert criteria["min_age"] <= age <= criteria["max_age"]


class TestDiabetesTrialData:
    """Diabetes trial data consistency checks."""

    def test_has_inclusion_criteria(self) -> None:
        """Trial has inclusion criteria for screening agent."""
        criteria = DIABETES_TRIAL["inclusion_criteria"]
        assert "min_age" in criteria
        assert "max_age" in criteria
        assert "diagnosis" in criteria

    def test_has_exclusion_criteria(self) -> None:
        """Trial has exclusion criteria for hard-exclude checks."""
        criteria = DIABETES_TRIAL["exclusion_criteria"]
        assert len(criteria) > 0
        assert all(isinstance(v, bool) for v in criteria.values())

    def test_has_operating_hours(self) -> None:
        """Trial has operating hours for scheduling agent."""
        hours = DIABETES_TRIAL["operating_hours"]
        assert "monday" in hours
        assert "open" in hours["monday"]
        assert "close" in hours["monday"]

    def test_has_visit_templates(self) -> None:
        """Trial has visit templates for appointment creation."""
        templates = DIABETES_TRIAL["visit_templates"]
        assert "screening" in templates
        assert "duration_min" in templates["screening"]

    def test_has_site_info_for_transport(self) -> None:
        """Trial has site address for transport dropoff."""
        assert DIABETES_TRIAL["site_address"]
        assert DIABETES_TRIAL["site_name"]

    def test_has_coordinator_for_handoff(self) -> None:
        """Trial has coordinator phone for handoff agent."""
        assert DIABETES_TRIAL["coordinator_phone"]
        assert DIABETES_TRIAL["coordinator_name"]


class TestCardiologyTrialData:
    """Cardiology trial data consistency checks."""

    def test_has_distinct_trial_id(self) -> None:
        """Second trial has a different ID."""
        assert CARDIOLOGY_TRIAL["trial_id"] != DIABETES_TRIAL["trial_id"]

    def test_has_complete_criteria(self) -> None:
        """Second trial has both inclusion and exclusion criteria."""
        assert len(CARDIOLOGY_TRIAL["inclusion_criteria"]) > 0
        assert len(CARDIOLOGY_TRIAL["exclusion_criteria"]) > 0


class TestExtraParticipants:
    """Extra participants for dashboard realism."""

    def test_all_have_required_fields(self) -> None:
        """Every extra participant has the fields needed by all agents."""
        required = [
            "first_name",
            "last_name",
            "date_of_birth",
            "phone",
            "address_zip",
        ]
        for p in EXTRA_PARTICIPANTS:
            for field in required:
                assert field in p, f"Missing {field} in {p['first_name']}"

    def test_unique_phones(self) -> None:
        """No phone number collisions with demo participant."""
        demo_phone = DEMO_PARTICIPANT["phone"]
        for p in EXTRA_PARTICIPANTS:
            assert p["phone"] != demo_phone
