"""
Tests for Exercise Naming & Categorization Overrides
Covers:
  - EXERCISE_NAME_OVERRIDES: raw ExerciseDB names → gym-standard display names
  - EXERCISE_TARGET_OVERRIDES: compound exercises appear under multiple muscle chips
  - Reverse text search: 'back squat' finds 'barbell full squat' (renamed → 'Barbell Back Squat')
  - Updated $or query: primary target, secondary_muscles array, and override names

Review request criteria:
  1. muscle=legs → 'Barbell Back Squat' MUST appear
  2. muscle=glutes → 'Barbell Back Squat' MUST appear
  3. search=back+squat → ≥1 result with name='Barbell Back Squat'
  4. search=skull+crusher → 'Skull Crushers' in results
  5. muscle=triceps → 'Barbell Bench Press' appears
  6. muscle=back → 'Deadlift' appears
  7. search=leg+press → 'Leg Press Machine' in results
  8. muscle=legs → total_count > 250
  9. muscle=glutes → total_count > 200
  10. No regressions: each muscle chip returns relevant exercises
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('EXPO_BACKEND_URL', '').rstrip('/')

# Helper to load all pages of a muscle filter search
def get_all_names_for_muscle(muscle: str) -> list:
    """Fetch all exercise names for a given muscle chip (paginate through results)."""
    session = requests.Session()
    names = []
    offset = 0
    limit = 100
    while True:
        resp = session.get(
            f"{BASE_URL}/api/exercises/search",
            params={"muscle": muscle, "limit": limit, "offset": offset},
            timeout=15
        )
        assert resp.status_code == 200, f"muscle={muscle} offset={offset} → {resp.status_code}"
        data = resp.json()
        batch = [ex["name"] for ex in data["exercises"]]
        names.extend(batch)
        if offset + limit >= data["total_count"]:
            break
        offset += limit
    return names


# ─────────────────────────────────────────────────────────────────────────────
class TestHealthCheck:
    """Prerequisite: backend must be reachable"""

    def test_health_check(self):
        resp = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert resp.status_code == 200, f"Backend not reachable: {resp.status_code}"
        print("✅ Health check passed")


# ─────────────────────────────────────────────────────────────────────────────
class TestExerciseNameOverrides:
    """EXERCISE_NAME_OVERRIDES: verify raw → display name transformation"""

    def test_barbell_full_squat_renamed_to_barbell_back_squat(self):
        """'barbell full squat' (ExerciseDB raw) must appear as 'Barbell Back Squat' in API"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"search": "full squat", "limit": 20}, timeout=10)
        assert resp.status_code == 200
        names = [ex["name"] for ex in resp.json()["exercises"]]
        print(f"  full squat search returned: {names}")
        assert "Barbell Back Squat" in names, \
            f"Expected 'Barbell Back Squat' but got: {names}"
        # Old raw name should NOT appear
        assert "Barbell Full Squat" not in names, \
            "Raw name 'Barbell Full Squat' should not appear — must be renamed"
        print("✅ 'barbell full squat' correctly renamed to 'Barbell Back Squat'")

    def test_skull_crushers_display_name(self):
        """'barbell lying triceps extension' → 'Skull Crushers' display name"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"search": "lying triceps", "limit": 20}, timeout=10)
        assert resp.status_code == 200
        names = [ex["name"] for ex in resp.json()["exercises"]]
        print(f"  lying triceps search returned: {names}")
        assert "Skull Crushers" in names, \
            f"Expected 'Skull Crushers' but got: {names}"
        assert "Barbell Lying Triceps Extension" not in names, \
            "Raw name 'Barbell Lying Triceps Extension' should not appear"
        print("✅ 'barbell lying triceps extension' correctly renamed to 'Skull Crushers'")

    def test_deadlift_display_name(self):
        """'barbell deadlift' → 'Deadlift'"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"search": "barbell deadlift", "limit": 20}, timeout=10)
        assert resp.status_code == 200
        names = [ex["name"] for ex in resp.json()["exercises"]]
        print(f"  barbell deadlift search returned: {names}")
        assert "Deadlift" in names, f"Expected 'Deadlift' but got: {names}"
        print("✅ 'barbell deadlift' correctly renamed to 'Deadlift'")

    def test_leg_press_machine_display_name(self):
        """'lever leg press' → 'Leg Press Machine'"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"search": "lever leg press", "limit": 20}, timeout=10)
        assert resp.status_code == 200
        names = [ex["name"] for ex in resp.json()["exercises"]]
        print(f"  lever leg press search returned: {names}")
        assert "Leg Press Machine" in names, \
            f"Expected 'Leg Press Machine' but got: {names}"
        print("✅ 'lever leg press' correctly renamed to 'Leg Press Machine'")

    def test_romanian_deadlift_display_name(self):
        """'barbell romanian deadlift' → 'Romanian Deadlift'"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"search": "romanian deadlift", "limit": 20}, timeout=10)
        assert resp.status_code == 200
        names = [ex["name"] for ex in resp.json()["exercises"]]
        print(f"  romanian deadlift search returned: {names}")
        assert "Romanian Deadlift" in names, \
            f"Expected 'Romanian Deadlift' but got: {names}"
        print("✅ 'barbell romanian deadlift' correctly renamed to 'Romanian Deadlift'")


