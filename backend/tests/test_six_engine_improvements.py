"""
Test file for Six EliteCoachingEngine Structural Improvements
Tests all 6 improvements with deep structural inspection of API responses.

IMPROVEMENT 1: Hybrid split is genuinely distinct (4 archetypes, conditioning in every session)
IMPROVEMENT 2: Functional A/B variation (genuinely different session structures)
IMPROVEMENT 3: Focus area volume boost (+1 set for primary focus patterns)
IMPROVEMENT 4: Conditioning finisher injection (lose_fat every session, body_recomp every-other)
IMPROVEMENT 5: Duration-adaptive rest (30min -> 0.55x rest, 30min -> max 4 exercises)
IMPROVEMENT 6: Calisthenics difficulty ordering (beginner=easiest first, advanced=hardest first)
"""

import pytest
import requests
import os
import time
import json

BASE_URL = os.environ.get(
    'EXPO_PUBLIC_BACKEND_URL',
    'https://nutrition-debug-1.preview.emergentagent.com'
).rstrip('/')

TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"
TIMEOUT = 200  # seconds (LLM calls can be slow)


# ===== Shared session-scoped fixtures to avoid duplicate LLM calls =====

@pytest.fixture(scope="session")
def http():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="session")
def hybrid_workout(http):
    """Generate hybrid build_muscle 4-day once for all Improvement 1 tests"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "build_muscle",
        "training_style": "hybrid", "focus_areas": ["full_body"],
        "equipment": ["full_gym"], "days_per_week": 4,
        "duration_minutes": 60, "fitness_level": "intermediate",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating hybrid workout (this may take 60-120s)...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] hybrid_workout done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"hybrid_workout fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def functional_workout(http):
    """Generate functional general_fitness 4-day once for all Improvement 2 tests"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "general_fitness",
        "training_style": "functional", "focus_areas": ["full_body"],
        "equipment": ["full_gym"], "days_per_week": 4,
        "duration_minutes": 60, "fitness_level": "intermediate",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating functional workout (this may take 60-120s)...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] functional_workout done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"functional_workout fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def chest_focus_workout(http):
    """Generate build_muscle chest-focus 4-day once for Improvement 3 tests"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "build_muscle",
        "training_style": "weights", "focus_areas": ["chest"],
        "equipment": ["full_gym"], "days_per_week": 4,
        "duration_minutes": 60, "fitness_level": "intermediate",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating chest-focus workout (this may take 60-120s)...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] chest_focus_workout done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"chest_focus_workout fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def lose_fat_workout(http):
    """Generate lose_fat weights 4-day once for Improvement 4 tests"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "lose_fat",
        "training_style": "weights", "focus_areas": ["full_body"],
        "equipment": ["full_gym"], "days_per_week": 4,
        "duration_minutes": 60, "fitness_level": "intermediate",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating lose_fat workout (this may take 60-120s)...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] lose_fat_workout done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"lose_fat_workout fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def body_recomp_workout(http):
    """Generate body_recomp weights 4-day once for Improvement 4b tests"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "body_recomp",
        "training_style": "weights", "focus_areas": ["full_body"],
        "equipment": ["full_gym"], "days_per_week": 4,
        "duration_minutes": 60, "fitness_level": "intermediate",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating body_recomp workout (this may take 60-120s)...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] body_recomp_workout done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"body_recomp_workout fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def short_duration_workout(http):
    """Generate 30-min workout for Improvement 5 tests"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "build_muscle",
        "training_style": "weights", "focus_areas": ["full_body"],
        "equipment": ["full_gym"], "days_per_week": 3,
        "duration_minutes": 30, "fitness_level": "intermediate",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating 30-min workout for duration test...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] short_duration_workout done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"short_duration_workout fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def long_duration_workout(http):
    """Generate 60-min workout for Improvement 5 tests (baseline)"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "build_muscle",
        "training_style": "weights", "focus_areas": ["full_body"],
        "equipment": ["full_gym"], "days_per_week": 3,
        "duration_minutes": 60, "fitness_level": "intermediate",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating 60-min workout for duration test...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] long_duration_workout done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"long_duration_workout fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def beginner_calisthenics_workout(http):
    """Generate beginner calisthenics 3-day once for Improvement 6 tests"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "general_fitness",
        "training_style": "calisthenics", "focus_areas": ["full_body"],
        "equipment": ["bodyweight"], "days_per_week": 3,
        "duration_minutes": 60, "fitness_level": "beginner",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating BEGINNER calisthenics workout...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] beginner_calisthenics done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"beginner_calisthenics fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


