#!/usr/bin/env python3

import requests
import json
import time

# Backend URL from review request  
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# User ID for testing (from review request)
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# Ingredient database values from backend code
INGREDIENT_VALUES = {
    "chicken breast (cooked)": {"per_100g": {"cal": 165, "protein": 31, "carbs": 0, "fats": 3.6}},
    "oats dry": {"per_40g": {"cal": 150, "protein": 5, "carbs": 27, "fats": 2.5}},
    "banana": {"per_medium_118g": {"cal": 105, "protein": 1.3, "carbs": 27, "fats": 0.4}},
    "brown rice (cooked)": {"per_100g": {"cal": 112, "protein": 2.6, "carbs": 24, "fats": 0.9}},
    "olive oil": {"per_tbsp_14g": {"cal": 119, "protein": 0, "carbs": 0, "fats": 14}},
    "ground turkey 93% lean (cooked)": {"per_100g": {"cal": 170, "protein": 21, "carbs": 0, "fats": 9}},
    "sweet potato (baked)": {"per_100g": {"cal": 90, "protein": 2, "carbs": 21, "fats": 0.1}},
    "greek yogurt 0% fat": {"per_100g": {"cal": 59, "protein": 10, "carbs": 4, "fats": 0.4}},
    "spinach": {"per_100g": {"cal": 23, "protein": 2.9, "carbs": 3.6, "fats": 0.4}},
    "avocado": {"per_100g": {"cal": 160, "protein": 2, "carbs": 9, "fats": 15}}
}

def calculate_ingredient_macros(ingredient_text):
    """Calculate expected macros for an ingredient based on database values"""
    ingredient_lower = ingredient_text.lower()
    
    # Extract quantity and find matching ingredient
    for db_ingredient, values in INGREDIENT_VALUES.items():
        if db_ingredient in ingredient_lower:
            # Try to extract quantity
            quantity = None
            unit = None
            
            # Look for patterns like "150g", "40g", "1 tbsp", "1 medium"
            import re
            
            # Pattern for amounts like "150g chicken breast"
            match = re.search(r'(\d+)g\s+' + db_ingredient.replace('(', r'\(').replace(')', r'\)'), ingredient_lower)
            if match:
                quantity = int(match.group(1))
                unit = "g"
            
            # Pattern for "1 tbsp olive oil"
            if "tbsp" in ingredient_lower and "olive oil" in db_ingredient:
                tbsp_match = re.search(r'(\d+)\s*tbsp', ingredient_lower)
                if tbsp_match:
                    quantity = int(tbsp_match.group(1)) * 14  # 1 tbsp = 14g
                    unit = "g"
            
            # Pattern for "1 medium banana"
            if "medium banana" in ingredient_lower and "banana" in db_ingredient:
                medium_match = re.search(r'(\d+)\s*medium', ingredient_lower)
                if medium_match:
                    quantity = int(medium_match.group(1)) * 118  # 1 medium = 118g
                    unit = "g"
            
            # Pattern for "40g oats dry"
            if "oats dry" in db_ingredient and "oats" in ingredient_lower:
                oats_match = re.search(r'(\d+)g', ingredient_lower)
                if oats_match:
                    quantity = int(oats_match.group(1))
                    unit = "g"
            
            if quantity is not None:
                # Get reference values
                ref_data = list(values.values())[0]  # Get the first (and usually only) reference
                
                # Calculate scaling factor
                if "per_100g" in list(values.keys())[0]:
                    scale_factor = quantity / 100.0
                elif "per_40g" in list(values.keys())[0]:
                    scale_factor = quantity / 40.0
                elif "per_medium_118g" in list(values.keys())[0]:
                    scale_factor = quantity / 118.0
                elif "per_tbsp_14g" in list(values.keys())[0]:
                    scale_factor = quantity / 14.0
                else:
                    scale_factor = 1.0
                
                # Calculate expected macros
                expected_cal = ref_data["cal"] * scale_factor
                expected_protein = ref_data["protein"] * scale_factor
                expected_carbs = ref_data["carbs"] * scale_factor
                expected_fats = ref_data["fats"] * scale_factor
                
                return {
                    "ingredient": db_ingredient,
                    "quantity": f"{quantity}g",
                    "expected": {
                        "calories": round(expected_cal, 1),
                        "protein": round(expected_protein, 1),
                        "carbs": round(expected_carbs, 1),
                        "fats": round(expected_fats, 1)
                    }
                }
    
    return None

