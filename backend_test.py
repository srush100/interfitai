#!/usr/bin/env python3
"""Backend Testing Script for InterFitAI - Foods to Avoid Feature"""

import asyncio
import httpx
import json
from datetime import datetime
import time
import re

# Backend URL from environment
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

class BackendTester:
    def __init__(self):
        self.test_results = []
        self.start_time = datetime.now()
        
    async def test_foods_to_avoid_feature(self):
        """Test the foods to avoid feature in meal plan generation"""
        print("🧪 TESTING: Meal Plan Generation with Foods to Avoid Feature")
        print("=" * 70)
        
        # Test parameters from review request
        test_data = {
            "user_id": "cbd82a69-3a37-48c2-88e8-0fe95081fa4b",
            "food_preferences": "none",
            "preferred_foods": "steak, eggs, potatoes", 
            "foods_to_avoid": "rice, pasta, bread"
        }
        
        print(f"📋 TEST PARAMETERS:")
        print(f"   User ID: {test_data['user_id']}")
        print(f"   Food Preferences: {test_data['food_preferences']}")
        print(f"   Preferred Foods: {test_data['preferred_foods']}")
        print(f"   Foods to Avoid: {test_data['foods_to_avoid']}")
        print()
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                print(f"🚀 Sending POST request to: {BACKEND_URL}/mealplans/generate")
                start_time = time.time()
                
                response = await client.post(
                    f"{BACKEND_URL}/mealplans/generate",
                    json=test_data
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                
                print(f"⏱️  Response Time: {response_time:.2f}s")
                print(f"📊 Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    await self.analyze_foods_to_avoid_compliance(data, test_data)
                    return True
                else:
                    print(f"❌ ERROR: {response.status_code}")
                    print(f"   Response: {response.text}")
                    return False
                    
            except Exception as e:
                print(f"❌ EXCEPTION: {str(e)}")
                return False
    
    async def analyze_foods_to_avoid_compliance(self, meal_plan_data, test_params):
        """Analyze the meal plan to verify foods to avoid compliance"""
        print("\n🔍 ANALYZING FOODS TO AVOID COMPLIANCE")
        print("=" * 50)
        
        avoided_foods = [food.strip().lower() for food in test_params['foods_to_avoid'].split(',')]
        preferred_foods = [food.strip().lower() for food in test_params['preferred_foods'].split(',')]
        
        print(f"FOODS TO AVOID: {', '.join(avoided_foods)}")
        print(f"PREFERRED FOODS: {', '.join(preferred_foods)}")
        print()
        
        meal_days = meal_plan_data.get('meal_days', [])
        
        total_violations = 0
        total_preferred_found = 0
        
        for day_data in meal_days:
            day_name = day_data.get('day', 'Unknown Day')
            meals = day_data.get('meals', [])
            
            print(f"{day_name} Meals - Ingredients check:")
            
            for meal in meals:
                meal_name = meal.get('name', 'Unknown Meal')
                meal_type = meal.get('meal_type', 'unknown')
                ingredients = meal.get('ingredients', [])
                
                # Join ingredients into a single string for analysis
                ingredients_text = ' '.join(ingredients).lower()
                
                # Check for avoided foods
                found_avoided = []
                for avoid_food in avoided_foods:
                    if avoid_food in ingredients_text:
                        found_avoided.append(avoid_food)
                        total_violations += 1
                
                # Check for preferred foods
                found_preferred = []
                for pref_food in preferred_foods:
                    if pref_food in ingredients_text:
                        found_preferred.append(pref_food)
                        total_preferred_found += 1
                
                # Display results
                violation_status = "❌ Y" if found_avoided else "✅ N"
                preferred_status = "✅ Y" if found_preferred else "❌ N"
                
                print(f"- {meal_type.title()}: {meal_name}")
                print(f"  Ingredients: {ingredients}")
                print(f"  Contains avoided foods? {violation_status} {found_avoided if found_avoided else ''}")
                print(f"  Contains preferred foods? {preferred_status} {found_preferred if found_preferred else ''}")
                print()
        
        # Final assessment
        print("COMPLIANCE SUMMARY:")
        print("=" * 30)
        
        if total_violations == 0:
            print("✅ FOODS TO AVOID COMPLIANCE: PASS")
            print("   No avoided foods (rice, pasta, bread) found in any meal")
        else:
            print(f"❌ FOODS TO AVOID COMPLIANCE: FAIL")
            print(f"   Found {total_violations} violations of avoided foods")
        
        if total_preferred_found > 0:
            print("✅ PREFERRED FOODS INCLUSION: PASS") 
            print(f"   Found {total_preferred_found} instances of preferred foods (steak, eggs, potatoes)")
        else:
            print("❌ PREFERRED FOODS INCLUSION: FAIL")
            print("   Preferred foods not found in meals")
        
        # Overall result
        overall_pass = total_violations == 0
        result_emoji = "✅ PASS" if overall_pass else "❌ FAIL"
        
        print(f"\nRESULT: {result_emoji}")
        
        if overall_pass:
            print("(no avoided foods found)")
        else:
            avoided_list = []
            for day_data in meal_days:
                for meal in day_data.get('meals', []):
                    ingredients_text = ' '.join(meal.get('ingredients', [])).lower()
                    for avoid_food in avoided_foods:
                        if avoid_food in ingredients_text:
                            avoided_list.append(avoid_food)
            print(f"(avoided foods found: {list(set(avoided_list))})")
        
        return overall_pass

    async def run_all_tests(self):
        """Run all backend tests"""
        print(f"🚀 Starting Backend Testing - {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Backend URL: {BACKEND_URL}")
        print()
        
        # Test the foods to avoid feature
        success = await self.test_foods_to_avoid_feature()
        
        # Summary
        print("\n" + "=" * 70)
        print("🏁 TESTING COMPLETE")
        print("=" * 70)
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        print(f"⏱️  Total Duration: {duration:.2f}s")
        print(f"📊 Test Result: {'✅ PASS' if success else '❌ FAIL'}")
        
        if not success:
            print("⚠️  Foods to avoid feature is not working correctly")
        else:
            print("✨ Foods to avoid feature working perfectly!")

async def main():
    """Main test execution"""
    tester = BackendTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())