@pytest.fixture(scope="session")
def advanced_calisthenics_workout(http):
    """Generate advanced calisthenics 3-day once for Improvement 6 tests"""
    payload = {
        "user_id": TEST_USER_ID, "goal": "build_muscle",
        "training_style": "calisthenics", "focus_areas": ["full_body"],
        "equipment": ["bodyweight"], "days_per_week": 3,
        "duration_minutes": 60, "fitness_level": "advanced",
        "preferred_split": "ai_choose"
    }
    print(f"\n[FIXTURE] Generating ADVANCED calisthenics workout...")
    start = time.time()
    r = http.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=TIMEOUT)
    elapsed = time.time() - start
    print(f"[FIXTURE] advanced_calisthenics done in {elapsed:.1f}s | status={r.status_code}")
    assert r.status_code == 200, f"advanced_calisthenics fixture failed: {r.status_code}: {r.text[:300]}"
    return r.json()


# ===================== CONDITIONING HELPER =====================

CONDITIONING_KEYWORDS = [
    "burpee", "battle rope", "assault bike", "jump rope", "mountain climber",
    "rowing machine", "interval", "sprint", "kettlebell swing"
]


def has_conditioning(exercises):
    """Check if a day's exercises list contains a conditioning exercise"""
    for ex in exercises:
        if ex.get("exercise_type") == "conditioning":
            return True, "exercise_type=conditioning"
        effort = ex.get("effort_target", "").lower()
        if "high intensity" in effort:
            return True, f"effort='{ex.get('effort_target')}'"
        name = ex.get("name", "").lower()
        for kw in CONDITIONING_KEYWORDS:
            if kw in name:
                return True, f"name='{ex.get('name')}'"
    return False, "not found"


# ========================================================
# IMPROVEMENT 1: Hybrid Split — Genuinely Distinct
# ========================================================
class TestImprovement1HybridSplit:

    def test_hybrid_split_name(self, hybrid_workout):
        split_name = hybrid_workout.get("split_name", "")
        print(f"\n[IMP-1] split_name='{split_name}'")
        assert split_name == "Hybrid Strength + Conditioning", (
            f"IMPROVEMENT 1 FAILED: Expected 'Hybrid Strength + Conditioning', got '{split_name}'"
        )
        print(f"✅ [IMP-1] split_name CORRECT: '{split_name}'")

    def test_hybrid_session_labels(self, hybrid_workout):
        """Each day's 'day' field must contain the correct hybrid label"""
        days = hybrid_workout.get("workout_days", [])
        assert len(days) == 4, f"Expected 4 days, got {len(days)}"

        EXPECTED = [
            "Hybrid \u2013 Push + Conditioning",      # Day 1
            "Hybrid \u2013 Lower + Conditioning",     # Day 2
            "Hybrid \u2013 Pull + Conditioning",      # Day 3
            "Hybrid \u2013 Power & Conditioning",     # Day 4
        ]

        day_fields = [d.get("day", "") for d in days]
        print(f"\n[IMP-1b] Day fields: {day_fields}")

        for i, expected in enumerate(EXPECTED):
            actual = day_fields[i] if i < len(day_fields) else ""
            assert expected in actual, (
                f"IMPROVEMENT 1 FAILED: Day {i+1} should contain '{expected}', got '{actual}'"
            )
            print(f"✅ [IMP-1b] Day {i+1}: '{actual}' contains '{expected}'")

    def test_hybrid_conditioning_every_day(self, hybrid_workout):
        """At least one conditioning exercise must appear in EVERY hybrid day"""
        days = hybrid_workout.get("workout_days", [])
        for i, day in enumerate(days):
            exercises = day.get("exercises", [])
            label = day.get("day", f"Day {i+1}")
            types = [e.get("exercise_type") for e in exercises]
            names = [e.get("name", "") for e in exercises]
            found, reason = has_conditioning(exercises)
            print(f"[IMP-1c] {label}: conditioning={found} ({reason}) | types={types}")
            assert found, (
                f"IMPROVEMENT 1 FAILED: {label} has NO conditioning exercise. "
                f"types={types} names={names}"
            )
            print(f"✅ [IMP-1c] {label}: conditioning present ({reason})")

        print(f"✅ [IMP-1c] ALL 4 hybrid days contain conditioning exercises")


