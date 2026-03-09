#!/usr/bin/env python3

import requests
import json
import time
from typing import Dict, Any

# Get backend URL from frontend .env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('EXPO_PUBLIC_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading backend URL: {e}")
    return "http://localhost:8001"

BACKEND_URL = get_backend_url()
API_BASE = f"{BACKEND_URL}/api"

# Test user ID from review request
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

print(f"🔗 Testing backend at: {API_BASE}")
print(f"👤 Using test user ID: {TEST_USER_ID}")

def test_health_check():
    """Test health check endpoint"""
    print("\n=== Health Check Test ===")
    start_time = time.time()
    
    try:
        response = requests.get(f"{API_BASE}/health", timeout=30)
        duration = time.time() - start_time
        
        print(f"Status: {response.status_code}")
        print(f"Response time: {duration:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def analyze_meal_plan_macros(meal_plan: Dict[str, Any], diet_type: str):
    """Analyze meal plan macros for diet compliance"""
    print(f"\n=== {diet_type.upper()} PLAN ANALYSIS ===")
    
    if not meal_plan.get("meal_days"):
        print("❌ No meal days found in plan")
        return
    
    # Analyze Day 1 as requested in review
    day_1 = meal_plan["meal_days"][0]
    day_1_meals = day_1.get("meals", [])
    
    print(f"Plan Name: {meal_plan.get('name', 'Unknown')}")
    print(f"Day 1 Analysis ({len(day_1_meals)} meals):")
    print(f"- Total Calories: {day_1.get('total_calories', 0)}")
    print(f"- Total Carbs: {day_1.get('total_carbs', 0)}g")
    print(f"- Total Fats: {day_1.get('total_fats', 0)}g")
    print(f"- Total Protein: {day_1.get('total_protein', 0)}g")
    
    # Sample meal names
    sample_meals = [meal.get("name", "Unknown") for meal in day_1_meals[:3]]
    print(f"- Sample meals: {sample_meals}")
    
    # Diet-specific compliance checks
    carbs = day_1.get('total_carbs', 0)
    
    if diet_type.lower() == "keto":
        if carbs < 50:
            print("✅ KETO COMPLIANCE: Carbs < 50g ✓")
        else:
            print(f"❌ KETO ISSUE: Carbs {carbs}g > 50g limit")
    
    elif diet_type.lower() == "carnivore":
        if carbs < 10:
            print("✅ CARNIVORE COMPLIANCE: Near-zero carbs ✓")
        else:
            print(f"❌ CARNIVORE ISSUE: Carbs {carbs}g > 10g limit")
        
        # Check if meals are meat-focused
        meat_keywords = ["steak", "eggs", "bacon", "beef", "chicken", "pork", "lamb", "fish", "salmon"]
        meat_meals = sum(1 for meal in day_1_meals if any(keyword in meal.get("name", "").lower() for keyword in meat_keywords))
        print(f"- Meat-based meals: {meat_meals}/{len(day_1_meals)}")

def test_keto_meal_plan():
    """Test Keto meal plan generation"""
    print("\n=== KETO MEAL PLAN TEST ===")
    start_time = time.time()
    
    payload = {
        "user_id": TEST_USER_ID,
        "food_preferences": "keto"
    }
    
    try:
        response = requests.post(f"{API_BASE}/mealplans/generate", 
                               json=payload, 
                               timeout=120)
        duration = time.time() - start_time
        
        print(f"Status: {response.status_code}")
        print(f"Response time: {duration:.2f}s")
        
        if response.status_code == 200:
            meal_plan = response.json()
            analyze_meal_plan_macros(meal_plan, "keto")
            print("✅ Keto meal plan generated successfully")
            return meal_plan
        else:
            print(f"❌ Keto meal plan failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Keto meal plan error: {e}")
        return None

def test_carnivore_meal_plan():
    """Test Carnivore meal plan generation"""
    print("\n=== CARNIVORE MEAL PLAN TEST ===")
    start_time = time.time()
    
    payload = {
        "user_id": TEST_USER_ID,
        "food_preferences": "carnivore"
    }
    
    try:
        response = requests.post(f"{API_BASE}/mealplans/generate", 
                               json=payload, 
                               timeout=120)
        duration = time.time() - start_time
        
        print(f"Status: {response.status_code}")
        print(f"Response time: {duration:.2f}s")
        
        if response.status_code == 200:
            meal_plan = response.json()
            analyze_meal_plan_macros(meal_plan, "carnivore")
            print("✅ Carnivore meal plan generated successfully")
            return meal_plan
        else:
            print(f"❌ Carnivore meal plan failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Carnivore meal plan error: {e}")
        return None

def main():
    """Run all diet-specific meal plan tests"""
    print("🧪 DIET-SPECIFIC MEAL PLAN TESTING")
    print("=" * 50)
    
    # Health check first
    if not test_health_check():
        print("❌ Health check failed - aborting tests")
        return
    
    results = {}
    
    # Test Keto
    keto_plan = test_keto_meal_plan()
    results["keto"] = keto_plan is not None
    
    # Test Carnivore  
    carnivore_plan = test_carnivore_meal_plan()
    results["carnivore"] = carnivore_plan is not None
    
    print(f"\n=== DIET-SPECIFIC TESTING SUMMARY ===")
    print(f"Health Check: ✅")
    print(f"Keto Plan: {'✅' if results['keto'] else '❌'}")
    print(f"Carnivore Plan: {'✅' if results['carnivore'] else '❌'}")
    
    if all(results.values()):
        print("🎉 All diet-specific meal plan tests passed!")
    else:
        print("⚠️ Some diet-specific tests failed")

if __name__ == "__main__":
    main()