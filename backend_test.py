#!/usr/bin/env python3
"""
Backend API Testing for InterFitAI - Calorie Adjustment Feature

This script tests the calorie adjustment feature specifically requested:
1. GET /api/profile/{user_id} - Verify calorie_adjustment field exists
2. PUT /api/profile/{user_id} - Test updating calorie_adjustment 
3. Multiple scenarios: positive adjustment, negative adjustment, reset to zero
"""

import httpx
import json
import asyncio
import time
from datetime import datetime

# Configuration
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"
TEST_USER_ID = "cbd82a69-3a37-48c2-88e8-0fe95081fa4b"  # Specified in review request

class CalorieAdjustmentTester:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.results = []
        
    def log_result(self, test_name: str, success: bool, details: str, response_time: float = 0):
        """Log test result with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append({
            "timestamp": timestamp,
            "test": test_name,
            "status": status,
            "details": details,
            "response_time": f"{response_time:.2f}s" if response_time > 0 else "N/A"
        })
        print(f"[{timestamp}] {status}: {test_name}")
        print(f"    Details: {details}")
        if response_time > 0:
            print(f"    Response Time: {response_time:.2f}s")
        print()

    async def test_get_profile_calorie_adjustment(self):
        """Test Case 1: GET /api/profile/{user_id} - Verify calorie_adjustment field exists"""
        try:
            start_time = time.time()
            response = await self.client.get(f"{BACKEND_URL}/profile/{TEST_USER_ID}")
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                if "calorie_adjustment" in data:
                    calorie_adjustment = data["calorie_adjustment"]
                    self.log_result(
                        "GET Profile - Calorie Adjustment Field Check",
                        True,
                        f"Profile contains calorie_adjustment field with value: {calorie_adjustment}. Profile ID: {data.get('id', 'N/A')}, Name: {data.get('name', 'N/A')}",
                        response_time
                    )
                    return True, calorie_adjustment
                else:
                    self.log_result(
                        "GET Profile - Calorie Adjustment Field Check",
                        False,
                        f"Profile missing calorie_adjustment field. Available fields: {list(data.keys())}",
                        response_time
                    )
                    return False, None
            else:
                self.log_result(
                    "GET Profile - Calorie Adjustment Field Check",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                    response_time
                )
                return False, None
                
        except Exception as e:
            self.log_result(
                "GET Profile - Calorie Adjustment Field Check",
                False,
                f"Exception: {str(e)}"
            )
            return False, None

    async def test_update_calorie_adjustment(self, adjustment_value: int, test_description: str):
        """Test updating calorie adjustment to a specific value"""
        try:
            start_time = time.time()
            response = await self.client.put(
                f"{BACKEND_URL}/profile/{TEST_USER_ID}",
                json={"calorie_adjustment": adjustment_value}
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                returned_adjustment = data.get("calorie_adjustment")
                if returned_adjustment == adjustment_value:
                    self.log_result(
                        f"PUT Profile - {test_description}",
                        True,
                        f"Successfully updated calorie_adjustment to {adjustment_value}. Profile updated_at: {data.get('updated_at', 'N/A')}",
                        response_time
                    )
                    return True
                else:
                    self.log_result(
                        f"PUT Profile - {test_description}",
                        False,
                        f"Expected calorie_adjustment {adjustment_value}, got {returned_adjustment}",
                        response_time
                    )
                    return False
            else:
                self.log_result(
                    f"PUT Profile - {test_description}",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                    response_time
                )
                return False
                
        except Exception as e:
            self.log_result(
                f"PUT Profile - {test_description}",
                False,
                f"Exception: {str(e)}"
            )
            return False

    async def test_verify_adjustment_persisted(self, expected_value: int, test_description: str):
        """Verify calorie adjustment persisted after update"""
        try:
            start_time = time.time()
            response = await self.client.get(f"{BACKEND_URL}/profile/{TEST_USER_ID}")
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                actual_value = data.get("calorie_adjustment")
                if actual_value == expected_value:
                    self.log_result(
                        f"GET Profile - {test_description}",
                        True,
                        f"Calorie adjustment correctly persisted as {expected_value}",
                        response_time
                    )
                    return True
                else:
                    self.log_result(
                        f"GET Profile - {test_description}",
                        False,
                        f"Expected calorie_adjustment {expected_value}, got {actual_value}",
                        response_time
                    )
                    return False
            else:
                self.log_result(
                    f"GET Profile - {test_description}",
                    False,
                    f"HTTP {response.status_code}: {response.text}",
                    response_time
                )
                return False
                
        except Exception as e:
            self.log_result(
                f"GET Profile - {test_description}",
                False,
                f"Exception: {str(e)}"
            )
            return False

    async def run_calorie_adjustment_tests(self):
        """Run all calorie adjustment tests as specified in review request"""
        print("=" * 80)
        print("🧪 CALORIE ADJUSTMENT FEATURE TESTING")
        print("=" * 80)
        print(f"Backend URL: {BACKEND_URL}")
        print(f"Test User ID: {TEST_USER_ID}")
        print(f"Test Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Test Case 1: GET profile and verify calorie_adjustment field
        print("📋 TEST CASE 1: Verify calorie_adjustment field exists")
        success1, initial_value = await self.test_get_profile_calorie_adjustment()
        
        if not success1:
            print("⚠️ Cannot continue testing - profile not accessible")
            return False
        
        # Test Case 2: Update to +200 calories
        print("📋 TEST CASE 2: Update calorie adjustment to +200")
        success2 = await self.test_update_calorie_adjustment(200, "Set Positive Adjustment (+200)")
        
        # Test Case 3: Verify +200 persisted
        print("📋 TEST CASE 3: Verify +200 adjustment persisted")
        success3 = await self.test_verify_adjustment_persisted(200, "Verify +200 Persisted")
        
        # Test Case 4: Update to -150 calories 
        print("📋 TEST CASE 4: Update calorie adjustment to -150")
        success4 = await self.test_update_calorie_adjustment(-150, "Set Negative Adjustment (-150)")
        
        # Test Case 5: Reset to 0 calories
        print("📋 TEST CASE 5: Reset calorie adjustment to 0")
        success5 = await self.test_update_calorie_adjustment(0, "Reset Adjustment to Zero")
        
        # Summary
        total_tests = 5
        passed_tests = sum([success1, success2, success3, success4, success5])
        
        print("=" * 80)
        print("📊 CALORIE ADJUSTMENT TESTING SUMMARY")
        print("=" * 80)
        print(f"✅ Passed: {passed_tests}/{total_tests} tests")
        print(f"❌ Failed: {total_tests - passed_tests}/{total_tests} tests")
        print(f"🎯 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print()
        
        # Print detailed results
        print("📋 DETAILED TEST RESULTS:")
        for result in self.results:
            print(f"[{result['timestamp']}] {result['status']}: {result['test']}")
            print(f"    📝 {result['details']}")
            if result['response_time'] != "N/A":
                print(f"    ⏱️ {result['response_time']}")
        
        print("=" * 80)
        
        return passed_tests == total_tests

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

async def main():
    """Main test execution function"""
    tester = CalorieAdjustmentTester()
    
    try:
        success = await tester.run_calorie_adjustment_tests()
        if success:
            print("🎉 ALL CALORIE ADJUSTMENT TESTS PASSED!")
        else:
            print("⚠️ SOME TESTS FAILED - Review results above")
        
    except Exception as e:
        print(f"💥 TESTING ERROR: {e}")
    finally:
        await tester.close()

if __name__ == "__main__":
    asyncio.run(main())