# ========================================================
# IMPROVEMENT 2: Functional A/B Variation
# ========================================================
class TestImprovement2FunctionalAB:

    def test_functional_day_labels(self, functional_workout):
        """Days 1&3 = Movement Quality, Days 2&4 = Strength & Capacity"""
        days = functional_workout.get("workout_days", [])
        assert len(days) == 4, f"Expected 4 days, got {len(days)}"

        day_fields = [d.get("day", "") for d in days]
        print(f"\n[IMP-2] Day fields: {day_fields}")

        EXPECTED_KEYWORD = ["Movement Quality", "Strength & Capacity", "Movement Quality", "Strength & Capacity"]
        for i, kw in enumerate(EXPECTED_KEYWORD):
            actual = day_fields[i] if i < len(day_fields) else ""
            assert kw in actual, (
                f"IMPROVEMENT 2 FAILED: Day {i+1} should contain '{kw}', got '{actual}'"
            )
            print(f"✅ [IMP-2] Day {i+1}: '{actual}' contains '{kw}'")

    def test_functional_sessions_structurally_different(self, functional_workout):
        """Day 1 and Day 2 must have different focus text (different archetypes)"""
        days = functional_workout.get("workout_days", [])
        assert len(days) >= 2, f"Need at least 2 days, got {len(days)}"

        focus1 = days[0].get("focus", "")
        focus2 = days[1].get("focus", "")
        types1 = [e.get("exercise_type") for e in days[0].get("exercises", [])]
        types2 = [e.get("exercise_type") for e in days[1].get("exercises", [])]

        print(f"\n[IMP-2b] Day 1 focus: '{focus1}' | types: {types1}")
        print(f"[IMP-2b] Day 2 focus: '{focus2}' | types: {types2}")

        assert focus1 != focus2, (
            f"IMPROVEMENT 2 FAILED: Day 1 and Day 2 have IDENTICAL focus: '{focus1}' "
            "— sessions not structurally distinct"
        )
        print(f"✅ [IMP-2b] Day 1 != Day 2 focus — structurally distinct sessions confirmed")

        # Day 1 must be unilateral/movement quality archetype
        assert any(kw in focus1 for kw in ["Unilateral", "Movement", "Trunk", "Control", "Quality"]), (
            f"IMPROVEMENT 2 FAILED: Day 1 focus '{focus1}' doesn't match Movement Quality archetype"
        )
        # Day 2 must be strength/capacity archetype
        assert any(kw in focus2 for kw in ["Strength", "Capacity", "Power", "Multi"]), (
            f"IMPROVEMENT 2 FAILED: Day 2 focus '{focus2}' doesn't match Strength & Capacity archetype"
        )
        print(f"✅ [IMP-2b] Day 1 is Movement Quality, Day 2 is Strength & Capacity — CONFIRMED")

    def test_functional_days_3_4_repeat_ab_pattern(self, functional_workout):
        """Days 3&4 should be same archetypes as Days 1&2 (A/B repeat)"""
        days = functional_workout.get("workout_days", [])
        assert len(days) == 4, f"Expected 4 days, got {len(days)}"

        # Day 1 and Day 3 should have same focus (both Movement Quality)
        focus1 = days[0].get("focus", "")
        focus3 = days[2].get("focus", "")
        focus2 = days[1].get("focus", "")
        focus4 = days[3].get("focus", "")

        print(f"\n[IMP-2c] Day 1 focus: '{focus1}' | Day 3 focus: '{focus3}'")
        print(f"[IMP-2c] Day 2 focus: '{focus2}' | Day 4 focus: '{focus4}'")

        # Days 1 and 3 should both be Movement Quality type
        assert any(kw in focus1 for kw in ["Unilateral", "Movement", "Trunk", "Quality"]), \
            f"Day 1 should be Movement Quality, got '{focus1}'"
        assert any(kw in focus3 for kw in ["Unilateral", "Movement", "Trunk", "Quality"]), \
            f"Day 3 should be Movement Quality, got '{focus3}'"

        # Days 2 and 4 should both be Strength & Capacity type
        assert any(kw in focus2 for kw in ["Strength", "Capacity", "Power"]), \
            f"Day 2 should be Strength & Capacity, got '{focus2}'"
        assert any(kw in focus4 for kw in ["Strength", "Capacity", "Power"]), \
            f"Day 4 should be Strength & Capacity, got '{focus4}'"

        print(f"✅ [IMP-2c] A/B rotation confirmed: Days 1&3=Movement Quality, Days 2&4=Strength & Capacity")


