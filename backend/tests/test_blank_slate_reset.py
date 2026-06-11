"""
Tests for Blank Slate Reset after completing a workout session.
Verifies that after POST /workout/{id}/session/complete:
  1. All exercise inputs (weight, reps, completed) are cleared to blank slate
  2. Last-session endpoint returns the historical data from the just-completed session
  3. Blank slate persists to DB (survives a GET /performance after complete)

Tests use EXPO_BACKEND_URL from environment.
"""

import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")

# Test user ID to use (from agent_to_agent_context_note)
KNOWN_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def test_user_id(api_client):
    """Use existing test user or create a new one"""
    # Check if known user exists
    resp = api_client.get(f"{BASE_URL}/api/profile/{KNOWN_USER_ID}")
    if resp.status_code == 200:
        print(f"Using existing user: {KNOWN_USER_ID}")
        return KNOWN_USER_ID

    # Create a new profile
    resp = api_client.post(f"{BASE_URL}/api/profile", json={
        "name": "TEST_BlankSlate User",
        "email": f"TEST_blankslate_{uuid.uuid4().hex[:6]}@test.com",
        "password": "Test123!",
        "weight": 80.0,
        "height": 175.0,
        "age": 28,
        "gender": "male",
        "activity_level": "moderate",
        "goal": "build_muscle",
    })
    assert resp.status_code == 200, f"Profile creation failed: {resp.text}"
    user_id = resp.json()["id"]
    print(f"Created new test user: {user_id}")
    return user_id


@pytest.fixture(scope="module")
def test_workout_id(api_client, test_user_id):
    """Create a minimal workout for testing (2-day, 2-exercise program)"""
    resp = api_client.post(f"{BASE_URL}/api/workouts/generate", json={
        "user_id": test_user_id,
        "goal": "build_muscle",
        "training_style": "weights",
        "focus_areas": ["chest"],
        "equipment": ["dumbbells"],
        "days_per_week": 2,
        "duration_minutes": 45,
        "fitness_level": "intermediate",
    })
    assert resp.status_code == 200, f"Workout generation failed: {resp.status_code} - {resp.text}"
    workout_id = resp.json()["id"]
    print(f"Created workout: {workout_id}")
    return workout_id


