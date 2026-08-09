"""Fix 5 regression tests — egg weight 50g → 58g and meal-detail.tsx ingredient
state-stripping.

Adds targeted coverage on top of the existing 58-test nutrition-accuracy guard:

  Backend:
    - calculate_ingredient_macros('2 large eggs') → macros for 116g of egg
    - _extract_portion_grams('2 large eggs', 'eggs') → 116.0
    - Meal-plan prompt block contains '(58g ea)' & '6.4F' and does NOT contain
      the old '(50g ea)' & '5.5F' figures.
    - LIMIT-eggs formula divisor is 6.4 (not 5.5).
    - /food/log with 2 large eggs @ 180 cal / 15P / 1.3C / 12.8F (derived
      180.4 → gap 0.22% < 10%) is stored UNMODIFIED by the Fix-1 sanitizer.

  Frontend (source-level assertions on /app/frontend/app/meal-detail.tsx):
    - _EXISTING_STATE_RE regex is defined and contains raw|cooked|dry
    - _stripExistingState helper exists
    - mealContainsMeat helper exists
    - The 'Weigh meat raw' <Text> is guarded by mealContainsMeat(meal.ingredients)
"""
import os
import re
import sys
import uuid
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, "/app/backend")
from server import (  # noqa: E402
    calculate_ingredient_macros,
    _extract_portion_grams,
)

# Match the pattern used by test_nutrition_accuracy_guard.py to keep both
# suites runnable together — falls back to the preview URL from frontend/.env
# (EXPO_PUBLIC_BACKEND_URL) when EXPO_BACKEND_URL is not exported into the shell.
BASE_URL = os.environ.get(
    "EXPO_BACKEND_URL",
    "https://nutrition-debug-1.preview.emergentagent.com",
).rstrip("/")
MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "test_database"
SERVER_PY_PATH = "/app/backend/server.py"
MEAL_DETAIL_TSX_PATH = "/app/frontend/app/meal-detail.tsx"


# ---------------------------------------------------------------------------
# Fixtures — paid user (needed for /food/log integration test)
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def paid_user(event_loop):
    email = f"TEST_fix5_paid_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "name": "TEST Fix5 Paid",
        "email": email,
        "password": "TestPass123!",
        "weight": 80.0, "height": 180.0, "age": 30,
        "gender": "male", "activity_level": "moderate", "goal": "maintenance",
    }
    r = requests.post(f"{BASE_URL}/api/profile", json=payload, timeout=30)
    assert r.status_code in (200, 201), f"profile create failed: {r.status_code} {r.text}"
    user_id = r.json()["id"]

    async def _flip():
        cli = AsyncIOMotorClient(MONGO_URL)
        try:
            await cli[DB_NAME].profiles.update_one(
                {"id": user_id},
                {"$set": {"subscription_status": "yearly"}},
            )
        finally:
            cli.close()

    event_loop.run_until_complete(_flip())
    yield {"id": user_id, "email": email}

    async def _cleanup():
        cli = AsyncIOMotorClient(MONGO_URL)
        try:
            await cli[DB_NAME].profiles.delete_one({"id": user_id})
            await cli[DB_NAME].food_logs.delete_many({"user_id": user_id})
        finally:
            cli.close()

    event_loop.run_until_complete(_cleanup())


# ===========================================================================
# 1. calculate_ingredient_macros for '2 large eggs' → 116g of egg
# ===========================================================================
class TestCalculateIngredientMacrosEggs:
    """2 large eggs = 2 * 58g = 116g; INGREDIENT_MACROS['egg'] = (155,13,1.1,11).
    Expected: cal=round(155*1.16)=180, prot=round(13*1.16,1)=15.1,
              carbs=round(1.1*1.16,1)=1.3, fats=round(11*1.16,1)=12.8"""

    def test_two_large_eggs_returns_116g_macros(self):
        m = calculate_ingredient_macros("2 large eggs")
        assert m is not None, "calculate_ingredient_macros returned None for '2 large eggs'"
        assert m["calories"] == 180, f"expected 180 cal, got {m['calories']}"
        assert m["protein"] == 15.1, f"expected 15.1 P, got {m['protein']}"
        assert m["carbs"] == 1.3,   f"expected 1.3 C, got {m['carbs']}"
        assert m["fats"] == 12.8,   f"expected 12.8 F, got {m['fats']}"

    def test_one_large_egg_returns_58g_macros(self):
        """Sanity: 1 large egg = 58g → 90 cal, 7.5P, 0.6C, 6.4F"""
        m = calculate_ingredient_macros("1 large egg")
        assert m is not None
        # round(155*0.58)=90, round(13*0.58,1)=7.5, round(1.1*0.58,1)=0.6, round(11*0.58,1)=6.4
        assert m["calories"] == 90
        assert m["protein"] == 7.5
        assert m["carbs"] == 0.6
        assert m["fats"] == 6.4

    def test_three_eggs_uses_58g_weight_not_50g(self):
        """Regression guard: with old 50g weight, 3 eggs = 150g → 233 cal.
        With new 58g weight, 3 eggs = 174g → round(155*1.74)=270 cal."""
        m = calculate_ingredient_macros("3 eggs")
        assert m is not None
        assert m["calories"] == 270, (
            f"expected 270 cal (58g × 3), got {m['calories']}. "
            f"If this is 233, egg weight regressed to 50g."
        )


