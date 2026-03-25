"""
Comprehensive Backend Tests - Macro Scaling Logic & foods_to_avoid Filtering
Review Request Acceptance Criteria:
1. GET /api/health - sanity check
2. POST /api/mealplans/generate (balanced, no preferred_foods) - ALL 3 days within ±3% cal, ±10% P/C/F of 2273cal/170g/227g/76g
3. POST /api/mealplans/generate (vegan, no preferred_foods) - protein 130-220g per day (NOT >250g). No animal products.
4. POST /api/mealplans/generate (keto, no preferred_foods) - Day 1 carbs MUST be < 50g
5. POST /api/mealplans/generate (high_protein, no preferred_foods) - protein within ±15% of 170g target
6. POST /api/mealplans/generate (balanced, foods_to_avoid='chicken') - ZERO chicken in any meal names or ingredients
7. POST /api/mealplan/alternate with foods_to_avoid='chicken' stored in plan - ZERO chicken in response
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://nutrition-debug-1.preview.emergentagent.com').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# User profile targets (from test user's profile)
TARGET_CAL = 2273
TARGET_PRO = 170
TARGET_CARB = 227
TARGET_FAT = 76


@pytest.fixture
def api_client():
    """Shared requests session with JSON content type"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ============================================================
# TEST 1: Health Check
# ============================================================
class TestHealthCheck:
    """Sanity check - server must be up and respond 200"""

    def test_health_returns_200(self, api_client):
        """GET /api/health - expect 200 OK"""
        start = time.time()
        response = api_client.get(f"{BASE_URL}/api/health")
        elapsed = time.time() - start
        print(f"\n[Health] Response time: {elapsed:.2f}s | Status: {response.status_code}")
        assert response.status_code == 200, f"Health check failed: {response.status_code} {response.text[:200]}"
        data = response.json()
        assert "status" in data or "timestamp" in data, f"Missing status/timestamp: {data}"
        print(f"✅ Health check PASSED: {data}")