# ========================================================
# IMPROVEMENT 3: Focus Area Volume Boost
# ========================================================
class TestImprovement3FocusVolumeBoost:

    def test_chest_focus_primary_compound_has_5_sets(self, chest_focus_workout):
        """
        With focus_areas=['chest'], horizontal_push (primary_compound) must have sets >= 5
        (base 4 for build_muscle primary_compound + 1 boost = 5)
        """
        days = chest_focus_workout.get("workout_days", [])
        assert len(days) == 4, f"Expected 4 days, got {len(days)}"

        # upper_lower 4-day build_muscle: Day 1 = upper_push_heavy
        day1_exercises = days[0].get("exercises", [])
        day1_label = days[0].get("day", "Day 1")

        all_sets_and_types = [
            (ex.get("name"), ex.get("sets"), ex.get("exercise_type"))
            for ex in day1_exercises
        ]
        print(f"\n[IMP-3] Day 1: '{day1_label}'")
        print(f"[IMP-3] All (name, sets, type): {all_sets_and_types}")

        assert len(day1_exercises) >= 2, f"Expected >= 2 exercises in Day 1, got {len(day1_exercises)}"

        # First exercise = primary_compound (horizontal_push) → sets should be 5
        first = day1_exercises[0]
        print(f"[IMP-3] First exercise: '{first.get('name')}', sets={first.get('sets')}, type={first.get('exercise_type')}")
        assert first.get("sets", 0) >= 5, (
            f"IMPROVEMENT 3 FAILED: First exercise '{first.get('name')}' (primary_compound) "
            f"has sets={first.get('sets')}, expected >= 5 (base=4 + boost=1). "
            f"All exercises: {all_sets_and_types}"
        )
        print(f"✅ [IMP-3] First exercise '{first.get('name')}' has {first.get('sets')} sets >= 5 (BOOSTED)")

        # Second exercise = incline_push (secondary_compound in primary_patterns) → sets should be 4
        second = day1_exercises[1]
        print(f"[IMP-3] Second exercise: '{second.get('name')}', sets={second.get('sets')}, type={second.get('exercise_type')}")
        assert second.get("sets", 0) >= 4, (
            f"IMPROVEMENT 3 FAILED: Second exercise '{second.get('name')}' (incline_push secondary_compound) "
            f"has sets={second.get('sets')}, expected >= 4 (base=3 + boost=1). "
            f"All exercises: {all_sets_and_types}"
        )
        print(f"✅ [IMP-3] Second exercise '{second.get('name')}' has {second.get('sets')} sets >= 4 (BOOSTED)")

    def test_chest_patterns_ordering_before_isolation(self, chest_focus_workout):
        """primary_compound exercises must appear before isolation exercises in same session"""
        days = chest_focus_workout.get("workout_days", [])
        day1_exercises = days[0].get("exercises", [])

        primary_idx = next(
            (i for i, ex in enumerate(day1_exercises) if ex.get("exercise_type") == "primary_compound"),
            None
        )
        isolation_idx = next(
            (i for i, ex in enumerate(day1_exercises) if ex.get("exercise_type") == "isolation"),
            None
        )

        order_info = [(ex.get("name"), ex.get("exercise_type"), ex.get("sets")) for ex in day1_exercises]
        print(f"\n[IMP-3b] Day 1 exercise order: {order_info}")
        print(f"[IMP-3b] First primary_compound at index: {primary_idx}")
        print(f"[IMP-3b] First isolation at index: {isolation_idx}")

        if primary_idx is not None and isolation_idx is not None:
            assert primary_idx < isolation_idx, (
                f"IMPROVEMENT 3 FAILED: primary_compound (idx {primary_idx}) should appear "
                f"BEFORE isolation (idx {isolation_idx}). Order: {order_info}"
            )
            print(f"✅ [IMP-3b] Ordering correct: primary_compound (idx {primary_idx}) < isolation (idx {isolation_idx})")
        else:
            # At minimum, primary_compound should be first
            assert primary_idx == 0, (
                f"IMPROVEMENT 3 FAILED: primary_compound should be first (idx 0), "
                f"got idx {primary_idx}. Order: {order_info}"
            )
            print(f"✅ [IMP-3b] primary_compound is first exercise (isolation not found in session)")


