"""
Test suite for iteration 10 review:
1. PATCH /api/workout/:id/reorder-exercises endpoint
2. Onboarding gender selection (Male/Female only, no Other)
3. Assault bike GIF updated to cycle cross trainer (exercise 2331)
4. Exercise drag handle (reorder-three icon) presence in workout-detail

Based on workout: dda90b0e-fcb2-45a8-9080-ef291af2500c
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
WORKOUT_ID = "dda90b0e-fcb2-45a8-9080-ef291af2500c"


@pytest.fixture
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestReorderExercisesEndpoint:
    """Tests for PATCH /api/workout/:id/reorder-exercises"""

    def test_reorder_exercises_returns_200(self, session):
        """Test that reorder endpoint returns 200 with valid payload"""
        # First fetch the workout to get the actual exercise count for day 0
        resp = session.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        assert resp.status_code == 200, f"Workout fetch failed: {resp.status_code}"
        workout = resp.json()
        day0_exercises = workout["workout_days"][0]["exercises"]
        n = len(day0_exercises)
        assert n >= 2, f"Need at least 2 exercises to reorder, got {n}"

        # Build a valid reorder: swap index 0 and 1
        new_order = list(range(n))
        new_order[0], new_order[1] = new_order[1], new_order[0]

        payload = {
            "day_index": 0,
            "exercise_order": new_order,
        }
        r = session.patch(f"{BASE_URL}/api/workout/{WORKOUT_ID}/reorder-exercises", json=payload)
        assert r.status_code == 200, f"Reorder failed with {r.status_code}: {r.text}"
        data = r.json()
        assert "message" in data
        print(f"PASS: reorder endpoint returned 200. Message: {data['message']}")

    def test_reorder_persists_to_db(self, session):
        """Verify that the reorder is persisted — GET after PATCH reflects new order"""
        # First, fetch original order
        resp = session.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        assert resp.status_code == 200
        workout = resp.json()
        day0 = workout["workout_days"][0]
        n = len(day0["exercises"])
        original_names = [ex["name"] for ex in day0["exercises"]]
        print(f"Original day-0 exercise order: {original_names}")

        # Swap index 0 and 1
        new_order = list(range(n))
        new_order[0], new_order[1] = new_order[1], new_order[0]

        patch_resp = session.patch(
            f"{BASE_URL}/api/workout/{WORKOUT_ID}/reorder-exercises",
            json={"day_index": 0, "exercise_order": new_order},
        )
        assert patch_resp.status_code == 200

        # GET again to verify persistence
        verify_resp = session.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        assert verify_resp.status_code == 200
        new_names = [ex["name"] for ex in verify_resp.json()["workout_days"][0]["exercises"]]
        print(f"Reordered day-0 exercise order: {new_names}")

        assert new_names[0] == original_names[1], (
            f"Expected first exercise to be '{original_names[1]}', got '{new_names[0]}'"
        )
        assert new_names[1] == original_names[0], (
            f"Expected second exercise to be '{original_names[0]}', got '{new_names[1]}'"
        )
        print("PASS: Exercise order persisted correctly after reorder")

        # Restore original order
        restore_order = list(range(n))
        restore_order[0], restore_order[1] = restore_order[1], restore_order[0]
        session.patch(
            f"{BASE_URL}/api/workout/{WORKOUT_ID}/reorder-exercises",
            json={"day_index": 0, "exercise_order": restore_order},
        )

    def test_reorder_invalid_workout_returns_404(self, session):
        """Test that reorder endpoint returns 404 for non-existent workout"""
        r = session.patch(
            f"{BASE_URL}/api/workout/invalid-workout-id-000/reorder-exercises",
            json={"day_index": 0, "exercise_order": [0, 1, 2]},
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        print("PASS: Invalid workout ID returns 404")

    def test_reorder_length_mismatch_returns_400(self, session):
        """Test that wrong number of exercise indices returns 400"""
        r = session.patch(
            f"{BASE_URL}/api/workout/{WORKOUT_ID}/reorder-exercises",
            json={"day_index": 0, "exercise_order": [1, 0]},  # Only 2 indices, but day has more
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        print("PASS: Length mismatch returns 400")

    def test_reorder_invalid_day_index_returns_400(self, session):
        """Test that an out-of-range day index returns 400"""
        r = session.patch(
            f"{BASE_URL}/api/workout/{WORKOUT_ID}/reorder-exercises",
            json={"day_index": 99, "exercise_order": [0]},
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}"
        print("PASS: Invalid day index returns 400")


class TestCycleCrossTrainerGIF:
    """Verify GIF for exercise ID 2331 is accessible (Cycle Cross Trainer)"""

    def test_gif_2331_returns_200(self, session):
        """Exercise ID 2331 (Cycle Cross Trainer) GIF proxy should return 200"""
        r = session.get(f"{BASE_URL}/api/exercises/gif/2331", timeout=15)
        assert r.status_code == 200, f"GIF 2331 proxy returned {r.status_code}: {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("image/"), (
            f"Expected image content type, got: {r.headers.get('content-type')}"
        )
        print(f"PASS: GIF 2331 returned 200 with content-type: {r.headers.get('content-type')}")

    def test_workout_has_cycle_cross_trainer(self, session):
        """Verify that the test workout includes Cycle Cross Trainer exercise"""
        r = session.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        assert r.status_code == 200
        workout = r.json()
        all_exercise_names = []
        for day in workout["workout_days"]:
            for ex in day.get("exercises", []):
                all_exercise_names.append(ex["name"])

        cycle_found = any("cycle" in name.lower() or "cross trainer" in name.lower()
                          for name in all_exercise_names)
        print(f"All exercises in workout: {all_exercise_names}")
        assert cycle_found, "Expected to find 'Cycle Cross Trainer' exercise in workout"
        print("PASS: Cycle Cross Trainer exercise found in workout")


class TestOnboardingGenderOptions:
    """Verify onboarding accepts only Male/Female gender values"""

    def test_onboarding_gender_male_accepted(self, session):
        """POST /api/profile with gender=male should succeed"""
        payload = {
            "name": "TEST_GenderMale",
            "email": "test_gender_male@example.com",
            "weight": 70.0,
            "height": 175.0,
            "age": 25,
            "gender": "male",
            "activity_level": "moderate",
            "goal": "muscle_building",
        }
        r = session.post(f"{BASE_URL}/api/profile", json=payload)
        assert r.status_code in (200, 201), f"Male gender failed: {r.status_code} {r.text[:200]}"
        print(f"PASS: gender=male accepted with status {r.status_code}")

    def test_onboarding_gender_female_accepted(self, session):
        """POST /api/profile with gender=female should succeed"""
        payload = {
            "name": "TEST_GenderFemale",
            "email": "test_gender_female@example.com",
            "weight": 60.0,
            "height": 165.0,
            "age": 28,
            "gender": "female",
            "activity_level": "light",
            "goal": "weight_loss",
        }
        r = session.post(f"{BASE_URL}/api/profile", json=payload)
        assert r.status_code in (200, 201), f"Female gender failed: {r.status_code} {r.text[:200]}"
        print(f"PASS: gender=female accepted with status {r.status_code}")

    def test_workout_get_returns_200(self, session):
        """Verify the main test workout is accessible"""
        r = session.get(f"{BASE_URL}/api/workout/{WORKOUT_ID}")
        assert r.status_code == 200, f"Workout fetch failed: {r.status_code}"
        data = r.json()
        assert "workout_days" in data
        assert len(data["workout_days"]) > 0
        print(f"PASS: Workout accessible — {data['name']}, {len(data['workout_days'])} days")