# ============================================================
# TEST 2: Balanced Plan - ALL 3 days macro accuracy
# ============================================================
class TestBalancedMealPlanAllDays:
    """Balanced plan (template path, no preferred_foods): ALL 3 days within ±3% cal and ±10% P/C/F"""

    def test_balanced_all_3_days_macro_accuracy(self, api_client):
        """ALL 3 days must have cal within ±3% and protein/carbs/fat within ±10% of targets"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "supplements": [],
            "allergies": []
            # No preferred_foods → template path
        }
        print(f"\n[Balanced] Sending POST /api/mealplans/generate - balanced, no preferred_foods")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[Balanced] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, f"Expected 200 got {response.status_code}: {response.text[:300]}"
        data = response.json()
        assert "meal_days" in data, "Response missing 'meal_days'"
        assert len(data["meal_days"]) == 3, f"Expected 3 days, got {len(data['meal_days'])}"

        print(f"\n[Balanced] Target: {TARGET_CAL} cal, {TARGET_PRO}g P, {TARGET_CARB}g C, {TARGET_FAT}g F")
        print(f"[Balanced] Path: {'AI' if data.get('preferred_foods') else 'Template'}")

        all_days_pass = True
        failed_days = []

        for i, day in enumerate(data["meal_days"]):
            cal = day.get("total_calories", 0)
            pro = day.get("total_protein", 0)
            carb = day.get("total_carbs", 0)
            fat = day.get("total_fats", 0)

            cal_dev = abs(cal - TARGET_CAL) / TARGET_CAL * 100
            pro_dev = abs(pro - TARGET_PRO) / TARGET_PRO * 100
            carb_dev = abs(carb - TARGET_CARB) / TARGET_CARB * 100
            fat_dev = abs(fat - TARGET_FAT) / TARGET_FAT * 100

            day_pass = cal_dev <= 3 and pro_dev <= 10 and carb_dev <= 10 and fat_dev <= 10

            status = "✅" if day_pass else "❌"
            print(f"\n[Balanced] Day {i+1}: {status}")
            print(f"  Calories: {cal} (target {TARGET_CAL}, dev {cal_dev:.1f}%) {'✅' if cal_dev <= 3 else '❌ >3%'}")
            print(f"  Protein:  {pro}g (target {TARGET_PRO}g, dev {pro_dev:.1f}%) {'✅' if pro_dev <= 10 else '❌ >10%'}")
            print(f"  Carbs:    {carb}g (target {TARGET_CARB}g, dev {carb_dev:.1f}%) {'✅' if carb_dev <= 10 else '❌ >10%'}")
            print(f"  Fats:     {fat}g (target {TARGET_FAT}g, dev {fat_dev:.1f}%) {'✅' if fat_dev <= 10 else '❌ >10%'}")

            if not day_pass:
                all_days_pass = False
                failed_days.append({
                    "day": i + 1,
                    "cal": f"{cal} ({cal_dev:.1f}% dev)",
                    "pro": f"{pro}g ({pro_dev:.1f}% dev)",
                    "carb": f"{carb}g ({carb_dev:.1f}% dev)",
                    "fat": f"{fat}g ({fat_dev:.1f}% dev)"
                })

        assert all_days_pass, (
            f"❌ BALANCED MACRO ACCURACY FAILED on {len(failed_days)} days:\n"
            + "\n".join([
                f"  Day {d['day']}: cal={d['cal']}, P={d['pro']}, C={d['carb']}, F={d['fat']}"
                for d in failed_days
            ])
        )
        print(f"\n✅ Balanced plan ALL 3 days macro accuracy PASSED!")


# ============================================================
# TEST 3: Vegan Plan Protein Accuracy
# ============================================================
class TestVeganMealPlanProtein:
    """Vegan plan protein must be 130-220g per day (NOT inflated >250g). No animal products."""

    def test_vegan_protein_range_and_no_animal_products(self, api_client):
        """Vegan plan: protein 130-220g per day, no chicken/beef/fish/pork/dairy in any meal"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "vegan",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[Vegan] Sending POST /api/mealplans/generate with food_preferences='vegan'")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[Vegan] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, f"Expected 200 got {response.status_code}: {response.text[:300]}"
        data = response.json()

        assert "meal_days" in data, "Response missing 'meal_days'"
        assert len(data["meal_days"]) > 0, "No meal days in response"
        assert data.get("food_preferences") == "vegan", f"food_preferences not 'vegan': {data.get('food_preferences')}"

        # Animal product keywords to check
        animal_products = ['chicken', 'beef', 'pork', 'fish', 'salmon', 'tuna', 'shrimp', 'turkey',
                           'bacon', 'ham', 'sausage', 'lamb', 'meat', 'milk', 'cheese', 'butter',
                           'cream', 'yogurt', 'whey', 'egg']
        # Exception - these are vegan
        vegan_exceptions = ['soy milk', 'oat milk', 'almond milk', 'coconut milk', 'plant-based',
                            'nutritional yeast', 'vegan cheese']

        protein_failures = []
        animal_product_violations = []

        for i, day in enumerate(data["meal_days"]):
            pro = day.get("total_protein", 0)
            cal = day.get("total_calories", 0)
            carb = day.get("total_carbs", 0)
            fat = day.get("total_fats", 0)

            print(f"\n[Vegan] Day {i+1}: {cal} cal, {pro}g P, {carb}g C, {fat}g F")

            # Check protein range 130-220g
            if not (130 <= pro <= 220):
                protein_failures.append(f"Day {i+1}: {pro}g (expected 130-220g)")

            # Check no animal products
            for meal in day.get("meals", []):
                meal_text = f"{meal.get('name', '')} {' '.join(meal.get('ingredients', []))}".lower()
                for animal in animal_products:
                    if animal in meal_text:
                        # Check vegan exceptions
                        is_exception = any(exc in meal_text for exc in vegan_exceptions)
                        if not is_exception:
                            animal_product_violations.append(
                                f"Day {i+1} meal '{meal.get('name')}': found '{animal}'"
                            )
                            break

        if protein_failures:
            print(f"❌ Vegan protein out of range: {protein_failures}")
        if animal_product_violations:
            print(f"⚠️  Animal products found: {animal_product_violations}")

        # Critical: Protein must not be inflated (old bug was >250g)
        for i, day in enumerate(data["meal_days"]):
            pro = day.get("total_protein", 0)
            assert pro <= 250, (
                f"❌ VEGAN PROTEIN INFLATION BUG STILL PRESENT: Day {i+1} protein = {pro}g > 250g. "
                f"The old inflation bug is back!"
            )

        # Protein should be in 130-220g range
        assert len(protein_failures) == 0, (
            f"❌ VEGAN PROTEIN OUT OF RANGE (expected 130-220g):\n"
            + "\n".join([f"  {f}" for f in protein_failures])
        )

        print(f"\n✅ Vegan plan protein accuracy PASSED and no animal products found!")


