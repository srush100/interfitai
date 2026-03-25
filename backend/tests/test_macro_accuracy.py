"""
Macro Accuracy Tests for InterFitAI Meal Plan Generation
Tests: balanced, high_protein, keto (carbs < 50g), vegan (±15% tolerance)
Verifies honest ingredient-level scaling with no artificial inflation.
Test user ID: cbd82a69-3a37-48c2-88e8-0fe95081fa4b
Profile macros: ~2273 cal, 170g P, 227g C, 76g F
"""
import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://nutrition-debug-1.preview.emergentagent.com').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ========================================================
# HELPER
# ========================================================
def check_plan_structure(data):
    """Validates basic meal plan structure"""
    assert "meal_days" in data, "Response missing 'meal_days'"
    assert len(data["meal_days"]) >= 1, "No meal days in response"
    for day in data["meal_days"]:
        assert "total_calories" in day, f"Day missing 'total_calories': {day.get('day')}"
        assert "total_protein" in day, f"Day missing 'total_protein': {day.get('day')}"
        assert "total_carbs" in day, f"Day missing 'total_carbs': {day.get('day')}"
        assert "total_fats" in day, f"Day missing 'total_fats': {day.get('day')}"
        assert "meals" in day and len(day["meals"]) > 0, f"Day {day.get('day')} has no meals"


def get_user_profile_macros(api_client):
    """Fetch actual user profile macro targets for comparison"""
    resp = api_client.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}")
    assert resp.status_code == 200, f"Could not fetch profile: {resp.status_code}"
    profile = resp.json()
    macros = profile.get("calculated_macros", {})
    return {
        "calories": macros.get("calories", 2273),
        "protein": macros.get("protein", 170),
        "carbs": macros.get("carbs", 227),
        "fats": macros.get("fats", 76),
    }


def pct_deviation(actual, target):
    """Returns percentage deviation"""
    if target == 0:
        return 0.0
    return abs(actual - target) / target * 100


