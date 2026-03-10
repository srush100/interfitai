#!/usr/bin/env python3

import asyncio
import httpx
import json
from datetime import datetime

# Configuration
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"

def log_test(message):
    """Log test messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

async def verify_individual_meal_accuracy():
    """Verify that individual meal macros add up to the day totals"""
    log_test("🔍 INDIVIDUAL MEAL MACRO VERIFICATION")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test with steak, rice, eggs
        test_request = {
            "user_id": TEST_USER_ID,
            "food_preferences": "none", 
            "preferred_foods": "steak, rice, eggs"
        }
        
        response = await client.post(f"{BACKEND_URL}/mealplans/generate", json=test_request)
        
        if response.status_code == 200:
            meal_plan = response.json()
            log_test(f"✅ Generated: '{meal_plan.get('name')}'")
            
            for i, day in enumerate(meal_plan.get('meal_days', []), 1):
                day_name = f"Day {i}"
                day_total_cal = day.get('total_calories', 0)
                day_total_pro = day.get('total_protein', 0)
                day_total_carb = day.get('total_carbs', 0)
                day_total_fat = day.get('total_fats', 0)
                
                log_test(f"\n🔎 {day_name} BREAKDOWN:")
                log_test(f"Day Total: {day_total_cal} cal, {day_total_pro}g P, {day_total_carb}g C, {day_total_fat}g F")
                
                # Sum individual meals
                meals = day.get('meals', [])
                calc_cal = sum(meal.get('calories', 0) for meal in meals)
                calc_pro = sum(meal.get('protein', 0) for meal in meals)
                calc_carb = sum(meal.get('carbs', 0) for meal in meals)
                calc_fat = sum(meal.get('fats', 0) for meal in meals)
                
                log_test(f"Meals Sum: {calc_cal} cal, {calc_pro}g P, {calc_carb}g C, {calc_fat}g F")
                
                # Check if sums match day totals
                cal_match = calc_cal == day_total_cal
                pro_match = calc_pro == day_total_pro
                carb_match = calc_carb == day_total_carb
                fat_match = calc_fat == day_total_fat
                
                if cal_match and pro_match and carb_match and fat_match:
                    log_test("✅ Individual meals sum correctly to day total")
                else:
                    log_test(f"❌ Mismatch - Diff: {calc_cal-day_total_cal} cal, {calc_pro-day_total_pro}g P, {calc_carb-day_total_carb}g C, {calc_fat-day_total_fat}g F")
                
                # Show each meal
                for j, meal in enumerate(meals):
                    meal_type = meal.get('meal_type', 'unknown')
                    meal_name = meal.get('name', 'Unknown')
                    meal_cal = meal.get('calories', 0)
                    meal_pro = meal.get('protein', 0)
                    meal_carb = meal.get('carbs', 0)
                    meal_fat = meal.get('fats', 0)
                    ingredients = meal.get('ingredients', [])
                    
                    log_test(f"  {meal_type.title()}: {meal_name}")
                    log_test(f"    Macros: {meal_cal} cal, {meal_pro}g P, {meal_carb}g C, {meal_fat}g F")
                    
                    # Show ingredients with specific amounts
                    if ingredients:
                        log_test(f"    Ingredients: {', '.join(ingredients[:3])}" + ("..." if len(ingredients) > 3 else ""))
            
            return True
        else:
            log_test(f"❌ Request failed: {response.status_code}")
            return False

async def main():
    """Main verification"""
    log_test("🔍 Starting detailed meal plan verification")
    
    try:
        success = await verify_individual_meal_accuracy()
        
        if success:
            log_test("\n✅ Detailed verification completed")
        else:
            log_test("\n❌ Verification failed")
            
    except Exception as e:
        log_test(f"💥 ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())