# ============================================================
# TEST 4: Keto Plan Carb Compliance
# ============================================================
class TestKetoMealPlanCarbs:
    """Keto plan: Day 1 carbs MUST be < 50g"""

    def test_keto_day1_carbs_under_50g(self, api_client):
        """POST /api/mealplans/generate keto - Day 1 carbs must be < 50g for keto compliance"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "keto",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[Keto] Sending POST /api/mealplans/generate with food_preferences='keto'")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[Keto] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, f"Expected 200 got {response.status_code}: {response.text[:300]}"
        data = response.json()

        assert "meal_days" in data, "Response missing 'meal_days'"
        assert len(data["meal_days"]) > 0, "No meal days in response"
        assert data.get("food_preferences") == "keto", f"food_preferences not 'keto': {data.get('food_preferences')}"

        day1 = data["meal_days"][0]
        total_carbs = day1.get("total_carbs", 0)
        total_calories = day1.get("total_calories", 0)
        total_protein = day1.get("total_protein", 0)
        total_fats = day1.get("total_fats", 0)

        print(f"\n[Keto] Day 1:")
        print(f"  Calories: {total_calories} kcal")
        print(f"  Protein:  {total_protein}g")
        print(f"  Carbs:    {total_carbs}g  ← MUST BE < 50g")
        print(f"  Fats:     {total_fats}g")
        print(f"  Fat % of calories: {(total_fats * 9 / total_calories * 100) if total_calories > 0 else 0:.1f}%")

        # Print all meals
        meals = day1.get("meals", [])
        print(f"\n[Keto] Individual meals ({len(meals)} total):")
        for meal in meals:
            print(f"  {meal.get('meal_type','?').upper()} - {meal.get('name', '?')}: "
                  f"{meal.get('calories',0)} cal, {meal.get('carbs',0)}g C, {meal.get('fats',0)}g F")

        # CRITICAL: Keto carbs MUST be < 50g per day
        assert total_carbs < 50, (
            f"❌ KETO COMPLIANCE FAILED: Day 1 carbs = {total_carbs}g, exceeds 50g limit. "
            f"Note: keto should NOT use user profile 229g carb target but diet-appropriate targets."
        )

        # Keto should have high fat
        assert total_fats > 50, (
            f"❌ KETO FAT TOO LOW: {total_fats}g. Keto requires high fat (usually 60%+ of calories)"
        )
        assert total_calories > 0, "Keto plan has zero calories"

        print(f"\n✅ Keto compliance PASSED: {total_carbs}g carbs (< 50g limit), {total_fats}g fats")


# ============================================================
# TEST 5: High Protein Plan Protein Accuracy
# ============================================================
class TestHighProteinMealPlan:
    """High protein plan: protein should be within ±15% of 170g target"""

    def test_high_protein_within_15_percent(self, api_client):
        """POST /api/mealplans/generate high_protein - protein within ±15% of 170g target"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "high_protein",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[HighProtein] Sending POST /api/mealplans/generate with food_preferences='high_protein'")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[HighProtein] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, f"Expected 200 got {response.status_code}: {response.text[:300]}"
        data = response.json()

        assert "meal_days" in data, "Response missing 'meal_days'"
        assert len(data["meal_days"]) > 0, "No meal days in response"

        failed_days = []
        for i, day in enumerate(data["meal_days"]):
            pro = day.get("total_protein", 0)
            cal = day.get("total_calories", 0)
            carb = day.get("total_carbs", 0)
            fat = day.get("total_fats", 0)

            pro_dev = abs(pro - TARGET_PRO) / TARGET_PRO * 100
            cal_dev = abs(cal - TARGET_CAL) / TARGET_CAL * 100

            print(f"\n[HighProtein] Day {i+1}:")
            print(f"  Calories: {cal} kcal (dev {cal_dev:.1f}%)")
            print(f"  Protein:  {pro}g (target {TARGET_PRO}g, dev {pro_dev:.1f}%)")
            print(f"  Carbs:    {carb}g")
            print(f"  Fats:     {fat}g")

            if pro_dev > 15:
                failed_days.append(f"Day {i+1}: {pro}g protein ({pro_dev:.1f}% deviation from {TARGET_PRO}g target)")

        assert len(failed_days) == 0, (
            f"❌ HIGH_PROTEIN PLAN PROTEIN DEVIATION > 15%:\n"
            + "\n".join([f"  {f}" for f in failed_days])
        )

        print(f"\n✅ High protein plan protein accuracy PASSED: all days within ±15% of {TARGET_PRO}g target")


