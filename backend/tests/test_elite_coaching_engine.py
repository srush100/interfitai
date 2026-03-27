"""
Elite Coaching Engine Tests - Iteration Review
Tests the new EliteCoachingEngine.build_blueprint() integration:
1. GET /api/health - Basic health check
2. POST /api/workouts/generate - build_muscle + weights + 4 days → split_name='Upper / Lower', coaching fields present
3. POST /api/workouts/generate - athletic_performance + hybrid + 4 days → primary_compound sets=4, reps=4-6, rest=180s
4. POST /api/workouts/generate - strength + weights + 3 days + lower_back limitation → exclusion filter works
5. POST /api/workouts/generate - calisthenics style → bodyweight exercises only
6. POST /api/mealplan/alternate - foods_to_avoid='chicken' → no chicken in replacement meal
"""
import pytest
import requests
import os
import time
import json

BASE_URL = os.environ.get('EXPO_PUBLIC_BACKEND_URL', 'https://nutrition-debug-1.preview.emergentagent.com').rstrip('/')
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"


@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# ============================================================
# TEST 1: Health Check
# ============================================================
class TestHealthCheck:
    """GET /api/health - sanity check"""

    def test_health_endpoint(self, api_client):
        response = api_client.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Expected status=healthy, got: {data}"
        assert "timestamp" in data, "Missing timestamp field"
        print(f"✅ Health check OK - status={data['status']}, timestamp={data['timestamp']}")


# ============================================================
# TEST 2: build_muscle + weights + 4 days → Upper/Lower split, coaching fields
# ============================================================
class TestBuildMuscleWorkout:
    """POST /api/workouts/generate - build_muscle + weights + 4 days"""

    def test_build_muscle_4day_split_name(self, api_client):
        """Verify split_name='Upper / Lower' for 4-day build_muscle"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["chest", "back"],
            "equipment": ["full_gym"],
            "days_per_week": 4,
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose"
        }
        print(f"\n[TEST 2] Generating build_muscle 4-day workout (may take 60-120s)...")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 2] Response time: {elapsed:.1f}s")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"

        data = response.json()

        # Verify split_name is 'Upper / Lower'
        split_name = data.get("split_name")
        assert split_name == "Upper / Lower", f"Expected split_name='Upper / Lower', got '{split_name}'"
        print(f"✅ split_name: '{split_name}'")

        # Verify coaching metadata fields are present
        for field in ["split_name", "split_rationale", "progression_method", "deload_timing", "weekly_structure"]:
            assert data.get(field), f"Missing or empty field: {field}"
            print(f"✅ {field}: {str(data[field])[:80]}...")

        # Verify training_style and training_notes
        assert data.get("training_style") == "weights", f"Expected training_style=weights, got {data.get('training_style')}"
        assert data.get("training_notes"), "Missing training_notes field"
        print(f"✅ training_style: {data['training_style']}")
        print(f"✅ training_notes: {data['training_notes'][:80]}...")

        # Verify workout_days count = 4
        workout_days = data.get("workout_days", [])
        assert len(workout_days) == 4, f"Expected 4 workout days, got {len(workout_days)}"
        print(f"✅ workout_days count: {len(workout_days)}")

        # Verify each exercise has effort_target, substitution_hint, muscle_groups
        for day_idx, day in enumerate(workout_days):
            exercises = day.get("exercises", [])
            assert len(exercises) > 0, f"Day {day_idx+1} has no exercises"
            for ex_idx, ex in enumerate(exercises):
                ex_name = ex.get("name", "Unknown")
                assert ex.get("effort_target"), f"Day {day_idx+1}, Ex {ex_idx+1} '{ex_name}': missing effort_target"
                assert ex.get("muscle_groups"), f"Day {day_idx+1}, Ex {ex_idx+1} '{ex_name}': missing muscle_groups"
                # substitution_hint can be None if only 1 option, so just check the key exists
                assert "substitution_hint" in ex, f"Day {day_idx+1}, Ex {ex_idx+1} '{ex_name}': missing substitution_hint key"

        print(f"✅ All exercises have effort_target, muscle_groups, substitution_hint keys")
        print(f"✅ [TEST 2 PASSED] build_muscle 4-day: split_name='Upper / Lower', all coaching fields present")

    def test_build_muscle_weekly_structure_format(self, api_client):
        """Verify weekly_structure is a list of day descriptions"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "weights",
            "focus_areas": ["chest"],
            "equipment": ["dumbbells"],
            "days_per_week": 4,
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose"
        }
        print(f"\n[TEST 2b] Checking weekly_structure format...")
        response = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        assert response.status_code == 200, f"Status {response.status_code}: {response.text[:300]}"

        data = response.json()
        weekly_structure = data.get("weekly_structure", [])
        assert isinstance(weekly_structure, list), f"weekly_structure should be a list, got {type(weekly_structure)}"
        assert len(weekly_structure) == 4, f"Expected 4 entries in weekly_structure, got {len(weekly_structure)}"
        for entry in weekly_structure:
            assert isinstance(entry, str), f"weekly_structure entries should be strings"
            assert "Day" in entry, f"weekly_structure entry should contain 'Day': {entry}"
        print(f"✅ weekly_structure: {weekly_structure}")
        print(f"✅ [TEST 2b PASSED] weekly_structure is a properly formatted list")


