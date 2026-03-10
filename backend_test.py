#!/usr/bin/env python3
"""
Comprehensive Backend Test for Meal Plan Macro Accuracy Fix
Testing programmatic macro calculation with proportional scaling as requested in review.
"""

import requests
import json
import time
import re
from typing import Dict, List, Tuple

# Get the backend URL from environment
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# INGREDIENT_MACROS from the backend - per 100g values for manual verification
INGREDIENT_MACROS = {
    # Key ingredients mentioned in the review request
    "chicken breast": (165, 31, 0, 3.6),
    "sweet potato": (86, 1.6, 20, 0.1), 
    "eggs": (155, 13, 1.1, 11),  # per 100g (about 2 eggs, so 50g per egg)
    "large eggs": (155, 13, 1.1, 11),  # same as regular eggs
    "whole eggs": (155, 13, 1.1, 11),  # same as regular eggs
    "broccoli": (34, 2.8, 7, 0.4),
    "olive oil": (884, 0, 0, 100),
    # Additional common ingredients
    "rice": (130, 2.7, 28, 0.3),
    "oats": (389, 17, 66, 7),
    # Dairy products
    "cheddar cheese": (403, 25, 1.3, 33),
    "cheese": (403, 25, 1.3, 33),
    "greek yogurt": (59, 10, 4, 0.4),
    "cottage cheese": (84, 11, 4, 2.5),
    # Proteins
    "steak": (180, 26, 0, 8),
    "salmon": (208, 20, 0, 13),
    "tuna": (116, 26, 0, 0.8),
    # Vegetables  
    "spinach": (23, 2.9, 3.6, 0.4),
    "avocado": (160, 2, 9, 15),
    "tomato": (18, 0.9, 3.9, 0.2),
    "carrot": (41, 0.9, 10, 0.2),
    # Grains
    "quinoa": (120, 4.4, 21, 1.9),
    "bread": (265, 9, 49, 3.2),
    "pasta": (131, 5, 25, 1.1),
}

def test_health_check():
    """Test basic health check endpoint"""
    print("\n=== TESTING HEALTH CHECK ===")
    start_time = time.time()
    response = requests.get(f"{BACKEND_URL}/health")
    response_time = time.time() - start_time
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Time: {response_time:.2f}s")
    
    if response.status_code == 200:
        print("✅ Health check PASSED")
        return True
    else:
        print("❌ Health check FAILED")
        return False

def calculate_manual_macros(ingredient_name: str, grams: float) -> Tuple[float, float, float, float]:
    """Calculate macros manually using the same logic as backend"""
    if ingredient_name.lower() in INGREDIENT_MACROS:
        cal_per_100g, pro_per_100g, carb_per_100g, fat_per_100g = INGREDIENT_MACROS[ingredient_name.lower()]
        
        # Calculate for the specified grams
        multiplier = grams / 100
        calories = cal_per_100g * multiplier
        protein = pro_per_100g * multiplier
        carbs = carb_per_100g * multiplier
        fats = fat_per_100g * multiplier
        
        return calories, protein, carbs, fats
    else:
        print(f"⚠️ Ingredient '{ingredient_name}' not found in manual database")
        return 0, 0, 0, 0

def parse_ingredient_amounts(ingredients_list: List[str]) -> Dict[str, float]:
    """Parse ingredient strings to extract amounts in grams"""
    ingredients_dict = {}
    
    for ingredient in ingredients_list:
        # Parse formats like "174g chicken breast", "231g sweet potato", "3 eggs", "4 large eggs"
        ingredient = ingredient.lower().strip()
        
        # Handle eggs specially (count-based or weight-based)
        if 'egg' in ingredient and any(char.isdigit() for char in ingredient):
            # First check for count-based patterns like "3 eggs", "4 large eggs"  
            egg_count_match = re.search(r'(\d+)\s+(?:large\s+)?eggs?', ingredient)
            if egg_count_match:
                egg_count = int(egg_count_match.group(1))
                # Backend assumes 50g per egg for count-based
                grams = egg_count * 50
                ingredients_dict['eggs'] = grams
                continue
            
            # Then check for weight-based patterns like "4g large eggs", "150g eggs"
            egg_weight_match = re.search(r'(\d+)g\s+(?:large\s+)?eggs?', ingredient)
            if egg_weight_match:
                grams = float(egg_weight_match.group(1))
                ingredients_dict['eggs'] = grams
                continue
        
        # Handle gram-based ingredients - match patterns like "209g sweet potato"
        gram_match = re.search(r'(\d+(?:\.\d+)?)g\s+(.+)', ingredient)
        if gram_match:
            try:
                grams = float(gram_match.group(1))
                ingredient_name = gram_match.group(2).strip()
                ingredients_dict[ingredient_name] = grams
            except ValueError:
                continue
    
    return ingredients_dict

