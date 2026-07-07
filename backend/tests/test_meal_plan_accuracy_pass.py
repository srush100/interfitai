"""
Meal Plan Accuracy Pass — Backend Tests
Tests for:
  - Change 3: POST /api/mealplan/alternate returns day_totals, enforces ±10% calorie tolerance
  - Change 1 (Proof 2): POST /api/mealplans/generate honours calorie_adjustment in target_calories
"""

import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# ─────────────────────────────────────────────────────────────────────────────
# Shared session fixture
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Helper: ensure user profile exists (creates if absent)
# ─────────────────────────────────────────────────────────────────────────────
def ensure_profile(session):
    """GET profile; if 404 create a fresh test profile."""
    r = session.get(f"{BASE_URL}/api/profile/{USER_ID}")
    if r.status_code == 200:
        profile = r.json()
        print(f"[profile] existing profile found — goal={profile.get('goal')}, "
              f"calculated_macros={profile.get('calculated_macros')}, "
              f"calorie_adjustment={profile.get('calorie_adjustment')}")
        return profile
    # Create a new profile
    print("[profile] not found — creating test profile …")
    payload = {
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "testpassword123",
        "weight": 80,
        "height": 178,
        "age": 30,
        "gender": "male",
        "activity_level": "moderately_active",
        "goal": "build_muscle",
    }
    cr = session.post(f"{BASE_URL}/api/profile", json=payload)
    assert cr.status_code in (200, 201), f"Profile creation failed: {cr.text}"
    created = cr.json()
    print(f"[profile] created user_id={created.get('id') or created.get('user_id')}")
    # Re-fetch to get calculated_macros
    gr = session.get(f"{BASE_URL}/api/profile/{USER_ID}")
    assert gr.status_code == 200, f"Profile re-fetch failed: {gr.text}"
    return gr.json()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: get or generate a meal plan for the test user
# ─────────────────────────────────────────────────────────────────────────────
def get_or_generate_plan(session):
    """Return an existing meal plan or generate a new one."""
    r = session.get(f"{BASE_URL}/api/mealplans/{USER_ID}")
    if r.status_code == 200:
        plans = r.json()
        if plans:
            plan = plans[0] if isinstance(plans, list) else plans
            print(f"[plan] using existing plan id={plan.get('id')}, "
                  f"target_calories={plan.get('target_calories')}, "
                  f"days={len(plan.get('meal_days', []))}")
            return plan
    # Generate a fresh plan
    print("[plan] no existing plan — generating …")
    gen_r = session.post(f"{BASE_URL}/api/mealplans/generate", json={
        "user_id": USER_ID,
        "food_preferences": "balanced",
        "preferred_foods": None,
        "foods_to_avoid": None,
        "supplements": [],
        "allergies": [],
    })
    assert gen_r.status_code == 200, f"Plan generation failed ({gen_r.status_code}): {gen_r.text[:500]}"
    plan = gen_r.json()
    print(f"[plan] generated plan id={plan.get('id')}, "
          f"target_calories={plan.get('target_calories')}, "
          f"days={len(plan.get('meal_days', []))}")
    return plan