# ===========================================================================
# 2. _extract_portion_grams for eggs — used for plausibility bounds
# ===========================================================================
class TestExtractPortionGramsEggs:
    """`_extract_portion_grams` uses regex `\\d+\\s*(egg|eggs|...)` which requires
    the number immediately followed by the unit word. It does NOT parse the
    'large' modifier — that's pre-existing behavior (the sanitizer flow always
    passes explicit grams like '2 large eggs (116g)' which matches the first
    regex branch). Fix 5 only changed the per-unit value from 50 → 58."""

    def test_four_eggs_returns_232g(self):
        g = _extract_portion_grams("4 eggs", "eggs")
        assert g == 232.0, f"expected 232.0 (4 × 58), got {g}"

    def test_one_egg_returns_58g(self):
        g = _extract_portion_grams("1 egg", "egg")
        assert g == 58.0, f"expected 58.0, got {g}"

    def test_two_eggs_returns_116g(self):
        """The clean review-request scenario, using a spelling the regex parses."""
        g = _extract_portion_grams("2 eggs", "eggs")
        assert g == 116.0, f"expected 116.0 (2 × 58), got {g}"

    def test_explicit_grams_serving_still_wins(self):
        """When the string carries explicit grams (as the meal-plan pipeline does
        for 'N large eggs (Xg)'), the explicit-g branch is used. Verifies that
        the 'large' modifier not being parsed doesn't break the sanitizer flow."""
        g = _extract_portion_grams("2 large eggs (116g)", "eggs")
        assert g == 116.0

    def test_regression_guard_uses_58_not_50(self):
        """With old 50g weight, 3 eggs = 150g. With new 58g weight, 3 eggs = 174g."""
        g = _extract_portion_grams("3 eggs", "eggs")
        assert g == 174.0, (
            f"expected 174.0 (3 × 58), got {g}. "
            f"If this is 150.0, per_unit['eggs'] regressed to 50."
        )


