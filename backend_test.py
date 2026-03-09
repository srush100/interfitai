#!/usr/bin/env python3

import requests
import json
import time

# Backend URL from frontend/.env
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

def test_review_request_format():
    """
    Test using the exact format requested in the review request
    """
    print("🧪 TESTING REVIEW REQUEST FORMAT")
    print("=" * 60)
    
    # Exact test data from review request
    user_id = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"
    preferred_foods = "steak, eggs, sweet potato"
    
    payload = {
        "user_id": user_id,
        "food_preferences": "none",
        "preferred_foods": preferred_foods
    }
    
    print(f"Testing POST /api/mealplans/generate")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        start_time = time.time()
        response = requests.post(
            f"{BACKEND_URL}/mealplans/generate",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        response_time = time.time() - start_time
        
        print(f"Response Time: {response_time:.2f}s")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ ERROR: {response.text}")
            return False
            
        meal_plan = response.json()
        day_1 = meal_plan["meal_days"][0]
        meals = day_1["meals"]
        
        print()
        print("PREFERRED FOODS TEST: steak, eggs, sweet potato")
        print("Day 1 Meals:")
        
        # Check each meal according to review format
        breakfast = next((m for m in meals if m.get("meal_type") == "breakfast"), None)
        lunch = next((m for m in meals if m.get("meal_type") == "lunch"), None)  
        dinner = next((m for m in meals if m.get("meal_type") == "dinner"), None)
        
        def contains_food(meal, food_keywords):
            if not meal:
                return False
            meal_text = (meal.get("name", "") + " " + " ".join(meal.get("ingredients", []))).lower()
            return any(keyword.lower() in meal_text for keyword in food_keywords)
        
        # Check for eggs in breakfast
        breakfast_has_eggs = contains_food(breakfast, ["egg"])
        lunch_has_steak_or_potato = contains_food(lunch, ["steak", "beef", "sweet potato"])  
        dinner_has_steak_or_potato = contains_food(dinner, ["steak", "beef", "sweet potato"])
        
        print(f"- Breakfast: {breakfast.get('name', 'N/A') if breakfast else 'N/A'} - Contains eggs? {'Y' if breakfast_has_eggs else 'N'}")
        print(f"- Lunch: {lunch.get('name', 'N/A') if lunch else 'N/A'} - Contains steak/sweet potato? {'Y' if lunch_has_steak_or_potato else 'N'}")
        print(f"- Dinner: {dinner.get('name', 'N/A') if dinner else 'N/A'} - Contains steak/sweet potato? {'Y' if dinner_has_steak_or_potato else 'N'}")
        print()
        
        # Overall assessment
        all_foods_present = breakfast_has_eggs and lunch_has_steak_or_potato and dinner_has_steak_or_potato
        
        if all_foods_present:
            print("Did the AI respect the preferred foods? ✅ YES")
            success = True
        else:
            print("Did the AI respect the preferred foods? ❌ NO")
            success = False
        
        print()
        print("DETAILED VERIFICATION:")
        for meal in meals:
            meal_type = meal.get("meal_type", "").title()
            name = meal.get("name", "")
            ingredients = meal.get("ingredients", [])[:3]  # First 3 ingredients
            print(f"{meal_type}: {name}")
            print(f"  Ingredients: {', '.join(ingredients)}")
        
        return success
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run the review request format test"""
    print("🚀 PREFERRED FOODS REVIEW REQUEST TEST")
    print("Testing exact scenario from review request")
    print()
    
    success = test_review_request_format()
    
    print()
    print("=" * 60)
    if success:
        print("✅ REVIEW REQUEST TEST: PASSED")
        print("The AI successfully respected preferred foods as requested.")
    else:
        print("❌ REVIEW REQUEST TEST: FAILED")
        print("The AI did not meet the expected criteria.")

if __name__ == "__main__":
    main()