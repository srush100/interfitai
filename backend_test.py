#!/usr/bin/env python3
"""
Backend Testing Script for InterFitAI
Testing meal plan macro accuracy and alternate meals as requested in review
"""
import requests
import json
import time
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# Test user ID from review request
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

class MealPlanTester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
    
    def log_test(self, test_name, status, message, response_time=None):
        """Log test result"""
        result = {
            'test': test_name,
            'status': status,  # 'PASS' or 'FAIL'
            'message': message,
            'response_time': response_time,
            'timestamp': datetime.now().isoformat()
        }
        self.test_results.append(result)
        status_symbol = "✅" if status == 'PASS' else "❌"
        print(f"{status_symbol} {test_name}: {message}")
        if response_time:
            print(f"   Response time: {response_time:.2f}s")
    
    def test_meal_plan_generation_with_macro_accuracy(self):
        """TEST 1: Meal Plan with No Preference (should hit exact macros)"""
        print("\n" + "="*60)
        print("TEST 1: MEAL PLAN MACRO ACCURACY")
        print("="*60)
        
        # Request payload from review
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "none",
            "preferred_foods": "chicken, rice, eggs"
        }
        
        start_time = time.time()
        try:
            response = self.session.post(
                f"{BACKEND_URL}/mealplans/generate",
                json=payload,
                timeout=120
            )
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                self.log_test(
                    "Meal Plan Generation API",
                    "FAIL", 
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    response_time
                )
                return None
                
            data = response.json()
            
            # Get Day 1 data from meal_days structure
            days = data.get('meal_days', [])
            if not days:
                self.log_test(
                    "Meal Plan Structure",
                    "FAIL",
                    "No meal_days found in meal plan response",
                    response_time
                )
                return None
            
            day_1 = days[0]
            meals = day_1.get('meals', [])
            
            # Get the daily totals (post-processed for accuracy)
            total_calories = day_1.get('total_calories', 0)
            total_protein = day_1.get('total_protein', 0)
            total_carbs = day_1.get('total_carbs', 0)
            total_fats = day_1.get('total_fats', 0)
            
            # Check ingredients specificity and show meal breakdown
            specific_ingredients_found = 0
            vague_ingredients_found = 0
            
            print(f"\nDAY 1 MEALS BREAKDOWN:")
            for i, meal in enumerate(meals, 1):
                meal_name = meal.get('name', 'Unknown')
                calories = meal.get('calories', 0)
                protein = meal.get('protein', 0)
                carbs = meal.get('carbs', 0)
                fats = meal.get('fats', 0)
                
                print(f"Meal {i} - {meal_name}: {calories}cal, {protein}g P, {carbs}g C, {fats}g F")
                
                # Check ingredients specificity
                ingredients = meal.get('ingredients', [])
                for ingredient in ingredients:
                    ingredient_text = ingredient.get('name', '') if isinstance(ingredient, dict) else str(ingredient)
                    # Look for specific quantities like "200g chicken breast"
                    if any(unit in ingredient_text.lower() for unit in ['g ', 'ml ', 'oz ', 'cup', 'tbsp']):
                        specific_ingredients_found += 1
                    elif ingredient_text.strip() and len(ingredient_text.split()) > 1:
                        specific_ingredients_found += 1
                    else:
                        vague_ingredients_found += 1
            
            # Target macros from review request
            target_calories = 2273
            target_protein = 170
            target_carbs = 227
            target_fats = 76
            
            print(f"\nDAY 1 TOTALS (POST-PROCESSED):")
            print(f"Actual Total: {total_calories}cal, {total_protein}g P, {total_carbs}g C, {total_fats}g F")
            print(f"Target:      {target_calories}cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
            
            # Check accuracy (±10% tolerance)
            cal_diff = abs(total_calories - target_calories)
            protein_diff = abs(total_protein - target_protein)
            carbs_diff = abs(total_carbs - target_carbs)
            fats_diff = abs(total_fats - target_fats)
            
            cal_tolerance = target_calories * 0.10  # ±10%
            protein_tolerance = target_protein * 0.10  # ±10%
            carbs_tolerance = target_carbs * 0.10  # ±10%
            fats_tolerance = target_fats * 0.10  # ±10%
            
            accuracy_status = (
                cal_diff <= cal_tolerance and
                protein_diff <= protein_tolerance and
                carbs_diff <= carbs_tolerance and
                fats_diff <= fats_tolerance
            )
            
            accuracy_details = []
            if cal_diff <= cal_tolerance:
                accuracy_details.append(f"Calories ✅ (±{cal_diff})")
            else:
                accuracy_details.append(f"Calories ❌ (±{cal_diff}, tolerance: ±{cal_tolerance:.1f})")
            
            if protein_diff <= protein_tolerance:
                accuracy_details.append(f"Protein ✅ (±{protein_diff}g)")
            else:
                accuracy_details.append(f"Protein ❌ (±{protein_diff}g, tolerance: ±{protein_tolerance:.1f}g)")
            
            if carbs_diff <= carbs_tolerance:
                accuracy_details.append(f"Carbs ✅ (±{carbs_diff}g)")
            else:
                accuracy_details.append(f"Carbs ❌ (±{carbs_diff}g, tolerance: ±{carbs_tolerance:.1f}g)")
            
            if fats_diff <= fats_tolerance:
                accuracy_details.append(f"Fats ✅ (±{fats_diff}g)")
            else:
                accuracy_details.append(f"Fats ❌ (±{fats_diff}g, tolerance: ±{fats_tolerance:.1f}g)")
            
            print(f"\nACCURACY CHECK: {' | '.join(accuracy_details)}")
            
            # Check ingredients specificity
            ingredients_specific = specific_ingredients_found > vague_ingredients_found
            sample_ingredient = "N/A"
            if meals and meals[0].get('ingredients'):
                first_ingredient = meals[0]['ingredients'][0]
                sample_ingredient = first_ingredient.get('name', '') if isinstance(first_ingredient, dict) else str(first_ingredient)
            
            print(f"\nINGREDIENT SPECIFICITY:")
            print(f"Specific ingredients: {specific_ingredients_found}")
            print(f"Vague ingredients: {vague_ingredients_found}")
            print(f"Sample ingredient: '{sample_ingredient}'")
            
            # Log results
            self.log_test(
                "Meal Plan Macro Accuracy",
                "PASS" if accuracy_status else "FAIL",
                f"Accuracy: {'Within 10%' if accuracy_status else 'Exceeds 10%'} - " + ", ".join(accuracy_details),
                response_time
            )
            
            self.log_test(
                "Ingredient Specificity",
                "PASS" if ingredients_specific else "FAIL",
                f"Sample: '{sample_ingredient[:50]}...' ({'Specific' if ingredients_specific else 'Vague'})",
            )
            
            # Return meal plan ID for alternate meal test
            return data.get('id')
            
        except requests.exceptions.Timeout:
            self.log_test(
                "Meal Plan Generation API",
                "FAIL",
                "Request timed out after 120 seconds"
            )
            return None
        except Exception as e:
            self.log_test(
                "Meal Plan Generation API", 
                "FAIL",
                f"Exception: {str(e)[:200]}"
            )
            return None
    
    def test_alternate_meal_generation(self, meal_plan_id):
        """TEST 2: Test Alternate Meal Generation"""
        print("\n" + "="*60)
        print("TEST 2: ALTERNATE MEAL GENERATION")
        print("="*60)
        
        if not meal_plan_id:
            self.log_test(
                "Alternate Meal Generation",
                "FAIL",
                "No meal plan ID available from Test 1"
            )
            return
        
        # Request payload for alternate meal (lunch = meal_index 1)
        payload = {
            "user_id": TEST_USER_ID,
            "meal_plan_id": meal_plan_id,
            "day_index": 0,  # Day 1
            "meal_index": 1,  # Lunch (2nd meal)
            "swap_preference": "similar"
        }
        
        start_time = time.time()
        try:
            response = self.session.post(
                f"{BACKEND_URL}/mealplan/alternate",
                json=payload,
                timeout=60
            )
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                self.log_test(
                    "Alternate Meal Generation API",
                    "FAIL",
                    f"HTTP {response.status_code}: {response.text[:200]}",
                    response_time
                )
                return
                
            data = response.json()
            alternate_meal = data.get('alternate_meal', {})
            
            # Extract alternate meal macros
            alt_calories = alternate_meal.get('calories', 0)
            alt_protein = alternate_meal.get('protein', 0)
            alt_carbs = alternate_meal.get('carbs', 0)
            alt_fats = alternate_meal.get('fats', 0)
            
            # Expected lunch macros (~30% of daily target)
            target_lunch_calories = 2273 * 0.30  # ~682 calories
            target_lunch_protein = 170 * 0.30  # ~51g protein
            target_lunch_carbs = 227 * 0.30  # ~68g carbs
            target_lunch_fats = 76 * 0.30  # ~23g fats
            
            print(f"\nALTERNATE MEAL DETAILS:")
            print(f"Name: {alternate_meal.get('name', 'Unknown')}")
            print(f"Macros: {alt_calories}cal, {alt_protein}g P, {alt_carbs}g C, {alt_fats}g F")
            print(f"Expected Lunch Target: ~{target_lunch_calories:.0f}cal, ~{target_lunch_protein:.0f}g P, ~{target_lunch_carbs:.0f}g C, ~{target_lunch_fats:.0f}g F")
            
            # Check if alternate meal is reasonable for lunch portion (~30% of daily)
            # Allow wider tolerance for individual meals (±20%)
            cal_diff = abs(alt_calories - target_lunch_calories)
            protein_diff = abs(alt_protein - target_lunch_protein)
            carbs_diff = abs(alt_carbs - target_lunch_carbs)
            fats_diff = abs(alt_fats - target_lunch_fats)
            
            cal_tolerance = target_lunch_calories * 0.20  # ±20%
            protein_tolerance = target_lunch_protein * 0.20
            carbs_tolerance = target_lunch_carbs * 0.20
            fats_tolerance = target_lunch_fats * 0.20
            
            matches_targets = (
                cal_diff <= cal_tolerance and
                protein_diff <= protein_tolerance and
                carbs_diff <= carbs_tolerance and
                fats_diff <= fats_tolerance
            )
            
            accuracy_details = []
            if cal_diff <= cal_tolerance:
                accuracy_details.append(f"Calories ✅")
            else:
                accuracy_details.append(f"Calories ❌ (off by {cal_diff:.0f})")
                
            if protein_diff <= protein_tolerance:
                accuracy_details.append(f"Protein ✅")
            else:
                accuracy_details.append(f"Protein ❌ (off by {protein_diff:.0f}g)")
                
            if carbs_diff <= carbs_tolerance:
                accuracy_details.append(f"Carbs ✅")
            else:
                accuracy_details.append(f"Carbs ❌ (off by {carbs_diff:.0f}g)")
                
            if fats_diff <= fats_tolerance:
                accuracy_details.append(f"Fats ✅")
            else:
                accuracy_details.append(f"Fats ❌ (off by {fats_diff:.0f}g)")
            
            print(f"\nTARGET MATCH: {' | '.join(accuracy_details)}")
            
            self.log_test(
                "Alternate Meal Generation",
                "PASS" if matches_targets else "FAIL",
                f"Lunch alternate: {alt_calories}cal, {alt_protein}g P, {alt_carbs}g C, {alt_fats}g F - {'Matches targets' if matches_targets else 'Does not match targets'}",
                response_time
            )
            
        except requests.exceptions.Timeout:
            self.log_test(
                "Alternate Meal Generation API",
                "FAIL",
                "Request timed out after 60 seconds"
            )
        except Exception as e:
            self.log_test(
                "Alternate Meal Generation API",
                "FAIL", 
                f"Exception: {str(e)[:200]}"
            )
    
    def print_summary(self):
        """Print test summary in requested format"""
        print("\n" + "="*60)
        print("MEAL PLAN MACRO ACCURACY AND ALTERNATE MEALS TEST RESULTS")
        print("="*60)
        
        # Format as requested in review
        meal_plan_test = None
        ingredient_test = None
        alternate_test = None
        
        for result in self.test_results:
            if "Meal Plan Macro Accuracy" in result['test']:
                meal_plan_test = result
            elif "Ingredient Specificity" in result['test']:
                ingredient_test = result
            elif "Alternate Meal Generation" in result['test']:
                alternate_test = result
        
        print("TEST 1 - MEAL PLAN MACROS:")
        if meal_plan_test:
            print(f"Accuracy: {meal_plan_test['message']}")
        
        if ingredient_test:
            print(f"Sample ingredient (specific?): {ingredient_test['message']}")
        
        print("\nTEST 2 - ALTERNATE MEAL:")
        if alternate_test:
            print(f"{alternate_test['message']}")
            print(f"Matches targets? {'✅' if alternate_test['status'] == 'PASS' else '❌'}")
        
        # Overall status
        all_passed = all(result['status'] == 'PASS' for result in self.test_results)
        print(f"\nOVERALL STATUS: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
        
        return all_passed

def main():
    """Run the meal plan macro accuracy tests"""
    print("InterFitAI Backend Testing - Meal Plan Macro Accuracy & Alternate Meals")
    print("Backend URL:", BACKEND_URL)
    print("Test User ID:", TEST_USER_ID)
    
    tester = MealPlanTester()
    
    # Run Test 1: Meal Plan Generation with Macro Accuracy
    meal_plan_id = tester.test_meal_plan_generation_with_macro_accuracy()
    
    # Run Test 2: Alternate Meal Generation
    tester.test_alternate_meal_generation(meal_plan_id)
    
    # Print final summary
    all_passed = tester.print_summary()
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit(main())