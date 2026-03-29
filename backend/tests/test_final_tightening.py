"""
Tests for Elite Coaching Engine - Final Tightening:
1. Minimum set floors (primary compounds >= 3 sets, accessories >= 2 sets)
2. Bro Split mapping (5 distinct day types: chest/back/shoulder/arm/leg)
3. ExerciseDB GIF accuracy (gif_url present and non-null on exercises)
4. General smoke test (200 OK, workout_days, exercises with sets/reps/rest)
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


@pytest.fixture(scope="session")
def smoke_workout(api_client):
    """General smoke test — build_muscle, chest focus, dumbbells, 3 days, 45 min"""
    payload = {
        "user_id": TEST_USER_ID,
        "goal": "build_muscle",
        "focus_areas": ["chest"],
        "equipment": ["dumbbells"],
        "days_per_week": 3,
        "duration_minutes": 45,
        "fitness_level": "intermediate",
        "preferred_split": "ai_choose",
    }
    resp = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
    return resp


@pytest.fixture(scope="session")
def bro_split_workout(api_client):
    """Bro split fixture — build_muscle, 5 days, full_gym, 60 min"""
    payload = {
        "user_id": TEST_USER_ID,
        "goal": "build_muscle",
        "focus_areas": ["chest", "back", "shoulders", "arms", "legs"],
        "equipment": ["full_gym"],
        "days_per_week": 5,
        "duration_minutes": 60,
        "fitness_level": "intermediate",
        "preferred_split": "bro_split",
        "duration_weeks": 4,
    }
    resp = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
    return resp


# ── TEST 1: General smoke test ───────────────────────────────────────────────

class TestSmokeWorkout:
    """General smoke test for workout generation"""

    def test_smoke_200_ok(self, smoke_workout):
        """Workout generation should return 200 OK"""
        assert smoke_workout.status_code == 200, (
            f"Expected 200 got {smoke_workout.status_code}: {smoke_workout.text[:500]}"
        )

    def test_smoke_has_workout_days(self, smoke_workout):
        """Response must contain workout_days array"""
        data = smoke_workout.json()
        assert "workout_days" in data, f"Missing 'workout_days' in response: {list(data.keys())}"
        assert len(data["workout_days"]) > 0, "workout_days is empty"

    def test_smoke_each_day_has_exercises(self, smoke_workout):
        """Each workout day must have at least one exercise"""
        data = smoke_workout.json()
        for i, day in enumerate(data["workout_days"]):
            assert "exercises" in day, f"Day {i} missing 'exercises'"
            assert len(day["exercises"]) > 0, f"Day {i} has no exercises"

    def test_smoke_exercises_have_required_fields(self, smoke_workout):
        """Each exercise must have sets, reps, and rest_seconds"""
        data = smoke_workout.json()
        for day in data["workout_days"]:
            for ex in day["exercises"]:
                name = ex.get("name", "unknown")
                assert "sets" in ex, f"Exercise '{name}' missing 'sets'"
                assert "reps" in ex, f"Exercise '{name}' missing 'reps'"
                assert "rest_seconds" in ex, f"Exercise '{name}' missing 'rest_seconds'"
                assert ex["sets"] is not None, f"Exercise '{name}' has null sets"
                assert ex["reps"] is not None, f"Exercise '{name}' has null reps"
                assert ex["rest_seconds"] is not None, f"Exercise '{name}' has null rest_seconds"


# ── TEST 2: Minimum set floors ───────────────────────────────────────────────

class TestMinSetFloors:
    """No exercise should have fewer sets than the minimum floor"""

    def test_no_exercise_has_fewer_than_2_sets(self, smoke_workout):
        """All exercises must have >= 2 sets (global floor)"""
        data = smoke_workout.json()
        violations = []
        for day in data["workout_days"]:
            for ex in day["exercises"]:
                sets = ex.get("sets", 0)
                if sets < 2:
                    violations.append(
                        f"Day '{day.get('day','?')}' exercise '{ex.get('name','?')}' has {sets} sets"
                    )
        assert not violations, f"Set floor violations (min 2 sets):\n" + "\n".join(violations)

    def test_primary_compounds_have_at_least_3_sets(self, smoke_workout):
        """Primary compound exercises must have >= 3 sets"""
        data = smoke_workout.json()
        # primary compounds identified by exercise_type field OR well-known names
        primary_names_lower = {
            "bench press", "barbell bench press", "dumbbell bench press",
            "back squat", "barbell squat", "squat",
            "deadlift", "barbell deadlift", "conventional deadlift",
            "overhead press", "barbell overhead press",
            "pull-up", "pull up", "chin up", "chin-up",
            "lat pulldown", "barbell row",
        }
        violations = []
        for day in data["workout_days"]:
            for ex in day["exercises"]:
                ex_type = ex.get("exercise_type", "")
                name_lower = ex.get("name", "").lower()
                is_primary = (
                    ex_type == "primary_compound"
                    or any(p in name_lower for p in primary_names_lower)
                )
                if is_primary and ex.get("sets", 0) < 3:
                    violations.append(
                        f"Day '{day.get('day','?')}' PRIMARY '{ex.get('name','?')}' has {ex.get('sets')} sets (need >= 3)"
                    )
        assert not violations, f"Primary compound set floor violations:\n" + "\n".join(violations)

    def test_no_exercise_has_fewer_than_2_sets_bro(self, bro_split_workout):
        """Bro split: all exercises must have >= 2 sets"""
        assert bro_split_workout.status_code == 200, (
            f"Bro split request failed: {bro_split_workout.status_code}"
        )
        data = bro_split_workout.json()
        violations = []
        for day in data["workout_days"]:
            for ex in day["exercises"]:
                sets = ex.get("sets", 0)
                if sets < 2:
                    violations.append(
                        f"Day '{day.get('day','?')}' exercise '{ex.get('name','?')}' has {sets} sets"
                    )
        assert not violations, f"Bro split set floor violations:\n" + "\n".join(violations)


# ── TEST 3: Bro Split Day Types ──────────────────────────────────────────────

class TestBroSplitDayTypes:
    """5-day bro split must produce exactly 5 distinct focus types"""

    def test_bro_split_200_ok(self, bro_split_workout):
        assert bro_split_workout.status_code == 200, (
            f"Bro split generation failed: {bro_split_workout.status_code}: {bro_split_workout.text[:500]}"
        )

    def test_bro_split_has_5_days(self, bro_split_workout):
        """5-day bro split must produce 5 workout days"""
        data = bro_split_workout.json()
        days = data.get("workout_days", [])
        assert len(days) == 5, f"Expected 5 workout days, got {len(days)}"

    def test_bro_split_has_chest_day(self, bro_split_workout):
        """Bro split must contain a Chest day"""
        data = bro_split_workout.json()
        focus_texts = [d.get("focus", "").lower() for d in data.get("workout_days", [])]
        day_texts = [d.get("day", "").lower() for d in data.get("workout_days", [])]
        all_texts = focus_texts + day_texts
        has_chest = any("chest" in t for t in all_texts)
        assert has_chest, f"No Chest day found. Day focuses: {focus_texts}"

    def test_bro_split_has_back_day(self, bro_split_workout):
        """Bro split must contain a Back day"""
        data = bro_split_workout.json()
        focus_texts = [d.get("focus", "").lower() for d in data.get("workout_days", [])]
        day_texts = [d.get("day", "").lower() for d in data.get("workout_days", [])]
        all_texts = focus_texts + day_texts
        has_back = any("back" in t for t in all_texts)
        assert has_back, f"No Back day found. Day focuses: {focus_texts}"

    def test_bro_split_has_shoulder_day(self, bro_split_workout):
        """Bro split must contain a Shoulders day"""
        data = bro_split_workout.json()
        focus_texts = [d.get("focus", "").lower() for d in data.get("workout_days", [])]
        day_texts = [d.get("day", "").lower() for d in data.get("workout_days", [])]
        all_texts = focus_texts + day_texts
        has_shoulders = any("shoulder" in t for t in all_texts)
        assert has_shoulders, f"No Shoulders day found. Day focuses: {focus_texts}"

    def test_bro_split_has_arms_day(self, bro_split_workout):
        """Bro split must contain an Arms day"""
        data = bro_split_workout.json()
        focus_texts = [d.get("focus", "").lower() for d in data.get("workout_days", [])]
        day_texts = [d.get("day", "").lower() for d in data.get("workout_days", [])]
        all_texts = focus_texts + day_texts
        has_arms = any("arm" in t or "bicep" in t or "tricep" in t for t in all_texts)
        assert has_arms, f"No Arms day found. Day focuses: {focus_texts}"

    def test_bro_split_has_legs_day(self, bro_split_workout):
        """Bro split must contain a Legs day"""
        data = bro_split_workout.json()
        focus_texts = [d.get("focus", "").lower() for d in data.get("workout_days", [])]
        day_texts = [d.get("day", "").lower() for d in data.get("workout_days", [])]
        all_texts = focus_texts + day_texts
        has_legs = any("leg" in t or "quad" in t or "hamstring" in t for t in all_texts)
        assert has_legs, f"No Legs day found. Day focuses: {focus_texts}"

    def test_bro_split_5_distinct_focuses(self, bro_split_workout):
        """5-day bro split must have 5 distinct focus types"""
        data = bro_split_workout.json()
        focuses = [d.get("focus", "unknown") for d in data.get("workout_days", [])]
        unique_focuses = set(focuses)
        assert len(unique_focuses) == 5, (
            f"Expected 5 distinct focuses, got {len(unique_focuses)}: {focuses}"
        )

    def test_bro_split_split_name(self, bro_split_workout):
        """Response must declare split_name as Bro Split"""
        data = bro_split_workout.json()
        split_name = data.get("split_name", "").lower()
        assert "bro" in split_name, f"Expected 'bro' in split_name, got: '{data.get('split_name')}'"


# ── TEST 4: GIF URL presence ─────────────────────────────────────────────────

class TestExerciseGifUrl:
    """gif_url must be present (non-null) on exercises in generated workouts"""

    def test_smoke_exercises_have_gif_url_field(self, smoke_workout):
        """gif_url field must exist on every exercise in smoke workout"""
        data = smoke_workout.json()
        missing = []
        for day in data["workout_days"]:
            for ex in day["exercises"]:
                if "gif_url" not in ex:
                    missing.append(f"Day '{day.get('day','?')}' ex '{ex.get('name','?')}' missing gif_url key")
        assert not missing, "Exercises missing gif_url key:\n" + "\n".join(missing)

    def test_smoke_majority_exercises_have_gif_url(self, smoke_workout):
        """At least 50% of exercises should have a non-empty gif_url"""
        data = smoke_workout.json()
        total = 0
        with_gif = 0
        for day in data["workout_days"]:
            for ex in day["exercises"]:
                total += 1
                url = ex.get("gif_url") or ""
                if url:
                    with_gif += 1
        pct = (with_gif / total * 100) if total > 0 else 0
        assert pct >= 50, (
            f"Only {with_gif}/{total} ({pct:.1f}%) exercises have gif_url. Expect >= 50%"
        )

    def test_bro_split_exercises_have_gif_url(self, bro_split_workout):
        """Bro split: at least 50% of exercises should have gif_url"""
        assert bro_split_workout.status_code == 200
        data = bro_split_workout.json()
        total = 0
        with_gif = 0
        for day in data["workout_days"]:
            for ex in day["exercises"]:
                total += 1
                url = ex.get("gif_url") or ""
                if url:
                    with_gif += 1
        pct = (with_gif / total * 100) if total > 0 else 0
        print(f"\nBro split GIF coverage: {with_gif}/{total} ({pct:.1f}%)")
        assert pct >= 50, (
            f"Only {with_gif}/{total} ({pct:.1f}%) bro split exercises have gif_url. Expect >= 50%"
        )

    def test_gif_urls_are_proxy_format(self, smoke_workout):
        """gif_url values should be proxy paths (/api/exercises/gif/<id>) or empty"""
        data = smoke_workout.json()
        invalid = []
        for day in data["workout_days"]:
            for ex in day["exercises"]:
                url = ex.get("gif_url") or ""
                if url and not url.startswith("/api/exercises/gif/"):
                    invalid.append(f"'{ex.get('name','?')}': gif_url='{url}'")
        assert not invalid, "gif_url not in expected /api/exercises/gif/<id> format:\n" + "\n".join(invalid)


# ── TEST 5: Verify min sets detail dump ─────────────────────────────────────

class TestSetDetails:
    """Detailed per-exercise set count verification"""

    def test_print_all_exercise_sets_smoke(self, smoke_workout):
        """Print all exercises and their set counts for debugging"""
        data = smoke_workout.json()
        print(f"\nSmoke workout: {data.get('name','?')} | Split: {data.get('split_name','?')}")
        for day in data["workout_days"]:
            print(f"  Day: {day.get('day','?')} | Focus: {day.get('focus','?')}")
            for ex in day["exercises"]:
                print(f"    [{ex.get('exercise_type','?'):20s}] {ex.get('name','?'):40s} sets={ex.get('sets','?')} reps={ex.get('reps','?')} gif={'Y' if ex.get('gif_url') else 'N'}")
        assert True  # always passes — just for visibility

    def test_print_all_exercise_sets_bro(self, bro_split_workout):
        """Print bro split exercises and set counts for debugging"""
        if bro_split_workout.status_code != 200:
            pytest.skip("Bro split workout failed — skipping detail dump")
        data = bro_split_workout.json()
        print(f"\nBro split workout: {data.get('name','?')} | Split: {data.get('split_name','?')}")
        for day in data["workout_days"]:
            print(f"  Day: {day.get('day','?')} | Focus: {day.get('focus','?')}")
            for ex in day["exercises"]:
                print(f"    [{ex.get('exercise_type','?'):20s}] {ex.get('name','?'):40s} sets={ex.get('sets','?')} reps={ex.get('reps','?')} gif={'Y' if ex.get('gif_url') else 'N'}")
        assert True