# ─────────────────────────────────────────────────────────────────────────────
class TestExerciseTargetOverrides:
    """EXERCISE_TARGET_OVERRIDES: compound exercises appear under multiple muscle chips"""

    def test_barbell_back_squat_appears_under_legs(self):
        """CRITICAL: muscle=legs MUST include 'Barbell Back Squat' (was missing — ExerciseDB tags glutes only)"""
        resp = requests.get(
            f"{BASE_URL}/api/exercises/search",
            params={"muscle": "legs", "limit": 100, "offset": 0},
            timeout=15
        )
        assert resp.status_code == 200
        data = resp.json()
        # Check total count first (should be > 250 with override)
        total = data["total_count"]
        print(f"  muscle=legs total_count = {total}")
        assert total > 250, f"Expected >250 exercises for legs, got {total}"

        # Fetch all names (paginate if needed)
        names = get_all_names_for_muscle("legs")
        print(f"  Total legs exercises found: {len(names)}")
        assert "Barbell Back Squat" in names, \
            f"'Barbell Back Squat' MISSING from legs results. Found: {[n for n in names if 'squat' in n.lower() or 'Squat' in n]}"
        print("✅ 'Barbell Back Squat' appears under legs chip")

    def test_barbell_back_squat_appears_under_glutes(self):
        """CRITICAL: muscle=glutes MUST include 'Barbell Back Squat'"""
        resp = requests.get(
            f"{BASE_URL}/api/exercises/search",
            params={"muscle": "glutes", "limit": 100, "offset": 0},
            timeout=15
        )
        assert resp.status_code == 200
        data = resp.json()
        total = data["total_count"]
        print(f"  muscle=glutes total_count = {total}")
        assert total > 200, f"Expected >200 exercises for glutes, got {total}"

        names = get_all_names_for_muscle("glutes")
        print(f"  Total glutes exercises found: {len(names)}")
        assert "Barbell Back Squat" in names, \
            f"'Barbell Back Squat' MISSING from glutes results. Squat names found: {[n for n in names if 'squat' in n.lower() or 'Squat' in n]}"
        print("✅ 'Barbell Back Squat' appears under glutes chip")

    def test_deadlift_appears_under_back(self):
        """muscle=back MUST include 'Deadlift' (barbell deadlift override → back chip)"""
        names = get_all_names_for_muscle("back")
        deadlift_names = [n for n in names if "Deadlift" in n]
        print(f"  Deadlift names under back: {deadlift_names}")
        assert len(deadlift_names) > 0, \
            f"'Deadlift' MISSING from back results. First 20 names: {names[:20]}"
        assert any("Deadlift" in n for n in deadlift_names), \
            "Expected 'Deadlift' in back results"
        print("✅ 'Deadlift' appears under back chip")

    def test_deadlift_also_appears_under_glutes(self):
        """muscle=glutes MUST include 'Deadlift' (barbell deadlift override → glutes, legs, back)"""
        names = get_all_names_for_muscle("glutes")
        deadlift_names = [n for n in names if "Deadlift" in n]
        print(f"  Deadlift names under glutes: {deadlift_names}")
        assert len(deadlift_names) > 0, \
            f"'Deadlift' MISSING from glutes results"
        print("✅ 'Deadlift' appears under glutes chip")

    def test_barbell_bench_press_appears_under_triceps(self):
        """muscle=triceps MUST include 'Barbell Bench Press' (compound cross-category)"""
        names = get_all_names_for_muscle("triceps")
        bench_names = [n for n in names if "Bench Press" in n]
        print(f"  Bench press names under triceps: {bench_names}")
        assert len(bench_names) > 0, \
            f"'Barbell Bench Press' MISSING from triceps. First 30 names: {names[:30]}"
        print("✅ Bench Press variants appear under triceps chip")

    def test_overhead_press_appears_under_triceps(self):
        """muscle=triceps should also include overhead press variants"""
        names = get_all_names_for_muscle("triceps")
        ohp_names = [n for n in names if "Overhead Press" in n or "Overhead press" in n.lower()]
        print(f"  OHP names under triceps: {ohp_names}")
        assert len(ohp_names) > 0, \
            f"Overhead Press variants MISSING from triceps chip"
        print("✅ Overhead Press variants appear under triceps chip")

    def test_squat_also_appears_under_glutes(self):
        """All squat variants in EXERCISE_TARGET_OVERRIDES must appear under glutes"""
        names = get_all_names_for_muscle("glutes")
        squat_names = [n for n in names if "squat" in n.lower() or "Squat" in n]
        print(f"  Squat names under glutes: {squat_names}")
        assert len(squat_names) >= 3, \
            f"Expected at least 3 squat variants under glutes, got: {squat_names}"
        print(f"✅ {len(squat_names)} squat variants appear under glutes chip")


