"""
Backend test — Allergen-safety hardening (three proofs + one live end-to-end).

Proofs required by the review request:
  (a) Swap flow with allergies=['nuts']: attempt-1 meal contains 'almond milk',
      attempt-2 is clean → mocked call_claude_haiku is called >=2 times AND the
      returned meal has NO nut derivatives.
  (b) 'mushrooms' ban catches 'mushroom' (singular) and vice versa; and
      'gluten-free oats' does NOT trigger banned 'gluten'.
  (c) strip_banned_and_recompute removes the offending ingredient AND recomputes
      the meal's macros from the SUM of remaining ingredients' macros via
      calculate_ingredient_macros.

Plus a LIVE end-to-end sanity:
  POST /api/mealplans/generate with allergies=['nuts'] for the seeded test user
  → NO ingredient in any meal matches any expand_banned_terms(['nuts']) term.
"""

import os
import sys
import json
import uuid
import asyncio
from unittest.mock import AsyncMock

import pytest
import requests

# Make backend importable
sys.path.insert(0, "/app/backend")
import server  # noqa: E402  — importing runs load_dotenv + Mongo client setup

from server import (  # noqa: E402
    ALLERGEN_SYNONYMS,
    expand_banned_terms,
    contains_banned_food,
    strip_banned_and_recompute,
    calculate_ingredient_macros,
    AlternateMealRequest,
    generate_alternate_meal,
    db,
)

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get("EXPO_BACKEND_URL", "")).rstrip("/")
USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

GEN_TIMEOUT = 240  # LLM generation can take 20-60s+


# ────────────────────────────────────────────────────────────────────────────
# PROOF (b) — synonym expansion + word-stem matching + gluten-free protection
# ────────────────────────────────────────────────────────────────────────────
class TestProofB_StemMatching:
    """Word-stem matching (singular↔plural) & gluten-free false-positive protection."""

    def test_expand_banned_terms_nuts_includes_almond(self):
        expanded = expand_banned_terms(["nuts"])
        assert "almond" in expanded, f"expected 'almond' in expanded, got {expanded}"
        # sanity: also cashew/peanut/walnut and nut-milk phrases
        for s in ("cashew", "peanut", "walnut", "nut milk"):
            assert s in expanded, f"expected '{s}' in expanded, got {expanded}"

    def test_ban_plural_catches_singular(self):
        # ban 'mushrooms' (plural) → text has 'mushroom' (singular)
        assert contains_banned_food("200g mushroom, sliced", "mushrooms") is True

    def test_ban_singular_catches_plural(self):
        # ban 'mushroom' (singular) → text has 'mushrooms' (plural)
        assert contains_banned_food("200g mushrooms, sliced", "mushroom") is True

    def test_gluten_free_does_not_trigger_gluten(self):
        # 'gluten-free oats' must NOT trigger banned 'gluten'
        assert contains_banned_food("50g gluten-free oats", "gluten") is False
        # dashless variant too
        assert contains_banned_food("50g gluten free oats", "gluten") is False

    def test_almond_milk_matches_nut_expanded_term(self):
        # sanity for (a): expanded nuts includes 'almond' → catches 'almond milk'
        expanded = expand_banned_terms(["nuts"])
        assert any(contains_banned_food("112ml unsweetened almond milk", b) for b in expanded)


