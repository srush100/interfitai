#!/usr/bin/env python3
"""
Backend test script for InterFitAI PROGRAMMATIC DAY GENERATION testing.

Tests the NEW meal plan generation approach with programmatic day generation:
1. AI generates Day 1 ONLY with a specific template
2. Python code creates Days 2 and 3 by copying Day 1 and swapping ingredients
3. All macros are calculated programmatically from the ingredient database
4. This should guarantee consistent macros across all 3 days because they're based on the same portion sizes.
"""

import httpx
import json
import asyncio
import sys
import re
from typing import Dict, List
import time

# Backend URL from frontend/.env
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com"
API_BASE = f"{BACKEND_URL}/api"

# Test user ID as specified in review request
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

async def test_meal_plan_programmatic_day_generation():
    """Test meal plan generation with programmatic day generation as specified in review request"""
    print("=" * 80)
    print("TESTING MEAL PLAN WITH PROGRAMMATIC DAY GENERATION")
    print("=" * 80)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            start_time = time.time()
            print(f"\n1. GENERATING A MEAL PLAN:")
            print(f"   POST /api/mealplans/generate")
            print(f"   Body: {{\"user_id\": \"{TEST_USER_ID}\", \"food_preferences\": \"whole_foods\"}}")
            print(f"   Backend URL: {API_BASE}")
            
            # Generate meal plan as specified in review request
            response = await client.post(
                f"{API_BASE}/mealplans/generate",
                json={
                    "user_id": TEST_USER_ID,
                    "food_preferences": "whole_foods"
                }
            )
            
            response_time = time.time() - start_time
            print(f"   Response Status: {response.status_code}")
            print(f"   Response Time: {response_time:.2f}s")
            
            if response.status_code != 200:
                print(f"   ERROR: {response.text}")
                return False
                
            meal_plan = response.json()
            print(f"   ✅ SUCCESS: Generated meal plan '{meal_plan.get('name', 'Unknown')}'")
            
            # Extract target macros (should be ~2273 cal, 170g P, 227g C, 76g F according to review)
            target_calories = meal_plan.get('target_calories', 0)
            target_protein = meal_plan.get('target_protein', 0)
            target_carbs = meal_plan.get('target_carbs', 0)
            target_fats = meal_plan.get('target_fats', 0)
            
            print(f"\n   Target: {target_calories} cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
            
            # Extract all 3 days
            day_1 = meal_plan["meal_days"][0]
            day_2 = meal_plan["meal_days"][1] 
            day_3 = meal_plan["meal_days"][2]
            
            # 2. CHECK MACRO CONSISTENCY ACROSS ALL 3 DAYS
            print(f"\n2. VERIFY CONSISTENCY (within ±10%):")
            
            day_1_totals = (day_1['total_calories'], day_1['total_protein'], day_1['total_carbs'], day_1['total_fats'])
            day_2_totals = (day_2['total_calories'], day_2['total_protein'], day_2['total_carbs'], day_2['total_fats'])
            day_3_totals = (day_3['total_calories'], day_3['total_protein'], day_3['total_carbs'], day_3['total_fats'])
            
            print(f"   Day 1: {day_1_totals[0]} cal, {day_1_totals[1]}g P, {day_1_totals[2]}g C, {day_1_totals[3]}g F")
            print(f"   Day 2: {day_2_totals[0]} cal, {day_2_totals[1]}g P, {day_2_totals[2]}g C, {day_2_totals[3]}g F")
            print(f"   Day 3: {day_3_totals[0]} cal, {day_3_totals[1]}g P, {day_3_totals[2]}g C, {day_3_totals[3]}g F")
            
            # Check consistency between days (±10% tolerance as specified)
            def check_consistency(val1, val2, val3):
                max_val = max(val1, val2, val3)
                min_val = min(val1, val2, val3)
                avg_val = (val1 + val2 + val3) / 3
                deviation = (max_val - min_val) / avg_val * 100 if avg_val > 0 else 0
                return deviation <= 10, deviation
            
            cal_consistent, cal_deviation = check_consistency(day_1_totals[0], day_2_totals[0], day_3_totals[0])
            protein_consistent, protein_deviation = check_consistency(day_1_totals[1], day_2_totals[1], day_3_totals[1])
            carbs_consistent, carbs_deviation = check_consistency(day_1_totals[2], day_2_totals[2], day_3_totals[2])
            fats_consistent, fats_deviation = check_consistency(day_1_totals[3], day_2_totals[3], day_3_totals[3])
            
            all_consistent = cal_consistent and protein_consistent and carbs_consistent and fats_consistent
            
            print(f"\n   Consistency Check (±10% tolerance):")
            print(f"   - Calories: {'✅' if cal_consistent else '❌'} {cal_deviation:.1f}% deviation")
            print(f"   - Protein:  {'✅' if protein_consistent else '❌'} {protein_deviation:.1f}% deviation") 
            print(f"   - Carbs:    {'✅' if carbs_consistent else '❌'} {carbs_deviation:.1f}% deviation")
            print(f"   - Fats:     {'✅' if fats_consistent else '❌'} {fats_deviation:.1f}% deviation")
            
            # 3. CHECK VARIETY (Different ingredients)
            print(f"\n3. CHECK VARIETY (Different ingredients but same portion sizes):")
            
            # Get ingredients from each day to check variety
            day1_ingredients = []
            day2_ingredients = []
            day3_ingredients = []
            
            for meal in day_1.get('meals', []):
                day1_ingredients.extend(meal.get('ingredients', []))
            for meal in day_2.get('meals', []):
                day2_ingredients.extend(meal.get('ingredients', []))
            for meal in day_3.get('meals', []):
                day3_ingredients.extend(meal.get('ingredients', []))
            
            print(f"   Day 1 sample ingredients: {day1_ingredients[:3]}...")
            print(f"   Day 2 sample ingredients: {day2_ingredients[:3]}...")  
            print(f"   Day 3 sample ingredients: {day3_ingredients[:3]}...")
            
            # Check if ingredients are different (basic check)
            variety_check = len(set(day1_ingredients[:5]) & set(day2_ingredients[:5])) < 3  # Less than 3 common ingredients
            variety_result = "✅ Different ingredients" if variety_check else "❌ Too similar ingredients"
            print(f"   Ingredient Variety: {variety_result}")
            
            # 4. FINAL REPORT FORMAT AS REQUESTED IN REVIEW
            print(f"\n" + "=" * 60)
            print(f"REPORT:")
            print(f"Day 1: {day_1_totals[0]} cal, {day_1_totals[1]}g P, {day_1_totals[2]}g C, {day_1_totals[3]}g F")
            print(f"Day 2: {day_2_totals[0]} cal, {day_2_totals[1]}g P, {day_2_totals[2]}g C, {day_2_totals[3]}g F") 
            print(f"Day 3: {day_3_totals[0]} cal, {day_3_totals[1]}g P, {day_3_totals[2]}g C, {day_3_totals[3]}g F")
            print(f"")
            print(f"Are all 3 days within ±10% of each other? {'✅' if all_consistent else '❌'}")
            print(f"Do the days have different ingredients? {'✅' if variety_check else '❌'}")
            print(f"=" * 60)
            
            # Return success if consistency passes (main goal of programmatic approach)
            success = all_consistent
            return success
            
        except Exception as e:
            print(f"   ERROR during meal plan testing: {e}")
            import traceback
            traceback.print_exc()
            return False

async def main():
    """Run meal plan programmatic day generation test as specified in review request"""
    print(f"Backend Test Suite - InterFitAI Meal Plan Programmatic Day Generation")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    
    success = await test_meal_plan_programmatic_day_generation()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ MEAL PLAN PROGRAMMATIC DAY GENERATION TEST COMPLETED")
    else:
        print("❌ MEAL PLAN PROGRAMMATIC DAY GENERATION TEST FAILED")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())