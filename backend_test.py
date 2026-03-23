#!/usr/bin/env python3
"""
Backend Test Suite for InterFitAI - Meal Replacement with Foods to Avoid Testing
Focus: Testing the MEAL REPLACEMENT endpoint (POST /api/mealplan/alternate) with foods_to_avoid filtering
"""

import requests
import json
import time
import sys
from typing import Dict, Any, List

# Backend URL from frontend/.env
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# Test user ID as specified in review request
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

class MealReplacementTester:
    def __init__(self):
        self.backend_url = BACKEND_URL
        self.test_user_id = TEST_USER_ID
        self.meal_plan_id = None
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str, response_time: float = 0):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "response_time": f"{response_time:.2f}s" if response_time > 0 else "N/A"
        }
        self.test_results.append(result)
        print(f"{status}: {test_name}")
        print(f"   Details: {details}")
        if response_time > 0:
            print(f"   Response Time: {response_time:.2f}s")
        print()

    def test_health_check(self):
        """Test basic health check"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.backend_url}/health", timeout=10)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Health Check", True, f"Backend responding. Status: {data.get('status')}", response_time)
                return True
            else:
                self.log_test("Health Check", False, f"HTTP {response.status_code}: {response.text}", response_time)
                return False
        except Exception as e:
            self.log_test("Health Check", False, f"Connection error: {str(e)}")
            return False

    def create_meal_plan_with_foods_to_avoid(self):
        """Step 1: Create a meal plan with foods_to_avoid set to 'chicken'"""
        try:
            start_time = time.time()
            
            payload = {
                "user_id": self.test_user_id,
                "food_preferences": "balanced",
                "foods_to_avoid": "chicken",
                "preferred_foods": "beef, rice, eggs"
            }
            
            response = requests.post(f"{self.backend_url}/mealplans/generate", json=payload, timeout=60)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                self.meal_plan_id = data.get("id")
                
                # Verify the meal plan was created with correct foods_to_avoid
                foods_to_avoid = data.get("foods_to_avoid", "")
                
                # Check if any meals contain chicken (they shouldn't)
                chicken_found = False
                chicken_meals = []
                
                for day_idx, day in enumerate(data.get("meal_days", [])):
                    for meal_idx, meal in enumerate(day.get("meals", [])):
                        meal_name = meal.get("name", "").lower()
                        ingredients = " ".join(meal.get("ingredients", [])).lower()
                        
                        if "chicken" in meal_name or "chicken" in ingredients:
                            chicken_found = True
                            chicken_meals.append(f"Day {day_idx+1}, Meal {meal_idx+1}: {meal.get('name')}")
                
                if chicken_found:
                    self.log_test("Create Meal Plan with Foods to Avoid", False, 
                                f"Meal plan created but contains chicken in: {chicken_meals}. foods_to_avoid: '{foods_to_avoid}'", response_time)
                else:
                    self.log_test("Create Meal Plan with Foods to Avoid", True, 
                                f"Meal plan created successfully without chicken. Plan ID: {self.meal_plan_id}, foods_to_avoid: '{foods_to_avoid}'", response_time)
                
                return True
            else:
                self.log_test("Create Meal Plan with Foods to Avoid", False, 
                            f"HTTP {response.status_code}: {response.text}", response_time)
                return False
                
        except Exception as e:
            self.log_test("Create Meal Plan with Foods to Avoid", False, f"Error: {str(e)}")
            return False

    def test_alternate_meal_with_foods_to_avoid(self):
        """Step 2: Test the alternate meal endpoint with foods_to_avoid filtering"""
        if not self.meal_plan_id:
            self.log_test("Test Alternate Meal with Foods to Avoid", False, "No meal plan ID available")
            return False
            
        try:
            start_time = time.time()
            
            payload = {
                "user_id": self.test_user_id,
                "meal_plan_id": self.meal_plan_id,
                "day_index": 0,
                "meal_index": 1,  # lunch
                "swap_preference": "similar"
            }
            
            response = requests.post(f"{self.backend_url}/mealplan/alternate", json=payload, timeout=60)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                alternate_meal = data.get("alternate_meal", {})
                
                # Check if the alternate meal contains any banned foods
                meal_name = alternate_meal.get("name", "").lower()
                ingredients = " ".join(alternate_meal.get("ingredients", [])).lower()
                instructions = alternate_meal.get("instructions", "").lower()
                
                all_text = f"{meal_name} {ingredients} {instructions}"
                
                # Check for chicken and related poultry
                banned_foods_found = []
                poultry_terms = ["chicken", "turkey", "poultry"]
                
                for term in poultry_terms:
                    if term in all_text:
                        banned_foods_found.append(term)
                
                if banned_foods_found:
                    self.log_test("Test Alternate Meal with Foods to Avoid", False, 
                                f"Alternate meal contains banned foods: {banned_foods_found}. Meal: {alternate_meal.get('name')}, Ingredients: {alternate_meal.get('ingredients')}", response_time)
                    return False
                else:
                    # Success - no banned foods found
                    macros = f"{alternate_meal.get('calories')}cal, {alternate_meal.get('protein')}g P, {alternate_meal.get('carbs')}g C, {alternate_meal.get('fats')}g F"
                    self.log_test("Test Alternate Meal with Foods to Avoid", True, 
                                f"Alternate meal generated without banned foods. Meal: '{alternate_meal.get('name')}', Macros: {macros}", response_time)
                    return True
                    
            else:
                self.log_test("Test Alternate Meal with Foods to Avoid", False, 
                            f"HTTP {response.status_code}: {response.text}", response_time)
                return False
                
        except Exception as e:
            self.log_test("Test Alternate Meal with Foods to Avoid", False, f"Error: {str(e)}")
            return False

    def test_multiple_alternate_meals(self):
        """Step 3: Test multiple alternate meal generations to ensure consistency"""
        if not self.meal_plan_id:
            self.log_test("Test Multiple Alternate Meals", False, "No meal plan ID available")
            return False
            
        success_count = 0
        total_tests = 3
        
        for i in range(total_tests):
            try:
                start_time = time.time()
                
                payload = {
                    "user_id": self.test_user_id,
                    "meal_plan_id": self.meal_plan_id,
                    "day_index": 0,
                    "meal_index": 2,  # dinner
                    "swap_preference": "similar"
                }
                
                response = requests.post(f"{self.backend_url}/mealplan/alternate", json=payload, timeout=60)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    alternate_meal = data.get("alternate_meal", {})
                    
                    # Check for banned foods
                    meal_name = alternate_meal.get("name", "").lower()
                    ingredients = " ".join(alternate_meal.get("ingredients", [])).lower()
                    instructions = alternate_meal.get("instructions", "").lower()
                    
                    all_text = f"{meal_name} {ingredients} {instructions}"
                    
                    banned_foods_found = []
                    poultry_terms = ["chicken", "turkey", "poultry"]
                    
                    for term in poultry_terms:
                        if term in all_text:
                            banned_foods_found.append(term)
                    
                    if not banned_foods_found:
                        success_count += 1
                        print(f"   Test {i+1}/3: ✅ '{alternate_meal.get('name')}' - No banned foods ({response_time:.2f}s)")
                    else:
                        print(f"   Test {i+1}/3: ❌ '{alternate_meal.get('name')}' - Contains: {banned_foods_found} ({response_time:.2f}s)")
                else:
                    print(f"   Test {i+1}/3: ❌ HTTP {response.status_code}")
                    
            except Exception as e:
                print(f"   Test {i+1}/3: ❌ Error: {str(e)}")
        
        success_rate = (success_count / total_tests) * 100
        if success_count == total_tests:
            self.log_test("Test Multiple Alternate Meals", True, 
                        f"All {total_tests} alternate meals generated without banned foods ({success_rate:.0f}% success rate)")
            return True
        else:
            self.log_test("Test Multiple Alternate Meals", False, 
                        f"Only {success_count}/{total_tests} alternate meals were clean ({success_rate:.0f}% success rate)")
            return False

    def test_protein_groups_filtering(self):
        """Step 4: Test that banning 'chicken' also bans 'turkey' (PROTEIN_GROUPS logic)"""
        if not self.meal_plan_id:
            self.log_test("Test PROTEIN_GROUPS Filtering", False, "No meal plan ID available")
            return False
            
        try:
            # Test with different meal positions to get variety
            test_positions = [
                {"day_index": 0, "meal_index": 0, "meal_type": "breakfast"},
                {"day_index": 0, "meal_index": 3, "meal_type": "snack"},
                {"day_index": 1, "meal_index": 1, "meal_type": "lunch"} if self.meal_plan_id else {"day_index": 0, "meal_index": 1, "meal_type": "lunch"}
            ]
            
            all_clean = True
            test_results = []
            
            for pos in test_positions[:2]:  # Test 2 positions
                try:
                    start_time = time.time()
                    
                    payload = {
                        "user_id": self.test_user_id,
                        "meal_plan_id": self.meal_plan_id,
                        "day_index": pos["day_index"],
                        "meal_index": pos["meal_index"],
                        "swap_preference": "similar"
                    }
                    
                    response = requests.post(f"{self.backend_url}/mealplan/alternate", json=payload, timeout=60)
                    response_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        data = response.json()
                        alternate_meal = data.get("alternate_meal", {})
                        
                        # Check for ALL poultry-related terms (PROTEIN_GROUPS logic)
                        meal_name = alternate_meal.get("name", "").lower()
                        ingredients = " ".join(alternate_meal.get("ingredients", [])).lower()
                        instructions = alternate_meal.get("instructions", "").lower()
                        
                        all_text = f"{meal_name} {ingredients} {instructions}"
                        
                        # Extended poultry check based on PROTEIN_GROUPS in server.py
                        poultry_terms = [
                            "chicken", "turkey", "poultry", "chicken breast", "chicken thigh", 
                            "grilled chicken", "rotisserie chicken", "chicken wings", 
                            "turkey breast", "ground turkey", "turkey bacon"
                        ]
                        
                        banned_found = []
                        for term in poultry_terms:
                            if term in all_text:
                                banned_found.append(term)
                        
                        if banned_found:
                            all_clean = False
                            test_results.append(f"{pos['meal_type']}: ❌ Contains {banned_found}")
                        else:
                            test_results.append(f"{pos['meal_type']}: ✅ Clean - '{alternate_meal.get('name')}'")
                            
                    else:
                        all_clean = False
                        test_results.append(f"{pos['meal_type']}: ❌ HTTP {response.status_code}")
                        
                except Exception as e:
                    all_clean = False
                    test_results.append(f"{pos['meal_type']}: ❌ Error: {str(e)}")
            
            if all_clean:
                self.log_test("Test PROTEIN_GROUPS Filtering", True, 
                            f"PROTEIN_GROUPS filtering working correctly. Results: {'; '.join(test_results)}")
                return True
            else:
                self.log_test("Test PROTEIN_GROUPS Filtering", False, 
                            f"PROTEIN_GROUPS filtering failed. Results: {'; '.join(test_results)}")
                return False
                
        except Exception as e:
            self.log_test("Test PROTEIN_GROUPS Filtering", False, f"Error: {str(e)}")
            return False

    def run_all_tests(self):
        """Run all meal replacement tests"""
        print("=" * 80)
        print("MEAL REPLACEMENT WITH FOODS TO AVOID - BACKEND TESTING")
        print("=" * 80)
        print(f"Backend URL: {self.backend_url}")
        print(f"Test User ID: {self.test_user_id}")
        print()
        
        # Test sequence as specified in review request
        tests = [
            ("Health Check", self.test_health_check),
            ("Create Meal Plan with Foods to Avoid", self.create_meal_plan_with_foods_to_avoid),
            ("Test Alternate Meal with Foods to Avoid", self.test_alternate_meal_with_foods_to_avoid),
            ("Test Multiple Alternate Meals", self.test_multiple_alternate_meals),
            ("Test PROTEIN_GROUPS Filtering", self.test_protein_groups_filtering)
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            if test_func():
                passed += 1
        
        print("=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        for result in self.test_results:
            print(f"{result['status']}: {result['test']}")
            print(f"   {result['details']}")
            if result['response_time'] != "N/A":
                print(f"   Response Time: {result['response_time']}")
            print()
        
        success_rate = (passed / total) * 100
        print(f"OVERALL RESULT: {passed}/{total} tests passed ({success_rate:.0f}% success rate)")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED - Meal replacement with foods_to_avoid filtering is working correctly!")
        else:
            print("❌ SOME TESTS FAILED - Meal replacement needs attention")
        
        return passed == total

if __name__ == "__main__":
    tester = MealReplacementTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)