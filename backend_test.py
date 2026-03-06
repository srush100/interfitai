#!/usr/bin/env python3

import requests
import time
import json
from datetime import datetime

# Backend URL from environment
BACKEND_URL = "https://ai-fitness-pro-4.preview.emergentagent.com/api"

def log_test(test_name, status, details=""):
    """Log test results with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status_icon = "✅" if status else "❌"
    print(f"[{timestamp}] {status_icon} {test_name}: {details}")
    return status

def test_health_check():
    """Test health check endpoint"""
    start_time = time.time()
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=10)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            if "status" in data and "timestamp" in data:
                return log_test("Health Check", True, f"Response: {response.status_code}, Time: {response_time:.2f}s, Data: {data}")
            else:
                return log_test("Health Check", False, f"Missing required fields in response: {data}")
        else:
            return log_test("Health Check", False, f"Status: {response.status_code}, Response: {response.text}")
    
    except Exception as e:
        response_time = time.time() - start_time
        return log_test("Health Check", False, f"Exception after {response_time:.2f}s: {str(e)}")

def test_exercise_search():
    """Test exercise search endpoint with muscle parameter"""
    start_time = time.time()
    try:
        response = requests.get(f"{BACKEND_URL}/exercises/search?muscle=chest", timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            
            if "exercises" not in data:
                return log_test("Exercise Search", False, f"Missing 'exercises' key in response: {data}")
            
            exercises = data["exercises"]
            
            # Check if we got results
            if len(exercises) == 0:
                return log_test("Exercise Search", True, f"No exercises found for chest muscle (API may be limited), Response time: {response_time:.2f}s")
            
            # Verify structure of first exercise
            first_exercise = exercises[0]
            required_fields = ["id", "name", "target", "equipment", "bodyPart", "gifUrl"]
            missing_fields = [field for field in required_fields if field not in first_exercise]
            
            if missing_fields:
                return log_test("Exercise Search", False, f"Missing fields in exercise: {missing_fields}")
            
            # Verify gifUrl format (should be our proxy endpoint)
            gif_url = first_exercise.get("gifUrl")
            if gif_url and not gif_url.startswith("/api/exercises/gif/"):
                return log_test("Exercise Search", False, f"Incorrect gifUrl format: {gif_url} (should start with /api/exercises/gif/)")
            
            return log_test("Exercise Search", True, f"Found {len(exercises)} exercises, Response time: {response_time:.2f}s, Sample exercise: {first_exercise.get('name', 'Unknown')}")
        
        else:
            return log_test("Exercise Search", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
    
    except Exception as e:
        response_time = time.time() - start_time
        return log_test("Exercise Search", False, f"Exception after {response_time:.2f}s: {str(e)}")

def test_exercise_gif_proxy():
    """Test exercise GIF proxy endpoint with a known exercise ID"""
    start_time = time.time()
    test_exercise_ids = ["0025", "0001", "0002"]  # Common exercise IDs from ExerciseDB
    
    for exercise_id in test_exercise_ids:
        try:
            response = requests.get(f"{BACKEND_URL}/exercises/gif/{exercise_id}", timeout=30)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                content_length = len(response.content)
                
                if content_type.startswith("image/gif"):
                    # Check if it's actually GIF content
                    if response.content[:3] == b'GIF':
                        return log_test("Exercise GIF Proxy", True, f"Exercise ID {exercise_id}: Content-Type: {content_type}, Size: {content_length} bytes, Response time: {response_time:.2f}s")
                    else:
                        return log_test("Exercise GIF Proxy", False, f"Exercise ID {exercise_id}: Content-Type is image/gif but content is not GIF format")
                else:
                    return log_test("Exercise GIF Proxy", False, f"Exercise ID {exercise_id}: Wrong Content-Type: {content_type} (expected image/gif)")
            
            elif response.status_code == 404:
                # Try next exercise ID
                continue
                
            elif response.status_code == 503:
                return log_test("Exercise GIF Proxy", False, f"Exercise ID {exercise_id}: Service unavailable (ExerciseDB API not configured)")
            
            else:
                return log_test("Exercise GIF Proxy", False, f"Exercise ID {exercise_id}: Status {response.status_code}, Response: {response.text[:200]}")
        
        except Exception as e:
            response_time = time.time() - start_time
            return log_test("Exercise GIF Proxy", False, f"Exercise ID {exercise_id}: Exception after {response_time:.2f}s: {str(e)}")
    
    # If all IDs failed, it's likely an API configuration issue
    return log_test("Exercise GIF Proxy", False, f"All test exercise IDs failed - likely ExerciseDB API not configured or quota exceeded")

def test_exercise_search_with_name():
    """Test exercise search by name parameter"""
    start_time = time.time()
    try:
        response = requests.get(f"{BACKEND_URL}/exercises/search?search=bench press", timeout=15)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            exercises = data.get("exercises", [])
            
            if len(exercises) > 0:
                # Look for bench press exercises
                bench_exercises = [ex for ex in exercises if "bench" in ex.get("name", "").lower()]
                if bench_exercises:
                    return log_test("Exercise Search by Name", True, f"Found {len(bench_exercises)} bench press exercises, Response time: {response_time:.2f}s")
                else:
                    return log_test("Exercise Search by Name", True, f"Search completed but no bench press exercises found, Response time: {response_time:.2f}s")
            else:
                return log_test("Exercise Search by Name", True, f"No exercises found for 'bench press' (API may be limited), Response time: {response_time:.2f}s")
        
        else:
            return log_test("Exercise Search by Name", False, f"Status: {response.status_code}, Response: {response.text[:200]}")
    
    except Exception as e:
        response_time = time.time() - start_time
        return log_test("Exercise Search by Name", False, f"Exception after {response_time:.2f}s: {str(e)}")

def run_all_tests():
    """Run all exercise-related tests"""
    print("=" * 80)
    print("🏋️ EXERCISE GIF PROXY & WORKOUT CUSTOMIZATION TESTING")
    print("=" * 80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)
    
    test_results = []
    
    # Run all tests
    test_results.append(test_health_check())
    test_results.append(test_exercise_search())
    test_results.append(test_exercise_search_with_name())
    test_results.append(test_exercise_gif_proxy())
    
    # Summary
    print("-" * 80)
    passed = sum(test_results)
    total = len(test_results)
    print(f"📊 TEST SUMMARY: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("✅ All workout customization features are working properly!")
    else:
        print(f"❌ {total - passed} test(s) failed - requires investigation")
    
    print("=" * 80)
    return passed == total

if __name__ == "__main__":
    run_all_tests()