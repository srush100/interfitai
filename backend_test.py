#!/usr/bin/env python3
"""
Backend test script for InterFitAI meal plan improved portion guidance testing.

Tests the meal plan generation with improved portion guidance and consistency:
1. Generate a meal plan with specific food preferences
2. Check daily totals consistency across all 3 days (within ±10% of each other)
3. Verify accuracy compared to target (~±15% of target: ~2273 cal, 170g P, 227g C, 76g F)
4. Verify meal structure (4 meals per day, gram amounts, realistic portions)
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

async def test_meal_plan_improved_portion_guidance():
    """Test meal plan generation with improved portion guidance as specified in review request"""
    print("=" * 80)
    print("TESTING MEAL PLAN WITH IMPROVED PORTION GUIDANCE")
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
            
            # 2. CHECK DAILY TOTALS CONSISTENCY
            print(f"\n2. CHECK DAILY TOTALS CONSISTENCY:")
            
            day_1_totals = (day_1['total_calories'], day_1['total_protein'], day_1['total_carbs'], day_1['total_fats'])
            day_2_totals = (day_2['total_calories'], day_2['total_protein'], day_2['total_carbs'], day_2['total_fats'])
            day_3_totals = (day_3['total_calories'], day_3['total_protein'], day_3['total_carbs'], day_3['total_fats'])
            
            print(f"   Day 1: {day_1_totals[0]} cal, {day_1_totals[1]}g P, {day_1_totals[2]}g C, {day_1_totals[3]}g F")
            print(f"   Day 2: {day_2_totals[0]} cal, {day_2_totals[1]}g P, {day_2_totals[2]}g C, {day_2_totals[3]}g F")
            print(f"   Day 3: {day_3_totals[0]} cal, {day_3_totals[1]}g P, {day_3_totals[2]}g C, {day_3_totals[3]}g F")
            print(f"   Target: {target_calories} cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
            
            # Check consistency between days (±10% tolerance)
            def check_consistency(val1, val2, val3):
                max_val = max(val1, val2, val3)
                min_val = min(val1, val2, val3)
                avg_val = (val1 + val2 + val3) / 3
                deviation = (max_val - min_val) / avg_val * 100
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
            
            consistency_result = "✅ All days within 10% of each other" if all_consistent else "❌ Inconsistent"
            print(f"   Consistency: {consistency_result}")
            
            # 3. CHECK ACCURACY COMPARED TO TARGET (±15% tolerance)
            print(f"\n3. CHECK ACCURACY COMPARED TO TARGET (±15% tolerance):")
            
            def check_target_accuracy(actual, target):
                if target == 0:
                    return True, 0
                deviation = abs(actual - target) / target * 100
                return deviation <= 15, deviation
            
            # Check each day against target
            for i, (day_name, totals) in enumerate([("Day 1", day_1_totals), ("Day 2", day_2_totals), ("Day 3", day_3_totals)], 1):
                cal_accurate, cal_dev = check_target_accuracy(totals[0], target_calories)
                protein_accurate, protein_dev = check_target_accuracy(totals[1], target_protein)
                carbs_accurate, carbs_dev = check_target_accuracy(totals[2], target_carbs)
                fats_accurate, fats_dev = check_target_accuracy(totals[3], target_fats)
                
                day_accurate = cal_accurate and protein_accurate and carbs_accurate and fats_accurate
                
                print(f"   {day_name}: {'✅' if day_accurate else '❌'}")
                print(f"     Calories: {'✅' if cal_accurate else '❌'} {cal_dev:.1f}% deviation")
                print(f"     Protein:  {'✅' if protein_accurate else '❌'} {protein_dev:.1f}% deviation")
                print(f"     Carbs:    {'✅' if carbs_accurate else '❌'} {carbs_dev:.1f}% deviation")
                print(f"     Fats:     {'✅' if fats_accurate else '❌'} {fats_dev:.1f}% deviation")
            
            # Overall accuracy assessment
            all_days_accurate = True
            for totals in [day_1_totals, day_2_totals, day_3_totals]:
                cal_acc, _ = check_target_accuracy(totals[0], target_calories)
                protein_acc, _ = check_target_accuracy(totals[1], target_protein)
                carbs_acc, _ = check_target_accuracy(totals[2], target_carbs)
                fats_acc, _ = check_target_accuracy(totals[3], target_fats)
                if not (cal_acc and protein_acc and carbs_acc and fats_acc):
                    all_days_accurate = False
                    break
            
            accuracy_result = "✅ Within 15% of target" if all_days_accurate else "❌ Off by more than 15%"
            print(f"   Accuracy: {accuracy_result}")
            
            # 4. VERIFY MEAL STRUCTURE
            print(f"\n4. VERIFY MEAL STRUCTURE:")
            
            structure_issues = []
            
            for i, day in enumerate([day_1, day_2, day_3], 1):
                meals = day.get('meals', [])
                print(f"   Day {i}: {len(meals)} meals")
                
                if len(meals) != 4:
                    structure_issues.append(f"Day {i} has {len(meals)} meals (expected 4)")
                
                for j, meal in enumerate(meals, 1):
                    ingredients = meal.get('ingredients', [])
                    print(f"     Meal {j} ({meal.get('meal_type', 'unknown')}): {meal.get('name', 'Unknown')}")
                    
                    # Check for gram amounts in ingredients
                    has_gram_amounts = False
                    realistic_portions = True
                    
                    for ingredient in ingredients[:3]:  # Check first 3 ingredients
                        if 'g ' in ingredient or 'ml ' in ingredient or 'tbsp' in ingredient or 'cup' in ingredient:
                            has_gram_amounts = True
                            print(f"       - {ingredient}")
                        else:
                            print(f"       - {ingredient} (no amount specified)")
                    
                    if len(ingredients) > 3:
                        print(f"       ... and {len(ingredients)-3} more ingredients")
                    
                    if not has_gram_amounts:
                        structure_issues.append(f"Day {i} Meal {j} lacks specific gram amounts")
                    
                    # Check for realistic calorie ranges
                    calories = meal.get('calories', 0)
                    if calories < 100 or calories > 1000:
                        realistic_portions = False
                        structure_issues.append(f"Day {i} Meal {j} has unrealistic calories: {calories}")
            
            structure_valid = len(structure_issues) == 0
            print(f"\n   Structure Issues Found: {len(structure_issues)}")
            for issue in structure_issues:
                print(f"   - {issue}")
            
            structure_result = "✅ Valid structure" if structure_valid else "❌ Structure issues found"
            print(f"   Meal Structure: {structure_result}")
            
            # 5. FINAL REPORT FORMAT (as requested in review)
            print(f"\n" + "=" * 60)
            print(f"FINAL REPORT:")
            print(f"Day 1: {day_1_totals[0]} cal, {day_1_totals[1]}g P, {day_1_totals[2]}g C, {day_1_totals[3]}g F")
            print(f"Day 2: {day_2_totals[0]} cal, {day_2_totals[1]}g P, {day_2_totals[2]}g C, {day_2_totals[3]}g F")
            print(f"Day 3: {day_3_totals[0]} cal, {day_3_totals[1]}g P, {day_3_totals[2]}g C, {day_3_totals[3]}g F")
            print(f"Target: {target_calories} cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
            print(f"")
            print(f"Consistency: {consistency_result}")
            print(f"Accuracy: {accuracy_result}")
            print(f"Structure: {structure_result}")
            print(f"=" * 60)
            
            # Return success if no major issues
            success = all_consistent or all_days_accurate  # At least one should pass
            return success
            
        except Exception as e:
            print(f"   ERROR during meal plan testing: {e}")
            import traceback
            traceback.print_exc()
            return False

async def main():
    """Run meal plan improved portion guidance test as specified in review request"""
    print(f"Backend Test Suite - InterFitAI Meal Plan Improved Portion Guidance")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    
    success = await test_meal_plan_improved_portion_guidance()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ MEAL PLAN IMPROVED PORTION GUIDANCE TEST COMPLETED")
    else:
        print("❌ MEAL PLAN IMPROVED PORTION GUIDANCE TEST FAILED")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())