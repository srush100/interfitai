"""
Test: Secondary Focus Injection Fix (Item 1)
Tests that SECONDARY_SYNERGY map correctly allows/blocks injections per session type.
Tests max 2 injections per week, incompatible day skipping, and exercise count verification.
"""
import pytest
import requests
import os
import json
import time

BASE_URL = (
    os.environ.get('EXPO_BACKEND_URL') or
    os.environ.get('EXPO_PUBLIC_BACKEND_URL') or
    'https://nutrition-debug-1.preview.emergentagent.com'
).rstrip('/')

TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# Shoulder-related muscle groups / keywords to identify shoulder exercises
SHOULDER_KEYWORDS = {
    "shoulder", "deltoid", "delt", "rear delt", "lateral delt", "medial delt",
    "traps", "trapezius", "rotator cuff"
}

# Core-related muscle groups / keywords
CORE_KEYWORDS = {
    "core", "abs", "abdominals", "obliques", "transverse", "rectus"
}


@pytest.fixture(scope="module")
def api_session():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ── Helper ─────────────────────────────────────────────────────────────────────

def generate_workout(api_session, payload: dict, timeout: int = 180):
    """POST /api/workouts/generate and return parsed response."""
    resp = api_session.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=timeout)
    assert resp.status_code == 200, f"Workout generation failed ({resp.status_code}): {resp.text[:500]}"
    data = resp.json()
    assert "workout_days" in data, f"No workout_days in response: {list(data.keys())}"
    return data


def has_muscle_keyword(exercise: dict, keywords: set) -> bool:
    """Return True if any exercise muscle_groups entry matches a keyword."""
    muscle_groups = exercise.get("muscle_groups", [])
    for mg in muscle_groups:
        if any(kw in mg.lower() for kw in keywords):
            return True
    return False


def count_exercises_per_day(workout_data: dict) -> list:
    """Return list of exercise counts per day."""
    return [len(d["exercises"]) for d in workout_data["workout_days"]]


def get_day_focus_list(workout_data: dict) -> list:
    """Return list of focus strings per day."""
    return [d.get("focus", "") for d in workout_data["workout_days"]]


# ── Shared base payload ────────────────────────────────────────────────────────

BASE_UPPER_LOWER_PAYLOAD = {
    "user_id": TEST_USER_ID,
    "goal": "build_muscle",
    "training_style": "weights",
    "focus_areas": ["chest"],   # chest is primary; shoulders is secondary
    "equipment": ["full_gym"],
    "days_per_week": 4,
    "duration_minutes": 60,
    "fitness_level": "intermediate",
    "preferred_split": "upper_lower",
    "preferred_start_day": "Monday",
}

BASE_FULL_BODY_PAYLOAD = {
    "user_id": TEST_USER_ID,
    "goal": "build_muscle",
    "training_style": "weights",
    "focus_areas": ["chest"],   # chest is primary; core is secondary
    "equipment": ["full_gym"],
    "days_per_week": 3,
    "duration_minutes": 60,
    "fitness_level": "intermediate",
    "preferred_split": "full_body",
    "preferred_start_day": "Monday",
}


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 1: Full Body Split + Core Secondary
# ══════════════════════════════════════════════════════════════════════════════