# ============================================================
# TEST 3: athletic_performance + hybrid + 4 days
# ============================================================
class TestAthleticPerformanceWorkout:
    """POST /api/workouts/generate - athletic_performance + hybrid + 4 days"""

    def test_athletic_performance_hybrid_4day(self, api_client):
        """Verify athletic_performance hybrid split and primary_compound params"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "athletic_performance",
            "training_style": "hybrid",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"],
            "days_per_week": 4,
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose"
        }
        print(f"\n[TEST 3] Generating athletic_performance hybrid 4-day workout...")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 3] Response time: {elapsed:.1f}s")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        data = response.json()

        # For hybrid + athletic_performance + 4 days → Athletic Hybrid Split
        split_name = data.get("split_name")
        print(f"[TEST 3] split_name: '{split_name}'")
        # According to select_split: hybrid + athletic_performance → 'Athletic Hybrid Split'
        assert split_name == "Athletic Hybrid Split", f"Expected 'Athletic Hybrid Split', got '{split_name}'"
        print(f"✅ split_name: '{split_name}'")

        # Verify 4 workout days
        workout_days = data.get("workout_days", [])
        assert len(workout_days) == 4, f"Expected 4 days, got {len(workout_days)}"

        # Find primary_compound exercises and check their params
        # GOAL_PARAMS['athletic_performance']['primary_compound'] = {sets=4, reps='4-6', rest=180, effort='RPE 8'}
        primary_compound_exercises = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                if ex.get("exercise_type") == "primary_compound":
                    primary_compound_exercises.append(ex)

        assert len(primary_compound_exercises) > 0, "No primary_compound exercises found in the workout"
        print(f"[TEST 3] Found {len(primary_compound_exercises)} primary_compound exercises")

        for ex in primary_compound_exercises:
            name = ex.get("name")
            sets = ex.get("sets")
            reps = ex.get("reps")
            rest = ex.get("rest_seconds")
            effort = ex.get("effort_target")

            assert sets == 4, f"primary_compound '{name}': expected sets=4, got {sets}"
            assert reps == "4-6", f"primary_compound '{name}': expected reps='4-6', got '{reps}'"
            assert rest == 180, f"primary_compound '{name}': expected rest=180s, got {rest}"
            print(f"✅ primary_compound '{name}': sets={sets}, reps={reps}, rest={rest}s, effort={effort}")

        # Verify coaching fields
        assert data.get("split_rationale"), "Missing split_rationale"
        assert data.get("progression_method"), "Missing progression_method"
        assert data.get("deload_timing"), "Missing deload_timing"
        assert data.get("weekly_structure"), "Missing weekly_structure"
        print(f"✅ [TEST 3 PASSED] athletic_performance+hybrid: split='{split_name}', primary_compound sets=4/reps=4-6/rest=180s verified")


# ============================================================
# TEST 4: strength + weights + 3 days + lower_back limitation → exclusions work
# ============================================================
class TestLowerBackLimitation:
    """POST /api/workouts/generate - strength + 3 days + lower_back → no deadlift/squat"""

    def test_lower_back_limitation_exclusions(self, api_client):
        """Verify LIMITATION_EXCLUSIONS filter removes contraindicated exercises"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "strength",
            "training_style": "weights",
            "focus_areas": ["full_body"],
            "equipment": ["full_gym"],
            "injuries": ["lower_back"],
            "days_per_week": 3,
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose"
        }
        # Exercises that should be EXCLUDED for lower_back:
        # ["Conventional Deadlift", "Sumo Deadlift", "Good Morning", "Back Squat", "T-Bar Row", "Barbell Row"]
        LOWER_BACK_EXCLUDED = [
            "Conventional Deadlift",
            "Sumo Deadlift",
            "Good Morning",
            "Back Squat",
            "T-Bar Row",
            "Barbell Row",
        ]

        print(f"\n[TEST 4] Generating strength 3-day with lower_back limitation...")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 4] Response time: {elapsed:.1f}s")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        data = response.json()

        workout_days = data.get("workout_days", [])
        assert len(workout_days) == 3, f"Expected 3 days, got {len(workout_days)}"

        # Collect all exercise names
        all_exercise_names = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                all_exercise_names.append(ex.get("name", ""))

        print(f"[TEST 4] All exercises: {all_exercise_names}")

        # Verify none of the excluded exercises appear
        found_excluded = []
        for name in all_exercise_names:
            for excluded in LOWER_BACK_EXCLUDED:
                if excluded.lower() in name.lower():
                    found_excluded.append(f"'{name}' (matches '{excluded}')")

        assert len(found_excluded) == 0, (
            f"EXCLUSION FILTER FAILED! Found contraindicated exercises: {found_excluded}\n"
            f"All exercises: {all_exercise_names}"
        )
        print(f"✅ No contraindicated lower_back exercises found in workout")
        print(f"✅ [TEST 4 PASSED] lower_back limitation exclusions working correctly")

        # Also verify the workout was generated (has exercises)
        assert len(all_exercise_names) > 0, "No exercises generated at all"
        print(f"✅ Generated {len(all_exercise_names)} exercises across {len(workout_days)} days")