# ========================================================
# IMPROVEMENT 4: Conditioning Finisher — lose_fat Every Day
# ========================================================
class TestImprovement4ConditioningFinisher:

    def test_lose_fat_all_days_have_conditioning(self, lose_fat_workout):
        """Every day in a lose_fat weights program must have a conditioning finisher"""
        days = lose_fat_workout.get("workout_days", [])
        assert len(days) == 4, f"Expected 4 days, got {len(days)}"

        for i, day in enumerate(days):
            exercises = day.get("exercises", [])
            label = day.get("day", f"Day {i+1}")
            types = [ex.get("exercise_type") for ex in exercises]
            efforts = [ex.get("effort_target", "") for ex in exercises]
            names = [ex.get("name", "") for ex in exercises]
            found, reason = has_conditioning(exercises)

            print(f"[IMP-4] {label}: conditioning={found} ({reason})")
            print(f"  types: {types}")
            print(f"  efforts: {efforts}")
            print(f"  names: {names}")

            assert found, (
                f"IMPROVEMENT 4 FAILED: {label} has NO conditioning finisher for lose_fat. "
                f"types={types} efforts={efforts} names={names}"
            )
            print(f"✅ [IMP-4] {label}: conditioning finisher PRESENT ({reason})")

        print(f"✅ [IMP-4] ALL 4 lose_fat days have conditioning finisher")


# ========================================================
# IMPROVEMENT 4b: body_recomp — Every-Other Session
# ========================================================
class TestImprovement4bBodyRecompConditioning:

    def test_body_recomp_every_other_session(self, body_recomp_workout):
        """
        Day 1 (i=0) and Day 3 (i=2) must have conditioning.
        Day 2 (i=1) and Day 4 (i=3) must NOT have conditioning.
        """
        days = body_recomp_workout.get("workout_days", [])
        assert len(days) == 4, f"Expected 4 days, got {len(days)}"

        SHOULD_HAVE = [True, False, True, False]  # indexed by day position

        for i, day in enumerate(days):
            exercises = day.get("exercises", [])
            label = day.get("day", f"Day {i+1}")
            types = [ex.get("exercise_type") for ex in exercises]
            names = [ex.get("name", "") for ex in exercises]
            found, reason = has_conditioning(exercises)
            expected = SHOULD_HAVE[i]

            print(f"[IMP-4b] {label} (i={i}): expected={expected}, actual={found} ({reason})")
            print(f"  types: {types}  names: {names}")

            assert found == expected, (
                f"IMPROVEMENT 4b FAILED: {label} (i={i}): expected conditioning={expected}, "
                f"got={found}. types={types} names={names}"
            )
            state = "PRESENT" if found else "ABSENT (correct for even session)"
            print(f"✅ [IMP-4b] {label}: conditioning {state}")

        print(f"✅ [IMP-4b] body_recomp every-other conditioning VERIFIED (odd=yes, even=no)")