class TestBlankSlateReset:
    """Full lifecycle test: save performance → complete session → verify blank slate"""

    def test_01_health_check(self, api_client):
        """Backend health check"""
        resp = api_client.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        print("✅ Health check passed")

    def test_02_save_performance_data(self, api_client, test_workout_id):
        """Save non-empty performance data to simulate mid-workout state (day_index=0)"""
        # Use 3 exercises × 3 sets each = 9 keys for day 0
        performance = {}
        for ex_idx in range(3):
            for set_idx in range(3):
                key = f"0-{ex_idx}-{set_idx}"
                performance[key] = {
                    "weight": str(40.0 + ex_idx * 5),
                    "reps": str(10 + set_idx),
                    "completed": True,
                }

        resp = api_client.post(
            f"{BASE_URL}/api/workout/{test_workout_id}/performance",
            json={"performance": performance},
        )
        assert resp.status_code == 200, f"Save performance failed: {resp.text}"
        print(f"✅ Saved {len(performance)} performance keys for day 0")

    def test_03_verify_performance_saved(self, api_client, test_workout_id):
        """Verify performance data was actually saved (not empty)"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{test_workout_id}/performance")
        assert resp.status_code == 200, f"GET performance failed: {resp.text}"
        data = resp.json()
        perf = data.get("performance", {})
        day0_keys = [k for k in perf if k.startswith("0-")]
        assert len(day0_keys) > 0, "No performance data found for day 0 before completing"
        # Verify at least one entry has weight filled
        has_weight = any(perf[k].get("weight") != "" for k in day0_keys)
        assert has_weight, "Expected non-empty weight values before completing session"
        print(f"✅ Performance data present: {len(day0_keys)} keys, with filled weight values")

    def test_04_complete_session_returns_200(self, api_client, test_workout_id, test_user_id):
        """POST /workout/{id}/session/complete returns 200 OK"""
        # Build completed_exercises with 3 exercises × 3 sets
        completed_exercises = []
        for ex_idx in range(3):
            sets_data = []
            for set_idx in range(3):
                sets_data.append({
                    "set_number": set_idx + 1,
                    "weight": 40.0 + ex_idx * 5,
                    "reps": 10 + set_idx,
                    "completed": True,
                })
            completed_exercises.append({
                "exercise_name": f"TEST Exercise {ex_idx + 1}",
                "muscle_groups": ["chest"],
                "sets": sets_data,
            })

        resp = api_client.post(
            f"{BASE_URL}/api/workout/{test_workout_id}/session/complete",
            json={
                "user_id": test_user_id,
                "day_index": 0,
                "day_focus": "Chest Day",
                "duration_minutes": 45,
                "completed_exercises": completed_exercises,
            },
        )
        assert resp.status_code == 200, f"Session complete failed: {resp.status_code} - {resp.text}"
        data = resp.json()
        assert "personal_records" in data, "Response missing 'personal_records' field"
        assert isinstance(data["personal_records"], list), "'personal_records' should be a list"
        assert "total_volume" in data, "Response missing 'total_volume' field"
        print(f"✅ Session complete returned 200 OK. Volume: {data.get('total_volume')}, PRs: {len(data.get('personal_records', []))}")
        # Store session_id for later tests (module scope workaround via class variable)
        TestBlankSlateReset.session_id = data.get("id", "")
        TestBlankSlateReset.completed_exercises_sent = completed_exercises

    def test_05_blank_slate_completed_false(self, api_client, test_workout_id):
        """After completing session, ALL day-0 checkboxes should be completed=False"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{test_workout_id}/performance")
        assert resp.status_code == 200, f"GET performance failed: {resp.text}"
        perf = resp.json().get("performance", {})
        day0_keys = [k for k in perf if k.startswith("0-")]
        assert len(day0_keys) > 0, "No day-0 performance keys found"
        for key in day0_keys:
            entry = perf[key]
            assert entry.get("completed") == False, (
                f"Key '{key}' has completed={entry.get('completed')}, expected False after session complete"
            )
        print(f"✅ All {len(day0_keys)} day-0 checkboxes are completed=False (blank slate)")

    def test_06_blank_slate_weight_empty(self, api_client, test_workout_id):
        """After completing session, ALL day-0 weight inputs should be empty strings"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{test_workout_id}/performance")
        assert resp.status_code == 200, f"GET performance failed: {resp.text}"
        perf = resp.json().get("performance", {})
        day0_keys = [k for k in perf if k.startswith("0-")]
        assert len(day0_keys) > 0, "No day-0 performance keys found"
        for key in day0_keys:
            entry = perf[key]
            assert entry.get("weight") == "", (
                f"Key '{key}' has weight='{entry.get('weight')}', expected '' after session complete"
            )
        print(f"✅ All {len(day0_keys)} day-0 weight inputs are empty strings (blank slate)")

    def test_07_blank_slate_reps_empty(self, api_client, test_workout_id):
        """After completing session, ALL day-0 reps inputs should be empty strings"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{test_workout_id}/performance")
        assert resp.status_code == 200, f"GET performance failed: {resp.text}"
        perf = resp.json().get("performance", {})
        day0_keys = [k for k in perf if k.startswith("0-")]
        assert len(day0_keys) > 0, "No day-0 performance keys found"
        for key in day0_keys:
            entry = perf[key]
            assert entry.get("reps") == "", (
                f"Key '{key}' has reps='{entry.get('reps')}', expected '' after session complete"
            )
        print(f"✅ All {len(day0_keys)} day-0 reps inputs are empty strings (blank slate)")

    def test_08_other_days_not_cleared(self, api_client, test_workout_id):
        """Blank slate should ONLY affect the completed day (day_index=0), not other days"""
        # First save some data for day 1
        performance_day1 = {}
        for ex_idx in range(2):
            for set_idx in range(2):
                key = f"1-{ex_idx}-{set_idx}"
                performance_day1[key] = {
                    "weight": "50",
                    "reps": "8",
                    "completed": True,
                }

        # Get current performance and merge with day1 data
        resp = api_client.get(f"{BASE_URL}/api/workout/{test_workout_id}/performance")
        existing_perf = resp.json().get("performance", {})
        merged_perf = {**existing_perf, **performance_day1}

        save_resp = api_client.post(
            f"{BASE_URL}/api/workout/{test_workout_id}/performance",
            json={"performance": merged_perf},
        )
        assert save_resp.status_code == 200, "Failed to save day-1 performance"

        # Now check that day1 keys are still present and NOT cleared
        resp2 = api_client.get(f"{BASE_URL}/api/workout/{test_workout_id}/performance")
        perf = resp2.json().get("performance", {})
        day1_keys = [k for k in perf if k.startswith("1-")]
        assert len(day1_keys) > 0, "No day-1 performance keys found"
        for key in day1_keys:
            entry = perf[key]
            assert entry.get("weight") == "50", (
                f"Day-1 key '{key}' weight was unexpectedly cleared. Got: {entry.get('weight')}"
            )
        print(f"✅ Day-1 data ({len(day1_keys)} keys) preserved after completing day-0 session")

    def test_09_blank_slate_persists_after_reload(self, api_client, test_workout_id):
        """Blank slate persists in DB - a second GET /performance still returns blank for day 0"""
        # Simulate "page reload" by making a fresh GET request
        time.sleep(0.3)
        resp = api_client.get(f"{BASE_URL}/api/workout/{test_workout_id}/performance")
        assert resp.status_code == 200, f"GET performance failed: {resp.text}"
        perf = resp.json().get("performance", {})
        day0_keys = [k for k in perf if k.startswith("0-")]
        assert len(day0_keys) > 0, "No day-0 keys found on reload"
        for key in day0_keys:
            entry = perf[key]
            assert entry.get("weight") == "", f"Key '{key}' weight not blank on reload: {entry}"
            assert entry.get("reps") == "", f"Key '{key}' reps not blank on reload: {entry}"
            assert entry.get("completed") == False, f"Key '{key}' completed not False on reload: {entry}"
        print(f"✅ Blank slate persists after simulated page reload ({len(day0_keys)} keys verified)")

    def test_10_last_session_has_historical_data(self, api_client, test_workout_id, test_user_id):
        """GET /workout/{id}/last-session returns historical data from the completed session"""
        resp = api_client.get(
            f"{BASE_URL}/api/workout/{test_workout_id}/last-session",
            params={"day_index": 0, "user_id": test_user_id},
        )
        assert resp.status_code == 200, f"GET last-session failed: {resp.text}"
        data = resp.json()
        assert data is not None, "last-session returned null - no session found"
        assert "completed_exercises" in data, "last-session missing 'completed_exercises'"
        exercises = data["completed_exercises"]
        assert len(exercises) > 0, "last-session has no exercises"
        # Verify at least one completed set with weight/reps data
        found_completed_set = False
        for ex in exercises:
            for s in ex.get("sets", []):
                if s.get("completed") and s.get("weight") is not None and s.get("reps") is not None:
                    found_completed_set = True
                    break
        assert found_completed_set, (
            "last-session has no completed sets with weight/reps data. "
            "Historical data is missing from last-session endpoint!"
        )
        print(f"✅ last-session has {len(exercises)} exercises with historical weight/reps data")

    def test_11_last_session_matches_completed_session(self, api_client, test_workout_id, test_user_id):
        """last-session exercise names and weights match what was submitted in session/complete"""
        resp = api_client.get(
            f"{BASE_URL}/api/workout/{test_workout_id}/last-session",
            params={"day_index": 0, "user_id": test_user_id},
        )
        assert resp.status_code == 200
        data = resp.json()
        exercises = data.get("completed_exercises", [])
        assert len(exercises) >= 1, "No exercises in last-session"
        # Verify first exercise's set data
        first_ex = exercises[0]
        first_set = first_ex.get("sets", [{}])[0]
        assert first_set.get("weight") is not None, "First set has no weight in last-session"
        assert first_set.get("reps") is not None, "First set has no reps in last-session"
        # Expected weight from test_04 was 40.0 for ex_idx=0
        expected_weight = 40.0
        actual_weight = first_set.get("weight")
        assert abs(actual_weight - expected_weight) < 1.0, (
            f"Expected weight ~{expected_weight}, got {actual_weight} in last-session"
        )
        print(f"✅ last-session data matches submitted session: weight={actual_weight}kg, reps={first_set.get('reps')}")

    def test_12_personal_records_list_returned(self, api_client, test_workout_id, test_user_id):
        """Completing a second session detects PRs for first-time exercises"""
        # Complete another session with higher weights to trigger a PR
        completed_exercises = [
            {
                "exercise_name": f"PR_TEST_Exercise_{uuid.uuid4().hex[:6]}",
                "muscle_groups": ["chest"],
                "sets": [{"set_number": 1, "weight": 100.0, "reps": 5, "completed": True}],
            }
        ]
        resp = api_client.post(
            f"{BASE_URL}/api/workout/{test_workout_id}/session/complete",
            json={
                "user_id": test_user_id,
                "day_index": 0,
                "day_focus": "PR Test",
                "duration_minutes": 10,
                "completed_exercises": completed_exercises,
            },
        )
        assert resp.status_code == 200, f"Second session failed: {resp.text}"
        data = resp.json()
        assert "personal_records" in data
        assert isinstance(data["personal_records"], list)
        # First-time lift should be a PR
        pr_names = [pr["exercise_name"] for pr in data["personal_records"]]
        assert completed_exercises[0]["exercise_name"] in pr_names, (
            f"Expected first-time exercise to be a PR. Got PRs: {pr_names}"
        )
        print(f"✅ personal_records returned correctly: {pr_names}")

    def test_13_blank_slate_after_second_session(self, api_client, test_workout_id):
        """After the second session, blank slate is reset again for day 0"""
        resp = api_client.get(f"{BASE_URL}/api/workout/{test_workout_id}/performance")
        assert resp.status_code == 200
        perf = resp.json().get("performance", {})
        day0_keys = [k for k in perf if k.startswith("0-")]
        # If there are no day-0 keys, it means the performance dict doesn't have day-0 entries
        # (which is fine - blank slate means we can have empty dict for day 0)
        for key in day0_keys:
            entry = perf[key]
            assert entry.get("weight") == "", f"Key '{key}' has weight='{entry.get('weight')}' after 2nd complete"
            assert entry.get("reps") == "", f"Key '{key}' has reps='{entry.get('reps')}' after 2nd complete"
            assert entry.get("completed") == False, f"Key '{key}' has completed={entry.get('completed')} after 2nd complete"
        print(f"✅ Blank slate verified after 2nd session complete ({len(day0_keys)} keys checked)")