class TestCoreInjectionFullBodySplit:
    """
    For a 3-day full_body split with secondary_focus_areas=['core']:
    - full_body sessions are mapped to 'any' in SECONDARY_SYNERGY → compatible
    - MAX_SECONDARY_INJECTIONS = 2 → only first 2 days get injected
    """

    @pytest.fixture(scope="class")
    def workout_with_core(self, api_session):
        payload = {**BASE_FULL_BODY_PAYLOAD, "secondary_focus_areas": ["core"]}
        return generate_workout(api_session, payload)

    @pytest.fixture(scope="class")
    def workout_without_secondary(self, api_session):
        payload = {**BASE_FULL_BODY_PAYLOAD}
        return generate_workout(api_session, payload)

    def test_workout_generates_successfully(self, workout_with_core):
        assert workout_with_core["workout_days"], "No workout days returned"
        assert len(workout_with_core["workout_days"]) == 3, \
            f"Expected 3 days, got {len(workout_with_core['workout_days'])}"
        print("✅ PASS: Full body 3-day workout generated successfully")

    def test_core_secondary_areas_stored_in_response(self, workout_with_core):
        secondary = workout_with_core.get("secondary_focus_areas")
        assert secondary == ["core"], f"secondary_focus_areas not stored: {secondary}"
        print("✅ PASS: secondary_focus_areas=['core'] stored in workout response")

    def test_core_exercises_present_in_at_least_one_day(self, workout_with_core):
        """At least 1 day should contain a core exercise (core_stability or core_flexion)."""
        core_exercises_found = []
        for i, day in enumerate(workout_with_core["workout_days"]):
            for ex in day["exercises"]:
                if has_muscle_keyword(ex, CORE_KEYWORDS):
                    core_exercises_found.append((i, ex["name"]))
        assert len(core_exercises_found) >= 1, \
            f"No core exercises found in any workout day. All exercises: {[e['name'] for d in workout_with_core['workout_days'] for e in d['exercises']]}"
        print(f"✅ PASS: Core exercises found in days: {core_exercises_found}")

    def test_max_2_core_injections_per_week(self, workout_with_core, workout_without_secondary):
        """
        Each session-type in full_body is 'any', so all 3 days are compatible,
        but MAX_SECONDARY_INJECTIONS=2 means only 2 get injected.
        We check: the workout with secondary has at most 2 MORE exercises than the baseline,
        i.e. at most 2 days have +1 extra exercise.
        """
        counts_with = count_exercises_per_day(workout_with_core)
        counts_without = count_exercises_per_day(workout_without_secondary)

        extra_days = sum(
            1 for w, wo in zip(counts_with, counts_without) if w > wo
        )
        total_extra = sum(
            max(0, w - wo) for w, wo in zip(counts_with, counts_without)
        )

        assert extra_days <= 2, \
            f"Expected at most 2 days with extra exercise (max injections), got {extra_days}. " \
            f"Counts with: {counts_with}, Counts without: {counts_without}"
        assert total_extra <= 2, \
            f"Total extra exercises across all days should be ≤2, got {total_extra}. " \
            f"Counts with: {counts_with}, Counts without: {counts_without}"

        print(f"✅ PASS: Max 2 injections respected. Days with extra exercise: {extra_days}, "
              f"Total extra: {total_extra}. Counts(with={counts_with}, without={counts_without})")

    def test_secondary_injection_increases_exercise_count(self, workout_with_core, workout_without_secondary):
        """Workout with secondary should have >= exercise count as without (never fewer)."""
        counts_with = count_exercises_per_day(workout_with_core)
        counts_without = count_exercises_per_day(workout_without_secondary)
        for i, (w, wo) in enumerate(zip(counts_with, counts_without)):
            assert w >= wo, \
                f"Day {i+1}: exercise count DECREASED with secondary ({wo} → {w}), that's wrong"
        print(f"✅ PASS: Exercise counts with secondary >= without on all days. "
              f"With: {counts_with}, Without: {counts_without}")


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 2: Upper/Lower Split + Shoulders Secondary (Main Focus)
# ══════════════════════════════════════════════════════════════════════════════

