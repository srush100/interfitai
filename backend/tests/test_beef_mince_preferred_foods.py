"""
Backend test — Beef mince preferred foods override + cooked weights rule.

Verifies:
  A. beef mince appears in AT LEAST one meal on EVERY day of the plan.
  B. beef-mince meal macros are consistent with extra-lean values
     (~25g protein / ~6g fat per 100g) — fat should NOT be ~17g per 100g.
  C. Each day's meal totals ≈ its meals' sum (±5 tolerance per macro).
  D. Eggs and rice appear somewhere in the plan.
"""

import os
import re
import json
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL", "")
BASE_URL = BASE_URL.rstrip("/")
USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

GEN_TIMEOUT = 180  # LLM meal-plan generation can take 20-60s+


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def profile(session):
    """Ensure profile exists; create if missing."""
    r = session.get(f"{BASE_URL}/api/profile/{USER_ID}")
    if r.status_code == 200:
        p = r.json()
        print(f"[profile] found, goal={p.get('goal')}, macros={p.get('calculated_macros')}")
        # Reset any adjustment
        session.put(f"{BASE_URL}/api/profile/{USER_ID}", json={"calorie_adjustment": 0})
        return p
    # Create profile with realistic muscle-gain stats
    payload = {
        "id": USER_ID,
        "user_id": USER_ID,
        "name": "Test User",
        "email": "testuser@example.com",
        "password": "testpassword123",
        "weight": 80,
        "height": 180,
        "age": 30,
        "gender": "male",
        "activity_level": "moderately_active",
        "goal": "build_muscle",
    }
    cr = session.post(f"{BASE_URL}/api/profile", json=payload)
    assert cr.status_code in (200, 201), f"Profile create failed: {cr.status_code} {cr.text[:400]}"
    gr = session.get(f"{BASE_URL}/api/profile/{USER_ID}")
    assert gr.status_code == 200, f"Profile refetch failed: {gr.text[:400]}"
    return gr.json()


@pytest.fixture(scope="module")
def generated_plan(session, profile):
    """Generate a fresh plan honouring the preferred-foods override."""
    payload = {
        "user_id": USER_ID,
        "food_preferences": "whole_foods",
        "preferred_foods": "extra lean beef mince, eggs, rice",
        "foods_to_avoid": "",
        "supplements": [],
        "allergies": [],
    }
    print(f"[gen] POST /api/mealplans/generate — payload={payload}")
    r = session.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=GEN_TIMEOUT)
    print(f"[gen] status={r.status_code}")
    assert r.status_code == 200, f"Generate failed ({r.status_code}): {r.text[:600]}"
    plan = r.json()
    print(f"[gen] plan.id={plan.get('id')} days={len(plan.get('meal_days', []))} target_cal={plan.get('target_calories')}")
    return plan


# ────────────────────────────────────────────────────────────────
# Helper: search ingredient list for a keyword
# ────────────────────────────────────────────────────────────────
def ingredients_contain(meal, keyword):
    kw = keyword.lower()
    for ing in meal.get("ingredients", []) or []:
        if isinstance(ing, str) and kw in ing.lower():
            return True
        if isinstance(ing, dict):
            for v in ing.values():
                if isinstance(v, str) and kw in v.lower():
                    return True
    if kw in (meal.get("name") or "").lower():
        return True
    if kw in (meal.get("instructions") or "").lower():
        return True
    return False


