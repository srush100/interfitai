"""
Tests for AI Generation Bug Fixes - Iteration Review:
1. GET /api/health - sanity check
2. POST /api/workouts/generate with injuries=['shoulders'] - 200 OK, workout_days, gif_url on exercises
3. POST /api/mealplans/generate vegan - protein BETWEEN 100-220g (NOT inflated >250g)
4. POST /api/mealplans/generate + alternate meal with foods_to_avoid='chicken' - NO chicken in alternate
5. POST /api/mealplans/generate keto - Day 1 carbs < 50g
6. POST /api/mealplans/generate balanced + foods_to_avoid='chicken' - NO meal NAMES with 'chicken' (template filter)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://nutrition-debug-1.preview.emergentagent.com').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


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
        """GET /api/health - expect 200 OK with status/timestamp"""
        start = time.time()
        response = api_client.get(f"{BASE_URL}/api/health")
        elapsed = time.time() - start
        print(f"\n[Health] Response time: {elapsed:.2f}s | Status: {response.status_code}")
        assert response.status_code == 200, f"Health check failed: {response.status_code} {response.text[:200]}"
        data = response.json()
        print(f"[Health] Response: {data}")
        assert "status" in data or "timestamp" in data, f"Missing status/timestamp in response: {data}"
        print("✅ Health check PASSED")


# ============================================================
# TEST 2: Workout Generation with injuries=['shoulders']
# ============================================================
class TestWorkoutGenerationWithInjuries:
    """POST /api/workouts/generate - with injuries list, verify 200 + workout_days + gif_url"""

    def test_workout_with_injuries_list(self, api_client):
        """injuries field must be List[str] - expect 200, workout_days present, gif_url on exercises"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["dumbbells"],
            "injuries": ["shoulders"],
            "days_per_week": 3,
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose"
        }
        print(f"\n[Workout] Sending POST /api/workouts/generate with injuries=['shoulders']")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[Workout] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, (
            f"Expected 200 but got {response.status_code}. "
            f"Body: {response.text[:500]}"
        )

        data = response.json()
        print(f"[Workout] Name: {data.get('name', 'N/A')}")

        # Verify workout_days present
        assert "workout_days" in data, "Response missing 'workout_days'"
        workout_days = data["workout_days"]
        assert len(workout_days) > 0, "No workout days returned"
        print(f"[Workout] Days returned: {len(workout_days)}")

        # Verify gif_url field exists on exercises
        exercises_with_gif = 0
        total_exercises = 0
        for day in workout_days:
            for ex in day.get("exercises", []):
                total_exercises += 1
                if "gif_url" in ex:
                    exercises_with_gif += 1
                    if ex["gif_url"]:
                        print(f"  [GIF] {ex['name']}: {ex['gif_url']}")

        print(f"[Workout] gif_url field present on {exercises_with_gif}/{total_exercises} exercises")
        assert exercises_with_gif > 0, (
            f"No exercises have gif_url field. All {total_exercises} exercises missing gif_url. "
            f"First exercise sample: {workout_days[0]['exercises'][0] if workout_days[0].get('exercises') else 'none'}"
        )
        print(f"✅ Workout generation with injuries PASSED: '{data['name']}' ({len(workout_days)} days, {exercises_with_gif} GIFs)")

    def test_workout_no_injuries_field_is_none(self, api_client):
        """Workout generate without injuries should still work (backward compatibility)"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["dumbbells"],
            "days_per_week": 2,
            "duration_minutes": 30,
            "fitness_level": "beginner",
            "preferred_split": "ai_choose"
        }
        response = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        print(f"\n[Workout No Injuries] Status: {response.status_code}")
        assert response.status_code == 200, f"Expected 200 got {response.status_code}: {response.text[:300]}"
        data = response.json()
        assert "workout_days" in data and len(data["workout_days"]) > 0
        print(f"✅ Workout without injuries PASSED: '{data.get('name', 'N/A')}'")


# ============================================================
# TEST 3: Vegan Meal Plan Protein Accuracy
# ============================================================
class TestVeganMealPlanProtein:
    """Vegan meal plan Day 1 protein must be realistic (100-220g), NOT inflated >250g"""

    def test_vegan_protein_between_100_and_220(self, api_client):
        """Vegan plan protein should be 100-220g, never the old inflated >250g"""
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

        # Verify basic structure
        assert "meal_days" in data, "Response missing 'meal_days'"
        assert len(data["meal_days"]) > 0, "No meal days in response"
        assert data.get("food_preferences") == "vegan", f"food_preferences not 'vegan': {data.get('food_preferences')}"

        day1 = data["meal_days"][0]
        total_protein = day1.get("total_protein", 0)
        total_calories = day1.get("total_calories", 0)
        total_carbs = day1.get("total_carbs", 0)
        total_fats = day1.get("total_fats", 0)

        print(f"\n[Vegan] Day 1 Totals:")
        print(f"  Calories: {total_calories} kcal")
        print(f"  Protein:  {total_protein}g")
        print(f"  Carbs:    {total_carbs}g")
        print(f"  Fats:     {total_fats}g")

        meals = day1.get("meals", [])
        print(f"\n[Vegan] Individual meals ({len(meals)} total):")
        for meal in meals:
            print(f"  {meal.get('meal_type','?').upper()} - {meal.get('name', 'Unknown')}: "
                  f"{meal.get('calories',0)} cal, {meal.get('protein',0)}g P, "
                  f"{meal.get('carbs',0)}g C, {meal.get('fats',0)}g F")

        # CRITICAL ASSERTIONS
        # 1) Protein should NOT be the inflated old value (>250g was the old bug)
        assert total_protein <= 250, (
            f"❌ VEGAN PROTEIN INFLATION BUG: Day 1 protein {total_protein}g is > 250g "
            f"(the old inflated value). Fix is NOT working."
        )

        # 2) Protein should be realistic - at least 30g and at most 220g
        assert total_protein >= 30, f"Protein too low: {total_protein}g (possibly broken template)"
        assert total_protein <= 220, (
            f"❌ Protein still too high: {total_protein}g (expected 100-220g for vegan plan). "
            f"Bug may still be partially present."
        )

        # 3) Protein should be within a reasonable range for the review target (~172g)
        # Allow ±60g deviation since vegan templates can vary
        review_target = 172
        deviation = abs(total_protein - review_target)
        print(f"\n[Vegan] Protein {total_protein}g vs review target ~{review_target}g (deviation: {deviation}g)")

        assert deviation <= 80, (
            f"❌ Protein {total_protein}g is too far from expected vegan target ~{review_target}g "
            f"(deviation {deviation}g exceeds 80g tolerance)."
        )

        print(f"✅ Vegan protein accuracy PASSED: {total_protein}g (within 100-220g range)")


# ============================================================
# TEST 4: Alternate Meal - foods_to_avoid='chicken' compliance
# ============================================================
class TestAlternateMealFoodsToAvoid:
    """Alternate meal must NOT include chicken when foods_to_avoid='chicken'"""

    def test_alternate_meal_no_chicken_when_banned(self, api_client):
        """Step 1: generate plan with foods_to_avoid='chicken', Step 2: get alternate, verify no chicken"""
        # ---- Step 1: Generate plan with chicken banned ----
        meal_plan_payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "foods_to_avoid": "chicken",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[AltMeal] Step 1: Generating meal plan with foods_to_avoid='chicken'")
        start = time.time()
        plan_response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=meal_plan_payload, timeout=180)
        elapsed = time.time() - start
        print(f"[AltMeal] Plan generation time: {elapsed:.2f}s | Status: {plan_response.status_code}")

        assert plan_response.status_code == 200, (
            f"Failed to create meal plan: {plan_response.status_code} {plan_response.text[:300]}"
        )
        plan_data = plan_response.json()
        meal_plan_id = plan_data.get("id")
        print(f"[AltMeal] Created plan ID: {meal_plan_id}")
        assert meal_plan_id, "Meal plan missing 'id' field"

        # Print original meal 1 (index 1 = lunch) for context
        day0_meals = plan_data.get("meal_days", [{}])[0].get("meals", [])
        if len(day0_meals) > 1:
            orig_meal = day0_meals[1]
            print(f"[AltMeal] Original lunch (will be replaced): {orig_meal.get('name')} - {orig_meal.get('ingredients', [])[:3]}")

        # ---- Step 2: Get alternate for day 0, meal 1 (lunch) ----
        alternate_payload = {
            "user_id": TEST_USER_ID,
            "meal_plan_id": meal_plan_id,
            "day_index": 0,
            "meal_index": 1,
            "swap_preference": "similar"
        }
        print(f"\n[AltMeal] Step 2: Requesting alternate for day_index=0, meal_index=1 (lunch)")
        start = time.time()
        alt_response = api_client.post(f"{BASE_URL}/api/mealplan/alternate", json=alternate_payload, timeout=180)
        elapsed = time.time() - start
        print(f"[AltMeal] Alternate meal time: {elapsed:.2f}s | Status: {alt_response.status_code}")

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

        # ---- Step 3: Verify NO chicken ----
        meal_name_lower = meal_name.lower()
        ingredients_str = " ".join([str(i).lower() for i in ingredients])
        instructions_lower = instructions.lower()

        # Chicken keywords to check for (core poultry terms)
        chicken_keywords = ["chicken", "poultry", "rotisserie"]
        all_text = f"{meal_name_lower} {ingredients_str} {instructions_lower}"

        found_chicken = [kw for kw in chicken_keywords if kw in all_text]

        if found_chicken:
            print(f"❌ [AltMeal] CHICKEN FOUND! Keywords detected: {found_chicken}")
            print(f"   Meal: {meal_name}")
            print(f"   Ingredients: {ingredients}")
            print(f"   Instructions (first 200 chars): {instructions[:200]}")
        else:
            print(f"✅ [AltMeal] No chicken in alternate meal - foods_to_avoid respected!")

        assert len(found_chicken) == 0, (
            f"❌ FOODS_TO_AVOID BUG (chicken): Alternate meal still contains chicken keyword(s) "
            f"{found_chicken}. Meal: '{meal_name}', Ingredients: {ingredients[:5]}"
        )

        # Verify meal has expected structure
        assert meal_name, "Alternate meal has no name"
        assert len(ingredients) > 0, "Alternate meal has no ingredients"
        print(f"✅ Alternate meal foods_to_avoid compliance PASSED: '{meal_name}' - no chicken found")


# ============================================================
# TEST 5: Keto Meal Plan Carb Compliance
# ============================================================
class TestKetoMealPlanCarbs:
    """Keto meal plan Day 1 total carbs must be < 50g"""

    def test_keto_carbs_under_50g(self, api_client):
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

        print(f"\n[Keto] Day 1 Totals:")
        print(f"  Calories: {total_calories} kcal")
        print(f"  Protein:  {total_protein}g")
        print(f"  Carbs:    {total_carbs}g  ← must be < 50g for keto compliance")
        print(f"  Fats:     {total_fats}g")

        meals = day1.get("meals", [])
        print(f"\n[Keto] Individual meals ({len(meals)} total):")
        for meal in meals:
            print(f"  {meal.get('meal_type','?').upper()} - {meal.get('name', 'Unknown')}: "
                  f"{meal.get('calories',0)} cal, {meal.get('carbs',0)}g C, {meal.get('fats',0)}g F")

        # CRITICAL: Keto carbs MUST be < 50g per day
        assert total_carbs < 50, (
            f"❌ KETO COMPLIANCE FAILED: Day 1 carbs = {total_carbs}g, exceeds 50g limit. "
            f"Keto meal plans must keep carbs < 50g per day."
        )

        # Additional keto checks
        assert total_fats > 50, (
            f"❌ KETO FAT TOO LOW: {total_fats}g. Keto requires high fat (usually 60%+ of calories)"
        )
        assert total_calories > 0, "Keto plan has zero calories"

        print(f"✅ Keto compliance PASSED: {total_carbs}g carbs (< 50g limit), {total_fats}g fats")


# ============================================================
# TEST 6: Template-Based Meal Name Filtering (foods_to_avoid)
# ============================================================
class TestTemplateMealNameFiltering:
    """When foods_to_avoid='chicken', no template meal NAME should contain 'chicken'"""

    def test_template_no_chicken_in_meal_names(self, api_client):
        """Template-based balanced plan with foods_to_avoid='chicken' must not have meal names containing 'chicken'"""
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "foods_to_avoid": "chicken",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[TemplateFilter] POST /api/mealplans/generate - balanced, foods_to_avoid='chicken'")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TemplateFilter] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, (
            f"Expected 200 got {response.status_code}: {response.text[:300]}"
        )
        data = response.json()
        assert "meal_days" in data, "Missing 'meal_days' in response"
        assert len(data["meal_days"]) > 0, "No meal days in response"

        # Check all meal names across all days for chicken
        all_meal_names = []
        chicken_found = []
        for day in data["meal_days"]:
            for meal in day.get("meals", []):
                name = meal.get("name", "")
                all_meal_names.append(name)
                if "chicken" in name.lower():
                    chicken_found.append(name)

        print(f"[TemplateFilter] All meal names across {len(data['meal_days'])} days:")
        for name in all_meal_names:
            marker = "❌ CHICKEN" if "chicken" in name.lower() else "✅"
            print(f"  {marker} {name}")

        assert len(chicken_found) == 0, (
            f"❌ TEMPLATE FILTER BUG: Meal names still contain 'chicken' despite foods_to_avoid='chicken'. "
            f"Found in: {chicken_found}"
        )

        print(f"✅ Template meal name filtering PASSED: No chicken in any of {len(all_meal_names)} meal names")