def detailed_meal_analysis():
    """Generate a meal plan and perform detailed ingredient-level analysis"""
    print("=== DETAILED MEAL PLAN INGREDIENT ANALYSIS ===")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print()

    # Generate meal plan
    print("1. Generating meal plan...")
    start_time = time.time()
    
    generate_request = {
        "user_id": TEST_USER_ID,
        "food_preferences": "whole_foods"
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/mealplans/generate",
            json=generate_request,
            timeout=60
        )
        
        response_time = time.time() - start_time
        
        if response.status_code != 200:
            print(f"❌ FAILED: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
        meal_plan = response.json()
        print(f"✅ Generated in {response_time:.2f}s")
        print()
        
    except Exception as e:
        print(f"❌ FAILED: {str(e)}")
        return False

    # Get meal plan details
    day_1 = meal_plan['meal_days'][0]
    meals = day_1.get('meals', [])
    target_calories = meal_plan.get('target_calories', 0)
    target_protein = meal_plan.get('target_protein', 0)
    target_carbs = meal_plan.get('target_carbs', 0)
    target_fats = meal_plan.get('target_fats', 0)
    
    print(f"TARGET MACROS: {target_calories} cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
    print()
    
    # Analyze each meal in detail
    total_expected_cal = 0
    total_expected_protein = 0
    total_expected_carbs = 0
    total_expected_fats = 0
    
    total_listed_cal = 0
    total_listed_protein = 0
    total_listed_carbs = 0
    total_listed_fats = 0
    
    for i, meal in enumerate(meals, 1):
        meal_name = meal.get('name', f'Meal {i}')
        meal_type = meal.get('meal_type', 'unknown')
        ingredients = meal.get('ingredients', [])
        
        listed_cal = meal.get('calories', 0)
        listed_protein = meal.get('protein', 0)
        listed_carbs = meal.get('carbs', 0)
        listed_fats = meal.get('fats', 0)
        
        print(f"MEAL {i}: {meal_name} ({meal_type})")
        print("INGREDIENTS:")
        
        expected_meal_cal = 0
        expected_meal_protein = 0
        expected_meal_carbs = 0
        expected_meal_fats = 0
        
        for ingredient in ingredients:
            analysis = calculate_ingredient_macros(ingredient)
            if analysis:
                expected_meal_cal += analysis["expected"]["calories"]
                expected_meal_protein += analysis["expected"]["protein"]
                expected_meal_carbs += analysis["expected"]["carbs"]
                expected_meal_fats += analysis["expected"]["fats"]
                
                print(f"  - {ingredient}")
                print(f"    → Expected: {analysis['expected']['calories']} cal, {analysis['expected']['protein']}g P, {analysis['expected']['carbs']}g C, {analysis['expected']['fats']}g F")
            else:
                print(f"  - {ingredient} → ⚠️  Could not calculate (not in reference database)")
        
        print(f"MEAL TOTALS:")
        print(f"  Expected: {expected_meal_cal:.0f} cal, {expected_meal_protein:.1f}g P, {expected_meal_carbs:.1f}g C, {expected_meal_fats:.1f}g F")
        print(f"  Listed:   {listed_cal} cal, {listed_protein}g P, {listed_carbs}g C, {listed_fats}g F")
        
        # Calculate deviations
        cal_dev = listed_cal - expected_meal_cal
        protein_dev = listed_protein - expected_meal_protein
        carbs_dev = listed_carbs - expected_meal_carbs
        fats_dev = listed_fats - expected_meal_fats
        
        print(f"  Deviation: {cal_dev:+.0f} cal, {protein_dev:+.1f}g P, {carbs_dev:+.1f}g C, {fats_dev:+.1f}g F")
        
        # Check if deviations are significant
        if abs(cal_dev) > 50 or abs(protein_dev) > 5 or abs(carbs_dev) > 5 or abs(fats_dev) > 3:
            print(f"  ❌ SIGNIFICANT DEVIATIONS DETECTED")
        else:
            print(f"  ✅ Macros match expected values")
        
        print()
        
        # Add to totals
        total_expected_cal += expected_meal_cal
        total_expected_protein += expected_meal_protein
        total_expected_carbs += expected_meal_carbs
        total_expected_fats += expected_meal_fats
        
        total_listed_cal += listed_cal
        total_listed_protein += listed_protein
        total_listed_carbs += listed_carbs
        total_listed_fats += listed_fats
    
    # Day totals comparison
    print("DAY 1 TOTALS COMPARISON:")
    print(f"Expected Sum:  {total_expected_cal:.0f} cal, {total_expected_protein:.1f}g P, {total_expected_carbs:.1f}g C, {total_expected_fats:.1f}g F")
    print(f"Listed Sum:    {total_listed_cal} cal, {total_listed_protein}g P, {total_listed_carbs}g C, {total_listed_fats}g F") 
    print(f"Target Macros: {target_calories} cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
    print()
    
    # Final accuracy assessment
    print("ACCURACY ASSESSMENT:")
    
    # Check if listed totals match expected ingredient sums
    ingredient_accuracy = True
    if abs(total_listed_cal - total_expected_cal) > 50:
        print(f"❌ INGREDIENT MISMATCH: Calories differ by {total_listed_cal - total_expected_cal:.0f}")
        ingredient_accuracy = False
        
    if abs(total_listed_protein - total_expected_protein) > 5:
        print(f"❌ INGREDIENT MISMATCH: Protein differs by {total_listed_protein - total_expected_protein:.1f}g")
        ingredient_accuracy = False
        
    if abs(total_listed_carbs - total_expected_carbs) > 5:
        print(f"❌ INGREDIENT MISMATCH: Carbs differ by {total_listed_carbs - total_expected_carbs:.1f}g")
        ingredient_accuracy = False
        
    if abs(total_listed_fats - total_expected_fats) > 3:
        print(f"❌ INGREDIENT MISMATCH: Fats differ by {total_listed_fats - total_expected_fats:.1f}g")
        ingredient_accuracy = False
    
    if ingredient_accuracy:
        print("✅ INGREDIENT ACCURACY: Listed meal macros match ingredient calculations")
    
    # Check if totals match target macros  
    target_accuracy = True
    cal_tolerance = target_calories * 0.10
    protein_tolerance = target_protein * 0.10
    carbs_tolerance = target_carbs * 0.10
    fats_tolerance = target_fats * 0.10
    
    if abs(total_listed_cal - target_calories) > cal_tolerance:
        print(f"❌ TARGET MISMATCH: Calories off by {total_listed_cal - target_calories:.0f} (tolerance: ±{cal_tolerance:.0f})")
        target_accuracy = False
        
    if abs(total_listed_protein - target_protein) > protein_tolerance:
        print(f"❌ TARGET MISMATCH: Protein off by {total_listed_protein - target_protein:.1f}g (tolerance: ±{protein_tolerance:.1f}g)")
        target_accuracy = False
        
    if abs(total_listed_carbs - target_carbs) > carbs_tolerance:
        print(f"❌ TARGET MISMATCH: Carbs off by {total_listed_carbs - target_carbs:.1f}g (tolerance: ±{carbs_tolerance:.1f}g)")
        target_accuracy = False
        
    if abs(total_listed_fats - target_fats) > fats_tolerance:
        print(f"❌ TARGET MISMATCH: Fats off by {total_listed_fats - target_fats:.1f}g (tolerance: ±{fats_tolerance:.1f}g)")
        target_accuracy = False
    
    if target_accuracy:
        print("✅ TARGET ACCURACY: Daily totals match target macros within tolerance")
    
    print()
    print("=== FINAL VERDICT ===")
    
    if ingredient_accuracy and target_accuracy:
        print("✅ MEAL PLAN NUTRITIONAL ACCURACY: WORKING CORRECTLY")
        print("- Ingredients used from database with accurate macro calculations")
        print("- Meal totals correctly sum ingredient values")  
        print("- Daily totals match target macros within acceptable tolerance")
        return True
    else:
        print("❌ MEAL PLAN NUTRITIONAL ACCURACY: ISSUES DETECTED")
        if not ingredient_accuracy:
            print("- Listed meal macros do not match ingredient calculations")
        if not target_accuracy:
            print("- Daily totals exceed acceptable tolerance from target macros")
        return False

if __name__ == "__main__":
    detailed_meal_analysis()