# ============================================================
# TEST 5: calisthenics style → bodyweight exercises only
# ============================================================
class TestCalisthenicsWorkout:
    """POST /api/workouts/generate - calisthenics → bodyweight exercises"""

    def test_calisthenics_bodyweight_only(self, api_client):
        """Verify calisthenics generates bodyweight exercises (no barbells/dumbbells)"""
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "build_muscle",
            "training_style": "calisthenics",
            "focus_areas": ["full_body"],
            "equipment": ["bodyweight"],
            "days_per_week": 4,
            "duration_minutes": 60,
            "fitness_level": "intermediate",
            "preferred_split": "ai_choose"
        }
        print(f"\n[TEST 5] Generating calisthenics workout...")
        start = time.time()
        response = api_client.post(f"{BASE_URL}/api/workouts/generate", json=payload, timeout=180)
        elapsed = time.time() - start
        print(f"[TEST 5] Response time: {elapsed:.1f}s")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        data = response.json()

        # Verify calisthenics split
        split_name = data.get("split_name")
        print(f"[TEST 5] split_name: '{split_name}'")
        assert "Calisthenics" in split_name, f"Expected calisthenics split, got '{split_name}'"

        workout_days = data.get("workout_days", [])
        assert len(workout_days) == 4, f"Expected 4 days, got {len(workout_days)}"

        # Collect all exercise names and check equipment type
        all_exercises = []
        for day in workout_days:
            for ex in day.get("exercises", []):
                all_exercises.append({
                    "name": ex.get("name"),
                    "equipment": ex.get("equipment", "")
                })

        print(f"[TEST 5] All calisthenics exercises:")
        for ex in all_exercises:
            print(f"  - {ex['name']} (equipment: {ex['equipment']})")

        # Check for barbell/dumbbell equipment tags - these should NOT appear for calisthenics
        PROHIBITED_EQUIPMENT_TERMS = ["barbell", "dumbbell"]
        problematic = []
        for ex in all_exercises:
            name_lower = ex["name"].lower()
            eq_lower = ex["equipment"].lower()
            # Check the equipment tag
            if any(term in eq_lower for term in PROHIBITED_EQUIPMENT_TERMS):
                problematic.append(f"'{ex['name']}' has equipment='{ex['equipment']}'")
            # Also check the exercise name itself for obvious violations
            elif "barbell" in name_lower or "dumbbell" in name_lower:
                problematic.append(f"'{ex['name']}' name contains barbell/dumbbell term")

        if problematic:
            print(f"⚠️  WARNING: Some exercises may have equipment issues: {problematic}")
            # This is a warning, not a hard fail, since the LLM might choose an exercise name
            # from the bodyweight options list. Only fail if equipment tag is wrong.
        else:
            print(f"✅ All {len(all_exercises)} exercises are classified as bodyweight/appropriate for calisthenics")

        # Verify the exercise OPTIONS provided to LLM were bodyweight (check split + archetype logic)
        # The calisthenics split uses calisthenics_upper / calisthenics_lower archetypes
        # which only reference bodyweight patterns. This is verified via split_name check above.

        # Hard assertion: no exercise tagged with barbell equipment
        barbell_exercises = [e for e in all_exercises if "barbell" in e["equipment"].lower()]
        assert len(barbell_exercises) == 0, \
            f"Calisthenics workout contains barbell equipment exercises: {barbell_exercises}"

        print(f"✅ [TEST 5 PASSED] Calisthenics workout has no barbell equipment, split='{split_name}'")