# ────────────────────────────────────────────────────────────────────────────
# PROOF (c) — strip removes offending ingredient AND recomputes meal macros
# ────────────────────────────────────────────────────────────────────────────
class TestProofC_StripAndRecompute:
    """strip_banned_and_recompute recomputes macros from remaining ingredients."""

    def test_almonds_stripped_and_macros_recomputed(self):
        meal = {
            "name": "Chicken & Rice with Almonds",
            "ingredients": ["150g chicken breast", "200g cooked white rice", "30g almonds"],
            "calories": 999,
            "protein": 999,
            "carbs": 999,
            "fats": 999,
        }
        banned = expand_banned_terms(["nuts"])
        removed = strip_banned_and_recompute(meal, banned)

        # 30g almonds must be the removed one; the other two must remain
        assert any("almond" in r.lower() for r in removed), f"almond not removed: {removed}"
        remaining_lower = [i.lower() for i in meal["ingredients"]]
        assert not any("almond" in i for i in remaining_lower), remaining_lower
        assert "150g chicken breast" in meal["ingredients"]
        assert "200g cooked white rice" in meal["ingredients"]

        # Macros must equal the SUM of remaining-ingredient macros (via
        # calculate_ingredient_macros), rounded the same way as the impl.
        expected_cal = 0.0
        expected_pro = 0.0
        expected_carb = 0.0
        expected_fat = 0.0
        for ing in meal["ingredients"]:
            m = calculate_ingredient_macros(ing)
            assert m is not None, f"calculate_ingredient_macros returned None for {ing!r}"
            expected_cal += m["calories"]
            expected_pro += m["protein"]
            expected_carb += m["carbs"]
            expected_fat += m["fats"]

        assert meal["calories"] == round(expected_cal), (meal["calories"], expected_cal)
        assert meal["protein"] == round(expected_pro, 1), (meal["protein"], expected_pro)
        assert meal["carbs"] == round(expected_carb, 1), (meal["carbs"], expected_carb)
        assert meal["fats"] == round(expected_fat, 1), (meal["fats"], expected_fat)
        # And the placeholder 999s must be gone
        assert meal["calories"] != 999


# ────────────────────────────────────────────────────────────────────────────
# PROOF (a) — swap-endpoint regeneration when attempt-1 includes almond milk
# ────────────────────────────────────────────────────────────────────────────
class TestProofA_SwapRegenerates:
    """Mock the LLM: attempt-1 returns almond milk, attempt-2 returns a clean
    nut-free meal. The endpoint logic must detect the banned food, regenerate,
    and return the clean meal — proving call_claude_haiku was invoked >=2×."""

    def _make_mock_llm(self):
        attempt1 = json.dumps({
            "id": "att1",
            "name": "Almond Milk Overnight Oats",
            "meal_type": "breakfast",
            "ingredients": ["50g oats", "112ml almond milk", "1 banana"],
            "instructions": "Combine and refrigerate overnight.",
            "calories": 350, "protein": 30, "carbs": 40, "fats": 8,
            "prep_time_minutes": 5,
        })
        attempt2 = json.dumps({
            "id": "att2",
            "name": "Greek Yogurt Berry Bowl",
            "meal_type": "breakfast",
            "ingredients": ["200g greek yogurt", "100g mixed berries", "20g honey"],
            "instructions": "Layer yogurt with berries and drizzle honey.",
            "calories": 340, "protein": 28, "carbs": 42, "fats": 6,
            "prep_time_minutes": 3,
        })
        # AsyncMock so `await call_claude_haiku(...)` returns these in sequence.
        mock = AsyncMock(side_effect=[attempt1, attempt2, attempt2])
        return mock

    def test_swap_regenerates_when_attempt1_has_almond_milk(self, monkeypatch):
        # 1) Seed a temporary meal-plan doc so the endpoint can find it.
        plan_id = f"TEST_{uuid.uuid4()}"
        seed_meal = {
            "id": "orig",
            "name": "Original Breakfast",
            "meal_type": "breakfast",
            "ingredients": ["3 whole eggs", "50g oats"],
            "instructions": "Cook eggs and oats.",
            "calories": 350, "protein": 30, "carbs": 40, "fats": 8,
            "prep_time_minutes": 5,
        }
        seed_plan = {
            "id": plan_id,
            "user_id": USER_ID,
            "name": "TEST plan",
            "food_preferences": "balanced",
            "allergies": ["nuts"],
            "foods_to_avoid": "",
            "target_calories": 2288, "target_protein": 172, "target_carbs": 229, "target_fats": 76,
            "meal_days": [
                {
                    "day": "Monday", "day_number": 1,
                    "meals": [seed_meal],
                    "total_calories": 350, "total_protein": 30, "total_carbs": 40, "total_fats": 8,
                }
            ],
        }

        async def _run():
            await db.mealplans.insert_one(seed_plan)
            try:
                mock_llm = self._make_mock_llm()
                monkeypatch.setattr(server, "call_claude_haiku", mock_llm)
                req = AlternateMealRequest(
                    user_id=USER_ID,
                    meal_plan_id=plan_id,
                    day_index=0,
                    meal_index=0,
                    swap_preference="similar",
                )
                result = await generate_alternate_meal(req)
                return result, mock_llm.call_count
            finally:
                await db.mealplans.delete_one({"id": plan_id})

        result, call_count = asyncio.run(_run())

        # ── Assertions ─────────────────────────────────────────────────────
        # (i) mock was called at least twice → regeneration happened
        assert call_count >= 2, f"expected regeneration (>=2 LLM calls), got {call_count}"

        alt = result["alternate_meal"]
        # (ii) returned meal is the clean one (name should NOT contain 'almond')
        assert "almond" not in alt.get("name", "").lower(), alt["name"]

        # (iii) no nut derivative appears anywhere in the returned meal
        expanded = expand_banned_terms(["nuts"])
        combined = f"{alt.get('name','')} {' '.join(alt.get('ingredients', []))} {alt.get('instructions','')}"
        hits = [b for b in expanded if contains_banned_food(combined, b)]
        assert not hits, f"nut derivatives still present in swap result: {hits} → {combined!r}"


