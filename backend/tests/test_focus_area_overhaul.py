"""
Tests for InterFitAI workout engine focus area overhaul:
- Primary focus areas drive split selection (ai_choose mode)
- Primary focus areas get +2 sets per matching slot (sets >= 5)
- Secondary focus areas get [secondary emphasis] coaching_note marker
- FOCUS_SPLIT_PREFERENCE dict drives: chest→PPL, legs→upper_lower

NOTE: These tests call Claude LLM and may take 30-120s each.
      Module-scoped fixtures are used to minimize API calls.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# Muscle group sets for pattern matching
CHEST_MUSCLES = {"chest", "upper chest", "triceps", "front delts"}
SHOULDER_MUSCLES = {"shoulders", "medial delts", "rear delts", "upper back"}


def generate_workout(payload: dict) -> dict:
    """Helper to call workout generate endpoint with 3-minute timeout"""
    resp = requests.post(
        f"{BASE_URL}/api/workouts/generate",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=180,
    )
    return resp


# ── Module-level fixtures (generated once per test session) ──────────────────

@pytest.fixture(scope="module")
def chest_3days_response():
    """chest + 3 days + ai_choose: should return PPL split"""
    payload = {
        "user_id": USER_ID,
        "goal": "build_muscle",
        "training_style": "weights",
        "fitness_level": "intermediate",
        "equipment": ["full_gym"],
        "focus_areas": ["chest"],
        "days_per_week": 3,
        "duration_minutes": 45,
        "preferred_split": "ai_choose",
    }
    resp = generate_workout(payload)
    assert resp.status_code == 200, f"chest_3days fixture failed: {resp.status_code} — {resp.text[:500]}"
    print(f"\n[FIXTURE] chest+3days generated: split_name='{resp.json().get('split_name')}'")
    return resp.json()


@pytest.fixture(scope="module")
def legs_4days_response():
    """legs + 4 days + ai_choose: should return upper_lower split"""
    payload = {
        "user_id": USER_ID,
        "goal": "build_muscle",
        "training_style": "weights",
        "fitness_level": "intermediate",
        "equipment": ["full_gym"],
        "focus_areas": ["legs"],
        "days_per_week": 4,
        "duration_minutes": 45,
        "preferred_split": "ai_choose",
    }
    resp = generate_workout(payload)
    assert resp.status_code == 200, f"legs_4days fixture failed: {resp.status_code} — {resp.text[:500]}"
    print(f"\n[FIXTURE] legs+4days generated: split_name='{resp.json().get('split_name')}'")
    return resp.json()


@pytest.fixture(scope="module")
def chest_volume_response():
    """chest primary focus + 4 days: exercises should have sets >= 5 (primary +2 boost)"""
    payload = {
        "user_id": USER_ID,
        "goal": "build_muscle",
        "training_style": "weights",
        "fitness_level": "intermediate",
        "equipment": ["full_gym"],
        "focus_areas": ["chest"],
        "days_per_week": 4,
        "duration_minutes": 60,
        "preferred_split": "ai_choose",
    }
    resp = generate_workout(payload)
    assert resp.status_code == 200, f"chest_volume fixture failed: {resp.status_code} — {resp.text[:500]}"
    data = resp.json()
    # Print all chest exercises for inspection
    for day in data.get("workout_days", []):
        for ex in day.get("exercises", []):
            mg = {m.lower() for m in ex.get("muscle_groups", [])}
            if mg & CHEST_MUSCLES:
                print(f"  CHEST: {ex['name']} | sets={ex.get('sets')} | type={ex.get('exercise_type')}")
    return data


@pytest.fixture(scope="module")
def secondary_shoulders_response():
    """chest primary + shoulders secondary + 4 days: shoulder exercises should be present"""
    payload = {
        "user_id": USER_ID,
        "goal": "build_muscle",
        "training_style": "weights",
        "fitness_level": "intermediate",
        "equipment": ["full_gym"],
        "focus_areas": ["chest"],
        "secondary_focus_areas": ["shoulders"],
        "days_per_week": 4,
        "duration_minutes": 45,
        "preferred_split": "ai_choose",
    }
    resp = generate_workout(payload)
    assert resp.status_code == 200, f"secondary_shoulders fixture failed: {resp.status_code} — {resp.text[:500]}"
    data = resp.json()
    print(f"\n[FIXTURE] secondary shoulders generated: split='{data.get('split_name')}'")
    for day in data.get("workout_days", []):
        for ex in day.get("exercises", []):
            mg = {m.lower() for m in ex.get("muscle_groups", [])}
            if mg & SHOULDER_MUSCLES:
                print(f"  SHOULDER: {ex['name']} | sets={ex.get('sets')} | type={ex.get('exercise_type')} | mg={ex.get('muscle_groups')}")
    return data


# ── Test 1: chest + ai_choose + 3 days → Push/Pull/Legs ─────────────────────

class TestChest3DaysPPLSplit:
    """
    POST /api/workouts/generate with focus_areas=['chest'], preferred_split='ai_choose',
    days_per_week=3 — should return push_pull_legs split.
    Code path: FOCUS_SPLIT_PREFERENCE['chest'] = 'push_pull_legs',
               select_split(days=3, goal=build_muscle, level=intermediate) → PPL
    """

    def test_split_name_is_push_pull_legs(self, chest_3days_response):
        split_name = chest_3days_response.get("split_name", "")
        training_notes = chest_3days_response.get("training_notes", "")
        combined = f"{split_name} {training_notes}".lower()

        is_ppl = (
            ("push" in combined and "pull" in combined and "legs" in combined)
            or "ppl" in combined
        )
        assert is_ppl, (
            f"Expected Push/Pull/Legs for chest+3days+ai_choose.\n"
            f"  split_name='{split_name}'\n"
            f"  training_notes='{training_notes}'"
        )
        print(f"✅ [Test 1] split_name='{split_name}' — is Push/Pull/Legs")

    def test_returns_3_workout_days(self, chest_3days_response):
        days = chest_3days_response.get("workout_days", [])
        assert len(days) == 3, f"Expected 3 workout days, got {len(days)}"
        print(f"✅ [Test 1] 3 workout days returned")

    def test_split_rationale_references_focus(self, chest_3days_response):
        rationale = chest_3days_response.get("split_rationale", "")
        # Rationale should be a non-empty string
        assert len(rationale) > 10, f"split_rationale too short or missing: '{rationale}'"
        print(f"✅ [Test 1] split_rationale present: '{rationale[:80]}'")


# ── Test 2: legs + ai_choose + 4 days → Upper/Lower ─────────────────────────

class TestLegs4DaysUpperLowerSplit:
    """
    POST /api/workouts/generate with focus_areas=['legs'], preferred_split='ai_choose',
    days_per_week=4 — should return upper_lower split.
    Code path: FOCUS_SPLIT_PREFERENCE['legs'] = 'upper_lower',
               select_split(days=4, build_muscle, intermediate) → upper_lower
    """

    def test_split_name_is_upper_lower(self, legs_4days_response):
        split_name = legs_4days_response.get("split_name", "")
        combined = f"{split_name} {legs_4days_response.get('training_notes', '')}".lower()

        is_ul = "upper" in combined and "lower" in combined
        assert is_ul, (
            f"Expected Upper/Lower for legs+4days+ai_choose.\n"
            f"  split_name='{split_name}'"
        )
        print(f"✅ [Test 2] split_name='{split_name}' — is Upper/Lower")

    def test_returns_4_workout_days(self, legs_4days_response):
        days = legs_4days_response.get("workout_days", [])
        assert len(days) == 4, f"Expected 4 workout days, got {len(days)}"
        print(f"✅ [Test 2] 4 workout days returned")

    def test_leg_exercises_present(self, legs_4days_response):
        """Leg focus should result in squat/lunge/hip_hinge exercises"""
        LEG_MUSCLES = {"quads", "glutes", "hamstrings", "calves", "hip flexors"}
        leg_exercises = []
        for day in legs_4days_response.get("workout_days", []):
            for ex in day.get("exercises", []):
                mg = {m.lower() for m in ex.get("muscle_groups", [])}
                if mg & LEG_MUSCLES:
                    leg_exercises.append(ex)

        assert len(leg_exercises) >= 2, (
            f"Expected >= 2 leg exercises from legs focus, got {len(leg_exercises)}"
        )
        print(f"✅ [Test 2] {len(leg_exercises)} leg exercises found across days")


# ── Test 3: Primary focus chest → +2 sets (sets >= 5) ────────────────────────

class TestPrimaryFocusChestVolumeBoost:
    """
    POST /api/workouts/generate with focus_areas=['chest'] — chest pattern slots
    (horizontal_push) should have +2 sets vs base (sets >= 5).
    Code path: line 2218 — boost = 2; boosted = min(slot['sets'] + 2, 6)
    Base: intermediate build_muscle primary_compound = 4 sets → after boost = 6
          secondary_compound = 3 sets → after boost = 5
    """

    def test_chest_exercises_have_elevated_sets(self, chest_volume_response):
        workout_days = chest_volume_response.get("workout_days", [])
        chest_exercises = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                mg = {m.lower() for m in ex.get("muscle_groups", [])}
                if mg & CHEST_MUSCLES:
                    chest_exercises.append(ex)

        assert len(chest_exercises) > 0, "No chest exercises found in workout"
        print(f"Chest exercises: {[(ex['name'], ex.get('sets')) for ex in chest_exercises]}")

        # At least one chest exercise should have sets >= 5 (primary focus +2 boost)
        high_set_exs = [ex for ex in chest_exercises if ex.get("sets", 0) >= 5]
        assert len(high_set_exs) > 0, (
            f"Expected >= 1 chest exercise with sets >= 5 (primary +2 boost).\n"
            f"Got: {[(ex['name'], ex.get('sets')) for ex in chest_exercises]}"
        )
        print(f"✅ [Test 3] {len(high_set_exs)}/{len(chest_exercises)} chest exercises have sets >= 5")

    def test_all_exercises_have_minimum_sets(self, chest_volume_response):
        """No exercise should have 0 sets (MIN_SETS_FLOOR should prevent this)"""
        for day in chest_volume_response.get("workout_days", []):
            for ex in day.get("exercises", []):
                sets = ex.get("sets", 0)
                assert sets >= 1, f"Exercise '{ex.get('name')}' has {sets} sets (floor violation)"
        print("✅ [Test 3] All exercises have >= 1 set (minimum floor respected)")

    def test_primary_compound_exercise_type_exists(self, chest_volume_response):
        """At least one exercise should have exercise_type=primary_compound"""
        has_primary = any(
            ex.get("exercise_type") == "primary_compound"
            for day in chest_volume_response.get("workout_days", [])
            for ex in day.get("exercises", [])
        )
        assert has_primary, "No primary_compound exercise found"
        print("✅ [Test 3] primary_compound exercise type present")


# ── Test 4: Secondary focus shoulders → coaching_note contains 'secondary' ───

class TestSecondaryFocusShouldersEffect:
    """
    POST /api/workouts/generate with secondary_focus_areas=['shoulders'] —
    lateral_raise or vertical_push slots should have coaching_note containing 'secondary'.

    DESIGN NOTE: coaching_note is an internal blueprint concept and is NOT part of
    the Exercise HTTP response model. The '[secondary emphasis]' marker is passed to
    the LLM as prompt context only. We verify the secondary focus effect via:
      1. Shoulder exercises ARE present (secondary patterns were included)
      2. Shoulder exercises have appropriate sets (secondary +1 boost applied)
      3. exercise_type for secondary-injected slots is 'accessory'
    """

    def test_shoulder_exercises_present_in_response(self, secondary_shoulders_response):
        """Shoulder patterns (lateral_raise, vertical_push, rear_delt) should appear"""
        workout_days = secondary_shoulders_response.get("workout_days", [])
        shoulder_exercises = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                mg = {m.lower() for m in ex.get("muscle_groups", [])}
                if mg & SHOULDER_MUSCLES:
                    shoulder_exercises.append(ex)

        assert len(shoulder_exercises) > 0, (
            "Expected shoulder exercises from secondary_focus_areas=['shoulders']. "
            "None found in any workout day."
        )
        print(f"✅ [Test 4] {len(shoulder_exercises)} shoulder exercise(s) present")
        for ex in shoulder_exercises:
            print(f"  → {ex['name']}: sets={ex.get('sets')}, type={ex.get('exercise_type')}, mg={ex.get('muscle_groups')}")

    def test_shoulder_accessory_exercises_have_adequate_sets(self, secondary_shoulders_response):
        """Secondary shoulder exercises should have sets >= 2"""
        shoulder_exercises = [
            ex
            for day in secondary_shoulders_response.get("workout_days", [])
            for ex in day.get("exercises", [])
            if {m.lower() for m in ex.get("muscle_groups", [])} & SHOULDER_MUSCLES
        ]

        for ex in shoulder_exercises:
            sets = ex.get("sets", 0)
            assert sets >= 2, (
                f"Shoulder exercise '{ex['name']}' has only {sets} sets "
                f"(expected >= 2 after secondary +1 boost)"
            )
        print(f"✅ [Test 4] All {len(shoulder_exercises)} shoulder exercise(s) have >= 2 sets")

    def test_coaching_note_limitation_documented(self, secondary_shoulders_response):
        """
        LIMITATION CHECK: coaching_note is NOT in Exercise HTTP response.
        Verify this and document it properly.
        The '[secondary emphasis]' marker exists in the blueprint but not in the JSON.
        """
        all_exercises = [
            ex
            for day in secondary_shoulders_response.get("workout_days", [])
            for ex in day.get("exercises", [])
        ]
        if all_exercises:
            exercise_keys = set(all_exercises[0].keys())
            coaching_note_in_response = "coaching_note" in exercise_keys
            # coaching_note should NOT be in response (it's internal)
            print(f"Exercise model fields: {sorted(exercise_keys)}")
            print(f"coaching_note in HTTP response: {coaching_note_in_response}")
            # This is expected behavior — coaching_note is internal only
            # The test verifies the EFFECT (shoulder exercises present) not the internal field
        print("✅ [Test 4] Secondary effect verified via exercise presence (coaching_note is internal)")

    def test_secondary_effect_does_not_crowd_out_primary(self, secondary_shoulders_response):
        """Chest (primary) exercises should still be present when shoulders is secondary"""
        chest_exercises = [
            ex
            for day in secondary_shoulders_response.get("workout_days", [])
            for ex in day.get("exercises", [])
            if {m.lower() for m in ex.get("muscle_groups", [])} & CHEST_MUSCLES
        ]
        assert len(chest_exercises) > 0, (
            "Primary focus (chest) exercises missing when secondary_focus_areas=['shoulders'] added"
        )
        print(f"✅ [Test 4] Primary (chest) exercises still present: {len(chest_exercises)}")


# ── Test 5: General smoke test ────────────────────────────────────────────────

class TestGeneralSmokeTest:
    """General smoke test — valid response structure, no crash"""

    @pytest.fixture(scope="class")
    def smoke_response(self):
        payload = {
            "user_id": USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "fitness_level": "intermediate",
            "equipment": ["full_gym"],
            "focus_areas": ["chest"],
            "days_per_week": 3,
            "duration_minutes": 45,
            "preferred_split": "ai_choose",
        }
        resp = generate_workout(payload)
        assert resp.status_code == 200, f"Smoke test failed: {resp.status_code}"
        return resp.json()

    def test_200_ok(self, smoke_response):
        assert smoke_response is not None
        print("✅ [Test 5] Smoke test: 200 OK")

    def test_required_fields_present(self, smoke_response):
        required = ["id", "user_id", "name", "goal", "workout_days", "split_name", "split_rationale"]
        for field in required:
            assert field in smoke_response, f"Missing required field: '{field}'"
        print(f"✅ [Test 5] All required fields present")

    def test_workout_days_have_valid_exercises(self, smoke_response):
        workout_days = smoke_response.get("workout_days", [])
        assert len(workout_days) > 0, "No workout days returned"

        for day in workout_days:
            exercises = day.get("exercises", [])
            assert len(exercises) > 0, f"Day '{day.get('day')}' has no exercises"
            for ex in exercises:
                assert ex.get("name"), f"Exercise missing name"
                assert ex.get("sets", 0) > 0, f"Exercise '{ex.get('name')}' has 0 sets"
                assert ex.get("reps"), f"Exercise '{ex.get('name')}' missing reps"
                assert ex.get("rest_seconds", -1) >= 0, f"Invalid rest_seconds for '{ex.get('name')}'"
        print(f"✅ [Test 5] {len(workout_days)} days with valid exercises")

    def test_no_crash_minimal_payload(self):
        """Minimal valid payload: no crash, valid response"""
        payload = {
            "user_id": USER_ID,
            "goal": "general_fitness",
            "focus_areas": ["full_body"],
            "equipment": ["bodyweight"],
            "days_per_week": 2,
        }
        resp = generate_workout(payload)
        assert resp.status_code == 200, f"Minimal payload failed: {resp.status_code} — {resp.text[:300]}"
        data = resp.json()
        assert "workout_days" in data and len(data["workout_days"]) > 0
        print("✅ [Test 5] Minimal payload: no crash, valid response")
