#!/usr/bin/env python3
"""
Backend Testing Script for InterFitAI
Tests specific endpoints as requested in the review request.
"""

import requests
import json
from datetime import datetime
import sys
import traceback

# Base URL for the backend API
BASE_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

def test_health_check():
    """Test the health check endpoint"""
    print("🏥 Testing Health Check Endpoint...")
    
    try:
        start_time = datetime.now()
        response = requests.get(f"{BASE_URL}/health", timeout=30)
        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response Time: {response_time:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {data}")
            print("  ✅ Health check endpoint working correctly")
            return True
        else:
            print(f"  ❌ Health check failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ Health check failed with error: {str(e)}")
        return False

def test_subscription_check():
    """Test the subscription check endpoint with specific user_id"""
    print("💳 Testing Subscription Check Endpoint...")
    
    # Test user ID from review request
    user_id = "d704bac8-fa54-4d5b-b984-cc17393c1244"
    
    try:
        start_time = datetime.now()
        response = requests.get(f"{BASE_URL}/subscription/check/{user_id}", timeout=30)
        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        
        print(f"  User ID: {user_id}")
        print(f"  Status Code: {response.status_code}")
        print(f"  Response Time: {response_time:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
            
            # Validate response structure
            required_fields = ['has_access', 'reason']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                print(f"  ❌ Missing required fields: {missing_fields}")
                return False
            
            print(f"  Has Access: {data['has_access']}")
            print(f"  Reason: {data['reason']}")
            print("  ✅ Subscription check endpoint working correctly")
            return True
        else:
            print(f"  ❌ Subscription check failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ Subscription check failed with error: {str(e)}")
        return False

def test_food_logging():
    """Test the manual food logging endpoint"""
    print("🍽️ Testing Food Logging Endpoint...")
    
    # Test data from review request
    food_data = {
        "user_id": "d704bac8-fa54-4d5b-b984-cc17393c1244",
        "food_name": "Test Manual Entry", 
        "serving_size": "1 serving",
        "calories": 300,
        "protein": 25.0,
        "carbs": 30.0,
        "fats": 10.0,
        "fiber": 5.0,
        "sugar": 8.0,
        "sodium": 400.0,
        "meal_type": "lunch",
        "logged_date": "2026-03-05"
    }
    
    try:
        start_time = datetime.now()
        response = requests.post(
            f"{BASE_URL}/food/log", 
            json=food_data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        
        print(f"  Status Code: {response.status_code}")
        print(f"  Response Time: {response_time:.2f}s")
        print(f"  Request Data: {json.dumps(food_data, indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response: {json.dumps(data, indent=2)}")
            
            # Validate response contains expected data
            if (data.get('food_name') == food_data['food_name'] and
                data.get('calories') == food_data['calories'] and
                data.get('protein') == food_data['protein']):
                print("  ✅ Food logging endpoint working correctly")
                
                # Test retrieval to verify it was saved
                print("  🔍 Testing food log retrieval...")
                return test_food_log_retrieval(food_data['user_id'], food_data['logged_date'])
            else:
                print("  ❌ Response data doesn't match request data")
                return False
        else:
            print(f"  ❌ Food logging failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ Food logging failed with error: {str(e)}")
        traceback.print_exc()
        return False

def test_food_log_retrieval(user_id, date):
    """Test retrieving food logs to verify logging worked"""
    try:
        response = requests.get(f"{BASE_URL}/food/logs/{user_id}?date={date}", timeout=30)
        
        if response.status_code == 200:
            logs = response.json()
            if logs and len(logs) > 0:
                # Check if our test entry exists
                test_entry = next((log for log in logs if log.get('food_name') == 'Test Manual Entry'), None)
                if test_entry:
                    print(f"    ✅ Food entry successfully retrieved: {test_entry['food_name']}")
                    return True
                else:
                    print("    ⚠️ Test entry not found in retrieved logs")
                    return False
            else:
                print("    ❌ No food logs retrieved")
                return False
        else:
            print(f"    ❌ Food log retrieval failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"    ❌ Food log retrieval failed: {str(e)}")
        return False

def main():
    """Run all backend tests"""
    print("🚀 Starting Backend API Tests for InterFitAI")
    print(f"🌐 Testing against: {BASE_URL}")
    print("=" * 60)
    
    results = []
    
    # Test 1: Health Check
    health_result = test_health_check()
    results.append(("Health Check", health_result))
    print()
    
    # Test 2: Subscription Check
    subscription_result = test_subscription_check()
    results.append(("Subscription Check", subscription_result))
    print()
    
    # Test 3: Food Logging
    food_log_result = test_food_logging()
    results.append(("Food Logging", food_log_result))
    print()
    
    # Summary
    print("=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print("=" * 60)
    print(f"📈 Total: {len(results)} tests | ✅ Passed: {passed} | ❌ Failed: {failed}")
    
    if failed > 0:
        print("\n⚠️  Some tests failed. Please check the detailed output above.")
        sys.exit(1)
    else:
        print("\n🎉 All tests passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()