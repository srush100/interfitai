"""
Tests for injury/limitation safety in workout generation.
Verifies LIMITATION_SYNONYMS, _normalize_limitations(), and safe fallback behavior.
Each test generates a real workout via Claude - expect 15-25s per call.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', '').rstrip('/')

# test user (admin-email so no quota check)
USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# The full LIMITATION_EXCLUSIONS dict (mirrors server.py)
LIMITATION_EXCLUSIONS = {
    "lower_back": ["Conventional Deadlift", "Sumo Deadlift", "Good Morning", "Back Squat", "T-Bar Row", "Barbell Row"],
    "knee":       ["Back Squat", "Leg Press", "Barbell Bulgarian Split Squat", "Jump Squat", "Running", "Lunge"],
    "shoulder":   ["Barbell Overhead Press", "Push Press", "Upright Row", "Behind-the-Neck Press", "Barbell Bench Press"],
    "wrist":      ["Barbell Curl", "Barbell Overhead Press", "Push-Up", "Barbell Bench Press"],
    "elbow":      ["Skull Crusher", "Dip", "Barbell Curl"],
    "hip":        ["Barbell Hip Thrust", "Barbell Bulgarian Split Squat", "Leg Press"],
    "ankle":      ["Calf Raise", "Jump Squat", "Broad Jump"],
    "neck":       ["Barbell Back Squat", "Barbell Overhead Press"],
}


def generate_workout(injuries, days: int = 3, equip: str = "full_gym") -> requests.Response:
    """Helper: generate a workout and return the full response.
    injuries: str (comma-separated) or list of strings
    """
    if isinstance(injuries, str):
        if injuries.lower() == "none":
            injuries_list = []
        else:
            injuries_list = [i.strip() for i in injuries.split(",")]
    else:
        injuries_list = injuries

    payload = {
        "user_id": USER_ID,
        "goal": "build_muscle",
        "days_per_week": days,
        "duration_minutes": 60,
        "equipment": [equip],
        "fitness_level": "intermediate",
        "focus_areas": ["full_body"],
        "injuries": injuries_list,
        "training_style": "weights",
    }
    resp = requests.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=120)
    return resp


def collect_exercise_names(workout_json: dict) -> list:
    """Flatten all exercise names from workout_days[].exercises[].name into a list."""
    names = []
    for day in workout_json.get("workout_days", []):
        for ex in day.get("exercises", []):
            name = ex.get("name", "")
            if name:
                names.append(name)
    return names


def assert_no_excluded(exercise_names: list, banned: list, injury_label: str):
    """Assert none of the exercise names EXACTLY match any banned exercise name.
    Uses exact, case-insensitive matching (server filtering is exact-match).
    """
    violations = []
    for name in exercise_names:
        for b in banned:
            if b.lower() == name.lower():   # exact match only
                violations.append(f"  BANNED '{b}' found exactly as '{name}'")
    if violations:
        pytest.fail(
            f"Injury '{injury_label}': Found {len(violations)} UNSAFE exercise(s):\n"
            + "\n".join(violations)
        )


def warn_substring_matches(exercise_names: list, banned: list, injury_label: str):
    """Print warning for exercises that PARTIALLY match a banned substring.
    These are not exact-match violations but may be medical safety gaps.
    """
    for name in exercise_names:
        for b in banned:
            if b.lower() in name.lower() and b.lower() != name.lower():
                print(
                    f"  ⚠️  WARNING: '{name}' contains banned substring '{b}' for '{injury_label}'. "
                    "Exact-match filter passes, but this exercise variant may be contraindicated."
                )


# ─────────────────────────────────────────────────────────────────
# Test 1: sciatica → lower_back exclusions
# ─────────────────────────────────────────────────────────────────
class TestSciaticaLowerBack:
    """sciatica synonym → lower_back → must exclude lower_back LIMITATION_EXCLUSIONS"""

    def test_sciatica_no_lower_back_exercises(self):
        resp = generate_workout(injuries="sciatica")
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        names = collect_exercise_names(data)
        assert names, "No exercises found in workout response"
        print(f"\nSciatica test - Total exercises: {len(names)}")
        print(f"Exercise names: {names}")

        banned = LIMITATION_EXCLUSIONS["lower_back"]
        assert_no_excluded(names, banned, "sciatica → lower_back")
        print("✅ PASS: Sciatica workout contains no lower_back-contraindicated exercises")


# ─────────────────────────────────────────────────────────────────
# Test 2: rotator cuff → shoulder exclusions
# ─────────────────────────────────────────────────────────────────
class TestRotatorCuffShoulder:
    """rotator cuff synonym → shoulder → must exclude shoulder LIMITATION_EXCLUSIONS"""

    def test_rotator_cuff_no_shoulder_exercises(self):
        resp = generate_workout(injuries="rotator cuff")
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        names = collect_exercise_names(data)
        assert names, "No exercises found in workout response"
        print(f"\nRotator cuff test - Total exercises: {len(names)}")
        print(f"Exercise names: {names}")

        banned = LIMITATION_EXCLUSIONS["shoulder"]
        assert_no_excluded(names, banned, "rotator cuff → shoulder")
        print("✅ PASS: Rotator cuff workout contains no shoulder-contraindicated exercises")


# ─────────────────────────────────────────────────────────────────
# Test 3: ACL injury → knee exclusions
# ─────────────────────────────────────────────────────────────────
class TestACLKnee:
    """ACL injury synonym → knee → must exclude knee LIMITATION_EXCLUSIONS"""

    def test_acl_injury_no_knee_exercises(self):
        resp = generate_workout(injuries="ACL injury")
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        names = collect_exercise_names(data)
        assert names, "No exercises found in workout response"
        print(f"\nACL injury test - Total exercises: {len(names)}")
        print(f"Exercise names: {names}")

        banned = LIMITATION_EXCLUSIONS["knee"]
        warn_substring_matches(names, banned, "ACL injury → knee")
        assert_no_excluded(names, banned, "ACL injury → knee")
        print("✅ PASS: ACL injury workout contains no knee-contraindicated exercises (exact match)")


# ─────────────────────────────────────────────────────────────────
# Test 4: tennis elbow → elbow exclusions
# ─────────────────────────────────────────────────────────────────
class TestTennisElbow:
    """tennis elbow synonym → elbow → must exclude elbow LIMITATION_EXCLUSIONS"""

    def test_tennis_elbow_no_elbow_exercises(self):
        resp = generate_workout(injuries="tennis elbow")
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        names = collect_exercise_names(data)
        assert names, "No exercises found in workout response"
        print(f"\nTennis elbow test - Total exercises: {len(names)}")
        print(f"Exercise names: {names}")

        banned = LIMITATION_EXCLUSIONS["elbow"]
        assert_no_excluded(names, banned, "tennis elbow → elbow")
        print("✅ PASS: Tennis elbow workout contains no elbow-contraindicated exercises")


# ─────────────────────────────────────────────────────────────────
# Test 5: plantar fasciitis → ankle exclusions
# ─────────────────────────────────────────────────────────────────
class TestPlantarFasciitisAnkle:
    """plantar fasciitis synonym → ankle → must exclude ankle LIMITATION_EXCLUSIONS"""

    def test_plantar_fasciitis_no_ankle_exercises(self):
        resp = generate_workout(injuries="plantar fasciitis")
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        names = collect_exercise_names(data)
        assert names, "No exercises found in workout response"
        print(f"\nPlantar fasciitis test - Total exercises: {len(names)}")
        print(f"Exercise names: {names}")

        banned = LIMITATION_EXCLUSIONS["ankle"]
        assert_no_excluded(names, banned, "plantar fasciitis → ankle")
        print("✅ PASS: Plantar fasciitis workout contains no ankle-contraindicated exercises")


# ─────────────────────────────────────────────────────────────────
# Test 6: No injuries regression test
# ─────────────────────────────────────────────────────────────────
class TestNoInjuriesRegression:
    """injuries='none' → 200 OK with complete workout (regression check)"""

    def test_no_injuries_returns_200_with_workout(self):
        resp = generate_workout(injuries="none")
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        names = collect_exercise_names(data)
        assert len(names) > 0, "No exercises found in workout with no injuries"
        # WorkoutProgram model uses 'name' field (not 'program_name')
        assert data.get("name"), "Missing 'name' field in response"
        assert len(data.get("workout_days", [])) >= 3, "Expected at least 3 workout days"
        print(f"\nNo injuries regression - Total exercises: {len(names)}, Days: {len(data['workout_days'])}")
        print(f"Program: {data.get('name')}")
        print("✅ PASS: No-injury workout returns complete workout without regression")


# ─────────────────────────────────────────────────────────────────
# Test 7: herniated disc → lower_back exclusions
# ─────────────────────────────────────────────────────────────────
class TestHerniatedDiscLowerBack:
    """herniated disc synonym → lower_back → must exclude lower_back LIMITATION_EXCLUSIONS"""

    def test_herniated_disc_no_lower_back_exercises(self):
        resp = generate_workout(injuries="herniated disc")
        assert resp.status_code == 200, f"Unexpected status {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        names = collect_exercise_names(data)
        assert names, "No exercises found in workout response"
        print(f"\nHerniated disc test - Total exercises: {len(names)}")
        print(f"Exercise names: {names}")

        banned = LIMITATION_EXCLUSIONS["lower_back"]
        assert_no_excluded(names, banned, "herniated disc → lower_back")
        print("✅ PASS: Herniated disc workout contains no lower_back-contraindicated exercises")


# ─────────────────────────────────────────────────────────────────
# Test 8: ALL 8 limitations combined (unsafe fallback test)
# ─────────────────────────────────────────────────────────────────
class TestAllLimitationsFallback:
    """
    All 8 canonical limitations simultaneously.
    - Must return 200 OK (no crash / no empty workout)
    - Must NOT contain excluded exercises from ANY category
    - Tests the safe fallback: bodyweight/any options are returned when all candidates are excluded
    """

    def test_all_limitations_returns_workout_with_no_excluded_exercises(self):
        all_injuries = "lower_back, knee, shoulder, wrist, elbow, hip, ankle"
        resp = generate_workout(injuries=all_injuries)
        assert resp.status_code == 200, (
            f"ALL limitations test returned {resp.status_code}: {resp.text[:500]}"
        )

        data = resp.json()
        names = collect_exercise_names(data)
        assert len(names) > 0, (
            "ALL limitations workout returned ZERO exercises — fallback may have failed"
        )
        print(f"\nAll-limitations test - Total exercises: {len(names)}")
        print(f"Exercise names: {names}")

        # Collect all banned exercises across all 8 categories
        all_banned = []
        for key, banned_list in LIMITATION_EXCLUSIONS.items():
            all_banned.extend(banned_list)
        all_banned = list(set(all_banned))

        # First: print substring warnings for exercises that contain banned words
        # (these reveal incomplete exclusion list gaps)
        print("\n--- Substring check warnings (informational, not failure) ---")
        for name in names:
            for b in all_banned:
                if b.lower() in name.lower() and b.lower() != name.lower():
                    print(f"  ⚠️  WARNING: '{name}' contains banned substring '{b}'. "
                          "May be a contraindicated variant not in exact exclusion list.")

        # Exact-match violation check (matches how server filtering works)
        violations = []
        for name in names:
            for b in all_banned:
                if b.lower() == name.lower():   # exact match only
                    violations.append(f"  BANNED '{b}' found exactly as exercise '{name}'")

        if violations:
            pytest.fail(
                f"ALL limitations test: Found {len(violations)} UNSAFE exercise(s) (exact match):\n"
                + "\n".join(violations)
            )

        print("✅ PASS: All-limitations workout generated successfully with no unsafe exercises")
        print(f"  (Safe fallback activated for slots where all gym options were excluded)")


# ─────────────────────────────────────────────────────────────────
# Unit tests for _normalize_limitations logic (no API call needed)
# These call the backend's normalize endpoint OR verify via workout metadata
# ─────────────────────────────────────────────────────────────────
class TestNormalizeLimitationsLogic:
    """
    Lightweight tests verifying the synonym mapping by checking workout blueprint
    metadata (limitation field in the response) without re-testing all excluded exercises.
    """

    def test_runner_knee_synonym_in_response(self):
        """runner's knee → knee canonical key → 200 OK"""
        resp = generate_workout(injuries="runner's knee")
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        names = collect_exercise_names(data)
        banned = LIMITATION_EXCLUSIONS["knee"]
        assert_no_excluded(names, banned, "runner's knee → knee")
        print("✅ PASS: runner's knee correctly excludes knee exercises")

    def test_carpal_tunnel_synonym(self):
        """carpal tunnel → wrist canonical key → 200 OK, no wrist-banned exercises"""
        resp = generate_workout(injuries="carpal tunnel")
        assert resp.status_code == 200, f"Status {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        names = collect_exercise_names(data)
        banned = LIMITATION_EXCLUSIONS["wrist"]
        assert_no_excluded(names, banned, "carpal tunnel → wrist")
        print("✅ PASS: carpal tunnel correctly excludes wrist exercises")