def verify_meal_macros(meal_data: Dict) -> bool:
    """Manually verify macro calculations for a meal"""
    print(f"\n--- Manual Verification for: {meal_data.get('name', 'Unknown')} ---")
    
    ingredients_list = meal_data.get('ingredients', [])
    api_calories = meal_data.get('calories', 0)
    api_protein = meal_data.get('protein', 0)
    api_carbs = meal_data.get('carbs', 0) 
    api_fats = meal_data.get('fats', 0)
    
    print(f"Ingredients: {ingredients_list}")
    print(f"API Result: {api_calories}cal, {api_protein}g P, {api_carbs}g C, {api_fats}g F")
    
    # Parse ingredients to get amounts
    ingredients_dict = parse_ingredient_amounts(ingredients_list)
    print(f"Parsed ingredients: {ingredients_dict}")
    
    # Calculate manual totals
    manual_cal = manual_pro = manual_carb = manual_fat = 0
    
    for ingredient_name, grams in ingredients_dict.items():
        cal, pro, carb, fat = calculate_manual_macros(ingredient_name, grams)
        manual_cal += cal
        manual_pro += pro
        manual_carb += carb
        manual_fat += fat
        print(f"  {ingredient_name} ({grams}g): {cal:.1f}cal, {pro:.1f}g P, {carb:.1f}g C, {fat:.1f}g F")
    
    print(f"Manual Total: {manual_cal:.1f}cal, {manual_pro:.1f}g P, {manual_carb:.1f}g C, {manual_fat:.1f}g F")
    
    # Compare with ±5% tolerance as specified in review
    tolerance = 0.05  # 5%
    
    cal_diff = abs(manual_cal - api_calories) / max(manual_cal, api_calories) if max(manual_cal, api_calories) > 0 else 0
    pro_diff = abs(manual_pro - api_protein) / max(manual_pro, api_protein) if max(manual_pro, api_protein) > 0 else 0
    carb_diff = abs(manual_carb - api_carbs) / max(manual_carb, api_carbs) if max(manual_carb, api_carbs) > 0 else 0
    fat_diff = abs(manual_fat - api_fats) / max(manual_fat, api_fats) if max(manual_fat, api_fats) > 0 else 0
    
    print(f"Differences: Cal {cal_diff*100:.1f}%, Pro {pro_diff*100:.1f}%, Carb {carb_diff*100:.1f}%, Fat {fat_diff*100:.1f}%")
    
    if cal_diff <= tolerance and pro_diff <= tolerance and carb_diff <= tolerance and fat_diff <= tolerance:
        print("✅ Manual verification PASSED - Macros match within ±5% tolerance")
        return True
    else:
        print("❌ Manual verification FAILED - Macros exceed ±5% tolerance")
        return False

