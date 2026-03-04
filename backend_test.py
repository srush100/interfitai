#!/usr/bin/env python3
"""
InterFitAI Backend API Testing Script
Tests all high priority backend endpoints according to test_result.md
"""

import requests
import json
import time
import base64
from datetime import datetime, date
import uuid
import random
from PIL import Image
import io

# Backend URL from frontend/.env
BASE_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

# Test results collector
test_results = {
    "passed": [],
    "failed": [],
    "errors": []
}

def log_result(test_name, success, message="", response_data=None):
    """Log test result"""
    result = {
        "test": test_name,
        "success": success,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }
    if response_data:
        result["response"] = response_data
    
    if success:
        test_results["passed"].append(result)
        print(f"✅ {test_name}: {message}")
    else:
        test_results["failed"].append(result)
        print(f"❌ {test_name}: {message}")

def log_error(test_name, error):
    """Log test error"""
    error_result = {
        "test": test_name,
        "error": str(error),
        "timestamp": datetime.now().isoformat()
    }
    test_results["errors"].append(error_result)
    print(f"💥 {test_name}: ERROR - {error}")

def test_health_check():
    """Test basic health check"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            log_result("Health Check", True, f"API is healthy - {response.json()}")
            return True
        else:
            log_result("Health Check", False, f"Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        log_error("Health Check", e)
        return False

def test_user_profile_crud():
    """Test User Profile CRUD with Macro Calculation"""
    try:
        # Test profile creation
        profile_data = {
            "name": "Alex Johnson",
            "email": "alex.johnson@test.com",
            "weight": 75.0,
            "height": 175.0,
            "age": 28,
            "gender": "male",
            "activity_level": "moderate",
            "goal": "muscle_building"
        }
        
        response = requests.post(f"{BASE_URL}/profile", json=profile_data, timeout=15)
        
        if response.status_code == 200:
            profile = response.json()
            user_id = profile["id"]
            
            # Validate macro calculation
            if "calculated_macros" in profile and profile["calculated_macros"]:
                macros = profile["calculated_macros"]
                required_fields = ["calories", "protein", "carbs", "fats", "bmr", "tdee"]
                if all(field in macros for field in required_fields):
                    log_result("Profile Creation", True, f"Profile created with macros: {macros['calories']} cal, {macros['protein']}g protein")
                else:
                    log_result("Profile Creation", False, f"Missing macro fields: {required_fields}")
                    return None
            else:
                log_result("Profile Creation", False, "No calculated macros in response")
                return None
            
            # Test profile retrieval
            get_response = requests.get(f"{BASE_URL}/profile/{user_id}", timeout=10)
            if get_response.status_code == 200:
                retrieved_profile = get_response.json()
                if retrieved_profile["id"] == user_id:
                    log_result("Profile Retrieval", True, f"Successfully retrieved profile for user {user_id}")
                else:
                    log_result("Profile Retrieval", False, "Retrieved profile ID doesn't match")
                    return None
            else:
                log_result("Profile Retrieval", False, f"Failed to retrieve profile: {get_response.status_code}")
                return None
            
            # Test profile update
            update_data = {
                "weight": 80.0,
                "goal": "weight_loss"
            }
            update_response = requests.put(f"{BASE_URL}/profile/{user_id}", json=update_data, timeout=15)
            
            if update_response.status_code == 200:
                updated_profile = update_response.json()
                if updated_profile["weight"] == 80.0 and updated_profile["goal"] == "weight_loss":
                    # Check if macros were recalculated
                    if updated_profile["calculated_macros"]["calories"] != macros["calories"]:
                        log_result("Profile Update", True, f"Profile updated and macros recalculated: {updated_profile['calculated_macros']['calories']} calories")
                    else:
                        log_result("Profile Update", False, "Macros not recalculated after goal change")
                        return None
                else:
                    log_result("Profile Update", False, "Profile update values not reflected")
                    return None
            else:
                log_result("Profile Update", False, f"Profile update failed: {update_response.status_code}")
                return None
            
            return user_id
            
        else:
            log_result("Profile Creation", False, f"Failed to create profile: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        log_error("User Profile CRUD", e)
        return None

def test_ai_workout_generation(user_id):
    """Test AI Workout Generation"""
    try:
        workout_request = {
            "user_id": user_id,
            "goal": "build_muscle",
            "focus_areas": ["chest", "back"],
            "equipment": ["dumbbells", "barbells"],
            "injuries": None,
            "days_per_week": 4
        }
        
        print("🔄 Generating AI workout (this may take 10-30 seconds)...")
        response = requests.post(f"{BASE_URL}/workouts/generate", json=workout_request, timeout=45)
        
        if response.status_code == 200:
            workout = response.json()
            
            # Validate workout structure
            required_fields = ["id", "user_id", "name", "goal", "workout_days"]
            if all(field in workout for field in required_fields):
                workout_days = workout["workout_days"]
                if len(workout_days) > 0:
                    # Check first workout day structure
                    day = workout_days[0]
                    day_fields = ["day", "focus", "exercises", "duration_minutes"]
                    if all(field in day for field in day_fields):
                        exercises = day["exercises"]
                        if len(exercises) > 0:
                            # Check exercise structure
                            exercise = exercises[0]
                            exercise_fields = ["name", "sets", "reps", "instructions", "muscle_groups"]
                            if all(field in exercise for field in exercise_fields):
                                log_result("AI Workout Generation", True, f"Generated workout '{workout['name']}' with {len(workout_days)} days and {len(exercises)} exercises on day 1")
                                return workout["id"]
                            else:
                                log_result("AI Workout Generation", False, f"Exercise missing required fields: {exercise_fields}")
                                return None
                        else:
                            log_result("AI Workout Generation", False, "No exercises in workout day")
                            return None
                    else:
                        log_result("AI Workout Generation", False, f"Workout day missing required fields: {day_fields}")
                        return None
                else:
                    log_result("AI Workout Generation", False, "No workout days in response")
                    return None
            else:
                log_result("AI Workout Generation", False, f"Workout missing required fields: {required_fields}")
                return None
        else:
            log_result("AI Workout Generation", False, f"Failed to generate workout: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        log_error("AI Workout Generation", e)
        return None

def test_ai_meal_plan_generation(user_id):
    """Test AI Meal Plan Generation"""
    try:
        meal_request = {
            "user_id": user_id,
            "food_preferences": "whole_foods",
            "supplements": [],
            "allergies": []
        }
        
        print("🔄 Generating AI meal plan (this may take 10-30 seconds)...")
        response = requests.post(f"{BASE_URL}/mealplans/generate", json=meal_request, timeout=45)
        
        if response.status_code == 200:
            meal_plan = response.json()
            
            # Validate meal plan structure
            required_fields = ["id", "user_id", "name", "meal_days", "target_calories", "target_protein"]
            if all(field in meal_plan for field in required_fields):
                meal_days = meal_plan["meal_days"]
                if len(meal_days) > 0:
                    # Check first meal day structure
                    day = meal_days[0]
                    day_fields = ["day", "meals", "total_calories", "total_protein"]
                    if all(field in day for field in day_fields):
                        meals = day["meals"]
                        if len(meals) > 0:
                            # Check meal structure
                            meal = meals[0]
                            meal_fields = ["name", "meal_type", "ingredients", "instructions", "calories", "protein", "carbs", "fats"]
                            if all(field in meal for field in meal_fields):
                                log_result("AI Meal Plan Generation", True, f"Generated meal plan '{meal_plan['name']}' with {len(meal_days)} days and {len(meals)} meals on day 1")
                                return meal_plan["id"]
                            else:
                                log_result("AI Meal Plan Generation", False, f"Meal missing required fields: {meal_fields}")
                                return None
                        else:
                            log_result("AI Meal Plan Generation", False, "No meals in meal day")
                            return None
                    else:
                        log_result("AI Meal Plan Generation", False, f"Meal day missing required fields: {day_fields}")
                        return None
                else:
                    log_result("AI Meal Plan Generation", False, "No meal days in response")
                    return None
            else:
                log_result("AI Meal Plan Generation", False, f"Meal plan missing required fields: {required_fields}")
                return None
        else:
            log_result("AI Meal Plan Generation", False, f"Failed to generate meal plan: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        log_error("AI Meal Plan Generation", e)
        return None

def test_ask_interfitai_chat(user_id):
    """Test Ask InterFitAI Chat"""
    try:
        chat_request = {
            "user_id": user_id,
            "message": "What should I eat before a workout?"
        }
        
        print("🔄 Testing AI chat (this may take 10-30 seconds)...")
        response = requests.post(f"{BASE_URL}/chat", json=chat_request, timeout=45)
        
        if response.status_code == 200:
            chat_response = response.json()
            
            # Validate chat response structure
            required_fields = ["id", "user_id", "role", "content"]
            if all(field in chat_response for field in required_fields):
                if chat_response["role"] == "assistant" and len(chat_response["content"]) > 0:
                    log_result("Ask InterFitAI Chat", True, f"AI responded: '{chat_response['content'][:100]}...'")
                    return True
                else:
                    log_result("Ask InterFitAI Chat", False, "Invalid role or empty content in response")
                    return False
            else:
                log_result("Ask InterFitAI Chat", False, f"Chat response missing required fields: {required_fields}")
                return False
        else:
            log_result("Ask InterFitAI Chat", False, f"Failed to get chat response: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log_error("Ask InterFitAI Chat", e)
        return False

def test_food_logging(user_id):
    """Test Food Logging & Search"""
    try:
        # Test food search first
        search_response = requests.get(f"{BASE_URL}/food/search?query=chicken", timeout=10)
        
        if search_response.status_code == 200:
            foods = search_response.json()
            if len(foods) > 0:
                log_result("Food Search", True, f"Found {len(foods)} foods for 'chicken' query")
                
                # Use first found food for logging test
                food = foods[0]
                
                # Test food logging
                today = datetime.now().strftime("%Y-%m-%d")
                food_log_request = {
                    "user_id": user_id,
                    "food_name": food["name"],
                    "serving_size": "1 serving",
                    "calories": food["calories"],
                    "protein": food["protein"],
                    "carbs": food["carbs"],
                    "fats": food["fats"],
                    "fiber": 2.0,
                    "sugar": 1.0,
                    "sodium": 100.0,
                    "meal_type": "lunch",
                    "logged_date": today
                }
                
                log_response = requests.post(f"{BASE_URL}/food/log", json=food_log_request, timeout=10)
                
                if log_response.status_code == 200:
                    logged_food = log_response.json()
                    food_entry_id = logged_food["id"]
                    
                    # Test food logs retrieval
                    logs_response = requests.get(f"{BASE_URL}/food/logs/{user_id}", timeout=10)
                    
                    if logs_response.status_code == 200:
                        logs = logs_response.json()
                        if len(logs) > 0 and any(log["id"] == food_entry_id for log in logs):
                            log_result("Food Logging", True, f"Successfully logged and retrieved food: {food['name']}")
                            return True
                        else:
                            log_result("Food Logging", False, "Logged food not found in retrieval")
                            return False
                    else:
                        log_result("Food Logging", False, f"Failed to retrieve food logs: {logs_response.status_code}")
                        return False
                else:
                    log_result("Food Logging", False, f"Failed to log food: {log_response.status_code} - {log_response.text}")
                    return False
            else:
                log_result("Food Search", False, "No foods found in search")
                return False
        else:
            log_result("Food Search", False, f"Food search failed: {search_response.status_code}")
            return False
            
    except Exception as e:
        log_error("Food Logging & Search", e)
        return False

def test_step_tracking(user_id):
    """Test Step Tracking"""
    try:
        # Test step logging
        log_response = requests.post(f"{BASE_URL}/steps/log", params={
            "user_id": user_id,
            "steps": 8500,
            "distance_km": 6.8,
            "source": "device"
        }, timeout=10)
        
        if log_response.status_code == 200:
            step_entry = log_response.json()
            
            # Test step retrieval
            get_response = requests.get(f"{BASE_URL}/steps/{user_id}", timeout=10)
            
            if get_response.status_code == 200:
                steps_data = get_response.json()
                if isinstance(steps_data, list) and len(steps_data) > 0:
                    if steps_data[0]["steps"] == 8500:
                        log_result("Step Tracking", True, f"Successfully logged and retrieved {steps_data[0]['steps']} steps")
                        return True
                    else:
                        log_result("Step Tracking", False, "Step count mismatch")
                        return False
                elif isinstance(steps_data, dict) and steps_data.get("steps") == 8500:
                    log_result("Step Tracking", True, f"Successfully logged and retrieved {steps_data['steps']} steps")
                    return True
                else:
                    log_result("Step Tracking", False, "No steps data in response")
                    return False
            else:
                log_result("Step Tracking", False, f"Failed to retrieve steps: {get_response.status_code}")
                return False
        else:
            log_result("Step Tracking", False, f"Failed to log steps: {log_response.status_code} - {log_response.text}")
            return False
            
    except Exception as e:
        log_error("Step Tracking", e)
        return False

def test_food_image_analysis(user_id):
    """Test Food Image Analysis (using a sample base64 image)"""
    try:
        # Create a proper test image with visual features for OpenAI Vision API
        import random
        from PIL import Image
        import io
        
        # Create a realistic looking test image (100x100 with some variation)
        img = Image.new('RGB', (100, 100))
        pixels = []
        for y in range(100):
            for x in range(100):
                # Create some patterns to simulate food
                r = int(120 + 50 * random.random())
                g = int(80 + 40 * random.random())
                b = int(40 + 30 * random.random())
                pixels.append((r, g, b))
        img.putdata(pixels)
        
        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=85)
        test_image_b64 = base64.b64encode(buffer.getvalue()).decode('ascii')
        
        image_request = {
            "user_id": user_id,
            "image_base64": test_image_b64,
            "meal_type": "snack"
        }
        
        print("🔄 Testing food image analysis (this may take 10-30 seconds)...")
        response = requests.post(f"{BASE_URL}/food/analyze", json=image_request, timeout=45)
        
        if response.status_code == 200:
            food_entry = response.json()
            
            # Validate food analysis response
            required_fields = ["id", "user_id", "food_name", "calories", "protein", "carbs", "fats"]
            if all(field in food_entry for field in required_fields):
                log_result("Food Image Analysis", True, f"Analyzed image and identified: {food_entry['food_name']} ({food_entry['calories']} cal)")
                return True
            else:
                log_result("Food Image Analysis", False, f"Food analysis missing required fields: {required_fields}")
                return False
        else:
            log_result("Food Image Analysis", False, f"Failed to analyze food image: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        log_error("Food Image Analysis", e)
        return False

def test_stripe_subscription_checkout(user_id):
    """Test Stripe Subscription Checkout"""
    try:
        checkout_request = {
            "user_id": user_id,
            "plan_id": "monthly",
            "origin_url": "https://ai-fitness-pro-4.preview.emergentagent.com"
        }
        
        response = requests.post(f"{BASE_URL}/subscription/checkout", json=checkout_request, timeout=15)
        
        if response.status_code == 200:
            checkout_data = response.json()
            
            # Validate checkout response
            required_fields = ["url", "session_id"]
            if all(field in checkout_data for field in required_fields):
                if "checkout.stripe.com" in checkout_data["url"]:
                    log_result("Stripe Subscription Checkout", True, f"Successfully created checkout session: {checkout_data['session_id']}")
                    return checkout_data["session_id"]
                else:
                    log_result("Stripe Subscription Checkout", False, "Invalid Stripe URL in response")
                    return None
            else:
                log_result("Stripe Subscription Checkout", False, f"Checkout response missing required fields: {required_fields}")
                return None
        else:
            log_result("Stripe Subscription Checkout", False, f"Failed to create checkout: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        log_error("Stripe Subscription Checkout", e)
        return None

def print_summary():
    """Print test summary"""
    print("\n" + "="*60)
    print("🧪 INTERFITAI BACKEND TEST SUMMARY")
    print("="*60)
    
    total_tests = len(test_results["passed"]) + len(test_results["failed"]) + len(test_results["errors"])
    passed = len(test_results["passed"])
    failed = len(test_results["failed"])
    errors = len(test_results["errors"])
    
    print(f"Total Tests: {total_tests}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"💥 Errors: {errors}")
    
    if failed > 0:
        print(f"\n📋 FAILED TESTS ({failed}):")
        for result in test_results["failed"]:
            print(f"  • {result['test']}: {result['message']}")
    
    if errors > 0:
        print(f"\n🚨 ERROR TESTS ({errors}):")
        for result in test_results["errors"]:
            print(f"  • {result['test']}: {result['error']}")
    
    print("\n" + "="*60)
    
    return {
        "total": total_tests,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "success_rate": (passed / total_tests * 100) if total_tests > 0 else 0
    }

def main():
    """Main testing function"""
    print("🚀 Starting InterFitAI Backend API Testing...")
    print(f"📡 Testing API at: {BASE_URL}")
    print("="*60)
    
    # Test health check first
    if not test_health_check():
        print("❌ Health check failed. Stopping tests.")
        return
    
    # Create user profile and get user_id
    user_id = test_user_profile_crud()
    if not user_id:
        print("❌ User profile creation failed. Stopping dependent tests.")
        print_summary()
        return
    
    print(f"\n👤 Using test user ID: {user_id}")
    print("-" * 60)
    
    # Test AI features (high priority)
    test_ai_workout_generation(user_id)
    test_ai_meal_plan_generation(user_id)
    test_ask_interfitai_chat(user_id)
    
    # Test other features
    test_food_logging(user_id)
    test_step_tracking(user_id)
    test_food_image_analysis(user_id)
    test_stripe_subscription_checkout(user_id)
    
    # Print summary
    summary = print_summary()
    
    # Save detailed results
    with open('/app/backend_test_results.json', 'w') as f:
        json.dump({
            "summary": summary,
            "results": test_results,
            "test_timestamp": datetime.now().isoformat()
        }, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: /app/backend_test_results.json")

if __name__ == "__main__":
    main()