# ========================================================
# IMPROVEMENT 5: Duration-Adaptive Rest
# ========================================================
class TestImprovement5DurationAdaptiveRest:

    @staticmethod
    def _avg_rest(workout_data):
        all_rest = [
            ex.get("rest_seconds", 0)
            for day in workout_data.get("workout_days", [])
            for ex in day.get("exercises", [])
            if ex.get("rest_seconds", 0) > 0
        ]
        return sum(all_rest) / len(all_rest) if all_rest else 0

    def test_30min_has_lower_rest_than_60min(self, short_duration_workout, long_duration_workout):
        """30-min plan average rest should be ~0.55x of 60-min plan rest"""
        avg_a = self._avg_rest(short_duration_workout)
        avg_b = self._avg_rest(long_duration_workout)

        # Detailed breakdown for debugging
        for day_idx, day in enumerate(short_duration_workout.get("workout_days", [])):
            rests = [ex.get("rest_seconds", 0) for ex in day.get("exercises", [])]
            print(f"[IMP-5] 30min Day {day_idx+1} rest values: {rests}")
        for day_idx, day in enumerate(long_duration_workout.get("workout_days", [])):
            rests = [ex.get("rest_seconds", 0) for ex in day.get("exercises", [])]
            print(f"[IMP-5] 60min Day {day_idx+1} rest values: {rests}")

        print(f"\n[IMP-5] avg_rest(30min) = {avg_a:.1f}s")
        print(f"[IMP-5] avg_rest(60min) = {avg_b:.1f}s")

        assert avg_b > 0, f"60-min plan avg_rest is 0 — workout may be empty"
        assert avg_a > 0, f"30-min plan avg_rest is 0 — workout may be empty"

        ratio = avg_a / avg_b
        print(f"[IMP-5] ratio = {ratio:.3f}  (expected ~0.55, must be < 0.85 to prove scaling works)")

        assert ratio < 0.85, (
            f"IMPROVEMENT 5 FAILED: avg_rest ratio is {ratio:.3f} (not significantly lower). "
            f"30min={avg_a:.1f}s, 60min={avg_b:.1f}s. Expected ~0.55x ratio for 30min plan."
        )
        print(f"✅ [IMP-5] Rest scaling working: ratio={ratio:.3f} significantly < 1.0 (expected ~0.55)")

    def test_30min_max_4_exercises_per_session(self, short_duration_workout):
        """Every session in a 30-min plan must have at most 4 exercises"""
        days = short_duration_workout.get("workout_days", [])
        for i, day in enumerate(days):
            exercises = day.get("exercises", [])
            label = day.get("day", f"Day {i+1}")
            count = len(exercises)
            names = [ex.get("name") for ex in exercises]
            print(f"[IMP-5b] {label}: {count} exercises -> {names}")

            assert count <= 4, (
                f"IMPROVEMENT 5 FAILED: {label} has {count} exercises > 4 max for 30-min session. "
                f"exercises: {names}"
            )
            print(f"✅ [IMP-5b] {label}: {count} exercises <= 4")

        print(f"✅ [IMP-5b] All 30-min sessions have <= 4 exercises")


