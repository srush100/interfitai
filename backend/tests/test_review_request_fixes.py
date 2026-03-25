"""
Review Request Tests - InterFitAI Bug Fix Verification (2026-03-25 New Fork)
Tests for recent backend fixes:
1. Health Check - GET /api/health
2. Vegan Meal Plan Protein Accuracy - protein between 100-220g (NOT inflated >250g)
3. Alternate Meal foods_to_avoid Compliance - food_preferences='none', foods_to_avoid='chicken' -> NO chicken in alternate
4. Keto Meal Plan Carb Compliance - Day 1 total_carbs < 50g
5. Workout Generation with GIFs - injuries=List[str], gif_url on exercises
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://nutrition-debug-1.preview.emergentagent.com').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session with JSON content type"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()


@pytest.fixture(scope="module", autouse=True)
def ensure_test_user(api_client):
    """Ensure test user exists, create if missing (404 case)"""
    response = api_client.get(f"{BASE_URL}/api/profile/{TEST_USER_ID}", timeout=15)
    if response.status_code == 404:
        print(f"\n[Setup] Test user not found - creating profile for {TEST_USER_ID}")
        create_resp = api_client.post(f"{BASE_URL}/api/profile", json={
            "user_id": TEST_USER_ID,
            "name": "TestUser",
            "gender": "male",
            "age": 30,
            "height": 175,
            "weight": 80,
            "activity_level": "moderate",
            "goal": "build_muscle"
        }, timeout=30)
        if create_resp.status_code in (200, 201):
            print(f"[Setup] ✅ Test user created successfully")
        else:
            print(f"[Setup] ⚠️ Could not create user: {create_resp.status_code} {create_resp.text[:200]}")
    else:
        data = response.json()
        print(f"\n[Setup] ✅ Test user exists: {data.get('name')} (macros: {data.get('calculated_macros', {}).get('calories')} cal, {data.get('calculated_macros', {}).get('protein')}g P)")
    yield


# ============================================================
# TEST 1: Health Check
# ============================================================
class TestHealthCheck:
    """Sanity check - server must be up and respond 200"""

    def test_health_returns_200(self, api_client):
        """GET /api/health - expect 200 OK with status/timestamp"""
        start = time.time()
        response = api_client.get(f"{BASE_URL}/api/health", timeout=15)
        elapsed = time.time() - start
        print(f"\n[TEST 1 - Health] Response time: {elapsed:.2f}s | Status: {response.status_code}")
        assert response.status_code == 200, f"Health check failed: {response.status_code} {response.text[:200]}"
        data = response.json()
        print(f"[TEST 1 - Health] Response: {data}")
        assert "status" in data or "timestamp" in data, f"Missing status/timestamp: {data}"
        print("✅ TEST 1 PASSED: Health check OK")


# ============================================================
# TEST 2: Vegan Meal Plan Protein Accuracy
# ============================================================
class TestVeganProteinAccuracy:
    """Vegan meal plan - protein must be between 100-220g, NOT inflated >250g"""

    def test_vegan_protein_not_inflated(self, api_client):
        """
        POST /api/mealplans/generate with food_preferences='vegan'
        VERIFY: Day 1 protein BETWEEN 100g-220g (NOT > 250g = old inflation bug)
        Target is ~170g. FAIL if protein > 250g.
        """
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "vegan",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[TEST 2 - Vegan Protein] POST /api/mealplans/generate food_preferences='vegan'")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 2 - Vegan Protein] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, (
            f"Expected 200 but got {response.status_code}. Body: {response.text[:500]}"
        )

        data = response.json()
        assert "meal_days" in data, f"Response missing 'meal_days'. Keys: {list(data.keys())}"
        assert len(data["meal_days"]) > 0, "No meal days in response"

        day1 = data["meal_days"][0]
        total_protein = day1.get("total_protein", 0)
        total_calories = day1.get("total_calories", 0)
        total_carbs = day1.get("total_carbs", 0)
        total_fats = day1.get("total_fats", 0)

        print(f"\n[TEST 2 - Vegan Protein] Day 1 Totals:")
        print(f"  Calories: {total_calories} kcal")
        print(f"  Protein:  {total_protein}g   ← target ~170g, must be 100-220g (NOT >250g)")
        print(f"  Carbs:    {total_carbs}g")
        print(f"  Fats:     {total_fats}g")

        meals = day1.get("meals", [])
        print(f"\n[TEST 2 - Vegan Protein] Individual meals ({len(meals)}):")
        for meal in meals:
            print(f"  [{meal.get('meal_type','?').upper()}] {meal.get('name','?')}: "
                  f"{meal.get('calories',0)}cal, {meal.get('protein',0)}g P, "
                  f"{meal.get('carbs',0)}g C, {meal.get('fats',0)}g F")

        # CRITICAL: Must NOT be inflated (old bug = >250g)
        assert total_protein <= 250, (
            f"❌ VEGAN PROTEIN INFLATION BUG: Day 1 protein = {total_protein}g > 250g. "
            f"Old inflation bug is back! scale_day_to_targets() is_plant_based_diet bypass NOT working."
        )

        # Must be within realistic range
        assert total_protein >= 100, (
            f"❌ Protein too low: {total_protein}g. Expected at least 100g for a muscle-building user."
        )
        assert total_protein <= 220, (
            f"❌ Protein too high: {total_protein}g. Vegan plan should be ≤ 220g (target ~170g). "
            f"Possible partial inflation bug."
        )

        deviation = abs(total_protein - 170)
        print(f"\n[TEST 2 - Vegan Protein] Deviation from 170g target: {deviation}g")

        print(f"✅ TEST 2 PASSED: Vegan protein = {total_protein}g (within 100-220g range, target ~170g)")


# ============================================================
# TEST 3: Alternate Meal - foods_to_avoid='chicken' compliance
# ============================================================
class TestAlternateChickenBan:
    """
    Critical recurring bug: alternate meal ignores foods_to_avoid.
    Fix uses PROTEIN_GROUPS filtering + 3-attempt retry + post-validation.
    """

    def test_alternate_no_chicken_when_avoided(self, api_client):
        """
        Step 1: Generate plan with food_preferences='none', foods_to_avoid='chicken'
        Step 2: POST /api/mealplan/alternate with plan_id, day_index=0, meal_index=1, swap_preference='similar'
        VERIFY: alternate meal name, ingredients, instructions contain NO mention of chicken
        """
        # ---- Step 1: Generate base meal plan ----
        plan_payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "none",
            "foods_to_avoid": "chicken",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[TEST 3 - Alternate/NoChicken] Step 1: Generating plan with food_preferences='none', foods_to_avoid='chicken'")
        start = time.time()
        plan_resp = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=plan_payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 3] Plan generation: {elapsed:.2f}s | Status: {plan_resp.status_code}")

        assert plan_resp.status_code == 200, (
            f"Failed to generate base plan: {plan_resp.status_code} {plan_resp.text[:400]}"
        )
        plan_data = plan_resp.json()
        plan_id = plan_data.get("id")
        assert plan_id, f"No 'id' in plan response. Keys: {list(plan_data.keys())}"
        print(f"[TEST 3] Plan ID: {plan_id}")

        # Show the original lunch for context
        day0 = plan_data.get("meal_days", [{}])[0]
        meals_day0 = day0.get("meals", [])
        if len(meals_day0) > 1:
            orig = meals_day0[1]
            print(f"[TEST 3] Original Day 0 Meal 1 (to be swapped): '{orig.get('name')}' | {orig.get('ingredients', [])[:4]}")
        else:
            print(f"[TEST 3] Only {len(meals_day0)} meals in Day 0 - using meal_index=0 instead of 1")
            # Adjust if fewer meals
            meal_index = min(1, len(meals_day0) - 1)
        meal_index = 1 if len(meals_day0) > 1 else 0

        # ---- Step 2: Request alternate meal ----
        alt_payload = {
            "user_id": TEST_USER_ID,
            "meal_plan_id": plan_id,
            "day_index": 0,
            "meal_index": meal_index,
            "swap_preference": "similar"
        }
        print(f"\n[TEST 3] Step 2: POST /api/mealplan/alternate day_index=0, meal_index={meal_index}, swap='similar'")
        start = time.time()
        alt_resp = api_client.post(f"{BASE_URL}/api/mealplan/alternate", json=alt_payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 3] Alternate meal: {elapsed:.2f}s | Status: {alt_resp.status_code}")

        assert alt_resp.status_code == 200, (
            f"Alternate meal endpoint failed: {alt_resp.status_code} {alt_resp.text[:400]}"
        )

        alt_data = alt_resp.json()
        # Handle both response envelope formats
        meal_obj = alt_data.get("alternate_meal") or alt_data
        meal_name = meal_obj.get("name", "")
        ingredients = meal_obj.get("ingredients", [])
        instructions = meal_obj.get("instructions", "")

        print(f"[TEST 3] Alternate meal: '{meal_name}'")
        print(f"[TEST 3] Ingredients: {ingredients}")
        print(f"[TEST 3] Instructions (first 300): {instructions[:300]}")

        # ---- Step 3: Check for chicken keywords ----
        # PROTEIN_GROUPS expands 'chicken' to include grilled chicken, chicken breast, poultry
        chicken_keywords = [
            "chicken", "grilled chicken", "chicken breast", "poultry",
            "rotisserie chicken", "chicken thigh", "chicken leg"
        ]
        all_text = f"{meal_name} {' '.join(str(i) for i in ingredients)} {instructions}".lower()

        violations = [kw for kw in chicken_keywords if kw in all_text]

        if violations:
            print(f"\n❌ [TEST 3] CHICKEN FOUND - foods_to_avoid NOT respected!")
            print(f"   Detected keywords: {violations}")
            print(f"   Full text checked: {all_text[:500]}")
        else:
            print(f"\n✅ [TEST 3] No chicken keywords in alternate meal - PROTEIN_GROUPS filter working!")

        assert len(violations) == 0, (
            f"❌ FOODS_TO_AVOID BUG: Alternate meal contains banned chicken keyword(s): {violations}. "
            f"Meal: '{meal_name}'. Ingredients: {ingredients[:8]}. "
            f"PROTEIN_GROUPS filtering and retry logic not working."
        )

        # Structural validation
        assert meal_name, "Alternate meal has no name"
        assert len(ingredients) > 0, "Alternate meal has no ingredients"
        macros_ok = meal_obj.get("calories", 0) > 0 or meal_obj.get("protein", 0) >= 0
        print(f"[TEST 3] Macros: {meal_obj.get('calories',0)}cal, {meal_obj.get('protein',0)}g P")
        print(f"✅ TEST 3 PASSED: Alternate meal '{meal_name}' contains no chicken - foods_to_avoid respected!")


# ============================================================
# TEST 4: Keto Meal Plan Carb Compliance
# ============================================================
class TestKetoCarbs:
    """POST /api/mealplans/generate keto - Day 1 carbs must be < 50g (keto compliance)"""

    def test_keto_day1_carbs_under_50g(self, api_client):
        """
        food_preferences='keto' - verify Day 1 total_carbs < 50g.
        Fix: is_low_carb=True bypasses macro inflation and keeps carbs low.
        """
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "keto",
            "supplements": [],
            "allergies": []
        }
        print(f"\n[TEST 4 - Keto] POST /api/mealplans/generate food_preferences='keto'")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/mealplans/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 4 - Keto] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        assert response.status_code == 200, (
            f"Expected 200 but got {response.status_code}. Body: {response.text[:500]}"
        )

        data = response.json()
        assert "meal_days" in data, f"Response missing 'meal_days'. Keys: {list(data.keys())}"
        assert len(data["meal_days"]) > 0, "No meal days in keto response"
        assert data.get("food_preferences") == "keto", (
            f"food_preferences should be 'keto', got: {data.get('food_preferences')}"
        )

        day1 = data["meal_days"][0]
        total_carbs = day1.get("total_carbs", 0)
        total_calories = day1.get("total_calories", 0)
        total_protein = day1.get("total_protein", 0)
        total_fats = day1.get("total_fats", 0)

        print(f"\n[TEST 4 - Keto] Day 1 Totals:")
        print(f"  Calories: {total_calories} kcal")
        print(f"  Protein:  {total_protein}g")
        print(f"  Carbs:    {total_carbs}g   ← MUST be < 50g for keto compliance")
        print(f"  Fats:     {total_fats}g")

        meals = day1.get("meals", [])
        print(f"\n[TEST 4 - Keto] Individual meals ({len(meals)}):")
        for meal in meals:
            print(f"  [{meal.get('meal_type','?').upper()}] {meal.get('name','?')}: "
                  f"{meal.get('carbs',0)}g C, {meal.get('fats',0)}g F, {meal.get('protein',0)}g P")

        # CRITICAL: Keto requires < 50g carbs
        assert total_carbs < 50, (
            f"❌ KETO COMPLIANCE FAILED: Day 1 carbs = {total_carbs}g, exceeds 50g limit! "
            f"is_low_carb=True bypass is NOT working. Check scale_day_to_targets() in server.py."
        )

        # Keto should be high fat
        assert total_fats > 50, (
            f"❌ KETO FAT TOO LOW: {total_fats}g. Keto must be high fat (typically 60%+ of calories)."
        )

        assert total_calories > 500, f"Keto plan calories too low: {total_calories}"

        print(f"✅ TEST 4 PASSED: Keto carbs = {total_carbs}g (< 50g limit), fats = {total_fats}g")


# ============================================================
# TEST 5: Workout Generation with GIF URLs
# ============================================================
class TestWorkoutWithGIFs:
    """
    POST /api/workouts/generate with injuries=['shoulders']
    VERIFY: 200 OK, workout_days array present with exercises, gif_url field present on exercises.
    """

    def test_workout_200_with_gif_urls(self, api_client):
        """
        Exact params from review request:
        goal='build_muscle', focus_areas=['chest'], equipment=['dumbbells'],
        injuries=['shoulders'], duration_weeks=4, sessions_per_week=3, experience_level='intermediate'
        """
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["dumbbells"],
            "injuries": ["shoulders"],
            "days_per_week": 3,       # sessions_per_week: 3
            "duration_minutes": 60,
            "fitness_level": "intermediate",  # experience_level: 'intermediate'
            "preferred_split": "ai_choose"
        }
        print(f"\n[TEST 5 - Workout GIFs] POST /api/workouts/generate")
        print(f"  injuries: {payload['injuries']}, days_per_week: {payload['days_per_week']}, "
              f"level: {payload['fitness_level']}")

        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 5 - Workout GIFs] Response time: {elapsed:.2f}s | Status: {response.status_code}")

        # 200 OK check
        assert response.status_code == 200, (
            f"Expected 200 but got {response.status_code}. Body: {response.text[:500]}"
        )

        data = response.json()
        print(f"[TEST 5 - Workout GIFs] Program: '{data.get('name', 'N/A')}'")

        # workout_days present and non-empty
        assert "workout_days" in data, f"Response missing 'workout_days'. Keys: {list(data.keys())}"
        workout_days = data["workout_days"]
        assert len(workout_days) > 0, "workout_days array is empty"
        print(f"[TEST 5 - Workout GIFs] Workout days: {len(workout_days)}")

        # gif_url must be present as a field on exercises (value can be empty string but field must exist)
        gif_field_present = 0
        gif_url_populated = 0
        total_exercises = 0

        for i, day in enumerate(workout_days):
            exercises = day.get("exercises", [])
            print(f"\n[TEST 5] Day {i+1}: {day.get('focus', 'N/A')} ({len(exercises)} exercises)")
            for ex in exercises:
                total_exercises += 1
                has_gif_field = "gif_url" in ex
                gif_val = ex.get("gif_url", None)

                if has_gif_field:
                    gif_field_present += 1
                if gif_val:
                    gif_url_populated += 1

                print(f"  {ex.get('name','?')}: sets={ex.get('sets','?')}, reps={ex.get('reps','?')}, "
                      f"gif_url={'✅ '+str(gif_val)[:40] if gif_val else ('FIELD_EXISTS(empty)' if has_gif_field else '❌ MISSING_FIELD')}")

        print(f"\n[TEST 5 - Workout GIFs] Summary:")
        print(f"  Total exercises: {total_exercises}")
        print(f"  gif_url field present: {gif_field_present}/{total_exercises}")
        print(f"  gif_url populated (non-empty): {gif_url_populated}/{total_exercises}")

        # CRITICAL: gif_url field must exist on all exercises
        assert gif_field_present == total_exercises, (
            f"❌ GIF FIELD MISSING: Only {gif_field_present}/{total_exercises} exercises have 'gif_url' field. "
            f"Exercise model requires gif_url: Optional[str] = None."
        )

        # At least some exercises should have actual GIF URLs
        assert gif_url_populated > 0, (
            f"❌ NO GIF URLs POPULATED: All {total_exercises} exercises have empty gif_url. "
            f"get_exercise_gif_from_api() may not be working. "
            f"Sample exercise: {workout_days[0]['exercises'][0] if workout_days[0].get('exercises') else 'none'}"
        )

        # Verify injuries field is stored as list
        injuries_stored = data.get("injuries", None)
        print(f"\n[TEST 5 - Workout GIFs] Injuries stored: {injuries_stored} (type: {type(injuries_stored).__name__})")
        assert isinstance(injuries_stored, list), (
            f"❌ injuries should be List[str], got {type(injuries_stored).__name__}: {injuries_stored}"
        )
        assert "shoulders" in injuries_stored, (
            f"❌ 'shoulders' not in stored injuries list: {injuries_stored}"
        )

        print(f"✅ TEST 5 PASSED: Workout '{data['name']}' - {len(workout_days)} days, "
              f"{gif_url_populated}/{total_exercises} exercises have GIF URLs, "
              f"injuries={injuries_stored}")
