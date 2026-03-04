#!/usr/bin/env python3
"""
Backend API Test Script for InterFitAI
Tests OpenAI GPT-4o reversion from Claude Sonnet 4.6
"""

import requests
import json
import time
from datetime import datetime

# Base URL from environment
BASE_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# Test user ID for consistency
TEST_USER_ID = "d704bac8-fa54-4d5b-b984-cc17393c1244"

def log_test(test_name, response_time, success, details=""):
    """Log test results with timing"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} {test_name} ({response_time:.2f}s)")
    if details:
        print(f"    Details: {details}")
    print()

def test_health_check():
    """Test 1: Health Check - GET /api/health"""
    print("=" * 60)
    print("Testing Health Check Endpoint")
    print("=" * 60)
    
    start_time = time.time()
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            log_test("Health Check", response_time, True, f"Response: {data}")
            return True
        else:
            log_test("Health Check", response_time, False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        response_time = time.time() - start_time
        log_test("Health Check", response_time, False, f"Error: {str(e)}")
        return False

def test_workout_generation():
    """Test 2: AI Workout Generation with OpenAI GPT-4o - POST /api/workouts/generate"""
    print("=" * 60)
    print("Testing AI Workout Generation (OpenAI GPT-4o)")
    print("=" * 60)
    
    payload = {
        "user_id": TEST_USER_ID,
        "goal": "muscle_building",
        "focus_areas": ["chest"],
        "equipment": ["dumbbell"],
        "injuries": None,
        "days_per_week": 3,
        "duration_minutes": 30
    }
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/workouts/generate", 
            json=payload, 
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            workout_name = data.get('name', 'Unknown')
            workout_days = len(data.get('workout_days', []))
            log_test("Workout Generation", response_time, True, 
                    f"Generated: '{workout_name}' with {workout_days} days")
            return True
        else:
            log_test("Workout Generation", response_time, False, 
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        response_time = time.time() - start_time
        log_test("Workout Generation", response_time, False, f"Error: {str(e)}")
        return False

def test_meal_plan_generation():
    """Test 3: AI Meal Plan Generation with OpenAI GPT-4o - POST /api/mealplans/generate"""
    print("=" * 60)
    print("Testing AI Meal Plan Generation (OpenAI GPT-4o)")
    print("=" * 60)
    
    payload = {
        "user_id": TEST_USER_ID,
        "food_preferences": "high_protein",
        "supplements": [],
        "supplements_custom": "",
        "allergies": [],
        "cuisine_preference": ""
    }
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/mealplans/generate",
            json=payload,
            timeout=30,
            headers={"Content-Type": "application/json"}
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            plan_name = data.get('name', 'Unknown')
            meal_days = len(data.get('meal_days', []))
            log_test("Meal Plan Generation", response_time, True,
                    f"Generated: '{plan_name}' with {meal_days} days")
            return True
        else:
            log_test("Meal Plan Generation", response_time, False,
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        response_time = time.time() - start_time
        log_test("Meal Plan Generation", response_time, False, f"Error: {str(e)}")
        return False

def test_chat_endpoint():
    """Test 4: Ask InterFitAI Chat with OpenAI GPT-4o - POST /api/chat"""
    print("=" * 60)
    print("Testing Ask InterFitAI Chat (OpenAI GPT-4o)")
    print("=" * 60)
    
    payload = {
        "user_id": TEST_USER_ID,
        "message": "What exercises are best for chest?"
    }
    
    start_time = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json=payload,
            timeout=20,
            headers={"Content-Type": "application/json"}
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            ai_response = data.get('response', '')[:100] + "..." if len(data.get('response', '')) > 100 else data.get('response', '')
            log_test("Chat Endpoint", response_time, True,
                    f"AI Response: {ai_response}")
            return True
        else:
            log_test("Chat Endpoint", response_time, False,
                    f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        response_time = time.time() - start_time
        log_test("Chat Endpoint", response_time, False, f"Error: {str(e)}")
        return False

def main():
    """Run all tests and summarize results"""
    print("🤖 InterFitAI Backend API Testing - OpenAI GPT-4o Reversion")
    print(f"🎯 Target URL: {BASE_URL}")
    print(f"📅 Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"👤 Test User ID: {TEST_USER_ID}")
    print()
    
    test_results = []
    
    # Run all tests
    test_results.append(("Health Check", test_health_check()))
    test_results.append(("Workout Generation", test_workout_generation()))
    test_results.append(("Meal Plan Generation", test_meal_plan_generation()))
    test_results.append(("Chat Endpoint", test_chat_endpoint()))
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in test_results if success)
    total = len(test_results)
    
    for test_name, success in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print()
    print(f"📊 Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("🎉 All OpenAI GPT-4o endpoints working correctly!")
    else:
        print("⚠️ Some endpoints failed - check details above")
    
    return passed == total

if __name__ == "__main__":
    main()