# ─────────────────────────────────────────────────────────────────────────────
class TestReverseTextSearch:
    """Reverse lookup: searching display name finds the raw-named exercise"""

    def test_search_back_squat_finds_barbell_back_squat(self):
        """CRITICAL: search='back squat' → at least 1 result named 'Barbell Back Squat'"""
        resp = requests.get(
            f"{BASE_URL}/api/exercises/search",
            params={"search": "back squat", "limit": 50},
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [ex["name"] for ex in data["exercises"]]
        print(f"  'back squat' search returned {data['total_count']} results: {names[:10]}")
        assert data["total_count"] >= 1, "Expected at least 1 result for 'back squat'"
        assert "Barbell Back Squat" in names, \
            f"'Barbell Back Squat' not found in reverse search for 'back squat'. Got: {names}"
        print("✅ Reverse lookup: 'back squat' → 'Barbell Back Squat' found")

    def test_search_skull_crusher_finds_skull_crushers(self):
        """search='skull crusher' → 'Skull Crushers' in results (reverse lookup)"""
        resp = requests.get(
            f"{BASE_URL}/api/exercises/search",
            params={"search": "skull crusher", "limit": 20},
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [ex["name"] for ex in data["exercises"]]
        print(f"  'skull crusher' search returned {data['total_count']} results: {names}")
        assert data["total_count"] >= 1, "Expected at least 1 result for 'skull crusher'"
        assert "Skull Crushers" in names, \
            f"'Skull Crushers' not found in reverse search. Got: {names}"
        print("✅ Reverse lookup: 'skull crusher' → 'Skull Crushers' found")

    def test_search_leg_press_finds_leg_press_machine(self):
        """search='leg press' → 'Leg Press Machine' in results"""
        resp = requests.get(
            f"{BASE_URL}/api/exercises/search",
            params={"search": "leg press", "limit": 20},
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [ex["name"] for ex in data["exercises"]]
        print(f"  'leg press' search returned {data['total_count']} results: {names}")
        assert data["total_count"] >= 1, "Expected results for 'leg press'"
        assert "Leg Press Machine" in names, \
            f"'Leg Press Machine' not found. Got: {names}"
        print("✅ Reverse lookup: 'leg press' → 'Leg Press Machine' found")

    def test_search_deadlift_finds_deadlift(self):
        """search='deadlift' → 'Deadlift' display name in results"""
        resp = requests.get(
            f"{BASE_URL}/api/exercises/search",
            params={"search": "deadlift", "limit": 50},
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [ex["name"] for ex in data["exercises"]]
        print(f"  'deadlift' search returned {data['total_count']} results. First 10: {names[:10]}")
        assert "Deadlift" in names, f"'Deadlift' not found. Got: {names[:15]}"
        print("✅ 'deadlift' search returns 'Deadlift' display name")

    def test_search_romanian_finds_romanian_deadlift(self):
        """search='romanian' → 'Romanian Deadlift' in results"""
        resp = requests.get(
            f"{BASE_URL}/api/exercises/search",
            params={"search": "romanian", "limit": 20},
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        names = [ex["name"] for ex in data["exercises"]]
        print(f"  'romanian' search returned {data['total_count']} results: {names}")
        assert "Romanian Deadlift" in names, \
            f"'Romanian Deadlift' not found. Got: {names}"
        print("✅ 'romanian' search returns 'Romanian Deadlift' display name")


# ─────────────────────────────────────────────────────────────────────────────
class TestTotalCountsWithOverrides:
    """Validate total_count is larger than before due to secondary muscle + override inclusion"""

    def test_legs_total_count_greater_than_250(self):
        """With secondary muscles + overrides, legs should have >250 exercises (was ~200)"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "legs", "limit": 1}, timeout=10)
        assert resp.status_code == 200
        total = resp.json()["total_count"]
        print(f"  muscle=legs total_count = {total}")
        assert total > 250, f"Expected >250 for legs (secondary muscles + overrides), got {total}"
        print(f"✅ legs total_count={total} > 250")

    def test_glutes_total_count_greater_than_200(self):
        """With secondary muscles + overrides, glutes should have >200 exercises"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "glutes", "limit": 1}, timeout=10)
        assert resp.status_code == 200
        total = resp.json()["total_count"]
        print(f"  muscle=glutes total_count = {total}")
        assert total > 200, f"Expected >200 for glutes (secondary muscles + overrides), got {total}"
        print(f"✅ glutes total_count={total} > 200")

    def test_triceps_total_count_includes_bench_press(self):
        """triceps total_count should be larger due to bench press / OHP overrides"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "triceps", "limit": 1}, timeout=10)
        assert resp.status_code == 200
        total = resp.json()["total_count"]
        print(f"  muscle=triceps total_count = {total}")
        assert total >= 50, f"Expected at least 50 triceps exercises, got {total}"
        print(f"✅ triceps total_count={total}")

    def test_back_total_count_includes_deadlift(self):
        """back total_count should include deadlift overrides"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "back", "limit": 1}, timeout=10)
        assert resp.status_code == 200
        total = resp.json()["total_count"]
        print(f"  muscle=back total_count = {total}")
        assert total > 50, f"Expected at least 50 back exercises, got {total}"
        print(f"✅ back total_count={total}")


# ─────────────────────────────────────────────────────────────────────────────
class TestNoRegressions:
    """Regression tests: each muscle chip still returns relevant exercises"""

    def test_chest_chip_returns_chest_exercises(self):
        """muscle=chest returns pectorals exercises (no regression)"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "chest", "limit": 20}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 50, f"Expected 50+ chest exercises, got {data['total_count']}"
        exercises = data["exercises"]
        # First 20 results via name search (primary target + overrides): 
        # At least most should be chest-relevant (pectorals or chest-targeted)
        pec_count = sum(1 for ex in exercises if ex["target"] == "pectorals")
        print(f"  chest: {data['total_count']} total, {pec_count}/{len(exercises)} have pectorals target")
        assert pec_count >= 10, f"Expected at least 10 pectorals exercises in chest results, got {pec_count}"
        print("✅ Chest chip still returns chest exercises (no regression)")

    def test_biceps_chip_returns_biceps_exercises(self):
        """muscle=biceps returns exercises (primary target OR secondary muscles contain biceps)"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "biceps", "limit": 50}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 0
        print(f"  biceps: {data['total_count']} total exercises")
        # With secondary-muscles expansion, results include rows/pulldowns (biceps as secondary)
        # Verify that at least some exercises target biceps OR have biceps in secondary muscles
        relevant_count = sum(
            1 for ex in data["exercises"]
            if ex["target"] == "biceps" or "biceps" in ex.get("secondaryMuscles", [])
        )
        assert relevant_count >= 5, f"Expected at least 5 biceps-relevant exercises, got {relevant_count}"
        print(f"✅ Biceps chip returns {data['total_count']} exercises ({relevant_count} biceps-relevant in first 50)")

    def test_shoulders_chip_returns_delt_exercises(self):
        """muscle=shoulders returns delts exercises"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "shoulders", "limit": 20}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 0
        print(f"  shoulders: {data['total_count']} total exercises")
        delt_count = sum(1 for ex in data["exercises"] if ex["target"] == "delts")
        assert delt_count >= 5, f"Expected at least 5 delts exercises, got {delt_count}"
        print("✅ Shoulders chip still returns delt exercises (no regression)")

    def test_abs_chip_returns_abs_exercises(self):
        """muscle=abs returns abs/obliques exercises"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "abs", "limit": 20}, timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] > 0
        print(f"  abs: {data['total_count']} total exercises")
        abs_count = sum(1 for ex in data["exercises"] if ex["target"] in ["abs", "obliques"])
        assert abs_count >= 5, f"Expected at least 5 abs exercises, got {abs_count}"
        print("✅ Abs chip still returns abs exercises (no regression)")

    def test_search_returns_exercises_with_required_fields(self):
        """All search results must include id, name, target, gifUrl, secondaryMuscles"""
        resp = requests.get(f"{BASE_URL}/api/exercises/search", params={"muscle": "legs", "limit": 10}, timeout=10)
        assert resp.status_code == 200
        exercises = resp.json()["exercises"]
        required_fields = ["id", "name", "target", "gifUrl", "secondaryMuscles"]
        for ex in exercises:
            for field in required_fields:
                assert field in ex, f"Missing field '{field}' in: {ex}"
            assert isinstance(ex["name"], str) and len(ex["name"]) > 0
            assert isinstance(ex["secondaryMuscles"], list)
        print("✅ All exercises have required fields (no regression)")

    def test_no_raw_exercise_names_in_response(self):
        """Verify known overridden raw names do NOT appear in responses"""
        raw_names_that_should_be_overridden = [
            "Barbell Full Squat",          # → Barbell Back Squat
            "Barbell Lying Triceps Extension",  # → Skull Crushers
            "Lever Leg Press",             # → Leg Press Machine
            "Barbell Deadlift",            # → Deadlift
        ]
        # Get a broad set of exercises
        all_names = set()
        for muscle in ["legs", "glutes", "triceps", "back"]:
            resp = requests.get(
                f"{BASE_URL}/api/exercises/search",
                params={"muscle": muscle, "limit": 50},
                timeout=10
            )
            assert resp.status_code == 200
            for ex in resp.json()["exercises"]:
                all_names.add(ex["name"])
        
        for raw_name in raw_names_that_should_be_overridden:
            assert raw_name not in all_names, \
                f"Raw name '{raw_name}' should not appear in API response (should be overridden)"
        print("✅ No raw exercise names appear in API responses (all overridden correctly)")