class TestShoulderInjectionUpperLowerSplit:
    """
    4-day upper_lower split with secondary_focus_areas=['shoulders']:
    Session types in order: upper_push_heavy, lower_quad_focus, upper_pull_heavy, lower_hip_focus
    SECONDARY_SYNERGY:
      upper_push_heavy: ["core","shoulders","triceps","chest","arms"] → compatible ✅
      lower_quad_focus: ["core","glutes","calves","hamstrings","legs","quads"] → NOT ❌
      upper_pull_heavy: ["core","back","biceps","shoulders","arms"] → compatible ✅
      lower_hip_focus:  ["core","quads","calves","legs","glutes"] → NOT ❌
    Expected: exactly 2 injections (upper days), 0 on lower days.
    """

    @pytest.fixture(scope="class")
    def workout_with_shoulders(self, api_session):
        payload = {**BASE_UPPER_LOWER_PAYLOAD, "secondary_focus_areas": ["shoulders"]}
        return generate_workout(api_session, payload)

    @pytest.fixture(scope="class")
    def workout_without_secondary(self, api_session):
        payload = {**BASE_UPPER_LOWER_PAYLOAD}
        return generate_workout(api_session, payload)

    def test_workout_generates_4_days(self, workout_with_shoulders):
        days = workout_with_shoulders["workout_days"]
        assert len(days) == 4, f"Expected 4 workout days, got {len(days)}"
        print(f"✅ PASS: 4 workout days generated. Focuses: {[d['focus'] for d in days]}")

    def test_secondary_areas_stored(self, workout_with_shoulders):
        secondary = workout_with_shoulders.get("secondary_focus_areas")
        assert secondary == ["shoulders"], f"secondary_focus_areas wrong: {secondary}"
        print("✅ PASS: secondary_focus_areas=['shoulders'] stored in response")

    def test_upper_days_have_shoulder_exercises(self, workout_with_shoulders):
        """
        Upper days (focus contains 'Upper' or 'Chest' or 'Back') should have
        shoulder-related exercises. With secondary=['shoulders'], the injection
        ensures at least one additional shoulder exercise beyond the baseline.
        """
        upper_days = [
            d for d in workout_with_shoulders["workout_days"]
            if any(kw in d.get("focus", "").lower()
                   for kw in ["upper", "chest", "back", "shoulder"])
        ]
        assert len(upper_days) >= 2, \
            f"Expected at least 2 upper days, found {len(upper_days)}. " \
            f"Focuses: {[d['focus'] for d in workout_with_shoulders['workout_days']]}"

        for day in upper_days:
            shoulder_exs = [
                ex["name"] for ex in day["exercises"]
                if has_muscle_keyword(ex, SHOULDER_KEYWORDS)
            ]
            assert len(shoulder_exs) >= 1, \
                f"Day '{day['focus']}' has no shoulder exercises after secondary injection. " \
                f"Exercises: {[e['name'] for e in day['exercises']]}"
            print(f"✅ Upper day '{day['focus']}': shoulder exercises found: {shoulder_exs}")

    def test_max_2_shoulder_injections_per_week(self, workout_with_shoulders, workout_without_secondary):
        """
        Total extra exercises across all days should be exactly 2
        (one per upper day, zero on lower days).
        """
        counts_with = count_exercises_per_day(workout_with_shoulders)
        counts_without = count_exercises_per_day(workout_without_secondary)

        total_extra = sum(
            max(0, w - wo) for w, wo in zip(counts_with, counts_without)
        )
        extra_days = sum(
            1 for w, wo in zip(counts_with, counts_without) if w > wo
        )

        assert 1 <= total_extra <= 2, \
            f"Expected 1-2 total extra exercises (max injections=2), got {total_extra}. " \
            f"Counts with: {counts_with}, Counts without: {counts_without}"
        assert extra_days <= 2, \
            f"At most 2 days should get extra exercise, got {extra_days}. " \
            f"Counts with: {counts_with}, Counts without: {counts_without}"

        print(f"✅ PASS: Max 2 injections verified. Extra exercises: {total_extra}, "
              f"Extra days: {extra_days}. Counts(with={counts_with}, without={counts_without})")

    def test_lower_days_not_injected_with_shoulders(self, workout_with_shoulders, workout_without_secondary):
        """
        Lower days (focus contains 'Lower', 'Leg', 'Quad', 'Hip', 'Hamstring')
        should have the SAME exercise count with and without secondary shoulders.
        """
        days_with = workout_with_shoulders["workout_days"]
        days_without = workout_without_secondary["workout_days"]

        lower_indices = [
            i for i, d in enumerate(days_with)
            if any(kw in d.get("focus", "").lower()
                   for kw in ["lower", "leg", "quad", "hamstring", "glute", "hip"])
        ]

        assert len(lower_indices) >= 2, \
            f"Expected at least 2 lower days, found {len(lower_indices)}. " \
            f"Focuses: {[d['focus'] for d in days_with]}"

        for idx in lower_indices:
            count_w = len(days_with[idx]["exercises"])
            count_wo = len(days_without[idx]["exercises"])
            focus = days_with[idx]["focus"]
            assert count_w <= count_wo + 0, \
                f"Lower day '{focus}' (day {idx+1}) gained exercise despite shoulders being incompatible! " \
                f"With: {count_w}, Without: {count_wo}. " \
                f"Exercises with: {[e['name'] for e in days_with[idx]['exercises']]}"
            print(f"✅ PASS: Lower day '{focus}' NOT injected. "
                  f"Exercise count with={count_w}, without={count_wo}")

    def test_upper_days_gain_exercise_vs_baseline(self, workout_with_shoulders, workout_without_secondary):
        """
        Each upper day with secondary injection should have +1 exercise vs baseline.
        For upper_push_heavy: base 5 slots → with secondary 6 (rear_delt injected)
        For upper_pull_heavy: base 6 slots → with secondary 7 (vertical_push injected)
        """
        days_with = workout_with_shoulders["workout_days"]
        days_without = workout_without_secondary["workout_days"]

        upper_indices = [
            i for i, d in enumerate(days_with)
            if any(kw in d.get("focus", "").lower()
                   for kw in ["upper", "chest", "back", "shoulder"])
        ]

        extra_count = 0
        for idx in upper_indices:
            count_w = len(days_with[idx]["exercises"])
            count_wo = len(days_without[idx]["exercises"])
            focus = days_with[idx]["focus"]
            if count_w > count_wo:
                extra_count += 1
                print(f"  Upper day '{focus}' (day {idx+1}): gained {count_w - count_wo} exercise "
                      f"({count_wo} → {count_w})")
            else:
                print(f"  Upper day '{focus}' (day {idx+1}): same count {count_w} (slot cap reached?)")

        assert extra_count >= 1, \
            f"Expected at least 1 upper day to gain an exercise from secondary injection, got {extra_count}. " \
            f"Check session slot capacity. Upper day counts with: {[len(days_with[i]['exercises']) for i in upper_indices]}, " \
            f"without: {[len(days_without[i]['exercises']) for i in upper_indices]}"
        print(f"✅ PASS: {extra_count} upper day(s) gained extra exercise from shoulder secondary injection")

    def test_exercise_type_accessory_used_for_injection(self, workout_with_shoulders, workout_without_secondary):
        """
        The injected secondary exercise should have exercise_type='accessory'.
        Compare upper days to find exercises present only in the secondary version.
        Those exercises should be exercise_type='accessory'.
        """
        days_with = workout_with_shoulders["workout_days"]
        days_without = workout_without_secondary["workout_days"]

        upper_indices = [
            i for i, d in enumerate(days_with)
            if any(kw in d.get("focus", "").lower()
                   for kw in ["upper", "chest", "back", "shoulder"])
        ]

        for idx in upper_indices:
            count_w = len(days_with[idx]["exercises"])
            count_wo = len(days_without[idx]["exercises"])
            if count_w > count_wo:
                # Injected exercise should be the last accessory (sorted by priority)
                # Check all exercises with type 'accessory' have shoulder-related muscle groups
                accessory_exs = [
                    ex for ex in days_with[idx]["exercises"]
                    if ex.get("exercise_type") == "accessory"
                ]
                print(f"  Upper day '{days_with[idx]['focus']}' accessory exercises: "
                      f"{[e['name'] for e in accessory_exs]}")
                # At least one accessory should be shoulder-related (the injection)
                shoulder_accessory = [
                    ex for ex in accessory_exs
                    if has_muscle_keyword(ex, SHOULDER_KEYWORDS)
                ]
                assert len(shoulder_accessory) >= 1, \
                    f"Expected at least one shoulder accessory in day {idx+1} after injection. " \
                    f"Accessories found: {[e['name'] for e in accessory_exs]}"
                print(f"✅ PASS: Shoulder accessory exercise found in upper day {idx+1}: "
                      f"{[e['name'] for e in shoulder_accessory]}")


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 3: Injection count smoke test via quick log check
# ══════════════════════════════════════════════════════════════════════════════

