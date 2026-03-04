#!/usr/bin/env python3

import requests
import json
import time
from datetime import datetime

# Backend URL from environment (matches frontend configuration)
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

def log_test(message):
    """Log test messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

def measure_response_time(func, *args, **kwargs):
    """Measure function execution time"""
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    response_time = end_time - start_time
    return result, response_time

def test_health_check():
    """Test the health check endpoint"""
    log_test("🔍 Testing Health Check Endpoint...")
    
    try:
        response, response_time = measure_response_time(
            requests.get, f"{BACKEND_URL}/health", timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(f"✅ Health check PASSED - Status: {response.status_code}")
            log_test(f"   Response time: {response_time:.2f}s")
            log_test(f"   Response: {data}")
            return True
        else:
            log_test(f"❌ Health check FAILED - Status: {response.status_code}")
            log_test(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        log_test(f"❌ Health check ERROR: {str(e)}")
        return False

def test_meal_plan_generation():
    """Test the OPTIMIZED meal plan generation with 3-day prompt"""
    log_test("🔍 Testing OPTIMIZED Meal Plan Generation (3-day prompt)...")
    
    # Test data using real profile ID with calculated macros
    test_data = {
        "user_id": "b060147a-bfac-4e3a-8eb3-44df35be48ae",
        "food_preferences": "high_protein",  # Should be string, not list
        "supplements": [],
        "supplements_custom": "",
        "allergies": [],
        "cuisine_preference": ""
    }
    
    try:
        log_test("   Sending request to meal plan generation...")
        response, response_time = measure_response_time(
            requests.post, 
            f"{BACKEND_URL}/mealplans/generate",
            json=test_data,
            timeout=120  # 2 minutes timeout for AI generation
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(f"✅ Meal plan generation PASSED - Status: {response.status_code}")
            log_test(f"   Response time: {response_time:.2f}s")
            log_test(f"   Generated plan: '{data.get('name', 'Unknown')}'")
            log_test(f"   Days in plan: {len(data.get('meal_days', []))}")
            log_test(f"   Target calories: {data.get('target_calories')} kcal")
            
            # Validate structure
            if data.get('meal_days') and len(data.get('meal_days')) >= 1:
                first_day = data['meal_days'][0]
                meals_count = len(first_day.get('meals', []))
                log_test(f"   Meals per day: {meals_count}")
                if meals_count > 0:
                    sample_meal = first_day['meals'][0]
                    log_test(f"   Sample meal: '{sample_meal.get('name')}' ({sample_meal.get('calories')} cal)")
            
            return True, response_time
        else:
            log_test(f"❌ Meal plan generation FAILED - Status: {response.status_code}")
            try:
                error_data = response.json()
                log_test(f"   Error: {error_data.get('detail', 'Unknown error')}")
            except:
                log_test(f"   Raw error: {response.text[:200]}...")
            return False, response_time
            
    except requests.exceptions.Timeout:
        log_test("❌ Meal plan generation TIMEOUT - Request exceeded 2 minutes")
        return False, 120.0
    except Exception as e:
        log_test(f"❌ Meal plan generation ERROR: {str(e)}")
        return False, 0.0

def test_workout_generation():
    """Test the OPTIMIZED workout generation with reduced days"""
    log_test("🔍 Testing OPTIMIZED Workout Generation (2 days)...")
    
    # Test data using real profile ID with calculated macros
    test_data = {
        "user_id": "b060147a-bfac-4e3a-8eb3-44df35be48ae",
        "goal": "muscle_building", 
        "focus_areas": ["chest"],
        "equipment": ["dumbbell"],
        "injuries": None,  # Should be string or None, not empty list
        "days_per_week": 2,
        "duration_minutes": 30
    }
    
    try:
        log_test("   Sending request to workout generation...")
        response, response_time = measure_response_time(
            requests.post,
            f"{BACKEND_URL}/workouts/generate", 
            json=test_data,
            timeout=120  # 2 minutes timeout for AI generation
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test(f"✅ Workout generation PASSED - Status: {response.status_code}")
            log_test(f"   Response time: {response_time:.2f}s") 
            log_test(f"   Generated program: '{data.get('name', 'Unknown')}'")
            log_test(f"   Days per week: {data.get('days_per_week')}")
            log_test(f"   Session duration: {data.get('session_duration_minutes')} minutes")
            
            # Validate structure
            workout_days = data.get('workout_days', [])
            log_test(f"   Workout days: {len(workout_days)}")
            
            if workout_days:
                first_day = workout_days[0]
                exercises_count = len(first_day.get('exercises', []))
                log_test(f"   Exercises in first day: {exercises_count}")
                if exercises_count > 0:
                    sample_exercise = first_day['exercises'][0] 
                    log_test(f"   Sample exercise: '{sample_exercise.get('name')}' - {sample_exercise.get('sets')} sets x {sample_exercise.get('reps')} reps")
            
            return True, response_time
        else:
            log_test(f"❌ Workout generation FAILED - Status: {response.status_code}")
            try:
                error_data = response.json()
                log_test(f"   Error: {error_data.get('detail', 'Unknown error')}")
            except:
                log_test(f"   Raw error: {response.text[:200]}...")
            return False, response_time
            
    except requests.exceptions.Timeout:
        log_test("❌ Workout generation TIMEOUT - Request exceeded 2 minutes")
        return False, 120.0
    except Exception as e:
        log_test(f"❌ Workout generation ERROR: {str(e)}")
        return False, 0.0

def main():
    """Run all backend tests"""
    log_test("=" * 80)
    log_test("🚀 BACKEND TESTING: Optimized AI Endpoints with Shorter Prompts")
    log_test("=" * 80)
    log_test(f"Backend URL: {BACKEND_URL}")
    log_test("")
    
    # Track results
    results = {}
    total_start = time.time()
    
    # Test 1: Health Check
    results['health'] = test_health_check()
    log_test("")
    
    # Test 2: Optimized Meal Plan Generation (3-day prompt)
    meal_success, meal_time = test_meal_plan_generation()
    results['meal_plan'] = meal_success
    results['meal_plan_time'] = meal_time
    log_test("")
    
    # Test 3: Optimized Workout Generation (2 days)
    workout_success, workout_time = test_workout_generation()
    results['workout'] = workout_success
    results['workout_time'] = workout_time
    log_test("")
    
    # Summary
    total_time = time.time() - total_start
    log_test("=" * 80)
    log_test("📊 TESTING SUMMARY")
    log_test("=" * 80)
    
    passed = sum([results['health'], results['meal_plan'], results['workout']])
    total = 3
    
    log_test(f"✅ Health Check: {'PASSED' if results['health'] else 'FAILED'}")
    log_test(f"✅ Meal Plan (3-day): {'PASSED' if results['meal_plan'] else 'FAILED'} - {results.get('meal_plan_time', 0):.2f}s")
    log_test(f"✅ Workout (2-day): {'PASSED' if results['workout'] else 'FAILED'} - {results.get('workout_time', 0):.2f}s")
    log_test("")
    log_test(f"🎯 OVERALL: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    log_test(f"⏱️  Total testing time: {total_time:.2f}s")
    
    if passed == total:
        log_test("🎉 ALL OPTIMIZED ENDPOINTS WORKING!")
    else:
        log_test("⚠️  Some endpoints need attention")
    
    return results

if __name__ == "__main__":
    main()