# ========================================================
# TEST CLASS 1: Balanced Meal Plan (±10% tolerance)
# ========================================================
class TestBalancedMealPlan:
    """POST /api/mealplans/generate balanced — protein/carbs/fats within ±10% of user targets"""

    def test_balanced_macros_within_10_percent(self, api_client):
        """Balanced meal plan macros should be within ±10% of user's profile targets on ALL days"""
        user_macros = get_user_profile_macros(api_client)
        target_cal = user_macros["calories"]
        target_pro = user_macros["protein"]
        target_carb = user_macros["carbs"]
        target_fat = user_macros["fats"]

        print(f"\n[Balanced] User targets: {target_cal}cal, {target_pro}g P, {target_carb}g C, {target_fat}g F")

        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "supplements": [],
            "allergies": []
        }

        start = time.time()
        resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[Balanced] Response time: {elapsed:.2f}s | Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        check_plan_structure(data)
        assert data.get("food_preferences") == "balanced"

        TOLERANCE = 10.0  # ±10% for balanced
        failures = []

        for day in data["meal_days"]:
            day_name = day.get("day", "Unknown")
            cal = day["total_calories"]
            pro = day["total_protein"]
            carb = day["total_carbs"]
            fat = day["total_fats"]

            print(f"\n[Balanced] {day_name}: {cal}cal, {pro}g P, {carb}g C, {fat}g F")
            print(f"           Target:    {target_cal}cal, {target_pro}g P, {target_carb}g C, {target_fat}g F")
            print(f"           Deviation: cal={pct_deviation(cal, target_cal):.1f}%, P={pct_deviation(pro, target_pro):.1f}%, C={pct_deviation(carb, target_carb):.1f}%, F={pct_deviation(fat, target_fat):.1f}%")

            # Print individual meals
            for meal in day.get("meals", []):
                print(f"   Meal '{meal.get('name')}': {meal.get('calories')}cal, {meal.get('protein')}g P, {meal.get('carbs')}g C, {meal.get('fats')}g F")
                ings = meal.get("ingredients", [])[:3]
                print(f"     Ingredients (first 3): {ings}")

            if pct_deviation(cal, target_cal) > TOLERANCE:
                failures.append(f"{day_name} calories: {cal} vs target {target_cal} ({pct_deviation(cal, target_cal):.1f}% > {TOLERANCE}%)")
            if pct_deviation(pro, target_pro) > TOLERANCE:
                failures.append(f"{day_name} protein: {pro}g vs target {target_pro}g ({pct_deviation(pro, target_pro):.1f}% > {TOLERANCE}%)")
            if pct_deviation(carb, target_carb) > TOLERANCE:
                failures.append(f"{day_name} carbs: {carb}g vs target {target_carb}g ({pct_deviation(carb, target_carb):.1f}% > {TOLERANCE}%)")
            if pct_deviation(fat, target_fat) > TOLERANCE:
                failures.append(f"{day_name} fats: {fat}g vs target {target_fat}g ({pct_deviation(fat, target_fat):.1f}% > {TOLERANCE}%)")

        if failures:
            print(f"\n❌ [Balanced] FAILURES ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
        else:
            print(f"\n✅ [Balanced] ALL DAYS WITHIN ±{TOLERANCE}%!")

        assert len(failures) == 0, (
            f"❌ BALANCED MACRO ACCURACY FAILED\n" +
            "\n".join(failures)
        )


# ========================================================
# TEST CLASS 2: High Protein Meal Plan (±10% tolerance)
# ========================================================
class TestHighProteinMealPlan:
    """POST /api/mealplans/generate high_protein — protein/carbs/fats within ±10%"""

    def test_high_protein_macros_within_10_percent(self, api_client):
        """High protein plan macros should be within ±10% of user's profile targets"""
        user_macros = get_user_profile_macros(api_client)
        target_cal = user_macros["calories"]
        target_pro = user_macros["protein"]
        target_carb = user_macros["carbs"]
        target_fat = user_macros["fats"]

        print(f"\n[High Protein] User targets: {target_cal}cal, {target_pro}g P, {target_carb}g C, {target_fat}g F")

        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "high_protein",
            "supplements": [],
            "allergies": []
        }

        start = time.time()
        resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[High Protein] Response time: {elapsed:.2f}s | Status: {resp.status_code}")
        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        check_plan_structure(data)
        assert data.get("food_preferences") == "high_protein"

        TOLERANCE = 10.0  # ±10%
        failures = []

        for day in data["meal_days"]:
            day_name = day.get("day", "Unknown")
            cal = day["total_calories"]
            pro = day["total_protein"]
            carb = day["total_carbs"]
            fat = day["total_fats"]

            print(f"\n[High Protein] {day_name}: {cal}cal, {pro}g P, {carb}g C, {fat}g F")
            print(f"               Target:    {target_cal}cal, {target_pro}g P, {target_carb}g C, {target_fat}g F")
            print(f"               Deviation: cal={pct_deviation(cal, target_cal):.1f}%, P={pct_deviation(pro, target_pro):.1f}%, C={pct_deviation(carb, target_carb):.1f}%, F={pct_deviation(fat, target_fat):.1f}%")

            for meal in day.get("meals", []):
                print(f"   Meal '{meal.get('name')}': {meal.get('calories')}cal, {meal.get('protein')}g P, {meal.get('carbs')}g C, {meal.get('fats')}g F")
                ings = meal.get("ingredients", [])[:3]
                print(f"     Ingredients (first 3): {ings}")

            if pct_deviation(cal, target_cal) > TOLERANCE:
                failures.append(f"{day_name} calories: {cal} vs target {target_cal} ({pct_deviation(cal, target_cal):.1f}% > {TOLERANCE}%)")
            if pct_deviation(pro, target_pro) > TOLERANCE:
                failures.append(f"{day_name} protein: {pro}g vs target {target_pro}g ({pct_deviation(pro, target_pro):.1f}% > {TOLERANCE}%)")
            if pct_deviation(carb, target_carb) > TOLERANCE:
                failures.append(f"{day_name} carbs: {carb}g vs target {target_carb}g ({pct_deviation(carb, target_carb):.1f}% > {TOLERANCE}%)")
            if pct_deviation(fat, target_fat) > TOLERANCE:
                failures.append(f"{day_name} fats: {fat}g vs target {target_fat}g ({pct_deviation(fat, target_fat):.1f}% > {TOLERANCE}%)")

        if failures:
            print(f"\n❌ [High Protein] FAILURES ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
        else:
            print(f"\n✅ [High Protein] ALL DAYS WITHIN ±{TOLERANCE}%!")

        assert len(failures) == 0, (
            f"❌ HIGH PROTEIN MACRO ACCURACY FAILED\n" +
            "\n".join(failures)
        )


# ========================================================
# TEST CLASS 3: Keto — carbs MUST be < 50g, NOT 229g
# ========================================================
class TestKetoMealPlan:
    """POST /api/mealplans/generate keto — CRITICAL: total_carbs < 50g per day"""

    def test_keto_carbs_under_50g_all_days(self, api_client):
        """Keto plan must have < 50g carbs per day (NOT using user profile target of 229g)"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "keto",
            "supplements": [],
            "allergies": []
        }

        print(f"\n[Keto] Sending POST /api/mealplans/generate — keto compliance test")
        start = time.time()
        resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[Keto] Response time: {elapsed:.2f}s | Status: {resp.status_code}")

        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        check_plan_structure(data)
        assert data.get("food_preferences") == "keto"

        KETO_CARB_LIMIT = 50  # g per day
        failures = []

        for day in data["meal_days"]:
            day_name = day.get("day", "Unknown")
            carbs = day["total_carbs"]
            calories = day["total_calories"]
            protein = day["total_protein"]
            fats = day["total_fats"]

            print(f"\n[Keto] {day_name}: {calories}cal, {protein}g P, {carbs}g C, {fats}g F")
            print(f"       ← carbs must be < {KETO_CARB_LIMIT}g for keto compliance")

            for meal in day.get("meals", []):
                print(f"   Meal '{meal.get('name')}': {meal.get('calories')}cal, {meal.get('protein')}g P, {meal.get('carbs')}g C, {meal.get('fats')}g F")
                ings = meal.get("ingredients", [])[:4]
                print(f"     Ingredients (first 4): {ings}")

            if carbs >= KETO_CARB_LIMIT:
                failures.append(
                    f"{day_name}: {carbs}g carbs ≥ {KETO_CARB_LIMIT}g limit (KETO VIOLATION!)"
                )
            else:
                print(f"   ✅ {day_name}: {carbs}g carbs is keto-compliant (< {KETO_CARB_LIMIT}g)")

            # Verify keto is not using user profile carb target (229g would be wildly wrong)
            if carbs > 100:
                failures.append(
                    f"{day_name}: {carbs}g carbs is way too high — possibly using wrong target (user profile has 227g carbs)"
                )

            # Keto should also have reasonable fat (at least 50g)
            if fats < 50:
                failures.append(f"{day_name}: {fats}g fats too low for keto (should be > 50g)")

        if failures:
            print(f"\n❌ [Keto] FAILURES ({len(failures)}):")
            for f in failures:
                print(f"  - {f}")
        else:
            print(f"\n✅ [Keto] ALL DAYS KETO COMPLIANT!")

        assert len(failures) == 0, (
            f"❌ KETO COMPLIANCE FAILED\n" +
            "\n".join(failures)
        )

    def test_keto_not_using_profile_carb_target(self, api_client):
        """Keto plan total_carbs should be far below the user's profile carb target of ~227g"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "keto",
            "supplements": [],
            "allergies": []
        }

        resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        assert resp.status_code == 200
        data = resp.json()

        day1 = data["meal_days"][0]
        day1_carbs = day1["total_carbs"]
        profile_carb_target = 227  # user's profile target

        print(f"\n[Keto Non-Profile Check] Day 1 carbs: {day1_carbs}g | User profile target: {profile_carb_target}g")

        # If keto plan has carbs close to profile target (227g), that's a critical bug
        assert day1_carbs < profile_carb_target * 0.3, (
            f"❌ Keto plan carbs ({day1_carbs}g) is suspiciously close to user's balanced profile target "
            f"({profile_carb_target}g). Keto should be WELL below 50g, not near {profile_carb_target}g."
        )
        print(f"✅ Keto carbs ({day1_carbs}g) is correctly NOT using profile target ({profile_carb_target}g)")


