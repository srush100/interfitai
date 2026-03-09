#!/usr/bin/env python3
"""
Backend Test Script for InterFitAI - Meal Plan Macro Accuracy Testing
Testing the improved meal plan generation with post-processing for exact macro totals
"""

import requests
import json
import time
from typing import Dict, List

# Backend URL from environment variable (production external URL)
BASE_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# Test user ID as specified in the review request
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

def test_meal_plan_macro_accuracy():
    """Test meal plan macro accuracy with post-processing improvements"""
    print("🧪 TESTING MEAL PLAN MACRO ACCURACY - ROUND 2")
    print("="*60)
    
    # 1. Generate a Meal Plan
    print("\n1. 📋 GENERATING MEAL PLAN...")
    meal_plan_data = {
        "user_id": TEST_USER_ID,
        "food_preferences": "whole_foods", 
        "allergies": []
    }
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/mealplans/generate",
            json=meal_plan_data,
            timeout=60
        )
        generation_time = time.time() - start_time
        
        if response.status_code != 200:
            print(f"❌ Meal plan generation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
        meal_plan = response.json()
        print(f"✅ Meal plan generated successfully in {generation_time:.2f} seconds")
        print(f"Plan name: {meal_plan.get('name')}")
        
        # Extract target macros from the response
        target_calories = meal_plan.get("target_calories")
        target_protein = meal_plan.get("target_protein") 
        target_carbs = meal_plan.get("target_carbs")
        target_fats = meal_plan.get("target_fats")
        
        print(f"🎯 Target macros: {target_calories} cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
        
        # 2. CRITICAL VALIDATION - Extract and Sum Day 1 Meals
        print("\n2. 🧮 CRITICAL VALIDATION - Day 1 Macro Analysis:")
        print("-" * 50)
        
        meal_days = meal_plan.get("meal_days", [])
        if not meal_days:
            print("❌ No meal days found in response")
            return False
            
        day_1 = meal_days[0]
        day_1_meals = day_1.get("meals", [])
        
        if len(day_1_meals) != 4:
            print(f"❌ Expected 4 meals, got {len(day_1_meals)}")
            return False
        
        # Extract and display each meal's macros
        total_cal = 0
        total_protein = 0  
        total_carbs = 0
        total_fats = 0
        
        for i, meal in enumerate(day_1_meals, 1):
            meal_name = meal.get("name", f"Meal {i}")
            meal_cal = meal.get("calories", 0)
            meal_protein = meal.get("protein", 0)
            meal_carbs = meal.get("carbs", 0) 
            meal_fats = meal.get("fats", 0)
            
            # Sum the totals
            total_cal += meal_cal
            total_protein += meal_protein
            total_carbs += meal_carbs
            total_fats += meal_fats
            
            print(f"Meal {i}: {meal_name}")
            print(f"  📊 {meal_cal} cal, {meal_protein}g P, {meal_carbs}g C, {meal_fats}g F")
        
        print("-" * 50)
        print(f"📈 CALCULATED TOTAL: {total_cal} cal, {total_protein}g P, {total_carbs}g C, {total_fats}g F")
        print(f"🎯 TARGET TOTAL:     {target_calories} cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
        
        # 3. Validation - Check for EXACT matches
        print("\n3. ✅ EXACT MATCH VALIDATION:")
        print("-" * 40)
        
        cal_diff = abs(total_cal - target_calories)
        protein_diff = abs(total_protein - target_protein) 
        carbs_diff = abs(total_carbs - target_carbs)
        fats_diff = abs(total_fats - target_fats)
        
        cal_match = cal_diff == 0
        protein_match = protein_diff == 0
        carbs_match = carbs_diff == 0
        fats_match = fats_diff == 0
        
        print(f"Calories: {'✅ EXACT' if cal_match else f'❌ OFF BY {cal_diff}'}")
        print(f"Protein:  {'✅ EXACT' if protein_match else f'❌ OFF BY {protein_diff}g'}")
        print(f"Carbs:    {'✅ EXACT' if carbs_match else f'❌ OFF BY {carbs_diff}g'}")
        print(f"Fats:     {'✅ EXACT' if fats_match else f'❌ OFF BY {fats_diff}g'}")
        
        all_exact = cal_match and protein_match and carbs_match and fats_match
        
        print(f"\n🏆 FINAL RESULT: {'✅ ALL MACROS EXACT!' if all_exact else '❌ MACRO ACCURACY FAILED'}")
        
        if all_exact:
            print("🎉 POST-PROCESSING SUCCESS: The backend post-processing is working perfectly!")
            print("   All meal macros sum to exactly match the target values.")
        else:
            print("🚨 POST-PROCESSING ISSUE: The backend post-processing is not achieving exact totals.")
            print("   The 4th meal (snack) adjustment logic may need refinement.")
        
        # Display the detailed meal breakdown for reference
        print(f"\n📋 DETAILED MEAL BREAKDOWN (Day 1):")
        for i, meal in enumerate(day_1_meals, 1):
            meal_type = meal.get("meal_type", "unknown") 
            print(f"{i}. {meal.get('name')} ({meal_type.title()})")
            print(f"   Ingredients: {', '.join(meal.get('ingredients', [])[:3])}...")
            
        return all_exact
        
    except requests.exceptions.Timeout:
        print(f"❌ Request timed out after 60 seconds")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        print(f"Response content: {response.text[:500]}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Run meal plan macro accuracy test"""
    print("🏃 Starting Meal Plan Macro Accuracy Testing...")
    print(f"🌐 Backend URL: {BASE_URL}")
    print(f"👤 Test User ID: {TEST_USER_ID}")
    
    success = test_meal_plan_macro_accuracy()
    
    print("\n" + "="*60)
    print("🏁 TEST SUMMARY:")
    if success:
        print("✅ MEAL PLAN MACRO ACCURACY: WORKING")
        print("   Post-processing successfully enforces exact macro totals")
    else:
        print("❌ MEAL PLAN MACRO ACCURACY: FAILING")
        print("   Post-processing is not achieving exact macro precision")
    print("="*60)

if __name__ == "__main__":
    main()