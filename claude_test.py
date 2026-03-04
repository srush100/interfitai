#!/usr/bin/env python3
"""
Backend Testing for InterFitAI - Claude Sonnet 4.6 Migration Testing
Testing all AI-powered endpoints that were migrated from OpenAI GPT-4o to Claude Sonnet 4.6
"""

import requests
import json
import sys
from datetime import datetime

# Backend URL from frontend/.env
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# Test user ID from review request
TEST_USER_ID = "d704bac8-fa54-4d5b-b984-cc17393c1244"

def log_test_result(test_name, success, details=""):
    """Log test results with timestamp"""
    status = "✅ PASS" if success else "❌ FAIL"
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {status} - {test_name}")
    if details:
        print(f"         └─ {details}")
    return success

def test_health_check():
    """Test basic health check endpoint"""
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "healthy":
                return log_test_result("Health Check", True, "Backend is healthy")
            else:
                return log_test_result("Health Check", False, f"Unexpected response: {data}")
        else:
            return log_test_result("Health Check", False, f"HTTP {response.status_code}")
    except Exception as e:
        return log_test_result("Health Check", False, f"Exception: {str(e)}")

def test_ai_workout_generation():
    """Test AI Workout Generation with Claude Sonnet 4.6"""
    try:
        payload = {
            "user_id": TEST_USER_ID,
            "goal": "muscle_building",
            "focus_areas": ["chest", "back"],
            "equipment": ["barbell", "dumbbell"],
            "injuries": None,
            "days_per_week": 3,
            "duration_minutes": 45
        }
        
        response = requests.post(f"{BACKEND_URL}/workouts/generate", json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            
            # Validate response structure
            if data.get("name") and data.get("workout_days"):
                workout_days = data.get("workout_days", [])
                if len(workout_days) >= 3:  # Should have 3 days
                    total_exercises = sum(len(day.get("exercises", [])) for day in workout_days)
                    return log_test_result("AI Workout Generation (Claude Sonnet 4.6)", True, 
                                         f"Generated '{data['name']}' with {len(workout_days)} days and {total_exercises} total exercises")
                else:
                    return log_test_result("AI Workout Generation (Claude Sonnet 4.6)", False, 
                                         f"Expected 3 workout days, got {len(workout_days)}")
            else:
                return log_test_result("AI Workout Generation (Claude Sonnet 4.6)", False, 
                                     f"Missing required fields in response: {list(data.keys())}")
        else:
            error_details = response.text if response.text else f"HTTP {response.status_code}"
            return log_test_result("AI Workout Generation (Claude Sonnet 4.6)", False, error_details)
            
    except Exception as e:
        return log_test_result("AI Workout Generation (Claude Sonnet 4.6)", False, f"Exception: {str(e)}")

def test_ai_meal_plan_generation():
    """Test AI Meal Plan Generation with Claude Sonnet 4.6"""
    try:
        payload = {
            "user_id": TEST_USER_ID,
            "food_preferences": "high_protein",
            "supplements": ["protein_powder"],
            "supplements_custom": "",
            "allergies": [],
            "cuisine_preference": ""
        }
        
        response = requests.post(f"{BACKEND_URL}/mealplans/generate", json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            
            # Validate response structure
            if data.get("name") and data.get("meal_days"):
                meal_days = data.get("meal_days", [])
                if len(meal_days) == 7:  # Should have 7 days
                    total_meals = sum(len(day.get("meals", [])) for day in meal_days)
                    return log_test_result("AI Meal Plan Generation (Claude Sonnet 4.6)", True,
                                         f"Generated '{data['name']}' with {len(meal_days)} days and {total_meals} total meals")
                else:
                    return log_test_result("AI Meal Plan Generation (Claude Sonnet 4.6)", False,
                                         f"Expected 7 meal days, got {len(meal_days)}")
            else:
                return log_test_result("AI Meal Plan Generation (Claude Sonnet 4.6)", False,
                                     f"Missing required fields in response: {list(data.keys())}")
        else:
            error_details = response.text if response.text else f"HTTP {response.status_code}"
            return log_test_result("AI Meal Plan Generation (Claude Sonnet 4.6)", False, error_details)
            
    except Exception as e:
        return log_test_result("AI Meal Plan Generation (Claude Sonnet 4.6)", False, f"Exception: {str(e)}")

def test_ask_interfitai_chat():
    """Test Ask InterFitAI Chat with Claude Sonnet 4.6"""
    try:
        payload = {
            "user_id": TEST_USER_ID,
            "message": "What's the best way to build muscle?"
        }
        
        response = requests.post(f"{BACKEND_URL}/chat", json=payload, timeout=40)
        
        if response.status_code == 200:
            data = response.json()
            
            # Validate response structure
            if data.get("content") and data.get("role") == "assistant":
                content = data.get("content", "")
                if len(content) > 50:  # Should have meaningful content
                    return log_test_result("Ask InterFitAI Chat (Claude Sonnet 4.6)", True,
                                         f"AI responded with {len(content)} characters of fitness advice")
                else:
                    return log_test_result("Ask InterFitAI Chat (Claude Sonnet 4.6)", False,
                                         f"Response too short: '{content}'")
            else:
                return log_test_result("Ask InterFitAI Chat (Claude Sonnet 4.6)", False,
                                     f"Invalid response structure: {list(data.keys())}")
        else:
            error_details = response.text if response.text else f"HTTP {response.status_code}"
            return log_test_result("Ask InterFitAI Chat (Claude Sonnet 4.6)", False, error_details)
            
    except Exception as e:
        return log_test_result("Ask InterFitAI Chat (Claude Sonnet 4.6)", False, f"Exception: {str(e)}")

def get_meal_plans_for_alternate_test():
    """Get meal plans to test alternate meal generation"""
    try:
        response = requests.get(f"{BACKEND_URL}/mealplans/{TEST_USER_ID}", timeout=10)
        if response.status_code == 200:
            plans = response.json()
            if plans and len(plans) > 0:
                return plans[0]  # Return first meal plan
        return None
    except:
        return None

def test_alternate_meal_generation():
    """Test Alternate Meal Generation with Claude Sonnet 4.6"""
    try:
        # First get existing meal plans
        meal_plan = get_meal_plans_for_alternate_test()
        
        if not meal_plan:
            return log_test_result("Alternate Meal Generation (Claude Sonnet 4.6)", False,
                                 "No existing meal plan found for testing. Need to generate meal plan first.")
        
        payload = {
            "user_id": TEST_USER_ID,
            "meal_plan_id": meal_plan.get("id"),
            "day_index": 0,  # First day
            "meal_index": 0,  # First meal
            "preferences": "Something different and tasty"
        }
        
        response = requests.post(f"{BACKEND_URL}/mealplan/alternate", json=payload, timeout=40)
        
        if response.status_code == 200:
            data = response.json()
            
            # Validate response structure
            alternate_meal = data.get("alternate_meal")
            if alternate_meal and alternate_meal.get("name") and alternate_meal.get("calories"):
                return log_test_result("Alternate Meal Generation (Claude Sonnet 4.6)", True,
                                     f"Generated alternate meal: '{alternate_meal['name']}' ({alternate_meal['calories']} cal)")
            else:
                return log_test_result("Alternate Meal Generation (Claude Sonnet 4.6)", False,
                                     f"Invalid alternate meal structure: {alternate_meal}")
        else:
            error_details = response.text if response.text else f"HTTP {response.status_code}"
            return log_test_result("Alternate Meal Generation (Claude Sonnet 4.6)", False, error_details)
            
    except Exception as e:
        return log_test_result("Alternate Meal Generation (Claude Sonnet 4.6)", False, f"Exception: {str(e)}")

def setup_test_user():
    """Setup test user profile for macro calculation"""
    try:
        # Check if user already exists
        response = requests.get(f"{BACKEND_URL}/profile/{TEST_USER_ID}")
        if response.status_code == 200:
            return True  # User already exists
        
        # Create user profile
        payload = {
            "name": "Claude Test User",
            "email": "claudetest@interfitai.com",
            "weight": 75.0,
            "height": 175.0,
            "age": 28,
            "gender": "male",
            "activity_level": "active",
            "goal": "muscle_building"
        }
        
        response = requests.post(f"{BACKEND_URL}/profiles/{TEST_USER_ID}", json=payload, timeout=10)
        return response.status_code == 200
        
    except Exception as e:
        print(f"Warning: Could not setup test user: {e}")
        return False

def run_claude_migration_tests():
    """Run all tests for Claude Sonnet 4.6 migration"""
    print("=" * 80)
    print("🧪 INTERFITAI CLAUDE SONNET 4.6 MIGRATION TESTING")
    print("=" * 80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print()
    
    # Setup test user
    print("🔧 Setting up test user...")
    setup_test_user()
    print()
    
    results = []
    
    # Test 1: Health Check
    print("1️⃣ HEALTH CHECK")
    results.append(test_health_check())
    print()
    
    # Test 2: AI Workout Generation (Claude Sonnet 4.6)
    print("2️⃣ AI WORKOUT GENERATION")
    results.append(test_ai_workout_generation())
    print()
    
    # Test 3: AI Meal Plan Generation (Claude Sonnet 4.6)
    print("3️⃣ AI MEAL PLAN GENERATION")
    results.append(test_ai_meal_plan_generation())
    print()
    
    # Test 4: Ask InterFitAI Chat (Claude Sonnet 4.6)
    print("4️⃣ ASK INTERFITAI CHAT")
    results.append(test_ask_interfitai_chat())
    print()
    
    # Test 5: Alternate Meal Generation (Claude Sonnet 4.6)
    print("5️⃣ ALTERNATE MEAL GENERATION")
    results.append(test_alternate_meal_generation())
    print()
    
    # Summary
    print("=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    if passed == total:
        print("🎉 ALL CLAUDE SONNET 4.6 MIGRATION TESTS PASSED!")
        print("✨ All AI endpoints successfully migrated from OpenAI GPT-4o to Claude Sonnet 4.6")
    else:
        print("⚠️  SOME TESTS FAILED - Claude Sonnet 4.6 migration needs attention")
        print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    print("=" * 80)
    return passed == total

if __name__ == "__main__":
    success = run_claude_migration_tests()
    sys.exit(0 if success else 1)