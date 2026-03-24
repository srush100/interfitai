#!/usr/bin/env python3
"""
Backend Test Suite for InterFitAI API - Review Request Testing

This test suite tests the specific meal plan scenarios requested in the review:

TEST 1: Vegan Meal Plan Accuracy
- Daily totals should match targets exactly
- Meals should only contain vegan ingredients (no meat, dairy, eggs)

TEST 2: Keto Meal Plan - Should show LOW carbs  
- target_carbs should be LOW (under 50g per day), NOT 227g
- Meals should have minimal carbs

TEST 3: Carnivore Meal Plan - Should show ZERO/near-zero carbs
- target_carbs should be very low (under 10g per day)
- Meals should contain only meat, fish, eggs, butter

TEST 4: Meal Replacement Accuracy
- Generate balanced meal plan
- Get breakfast from Day 1, note its calories
- Call alternate meal endpoint
- Verify alternate meal calories within ±10% of original

ACCEPTANCE CRITERIA:
- Vegan: No animal products in ingredients
- Keto: target_carbs < 50g
- Carnivore: target_carbs < 10g  
- Meal replacement: Calories within ±10% of original
"""

import asyncio
import aiohttp
import json
import logging
import time
from typing import Dict, List, Any
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration
BACKEND_URL = "https://nutrition-debug-1.preview.emergentagent.com/api"
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"  # User from review request

class ReviewRequestTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        
    async def setup(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=120),
            connector=aiohttp.TCPConnector(limit=10)
        )
        
    async def cleanup(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
            
    async def health_check(self):
        """Verify backend is accessible"""
        try:
            start_time = time.time()
            async with self.session.get(f"{BACKEND_URL}/health") as response:
                response_time = time.time() - start_time
                if response.status == 200:
                    logger.info(f"✅ Health check passed ({response_time:.2f}s)")
                    return True
                else:
                    logger.error(f"❌ Health check failed: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"❌ Health check error: {e}")
            return False

    async def check_vegan_ingredients(self, meal_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Check if meal plan contains only vegan ingredients"""
        non_vegan_ingredients = [
            # Meat
            'chicken', 'beef', 'pork', 'lamb', 'turkey', 'fish', 'salmon', 'tuna', 
            'shrimp', 'bacon', 'ham', 'sausage', 'meat', 'steak', 'jerky',
            # Dairy (but exclude plant-based versions)
            'dairy milk', 'cow milk', 'whole milk', 'skim milk', ' milk ', 'cheese', 'butter', 'cream', 'yogurt', 'whey', 'casein',
            # Eggs
            'egg', 'eggs'
        ]
        
        # Plant-based items that should NOT be flagged (contains excluded words but are vegan)
        vegan_exceptions = [
            'coconut milk', 'almond milk', 'soy milk', 'oat milk', 'rice milk', 'plant milk',
            'coconut cream', 'cashew cream', 'oat cream',
            'almond butter', 'peanut butter', 'cashew butter', 'nut butter', 'seed butter',
            'nutritional yeast'
        ]
        
        violations = []
        meal_days = meal_plan.get('meal_days', [])
        
        for day_idx, day in enumerate(meal_days, 1):
            for meal_idx, meal in enumerate(day.get('meals', []), 1):
                ingredients_text = ' '.join(meal.get('ingredients', [])).lower()
                meal_name = meal.get('name', '').lower()
                instructions = meal.get('instructions', '').lower()
                
                # Check all text for non-vegan ingredients
                full_text = f"{meal_name} {ingredients_text} {instructions}"
                
                # First check if any vegan exceptions are present
                is_vegan_friendly = any(exception in full_text for exception in vegan_exceptions)
                
                for ingredient in non_vegan_ingredients:
                    if ingredient in full_text and not is_vegan_friendly:
                        # Additional check: if it's "milk", make sure it's not plant milk
                        if ingredient == ' milk ' and any(plant in full_text for plant in ['coconut', 'almond', 'soy', 'oat', 'rice', 'plant']):
                            continue
                        if ingredient in ['butter'] and any(nut in full_text for nut in ['almond', 'peanut', 'cashew', 'nut']):
                            continue
                            
                        violations.append({
                            'day': day_idx,
                            'meal': meal_idx,
                            'meal_name': meal.get('name', 'Unknown'),
                            'violation': ingredient,
                            'context': full_text[:100] + '...'
                        })
        
        return {
            'is_vegan': len(violations) == 0,
            'violations': violations,
            'total_violations': len(violations)
        }

    async def test_vegan_meal_plan(self) -> Dict[str, Any]:
        """TEST 1: Vegan Meal Plan Accuracy"""
        test_name = "Vegan Meal Plan"
        logger.info(f"\n🧪 TEST 1: {test_name}")
        
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "vegan",
            "allergies": []
        }
        
        try:
            start_time = time.time()
            async with self.session.post(f"{BACKEND_URL}/mealplans/generate", json=payload) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    meal_plan = await response.json()
                    logger.info(f"✅ Generated vegan meal plan: '{meal_plan.get('name', 'Unknown')}' in {response_time:.2f}s")
                    
                    # Check macro accuracy
                    meal_days = meal_plan.get('meal_days', [])
                    target_cal = meal_plan.get('target_calories', 0)
                    target_pro = meal_plan.get('target_protein', 0)
                    target_carb = meal_plan.get('target_carbs', 0)
                    target_fat = meal_plan.get('target_fats', 0)
                    
                    logger.info(f"Target macros: {target_cal} cal, {target_pro}g P, {target_carb}g C, {target_fat}g F")
                    
                    # Check each day's totals
                    daily_accuracy = []
                    for i, day in enumerate(meal_days, 1):
                        day_cal = day.get('total_calories', 0)
                        day_pro = day.get('total_protein', 0) 
                        day_carb = day.get('total_carbs', 0)
                        day_fat = day.get('total_fats', 0)
                        
                        # Calculate deviations
                        cal_dev = abs(day_cal - target_cal)
                        pro_dev = abs(day_pro - target_pro)
                        carb_dev = abs(day_carb - target_carb) 
                        fat_dev = abs(day_fat - target_fat)
                        
                        exact_match = (cal_dev == 0 and pro_dev == 0 and carb_dev == 0 and fat_dev == 0)
                        
                        logger.info(f"Day {i}: {day_cal}cal, {day_pro}g P, {day_carb}g C, {day_fat}g F {'✅' if exact_match else '❌'}")
                        
                        daily_accuracy.append({
                            'day': i,
                            'exact_match': exact_match,
                            'deviations': {'cal': cal_dev, 'pro': pro_dev, 'carb': carb_dev, 'fat': fat_dev}
                        })
                    
                    # Check vegan compliance
                    vegan_check = await self.check_vegan_ingredients(meal_plan)
                    
                    if vegan_check['is_vegan']:
                        logger.info("✅ VEGAN COMPLIANCE: All ingredients are vegan")
                    else:
                        logger.info(f"❌ VEGAN VIOLATIONS: Found {vegan_check['total_violations']} non-vegan ingredients")
                        for v in vegan_check['violations'][:5]:  # Show first 5
                            logger.info(f"  Day {v['day']} Meal {v['meal']}: '{v['violation']}' in {v['meal_name']}")
                    
                    all_exact = all(day['exact_match'] for day in daily_accuracy)
                    
                    return {
                        'test_name': test_name,
                        'status': 'PASS' if (all_exact and vegan_check['is_vegan']) else 'FAIL',
                        'macro_accuracy': all_exact,
                        'vegan_compliance': vegan_check['is_vegan'],
                        'daily_accuracy': daily_accuracy,
                        'vegan_violations': vegan_check['violations'],
                        'response_time': response_time
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ {test_name} failed: {response.status} - {error_text}")
                    return {'test_name': test_name, 'status': 'ERROR', 'error': f"{response.status}: {error_text}"}
                    
        except Exception as e:
            logger.error(f"❌ Error in {test_name}: {e}")
            return {'test_name': test_name, 'status': 'ERROR', 'error': str(e)}

    async def test_keto_meal_plan(self) -> Dict[str, Any]:
        """TEST 2: Keto Meal Plan - Should show LOW carbs"""
        test_name = "Keto Meal Plan"
        logger.info(f"\n🧪 TEST 2: {test_name}")
        
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "keto",
            "allergies": []
        }
        
        try:
            start_time = time.time()
            async with self.session.post(f"{BACKEND_URL}/mealplans/generate", json=payload) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    meal_plan = await response.json()
                    logger.info(f"✅ Generated keto meal plan: '{meal_plan.get('name', 'Unknown')}' in {response_time:.2f}s")
                    
                    # Check target carbs
                    target_carb = meal_plan.get('target_carbs', 0)
                    target_cal = meal_plan.get('target_calories', 0)
                    target_pro = meal_plan.get('target_protein', 0)
                    target_fat = meal_plan.get('target_fats', 0)
                    
                    logger.info(f"Target macros: {target_cal} cal, {target_pro}g P, {target_carb}g C, {target_fat}g F")
                    
                    # KETO COMPLIANCE CHECK: target_carbs should be < 50g, NOT 227g
                    keto_compliant = target_carb < 50
                    logger.info(f"Keto compliance (target carbs < 50g): {'✅' if keto_compliant else '❌'} ({target_carb}g)")
                    
                    if not keto_compliant:
                        logger.info(f"❌ CRITICAL: Keto meal plan showing {target_carb}g carbs (should be <50g)")
                    
                    # Check daily totals
                    meal_days = meal_plan.get('meal_days', [])
                    daily_carbs = []
                    
                    for i, day in enumerate(meal_days, 1):
                        day_carb = day.get('total_carbs', 0)
                        daily_carbs.append(day_carb)
                        day_keto_compliant = day_carb < 50
                        logger.info(f"Day {i} carbs: {day_carb}g {'✅' if day_keto_compliant else '❌'}")
                    
                    # Check meal contents for low-carb foods
                    meal_names = []
                    for day in meal_days:
                        for meal in day.get('meals', []):
                            meal_names.append(meal.get('name', ''))
                    
                    logger.info(f"Sample meals: {meal_names[:3]}")
                    
                    return {
                        'test_name': test_name,
                        'status': 'PASS' if keto_compliant else 'FAIL',
                        'target_carbs': target_carb,
                        'keto_compliant': keto_compliant,
                        'daily_carbs': daily_carbs,
                        'response_time': response_time
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ {test_name} failed: {response.status} - {error_text}")
                    return {'test_name': test_name, 'status': 'ERROR', 'error': f"{response.status}: {error_text}"}
                    
        except Exception as e:
            logger.error(f"❌ Error in {test_name}: {e}")
            return {'test_name': test_name, 'status': 'ERROR', 'error': str(e)}

    async def test_carnivore_meal_plan(self) -> Dict[str, Any]:
        """TEST 3: Carnivore Meal Plan - Should show ZERO/near-zero carbs"""
        test_name = "Carnivore Meal Plan"
        logger.info(f"\n🧪 TEST 3: {test_name}")
        
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "carnivore",
            "allergies": []
        }
        
        try:
            start_time = time.time()
            async with self.session.post(f"{BACKEND_URL}/mealplans/generate", json=payload) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    meal_plan = await response.json()
                    logger.info(f"✅ Generated carnivore meal plan: '{meal_plan.get('name', 'Unknown')}' in {response_time:.2f}s")
                    
                    # Check target carbs
                    target_carb = meal_plan.get('target_carbs', 0)
                    target_cal = meal_plan.get('target_calories', 0)
                    target_pro = meal_plan.get('target_protein', 0)
                    target_fat = meal_plan.get('target_fats', 0)
                    
                    logger.info(f"Target macros: {target_cal} cal, {target_pro}g P, {target_carb}g C, {target_fat}g F")
                    
                    # CARNIVORE COMPLIANCE CHECK: target_carbs should be < 10g
                    carnivore_compliant = target_carb < 10
                    logger.info(f"Carnivore compliance (target carbs < 10g): {'✅' if carnivore_compliant else '❌'} ({target_carb}g)")
                    
                    # Check daily totals
                    meal_days = meal_plan.get('meal_days', [])
                    daily_carbs = []
                    
                    for i, day in enumerate(meal_days, 1):
                        day_carb = day.get('total_carbs', 0)
                        daily_carbs.append(day_carb)
                        day_carnivore_compliant = day_carb < 10
                        logger.info(f"Day {i} carbs: {day_carb}g {'✅' if day_carnivore_compliant else '❌'}")
                    
                    # Check meal contents for meat-only foods  
                    meal_names = []
                    carnivore_foods = ['steak', 'beef', 'chicken', 'fish', 'salmon', 'eggs', 'bacon', 'lamb', 'pork']
                    
                    for day in meal_days:
                        for meal in day.get('meals', []):
                            meal_name = meal.get('name', '').lower()
                            meal_names.append(meal.get('name', ''))
                            
                            # Check if meal contains carnivore foods
                            contains_meat = any(meat in meal_name for meat in carnivore_foods)
                            if not contains_meat:
                                logger.info(f"⚠️ Non-carnivore meal detected: {meal.get('name', '')}")
                    
                    logger.info(f"Sample meals: {meal_names[:4]}")
                    
                    return {
                        'test_name': test_name,
                        'status': 'PASS' if carnivore_compliant else 'FAIL',
                        'target_carbs': target_carb,
                        'carnivore_compliant': carnivore_compliant,
                        'daily_carbs': daily_carbs,
                        'meal_names': meal_names[:4],
                        'response_time': response_time
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ {test_name} failed: {response.status} - {error_text}")
                    return {'test_name': test_name, 'status': 'ERROR', 'error': f"{response.status}: {error_text}"}
                    
        except Exception as e:
            logger.error(f"❌ Error in {test_name}: {e}")
            return {'test_name': test_name, 'status': 'ERROR', 'error': str(e)}

    async def test_meal_replacement_accuracy(self) -> Dict[str, Any]:
        """TEST 4: Meal Replacement Accuracy"""
        test_name = "Meal Replacement Accuracy"
        logger.info(f"\n🧪 TEST 4: {test_name}")
        
        try:
            # Step 1: Generate balanced meal plan
            logger.info("Step 1: Generating balanced meal plan...")
            payload = {
                "user_id": TEST_USER_ID,
                "food_preferences": "balanced",
                "allergies": []
            }
            
            meal_plan_id = None
            original_breakfast_calories = 0
            
            async with self.session.post(f"{BACKEND_URL}/mealplans/generate", json=payload) as response:
                if response.status == 200:
                    meal_plan = await response.json()
                    meal_plan_id = meal_plan.get('id')
                    logger.info(f"✅ Generated balanced meal plan: {meal_plan.get('name', 'Unknown')}")
                    
                    # Get Day 1 Breakfast calories
                    meal_days = meal_plan.get('meal_days', [])
                    if meal_days and len(meal_days) > 0:
                        day1_meals = meal_days[0].get('meals', [])
                        if day1_meals and len(day1_meals) > 0:
                            breakfast = day1_meals[0]  # First meal is breakfast
                            original_breakfast_calories = breakfast.get('calories', 0)
                            logger.info(f"Original breakfast: '{breakfast.get('name', 'Unknown')}' - {original_breakfast_calories} calories")
                        else:
                            logger.error("❌ No meals found in Day 1")
                            return {'test_name': test_name, 'status': 'ERROR', 'error': 'No meals in Day 1'}
                    else:
                        logger.error("❌ No meal days found")
                        return {'test_name': test_name, 'status': 'ERROR', 'error': 'No meal days found'}
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to generate meal plan: {response.status} - {error_text}")
                    return {'test_name': test_name, 'status': 'ERROR', 'error': f"Failed to generate meal plan: {response.status}"}
            
            if not meal_plan_id or original_breakfast_calories == 0:
                logger.error("❌ Could not get meal plan ID or breakfast calories")
                return {'test_name': test_name, 'status': 'ERROR', 'error': 'Missing meal plan ID or breakfast calories'}
            
            # Step 2: Generate alternate meal
            logger.info("Step 2: Generating alternate meal...")
            alternate_payload = {
                "user_id": TEST_USER_ID,
                "meal_plan_id": meal_plan_id,
                "day_index": 0,
                "meal_index": 0,  # Breakfast
                "swap_preference": "similar"
            }
            
            async with self.session.post(f"{BACKEND_URL}/mealplan/alternate", json=alternate_payload) as response:
                if response.status == 200:
                    response_data = await response.json()
                    alternate_meal = response_data.get('alternate_meal', response_data)
                    alternate_calories = alternate_meal.get('calories', 0)
                    alternate_name = alternate_meal.get('name', 'Unknown')
                    
                    logger.info(f"✅ Generated alternate meal: '{alternate_name}' - {alternate_calories} calories")
                    
                    # Calculate calorie difference
                    calorie_diff = abs(alternate_calories - original_breakfast_calories)
                    percent_diff = (calorie_diff / original_breakfast_calories * 100) if original_breakfast_calories > 0 else 100
                    
                    # Check ±10% tolerance
                    within_tolerance = percent_diff <= 10
                    
                    logger.info(f"Calorie comparison:")
                    logger.info(f"  Original: {original_breakfast_calories} cal")
                    logger.info(f"  Alternate: {alternate_calories} cal")
                    logger.info(f"  Difference: {calorie_diff} cal ({percent_diff:.1f}%)")
                    logger.info(f"  Within ±10%: {'✅' if within_tolerance else '❌'}")
                    
                    return {
                        'test_name': test_name,
                        'status': 'PASS' if within_tolerance else 'FAIL',
                        'original_calories': original_breakfast_calories,
                        'alternate_calories': alternate_calories,
                        'calorie_difference': calorie_diff,
                        'percent_difference': percent_diff,
                        'within_tolerance': within_tolerance,
                        'alternate_name': alternate_name
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to generate alternate meal: {response.status} - {error_text}")
                    return {'test_name': test_name, 'status': 'ERROR', 'error': f"Failed to generate alternate meal: {response.status}"}
                    
        except Exception as e:
            logger.error(f"❌ Error in {test_name}: {e}")
            return {'test_name': test_name, 'status': 'ERROR', 'error': str(e)}

    async def run_review_tests(self):
        """Run all review request tests"""
        logger.info("=" * 80)
        logger.info("🧪 REVIEW REQUEST TESTING - Meal Plan Fixes Verification")
        logger.info("=" * 80)
        
        await self.setup()
        
        try:
            # Health check first
            if not await self.health_check():
                logger.error("❌ Backend health check failed, aborting tests")
                return
            
            # Run all 4 tests
            logger.info("\nRunning 4 meal plan tests as specified in review request...")
            
            test1_result = await self.test_vegan_meal_plan()
            self.test_results.append(test1_result)
            
            test2_result = await self.test_keto_meal_plan()
            self.test_results.append(test2_result)
            
            test3_result = await self.test_carnivore_meal_plan()
            self.test_results.append(test3_result)
            
            test4_result = await self.test_meal_replacement_accuracy()
            self.test_results.append(test4_result)
            
            # Final summary
            await self.generate_final_summary()
            
        finally:
            await self.cleanup()

    async def generate_final_summary(self):
        """Generate final test summary"""
        logger.info("\n" + "=" * 80)
        logger.info("🏁 REVIEW REQUEST TEST SUMMARY")
        logger.info("=" * 80)
        
        all_pass = True
        passed_tests = 0
        
        for result in self.test_results:
            status = result.get('status', 'UNKNOWN')
            test_name = result.get('test_name', 'Unknown Test')
            
            if status == 'PASS':
                logger.info(f"✅ {test_name}: PASS")
                passed_tests += 1
                
                # Show specific details for each test
                if 'Vegan' in test_name:
                    macro_acc = result.get('macro_accuracy', False)
                    vegan_comp = result.get('vegan_compliance', False)
                    logger.info(f"   - Macro accuracy: {'✅' if macro_acc else '❌'}")
                    logger.info(f"   - Vegan compliance: {'✅' if vegan_comp else '❌'}")
                    
                elif 'Keto' in test_name:
                    keto_comp = result.get('keto_compliant', False)
                    target_carbs = result.get('target_carbs', 0)
                    logger.info(f"   - Target carbs: {target_carbs}g (should be <50g): {'✅' if keto_comp else '❌'}")
                    
                elif 'Carnivore' in test_name:
                    carnivore_comp = result.get('carnivore_compliant', False)
                    target_carbs = result.get('target_carbs', 0)
                    logger.info(f"   - Target carbs: {target_carbs}g (should be <10g): {'✅' if carnivore_comp else '❌'}")
                    
                elif 'Replacement' in test_name:
                    tolerance = result.get('within_tolerance', False)
                    percent_diff = result.get('percent_difference', 0)
                    logger.info(f"   - Calorie difference: {percent_diff:.1f}% (should be ±10%): {'✅' if tolerance else '❌'}")
                    
            elif status == 'FAIL':
                logger.info(f"❌ {test_name}: FAIL")
                all_pass = False
                
                # Show failure reasons
                if 'Vegan' in test_name:
                    violations = result.get('vegan_violations', [])
                    if violations:
                        logger.info(f"   - Found {len(violations)} non-vegan ingredients")
                        
                elif 'Keto' in test_name:
                    target_carbs = result.get('target_carbs', 0)
                    logger.info(f"   - Target carbs too high: {target_carbs}g (should be <50g)")
                    
                elif 'Carnivore' in test_name:
                    target_carbs = result.get('target_carbs', 0)
                    logger.info(f"   - Target carbs too high: {target_carbs}g (should be <10g)")
                    
                elif 'Replacement' in test_name:
                    percent_diff = result.get('percent_difference', 0)
                    logger.info(f"   - Calorie difference too large: {percent_diff:.1f}% (should be ±10%)")
                    
            else:
                logger.info(f"⚠️ {test_name}: ERROR - {result.get('error', 'Unknown error')}")
                all_pass = False
        
        logger.info("\n" + "-" * 40)
        if all_pass and passed_tests == 4:
            logger.info("🎉 OVERALL RESULT: ALL TESTS PASS")
            logger.info("✅ Vegan meal plans: No animal products, exact macro matching")
            logger.info("✅ Keto meal plans: Low carbs (<50g per day)")
            logger.info("✅ Carnivore meal plans: Very low carbs (<10g per day)")
            logger.info("✅ Meal replacement: Calories within ±10% tolerance")
            logger.info("\n✅ All meal plan fixes working correctly as requested!")
        else:
            logger.info("❌ OVERALL RESULT: SOME TESTS FAILED")
            logger.info(f"Passed: {passed_tests}/4 tests")
            failed_tests = [r['test_name'] for r in self.test_results if r.get('status') != 'PASS']
            logger.info(f"Failed tests: {', '.join(failed_tests)}")

async def main():
    """Main test runner"""
    tester = ReviewRequestTester()
    await tester.run_review_tests()

if __name__ == "__main__":
    asyncio.run(main())