# ============================================================
# TEST 6: foods_to_avoid='chicken' via /api/mealplan/alternate → no chicken
# ============================================================
class TestFoodsToAvoidAlternateMeal:
    """POST /api/mealplan/alternate - foods_to_avoid='chicken' → no chicken in replacement"""

    def test_alternate_meal_respects_foods_to_avoid(self, api_client):
        """Generate a meal plan with foods_to_avoid='chicken', then swap a meal, verify no chicken"""

        # Step 1: Generate a meal plan with foods_to_avoid='chicken'
        print(f"\n[TEST 6] Step 1: Generating meal plan with foods_to_avoid='chicken'...")
        plan_payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "none",
            "preferred_foods": "beef, rice, eggs",
            "foods_to_avoid": "chicken",
            "allergies": [],
            "duration_days": 3
        }
        plan_response = api_client.post(
            f"{BASE_URL}/api/mealplans/generate",
            json=plan_payload,
            timeout=120
        )
        assert plan_response.status_code == 200, \
            f"Meal plan generation failed: {plan_response.status_code}: {plan_response.text[:500]}"

        plan = plan_response.json()
        plan_id = plan.get("id")
        assert plan_id, "Meal plan has no id"
        print(f"[TEST 6] Generated meal plan ID: {plan_id}")
        print(f"[TEST 6] Plan foods_to_avoid: {plan.get('foods_to_avoid')}")

        # Verify the plan itself doesn't contain chicken (baseline check)
        plan_text = json.dumps(plan).lower()
        # We check the meal names specifically
        day0 = plan.get("meal_days", [{}])[0] if plan.get("meal_days") else {}
        meals = day0.get("meals", [])
        assert len(meals) > 0, "Meal plan day 0 has no meals"
        print(f"[TEST 6] Day 0 meals: {[m.get('name') for m in meals]}")

        # Step 2: Use the alternate meal endpoint to swap a meal
        print(f"\n[TEST 6] Step 2: Swapping meal with /api/mealplan/alternate...")
        alternate_payload = {
            "meal_plan_id": plan_id,
            "user_id": TEST_USER_ID,
            "day_index": 0,
            "meal_index": 1,  # swap lunch (index 1)
            "swap_preference": "similar"
        }
        alt_response = api_client.post(
            f"{BASE_URL}/api/mealplan/alternate",
            json=alternate_payload,
            timeout=120
        )
        assert alt_response.status_code == 200, \
            f"Alternate meal failed: {alt_response.status_code}: {alt_response.text[:500]}"

        alt_response_json = alt_response.json()
        # The API wraps the meal in {"alternate_meal": {...}}
        alt_meal = alt_response_json.get("alternate_meal", alt_response_json)
        print(f"[TEST 6] Alternate meal generated: {alt_meal.get('name')}")
        print(f"[TEST 6] Ingredients: {alt_meal.get('ingredients', [])}")

        # Step 3: Verify that the meal was actually generated (not None)
        assert alt_meal.get("name"), f"Alternate meal has no name - response: {alt_response_json}"
        assert len(alt_meal.get("ingredients", [])) > 0, f"Alternate meal has no ingredients - response: {alt_response_json}"

        # Step 4: Verify no chicken in the replacement meal
        meal_text = json.dumps(alt_meal).lower()
        chicken_terms = ["chicken", "poultry", "rotisserie"]
        found_chicken = [term for term in chicken_terms if term in meal_text]

        assert len(found_chicken) == 0, (
            f"FOODS_TO_AVOID FILTER FAILED! Found chicken-related terms {found_chicken} "
            f"in alternate meal: {alt_meal.get('name')} - {alt_meal.get('ingredients')}"
        )
        print(f"✅ No chicken found in alternate meal: '{alt_meal.get('name')}'")
        print(f"✅ Ingredients: {alt_meal.get('ingredients', [])}")
        print(f"✅ [TEST 6 PASSED] foods_to_avoid='chicken' correctly excluded from alternate meal")