# ─────────────────────────────────────────────────────────────────────────────
# CLASS 1 — PROOF 1: POST /api/mealplan/alternate
# ─────────────────────────────────────────────────────────────────────────────
class TestAlternateMealProof1:
    """
    PROOF 1: POST /api/mealplan/alternate with swap_preference='similar'
    - Response MUST contain top-level 'day_totals' field
    - day_totals must have keys: total_calories, total_protein, total_carbs, total_fats
    - alternate_meal calories must be within ±10% of the replaced meal's original calories
    """

    def test_profile_exists(self, session):
        """Ensure the test user profile exists before running meal plan tests."""
        profile = ensure_profile(session)
        assert profile is not None, "Profile could not be fetched or created"
        assert profile.get("calculated_macros") is not None, \
            "Profile is missing calculated_macros — cannot proceed"
        print(f"[test_profile_exists] PASS — macros={profile['calculated_macros']}")

    def test_alternate_meal_has_day_totals(self, session):
        """Full end-to-end proof: alternate returns day_totals."""
        ensure_profile(session)
        plan = get_or_generate_plan(session)
        plan_id = plan["id"]

        # Pick day_index=0, meal_index=1 per spec
        meal_days = plan.get("meal_days", [])
        assert len(meal_days) > 0, "Plan has no meal_days"
        day0 = meal_days[0]
        meals0 = day0.get("meals", [])
        assert len(meals0) > 1, f"Day 0 has fewer than 2 meals (got {len(meals0)})"
        original_meal = meals0[1]
        original_cal = original_meal.get("calories", 0)
        print(f"\n[alternate] original meal: '{original_meal.get('name')}' "
              f"— calories={original_cal}, protein={original_meal.get('protein')}g, "
              f"carbs={original_meal.get('carbs')}g, fats={original_meal.get('fats')}g")

        # POST alternate
        payload = {
            "user_id": USER_ID,
            "meal_plan_id": plan_id,
            "day_index": 0,
            "meal_index": 1,
            "swap_preference": "similar",
        }
        r = session.post(f"{BASE_URL}/api/mealplan/alternate", json=payload)

        # Print full JSON response for proof
        print(f"\n===== FULL JSON RESPONSE from POST /api/mealplan/alternate =====")
        try:
            resp_json = r.json()
            print(json.dumps(resp_json, indent=2))
        except Exception:
            print(f"Raw: {r.text[:2000]}")
            resp_json = {}
        print(f"=================================================================\n")

        assert r.status_code == 200, f"Alternate meal returned {r.status_code}: {r.text[:500]}"

        # PROOF 1a: 'day_totals' field exists at top level
        assert "day_totals" in resp_json, \
            f"FAIL: 'day_totals' key missing from response. Got keys: {list(resp_json.keys())}"
        print("[PROOF 1a] PASS — 'day_totals' field present in response")

        # PROOF 1b: day_totals has all required sub-keys
        day_totals = resp_json["day_totals"]
        for key in ("total_calories", "total_protein", "total_carbs", "total_fats"):
            assert key in day_totals, \
                f"FAIL: '{key}' missing from day_totals. Got: {day_totals}"
        print(f"[PROOF 1b] PASS — day_totals keys all present: {list(day_totals.keys())}")
        print(f"           day_totals = {day_totals}")

        # PROOF 1c: alternate_meal calories within ±10% of original
        assert "alternate_meal" in resp_json, \
            f"FAIL: 'alternate_meal' key missing from response"
        alt_meal = resp_json["alternate_meal"]
        alt_cal = float(alt_meal.get("calories", 0))
        print(f"[PROOF 1c] alternate_meal: '{alt_meal.get('name')}' — calories={alt_cal}")
        print(f"           original calories={original_cal}, 10% tolerance=[{original_cal * 0.9:.1f}, {original_cal * 1.1:.1f}]")

        if original_cal > 0:
            tolerance = original_cal * 0.10
            diff = abs(alt_cal - original_cal)
            pct_diff = (diff / original_cal) * 100
            within_tolerance = diff <= tolerance
            print(f"           diff={diff:.1f} cal ({pct_diff:.1f}%), within ±10%: {within_tolerance}")
            assert within_tolerance, (
                f"FAIL: alternate_meal calories {alt_cal} is NOT within ±10% of "
                f"original {original_cal} (diff={diff:.1f}, tolerance={tolerance:.1f})"
            )
            print(f"[PROOF 1c] PASS — alternate_meal calories within ±10% tolerance")
        else:
            print("[PROOF 1c] SKIP — original_cal is 0, skipping tolerance check")

    def test_day_totals_values_are_numeric(self, session):
        """Sanity-check that all day_totals values are non-negative numbers."""
        ensure_profile(session)
        plan = get_or_generate_plan(session)
        meals0 = plan.get("meal_days", [{}])[0].get("meals", [])
        if len(meals0) < 2:
            pytest.skip("Not enough meals in day 0 to run alternate test")

        payload = {
            "user_id": USER_ID,
            "meal_plan_id": plan["id"],
            "day_index": 0,
            "meal_index": 1,
            "swap_preference": "similar",
        }
        r = session.post(f"{BASE_URL}/api/mealplan/alternate", json=payload)
        assert r.status_code == 200
        resp = r.json()

        day_totals = resp.get("day_totals", {})
        for key in ("total_calories", "total_protein", "total_carbs", "total_fats"):
            val = day_totals.get(key)
            assert val is not None, f"day_totals['{key}'] is None"
            assert isinstance(val, (int, float)), f"day_totals['{key}'] = {val!r} is not numeric"
            assert val >= 0, f"day_totals['{key}'] = {val} is negative"
        print(f"[test_day_totals_values_are_numeric] PASS — {day_totals}")


