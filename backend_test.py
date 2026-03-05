#!/usr/bin/env python3
"""
Comprehensive backend testing for InterFitAI
Testing all newly implemented features based on review request:
1. Admin Access System
2. Subscription System  
3. Exercise GIFs in Workout Generation
4. Health Check
"""

import requests
import json
import sys
import os
from datetime import datetime

# Backend URL from frontend .env
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

def test_health_check():
    """Test GET /api/health endpoint"""
    print("\n🔍 Testing Health Check...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=20)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check successful: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {str(e)}")
        return False

def test_admin_access_system():
    """Test all admin access endpoints"""
    print("\n🔍 Testing Admin Access System...")
    
    results = []
    
    # Test 1: Check admin status for sebastianrush5@gmail.com (should be admin)
    print("\n1. Testing admin check for sebastianrush5@gmail.com...")
    try:
        response = requests.get(f"{BACKEND_URL}/admin/is-admin/sebastianrush5@gmail.com", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("is_admin") == True:
                print(f"✅ Admin check passed: {data}")
                results.append(True)
            else:
                print(f"❌ Expected is_admin: true, got: {data}")
                results.append(False)
        else:
            print(f"❌ Admin check failed: {response.status_code} - {response.text}")
            results.append(False)
    except Exception as e:
        print(f"❌ Admin check error: {str(e)}")
        results.append(False)
    
    # Test 2: Check admin status for random email (should be false)
    print("\n2. Testing admin check for random@email.com...")
    try:
        response = requests.get(f"{BACKEND_URL}/admin/is-admin/random@email.com", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("is_admin") == False:
                print(f"✅ Non-admin check passed: {data}")
                results.append(True)
            else:
                print(f"❌ Expected is_admin: false, got: {data}")
                results.append(False)
        else:
            print(f"❌ Non-admin check failed: {response.status_code} - {response.text}")
            results.append(False)
    except Exception as e:
        print(f"❌ Non-admin check error: {str(e)}")
        results.append(False)
    
    # Test 3: Grant access endpoint
    print("\n3. Testing admin grant access...")
    grant_data = {
        "admin_email": "sebastianrush5@gmail.com",
        "user_email": "testuser@example.com",
        "reason": "testing"
    }
    try:
        response = requests.post(f"{BACKEND_URL}/admin/grant-access", 
                                json=grant_data, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Grant access successful: {data}")
            results.append(True)
        else:
            print(f"❌ Grant access failed: {response.status_code} - {response.text}")
            results.append(False)
    except Exception as e:
        print(f"❌ Grant access error: {str(e)}")
        results.append(False)
    
    # Test 4: Get free access list
    print("\n4. Testing get free access list...")
    try:
        response = requests.get(f"{BACKEND_URL}/admin/free-access-list?admin_email=sebastianrush5@gmail.com", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Free access list retrieved: {len(data)} users")
            # Check if our test user is in the list
            test_user_found = any(user.get("email") == "testuser@example.com" for user in data)
            if test_user_found:
                print("✅ Test user found in free access list")
            else:
                print("⚠️  Test user not found in free access list (might be expected)")
            results.append(True)
        else:
            print(f"❌ Get free access list failed: {response.status_code} - {response.text}")
            results.append(False)
    except Exception as e:
        print(f"❌ Get free access list error: {str(e)}")
        results.append(False)
    
    return all(results)

def test_subscription_system():
    """Test subscription system endpoints"""
    print("\n🔍 Testing Subscription System...")
    
    results = []
    
    # Test 1: Get subscription plans
    print("\n1. Testing subscription plans endpoint...")
    try:
        response = requests.get(f"{BACKEND_URL}/subscription/plans", timeout=10)
        if response.status_code == 200:
            plans = response.json()
            print(f"✅ Subscription plans retrieved: {json.dumps(plans, indent=2)}")
            
            # Verify required plans exist with 3-day trial
            required_plans = ["monthly", "quarterly", "yearly"]
            all_plans_exist = all(plan in plans for plan in required_plans)
            all_trials_correct = all(plans[plan].get("trial_days") == 3 for plan in required_plans if plan in plans)
            
            if all_plans_exist and all_trials_correct:
                print("✅ All required plans with 3-day trial found")
                results.append(True)
            else:
                print(f"❌ Missing required plans or incorrect trial days")
                results.append(False)
        else:
            print(f"❌ Get subscription plans failed: {response.status_code} - {response.text}")
            results.append(False)
    except Exception as e:
        print(f"❌ Get subscription plans error: {str(e)}")
        results.append(False)
    
    # Test 2: Check subscription status for test user
    print("\n2. Testing subscription check endpoint...")
    test_user_id = "d704bac8-fa54-4d5b-b984-cc17393c1244"
    try:
        response = requests.get(f"{BACKEND_URL}/subscription/check/{test_user_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Subscription check successful: {data}")
            # Should contain has_access, reason, subscription_status
            required_fields = ["has_access", "reason", "subscription_status"]
            if all(field in data for field in required_fields):
                print("✅ All required subscription fields present")
                results.append(True)
            else:
                print(f"❌ Missing required subscription fields")
                results.append(False)
        else:
            print(f"❌ Subscription check failed: {response.status_code} - {response.text}")
            results.append(False)
    except Exception as e:
        print(f"❌ Subscription check error: {str(e)}")
        results.append(False)
    
    return all(results)

def test_workout_generation_with_gifs():
    """Test workout generation includes GIF URLs"""
    print("\n🔍 Testing Exercise GIFs in Workout Generation...")
    
    workout_data = {
        "user_id": "d704bac8-fa54-4d5b-b984-cc17393c1244",
        "goal": "muscle_building",
        "focus_areas": ["chest"],
        "equipment": ["dumbbell", "barbell"],
        "injuries": "none",
        "days_per_week": 2,
        "duration_minutes": 30
    }
    
    try:
        response = requests.post(f"{BACKEND_URL}/workouts/generate", 
                                json=workout_data, timeout=60)
        if response.status_code == 200:
            workout = response.json()
            print(f"✅ Workout generation successful")
            print(f"Response keys: {list(workout.keys())}")
            
            # Check if workout has exercises with gif_url
            exercises_with_gifs = []
            total_exercises = 0
            
            # Debug: print structure
            if "workout_days" in workout:
                print(f"Number of workout days: {len(workout['workout_days'])}")
                for i, day in enumerate(workout["workout_days"]):
                    print(f"Day {i+1} keys: {list(day.keys())}")
                    if "exercises" in day:
                        print(f"Day {i+1} exercises count: {len(day['exercises'])}")
                        for j, exercise in enumerate(day["exercises"]):
                            total_exercises += 1
                            print(f"Exercise {j+1} keys: {list(exercise.keys())}")
                            if "gif_url" in exercise and exercise["gif_url"]:
                                exercises_with_gifs.append({
                                    "name": exercise.get("name", "Unknown"),
                                    "gif_url": exercise["gif_url"]
                                })
            elif "workout_plan" in workout:
                workout_plan = workout["workout_plan"]
                print(f"Workout plan keys: {list(workout_plan.keys())}")
                if "workout_days" in workout_plan:
                    print(f"Number of workout days: {len(workout_plan['workout_days'])}")
                    for i, day in enumerate(workout_plan["workout_days"]):
                        print(f"Day {i+1} keys: {list(day.keys())}")
                        if "exercises" in day:
                            print(f"Day {i+1} exercises count: {len(day['exercises'])}")
                            for j, exercise in enumerate(day["exercises"]):
                                total_exercises += 1
                                print(f"Exercise {j+1} keys: {list(exercise.keys())}")
                                if "gif_url" in exercise and exercise["gif_url"]:
                                    exercises_with_gifs.append({
                                        "name": exercise.get("name", "Unknown"),
                                        "gif_url": exercise["gif_url"]
                                    })
            
            print(f"✅ Total exercises: {total_exercises}")
            print(f"✅ Exercises with GIFs: {len(exercises_with_gifs)}")
            
            if exercises_with_gifs:
                print("✅ Sample exercises with GIFs:")
                for i, ex in enumerate(exercises_with_gifs[:3]):  # Show first 3
                    print(f"   - {ex['name']}: {ex['gif_url']}")
                return True
            else:
                if total_exercises > 0:
                    print("❌ Exercises found but no gif_url field present")
                else:
                    print("❌ No exercises found in workout response")
                return False
        else:
            print(f"❌ Workout generation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Workout generation error: {str(e)}")
        return False

def run_all_tests():
    """Run all tests and provide summary"""
    print("🚀 Starting InterFitAI Backend Testing...")
    print(f"Backend URL: {BACKEND_URL}")
    print("=" * 60)
    
    test_results = {}
    
    # Run all tests
    test_results["Health Check"] = test_health_check()
    test_results["Admin Access System"] = test_admin_access_system()
    test_results["Subscription System"] = test_subscription_system()
    test_results["Exercise GIFs"] = test_workout_generation_with_gifs()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    success_rate = (passed / (passed + failed)) * 100 if (passed + failed) > 0 else 0
    print(f"Success Rate: {success_rate:.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) failed - check details above")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)