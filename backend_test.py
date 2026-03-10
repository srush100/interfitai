#!/usr/bin/env python3
"""
Comprehensive Backend Testing for InterFitAI - Meal Plan Macro Accuracy
Testing Agent for backend API endpoints validation
"""

import requests
import json
import time
from typing import Dict, List, Any
import sys
import os

# Backend URL configuration
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# Test user ID from review request
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

class MealPlanMacroAccuracyTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_user_id = TEST_USER_ID
        self.results = []
        
    def log_result(self, test_name: str, passed: bool, details: str, response_time: float = 0):
        """Log test result"""
        result = {
            "test": test_name,
            "passed": passed,
            "details": details,
            "response_time": f"{response_time:.2f}s"
        }
        self.results.append(result)
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name}: {details} ({response_time:.2f}s)")
        
    def calculate_macro_deviation(self, actual: Dict[str, float], target: Dict[str, float]) -> Dict[str, float]:
        """Calculate percentage deviation from target macros"""
        deviations = {}
        for macro in ['calories', 'protein', 'carbs', 'fats']:
            if target.get(macro, 0) > 0:
                deviation = abs(actual[macro] - target[macro]) / target[macro] * 100
                deviations[macro] = deviation
            else:
                deviations[macro] = 0
        return deviations
    
    def validate_macro_accuracy(self, daily_totals: Dict[str, float], target_macros: Dict[str, float], 
                              criteria: Dict[str, float]) -> tuple[bool, str]:
        """Validate macro accuracy against acceptance criteria"""
        deviations = self.calculate_macro_deviation(daily_totals, target_macros)
        
        validation_results = []
        passed = True
        
        for macro, tolerance in criteria.items():
            deviation = deviations.get(macro, 0)
            macro_passed = deviation <= tolerance
            passed = passed and macro_passed
            
            actual = daily_totals.get(macro, 0)
            target = target_macros.get(macro, 0)
            diff = actual - target
            
            validation_results.append(
                f"{macro.title()}: {actual:.1f} vs {target:.1f} "
                f"({diff:+.1f}, {deviation:.1f}% dev, ≤{tolerance}% req) "
                f"{'✅' if macro_passed else '❌'}"
            )
        
        details = " | ".join(validation_results)
        return passed, details
    
    def extract_daily_totals(self, meal_plan: Dict[str, Any], day_index: int = 0) -> Dict[str, float]:
        """Extract daily macro totals from meal plan response"""
        try:
            meal_days = meal_plan.get('meal_days', [])
            if day_index >= len(meal_days):
                return {'calories': 0, 'protein': 0, 'carbs': 0, 'fats': 0}
            
            day = meal_days[day_index]
            return {
                'calories': day.get('total_calories', 0),
                'protein': day.get('total_protein', 0),
                'carbs': day.get('total_carbs', 0),
                'fats': day.get('total_fats', 0)
            }
        except Exception as e:
            print(f"Error extracting daily totals: {e}")
            return {'calories': 0, 'protein': 0, 'carbs': 0, 'fats': 0}
    
    def get_user_profile(self) -> Dict[str, Any]:
        """Get user profile to extract target macros"""
        start_time = time.time()
        try:
            response = requests.get(f"{self.backend_url}/profile/{self.test_user_id}", timeout=30)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                profile = response.json()
                macros = profile.get('calculated_macros', {})
                self.log_result("Get User Profile", True, 
                              f"Retrieved profile with macros: {macros.get('calories')}cal, "
                              f"{macros.get('protein')}g P, {macros.get('carbs')}g C, {macros.get('fats')}g F", 
                              response_time)
                return profile
            else:
                self.log_result("Get User Profile", False, 
                              f"Failed to get profile: {response.status_code} - {response.text}", 
                              response_time)
                return {}
        except Exception as e:
            response_time = time.time() - start_time
            self.log_result("Get User Profile", False, f"Exception: {str(e)}", response_time)
            return {}
    
    def test_balanced_meal_plan_with_preferred_foods(self, target_macros: Dict[str, float]):
        """TEST 1: Balanced meal plan with preferred foods"""
        print("\n" + "="*80)
        print("TEST 1: Balanced meal plan with preferred foods")
        print("="*80)
        
        payload = {
            "user_id": self.test_user_id,
            "food_preferences": "balanced",
            "preferred_foods": "chicken breast, rice, broccoli",
            "allergies": []
        }
        
        start_time = time.time()
        try:
            response = requests.post(f"{self.backend_url}/mealplans/generate", 
                                   json=payload, timeout=60)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                meal_plan = response.json()
                daily_totals = self.extract_daily_totals(meal_plan, 0)  # Day 1
                
                # Acceptance criteria for balanced meal plan
                criteria = {
                    'calories': 10,  # ±10%
                    'protein': 15,   # ±15%
                    'carbs': 15,     # ±15%
                    'fats': 20       # ±20%
                }
                
                passed, details = self.validate_macro_accuracy(daily_totals, target_macros, criteria)
                
                # Check for preferred foods presence
                plan_text = json.dumps(meal_plan).lower()
                preferred_found = []
                for food in ["chicken", "rice", "broccoli"]:
                    if food in plan_text:
                        preferred_found.append(food)
                
                preferred_details = f" | Preferred foods found: {', '.join(preferred_found) if preferred_found else 'none'}"
                
                self.log_result("TEST 1: Balanced + Preferred Foods", passed,
                              f"{details}{preferred_details}", response_time)
                
                return meal_plan, passed
                
            else:
                self.log_result("TEST 1: Balanced + Preferred Foods", False,
                              f"API Error: {response.status_code} - {response.text}", response_time)
                return {}, False
                
        except Exception as e:
            response_time = time.time() - start_time
            self.log_result("TEST 1: Balanced + Preferred Foods", False,
                          f"Exception: {str(e)}", response_time)
            return {}, False
    
    def test_template_based_meal_plan(self, target_macros: Dict[str, float]):
        """TEST 2: Template-based meal plan (no preferred foods)"""
        print("\n" + "="*80)
        print("TEST 2: Template-based meal plan (no preferred foods)")
        print("="*80)
        
        payload = {
            "user_id": self.test_user_id,
            "food_preferences": "high_protein",
            "allergies": []
        }
        
        start_time = time.time()
        try:
            response = requests.post(f"{self.backend_url}/mealplans/generate", 
                                   json=payload, timeout=60)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                meal_plan = response.json()
                daily_totals = self.extract_daily_totals(meal_plan, 0)  # Day 1
                
                # Template-based should be more accurate - stricter criteria
                criteria = {
                    'calories': 5,   # ±5% (should be more accurate)
                    'protein': 10,   # ±10%
                    'carbs': 10,     # ±10%
                    'fats': 15       # ±15%
                }
                
                passed, details = self.validate_macro_accuracy(daily_totals, target_macros, criteria)
                
                template_info = f" | Template-based generation (higher accuracy expected)"
                
                self.log_result("TEST 2: Template-based High Protein", passed,
                              f"{details}{template_info}", response_time)
                
                return meal_plan, passed
                
            else:
                self.log_result("TEST 2: Template-based High Protein", False,
                              f"API Error: {response.status_code} - {response.text}", response_time)
                return {}, False
                
        except Exception as e:
            response_time = time.time() - start_time
            self.log_result("TEST 2: Template-based High Protein", False,
                          f"Exception: {str(e)}", response_time)
            return {}, False
    
    def test_keto_meal_plan(self, target_macros: Dict[str, float]):
        """TEST 3: Keto meal plan"""
        print("\n" + "="*80)
        print("TEST 3: Keto meal plan")
        print("="*80)
        
        payload = {
            "user_id": self.test_user_id,
            "food_preferences": "keto",
            "allergies": []
        }
        
        start_time = time.time()
        try:
            response = requests.post(f"{self.backend_url}/mealplans/generate", 
                                   json=payload, timeout=60)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                meal_plan = response.json()
                daily_totals = self.extract_daily_totals(meal_plan, 0)  # Day 1
                
                # Keto compliance check: carbs should be under 50g
                carbs = daily_totals.get('carbs', 0)
                keto_compliant = carbs < 50
                
                # Standard macro accuracy criteria
                criteria = {
                    'calories': 10,  # ±10%
                    'protein': 15,   # ±15%
                    'carbs': 20,     # ±20% (but absolute limit more important)
                    'fats': 20       # ±20%
                }
                
                macro_passed, macro_details = self.validate_macro_accuracy(daily_totals, target_macros, criteria)
                
                # Overall pass requires both macro accuracy AND keto compliance
                passed = macro_passed and keto_compliant
                
                keto_details = f" | Keto compliance: {carbs:.1f}g carbs {'✅ <50g' if keto_compliant else '❌ ≥50g'}"
                
                self.log_result("TEST 3: Keto Meal Plan", passed,
                              f"{macro_details}{keto_details}", response_time)
                
                return meal_plan, passed
                
            else:
                self.log_result("TEST 3: Keto Meal Plan", False,
                              f"API Error: {response.status_code} - {response.text}", response_time)
                return {}, False
                
        except Exception as e:
            response_time = time.time() - start_time
            self.log_result("TEST 3: Keto Meal Plan", False,
                          f"Exception: {str(e)}", response_time)
            return {}, False
    
    def run_comprehensive_tests(self):
        """Run all comprehensive macro accuracy tests"""
        print("🧪 COMPREHENSIVE MEAL PLAN MACRO ACCURACY TESTING")
        print("=" * 80)
        print(f"Backend URL: {self.backend_url}")
        print(f"Test User ID: {self.test_user_id}")
        
        # Get user profile for target macros
        profile = self.get_user_profile()
        if not profile:
            print("❌ CRITICAL: Cannot proceed without user profile")
            return False
        
        calculated_macros = profile.get('calculated_macros', {})
        if not calculated_macros:
            print("❌ CRITICAL: No calculated macros in profile")
            return False
        
        target_macros = {
            'calories': calculated_macros.get('calories', 0),
            'protein': calculated_macros.get('protein', 0),
            'carbs': calculated_macros.get('carbs', 0),
            'fats': calculated_macros.get('fats', 0)
        }
        
        print(f"\n📊 TARGET MACROS from profile:")
        print(f"   Calories: {target_macros['calories']}")
        print(f"   Protein: {target_macros['protein']}g")
        print(f"   Carbs: {target_macros['carbs']}g")
        print(f"   Fats: {target_macros['fats']}g")
        
        # Run all tests
        test1_plan, test1_passed = self.test_balanced_meal_plan_with_preferred_foods(target_macros)
        test2_plan, test2_passed = self.test_template_based_meal_plan(target_macros)
        test3_plan, test3_passed = self.test_keto_meal_plan(target_macros)
        
        # Overall results
        all_passed = test1_passed and test2_passed and test3_passed
        passed_count = sum([test1_passed, test2_passed, test3_passed])
        
        print("\n" + "="*80)
        print("🏁 COMPREHENSIVE TEST RESULTS SUMMARY")
        print("="*80)
        
        print(f"✅ TEST 1 - Balanced + Preferred Foods: {'PASS' if test1_passed else 'FAIL'}")
        print(f"✅ TEST 2 - Template-based High Protein: {'PASS' if test2_passed else 'FAIL'}")
        print(f"✅ TEST 3 - Keto Meal Plan: {'PASS' if test3_passed else 'FAIL'}")
        
        print(f"\n📈 OVERALL RESULT: {passed_count}/3 tests passed")
        
        if all_passed:
            print("🎉 ALL TESTS PASSED - Meal plan macro accuracy is WORKING PERFECTLY!")
        else:
            print("⚠️  SOME TESTS FAILED - Meal plan macro accuracy needs attention")
        
        return all_passed

def main():
    """Main test execution"""
    tester = MealPlanMacroAccuracyTester()
    success = tester.run_comprehensive_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()