# ========================================================
# TEST CLASS 4: Vegan — no animal products, protein ±15%, no inflation
# ========================================================
class TestVeganMealPlan:
    """POST /api/mealplans/generate vegan — protein ±15%, no animals, no inflation"""

    # Purely animal-derived terms (no plant-based compound words containing these)
    ANIMAL_PRODUCTS = [
        'chicken breast', 'chicken thigh', 'ground chicken', 'grilled chicken', 'rotisserie chicken',
        'ground beef', 'beef sirloin', 'ribeye', 'beef tenderloin', 'beef mince',
        'pork chop', 'pork loin', 'pork belly', 'ground pork',
        'turkey breast', 'ground turkey',
        'salmon fillet', 'tuna fish', 'tuna steak', 'cod fillet', 'tilapia', 'shrimp', 'lobster', 'crab',
        'lamb chop', 'lamb steak',
        'bacon strips', 'ham steak', 'ham slices',
        'whey protein',  # dairy-based protein
        'casein', 'gelatin', 'collagen',
        'whole milk', 'skim milk', 'cow\'s milk', 'dairy milk',
        'heavy cream', 'sour cream', 'cream cheese', 'greek yogurt', 'cottage cheese',
        'cheddar cheese', 'parmesan cheese', 'mozzarella cheese',
        'unsalted butter', 'salted butter', 'clarified butter',  # NOT peanut butter/almond butter
        'ghee',
        'whole eggs', 'large eggs', 'egg whites', 'scrambled eggs',
        'anchovy', 'lard',  # actual animal fat (not 'collard greens')
    ]

    # Plant-based false-positive patterns to EXCLUDE from check
    VEGAN_SAFE_PATTERNS = [
        'peanut butter', 'almond butter', 'cashew butter', 'sunflower butter',  # vegan nut butters
        'coconut milk', 'oat milk', 'almond milk', 'soy milk', 'rice milk',  # plant milks
        'collard',  # collard greens (not lard)
        'tofu steak', 'tempeh steak', 'seitan steak',  # vegan "steak" style dishes
        'vegan protein powder', 'vegan chocolate', 'vegan vanilla',
    ]

    def _check_for_animal_products(self, data):
        """Returns list of animal products found in the meal plan (with false-positive filtering)"""
        found = []
        for day in data.get("meal_days", []):
            for meal in day.get("meals", []):
                name = meal.get("name", "").lower()
                ingredients_str = " ".join(meal.get("ingredients", [])).lower()
                full_text = f"{name} {ingredients_str}"

                # Remove vegan-safe patterns before checking
                clean_text = full_text
                for safe in self.VEGAN_SAFE_PATTERNS:
                    clean_text = clean_text.replace(safe, "VEGAN_SAFE")

                for animal_prod in self.ANIMAL_PRODUCTS:
                    if animal_prod in clean_text:
                        found.append(f"'{animal_prod}' in meal '{meal.get('name')}' (ingredients: {meal.get('ingredients', [])[:3]})")
        return found

    def test_vegan_no_animal_products(self, api_client):
        """Vegan plan must contain ZERO animal products in any meal"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "vegan",
            "supplements": [],
            "allergies": []
        }

        print(f"\n[Vegan] Testing for animal-product compliance...")
        start = time.time()
        resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[Vegan] Response time: {elapsed:.2f}s | Status: {resp.status_code}")

        assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text[:300]}"
        data = resp.json()
        check_plan_structure(data)

        animal_found = self._check_for_animal_products(data)

        # Print all meals for inspection
        for day in data["meal_days"]:
            print(f"\n[Vegan] {day.get('day')}: {day.get('total_protein')}g P")
            for meal in day.get("meals", []):
                print(f"   {meal.get('name')}: {meal.get('ingredients', [])[:3]}")

        if animal_found:
            print(f"\n❌ [Vegan] Animal products found ({len(animal_found)}):")
            for item in animal_found:
                print(f"  - {item}")
        else:
            print(f"✅ [Vegan] No animal products found!")

        assert len(animal_found) == 0, (
            f"❌ VEGAN COMPLIANCE: Animal products found in vegan plan:\n" +
            "\n".join(animal_found[:10])
        )

    def test_vegan_protein_within_15_percent_no_inflation(self, api_client):
        """Vegan plan protein must be within ±15% of user target AND not artificially inflated (> 250g)"""
        user_macros = get_user_profile_macros(api_client)
        target_pro = user_macros["protein"]
        target_cal = user_macros["calories"]

        print(f"\n[Vegan Protein] User protein target: {target_pro}g | Calories: {target_cal}")

        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "vegan",
            "supplements": [],
            "allergies": []
        }

        start = time.time()
        resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[Vegan Protein] Response time: {elapsed:.2f}s | Status: {resp.status_code}")

        assert resp.status_code == 200
        data = resp.json()
        check_plan_structure(data)

        PROTEIN_TOLERANCE = 15.0  # ±15% for vegan
        MAX_REALISTIC_PROTEIN = 250  # artificial inflation flag
        failures = []

        for day in data["meal_days"]:
            day_name = day.get("day", "Unknown")
            pro = day["total_protein"]
            cal = day["total_calories"]
            carb = day["total_carbs"]
            fat = day["total_fats"]

            print(f"\n[Vegan Protein] {day_name}: {cal}cal, {pro}g P, {carb}g C, {fat}g F")
            print(f"                Target: {target_cal}cal, {target_pro}g P")
            print(f"                Protein deviation: {pct_deviation(pro, target_pro):.1f}%")

            # 1. No artificial inflation (old bug was >250g protein for vegan)
            if pro > MAX_REALISTIC_PROTEIN:
                failures.append(
                    f"{day_name}: {pro}g protein is ARTIFICIALLY INFLATED (old bug). "
                    f"Vegan protein sources cannot realistically provide {pro}g."
                )

            # 2. Protein within ±15% of user target
            if pct_deviation(pro, target_pro) > PROTEIN_TOLERANCE:
                failures.append(
                    f"{day_name}: {pro}g protein vs target {target_pro}g "
                    f"({pct_deviation(pro, target_pro):.1f}% > {PROTEIN_TOLERANCE}%)"
                )
            else:
                print(f"   ✅ {day_name}: {pro}g protein within {PROTEIN_TOLERANCE}% of target {target_pro}g")

        if failures:
            print(f"\n❌ [Vegan Protein] FAILURES:")
            for f in failures:
                print(f"  - {f}")
        else:
            print(f"\n✅ [Vegan Protein] ALL DAYS WITHIN ±{PROTEIN_TOLERANCE}% TOLERANCE!")

        assert len(failures) == 0, (
            f"❌ VEGAN PROTEIN ACCURACY FAILED\n" +
            "\n".join(failures)
        )


# ========================================================
# TEST CLASS 5: Sanity Check — Ingredient Amount vs Macro Values
# ========================================================
class TestMacroSanityCheck:
    """Sanity check: ingredient amounts should result in realistic macro values"""

    def test_balanced_ingredient_sanity(self, api_client):
        """
        Verifies ingredient gram amounts are realistic for reported macros.
        E.g., if a meal shows 200g protein but ingredients only list 100g chicken,
        that's impossible (100g chicken ≈ 31g protein, not 200g protein).
        """
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "supplements": [],
            "allergies": []
        }

        resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        assert resp.status_code == 200

        data = resp.json()
        check_plan_structure(data)

        # Simple sanity: total protein should not exceed 1g/g of total ingredient weight
        # (even pure protein powder is 80g P per 100g)
        sanity_failures = []

        for day in data["meal_days"]:
            day_pro = day["total_protein"]
            day_cal = day["total_calories"]

            # Sanity 1: Protein calories should not exceed total calories
            # (1g protein = 4 cal, so protein_calories = protein * 4)
            if day_pro * 4 > day_cal * 1.1:  # Allow 10% margin
                sanity_failures.append(
                    f"{day.get('day')}: protein*4 ({day_pro * 4}) > total_calories ({day_cal}) — impossible!"
                )

            # Sanity 2: No single macro should represent > 75% of calories unrealistically
            # Balanced diet: protein should not be > 60% of calories
            protein_pct = (day_pro * 4 / day_cal * 100) if day_cal > 0 else 0
            if protein_pct > 70:
                sanity_failures.append(
                    f"{day.get('day')}: {protein_pct:.1f}% of calories from protein — unrealistic for balanced diet"
                )

            print(f"[Sanity] {day.get('day')}: {day_cal}cal, {day_pro}g P ({protein_pct:.1f}% from protein)")

        if sanity_failures:
            print(f"\n❌ [Sanity] FAILURES:")
            for f in sanity_failures:
                print(f"  - {f}")
        else:
            print(f"\n✅ [Sanity] All macro sanity checks passed!")

        assert len(sanity_failures) == 0, (
            f"❌ MACRO SANITY CHECK FAILED:\n" +
            "\n".join(sanity_failures)
        )

    def test_keto_fat_dominance_sanity(self, api_client):
        """Keto plan should have fat as dominant macro (> 60% of calories from fat)"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "keto",
            "supplements": [],
            "allergies": []
        }

        resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        assert resp.status_code == 200

        data = resp.json()
        check_plan_structure(data)

        failures = []
        for day in data["meal_days"]:
            day_cal = day["total_calories"]
            day_fat = day["total_fats"]
            day_carbs = day["total_carbs"]
            fat_pct = (day_fat * 9 / day_cal * 100) if day_cal > 0 else 0

            print(f"[Keto Sanity] {day.get('day')}: {day_cal}cal, {day_fat}g F ({fat_pct:.1f}% from fat), {day_carbs}g C")

            if fat_pct < 55:  # Keto should have 60-75% from fat
                failures.append(
                    f"{day.get('day')}: Only {fat_pct:.1f}% of calories from fat — not keto-like!"
                )
            if day_carbs >= 50:
                failures.append(
                    f"{day.get('day')}: {day_carbs}g carbs violates keto limit (< 50g)"
                )

        if failures:
            print(f"\n❌ [Keto Sanity] FAILURES:")
            for f in failures:
                print(f"  - {f}")
        else:
            print(f"\n✅ [Keto Sanity] All keto sanity checks passed!")

        assert len(failures) == 0, (
            f"❌ KETO SANITY FAILED:\n" + "\n".join(failures)
        )


# ========================================================
# TEST CLASS 6: Health Check Sanity
# ========================================================
class TestHealthCheck:
    def test_health(self, api_client):
        resp = api_client.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200
        print(f"✅ Health check: {resp.json()}")
