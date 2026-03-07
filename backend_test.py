#!/usr/bin/env python3
"""
Backend API Testing Script for InterFitAI - Save Favorite Meals Feature
Tests the favorite meals endpoints as requested in the review.
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from frontend environment
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# Test user ID as specified in the review request
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

# Test meal data as specified in the review request
TEST_MEAL_DATA = {
    "user_id": TEST_USER_ID,
    "meal_name": "Test Grilled Chicken Salad",
    "calories": 450,
    "protein": 45,
    "carbs": 20,
    "fats": 18
}

def log_test_result(test_name, success, response_time=None, details=""):
    """Log test result with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ PASSED" if success else "❌ FAILED"
    time_info = f" ({response_time:.2f}s)" if response_time else ""
    print(f"[{timestamp}] {status}{time_info} - {test_name}")
    if details:
        print(f"    Details: {details}")
    print()

def test_health_check():
    """Test GET /api/health endpoint"""
    print("=" * 60)
    print("Testing Health Check Endpoint")
    print("=" * 60)
    
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test_result("Health Check", True, response_time, 
                          f"Status: {response.status_code}, Response: {data}")
            return True
        else:
            log_test_result("Health Check", False, response_time,
                          f"Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        log_test_result("Health Check", False, details=f"Exception: {str(e)}")
        return False

def test_add_favorite_meal():
    """Test POST /api/food/favorite endpoint"""
    print("=" * 60)
    print("Testing Add Favorite Meal Endpoint")
    print("=" * 60)
    
    try:
        start_time = time.time()
        response = requests.post(f"{BACKEND_URL}/food/favorite", params=TEST_MEAL_DATA, timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            favorite_id = data.get('id')
            log_test_result("Add Favorite Meal", True, response_time,
                          f"Status: {response.status_code}, Favorite ID: {favorite_id}")
            return favorite_id
        else:
            log_test_result("Add Favorite Meal", False, response_time,
                          f"Status: {response.status_code}, Response: {response.text}")
            return None
            
    except Exception as e:
        log_test_result("Add Favorite Meal", False, details=f"Exception: {str(e)}")
        return None

def test_get_favorite_meals():
    """Test GET /api/food/favorites/{user_id} endpoint"""
    print("=" * 60)
    print("Testing Get Favorite Meals Endpoint")
    print("=" * 60)
    
    try:
        start_time = time.time()
        response = requests.get(f"{BACKEND_URL}/food/favorites/{TEST_USER_ID}", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            favorites = response.json()
            log_test_result("Get Favorite Meals", True, response_time,
                          f"Status: {response.status_code}, Found {len(favorites)} favorite meals")
            
            # Verify nested meal object structure as requested
            if favorites:
                first_favorite = favorites[0]
                required_fields = ['id', 'user_id', 'meal', 'created_at']
                meal_fields = ['name', 'calories', 'protein', 'carbs', 'fats']
                
                structure_valid = True
                missing_fields = []
                
                # Check top-level fields
                for field in required_fields:
                    if field not in first_favorite:
                        structure_valid = False
                        missing_fields.append(field)
                
                # Check nested meal object
                if 'meal' in first_favorite:
                    meal_obj = first_favorite['meal']
                    for field in meal_fields:
                        if field not in meal_obj:
                            structure_valid = False
                            missing_fields.append(f"meal.{field}")
                
                if structure_valid:
                    log_test_result("Favorite Meals Structure Validation", True, 
                                  details=f"Correct nested structure with meal object: {json.dumps(first_favorite, indent=2)}")
                else:
                    log_test_result("Favorite Meals Structure Validation", False,
                                  details=f"Missing fields: {missing_fields}")
            
            return favorites
        else:
            log_test_result("Get Favorite Meals", False, response_time,
                          f"Status: {response.status_code}, Response: {response.text}")
            return None
            
    except Exception as e:
        log_test_result("Get Favorite Meals", False, details=f"Exception: {str(e)}")
        return None

def test_remove_favorite_meal(favorite_id):
    """Test DELETE /api/food/favorite/{favorite_id} endpoint"""
    print("=" * 60)
    print("Testing Remove Favorite Meal Endpoint")
    print("=" * 60)
    
    if not favorite_id:
        log_test_result("Remove Favorite Meal", False, details="No favorite ID provided")
        return False
    
    try:
        start_time = time.time()
        response = requests.delete(f"{BACKEND_URL}/food/favorite/{favorite_id}", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test_result("Remove Favorite Meal", True, response_time,
                          f"Status: {response.status_code}, Response: {data}")
            return True
        else:
            log_test_result("Remove Favorite Meal", False, response_time,
                          f"Status: {response.status_code}, Response: {response.text}")
            return False
            
    except Exception as e:
        log_test_result("Remove Favorite Meal", False, details=f"Exception: {str(e)}")
        return False

def main():
    """Run all favorite meals endpoint tests"""
    print("🚀 Starting Save Favorite Meals Feature Backend Testing")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print(f"Test Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n")
    
    results = {
        'health_check': False,
        'add_favorite': False,
        'get_favorites': False,
        'remove_favorite': False,
        'structure_validation': False
    }
    
    # 1. Test Health Check
    results['health_check'] = test_health_check()
    
    # 2. Test Add Favorite Meal
    favorite_id = test_add_favorite_meal()
    results['add_favorite'] = favorite_id is not None
    
    # 3. Test Get Favorite Meals (and verify structure)
    favorites = test_get_favorite_meals()
    results['get_favorites'] = favorites is not None
    
    # Check if we found our test meal in the results
    if favorites and favorite_id:
        found_test_meal = any(fav.get('id') == favorite_id for fav in favorites)
        if found_test_meal:
            log_test_result("Test Meal Found in Favorites", True,
                          details="Successfully retrieved the meal we just added")
            results['structure_validation'] = True
        else:
            log_test_result("Test Meal Found in Favorites", False,
                          details="Could not find the test meal we just added")
    
    # 4. Test Remove Favorite Meal
    results['remove_favorite'] = test_remove_favorite_meal(favorite_id)
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed_tests = sum(results.values())
    total_tests = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name.replace('_', ' ').title()}")
    
    print(f"\nOverall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All Save Favorite Meals endpoints working perfectly!")
        return True
    else:
        print("⚠️  Some Save Favorite Meals endpoints need attention")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)