def test_meal_plan_generation_with_preferred_foods():
    """TEST 1: Generate meal plan with preferred foods - CRITICAL MACRO ACCURACY TEST"""
    print("\n=== TEST 1: MEAL PLAN WITH PREFERRED FOODS - MACRO ACCURACY ===")
    
    request_data = {
        "user_id": "cbd82a69-3a37-48c2-88e8-0fe95081fa4b",
        "food_preferences": "balanced",
        "preferred_foods": "sweet potato, broccoli, eggs",
        "allergies": []
    }
    
    print(f"Request: {json.dumps(request_data, indent=2)}")
    
    start_time = time.time()
    response = requests.post(f"{BACKEND_URL}/mealplans/generate", json=request_data)
    response_time = time.time() - start_time
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Time: {response_time:.2f}s")
    
    if response.status_code != 200:
        print(f"❌ TEST 1 FAILED - API Error: {response.text}")
        return False
    
    meal_plan = response.json()
    print(f"Generated: {meal_plan.get('name', 'Unknown Plan')}")
    
    # Get user's target macros
    target_calories = meal_plan.get('target_calories', 0)
    target_protein = meal_plan.get('target_protein', 0)
    target_carbs = meal_plan.get('target_carbs', 0)
    target_fats = meal_plan.get('target_fats', 0)
    
    print(f"Target Macros: {target_calories}cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
    
    # VERIFICATION STEP 1: Check daily calorie totals are within ±10 of target
    daily_totals_pass = True
    meal_verification_pass = True
    
    for day_idx, day in enumerate(meal_plan.get('meal_days', [])):
        day_cal = day.get('total_calories', 0)
        day_pro = day.get('total_protein', 0)
        day_carb = day.get('total_carbs', 0)
        day_fat = day.get('total_fats', 0)
        
        cal_diff = abs(day_cal - target_calories)
        
        print(f"\nDay {day_idx + 1}: {day_cal}cal, {day_pro}g P, {day_carb}g C, {day_fat}g F")
        print(f"Calorie difference from target: {cal_diff} (target ±10)")
        
        if cal_diff > 10:
            print(f"❌ Day {day_idx + 1} calorie total exceeds ±10 tolerance")
            daily_totals_pass = False
        else:
            print(f"✅ Day {day_idx + 1} calorie total within ±10 tolerance")
        
        # VERIFICATION STEP 2: Manual verify macros for ONE meal (Day 1, first meal)
        if day_idx == 0 and len(day.get('meals', [])) > 0:
            first_meal = day['meals'][0]
            print(f"\n🔍 MANUAL MACRO VERIFICATION - {first_meal.get('name', 'Unknown')}")
            meal_pass = verify_meal_macros(first_meal)
            if not meal_pass:
                meal_verification_pass = False
        
        # VERIFICATION STEP 3: Verify daily totals = sum of meal macros
        meals = day.get('meals', [])
        calculated_cal = sum(meal.get('calories', 0) for meal in meals)
        calculated_pro = sum(meal.get('protein', 0) for meal in meals)
        calculated_carb = sum(meal.get('carbs', 0) for meal in meals)
        calculated_fat = sum(meal.get('fats', 0) for meal in meals)
        
        print(f"\nCalculated from meals: {calculated_cal}cal, {calculated_pro}g P, {calculated_carb}g C, {calculated_fat}g F")
        print(f"Day totals from API:   {day_cal}cal, {day_pro}g P, {day_carb}g C, {day_fat}g F")
        
        # Check if sums match (within 1 unit for rounding)
        sum_match = (abs(calculated_cal - day_cal) <= 1 and 
                    abs(calculated_pro - day_pro) <= 1 and
                    abs(calculated_carb - day_carb) <= 1 and 
                    abs(calculated_fat - day_fat) <= 1)
        
        if sum_match:
            print("✅ Daily totals match sum of meal macros")
        else:
            print("❌ Daily totals do NOT match sum of meal macros")
            daily_totals_pass = False
    
    # Overall result
    if daily_totals_pass and meal_verification_pass:
        print("\n🎉 TEST 1 PASSED - All macro accuracy checks successful!")
        return True
    else:
        print("\n❌ TEST 1 FAILED - Macro accuracy issues detected")
        return False

def test_keto_meal_plan_generation():
    """TEST 2: Generate Keto meal plan (template-based) - DIET COMPLIANCE TEST"""
    print("\n=== TEST 2: KETO MEAL PLAN - TEMPLATE-BASED SCALING ===")
    
    request_data = {
        "user_id": "cbd82a69-3a37-48c2-88e8-0fe95081fa4b", 
        "food_preferences": "keto",
        "allergies": []
    }
    
    print(f"Request: {json.dumps(request_data, indent=2)}")
    
    start_time = time.time()
    response = requests.post(f"{BACKEND_URL}/mealplans/generate", json=request_data)
    response_time = time.time() - start_time
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Time: {response_time:.2f}s")
    
    if response.status_code != 200:
        print(f"❌ TEST 2 FAILED - API Error: {response.text}")
        return False
    
    meal_plan = response.json()
    print(f"Generated: {meal_plan.get('name', 'Unknown Plan')}")
    
    target_calories = meal_plan.get('target_calories', 0)
    print(f"Target Calories: {target_calories}")
    
    # KETO COMPLIANCE: Verify carbs are < 50g per day
    keto_compliance = True
    calorie_accuracy = True
    
    for day_idx, day in enumerate(meal_plan.get('meal_days', [])):
        day_cal = day.get('total_calories', 0)
        day_carb = day.get('total_carbs', 0)
        
        print(f"\nDay {day_idx + 1}: {day_cal}cal, {day_carb}g carbs")
        
        # Check keto compliance (< 50g carbs)
        if day_carb >= 50:
            print(f"❌ Day {day_idx + 1} carbs {day_carb}g >= 50g - NOT KETO COMPLIANT")
            keto_compliance = False
        else:
            print(f"✅ Day {day_idx + 1} carbs {day_carb}g < 50g - KETO COMPLIANT")
        
        # Check calorie scaling accuracy (within ±10)
        cal_diff = abs(day_cal - target_calories)
        if cal_diff > 10:
            print(f"❌ Day {day_idx + 1} calories off by {cal_diff} (target ±10)")
            calorie_accuracy = False
        else:
            print(f"✅ Day {day_idx + 1} calories within ±10 tolerance")
    
    # Overall result
    if keto_compliance and calorie_accuracy:
        print("\n🎉 TEST 2 PASSED - Keto diet compliance and calorie scaling successful!")
        return True
    else:
        print("\n❌ TEST 2 FAILED - Issues with keto compliance or calorie scaling")
        return False

def main():
    """Run comprehensive meal plan macro accuracy tests"""
    print("="*80)
    print("COMPREHENSIVE MEAL PLAN MACRO ACCURACY TESTING")
    print("Testing programmatic macro calculation with proportional scaling")
    print("="*80)
    
    # Track test results
    results = []
    
    # Test 1: Health Check
    results.append(("Health Check", test_health_check()))
    
    # Test 2: Meal Plan with Preferred Foods (CRITICAL TEST)
    results.append(("Meal Plan with Preferred Foods - MACRO ACCURACY", test_meal_plan_generation_with_preferred_foods()))
    
    # Test 3: Keto Meal Plan (Template-based)
    results.append(("Keto Meal Plan - DIET COMPLIANCE", test_keto_meal_plan_generation()))
    
    # Final Summary
    print("\n" + "="*80)
    print("FINAL TEST SUMMARY")
    print("="*80)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED - Meal plan macro accuracy fix is working correctly!")
        return True
    else:
        print("❌ SOME TESTS FAILED - Meal plan macro accuracy needs attention")
        return False

if __name__ == "__main__":
    main()