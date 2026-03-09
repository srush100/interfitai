#!/usr/bin/env python3
"""
Backend API Testing for InterFitAI - Meal Plan Macro Accuracy Validation

This script tests the meal plan macro accuracy as specifically requested:
1. POST /api/mealplans/generate - Generate meal plan with specific macro targets
2. Validate macro accuracy by summing Day 1 meals
3. Compare against targets with acceptable tolerance
4. Report detailed results in specified format
"""

import httpx
import json
import asyncio
import time
from datetime import datetime

# Configuration
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"  # Specified in review request

# Target macro values for testing
TARGET_CALORIES = 2200
TARGET_PROTEIN = 180
TARGET_CARBS = 200
TARGET_FATS = 70

# Acceptable tolerances
CALORIE_TOLERANCE = 50
MACRO_TOLERANCE = 10

class MealPlanMacroTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)  # Extended timeout for AI generation
        self.results = []
        
    def log_result(self, test_name: str, success: bool, details: str, response_time: float = 0):
        """Log test result with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append({
            "timestamp": timestamp,
            "test": test_name,
            "status": status,
            "details": details,
            "response_time": f"{response_time:.2f}s" if response_time > 0 else "N/A"
        })
        print(f"[{timestamp}] {status}: {test_name}")
        print(f"    Details: {details}")
        if response_time > 0:
            print(f"    Response Time: {response_time:.2f}s")
        print()

    def calculate_day_totals(self, meal_plan_data, day_number=1):
        """Calculate total macros for a specific day"""
        try:
            # Find the specified day in the meal plan - use meal_days instead of days
            target_day = None
            for day in meal_plan_data.get("meal_days", []):
                # Check if day matches pattern "Day 1", "Day 2", etc.
                if day.get("day") == f"Day {day_number}":
                    target_day = day
                    break
            
            if not target_day:
                available_days = [day.get("day", "Unknown") for day in meal_plan_data.get("meal_days", [])]
                return None, f"Day {day_number} not found in meal plan. Available days: {available_days}. Response structure: {list(meal_plan_data.keys())}"
            
            # Sum up macros from all meals in the day
            total_calories = 0
            total_protein = 0
            total_carbs = 0
            total_fats = 0
            
            meal_details = []
            
            for meal in target_day.get("meals", []):
                meal_name = meal.get("name", "Unknown Meal")
                calories = meal.get("calories", 0)
                protein = meal.get("protein", 0)
                carbs = meal.get("carbs", 0)
                fats = meal.get("fats", 0)
                
                # Add to totals
                total_calories += calories
                total_protein += protein
                total_carbs += carbs
                total_fats += fats
                
                # Store meal details for reporting
                meal_details.append({
                    "name": meal_name,
                    "calories": calories,
                    "protein": protein,
                    "carbs": carbs,
                    "fats": fats
                })
            
            totals = {
                "calories": total_calories,
                "protein": total_protein,
                "carbs": total_carbs,
                "fats": total_fats
            }
            
            return totals, meal_details
            
        except Exception as e:
            return None, f"Error calculating day totals: {str(e)}"

    def check_macro_accuracy(self, actual_totals, targets):
        """Check if actual totals are within acceptable tolerance of targets"""
        accuracy_results = {}
        
        # Check calories
        cal_diff = abs(actual_totals["calories"] - targets["calories"])
        accuracy_results["calories"] = {
            "accurate": cal_diff <= CALORIE_TOLERANCE,
            "difference": actual_totals["calories"] - targets["calories"],
            "abs_difference": cal_diff
        }
        
        # Check protein
        protein_diff = abs(actual_totals["protein"] - targets["protein"])
        accuracy_results["protein"] = {
            "accurate": protein_diff <= MACRO_TOLERANCE,
            "difference": actual_totals["protein"] - targets["protein"],
            "abs_difference": protein_diff
        }
        
        # Check carbs
        carbs_diff = abs(actual_totals["carbs"] - targets["carbs"])
        accuracy_results["carbs"] = {
            "accurate": carbs_diff <= MACRO_TOLERANCE,
            "difference": actual_totals["carbs"] - targets["carbs"],
            "abs_difference": carbs_diff
        }
        
        # Check fats
        fats_diff = abs(actual_totals["fats"] - targets["fats"])
        accuracy_results["fats"] = {
            "accurate": fats_diff <= MACRO_TOLERANCE,
            "difference": actual_totals["fats"] - targets["fats"],
            "abs_difference": fats_diff
        }
        
        # Overall accuracy - all macros must be within tolerance
        overall_accurate = all([
            accuracy_results["calories"]["accurate"],
            accuracy_results["protein"]["accurate"],
            accuracy_results["carbs"]["accurate"],
            accuracy_results["fats"]["accurate"]
        ])
        
        return accuracy_results, overall_accurate

    async def test_meal_plan_generation(self):
        """Test meal plan generation with specific macro targets"""
        try:
            print("🔄 Generating meal plan (this may take 20-30 seconds)...")
            
            # Prepare request payload for MealPlanGenerateRequest
            payload = {
                "user_id": TEST_USER_ID,
                "food_preferences": "whole_foods",
                "supplements": [],
                "supplements_custom": None,
                "allergies": [],
                "cuisine_preference": "american"
            }
            
            start_time = time.time()
            response = await self.client.post(
                f"{BACKEND_URL}/mealplans/generate",
                json=payload
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                self.log_result(
                    "Meal Plan Generation",
                    True,
                    f"Successfully generated meal plan. Plan name: {data.get('name', 'Unknown')}. Days: {len(data.get('meal_days', []))}",
                    response_time
                )
                return True, data
            else:
                self.log_result(
                    "Meal Plan Generation",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                    response_time
                )
                return False, None
                
        except Exception as e:
            self.log_result(
                "Meal Plan Generation",
                False,
                f"Exception: {str(e)}"
            )
            return False, None

    async def test_macro_accuracy_validation(self, meal_plan_data):
        """Test macro accuracy validation for Day 1"""
        try:
            # Calculate Day 1 totals
            day_totals, meal_details = self.calculate_day_totals(meal_plan_data, day_number=1)
            
            if day_totals is None:
                self.log_result(
                    "Day 1 Macro Calculation",
                    False,
                    meal_details  # This contains the error message in this case
                )
                return False, None, None
            
            # Check accuracy against targets
            targets = {
                "calories": TARGET_CALORIES,
                "protein": TARGET_PROTEIN,
                "carbs": TARGET_CARBS,
                "fats": TARGET_FATS
            }
            
            accuracy_results, overall_accurate = self.check_macro_accuracy(day_totals, targets)
            
            # Generate detailed report
            report_lines = ["Day 1 Meal Plan Analysis:"]
            
            # Add individual meal details
            for i, meal in enumerate(meal_details, 1):
                report_lines.append(f"- Meal {i}: {meal['name']} - {meal['calories']}cal, {meal['protein']}g P, {meal['carbs']}g C, {meal['fats']}g F")
            
            # Add totals and targets
            report_lines.append(f"**DAY 1 TOTAL:** {day_totals['calories']}cal, {day_totals['protein']}g P, {day_totals['carbs']}g C, {day_totals['fats']}g F")
            report_lines.append(f"**TARGET:** {TARGET_CALORIES}cal, {TARGET_PROTEIN}g P, {TARGET_CARBS}g C, {TARGET_FATS}g F")
            
            # Add accuracy assessment
            if overall_accurate:
                report_lines.append(f"**ACCURACY:** ✅ ACCURATE (All macros within tolerance)")
            else:
                inaccurate_macros = []
                for macro, result in accuracy_results.items():
                    if not result["accurate"]:
                        diff = result["difference"]
                        sign = "+" if diff > 0 else ""
                        inaccurate_macros.append(f"{macro}: {sign}{diff}")
                
                report_lines.append(f"**ACCURACY:** ❌ INACCURATE ({', '.join(inaccurate_macros)})")
            
            detailed_report = "\n".join(report_lines)
            
            self.log_result(
                "Macro Accuracy Validation",
                overall_accurate,
                detailed_report
            )
            
            return True, day_totals, accuracy_results
            
        except Exception as e:
            self.log_result(
                "Macro Accuracy Validation",
                False,
                f"Exception during validation: {str(e)}"
            )
            return False, None, None

    async def run_meal_plan_macro_tests(self):
        """Run meal plan macro accuracy tests as specified in review request"""
        print("=" * 80)
        print("🧪 MEAL PLAN MACRO ACCURACY VALIDATION")
        print("=" * 80)
        print(f"Backend URL: {BACKEND_URL}")
        print(f"Test User ID: {TEST_USER_ID}")
        print(f"Target Macros: {TARGET_CALORIES}cal, {TARGET_PROTEIN}g protein, {TARGET_CARBS}g carbs, {TARGET_FATS}g fats")
        print(f"Tolerances: ±{CALORIE_TOLERANCE} cal, ±{MACRO_TOLERANCE}g macros")
        print(f"Test Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Test Case 1: Generate meal plan
        print("📋 TEST CASE 1: Generate meal plan with specific macro targets")
        success1, meal_plan_data = await self.test_meal_plan_generation()
        
        if not success1:
            print("⚠️ Cannot continue testing - meal plan generation failed")
            return False
        
        # Test Case 2: Validate macro accuracy for Day 1
        print("📋 TEST CASE 2: Validate Day 1 macro accuracy")
        success2, day_totals, accuracy_results = await self.test_macro_accuracy_validation(meal_plan_data)
        
        if not success2:
            print("⚠️ Macro accuracy validation failed")
            return False
        
        # Summary
        total_tests = 2
        passed_tests = sum([success1, success2])
        overall_success = passed_tests == total_tests and accuracy_results is not None
        
        print("=" * 80)
        print("📊 MEAL PLAN MACRO ACCURACY TESTING SUMMARY")
        print("=" * 80)
        print(f"✅ Tests Completed: {passed_tests}/{total_tests}")
        
        if accuracy_results:
            # Check overall macro accuracy
            overall_accurate = all([
                accuracy_results["calories"]["accurate"],
                accuracy_results["protein"]["accurate"],
                accuracy_results["carbs"]["accurate"],
                accuracy_results["fats"]["accurate"]
            ])
            
            if overall_accurate:
                print("🎯 RESULT: ✅ MEAL PLAN MACROS ARE ACCURATE")
                print("   All Day 1 macros are within acceptable tolerance of targets")
            else:
                print("🎯 RESULT: ❌ MEAL PLAN MACROS ARE INACCURATE")
                print("   One or more Day 1 macros exceed acceptable tolerance:")
                for macro, result in accuracy_results.items():
                    if not result["accurate"]:
                        diff = result["difference"]
                        sign = "+" if diff > 0 else ""
                        tolerance = CALORIE_TOLERANCE if macro == "calories" else MACRO_TOLERANCE
                        print(f"     - {macro.title()}: {sign}{diff} (tolerance: ±{tolerance})")
        
        print()
        
        # Print detailed results
        print("📋 DETAILED TEST RESULTS:")
        for result in self.results:
            print(f"[{result['timestamp']}] {result['status']}: {result['test']}")
            print(f"    📝 {result['details']}")
            if result['response_time'] != "N/A":
                print(f"    ⏱️ {result['response_time']}")
            print()
        
        print("=" * 80)
        
        return overall_success

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

async def main():
    """Main test execution function"""
    tester = MealPlanMacroTester()
    
    try:
        success = await tester.run_meal_plan_macro_tests()
        if success:
            print("🎉 MEAL PLAN MACRO ACCURACY TEST COMPLETED!")
        else:
            print("⚠️ MEAL PLAN MACRO ACCURACY TEST HAD ISSUES - Review results above")
        
    except Exception as e:
        print(f"💥 TESTING ERROR: {e}")
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main())