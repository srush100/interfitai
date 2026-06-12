"""
Tests for Week Progression Banner and Rest Days features:
- PATCH /api/workout/{id}/week-override endpoint
- GET /api/workout/{id} returns current_week_override and weekly_progression/weekly_structure fields
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_BACKEND_URL', '').rstrip('/')
WORKOUT_ID = "13879b5a-82d5-4fa1-8c68-a7e1a999b750"
USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

@pytest.fixture
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


class TestWeekOverrideEndpoint:
    """PATCH /api/workout/{id}/week-override endpoint tests"""

    def test_patch_week_override_to_week_1(self, api_client):
        """Set week override to 1 returns success"""
        resp = api_client.patch(f"{BASE_URL}/api/workout/{WORKOUT_ID}/week-override",
                                json={"current_week_override": 1})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("success") is True
        assert data.get("current_week_override") == 1

    def test_patch_week_override_to_week_2(self, api_client):
        """Set week override to 2 returns success"""
        resp = api_client.patch(f"{BASE_URL}/api/workout/{WORKOUT_ID}/week-override",
                                json={"current_week_override": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("current_week_override") == 2

    def test_patch_week_override_to_week_3(self, api_client):
        """Set week override to 3 works"""
        resp = api_client.patch(f"{BASE_URL}/api/workout/{WORKOUT_ID}/week-override",
                                json={"current_week_override": 3})
        assert resp.status_code == 200
        assert resp.json().get("current_week_override") == 3

    def test_patch_week_override_to_week_4(self, api_client):
        """Set week override to 4 (Deload) works"""
        resp = api_client.patch(f"{BASE_URL}/api/workout/{WORKOUT_ID}/week-override",
                                json={"current_week_override": 4})
        assert resp.status_code == 200
        assert resp.json().get("current_week_override") == 4

    def test_patch_week_override_reset_to_null(self, api_client):
        """Reset week override to null (use auto-computed) works"""
        resp = api_client.patch(f"{BASE_URL}/api/workout/{WORKOUT_ID}/week-override",
                                json={"current_week_override": None})
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("current_week_override") is None

    def test_patch_week_override_persists_to_get(self, api_client):
        """Override persists: GET after PATCH returns updated value"""
        # Set to week 2
        api_client.patch(f"{BASE_URL}/api/workout/{WORKOUT_ID}/week-override",
                         json={"current_week_override": 2})
        # Verify via GET
        resp = api_client.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("current_week_override") == 2
        # Reset
        api_client.patch(f"{BASE_URL}/api/workout/{WORKOUT_ID}/week-override",
                         json={"current_week_override": None})

    def test_patch_week_override_invalid_workout(self, api_client):
        """Invalid workout ID returns 404"""
        resp = api_client.patch(f"{BASE_URL}/api/workout/nonexistent-id/week-override",
                                json={"current_week_override": 1})
        assert resp.status_code == 404


class TestWorkoutWeeklyData:
    """GET /api/workout/{id} returns required week progression fields"""

    def test_workout_has_weekly_progression(self, api_client):
        """workout.weekly_progression is a list of 4 dicts"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        progression = data.get("weekly_progression")
        assert progression is not None, "weekly_progression field missing"
        assert isinstance(progression, list)
        assert len(progression) == 4, f"Expected 4 weeks, got {len(progression)}"

    def test_weekly_progression_has_correct_labels(self, api_client):
        """Each week has week number, label, and instruction"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        data = resp.json()
        progression = data.get("weekly_progression", [])
        weeks = {w["week"]: w for w in progression}
        assert weeks.get(1, {}).get("label") == "Foundation"
        assert weeks.get(2, {}).get("label") == "Build"
        assert weeks.get(3, {}).get("label") == "Overreach"
        assert weeks.get(4, {}).get("label") == "Deload"
        for w in progression:
            assert "instruction" in w, f"Week {w['week']} missing instruction"
            assert len(w["instruction"]) > 10, "Instruction too short"

    def test_workout_has_weekly_structure(self, api_client):
        """workout.weekly_structure is a list of day strings"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        data = resp.json()
        structure = data.get("weekly_structure")
        assert structure is not None, "weekly_structure field missing"
        assert isinstance(structure, list)
        assert len(structure) == 7, f"Expected 7 days, got {len(structure)}"

    def test_weekly_structure_has_rest_days(self, api_client):
        """weekly_structure has days ending in ': Rest'"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        data = resp.json()
        structure = data.get("weekly_structure", [])
        rest_days = [d for d in structure if d.endswith(": Rest")]
        assert len(rest_days) >= 1, f"No rest days found in: {structure}"
        # This is a 4-day program, so 3 rest days expected
        assert len(rest_days) >= 2, f"Expected at least 2 rest days for 4-day program, got: {rest_days}"

    def test_weekly_structure_wednesday_saturday_sunday_rest(self, api_client):
        """For this 4-day workout, Wednesday, Saturday, Sunday are rest days"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        data = resp.json()
        structure = data.get("weekly_structure", [])
        rest_days = [d.split(":")[0] for d in structure if d.endswith(": Rest")]
        assert "Wednesday" in rest_days, f"Wednesday not a rest day: {rest_days}"
        assert "Saturday" in rest_days, f"Saturday not a rest day: {rest_days}"
        assert "Sunday" in rest_days, f"Sunday not a rest day: {rest_days}"

    def test_workout_current_week_override_field_exists(self, api_client):
        """current_week_override field is present (may be null)"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        data = resp.json()
        assert "current_week_override" in data, "current_week_override field missing from response"