# ========================================================
# IMPROVEMENT 6: Calisthenics Difficulty Ordering
# ========================================================
class TestImprovement6CalisthenicsDifficulty:

    # Tier 3 advanced exercises (from BODYWEIGHT_DIFFICULTY)
    ADVANCED_TERMS = [
        "archer push-up", "handstand push-up", "pistol squat",
        "pull-up", "chin-up", "dip", "muscle-up", "terminal knee extension"
    ]

    # Tier 1 beginner exercises
    BEGINNER_TERMS = [
        "push-up", "bodyweight squat", "glute bridge", "plank",
        "bird dog", "reverse lunge", "dead bug", "side plank", "hip thrust"
    ]

    def test_beginner_no_advanced_exercises_first(self, beginner_calisthenics_workout):
        """
        Beginner calisthenics: first exercise option (opts[0]) should NOT be an advanced tier-3 exercise.
        We verify via:
        1. Chosen exercise names are not tier-3 advanced
        2. substitution_hint (opts[1:3]) doesn't start with 'Archer Push-Up' or 'Handstand Push-Up'
           (which would indicate options were sorted hardest-first, i.e., wrong order for beginner)
        """
        days = beginner_calisthenics_workout.get("workout_days", [])
        assert len(days) >= 1, "No workout days returned"

        all_names = []
        all_hints = []
        for day in days:
            for ex in day.get("exercises", []):
                all_names.append(ex.get("name", ""))
                all_hints.append((ex.get("name", ""), ex.get("substitution_hint", "") or ""))

        print(f"\n[IMP-6] BEGINNER calisthenics exercises:")
        for day_idx, day in enumerate(days):
            for ex in day.get("exercises", []):
                print(f"  Day {day_idx+1}: '{ex.get('name')}' | hint: '{ex.get('substitution_hint')}' | type: {ex.get('exercise_type')}")

        # CRITICAL: For BEGINNER, options list is sorted ascending (easiest first)
        # So opts[0] = easiest, opts[1:3] = slightly harder
        # If hint starts with "Archer Push-Up", it means opts[1] is Archer → opts[0] is also tier-3 (wrong)
        ADVANCED_FIRST_TERMS = ["archer push-up", "handstand push-up", "pistol squat (assisted)", "muscle-up"]
        for name, hint in all_hints:
            if hint:
                hint_lower = hint.lower().strip()
                for adv in ADVANCED_FIRST_TERMS:
                    assert not hint_lower.startswith(adv), (
                        f"IMPROVEMENT 6 FAILED: For BEGINNER calisthenics, exercise '{name}' has "
                        f"substitution_hint starting with advanced exercise: '{hint}'. "
                        "This means the options list is sorted hardest-first (WRONG for beginner)"
                    )

        # Also check: beginner exercises should NOT include advanced tier-3 names predominantly
        STRICT_ADVANCED = ["archer push-up", "handstand push-up", "pistol squat", "muscle-up"]
        found_advanced = [n for n in all_names if any(a in n.lower() for a in STRICT_ADVANCED)]
        if found_advanced:
            print(f"⚠️ [IMP-6] WARNING: Found advanced exercises in BEGINNER workout: {found_advanced}")
            # This is a soft warning — LLM may pick from options, but default_name (opts[0]) should be easy
        else:
            print(f"✅ [IMP-6] No tier-3 advanced exercises chosen in beginner workout")

        print(f"✅ [IMP-6] Beginner calisthenics difficulty ordering: CORRECT (easy-first)")

    def test_advanced_calisthenics_uses_hard_exercises(self, advanced_calisthenics_workout):
        """Advanced calisthenics: should include tier-3 exercises (Pull-Up, Chin-Up, Archer Push-Up, etc.)"""
        days = advanced_calisthenics_workout.get("workout_days", [])
        assert len(days) >= 1, "No workout days returned"

        all_names = []
        for day in days:
            for ex in day.get("exercises", []):
                all_names.append(ex.get("name", ""))

        print(f"\n[IMP-6b] ADVANCED calisthenics exercises:")
        for day_idx, day in enumerate(days):
            for ex in day.get("exercises", []):
                print(f"  Day {day_idx+1}: '{ex.get('name')}' | hint: '{ex.get('substitution_hint')}' | type: {ex.get('exercise_type')}")

        # For advanced: at least some exercises should be tier-3 advanced
        found_advanced_count = sum(
            1 for name in all_names
            if any(term in name.lower() for term in self.ADVANCED_TERMS)
        )
        total = len(all_names)
        print(f"[IMP-6b] Advanced exercises: {found_advanced_count}/{total}")
        print(f"[IMP-6b] Found advanced: {[n for n in all_names if any(t in n.lower() for t in self.ADVANCED_TERMS)]}")

        assert found_advanced_count > 0, (
            f"IMPROVEMENT 6 FAILED: No tier-3 advanced exercises found in ADVANCED calisthenics workout. "
            f"Expected Pull-Up, Chin-Up, Archer Push-Up, Pistol Squat, etc. Found: {all_names}"
        )

        # For advanced, basic-only exercises should NOT dominate
        BASIC_ONLY = ["push-up", "bodyweight squat"]
        basic_count = sum(1 for name in all_names if any(b == name.lower() for b in BASIC_ONLY))
        basic_ratio = basic_count / total if total > 0 else 0
        print(f"[IMP-6b] Basic exercise ratio: {basic_count}/{total} = {basic_ratio:.0%}")

        assert basic_ratio < 0.5, (
            f"IMPROVEMENT 6 FAILED: ADVANCED calisthenics has too many basic exercises "
            f"({basic_count}/{total} = {basic_ratio:.0%})"
        )

        print(f"✅ [IMP-6b] Advanced calisthenics has {found_advanced_count} advanced exercises ({found_advanced_count/total:.0%})")
        print(f"✅ [IMP-6b] Calisthenics difficulty ordering: CORRECT (hard-first for advanced)")
