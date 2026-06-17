"""
Tests for exercise_preferences field wired into workout generation.

Feature: exercise_preferences free-text field is now active — previously accepted but silently ignored.
Fix:
  1. build_blueprint() returns 'exercise_preferences' in its blueprint dict
  2. Prompt construction adds advisory guidance when exercise_preferences is present:
     - 'When an option matches a liked exercise, prefer it.'
     - 'When an option matches a disliked exercise, choose a different option from the list.'
     - 'Never pick an exercise outside the provided Options.'

Tests:
  - blueprint_includes_exercise_preferences: unit-level check (no LLM call)
  - without_exercise_preferences: regression — 200 OK, workout is complete
  - hate_burpees: bodyweight + lose_fat → no burpees in generated workout
  - love_rdl_hate_burpees: full_gym + build_muscle → RDL present, no burpees

NOTE: Tests 2-4 call Claude LLM — each takes 20-90s.
      Module-scoped fixtures minimise API calls (one generation per scenario).
"""

import sys
import os
import pytest
import requests

# Resolve BASE_URL from env
BASE_URL = (
    os.environ.get("EXPO_PUBLIC_BACKEND_URL")
    or os.environ.get("EXPO_BACKEND_URL")
    or ""
).rstrip("/")

USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"  # admin email user — no quota limit


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def call_generate(payload: dict) -> requests.Response:
    """POST /api/workouts/generate with 180-second timeout for Claude."""
    if not BASE_URL:
        pytest.skip("EXPO_PUBLIC_BACKEND_URL / EXPO_BACKEND_URL not set")
    return requests.post(
        f"{BASE_URL}/api/workouts/generate",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=180,
    )


def all_exercise_names(workout_json: dict) -> list[str]:
    """Flatten all exercise names from all workout days into one list (lowercase)."""
    names = []
    for day in workout_json.get("workout_days", []):
        for ex in day.get("exercises", []):
            names.append(ex.get("name", "").lower())
    return names


# ─────────────────────────────────────────────────────────────────────────────
# Module-scoped fixtures  (each LLM call shared across multiple test functions)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def no_prefs_response():
    """Workout generated WITHOUT exercise_preferences — regression baseline."""
    payload = {
        "user_id": USER_ID,
        "goal": "build_muscle",
        "training_style": "weights",
        "days_per_week": 3,
        "duration_minutes": 60,
        "fitness_level": "intermediate",
        "equipment": ["full_gym"],
        "focus_areas": ["chest", "back"],
        "exercise_preferences": None,
    }
    resp = call_generate(payload)
    return resp


@pytest.fixture(scope="module")
def hate_burpees_response():
    """
    Workout generated WITH exercise_preferences = 'I hate burpees'.
    bodyweight + lose_fat → conditioning finisher injected with options
    [Burpee Intervals, Jump Rope, Mountain Climbers EMOM].
    Advisory guidance should steer Claude away from Burpee Intervals.
    """
    payload = {
        "user_id": USER_ID,
        "goal": "lose_fat",
        "training_style": "weights",
        "days_per_week": 3,
        "duration_minutes": 45,
        "fitness_level": "intermediate",
        "equipment": ["bodyweight"],
        "focus_areas": ["full_body"],
        "exercise_preferences": "I hate burpees",
    }
    resp = call_generate(payload)
    return resp


@pytest.fixture(scope="module")
def love_rdl_hate_burpees_response():
    """
    Workout WITH exercise_preferences = 'love Romanian Deadlifts, hate burpees'.
    full_gym + build_muscle, legs/full_body focus so hip_hinge slot is included.
    hip_hinge options (full_gym): [Romanian Deadlift, Conventional Deadlift, Cable Pull-Through].
    Advisory: Claude should prefer Romanian Deadlift.
    """
    payload = {
        "user_id": USER_ID,
        "goal": "build_muscle",
        "training_style": "weights",
        "days_per_week": 4,
        "duration_minutes": 60,
        "fitness_level": "intermediate",
        "equipment": ["full_gym"],
        "focus_areas": ["legs", "back"],
        "exercise_preferences": "love Romanian Deadlifts, hate burpees",
    }
    resp = call_generate(payload)
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# Test 1 — Unit-level: build_blueprint() includes exercise_preferences
# ─────────────────────────────────────────────────────────────────────────────

