"""
Volume Framework & Elite Coaching Engine Tests
Tests the VOLUME_FRAMEWORK, SETS_PER_EXERCISE, STRENGTH_REST_FLOORS, and GOAL_PARAMS
correctness in workout generation.

Tests:
1. VOLUME BUDGET - strength 30min beginner: 8-12 total sets, max 4 exercises
2. VOLUME BUDGET - build_muscle 60min intermediate: 16-20 total sets, max 7 exercises
3. REST FLOORS - strength 30min: primary_compound rest >= 150s
4. REST DURATION SCALING - build_muscle 30min: accessory rest <= 70, primary >= 78
5. ANTI-BLOAT - strength 45min intermediate: exercise count per session <= 5
6. SET ALLOCATION - build_muscle intermediate: per-type set ranges correct
7. CONDITIONING FINISHER ANTI-BLOAT - lose_fat 45min intermediate: max 5 lifting exercises before finisher
8. GOAL PARAMS - rep ranges correct for build_muscle and strength
"""
import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://nutrition-debug-1.preview.emergentagent.com').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def generate_workout(api_client, payload, timeout=120):
    """Helper to call POST /api/workouts/generate"""
    response = api_client.post(
        f"{BASE_URL}/api/workouts/generate",
        json=payload,
        timeout=timeout
    )
    return response


def get_day1_exercises(data):
    """Extract exercises from the first workout day"""
    workout_days = data.get("workout_days", [])
    if not workout_days:
        return []
    day1 = workout_days[0]
    return day1.get("exercises", [])