# ============================================================
# TEST 6: Balanced + foods_to_avoid='chicken' — NO chicken in names OR ingredients
# ============================================================
class TestFoodsToAvoidChickenTemplate:
    """Template balanced plan with foods_to_avoid='chicken': ZERO chicken in names, ingredients, instructions"""

    def test_balanced_no_chicken_in_names_or_ingredients(self, api_client):
        """ALL meal names AND ingredient lists must be chicken-free when foods_to_avoid='chicken'"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "foods_to_avoid": "chicken",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[FoodsToAvoid] POST /api/mealplans/generate - balanced, foods_to_avoid='chicken'")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[FoodsToAvoid] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, f"Expected 200 got {response.status_code}: {response.text[:300]}"
        data = response.json()
        assert "meal_days" in data, "Missing 'meal_days' in response"
        assert len(data["meal_days"]) > 0, "No meal days in response"

        chicken_violations = []
        all_meal_names = []
        total_meals = 0

        for day_idx, day in enumerate(data["meal_days"]):
            for meal in day.get("meals", []):
                total_meals += 1
                meal_name = meal.get("name", "")
                all_meal_names.append(meal_name)
                ingredients = meal.get("ingredients", [])
                instructions = meal.get("instructions", "")

                # Check name
                if "chicken" in meal_name.lower():
                    chicken_violations.append(f"Day {day_idx+1} meal NAME: '{meal_name}'")

                # Check each ingredient
                for ing in ingredients:
                    if "chicken" in str(ing).lower():
                        chicken_violations.append(f"Day {day_idx+1} meal '{meal_name}' INGREDIENT: '{ing}'")

                # Check instructions
                if "chicken" in str(instructions).lower():
                    chicken_violations.append(f"Day {day_idx+1} meal '{meal_name}' INSTRUCTIONS contain 'chicken'")

        print(f"\n[FoodsToAvoid] Checked {total_meals} meals across {len(data['meal_days'])} days:")
        for name in all_meal_names:
            marker = "❌ CHICKEN" if "chicken" in name.lower() else "✅"
            print(f"  {marker} {name}")

        if chicken_violations:
            print(f"\n❌ CHICKEN FOUND IN {len(chicken_violations)} places:")
            for v in chicken_violations:
                print(f"  - {v}")

        assert len(chicken_violations) == 0, (
            f"❌ FOODS_TO_AVOID FILTER FAILED: 'chicken' found in {len(chicken_violations)} places "
            f"despite foods_to_avoid='chicken':\n"
            + "\n".join([f"  {v}" for v in chicken_violations])
        )

        print(f"\n✅ foods_to_avoid='chicken' template filter PASSED: no chicken in {total_meals} meals!")


# ============================================================
# TEST 7: Alternate Meal — foods_to_avoid='chicken' compliance
# ============================================================
class TestAlternateMealChickenFree:
    """Generate alternate meal from plan with foods_to_avoid='chicken': ZERO chicken in result"""

    def test_alternate_meal_no_chicken(self, api_client):
        """Step 1: generate plan with foods_to_avoid='chicken'. Step 2: get alternate. Verify zero chicken."""
        # Step 1: Generate plan with chicken banned
        plan_payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "foods_to_avoid": "chicken",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[AltMeal] Step 1: Generating meal plan with foods_to_avoid='chicken'")
        start = time.time()
        plan_response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=plan_payload, timeout=180)
        elapsed = time.time() - start
        print(f"[AltMeal] Plan generation: {elapsed:.2f}s | Status: {plan_response.status_code}")

        assert plan_response.status_code == 200, (
            f"Failed to create meal plan: {plan_response.status_code} {plan_response.text[:300]}"
        )
        plan_data = plan_response.json()
        meal_plan_id = plan_data.get("id")
        assert meal_plan_id, "Meal plan missing 'id' field"
        print(f"[AltMeal] Created plan ID: {meal_plan_id}")

        # Print original meal 1 (index 1 = lunch) for context
        day0_meals = plan_data.get("meal_days", [{}])[0].get("meals", [])
        if len(day0_meals) > 1:
            orig_meal = day0_meals[1]
            print(f"[AltMeal] Original lunch: {orig_meal.get('name')} - "
                  f"ingredients[:3]: {orig_meal.get('ingredients', [])[:3]}")

        # Step 2: Get alternate for day 0, meal 1 (lunch)
        alt_payload = {
            "user_id": TEST_USER_ID,
            "meal_plan_id": meal_plan_id,
            "day_index": 0,
            "meal_index": 1,
            "swap_preference": "similar"
        }
        print(f"\n[AltMeal] Step 2: Requesting alternate for day_index=0, meal_index=1")
        start = time.time()
        alt_response = api_client.post(f"{BASE_URL}/api/mealplan/alternate", json=alt_payload, timeout=180)
        elapsed = time.time() - start
        print(f"[AltMeal] Alternate meal: {elapsed:.2f}s | Status: {alt_response.status_code}")

        assert alt_response.status_code == 200, (
            f"Alternate meal failed: {alt_response.status_code} {alt_response.text[:300]}"
        )
        alt_data = alt_response.json()

        # Handle both response structures
        meal_obj = alt_data.get("alternate_meal") or alt_data
        meal_name = meal_obj.get("name", "")
        ingredients = meal_obj.get("ingredients", [])
        instructions = meal_obj.get("instructions", "")

        print(f"[AltMeal] Generated alternate meal: {meal_name}")
        print(f"[AltMeal] Ingredients: {ingredients}")

        # Verify NO chicken anywhere
        all_text = f"{meal_name} {' '.join([str(i) for i in ingredients])} {instructions}".lower()
        chicken_keywords = ["chicken", "poultry", "rotisserie"]
        found_chicken = [kw for kw in chicken_keywords if kw in all_text]

        if found_chicken:
            print(f"❌ CHICKEN FOUND! Keywords: {found_chicken}")
            print(f"   Meal: {meal_name}")
            print(f"   Ingredients: {ingredients}")
            print(f"   Instructions (first 200): {str(instructions)[:200]}")
        else:
            print(f"✅ No chicken found in alternate meal!")

        assert len(found_chicken) == 0, (
            f"❌ ALTERNATE MEAL FOODS_TO_AVOID BUG: Found chicken keywords {found_chicken} "
            f"in meal '{meal_name}'. Ingredients: {ingredients[:5]}"
        )

        # Verify meal has expected structure
        assert meal_name, "Alternate meal has no name"
        assert len(ingredients) > 0, "Alternate meal has no ingredients"
        print(f"\n✅ Alternate meal chicken-free compliance PASSED: '{meal_name}'")