class TestBlueprintStructure:
    """Verify build_blueprint() returns exercise_preferences without LLM call."""

    def test_blueprint_includes_exercise_preferences_when_set(self):
        """build_blueprint must propagate exercise_preferences into the returned dict."""
        sys.path.insert(0, "/app/backend")
        from server import EliteCoachingEngine

        engine = EliteCoachingEngine()

        class FakeReq:
            goal = "build_muscle"
            training_style = "weights"
            days_per_week = 3
            duration_minutes = 60
            fitness_level = "intermediate"
            equipment = ["full_gym"]
            injuries = []
            focus_areas = ["chest"]
            secondary_focus_areas = []
            preferred_split = "ai_choose"
            exercise_preferences = "love Romanian Deadlifts, hate burpees"
            preferred_start_day = "Monday"

        bp = engine.build_blueprint(FakeReq())
        assert "exercise_preferences" in bp, (
            "build_blueprint() must include 'exercise_preferences' key in returned dict"
        )
        assert bp["exercise_preferences"] == "love Romanian Deadlifts, hate burpees", (
            f"Expected preference string, got: {bp['exercise_preferences']!r}"
        )
        print("✅ blueprint includes exercise_preferences correctly")

    def test_blueprint_exercise_preferences_none_when_omitted(self):
        """When exercise_preferences is not set, blueprint key should be None/absent."""
        sys.path.insert(0, "/app/backend")
        from server import EliteCoachingEngine

        engine = EliteCoachingEngine()

        class FakeReq:
            goal = "build_muscle"
            training_style = "weights"
            days_per_week = 3
            duration_minutes = 60
            fitness_level = "intermediate"
            equipment = ["full_gym"]
            injuries = []
            focus_areas = ["chest"]
            secondary_focus_areas = []
            preferred_split = "ai_choose"
            exercise_preferences = None
            preferred_start_day = "Monday"

        bp = engine.build_blueprint(FakeReq())
        # Should be None or falsy when not provided
        assert not bp.get("exercise_preferences"), (
            f"Expected None/falsy, got: {bp.get('exercise_preferences')!r}"
        )
        print("✅ blueprint exercise_preferences is None when not set")


# ─────────────────────────────────────────────────────────────────────────────
# Test 2 — Regression: generate WITHOUT exercise_preferences returns 200
# ─────────────────────────────────────────────────────────────────────────────

class TestNoExercisePreferences:
    """Regression: workout generation still works without exercise_preferences."""

    def test_status_200(self, no_prefs_response):
        resp = no_prefs_response
        print(f"Response status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error body: {resp.text[:500]}")
        assert resp.status_code == 200, (
            f"Expected 200 without exercise_preferences, got {resp.status_code}: {resp.text[:300]}"
        )
        print("✅ 200 OK without exercise_preferences")

    def test_workout_has_days(self, no_prefs_response):
        assert no_prefs_response.status_code == 200
        data = no_prefs_response.json()
        days = data.get("workout_days", [])
        assert len(days) > 0, "workout_days must not be empty"
        print(f"✅ Workout has {len(days)} day(s)")

    def test_workout_exercises_have_required_fields(self, no_prefs_response):
        assert no_prefs_response.status_code == 200
        data = no_prefs_response.json()
        for day in data.get("workout_days", []):
            for ex in day.get("exercises", []):
                assert ex.get("name"), f"Exercise missing name: {ex}"
                assert ex.get("sets"), f"Exercise missing sets: {ex}"
                assert ex.get("reps"), f"Exercise missing reps: {ex}"
        print("✅ All exercises have name, sets, reps")


# ─────────────────────────────────────────────────────────────────────────────
# Test 3 — hate_burpees: generated workout must NOT contain burpees
# ─────────────────────────────────────────────────────────────────────────────

