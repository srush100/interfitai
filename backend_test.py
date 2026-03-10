#!/usr/bin/env python3

import asyncio
import httpx
import json
import time
from datetime import datetime

# Configuration
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# Target macros from the review request
TARGET_CALORIES = 2273
TARGET_PROTEIN = 170
TARGET_CARBS = 227
TARGET_FATS = 76

def log_test(message):
    """Log test messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def analyze_macro_accuracy(actual_cal, actual_pro, actual_carb, actual_fat, day_name):
    """Analyze if macros hit EXACT targets and return results"""
    results = {
        'cal_diff': actual_cal - TARGET_CALORIES,
        'pro_diff': actual_pro - TARGET_PROTEIN,
        'carb_diff': actual_carb - TARGET_CARBS,
        'fat_diff': actual_fat - TARGET_FATS,
        'cal_pass': actual_cal == TARGET_CALORIES,
        'pro_pass': actual_pro == TARGET_PROTEIN,
        'carb_pass': actual_carb == TARGET_CARBS,
        'fat_pass': actual_fat == TARGET_FATS
    }
    
    # Check if all macros match exactly
    results['perfect_match'] = all([results['cal_pass'], results['pro_pass'], results['carb_pass'], results['fat_pass']])
    
    return results

def check_food_specificity(meals, expected_foods):
    """Check if meals use specific food names instead of generic ones"""
    specificity_issues = []
    found_foods = {}
    
    for meal in meals:
        meal_name = meal.get('name', '')
        ingredients = meal.get('ingredients', [])
        
        # Check for generic "steak" vs specific cuts
        if 'steak' in expected_foods:
            if 'steak' in meal_name.lower() and not any(cut in meal_name.lower() for cut in ['sirloin', 'ribeye', 'filet', 'strip', 'flank', 'skirt']):
                # Check ingredients for specificity
                steak_specific = False
                for ingredient in ingredients:
                    if any(cut in ingredient.lower() for cut in ['sirloin', 'ribeye', 'filet', 'strip', 'flank', 'skirt']):
                        steak_specific = True
                        found_foods['steak'] = ingredient
                        break
                
                if not steak_specific:
                    specificity_issues.append(f"Generic 'steak' found in '{meal_name}' - should specify cut (sirloin, ribeye, etc.)")
        
        # Check for chicken specificity
        if 'chicken breast' in expected_foods:
            for ingredient in ingredients:
                if 'chicken' in ingredient.lower():
                    if 'breast' in ingredient.lower():
                        found_foods['chicken_breast'] = ingredient
                    elif ingredient.lower().strip() == 'chicken':
                        specificity_issues.append(f"Generic 'chicken' found - should specify 'chicken breast' in '{ingredient}'")
    
    return specificity_issues, found_foods

async def test_meal_plan_generation():
    """Test comprehensive meal plan macro accuracy"""
    log_test("🧪 COMPREHENSIVE MEAL PLAN MACRO ACCURACY TEST STARTING")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        
        # TEST 1: Generic "steak" preference (should pick appropriate cut)
        log_test("=" * 80)
        log_test("TEST 1: Generic 'steak' preference (should pick appropriate cut)")
        log_test("=" * 80)
        
        test1_request = {
            "user_id": TEST_USER_ID,
            "food_preferences": "none",
            "preferred_foods": "steak, rice, eggs"
        }
        
        log_test(f"Request: POST /api/mealplans/generate")
        log_test(f"Payload: {json.dumps(test1_request, indent=2)}")
        
        start_time = time.time()
        response1 = await client.post(f"{BACKEND_URL}/mealplans/generate", json=test1_request)
        response_time1 = time.time() - start_time
        
        log_test(f"Response time: {response_time1:.2f}s")
        log_test(f"Status code: {response1.status_code}")
        
        if response1.status_code == 200:
            meal_plan1 = response1.json()
            log_test(f"✅ Generated meal plan: '{meal_plan1.get('name')}'")
            
            # Analyze each day's macros
            test1_results = {}
            for i, day in enumerate(meal_plan1.get('meal_days', []), 1):
                day_name = f"Day {i}"
                actual_cal = day.get('total_calories', 0)
                actual_pro = day.get('total_protein', 0)
                actual_carb = day.get('total_carbs', 0)
                actual_fat = day.get('total_fats', 0)
                
                results = analyze_macro_accuracy(actual_cal, actual_pro, actual_carb, actual_fat, day_name)
                test1_results[day_name] = results
                
                # Log results
                status = "✅" if results['perfect_match'] else "❌"
                log_test(f"{status} {day_name}: {actual_cal} cal, {actual_pro}g P, {actual_carb}g C, {actual_fat}g F")
                log_test(f"    Target: {TARGET_CALORIES} cal, {TARGET_PROTEIN}g P, {TARGET_CARBS}g C, {TARGET_FATS}g F")
                if not results['perfect_match']:
                    log_test(f"    Diff: {results['cal_diff']:+} cal, {results['pro_diff']:+}g P, {results['carb_diff']:+}g C, {results['fat_diff']:+}g F")
            
            # Check steak specificity
            all_meals = []
            for day in meal_plan1.get('meal_days', []):
                all_meals.extend(day.get('meals', []))
            
            specificity_issues, found_foods = check_food_specificity(all_meals, ["steak", "rice", "eggs"])
            
            log_test("\n📋 STEAK SPECIFICITY CHECK:")
            if specificity_issues:
                for issue in specificity_issues:
                    log_test(f"❌ {issue}")
            else:
                log_test("✅ All steak references are specific cuts")
            
            if 'steak' in found_foods:
                log_test(f"✅ Found specific steak: {found_foods['steak']}")
        else:
            log_test(f"❌ FAILED - Status: {response1.status_code}")
            log_test(f"Error: {response1.text}")
            return False
        
        # TEST 2: Specific food preference
        log_test("\n" + "=" * 80)
        log_test("TEST 2: Specific food preference (chicken breast, brown rice)")
        log_test("=" * 80)
        
        test2_request = {
            "user_id": TEST_USER_ID,
            "food_preferences": "none",
            "preferred_foods": "chicken breast, brown rice"
        }
        
        log_test(f"Request: POST /api/mealplans/generate")
        log_test(f"Payload: {json.dumps(test2_request, indent=2)}")
        
        start_time = time.time()
        response2 = await client.post(f"{BACKEND_URL}/mealplans/generate", json=test2_request)
        response_time2 = time.time() - start_time
        
        log_test(f"Response time: {response_time2:.2f}s")
        log_test(f"Status code: {response2.status_code}")
        
        if response2.status_code == 200:
            meal_plan2 = response2.json()
            log_test(f"✅ Generated meal plan: '{meal_plan2.get('name')}'")
            
            # Analyze each day's macros
            test2_results = {}
            for i, day in enumerate(meal_plan2.get('meal_days', []), 1):
                day_name = f"Day {i}"
                actual_cal = day.get('total_calories', 0)
                actual_pro = day.get('total_protein', 0)
                actual_carb = day.get('total_carbs', 0)
                actual_fat = day.get('total_fats', 0)
                
                results = analyze_macro_accuracy(actual_cal, actual_pro, actual_carb, actual_fat, day_name)
                test2_results[day_name] = results
                
                # Log results
                status = "✅" if results['perfect_match'] else "❌"
                log_test(f"{status} {day_name}: {actual_cal} cal, {actual_pro}g P, {actual_carb}g C, {actual_fat}g F")
                if not results['perfect_match']:
                    log_test(f"    Diff: {results['cal_diff']:+} cal, {results['pro_diff']:+}g P, {results['carb_diff']:+}g C, {results['fat_diff']:+}g F")
            
            # Check chicken breast specificity
            all_meals2 = []
            for day in meal_plan2.get('meal_days', []):
                all_meals2.extend(day.get('meals', []))
            
            specificity_issues2, found_foods2 = check_food_specificity(all_meals2, ["chicken breast", "brown rice"])
            
            log_test("\n📋 CHICKEN BREAST SPECIFICITY CHECK:")
            if 'chicken_breast' in found_foods2:
                log_test(f"✅ Uses chicken breast specifically: {found_foods2['chicken_breast']}")
            else:
                log_test("❌ Did not find specific 'chicken breast' usage")
            
            if specificity_issues2:
                for issue in specificity_issues2:
                    log_test(f"❌ {issue}")
        else:
            log_test(f"❌ FAILED - Status: {response2.status_code}")
            log_test(f"Error: {response2.text}")
            return False
        
        # SUMMARY REPORT
        log_test("\n" + "=" * 80)
        log_test("🎯 FINAL RESULTS SUMMARY")
        log_test("=" * 80)
        
        # Test 1 Summary
        test1_perfect_days = sum(1 for results in test1_results.values() if results['perfect_match'])
        log_test(f"TEST 1 (steak, rice, eggs):")
        for day_name, results in test1_results.items():
            status = "✅" if results['perfect_match'] else "❌"
            actual_cal = TARGET_CALORIES + results['cal_diff']
            actual_pro = TARGET_PROTEIN + results['pro_diff']
            actual_carb = TARGET_CARBS + results['carb_diff']
            actual_fat = TARGET_FATS + results['fat_diff']
            log_test(f"{day_name}: {actual_cal} cal, {actual_pro}g P, {actual_carb}g C, {actual_fat}g F (target: {TARGET_CALORIES}/{TARGET_PROTEIN}/{TARGET_CARBS}/{TARGET_FATS}) {status}")
        
        if specificity_issues:
            log_test(f"Steak specificity: ❌ Generic steak found")
        else:
            log_test(f"Steak specificity: ✅ Specific cuts used")
        
        # Test 2 Summary  
        test2_perfect_days = sum(1 for results in test2_results.values() if results['perfect_match'])
        log_test(f"\nTEST 2 (chicken breast, brown rice):")
        for day_name, results in test2_results.items():
            status = "✅" if results['perfect_match'] else "❌"
            actual_cal = TARGET_CALORIES + results['cal_diff']
            actual_pro = TARGET_PROTEIN + results['pro_diff']
            actual_carb = TARGET_CARBS + results['carb_diff']
            actual_fat = TARGET_FATS + results['fat_diff']
            log_test(f"{day_name}: {actual_cal} cal, {actual_pro}g P, {actual_carb}g C, {actual_fat}g F {status}")
        
        chicken_breast_ok = 'chicken_breast' in found_foods2
        log_test(f"Uses chicken breast specifically? {'✅' if chicken_breast_ok else '❌'}")
        
        # Overall assessment
        total_perfect_days = test1_perfect_days + test2_perfect_days
        total_days = len(test1_results) + len(test2_results)
        
        log_test(f"\n🎯 OVERALL: {total_perfect_days}/{total_days} days hit exact targets")
        if total_perfect_days == total_days and not specificity_issues and chicken_breast_ok:
            log_test("✅ All macros match targets perfectly AND food specificity is correct")
            return True
        else:
            log_test("❌ Issues found with macro accuracy or food specificity")
            return False

async def main():
    """Main test execution"""
    log_test("🚀 Starting InterFitAI Meal Plan Macro Accuracy Testing")
    
    try:
        success = await test_meal_plan_generation()
        
        if success:
            log_test("\n🎉 ALL TESTS PASSED - Meal plan generation working perfectly!")
        else:
            log_test("\n💥 SOME TESTS FAILED - See issues above")
            
    except Exception as e:
        log_test(f"💥 CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())