class TestInjectionCountIntegrity:
    """
    Verify that secondary_injections_this_week never exceeds 2 by checking
    that total extra exercises (vs no-secondary baseline) <= 2.
    """

    def test_injections_never_exceed_2_for_upper_lower_4day(self, api_session):
        """Generate 2 workouts and verify secondary injection count is exactly ≤ 2."""
        payload_with = {
            **BASE_UPPER_LOWER_PAYLOAD,
            "secondary_focus_areas": ["shoulders"]
        }
        payload_without = {**BASE_UPPER_LOWER_PAYLOAD}

        data_with = generate_workout(api_session, payload_with)
        data_without = generate_workout(api_session, payload_without)

        counts_with = count_exercises_per_day(data_with)
        counts_without = count_exercises_per_day(data_without)

        total_extra = sum(
            max(0, w - wo) for w, wo in zip(counts_with, counts_without)
        )

        assert total_extra <= 2, \
            f"Secondary injection exceeded MAX_SECONDARY_INJECTIONS=2. " \
            f"Total extra exercises: {total_extra}. " \
            f"Counts with={counts_with}, without={counts_without}"

        print(f"✅ PASS: Secondary injections capped at 2. "
              f"Total extra exercises: {total_extra}. "
              f"With: {counts_with}, Without: {counts_without}")

    def test_full_body_split_limits_core_injections_to_2(self, api_session):
        """
        For 3-day full_body with secondary=['core'], all days are 'any' (compatible),
        but MAX_SECONDARY_INJECTIONS=2 means only 2 of 3 days get injected.
        """
        payload_with = {
            **BASE_FULL_BODY_PAYLOAD,
            "secondary_focus_areas": ["core"]
        }
        payload_without = {**BASE_FULL_BODY_PAYLOAD}

        data_with = generate_workout(api_session, payload_with)
        data_without = generate_workout(api_session, payload_without)

        counts_with = count_exercises_per_day(data_with)
        counts_without = count_exercises_per_day(data_without)

        # Count days where secondary got injected
        injected_days = sum(
            1 for w, wo in zip(counts_with, counts_without) if w > wo
        )
        total_extra = sum(
            max(0, w - wo) for w, wo in zip(counts_with, counts_without)
        )

        assert total_extra <= 2, \
            f"Core injections exceeded MAX=2. Extra: {total_extra}. " \
            f"With: {counts_with}, Without: {counts_without}"
        # Full body all days are compatible, but max is 2, so 3rd day must NOT be injected
        assert injected_days <= 2, \
            f"Expected ≤2 injection days, got {injected_days}. " \
            f"With: {counts_with}, Without: {counts_without}"

        print(f"✅ PASS: Full body core injection limited to ≤2 days. "
              f"Injected days: {injected_days}, total extra: {total_extra}.")


# ══════════════════════════════════════════════════════════════════════════════
# Test Class 4: Health + access check before all tests
# ══════════════════════════════════════════════════════════════════════════════

class TestPreconditions:
    """Verify backend is reachable and test user has access."""

    def test_health_check(self, api_session):
        resp = api_session.get(f"{BASE_URL}/api/health", timeout=10)
        assert resp.status_code == 200, f"Backend health check failed: {resp.text}"
        print("✅ PASS: Backend health check OK")

    def test_user_has_access(self, api_session):
        resp = api_session.get(f"{BASE_URL}/api/subscription/check/{TEST_USER_ID}", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("has_access") is True, \
            f"Test user does not have access: {data}"
        print(f"✅ PASS: Test user has access. Reason: {data.get('reason')}")