class TestHateBurpees:
    """exercise_preferences = 'I hate burpees': no burpee exercises in output."""

    def test_status_200(self, hate_burpees_response):
        resp = hate_burpees_response
        print(f"Response status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error body: {resp.text[:500]}")
        assert resp.status_code == 200, (
            f"Expected 200 with exercise_preferences set, got {resp.status_code}: {resp.text[:300]}"
        )
        print("✅ 200 OK with exercise_preferences='I hate burpees'")

    def test_workout_has_days(self, hate_burpees_response):
        assert hate_burpees_response.status_code == 200
        data = hate_burpees_response.json()
        days = data.get("workout_days", [])
        assert len(days) > 0, "workout_days must not be empty"
        print(f"✅ Workout has {len(days)} day(s)")

    def test_no_burpees_in_workout(self, hate_burpees_response):
        """
        Advisory guidance: 'When an option matches a disliked exercise, choose a different option'.
        The conditioning slot for bodyweight presents [Burpee Intervals, Jump Rope, Mountain Climbers EMOM].
        Claude should pick Jump Rope or Mountain Climbers EMOM.
        """
        assert hate_burpees_response.status_code == 200
        data = hate_burpees_response.json()
        names = all_exercise_names(data)

        print(f"All exercise names in 'hate burpees' workout: {names}")

        burpee_exercises = [n for n in names if "burpee" in n]
        assert len(burpee_exercises) == 0, (
            f"Found burpee exercise(s) despite dislike preference: {burpee_exercises}. "
            f"All exercises: {names}"
        )
        print("✅ No burpees in workout — preference honored")

    def test_workout_is_complete(self, hate_burpees_response):
        """Ensure the workout is properly structured with exercises and instructions."""
        assert hate_burpees_response.status_code == 200
        data = hate_burpees_response.json()
        total_exercises = sum(
            len(day.get("exercises", []))
            for day in data.get("workout_days", [])
        )
        assert total_exercises >= 3, f"Expected ≥3 exercises total, got {total_exercises}"
        print(f"✅ Workout complete with {total_exercises} total exercises")


# ─────────────────────────────────────────────────────────────────────────────
# Test 4 — love_rdl_hate_burpees: RDL present, no burpees
# ─────────────────────────────────────────────────────────────────────────────

class TestLoveRDLHateBurpees:
    """exercise_preferences = 'love Romanian Deadlifts, hate burpees'."""

    def test_status_200(self, love_rdl_hate_burpees_response):
        resp = love_rdl_hate_burpees_response
        print(f"Response status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error body: {resp.text[:500]}")
        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text[:300]}"
        )
        print("✅ 200 OK with love RDL / hate burpees preferences")

    def test_workout_has_days(self, love_rdl_hate_burpees_response):
        assert love_rdl_hate_burpees_response.status_code == 200
        data = love_rdl_hate_burpees_response.json()
        days = data.get("workout_days", [])
        assert len(days) > 0, "workout_days must not be empty"
        print(f"✅ Workout has {len(days)} day(s)")

    def test_romanian_deadlift_appears(self, love_rdl_hate_burpees_response):
        """
        Advisory: 'When an option matches a liked exercise, prefer it.'
        hip_hinge slot for full_gym offers: [Romanian Deadlift, Conventional Deadlift, Cable Pull-Through].
        Claude should pick Romanian Deadlift since user loves it.
        Check all exercise names for 'romanian deadlift' or 'rdl'.
        """
        assert love_rdl_hate_burpees_response.status_code == 200
        data = love_rdl_hate_burpees_response.json()
        names = all_exercise_names(data)

        print(f"All exercise names in 'love RDL' workout: {names}")

        rdl_exercises = [
            n for n in names
            if "romanian" in n or "rdl" in n
        ]
        assert len(rdl_exercises) >= 1, (
            f"Expected Romanian Deadlift/RDL in workout due to preference, but got: {names}"
        )
        print(f"✅ Romanian Deadlift found: {rdl_exercises}")

    def test_no_burpees_in_workout(self, love_rdl_hate_burpees_response):
        """No burpees should appear since user hates them."""
        assert love_rdl_hate_burpees_response.status_code == 200
        data = love_rdl_hate_burpees_response.json()
        names = all_exercise_names(data)

        burpee_exercises = [n for n in names if "burpee" in n]
        assert len(burpee_exercises) == 0, (
            f"Found burpee(s) despite dislike: {burpee_exercises}. All: {names}"
        )
        print("✅ No burpees in workout")

    def test_workout_has_sufficient_exercises(self, love_rdl_hate_burpees_response):
        """4-day build_muscle should have substantial exercise count."""
        assert love_rdl_hate_burpees_response.status_code == 200
        data = love_rdl_hate_burpees_response.json()
        total = sum(
            len(day.get("exercises", []))
            for day in data.get("workout_days", [])
        )
        assert total >= 8, f"Expected ≥8 exercises for 4-day plan, got {total}"
        print(f"✅ {total} total exercises across 4 days")
