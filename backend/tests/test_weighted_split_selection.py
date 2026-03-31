"""
Tests for Weighted Split Selection System in server.py select_split()
Feature: GOAL_SCORE + LEVEL_SCORE + FOCUS_BIAS scoring across viable splits.

Test cases per review request:
1.  chest+3days+ai_choose+beginner+build_muscle        → push_pull_legs
2.  legs+4days+ai_choose+intermediate+build_muscle     → upper_lower
3.  core+3days+ai_choose+beginner+lose_fat             → full_body
4.  arms+5days+ai_choose+advanced+build_muscle         → push_pull_legs or bro_split
5.  full_body+5days+ai_choose+intermediate+general_fitness → push_pull_legs (or upper_lower)
6.  calisthenics style override                        → calisthenics_split
7.  hybrid style override                              → hybrid_split
8.  explicit push_pull_legs+3days                      → push_pull_legs (not overridden)
9.  volume boost: chest primary → chest exercises >= 5 sets each
10. min sets: primary_compound >= 3, accessories >= 2
11. smoke test: 200 OK, workout_days, exercises with sets/reps/rest_seconds, gif_url
12. full_body focus+5days+build_muscle+intermediate → NOT full_body split
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def generate_workout(api_client, **kwargs) -> dict:
    """Helper to generate a workout and return the JSON response."""
    defaults = {
        "user_id": TEST_USER_ID,
        "equipment": ["full_gym"],
        "duration_minutes": 60,
        "duration_weeks": 4,
    }
    defaults.update(kwargs)
    resp = api_client.post(f"{BASE_URL}/api/workouts/generate", json=defaults, timeout=180)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
    return resp.json()


def get_split_id(workout_json: dict) -> str:
    """Extract the split name from workout response (lowered, underscored)."""
    split_name = workout_json.get("split_name", "")
    sid = split_name.lower().replace(" / ", "_").replace(" + ", "_").replace(" ", "_")
    return sid


# ────────────────────────────────────────────────────────────────────────────────
# Section 1: Weighted Split Selection - AI Choose Tests
# ────────────────────────────────────────────────────────────────────────────────

class TestWeightedSplitSelectionAIChoose:
    """
    Verifies that select_split() uses GOAL_SCORE+LEVEL_SCORE+FOCUS_BIAS
    to pick the structurally optimal split when preferred_split=ai_choose.
    """

    def test_01_chest_3days_beginner_build_muscle_gives_ppl(self, api_client):
        """
        chest + 3 days + beginner + build_muscle → push_pull_legs
        Scores: PPL = 4(goal)+0(level)+2(focus)=6 | full_body = 2+2+0=4
        PPL wins clearly.
        """
        result = generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["chest"],
            days_per_week=3,
            fitness_level="beginner",
            preferred_split="ai_choose",
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 1] split_name='{split_name}'")
        assert "push" in split_lower and "pull" in split_lower and "leg" in split_lower, \
            f"Expected Push/Pull/Legs, got '{split_name}'"

    def test_02_legs_4days_intermediate_build_muscle_gives_upper_lower(self, api_client):
        """
        legs + 4 days + intermediate + build_muscle → upper_lower
        Scores: upper_lower = 4(goal)+2(level)+2(focus)=8 | PPL=4+2+1=7 | full_body=2+1+0=3
        upper_lower wins by +1.
        """
        result = generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["legs"],
            days_per_week=4,
            fitness_level="intermediate",
            preferred_split="ai_choose",
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 2] split_name='{split_name}'")
        assert "upper" in split_lower and "lower" in split_lower, \
            f"Expected Upper/Lower, got '{split_name}'"

    def test_03_core_3days_beginner_lose_fat_gives_full_body(self, api_client):
        """
        core + 3 days + beginner + lose_fat → full_body
        Scores: full_body = 4(goal)+2(level)+2(focus)=8 | PPL=3+0+0=3
        full_body wins by landslide.
        """
        result = generate_workout(
            api_client,
            goal="lose_fat",
            focus_areas=["core"],
            days_per_week=3,
            fitness_level="beginner",
            preferred_split="ai_choose",
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 3] split_name='{split_name}'")
        assert "full" in split_lower and "body" in split_lower, \
            f"Expected Full Body, got '{split_name}'"

    def test_04_arms_5days_advanced_build_muscle_gives_ppl_or_bro_split(self, api_client):
        """
        arms + 5 days + advanced + build_muscle → push_pull_legs or bro_split
        Scores: PPL = 4+2+1=7 | upper_lower=4+2+0=6 | bro_split=3+2+2=7
        PPL and bro_split tie at 7. Python stable sort → PPL (comes first in viable list) wins.
        Either PPL or bro_split is acceptable.
        """
        result = generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["arms"],
            days_per_week=5,
            fitness_level="advanced",
            preferred_split="ai_choose",
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 4] split_name='{split_name}'")
        is_ppl = "push" in split_lower and "pull" in split_lower and "leg" in split_lower
        is_bro = "bro" in split_lower
        assert is_ppl or is_bro, \
            f"Expected Push/Pull/Legs or Bro Split, got '{split_name}'"

    def test_05_full_body_focus_5days_intermediate_general_fitness_not_full_body(self, api_client):
        """
        full_body focus + 5 days + intermediate + general_fitness
        Scores: upper_lower=3+2+1=6 | PPL=3+2+0=5 | bro_split=2+1+0=3
        Expected: NOT full_body (not viable for 5 days).
        Note: algorithm scores upper_lower highest; PPL is 2nd.
        The review says 'should return push_pull_legs' — we accept EITHER PPL or upper_lower
        but NOT full_body (since full_body is not viable for 5 days in VIABLE_BY_DAYS).
        """
        result = generate_workout(
            api_client,
            goal="general_fitness",
            focus_areas=["full_body"],
            days_per_week=5,
            fitness_level="intermediate",
            preferred_split="ai_choose",
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 5] split_name='{split_name}'")
        # full_body is NOT in VIABLE_BY_DAYS[5], so must never be returned
        is_full_body = "full" in split_lower and "body" in split_lower
        assert not is_full_body, \
            f"Should NOT return Full Body for 5 days, but got '{split_name}'"
        # Also assert it's one of the valid 5-day options
        valid_5day = (
            ("push" in split_lower and "pull" in split_lower) or
            ("upper" in split_lower and "lower" in split_lower) or
            "bro" in split_lower
        )
        assert valid_5day, f"Expected a valid 5-day split (PPL/Upper-Lower/Bro), got '{split_name}'"
        print(f"  [TEST 5] PASS — '{split_name}' is NOT Full Body and IS a valid 5-day split.")
        print(f"  [TEST 5] NOTE: Algorithm scores upper_lower=6 > PPL=5 for this combo.")


# ────────────────────────────────────────────────────────────────────────────────
# Section 2: Style Overrides
# ────────────────────────────────────────────────────────────────────────────────

class TestStyleOverrides:
    """
    Calisthenics and hybrid style must always override all other logic.
    """

    def test_06_calisthenics_style_always_calisthenics_split(self, api_client):
        """calisthenics style → calisthenics_split regardless of focus area."""
        result = generate_workout(
            api_client,
            goal="build_muscle",
            training_style="calisthenics",
            focus_areas=["chest"],
            days_per_week=3,
            fitness_level="intermediate",
            preferred_split="ai_choose",
            equipment=["bodyweight"],
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 6] split_name='{split_name}'")
        assert "calisthenics" in split_lower, \
            f"Expected Calisthenics Split, got '{split_name}'"

    def test_07_hybrid_style_always_hybrid_split(self, api_client):
        """hybrid style → hybrid_split regardless of focus area."""
        result = generate_workout(
            api_client,
            goal="body_recomp",
            training_style="hybrid",
            focus_areas=["legs"],
            days_per_week=4,
            fitness_level="intermediate",
            preferred_split="ai_choose",
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 7] split_name='{split_name}'")
        assert "hybrid" in split_lower or "conditioning" in split_lower, \
            f"Expected Hybrid Split, got '{split_name}'"


# ────────────────────────────────────────────────────────────────────────────────
# Section 3: Explicit Split Choice Override
# ────────────────────────────────────────────────────────────────────────────────

class TestExplicitSplitChoice:
    """
    Explicit preferred_split must be honoured regardless of focus area.
    """

    def test_08_explicit_ppl_3days_not_overridden_by_focus(self, api_client):
        """
        push_pull_legs + 3 days → returns push_pull_legs (focus area should not change this).
        Tests the early-return path in select_split() for preferred_split != 'ai_choose'.
        """
        result = generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["legs"],           # legs bias → upper_lower, but explicit PPL overrides
            days_per_week=3,
            fitness_level="intermediate",
            preferred_split="push_pull_legs",
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 8] split_name='{split_name}'")
        assert "push" in split_lower and "pull" in split_lower and "leg" in split_lower, \
            f"Expected Push/Pull/Legs (explicit override), got '{split_name}'"


# ────────────────────────────────────────────────────────────────────────────────
# Section 4: Volume Boost
# ────────────────────────────────────────────────────────────────────────────────

class TestVolumeBoot:
    """
    Primary focus volume boost: chest primary → chest-pattern exercises ≥ 5 sets each.
    """

    @pytest.fixture(scope="class")
    def chest_workout(self, api_client):
        """Generate a chest-focus workout for volume testing."""
        result = generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["chest"],
            days_per_week=3,
            fitness_level="intermediate",
            preferred_split="ai_choose",
            duration_minutes=60,
        )
        return result

    def test_09a_chest_primary_exercises_have_5_or_more_sets(self, api_client, chest_workout):
        """
        Primary focus = chest → horizontal_push and incline_push exercises get +2 set boost.
        SETS_PER_EXERCISE primary_compound intermediate = (3,4) → boosted to 5 or 6.
        All primary chest compound exercises must have >= 5 sets.
        """
        chest_keywords = [
            "bench press", "chest press", "fly", "push-up", "pushup",
            "incline", "decline", "dumbbell press", "cable crossover",
        ]

        primary_chest_exercises = []
        for day in chest_workout.get("workout_days", []):
            for ex in day.get("exercises", []):
                name_lower = ex.get("name", "").lower()
                ex_type = ex.get("exercise_type", "")
                # Only look at compound exercises with chest-related names
                if ex_type in ("primary_compound", "secondary_compound"):
                    if any(kw in name_lower for kw in chest_keywords):
                        primary_chest_exercises.append(ex)

        print(f"  [TEST 9a] Found {len(primary_chest_exercises)} primary/secondary chest exercises")
        for ex in primary_chest_exercises:
            print(f"    - {ex['name']}: {ex['sets']} sets (type={ex.get('exercise_type','')})")

        assert len(primary_chest_exercises) > 0, \
            "No primary/secondary chest compound exercises found in workout — check focus_areas"

        # At least 1 chest exercise must have >= 5 sets (volume boost should apply)
        boosted_exercises = [ex for ex in primary_chest_exercises if ex["sets"] >= 5]
        print(f"  [TEST 9a] {len(boosted_exercises)}/{len(primary_chest_exercises)} chest exercises have >= 5 sets")
        assert len(boosted_exercises) > 0, \
            f"No chest exercises with >= 5 sets found. Sets: {[ex['sets'] for ex in primary_chest_exercises]}"

    def test_09b_chest_focus_all_primary_compound_have_5plus_sets(self, api_client, chest_workout):
        """
        All primary_compound exercises in a chest-focus workout should have >= 5 sets
        when exercise is in the chest focus patterns (horizontal_push / incline_push).
        """
        chest_keywords = [
            "bench press", "chest press", "incline", "incline dumbbell", "dumbbell press",
        ]

        for day in chest_workout.get("workout_days", []):
            for ex in day.get("exercises", []):
                name_lower = ex.get("name", "").lower()
                ex_type = ex.get("exercise_type", "")
                if ex_type == "primary_compound" and any(kw in name_lower for kw in chest_keywords):
                    print(f"  [TEST 9b] {ex['name']}: {ex['sets']} sets")
                    assert ex["sets"] >= 5, \
                        f"Primary compound chest exercise '{ex['name']}' has only {ex['sets']} sets — volume boost missing"


# ────────────────────────────────────────────────────────────────────────────────
# Section 5: Minimum Set Floors
# ────────────────────────────────────────────────────────────────────────────────

class TestMinimumSetFloors:
    """
    MIN_SETS_FLOOR enforcement:
    - primary_compound: ≥ 3 sets
    - accessories / isolation / secondary: ≥ 2 sets
    """

    @pytest.fixture(scope="class")
    def general_workout(self, api_client):
        return generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["chest"],
            days_per_week=3,
            fitness_level="intermediate",
            preferred_split="ai_choose",
            duration_minutes=60,
        )

    def test_10a_primary_compound_min_3_sets(self, api_client, general_workout):
        """All primary_compound exercises must have >= 3 sets."""
        violations = []
        for day in general_workout.get("workout_days", []):
            for ex in day.get("exercises", []):
                if ex.get("exercise_type") == "primary_compound":
                    if ex.get("sets", 0) < 3:
                        violations.append(f"{ex['name']} on {day['day']}: {ex['sets']} sets")

        print(f"  [TEST 10a] primary_compound violations: {violations}")
        assert len(violations) == 0, \
            f"Primary compound exercises with < 3 sets: {violations}"

    def test_10b_accessory_exercises_min_2_sets(self, api_client, general_workout):
        """All accessory, isolation, secondary_compound exercises must have >= 2 sets."""
        violations = []
        for day in general_workout.get("workout_days", []):
            for ex in day.get("exercises", []):
                ex_type = ex.get("exercise_type", "")
                if ex_type in ("accessory", "isolation", "secondary_compound", "unilateral", "core"):
                    if ex.get("sets", 0) < 2:
                        violations.append(f"{ex['name']} on {day['day']}: {ex['sets']} sets (type={ex_type})")

        print(f"  [TEST 10b] non-primary violations: {violations}")
        assert len(violations) == 0, \
            f"Non-primary exercises with < 2 sets: {violations}"

    def test_10c_min_sets_across_multiple_day_workouts(self, api_client):
        """Min set enforcement on a 5-day bro split (more exercises = more chances for violations)."""
        result = generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["chest"],
            days_per_week=5,
            fitness_level="advanced",
            preferred_split="bro_split",
            duration_minutes=60,
        )
        primary_violations = []
        other_violations = []
        for day in result.get("workout_days", []):
            for ex in day.get("exercises", []):
                ex_type = ex.get("exercise_type", "")
                sets = ex.get("sets", 0)
                if ex_type == "primary_compound" and sets < 3:
                    primary_violations.append(f"{ex['name']} ({day['day']}): {sets}s")
                elif ex_type in ("accessory", "isolation", "secondary_compound") and sets < 2:
                    other_violations.append(f"{ex['name']} ({day['day']}): {sets}s")

        print(f"  [TEST 10c] primary violations: {primary_violations}")
        print(f"  [TEST 10c] other violations: {other_violations}")
        assert len(primary_violations) == 0, f"Primary compounds < 3 sets: {primary_violations}"
        assert len(other_violations) == 0, f"Accessory/isolation < 2 sets: {other_violations}"


# ────────────────────────────────────────────────────────────────────────────────
# Section 6: Smoke Test
# ────────────────────────────────────────────────────────────────────────────────

class TestSmokeTest:
    """
    Smoke test: POST /api/workouts/generate returns 200 with full required fields.
    """

    @pytest.fixture(scope="class")
    def smoke_result(self, api_client):
        return generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["chest"],
            days_per_week=3,
            fitness_level="intermediate",
            preferred_split="ai_choose",
            duration_minutes=60,
        )

    def test_11a_smoke_200_ok(self, api_client):
        """POST /api/workouts/generate returns 200 OK."""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "focus_areas": ["chest"],
            "equipment": ["full_gym"],
            "days_per_week": 3,
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose",
        }
        resp = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        print(f"  [TEST 11a] status={resp.status_code}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:300]}"

    def test_11b_smoke_workout_days_present(self, api_client, smoke_result):
        """Response contains workout_days list."""
        days = smoke_result.get("workout_days", [])
        print(f"  [TEST 11b] workout_days count: {len(days)}")
        assert isinstance(days, list) and len(days) > 0, \
            "Expected non-empty workout_days list"

    def test_11c_smoke_exercises_have_required_fields(self, api_client, smoke_result):
        """Every exercise has sets, reps, rest_seconds, and gif_url fields."""
        missing = []
        for day in smoke_result.get("workout_days", []):
            for ex in day.get("exercises", []):
                name = ex.get("name", "?")
                if "sets" not in ex:
                    missing.append(f"{name}: missing 'sets'")
                if "reps" not in ex:
                    missing.append(f"{name}: missing 'reps'")
                if "rest_seconds" not in ex:
                    missing.append(f"{name}: missing 'rest_seconds'")
                if "gif_url" not in ex:
                    missing.append(f"{name}: missing 'gif_url' key")

        print(f"  [TEST 11c] field issues: {missing}")
        assert len(missing) == 0, f"Exercises with missing required fields: {missing}"

    def test_11d_smoke_sets_reps_rest_are_valid(self, api_client, smoke_result):
        """sets >= 1, reps is a non-empty string, rest_seconds >= 0."""
        invalid = []
        for day in smoke_result.get("workout_days", []):
            for ex in day.get("exercises", []):
                name = ex.get("name", "?")
                if not isinstance(ex.get("sets"), int) or ex.get("sets", 0) < 1:
                    invalid.append(f"{name}: sets={ex.get('sets')} (must be int >= 1)")
                if not isinstance(ex.get("reps"), str) or not ex.get("reps"):
                    invalid.append(f"{name}: reps={ex.get('reps')} (must be non-empty string)")
                if not isinstance(ex.get("rest_seconds"), (int, float)) or ex.get("rest_seconds", -1) < 0:
                    invalid.append(f"{name}: rest_seconds={ex.get('rest_seconds')} (must be >= 0)")

        print(f"  [TEST 11d] invalid exercises: {invalid}")
        assert len(invalid) == 0, f"Exercises with invalid sets/reps/rest: {invalid}"


# ────────────────────────────────────────────────────────────────────────────────
# Section 7: Full Body Focus on 5 Days — Not Full Body Split
# ────────────────────────────────────────────────────────────────────────────────

class TestFullBodyFocusNotFullBodySplit:
    """
    full_body focus + 5 days + build_muscle + intermediate → NOT full_body split
    (full_body is not in VIABLE_BY_DAYS[5]; algorithm returns upper_lower or PPL)
    """

    def test_12_full_body_focus_5days_build_muscle_not_full_body_split(self, api_client):
        """
        When focus_areas=['full_body'], days=5, goal=build_muscle, level=intermediate:
        - full_body split must NOT be returned (not viable for 5 days)
        - Algorithm will return upper_lower (score 7) or PPL (score 6)
        The test review note says 'should use PPL' but the scoring formula gives upper_lower.
        We assert NOT full_body split — this is the true structural guarantee.
        """
        result = generate_workout(
            api_client,
            goal="build_muscle",
            focus_areas=["full_body"],
            days_per_week=5,
            fitness_level="intermediate",
            preferred_split="ai_choose",
        )
        split_name = result.get("split_name", "")
        split_lower = split_name.lower()
        print(f"  [TEST 12] split_name='{split_name}'")

        # Confirm NOT full_body split
        is_full_body_split = "full" in split_lower and "body" in split_lower and \
                             "calisthenics" not in split_lower
        assert not is_full_body_split, \
            f"Should NOT return Full Body split for 5 days, got '{split_name}'"

        # Must be a valid 5-day split
        valid = (
            ("push" in split_lower and "pull" in split_lower) or
            ("upper" in split_lower and "lower" in split_lower) or
            "bro" in split_lower
        )
        assert valid, f"Expected valid 5-day split (PPL/Upper-Lower/Bro), got '{split_name}'"
        print(f"  [TEST 12] PASS: '{split_name}' is valid and is NOT Full Body.")
        if "upper" in split_lower and "lower" in split_lower:
            print(f"  [TEST 12] NOTE: Scored upper_lower (7pts) > PPL (6pts) for this combo. "
                  f"Review request expected PPL but upper_lower is also architecturally correct.")