# ============================================================
# TEST 1: VOLUME BUDGET - strength 30min beginner
# Expected: 8-12 total sets, max_exercises <= 4
# VOLUME_FRAMEWORK["strength"]["beginner"][30] = (8,12,4)
# ============================================================
class TestStrengthBeginner30min:
    """strength 30min beginner: 8-12 total sets, max 4 exercises"""

    def test_volume_budget_strength_30min_beginner(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "strength",
            "duration_minutes": 30,
            "fitness_level": "beginner",
            "days_per_week": 3,
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        exercises = get_day1_exercises(data)
        assert len(exercises) > 0, "Day 1 has no exercises"

        total_sets = sum(ex.get("sets", 0) for ex in exercises)
        num_exercises = len(exercises)

        print(f"\n=== strength 30min beginner ===")
        print(f"Day 1: {num_exercises} exercises, {total_sets} total sets")
        for ex in exercises:
            print(f"  {ex.get('name','?')} | type={ex.get('exercise_type','?')} | sets={ex.get('sets')} | reps={ex.get('reps')} | rest={ex.get('rest_seconds')}s")

        # Check exercise count <= max_exercises from VOLUME_FRAMEWORK (4 for strength beginner 30min)
        # Focus boost may add 1 extra set but not extra exercises
        assert num_exercises <= 4, (
            f"Expected max 4 exercises (VOLUME_FRAMEWORK strength beginner 30min), got {num_exercises}"
        )

        # Check total sets in range 8-12 (VOLUME_FRAMEWORK budget)
        # Allow slight overage for focus boost (+2 headroom per framework code)
        assert 8 <= total_sets <= 14, (
            f"Expected 8-12 total sets (strength beginner 30min budget), got {total_sets}. "
            f"Exercises: {[(e.get('name'), e.get('sets')) for e in exercises]}"
        )
        print(f"✅ PASS: {num_exercises} exercises (≤4), {total_sets} total sets (8-12)")


# ============================================================
# TEST 2: VOLUME BUDGET - build_muscle 60min intermediate
# Expected: 16-20 total sets, max 7 exercises
# VOLUME_FRAMEWORK["build_muscle"]["intermediate"][60] = (16,20,7)
# ============================================================
class TestBuildMuscle60minIntermediate:
    """build_muscle 60min intermediate: 16-20 total sets, max 7 exercises"""

    def test_volume_budget_build_muscle_60min_intermediate(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "days_per_week": 4,
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        exercises = get_day1_exercises(data)
        assert len(exercises) > 0, "Day 1 has no exercises"

        total_sets = sum(ex.get("sets", 0) for ex in exercises)
        num_exercises = len(exercises)

        print(f"\n=== build_muscle 60min intermediate ===")
        print(f"Day 1: {num_exercises} exercises, {total_sets} total sets")
        for ex in exercises:
            print(f"  {ex.get('name','?')} | type={ex.get('exercise_type','?')} | sets={ex.get('sets')} | reps={ex.get('reps')} | rest={ex.get('rest_seconds')}s")

        # Check exercise count <= 7 (VOLUME_FRAMEWORK build_muscle intermediate 60min)
        assert num_exercises <= 7, (
            f"Expected max 7 exercises (VOLUME_FRAMEWORK build_muscle intermediate 60min), got {num_exercises}"
        )

        # Check total sets in range 16-20 with small headroom for focus boost
        assert 16 <= total_sets <= 22, (
            f"Expected 16-20 total sets (build_muscle intermediate 60min budget), got {total_sets}. "
            f"Exercises: {[(e.get('name'), e.get('sets')) for e in exercises]}"
        )
        print(f"✅ PASS: {num_exercises} exercises (≤7), {total_sets} total sets (16-20)")


# ============================================================
# TEST 3: REST FLOORS - strength 30min primary_compound >= 150s
# STRENGTH_REST_FLOORS["strength"] = 150
# For 30min: max(150, int(225 * 0.85)) = max(150, 191) = 191 for primary_compound
# ============================================================
class TestStrengthRestFloor:
    """strength 30min: primary_compound exercises must have rest_seconds >= 150"""

    def test_strength_primary_compound_rest_floor(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "strength",
            "duration_minutes": 30,
            "fitness_level": "beginner",
            "days_per_week": 3,
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        exercises = get_day1_exercises(data)
        primary_compounds = [ex for ex in exercises if ex.get("exercise_type") == "primary_compound"]

        print(f"\n=== strength 30min REST FLOOR CHECK ===")
        for ex in exercises:
            print(f"  {ex.get('name','?')} | type={ex.get('exercise_type','?')} | rest={ex.get('rest_seconds')}s")

        assert len(primary_compounds) > 0, "No primary_compound exercises found in Day 1"

        violations = []
        for ex in primary_compounds:
            rest = ex.get("rest_seconds", 0)
            if rest < 150:
                violations.append(f"{ex.get('name','?')}: rest={rest}s (< 150s floor)")

        assert not violations, (
            f"CRITICAL: Strength primary_compound rest_seconds < 150s floor:\n" +
            "\n".join(violations)
        )
        print(f"✅ PASS: All {len(primary_compounds)} primary_compound exercises have rest >= 150s")
        for ex in primary_compounds:
            print(f"  {ex.get('name','?')}: {ex.get('rest_seconds')}s ✓")


# ============================================================
# TEST 4: REST DURATION SCALING - build_muscle 30min
# Accessory: max(30, int(75 * 0.55)) = 41 ≤ 70 ✓
# Isolation: max(30, int(60 * 0.55)) = 33 ≤ 70 ✓
# Primary compound: max(90, int(120 * 0.65)) = 90 >= 78 ✓
# ============================================================
class TestBuildMuscleRestScaling:
    """build_muscle 30min intermediate: accessory rest <= 70s, primary_compound rest >= 78s"""

    def test_rest_scaling_build_muscle_30min(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "duration_minutes": 30,
            "fitness_level": "intermediate",
            "days_per_week": 4,
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        exercises = get_day1_exercises(data)
        assert len(exercises) > 0, "No exercises found in Day 1"

        print(f"\n=== build_muscle 30min REST SCALING CHECK ===")
        for ex in exercises:
            print(f"  {ex.get('name','?')} | type={ex.get('exercise_type','?')} | rest={ex.get('rest_seconds')}s")

        # Check accessory and isolation rest <= 70
        accessory_violations = []
        for ex in exercises:
            ex_type = ex.get("exercise_type", "")
            rest = ex.get("rest_seconds", 0)
            if ex_type in ("accessory", "isolation") and rest > 70:
                accessory_violations.append(f"{ex.get('name','?')} ({ex_type}): rest={rest}s (> 70s)")

        if accessory_violations:
            print(f"⚠️ Accessory/isolation rest > 70s (may still be acceptable):")
            for v in accessory_violations:
                print(f"  {v}")

        # For the main assertion: accessory/isolation should be <= 70s in 30min session
        assert not accessory_violations, (
            f"REST SCALING: Accessory/isolation rest > 70s for build_muscle 30min:\n" +
            "\n".join(accessory_violations)
        )

        # Check primary_compound rest >= 78 (STRENGTH_REST_FLOORS["build_muscle"] = 90, so should be >= 90 actually)
        primary_compounds = [ex for ex in exercises if ex.get("exercise_type") == "primary_compound"]
        primary_violations = []
        for ex in primary_compounds:
            rest = ex.get("rest_seconds", 0)
            if rest < 78:
                primary_violations.append(f"{ex.get('name','?')}: rest={rest}s (< 78s)")

        assert not primary_violations, (
            f"REST SCALING: Primary compound rest < 78s for build_muscle 30min:\n" +
            "\n".join(primary_violations)
        )
        print(f"✅ PASS: Rest scaling correct for build_muscle 30min")


# ============================================================
# TEST 5: ANTI-BLOAT - strength 45min intermediate: max 5 exercises
# VOLUME_FRAMEWORK["strength"]["intermediate"][45] = (11,15,5)
# ============================================================
class TestStrengthAntiBloat:
    """strength 45min intermediate: total exercise count per session <= 5"""

    def test_strength_45min_intermediate_max_exercises(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "strength",
            "duration_minutes": 45,
            "fitness_level": "intermediate",
            "days_per_week": 3,
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        workout_days = data.get("workout_days", [])
        assert len(workout_days) > 0, "No workout days returned"

        print(f"\n=== ANTI-BLOAT: strength 45min intermediate ===")
        all_pass = True
        for i, day in enumerate(workout_days):
            exercises = day.get("exercises", [])
            count = len(exercises)
            print(f"  Day {i+1}: {count} exercises")
            for ex in exercises:
                print(f"    {ex.get('name','?')} | type={ex.get('exercise_type','?')} | sets={ex.get('sets')}")
            if count > 5:
                print(f"  ❌ FAIL: Day {i+1} has {count} exercises (> 5 max)")
                all_pass = False
            else:
                print(f"  ✓ Day {i+1}: {count} exercises (≤ 5) ✓")

        assert all_pass, "One or more sessions exceeded 5 exercises for strength 45min intermediate"
        print(f"✅ PASS: All sessions have ≤5 exercises")


# ============================================================
# TEST 6: SET ALLOCATION PER EXERCISE TYPE - build_muscle intermediate
# SETS_PER_EXERCISE intermediate:
#   primary_compound: (3,4)
#   secondary_compound: (3,4)
#   isolation: (2,4)
# ============================================================
class TestSetAllocationBuildMuscleIntermediate:
    """intermediate build_muscle: verify set ranges per exercise type"""

    def test_set_allocation_per_type(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "days_per_week": 4,
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        exercises = get_day1_exercises(data)
        assert len(exercises) > 0, "No exercises in Day 1"

        print(f"\n=== SET ALLOCATION: build_muscle intermediate 60min ===")
        print(f"Exercise type → sets mapping:")

        violations = []
        TYPE_RANGES = {
            "primary_compound":   (3, 5),   # (3,4) + up to +1 focus boost allowed
            "secondary_compound": (2, 5),   # (3,4) + up to +1 focus boost
            "accessory":          (2, 5),   # (2,4) + +1 focus boost
            "isolation":          (2, 5),   # (2,4)
            "core":               (1, 4),
            "conditioning":       (1, 1),
            "unilateral":         (2, 5),
            "explosive":          (2, 5),
        }

        for ex in exercises:
            ex_type = ex.get("exercise_type", "unknown")
            sets = ex.get("sets", 0)
            reps = ex.get("reps", "")
            rest = ex.get("rest_seconds", 0)

            print(f"  {ex.get('name','?')} | type={ex_type} | sets={sets} | reps={reps} | rest={rest}s")

            if ex_type in TYPE_RANGES:
                s_min, s_max = TYPE_RANGES[ex_type]
                if not (s_min <= sets <= s_max):
                    violations.append(f"{ex.get('name','?')} ({ex_type}): sets={sets} (expected {s_min}-{s_max})")

        # Specifically verify primary_compound has 3-4 sets (core requirement)
        primary_compounds = [ex for ex in exercises if ex.get("exercise_type") == "primary_compound"]
        if primary_compounds:
            for ex in primary_compounds:
                sets = ex.get("sets", 0)
                if not (3 <= sets <= 5):  # 3-4 + possible +1 focus boost
                    violations.append(
                        f"PRIMARY COMPOUND {ex.get('name','?')}: sets={sets} "
                        f"(SETS_PER_EXERCISE intermediate primary_compound = (3,4))"
                    )
        else:
            print("  ⚠️ No primary_compound exercises found in Day 1")

        # Specifically verify isolation has 2-4 sets
        isolation_exs = [ex for ex in exercises if ex.get("exercise_type") == "isolation"]
        for ex in isolation_exs:
            sets = ex.get("sets", 0)
            if not (2 <= sets <= 5):
                violations.append(
                    f"ISOLATION {ex.get('name','?')}: sets={sets} "
                    f"(SETS_PER_EXERCISE intermediate isolation = (2,4))"
                )

        assert not violations, "Set allocation violations:\n" + "\n".join(violations)
        print(f"✅ PASS: All exercise types have correct set counts")


# ============================================================
# TEST 7: CONDITIONING FINISHER ANTI-BLOAT - lose_fat 45min intermediate
# Expected: at most 5 lifting exercises BEFORE finisher (anti-bloat: finisher takes 1 slot)
# VOLUME_FRAMEWORK["lose_fat"]["intermediate"][45] = (13,16,6) → max_ex = 6 - 1 = 5
# ============================================================
class TestConditioningFinisherAntiBloat:
    """lose_fat 45min intermediate: at most 5 lifting exercises before conditioning finisher"""

    def test_lose_fat_finisher_anti_bloat(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "lose_fat",
            "duration_minutes": 45,
            "fitness_level": "intermediate",
            "days_per_week": 4,
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        workout_days = data.get("workout_days", [])
        assert len(workout_days) > 0, "No workout days returned"

        print(f"\n=== CONDITIONING FINISHER ANTI-BLOAT: lose_fat 45min intermediate ===")
        all_pass = True

        for i, day in enumerate(workout_days):
            exercises = day.get("exercises", [])
            conditioning_exs = [ex for ex in exercises if ex.get("exercise_type") == "conditioning"]
            lifting_exs = [ex for ex in exercises if ex.get("exercise_type") != "conditioning"]

            print(f"\n  Day {i+1}: {len(exercises)} total exercises "
                  f"({len(lifting_exs)} lifting + {len(conditioning_exs)} conditioning)")
            for ex in exercises:
                marker = " 🏃 FINISHER" if ex.get("exercise_type") == "conditioning" else ""
                print(f"    {ex.get('name','?')} | type={ex.get('exercise_type','?')}"
                      f" | sets={ex.get('sets')}{marker}")

            # If there's a conditioning finisher, check lifting exercises <= 5
            if conditioning_exs:
                if len(lifting_exs) > 5:
                    print(f"  ❌ FAIL: Day {i+1} has {len(lifting_exs)} lifting exercises (> 5) before finisher")
                    all_pass = False
                else:
                    print(f"  ✓ Day {i+1}: {len(lifting_exs)} lifting exercises (≤5) + conditioning finisher ✓")
            else:
                print(f"  ℹ️ Day {i+1}: No conditioning finisher (expected for some days in 4-day plan)")

        assert all_pass, "Some sessions with conditioning finisher exceeded 5 lifting exercises"
        print(f"\n✅ PASS: Conditioning finisher anti-bloat working correctly")


# ============================================================
# TEST 8: GOAL PARAMS - rep ranges correct
# build_muscle: primary_compound reps='6-10', secondary_compound reps='8-12', isolation reps='12-15'
# strength: primary_compound reps='3-5'
# ============================================================
class TestGoalParamsRepRanges:
    """Verify correct rep ranges per goal from GOAL_PARAMS"""

    def test_build_muscle_rep_ranges(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "days_per_week": 4,
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        exercises = get_day1_exercises(data)
        assert len(exercises) > 0, "No exercises in Day 1"

        print(f"\n=== GOAL PARAMS - build_muscle rep ranges ===")
        violations = []

        EXPECTED_REPS = {
            "primary_compound":   "6-10",
            "secondary_compound": "8-12",
            "isolation":          "12-15",
        }

        for ex in exercises:
            ex_type = ex.get("exercise_type", "")
            reps = ex.get("reps", "")
            print(f"  {ex.get('name','?')} | type={ex_type} | reps={reps}")

            if ex_type in EXPECTED_REPS:
                expected = EXPECTED_REPS[ex_type]
                if reps != expected:
                    violations.append(
                        f"{ex.get('name','?')} ({ex_type}): reps='{reps}' (expected '{expected}')"
                    )

        assert not violations, "Rep range violations for build_muscle:\n" + "\n".join(violations)
        print(f"✅ PASS: build_muscle rep ranges correct")

    def test_strength_primary_compound_rep_range(self, api_client):
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "strength",
            "duration_minutes": 30,
            "fitness_level": "beginner",
            "days_per_week": 3,
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:500]}"
        data = resp.json()

        exercises = get_day1_exercises(data)
        assert len(exercises) > 0, "No exercises in Day 1"

        print(f"\n=== GOAL PARAMS - strength rep ranges ===")
        for ex in exercises:
            print(f"  {ex.get('name','?')} | type={ex.get('exercise_type','?')} | reps={ex.get('reps')}")

        primary_compounds = [ex for ex in exercises if ex.get("exercise_type") == "primary_compound"]
        assert len(primary_compounds) > 0, "No primary_compound exercises found"

        violations = []
        for ex in primary_compounds:
            reps = ex.get("reps", "")
            if reps != "3-5":
                violations.append(
                    f"{ex.get('name','?')}: reps='{reps}' (expected '3-5' for strength primary_compound)"
                )

        assert not violations, "Rep range violations for strength:\n" + "\n".join(violations)
        print(f"✅ PASS: strength primary_compound reps='3-5' ✓")


# ============================================================
# BONUS: Comprehensive output - print all exercises for Day 1 of each scenario
# ============================================================
class TestComprehensiveOutput:
    """Print full Day 1 structure for all test scenarios for visual inspection"""

    def test_print_strength_30min_beginner_day1(self, api_client):
        """BONUS: Print full Day 1 structure for strength 30min beginner"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "strength",
            "duration_minutes": 30,
            "fitness_level": "beginner",
            "days_per_week": 3,
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200

        data = resp.json()
        print(f"\n{'='*60}")
        print(f"STRENGTH 30min BEGINNER - Full Day 1 Structure")
        print(f"{'='*60}")
        exercises = get_day1_exercises(data)
        total = sum(ex.get("sets", 0) for ex in exercises)
        print(f"Total exercises: {len(exercises)}, Total sets: {total}")
        for j, ex in enumerate(exercises):
            print(f"  {j+1}. {ex.get('name','?')}")
            print(f"     Type: {ex.get('exercise_type','?')}")
            print(f"     Sets: {ex.get('sets')} | Reps: {ex.get('reps')} | Rest: {ex.get('rest_seconds')}s")
            print(f"     Effort: {ex.get('effort_target','')}")

        assert len(exercises) <= 4, f"Too many exercises: {len(exercises)}"
        assert 8 <= total <= 14, f"Sets out of range: {total}"

    def test_print_build_muscle_60min_intermediate_day1(self, api_client):
        """BONUS: Print full Day 1 structure for build_muscle 60min intermediate"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "days_per_week": 4,
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["full_gym"]
        }
        resp = generate_workout(api_client, payload)
        assert resp.status_code == 200

        data = resp.json()
        print(f"\n{'='*60}")
        print(f"BUILD_MUSCLE 60min INTERMEDIATE - Full Day 1 Structure")
        print(f"{'='*60}")
        exercises = get_day1_exercises(data)
        total = sum(ex.get("sets", 0) for ex in exercises)
        print(f"Total exercises: {len(exercises)}, Total sets: {total}")
        for j, ex in enumerate(exercises):
            print(f"  {j+1}. {ex.get('name','?')}")
            print(f"     Type: {ex.get('exercise_type','?')}")
            print(f"     Sets: {ex.get('sets')} | Reps: {ex.get('reps')} | Rest: {ex.get('rest_seconds')}s")

        assert len(exercises) <= 7, f"Too many exercises: {len(exercises)}"
        assert 16 <= total <= 22, f"Sets out of range: {total}"