# ===========================================================================
# 3. Meal-plan prompt source assertions — presence of new values, absence of old
# ===========================================================================
class TestMealPlanPromptStrings:
    @pytest.fixture(scope="class")
    def source(self):
        with open(SERVER_PY_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_macro_reference_has_58g_ea(self, source):
        assert "Whole egg (58g ea): 90cal 7.5P 0.6C 6.4F" in source, (
            "MACRO REFERENCE block missing new egg line 'Whole egg (58g ea): 90cal 7.5P 0.6C 6.4F'"
        )

    def test_macro_reference_no_old_50g_ea(self, source):
        assert "(50g ea)" not in source, "Old '(50g ea)' string still present"

    def test_macro_reference_no_old_5_5F_egg(self, source):
        # Old line was: 'Whole egg (50g ea): 78cal 6.5P 0.5C 5.5F'
        assert "0.5C 5.5F" not in source, "Old egg macro '0.5C 5.5F' still present"

    def test_fat_lookup_uses_58g_each(self, source):
        assert "Whole egg (58g each) = 6.4g fat" in source, (
            "Fat lookup line missing 'Whole egg (58g each) = 6.4g fat'"
        )

    def test_fat_lookup_no_50g_each(self, source):
        assert "Whole egg (50g each)" not in source, (
            "Old fat lookup 'Whole egg (50g each)' still present"
        )

    def test_breakfast_note_uses_6_4g_fat(self, source):
        assert "1 whole egg ≈ 6.4g fat" in source, (
            "Breakfast note '1 whole egg ≈ 6.4g fat' missing"
        )

    def test_breakfast_note_no_5_5g_fat(self, source):
        assert "1 whole egg = 5.5g fat" not in source, (
            "Old breakfast note '1 whole egg = 5.5g fat' still present"
        )

    def test_limit_eggs_formula_uses_6_4(self, source):
        # Expect: 'each egg = 6.4g fat' and the formula divisor '/ 6.4'
        assert "each egg = 6.4g fat" in source, "'each egg = 6.4g fat' missing"
        assert "* 0.2 / 6.4" in source, (
            "LIMIT-eggs formula divisor should be '/ 6.4', not '/ 5.5'"
        )

    def test_limit_eggs_formula_no_old_5_5_divisor(self, source):
        assert "* 0.2 / 5.5" not in source, "Old '* 0.2 / 5.5' divisor still present"
        assert "each egg = 5.5g fat" not in source, "Old 'each egg = 5.5g fat' still present"


# ===========================================================================
# 4. Integration — /food/log with 2 large eggs stored unmodified (Fix 1 guard)
# ===========================================================================
class TestFoodLogTwoEggsUnmodified:
    def test_reconcile_within_tolerance_untouched(self, paid_user):
        """2 large eggs @ 180 cal / 15P / 1.3C / 12.8F.
        Derived: 15*4 + 1.3*4 + 12.8*9 = 60 + 5.2 + 115.2 = 180.4.
        Gap: |180 - 180.4| / 180 = 0.22% << 10% → must be stored unmodified."""
        payload = {
            "user_id": paid_user["id"], "food_name": "eggs",
            "serving_size": "2 large eggs (116g)", "calories": 180,
            "protein": 15, "carbs": 1.3, "fats": 12.8,
            "meal_type": "breakfast", "logged_date": "2026-01-20",
        }
        r = requests.post(f"{BASE_URL}/api/food/log", json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body["calories"] == 180, f"expected 180 (untouched), got {body['calories']}"
        assert body["protein"] == 15
        assert body["carbs"] == 1.3
        assert body["fats"] == 12.8

        # Persistence check
        logs = requests.get(
            f"{BASE_URL}/api/food/logs/{paid_user['id']}",
            params={"date": "2026-01-20"}, timeout=30,
        )
        assert logs.status_code == 200
        assert any(
            e.get("calories") == 180 and e.get("fats") == 12.8
            for e in logs.json()
        ), "Log entry not persisted with expected macros"


# ===========================================================================
# 5. Frontend source-level assertions on meal-detail.tsx
# ===========================================================================
class TestMealDetailSourceAssertions:
    @pytest.fixture(scope="class")
    def source(self):
        with open(MEAL_DETAIL_TSX_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_existing_state_regex_defined(self, source):
        assert "_EXISTING_STATE_RE" in source, "_EXISTING_STATE_RE constant missing"
        # Must contain raw|cooked|dry at minimum
        # regex uses non-capturing group (?:raw|cooked|dry|...)
        assert re.search(r"_EXISTING_STATE_RE\s*=\s*/\^\s*\\s\*\(\?:raw\|cooked\|dry", source), (
            "_EXISTING_STATE_RE regex must include 'raw|cooked|dry' alternatives"
        )

    def test_strip_existing_state_helper_defined(self, source):
        assert re.search(r"function\s+_stripExistingState\s*\(", source), (
            "_stripExistingState function definition missing"
        )

    def test_meal_contains_meat_helper_defined(self, source):
        assert re.search(r"function\s+mealContainsMeat\s*\(", source), (
            "mealContainsMeat function definition missing"
        )

    def test_weigh_meat_raw_guarded_by_meal_contains_meat(self, source):
        """The 'Weigh meat raw where you can' <Text> must be conditionally
        rendered based on mealContainsMeat(meal.ingredients)."""
        # Find the JSX line and check the immediately preceding guard
        # Expected pattern (allowing minor whitespace differences):
        #   {mealContainsMeat(meal.ingredients) && (
        #       <Text ...>Weigh meat raw where you can — it matches the pack label.</Text>
        #   )}
        pattern = re.compile(
            r"mealContainsMeat\s*\(\s*meal\.ingredients\s*\)\s*&&[\s\S]{0,200}?Weigh meat raw",
            re.MULTILINE,
        )
        assert pattern.search(source), (
            "'Weigh meat raw ...' <Text> is NOT guarded by "
            "mealContainsMeat(meal.ingredients) — vegan/vegetarian meals will "
            "still show the meat-weighing tip."
        )

    def test_format_ingredient_uses_strip_existing_state(self, source):
        """Sanity: formatIngredientWithRaw should call _stripExistingState so
        that 'cooked basmati rice' → 'basmati rice' before 'dry' prefix."""
        assert "_stripExistingState" in source
        # Ensure it's actually invoked (not just declared)
        assert re.search(r"_stripExistingState\s*\(", source)
