#!/usr/bin/env python3

import requests
import json
import time

BACKEND_URL = "https://nutrition-debug-1.preview.emergentagent.com/api"

def test_model_availability():
    """Test different Claude model names to see which ones work"""
    
    models_to_test = [
        "claude-haiku-4-5-20251001",  # New replacement model
        "claude-3-5-haiku-20241022",  # Original model (deprecated)  
        "claude-3-haiku-20240307",    # Claude 3 Haiku (older)
        "claude-sonnet-4-6"           # Current working model
    ]
    
    test_payload = {
        "user_id": "d704bac8-fa54-4d5b-b984-cc17393c1244",
        "goal": "muscle_building",
        "focus_areas": ["chest"],
        "equipment": ["dumbbell"],
        "injuries": "",
        "days_per_week": 2,
        "duration_minutes": 30
    }
    
    for model in models_to_test:
        print(f"\n🧪 Testing model: {model}")
        print("=" * 50)
        
        # We can't directly test the model since it's hardcoded in server.py
        # But we can test the working endpoint first
        if model == "claude-sonnet-4-6":
            print("Testing known working model (claude-sonnet-4-6)...")
            try:
                start_time = time.time()
                
                # For claude-sonnet-4-6, we need to test a different endpoint that doesn't use fast model
                # Let's test the chat endpoint which likely uses the regular model
                chat_payload = {
                    "user_id": "d704bac8-fa54-4d5b-b984-cc17393c1244",
                    "message": "What is a good chest exercise?",
                    "save": False
                }
                
                response = requests.post(
                    f"{BACKEND_URL}/chat", 
                    json=chat_payload, 
                    timeout=30,
                    headers={"Content-Type": "application/json"}
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                print(f"Status Code: {response.status_code}")
                print(f"Response Time: {duration:.2f} seconds")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Model {model} is working!")
                    print(f"Response preview: {result.get('response', '')[:100]}...")
                else:
                    print(f"❌ Model {model} failed")
                    print(f"Response: {response.text}")
                    
            except Exception as e:
                print(f"❌ Model {model} error: {str(e)}")
        else:
            print(f"Model {model} - Cannot test directly (hardcoded in backend)")
            print("This would need to be updated in server.py to test")

if __name__ == "__main__":
    print("🔍 TESTING CLAUDE MODEL AVAILABILITY")
    print("=" * 60)
    test_model_availability()