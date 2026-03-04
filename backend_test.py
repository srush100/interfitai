#!/usr/bin/env python3

import requests
import json
import time
import sys

# Backend URL from environment
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

def test_health_check():
    """Test the health check endpoint"""
    print("\n🔍 Testing Health Check...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check failed with error: {str(e)}")
        return False

def test_meal_plan_generation():
    """Test the optimized meal plan generation endpoint using Claude 3.5 Haiku"""
    print("\n🍽️  Testing OPTIMIZED Meal Plan Generation (Claude 3.5 Haiku)...")
    
    payload = {
        "user_id": "d704bac8-fa54-4d5b-b984-cc17393c1244",
        "food_preferences": "whole_foods",
        "supplements": [],
        "supplements_custom": "",
        "allergies": [],
        "cuisine_preference": ""
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/mealplans/generate", 
            json=payload, 
            timeout=60,  # 60 second timeout
            headers={"Content-Type": "application/json"}
        )
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {duration:.2f} seconds")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Meal plan generated successfully")
            print(f"Plan Name: {result.get('name', 'N/A')}")
            print(f"Total Meals: {len(result.get('meals', []))}")
            print(f"Total Calories: {result.get('total_calories', 'N/A')}")
            
            # Check if it completed within 30 seconds (optimization goal)
            if duration <= 30:
                print(f"🚀 PERFORMANCE GOAL MET: Completed in {duration:.2f}s (under 30s target)")
            else:
                print(f"⚠️  PERFORMANCE WARNING: Took {duration:.2f}s (over 30s target)")
            
            return True
        else:
            print(f"❌ Meal plan generation failed")
            print(f"Response: {response.text}")
            
            # Check for budget/quota errors
            if "budget" in response.text.lower() or "quota" in response.text.lower():
                print("💰 BUDGET ERROR DETECTED")
            
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Meal plan generation timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Meal plan generation failed with error: {str(e)}")
        return False

def test_workout_generation():
    """Test the optimized workout generation endpoint using Claude 3.5 Haiku"""
    print("\n💪 Testing OPTIMIZED Workout Generation (Claude 3.5 Haiku)...")
    
    payload = {
        "user_id": "d704bac8-fa54-4d5b-b984-cc17393c1244",
        "goal": "muscle_building",
        "focus_areas": ["chest"],
        "equipment": ["dumbbell"],
        "injuries": "",
        "days_per_week": 2,
        "duration_minutes": 30
    }
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/workouts/generate", 
            json=payload, 
            timeout=60,  # 60 second timeout
            headers={"Content-Type": "application/json"}
        )
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {duration:.2f} seconds")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Workout generated successfully")
            print(f"Program Name: {result.get('name', 'N/A')}")
            print(f"Workout Days: {len(result.get('workout_days', []))}")
            
            # Check if it completed within 30 seconds (optimization goal)
            if duration <= 30:
                print(f"🚀 PERFORMANCE GOAL MET: Completed in {duration:.2f}s (under 30s target)")
            else:
                print(f"⚠️  PERFORMANCE WARNING: Took {duration:.2f}s (over 30s target)")
            
            return True
        else:
            print(f"❌ Workout generation failed")
            print(f"Response: {response.text}")
            
            # Check for budget/quota errors
            if "budget" in response.text.lower() or "quota" in response.text.lower():
                print("💰 BUDGET ERROR DETECTED")
            
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Workout generation timed out after 60 seconds")
        return False
    except Exception as e:
        print(f"❌ Workout generation failed with error: {str(e)}")
        return False

def main():
    """Run all tests for the optimized AI endpoints"""
    print("🧪 TESTING OPTIMIZED AI ENDPOINTS (Claude 3.5 Haiku)")
    print("=" * 60)
    
    results = {
        'health': test_health_check(),
        'meal_plan': test_meal_plan_generation(), 
        'workout': test_workout_generation()
    }
    
    print("\n📊 SUMMARY")
    print("=" * 30)
    
    success_count = sum(results.values())
    total_count = len(results)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nOverall: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("🎉 ALL OPTIMIZED ENDPOINTS WORKING!")
    else:
        print("⚠️  Some optimized endpoints need attention")
    
    return success_count == total_count

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)