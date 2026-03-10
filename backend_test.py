#!/usr/bin/env python3
"""
Backend Test Suite for InterFitAI API - FINAL MEAL PLAN MACRO ACCURACY VERIFICATION

This test suite performs comprehensive testing of the meal plan generation endpoints
to verify that daily totals EXACTLY match user targets for all 3 days.

Test focuses on:
1. Template-based meal plan (no preferred foods)
2. AI-generated meal plan with preferred foods  
3. Keto meal plan

Acceptance criteria: ALL daily totals (calories, protein, carbs, fats) must EXACTLY 
match the target values for ALL 3 days.
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
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"  # User from review request

class MealPlanMacroAccuracyTester:
    def __init__(self):
        self.session = None
        self.test_results = []
        
    async def setup(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=10)
        )
        
    async def cleanup(self):
        """Clean up resources"""
        if self.session:
            await self.session.close()
            
    async def get_user_profile(self) -> Dict[str, Any]:
        """Get user profile to understand target macros"""
        try:
            async with self.session.get(f"{BACKEND_URL}/profile/{TEST_USER_ID}") as response:
                if response.status == 200:
                    profile_data = await response.json()
                    logger.info(f"✅ Retrieved user profile for {TEST_USER_ID}")
                    
                    macros = profile_data.get('calculated_macros', {})
                    calorie_adj = profile_data.get('calorie_adjustment', 0)
                    
                    # Apply calorie adjustment
                    target_calories = macros.get('calories', 0) + calorie_adj
                    target_protein = macros.get('protein', 0)
                    target_carbs = macros.get('carbs', 0)
                    target_fats = macros.get('fats', 0)
                    
                    logger.info(f"Target macros: {target_calories} cal, {target_protein}g P, {target_carbs}g C, {target_fats}g F")
                    
                    return {
                        'calories': target_calories,
                        'protein': target_protein,
                        'carbs': target_carbs,
                        'fats': target_fats
                    }
                else:
                    logger.error(f"❌ Failed to get user profile: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"❌ Error getting user profile: {e}")
            return {}
    
    async def analyze_meal_plan_accuracy(self, meal_plan_data: Dict[str, Any], targets: Dict[str, float], test_name: str) -> Dict[str, Any]:
        """Analyze meal plan for macro accuracy across all 3 days"""
        try:
            meal_days = meal_plan_data.get('meal_days', [])
            logger.info(f"\n=== {test_name.upper()} MEAL PLAN ANALYSIS ===")
            logger.info(f"Target: {targets['calories']} cal, {targets['protein']}g P, {targets['carbs']}g C, {targets['fats']}g F")
            
            analysis_results = {
                'test_name': test_name,
                'target_macros': targets,
                'daily_results': [],
                'all_days_exact': True,
                'total_deviations': {'calories': 0, 'protein': 0, 'carbs': 0, 'fats': 0}
            }
            
            for i, day in enumerate(meal_days, 1):
                day_totals = {
                    'calories': day.get('total_calories', 0),
                    'protein': day.get('total_protein', 0),
                    'carbs': day.get('total_carbs', 0),
                    'fats': day.get('total_fats', 0)
                }
                
                # Calculate deviations from targets
                deviations = {}
                exact_match = True
                for macro in ['calories', 'protein', 'carbs', 'fats']:
                    deviation = abs(day_totals[macro] - targets[macro])
                    deviations[macro] = deviation
                    analysis_results['total_deviations'][macro] += deviation
                    if deviation > 0:
                        exact_match = False
                        analysis_results['all_days_exact'] = False
                
                day_result = {
                    'day': i,
                    'totals': day_totals,
                    'deviations': deviations,
                    'exact_match': exact_match
                }
                analysis_results['daily_results'].append(day_result)
                
                # Log day results
                status = "✅ EXACT" if exact_match else "❌ DEVIATION"
                logger.info(f"Day {i}: {day_totals['calories']:.0f}cal, {day_totals['protein']:.0f}g P, {day_totals['carbs']:.0f}g C, {day_totals['fats']:.0f}g F {status}")
                
                # Show deviations if any
                if not exact_match:
                    dev_strs = []
                    for macro in ['calories', 'protein', 'carbs', 'fats']:
                        if deviations[macro] > 0:
                            dev_strs.append(f"{macro}: ±{deviations[macro]:.1f}")
                    logger.info(f"  Deviations: {', '.join(dev_strs)}")
            
            # Overall summary
            if analysis_results['all_days_exact']:
                logger.info(f"🎉 {test_name}: ALL 3 DAYS EXACTLY MATCH TARGETS!")
                analysis_results['status'] = 'PASS'
            else:
                logger.info(f"❌ {test_name}: FAILED - Daily totals do not exactly match targets")
                analysis_results['status'] = 'FAIL'
                
            return analysis_results
            
        except Exception as e:
            logger.error(f"❌ Error analyzing meal plan accuracy: {e}")
            return {'test_name': test_name, 'status': 'ERROR', 'error': str(e)}

    async def test_template_meal_plan(self, targets: Dict[str, float]) -> Dict[str, Any]:
        """TEST 1: Template-based meal plan (no preferred foods)"""
        test_name = "Template-based meal plan"
        logger.info(f"\n🧪 TESTING: {test_name}")
        
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "allergies": []
        }
        
        try:
            start_time = time.time()
            async with self.session.post(f"{BACKEND_URL}/mealplans/generate", json=payload) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    meal_plan = await response.json()
                    logger.info(f"✅ Generated meal plan: '{meal_plan.get('name', 'Unknown')}' in {response_time:.2f}s")
                    
                    # Analyze accuracy
                    return await self.analyze_meal_plan_accuracy(meal_plan, targets, test_name)
                else:
                    error_text = await response.text()
                    logger.error(f"❌ {test_name} failed: {response.status} - {error_text}")
                    return {'test_name': test_name, 'status': 'ERROR', 'error': f"{response.status}: {error_text}"}
                    
        except Exception as e:
            logger.error(f"❌ Error in {test_name}: {e}")
            return {'test_name': test_name, 'status': 'ERROR', 'error': str(e)}

    async def test_ai_meal_plan_with_preferred_foods(self, targets: Dict[str, float]) -> Dict[str, Any]:
        """TEST 2: AI-generated meal plan with preferred foods"""
        test_name = "AI-generated meal plan with preferred foods"
        logger.info(f"\n🧪 TESTING: {test_name}")
        
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "balanced",
            "preferred_foods": "chicken breast, sweet potato, eggs",
            "allergies": []
        }
        
        try:
            start_time = time.time()
            async with self.session.post(f"{BACKEND_URL}/mealplans/generate", json=payload) as response:
                response_time = time.time() - start_time
                
                if response.status == 200:
                    meal_plan = await response.json()
                    logger.info(f"✅ Generated meal plan: '{meal_plan.get('name', 'Unknown')}' in {response_time:.2f}s")
                    
                    # Verify preferred foods are included
                    preferred_foods = ["chicken breast", "sweet potato", "eggs"]
                    meals_text = json.dumps(meal_plan).lower()
                    found_foods = [food for food in preferred_foods if food.replace(" ", "") in meals_text.replace(" ", "")]
                    logger.info(f"Preferred foods found: {found_foods}")
                    
                    # Analyze accuracy
                    return await self.analyze_meal_plan_accuracy(meal_plan, targets, test_name)
                else:
                    error_text = await response.text()
                    logger.error(f"❌ {test_name} failed: {response.status} - {error_text}")
                    return {'test_name': test_name, 'status': 'ERROR', 'error': f"{response.status}: {error_text}"}
                    
        except Exception as e:
            logger.error(f"❌ Error in {test_name}: {e}")
            return {'test_name': test_name, 'status': 'ERROR', 'error': str(e)}

    async def test_keto_meal_plan(self, targets: Dict[str, float]) -> Dict[str, Any]:
        """TEST 3: Keto meal plan"""
        test_name = "Keto meal plan"
        logger.info(f"\n🧪 TESTING: {test_name}")
        
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
                    logger.info(f"✅ Generated meal plan: '{meal_plan.get('name', 'Unknown')}' in {response_time:.2f}s")
                    
                    # Check keto compliance (low carbs)
                    meal_days = meal_plan.get('meal_days', [])
                    if meal_days:
                        day1_carbs = meal_days[0].get('total_carbs', 0)
                        logger.info(f"Day 1 carbs: {day1_carbs}g (keto compliance: {'✅' if day1_carbs < 50 else '❌'})")
                    
                    # Analyze accuracy (should still match user's actual targets, not keto-specific ones)
                    return await self.analyze_meal_plan_accuracy(meal_plan, targets, test_name)
                else:
                    error_text = await response.text()
                    logger.error(f"❌ {test_name} failed: {response.status} - {error_text}")
                    return {'test_name': test_name, 'status': 'ERROR', 'error': f"{response.status}: {error_text}"}
                    
        except Exception as e:
            logger.error(f"❌ Error in {test_name}: {e}")
            return {'test_name': test_name, 'status': 'ERROR', 'error': str(e)}

    async def run_comprehensive_test(self):
        """Run all meal plan macro accuracy tests"""
        logger.info("=" * 80)
        logger.info("🧪 COMPREHENSIVE MEAL PLAN MACRO ACCURACY TEST - FINAL VERIFICATION")
        logger.info("=" * 80)
        
        await self.setup()
        
        try:
            # Get user targets
            targets = await self.get_user_profile()
            if not targets:
                logger.error("❌ Cannot proceed without user profile targets")
                return
            
            # Run all tests
            test1_result = await self.test_template_meal_plan(targets)
            self.test_results.append(test1_result)
            
            test2_result = await self.test_ai_meal_plan_with_preferred_foods(targets)
            self.test_results.append(test2_result)
            
            test3_result = await self.test_keto_meal_plan(targets)
            self.test_results.append(test3_result)
            
            # Final summary
            await self.generate_final_summary()
            
        finally:
            await self.cleanup()

    async def generate_final_summary(self):
        """Generate final test summary"""
        logger.info("\n" + "=" * 80)
        logger.info("🏁 FINAL MEAL PLAN MACRO ACCURACY TEST SUMMARY")
        logger.info("=" * 80)
        
        all_pass = True
        for result in self.test_results:
            status = result.get('status', 'UNKNOWN')
            test_name = result.get('test_name', 'Unknown Test')
            
            if status == 'PASS':
                logger.info(f"✅ {test_name}: PASS - All daily totals exactly match targets")
            elif status == 'FAIL':
                logger.info(f"❌ {test_name}: FAIL - Daily totals do not exactly match targets")
                all_pass = False
            else:
                logger.info(f"⚠️ {test_name}: ERROR - {result.get('error', 'Unknown error')}")
                all_pass = False
        
        logger.info("\n" + "-" * 40)
        if all_pass and len([r for r in self.test_results if r.get('status') == 'PASS']) == 3:
            logger.info("🎉 OVERALL RESULT: PASS")
            logger.info("All 3 tests have daily totals exactly matching targets!")
            logger.info("✅ Template-based meal plans working perfectly")
            logger.info("✅ AI-generated meal plans with preferred foods working perfectly")  
            logger.info("✅ Keto meal plans working perfectly")
        else:
            logger.info("❌ OVERALL RESULT: FAIL")
            logger.info("Not all tests achieved exact macro target matching.")
            failed_tests = [r['test_name'] for r in self.test_results if r.get('status') != 'PASS']
            logger.info(f"Failed tests: {', '.join(failed_tests)}")

async def main():
    """Main test runner"""
    tester = MealPlanMacroAccuracyTester()
    await tester.run_comprehensive_test()

if __name__ == "__main__":
    asyncio.run(main())