def parse_grams(ingredient_text):
    """Extract first gram amount from an ingredient string like '150g extra lean beef mince'."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*g\b", ingredient_text)
    return float(m.group(1)) if m else None


# ────────────────────────────────────────────────────────────────
# TEST A: beef mince on every day
# ────────────────────────────────────────────────────────────────
def test_beef_mince_present_on_every_day(generated_plan):
    days = generated_plan.get("meal_days", [])
    assert len(days) >= 1, "No meal_days in plan"

    per_day_hits = []
    for idx, day in enumerate(days):
        meals = day.get("meals", [])
        hits = [m for m in meals if (
            ingredients_contain(m, "beef mince") or
            ingredients_contain(m, "ground beef") or
            ingredients_contain(m, "beef") and "mince" in json.dumps(m).lower()
        )]
        per_day_hits.append((day.get("day", f"Day {idx+1}"), len(hits), [m.get("name") for m in hits]))
        print(f"[day {idx+1}] '{day.get('day')}' — beef mince meals: {[m.get('name') for m in hits]}")

    days_without = [d for d, n, _ in per_day_hits if n == 0]
    assert not days_without, f"Beef mince missing on days: {days_without}. Details: {per_day_hits}"
    print(f"[TEST A] PASS — beef mince present on all {len(days)} days")


# ────────────────────────────────────────────────────────────────
# TEST B: extra-lean beef mince macros are consistent
# ────────────────────────────────────────────────────────────────
def test_beef_mince_meals_use_extra_lean_macros(generated_plan):
    """For meals containing extra lean beef mince, check fat is NOT ~17g/100g (regular).
    Extra-lean should be ~6g fat / 100g. We accept fat/protein ratio ≤ 0.5 for extra-lean.
    """
    days = generated_plan.get("meal_days", [])
    checked = 0
    problems = []
    for day in days:
        for meal in day.get("meals", []):
            has_extra_lean = False
            grams_beef = None
            for ing in meal.get("ingredients", []) or []:
                s = ing if isinstance(ing, str) else json.dumps(ing)
                sl = s.lower()
                if ("extra lean beef mince" in sl) or ("extra-lean beef mince" in sl) or ("5% beef mince" in sl) or ("5% mince" in sl):
                    has_extra_lean = True
                    g = parse_grams(s)
                    if g is not None:
                        grams_beef = g
                    break
            if not has_extra_lean:
                continue
            checked += 1
            protein = float(meal.get("protein", 0))
            fat = float(meal.get("fats", 0))
            if protein <= 0:
                continue
            # ratio for extra-lean 5%: 6/25 = 0.24. Regular 20% mince: 17/26 = 0.65
            ratio = fat / protein if protein > 0 else 999
            print(f"[beef-meal] '{meal.get('name')}' — protein={protein}g, fat={fat}g, ratio={ratio:.2f}, grams_beef={grams_beef}")
            # Accept meals up to 0.55 ratio (accounts for added oil/other fatty ingredients)
            # But if meal is pure beef+carb, fat/protein should be low
            if ratio > 0.60:
                problems.append({
                    "meal": meal.get("name"),
                    "protein": protein,
                    "fat": fat,
                    "ratio": round(ratio, 2),
                    "note": "fat/protein ratio too high — smells like regular 20% mince, not extra-lean 5%",
                })
    print(f"[TEST B] checked {checked} extra-lean beef meals; problems={len(problems)}")
    for p in problems:
        print(f"  ⚠ {p}")
    if checked == 0:
        pytest.skip("No meal explicitly listed 'extra lean beef mince' by name — cannot verify macros")
    assert not problems, f"Extra-lean beef mince meals had implausible macros: {problems}"


# ────────────────────────────────────────────────────────────────
# TEST C: day totals ≈ sum of meals
# ────────────────────────────────────────────────────────────────
def test_day_totals_match_meal_sums(generated_plan):
    days = generated_plan.get("meal_days", [])
    tolerance = 5.0
    issues = []
    for i, day in enumerate(days):
        sum_cal = sum(float(m.get("calories", 0)) for m in day.get("meals", []))
        sum_p = sum(float(m.get("protein", 0)) for m in day.get("meals", []))
        sum_c = sum(float(m.get("carbs", 0)) for m in day.get("meals", []))
        sum_f = sum(float(m.get("fats", 0)) for m in day.get("meals", []))
        dc = float(day.get("total_calories", 0))
        dp = float(day.get("total_protein", 0))
        dcarb = float(day.get("total_carbs", 0))
        df = float(day.get("total_fats", 0))
        print(f"[day {i+1}] day_totals=({dc},{dp},{dcarb},{df}) vs meal_sums=({sum_cal},{sum_p},{sum_c},{sum_f})")
        if abs(dc - sum_cal) > tolerance:
            issues.append(f"day{i+1} calories diff={dc-sum_cal}")
        if abs(dp - sum_p) > tolerance:
            issues.append(f"day{i+1} protein diff={dp-sum_p}")
        if abs(dcarb - sum_c) > tolerance:
            issues.append(f"day{i+1} carbs diff={dcarb-sum_c}")
        if abs(df - sum_f) > tolerance:
            issues.append(f"day{i+1} fats diff={df-sum_f}")
    assert not issues, f"Day totals don't match meal sums: {issues}"
    print(f"[TEST C] PASS — all {len(days)} days have consistent totals (±{tolerance})")


# ────────────────────────────────────────────────────────────────
# TEST D: eggs and rice also appear (Backend test 2)
# ────────────────────────────────────────────────────────────────
def test_eggs_and_rice_appear_in_plan(generated_plan):
    days = generated_plan.get("meal_days", [])
    all_ingredients_text = ""
    for day in days:
        for meal in day.get("meals", []):
            all_ingredients_text += " ".join(str(i) for i in (meal.get("ingredients") or []))
            all_ingredients_text += " " + (meal.get("name") or "")
    text = all_ingredients_text.lower()
    has_eggs = ("egg" in text)
    has_rice = ("rice" in text)
    print(f"[TEST D] eggs found={has_eggs}, rice found={has_rice}")
    assert has_eggs, "'eggs' preferred food not present anywhere in generated plan"
    assert has_rice, "'rice' preferred food not present anywhere in generated plan"