# ────────────────────────────────────────────────────────────────────────────
# LIVE E2E sanity — real /api/mealplans/generate with allergies=['nuts']
# ────────────────────────────────────────────────────────────────────────────
class TestLiveNutAllergyGeneration:
    """Hits the real endpoint. Slow (LLM 20-60s). Asserts no nut derivatives."""

    def test_live_generate_no_nut_derivatives(self):
        assert BASE_URL, "EXPO_PUBLIC_BACKEND_URL / EXPO_BACKEND_URL must be set"
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})

        # sanity: profile exists
        r = s.get(f"{BASE_URL}/api/profile/{USER_ID}", timeout=15)
        assert r.status_code == 200, f"profile fetch failed: {r.status_code} {r.text[:200]}"

        payload = {
            "user_id": USER_ID,
            "food_preferences": "balanced",
            "preferred_foods": None,
            "foods_to_avoid": None,
            "supplements": [],
            "supplements_custom": None,
            "allergies": ["nuts"],
        }
        r = s.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=GEN_TIMEOUT)
        assert r.status_code == 200, f"generate failed: {r.status_code} {r.text[:400]}"
        plan = r.json()

        expanded = expand_banned_terms(["nuts"])
        print(f"[live] expanded banned terms for 'nuts': {expanded}")

        # Review request contract: NO ingredient in any meal matches any expanded nut term.
        ingredient_offenders = []  # (day, meal, ingredient, matched-term)
        # Informational only: leaks in meal name / instructions (not part of the pass/fail
        # contract, but printed so the main agent can decide whether to harden further).
        meta_leaks = []
        for day in plan.get("meal_days", []):
            day_name = day.get("day", "?")
            for meal in day.get("meals", []):
                name = meal.get("name", "")
                ingredients = meal.get("ingredients", []) or []
                for ing in ingredients:
                    for b in expanded:
                        if contains_banned_food(str(ing), b):
                            ingredient_offenders.append((day_name, name, ing, b))
                combined_meta = f"{name} {meal.get('instructions','')}"
                for b in expanded:
                    if contains_banned_food(combined_meta, b):
                        meta_leaks.append((day_name, name, b))

        n_meals = sum(len(d.get("meals", [])) for d in plan.get("meal_days", []))
        if meta_leaks:
            print(
                f"[live] ⚠ INFO — name/instructions still mention nut terms in "
                f"{len(meta_leaks)} meals (ingredients are clean; not a test failure):"
            )
            for d, n, b in meta_leaks:
                print(f"    {d} · {n} → mentions '{b}'")

        assert not ingredient_offenders, (
            "nut derivatives found in generated plan ingredients:\n"
            + "\n".join(f"  {d} · {n} · {i} → matched '{b}'" for d, n, i, b in ingredient_offenders)
        )
        print(f"[live] plan_id={plan.get('id')} — {n_meals} meals, zero nut hits in ingredients ✅")