# ─────────────────────────────────────────────────────────────────────────────
# CLASS 2 — PROOF 2: calorie_adjustment honoured in plan generation
# ─────────────────────────────────────────────────────────────────────────────
class TestCalorieAdjustmentProof2:
    """
    PROOF 2: POST /api/mealplans/generate honours calorie_adjustment.
    - GET profile → note base calculated_macros.calories
    - PUT profile with calorie_adjustment=300
    - POST generate → plan.target_calories must equal base_calories + 300
    """

    def test_calorie_adjustment_honoured_in_plan(self, session):
        """End-to-end proof that calorie_adjustment is added to target_calories."""
        # Step 1: Get current profile & base calories
        profile = ensure_profile(session)
        macros = profile.get("calculated_macros", {})
        assert macros, "Profile has no calculated_macros"
        base_cal = macros.get("calories", 0)
        assert base_cal > 0, f"base calculated_macros.calories is {base_cal}"
        original_adj = profile.get("calorie_adjustment", 0)
        print(f"\n[proof2] base calculated_macros.calories = {base_cal}")
        print(f"[proof2] current calorie_adjustment = {original_adj}")

        # Step 2: Set calorie_adjustment=300
        adj = 300
        put_r = session.put(
            f"{BASE_URL}/api/profile/{USER_ID}",
            json={"calorie_adjustment": adj},
        )
        assert put_r.status_code == 200, \
            f"PUT /api/profile/{USER_ID} failed ({put_r.status_code}): {put_r.text[:500]}"
        updated = put_r.json()
        actual_adj = updated.get("calorie_adjustment", None)
        print(f"[proof2] PUT profile — calorie_adjustment set to: {actual_adj}")
        assert actual_adj == adj, \
            f"Profile calorie_adjustment not saved correctly: expected {adj}, got {actual_adj}"

        # Verify it persisted with a GET
        gr = session.get(f"{BASE_URL}/api/profile/{USER_ID}")
        assert gr.status_code == 200
        saved_profile = gr.json()
        saved_adj = saved_profile.get("calorie_adjustment", None)
        saved_macros = saved_profile.get("calculated_macros", {})
        saved_base_cal = saved_macros.get("calories", base_cal)
        print(f"[proof2] GET profile — calorie_adjustment={saved_adj}, "
              f"calculated_macros.calories={saved_base_cal}")
        assert saved_adj == adj, \
            f"calorie_adjustment not persisted: expected {adj}, got {saved_adj}"

        # Step 3: Generate meal plan
        print("[proof2] generating meal plan …")
        gen_r = session.post(f"{BASE_URL}/api/mealplans/generate", json={
            "user_id": USER_ID,
            "food_preferences": "balanced",
            "preferred_foods": None,
            "foods_to_avoid": None,
            "supplements": [],
            "allergies": [],
        })

        print(f"\n===== POST /api/mealplans/generate response (status={gen_r.status_code}) =====")
        try:
            plan_json = gen_r.json()
            # Print compact view of key fields (avoid full meal dump)
            summary = {
                "id": plan_json.get("id"),
                "target_calories": plan_json.get("target_calories"),
                "target_protein": plan_json.get("target_protein"),
                "target_carbs": plan_json.get("target_carbs"),
                "target_fats": plan_json.get("target_fats"),
                "days_count": len(plan_json.get("meal_days", [])),
            }
            print(json.dumps(summary, indent=2))
        except Exception:
            print(f"Raw: {gen_r.text[:1000]}")
            plan_json = {}
        print(f"===============================================================================\n")

        assert gen_r.status_code == 200, \
            f"Plan generation failed ({gen_r.status_code}): {gen_r.text[:500]}"

        plan_target_cal = plan_json.get("target_calories")
        expected_cal = saved_base_cal + adj

        print(f"[proof2] profile base calories: {saved_base_cal}")
        print(f"[proof2] calorie_adjustment:    +{adj}")
        print(f"[proof2] expected target_cal:   {expected_cal}")
        print(f"[proof2] plan target_calories:  {plan_target_cal}")

        assert plan_target_cal is not None, "plan.target_calories is None"
        assert plan_target_cal == expected_cal, (
            f"FAIL: plan.target_calories={plan_target_cal} != "
            f"base_calories({saved_base_cal}) + adjustment({adj}) = {expected_cal}"
        )
        print(f"\n✅ PROOF 2 PASS: plan.target_calories ({plan_target_cal}) == "
              f"base_calories ({saved_base_cal}) + 300 = {expected_cal}")

    def test_calorie_adjustment_zero_baseline(self, session):
        """Reset calorie_adjustment to 0 and confirm plan uses base calories exactly."""
        profile = ensure_profile(session)
        macros = profile.get("calculated_macros", {})
        base_cal = macros.get("calories", 0)
        if base_cal <= 0:
            pytest.skip("base_cal is 0, cannot test baseline")

        # Reset adjustment to 0
        put_r = session.put(
            f"{BASE_URL}/api/profile/{USER_ID}",
            json={"calorie_adjustment": 0},
        )
        assert put_r.status_code == 200

        gen_r = session.post(f"{BASE_URL}/api/mealplans/generate", json={
            "user_id": USER_ID,
            "food_preferences": "balanced",
            "preferred_foods": None,
            "foods_to_avoid": None,
            "supplements": [],
            "allergies": [],
        })
        assert gen_r.status_code == 200, f"Plan gen failed: {gen_r.text[:300]}"
        plan = gen_r.json()
        target_cal = plan.get("target_calories")
        print(f"[zero_baseline] plan.target_calories={target_cal}, base_cal={base_cal}")
        assert target_cal == base_cal, (
            f"FAIL: with adj=0, plan.target_calories={target_cal} should equal base_cal={base_cal}"
        )
        print(f"[test_calorie_adjustment_zero_baseline] PASS — target_calories={target_cal} == base_cal={base_cal}")
