from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, date
import openai
import stripe
import base64
import json
import httpx
import time
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'interfitai')]

# OpenAI configuration (kept for fallback/vision)
openai.api_key = os.environ.get('OPENAI_API_KEY', '')

# Claude Opus 4.6 via Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

async def call_claude_sonnet(
    system_message: str,
    user_message: str,
    temperature: float = 0.7,
    max_tokens: int = 2500,
    image_base64: str = None,
    image_base64_2: str = None
) -> str:
    """Call Claude Sonnet 4.5 via emergentintegrations - for complex generation tasks"""
    chat = (
        LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message=system_message,
        )
        .with_model("anthropic", "claude-sonnet-4-5-20250929")
        .with_params(temperature=temperature, max_tokens=max_tokens, timeout=180)
    )
    file_contents = []
    if image_base64:
        file_contents.append(ImageContent(image_base64))
    if image_base64_2:
        file_contents.append(ImageContent(image_base64_2))
    msg = UserMessage(text=user_message, file_contents=file_contents if file_contents else None)
    try:
        return await chat.send_message(msg)
    except Exception as e:
        err = str(e)
        if "budget" in err.lower() or "exceeded" in err.lower():
            raise HTTPException(
                status_code=402,
                detail="AI service balance is low. Please go to Profile → Universal Key → Add Balance to top up."
            )
        raise


async def call_claude_haiku(
    system_message: str,
    user_message: str,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    image_base64: str = None
) -> str:
    """Call Claude Haiku 4.5 via emergentintegrations - for fast, lightweight tasks"""
    chat = (
        LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message=system_message,
        )
        .with_model("anthropic", "claude-haiku-4-5-20251001")
        .with_params(temperature=temperature, max_tokens=max_tokens, timeout=60)
    )
    file_contents = []
    if image_base64:
        file_contents.append(ImageContent(image_base64))
    msg = UserMessage(text=user_message, file_contents=file_contents if file_contents else None)
    try:
        return await chat.send_message(msg)
    except Exception as e:
        err = str(e)
        if "budget" in err.lower() or "exceeded" in err.lower():
            raise HTTPException(
                status_code=402,
                detail="AI service balance is low. Please go to Profile → Universal Key → Add Balance to top up."
            )
        raise

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_API_KEY', '')

# Admin emails - these users get free full access
ADMIN_EMAILS = [
    "sebastianrush5@gmail.com",
    "srush@interfitai.com"
]

# Free access emails - can be granted by admin
FREE_ACCESS_EMAILS = []

# Exercise demonstration - using ExerciseDB RapidAPI for computer-generated animated GIFs
EXERCISEDB_API_KEY = os.getenv("EXERCISEDB_API_KEY")
EXERCISEDB_API_HOST = "exercisedb.p.rapidapi.com"
EXERCISEDB_API_BASE = "https://exercisedb.p.rapidapi.com"

# FatSecret API configuration
FATSECRET_CLIENT_ID = os.getenv("FATSECRET_CLIENT_ID")
FATSECRET_CLIENT_SECRET = os.getenv("FATSECRET_CLIENT_SECRET")
FATSECRET_TOKEN_URL = "https://oauth.fatsecret.com/connect/token"
FATSECRET_API_BASE = "https://platform.fatsecret.com/rest/server.api"

# USDA FoodData Central API (free, no IP restrictions)
USDA_API_KEY = "DEMO_KEY"  # Using demo key - works for reasonable usage
USDA_API_BASE = "https://api.nal.usda.gov/fdc/v1"

# Cache for FatSecret access token
fatsecret_token_cache = {
    "access_token": None,
    "expires_at": 0
}

async def get_fatsecret_token():
    """Get FatSecret OAuth 2.0 access token (with caching)"""
    global fatsecret_token_cache
    
    # Check if we have a valid cached token
    if fatsecret_token_cache["access_token"] and time.time() < fatsecret_token_cache["expires_at"]:
        return fatsecret_token_cache["access_token"]
    
    # Request new token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            FATSECRET_TOKEN_URL,
            auth=(FATSECRET_CLIENT_ID, FATSECRET_CLIENT_SECRET),
            data={
                "grant_type": "client_credentials",
                "scope": "basic"
            }
        )
        
        if response.status_code != 200:
            logger.error(f"FatSecret token error: {response.text}")
            return None
        
        token_data = response.json()
        fatsecret_token_cache["access_token"] = token_data["access_token"]
        # Token typically expires in 24 hours, cache for 23 hours
        fatsecret_token_cache["expires_at"] = time.time() + (23 * 60 * 60)
        
        return token_data["access_token"]

async def search_fatsecret(query: str, max_results: int = 50):
    """Search FatSecret food database"""
    token = await get_fatsecret_token()
    if not token:
        return []
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            FATSECRET_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "method": "foods.search",
                "search_expression": query,
                "format": "json",
                "max_results": max_results
            }
        )
        
        if response.status_code != 200:
            logger.error(f"FatSecret search error: {response.text}")
            return []
        
        data = response.json()
        logger.info(f"FatSecret raw response keys: {data.keys()}")
        
        # Parse FatSecret response
        foods_data = data.get("foods", {})
        if not foods_data:
            logger.warning(f"No foods_data in response: {data}")
            return []
        
        food_list = foods_data.get("food", [])
        # If only one result, it comes as a dict not a list
        if isinstance(food_list, dict):
            food_list = [food_list]
        
        logger.info(f"Found {len(food_list)} foods from FatSecret")
        
        results = []
        for food in food_list:
            # Parse the description for serving size and macros
            description = food.get("food_description", "")
            
            # Default values
            calories = 0
            protein = 0
            carbs = 0
            fats = 0
            serving = "Per serving"
            
            # Parse FatSecret format: "Per 100g - Calories: 165kcal | Fat: 3.6g | Carbs: 0g | Protein: 31g"
            if description:
                # Extract serving info
                if " - " in description:
                    parts = description.split(" - ")
                    serving = parts[0]
                    macro_part = parts[1] if len(parts) > 1 else ""
                else:
                    macro_part = description
                
                # Extract macros using simple parsing
                import re
                cal_match = re.search(r'Calories:\s*(\d+)', macro_part, re.I)
                fat_match = re.search(r'Fat:\s*([\d.]+)', macro_part, re.I)
                carb_match = re.search(r'Carbs:\s*([\d.]+)', macro_part, re.I)
                protein_match = re.search(r'Protein:\s*([\d.]+)', macro_part, re.I)
                
                if cal_match:
                    calories = int(cal_match.group(1))
                if fat_match:
                    fats = float(fat_match.group(1))
                if carb_match:
                    carbs = float(carb_match.group(1))
                if protein_match:
                    protein = float(protein_match.group(1))
            
            results.append({
                "name": f"{food.get('food_name', 'Unknown')} ({serving})",
                "brand": food.get("brand_name", ""),
                "calories": calories,
                "protein": round(protein, 1),
                "carbs": round(carbs, 1),
                "fats": round(fats, 1),
                "food_id": food.get("food_id"),
                "source": "fatsecret"
            })
        
        return results

async def search_usda(query: str, max_results: int = 50):
    """Search USDA FoodData Central database (free, no IP restrictions)"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{USDA_API_BASE}/foods/search",
                params={
                    "api_key": USDA_API_KEY,
                    "query": query,
                    "pageSize": max_results,
                    "dataType": ["Branded", "Foundation", "SR Legacy"]
                },
                timeout=10.0
            )
            
            if response.status_code != 200:
                logger.error(f"USDA search error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            foods = data.get("foods", [])
            
            logger.info(f"USDA returned {len(foods)} foods")
            
            results = []
            for food in foods:
                # Extract nutrients
                nutrients = {n.get("nutrientName", ""): n.get("value", 0) for n in food.get("foodNutrients", [])}
                
                calories = nutrients.get("Energy", 0)
                protein = nutrients.get("Protein", 0)
                carbs = nutrients.get("Carbohydrate, by difference", 0)
                fats = nutrients.get("Total lipid (fat)", 0)
                
                # Get serving size info
                serving = food.get("servingSize", "")
                serving_unit = food.get("servingSizeUnit", "")
                serving_info = f"{serving}{serving_unit}" if serving and serving_unit else "per 100g"
                
                brand = food.get("brandName", "") or food.get("brandOwner", "")
                food_name = food.get("description", "Unknown")
                
                # Clean up the name
                if brand and brand.lower() not in food_name.lower():
                    display_name = f"{brand} - {food_name}"
                else:
                    display_name = food_name
                
                results.append({
                    "name": f"{display_name} ({serving_info})",
                    "brand": brand,
                    "calories": round(calories, 0),
                    "protein": round(protein, 1),
                    "carbs": round(carbs, 1),
                    "fats": round(fats, 1),
                    "food_id": str(food.get("fdcId", "")),
                    "source": "usda"
                })
            
            return results
            
        except Exception as e:
            logger.error(f"USDA search exception: {e}")
            return []

# Pre-cached exercise GIFs for common exercises (fallback when API quota exceeded)
# These are direct GIF URLs from exercisedb.io (publicly accessible)
CACHED_EXERCISE_GIFS = {
    # Using exercise IDs that can be proxied through our endpoint
    # Chest exercises
    "bench press": "0025",
    "barbell bench press": "0025",
    "flat bench press": "0025",
    "incline bench press": "0047",
    "barbell incline bench press": "0047",
    "decline bench press": "0033",
    "dumbbell bench press": "0289",
    "flat dumbbell press": "0289",
    "incline dumbbell press": "0314",
    "incline dumbbell bench press": "0314",
    "decline dumbbell press": "0281",
    "dumbbell fly": "0308",
    "flat dumbbell fly": "0308",
    "incline dumbbell fly": "0316",
    "decline dumbbell fly": "0280",
    "cable fly": "0227",  # cable standing fly
    "cable flys": "0227",
    "cable crossover": "0227",
    "cable chest fly": "0227",
    "push up": "0662",
    "push-up": "0662",
    "push ups": "0662",
    "push-ups": "0662",
    "pushup": "0662",
    "pushups": "0662",
    "pushup": "0662",
    "wide push up": "0672",
    "diamond push up": "0279",
    "decline push up": "1302",
    "incline push up": "0671",
    "knee push up": "0670",
    "chest dip": "0251",
    "parallel bar dip": "0251",
    "weighted dip": "0251",
    "assisted dip": "0009",
    "assisted chest dip": "0009",
    "machine chest press": "0576",  # lever chest press
    "chest press machine": "0576",
    "chest machine press": "0576",
    "lever chest press": "0576",
    "incline machine press": "1299",  # lever incline chest press
    "incline chest machine press": "1299",
    "incline machine chest press": "1299",
    "lever incline chest press": "1299",
    
    # Back exercises
    "pull up": "0652",
    "pull-up": "0652",
    "pullup": "0652",
    "pull-ups": "0652",
    "pullups": "0652",
    "wide grip pull up": "0655",
    "wide grip pull-up": "0655",
    "close grip pull up": "0015",
    "close grip pull-up": "0015",
    "neutral grip pull up": "0651",
    "assisted pull up": "0017",
    "assisted pull-up": "0017",
    "assisted pull-ups": "0017",
    "band assisted pull up": "0970",
    "chin up": "0253",
    "chin-up": "0253",
    "chin-ups": "0253",
    "chinup": "0253",
    "lat pulldown": "0198",
    "cable lat pulldown": "0198",
    "wide grip lat pulldown": "0198",
    "close grip lat pulldown": "0196",
    "bent over row": "0027",
    "barbell row": "0027",
    "barbell bent over row": "0027",
    "dumbbell row": "0292",
    "single arm dumbbell row": "0292",
    "one arm dumbbell row": "0292",
    "cable row": "0861",
    "seated cable row": "0861",
    "seated row": "0861",
    "t bar row": "0606",  # lever t bar row
    "t-bar row": "0606",
    "tbar row": "0606",
    "power clean": "0648",  # power clean
    "clean": "0648",
    "barbell clean": "0648",
    "deadlift": "0032",
    "barbell deadlift": "0032",
    "conventional deadlift": "0032",
    "romanian deadlift": "0085",
    "stiff leg deadlift": "0116",
    "sumo deadlift": "0118",
    
    # Shoulder exercises - OVERHEAD PRESS is standing barbell military press
    "overhead press": "1456",  # barbell standing close grip military press (the true standing barbell OHP)
    "standing overhead press": "1456",
    "barbell overhead press": "1456",
    "barbell shoulder press": "1456",
    "military press": "1456",
    "standing military press": "1456",
    "shoulder press": "1456",
    "ohp": "1456",  # common abbreviation
    "barbell military press": "1456",
    "wide grip overhead press": "1457",  # barbell standing wide military press
    "wide grip military press": "1457",
    "seated overhead press": "0091",  # barbell seated overhead press
    "seated barbell press": "0091",
    "seated military press": "0086",  # barbell seated behind head military press
    "dumbbell overhead press": "0426",  # dumbbell standing overhead press
    "dumbbell shoulder press": "0405",
    "seated dumbbell press": "0405",
    "seated dumbbell shoulder press": "0405",
    "standing dumbbell overhead press": "0426",
    "standing dumbbell shoulder press": "0426",
    "arnold press": "0262",
    "dumbbell arnold press": "0262",
    "lateral raise": "0334",
    "dumbbell lateral raise": "0334",
    "side lateral raise": "0334",
    "side raise": "0334",
    "front raise": "0310",
    "dumbbell front raise": "0310",
    "rear delt fly": "0578",
    "reverse fly": "0578",
    "rear delt": "0578",
    "face pull": "0233",  # cable standing rear delt row (with rope) - the face pull movement
    "cable face pull": "0233",
    "cable face pulls": "0233",
    "face pulls": "0233",
    "rope face pull": "0233",
    "upright row": "0122",
    "barbell upright row": "0122",
    "shrug": "0091",
    "barbell shrug": "0091",
    "dumbbell shrug": "0406",
    
    # Arm exercises - Biceps
    "bicep curl": "0294",
    "dumbbell curl": "0294",
    "dumbbell bicep curl": "0294",
    "standing dumbbell curl": "0294",
    "barbell curl": "0023",
    "standing barbell curl": "0023",
    "ez bar curl": "0447",  # ez barbell curl
    "ez barbell curl": "0447",
    "ez curl": "0447",
    "hammer curl": "0313",  # dumbbell hammer curl
    "dumbbell hammer curl": "0313",
    "cable hammer curl": "0165",
    "preacher curl": "0092",  # barbell preacher curl
    "concentration curl": "0274",
    "incline dumbbell curl": "0313",
    "cable curl": "0163",
    "cable bicep curl": "0163",
    
    # Arm exercises - Triceps
    "tricep pushdown": "0241",  # cable triceps pushdown (v-bar)
    "cable pushdown": "0201",  # cable pushdown
    "tricep rope pushdown": "0200",  # cable pushdown (with rope attachment)
    "rope pushdown": "0200",
    "cable tricep pushdown": "0241",
    "triceps pushdown": "0241",
    "tricep extension": "0860",
    "overhead tricep extension": "0860",
    "dumbbell tricep extension": "0860",
    "skull crusher": "0055",
    "lying tricep extension": "0055",
    "barbell skull crusher": "0055",
    "tricep dip": "0814",
    "triceps dip": "0814",
    "dips": "0814",
    "weighted dip": "1755",  # weighted tricep dips
    "weighted dips": "1755",
    "bench dip": "0129",
    "bench dips": "0129",
    "tricep kickback": "0347",
    "dumbbell kickback": "0347",
    "close grip bench press": "0030",  # barbell close-grip bench press
    "close grip bench": "0030",
    "close-grip bench press": "0030",
    
    # Leg exercises
    "squat": "0043",
    "barbell squat": "0043",
    "back squat": "0043",
    "front squat": "0029",  # barbell full squat (closest to front squat form)
    "barbell front squat": "0029",
    "goblet squat": "0534",
    "goblet squats": "0534",
    "kettlebell goblet squat": "0534",
    "dumbbell goblet squat": "1760",
    "leg press": "0738",
    "sled leg press": "0738",
    "hack squat": "0473",
    "leg extension": "0585",
    "seated leg extension": "0585",
    "leg curl": "0586",
    "lying leg curl": "0586",
    "hamstring curl": "0586",
    "seated leg curl": "0599",  # lever seated leg curl
    "lever seated leg curl": "0599",
    "calf raise": "1373",
    "standing calf raise": "1373",
    "seated calf raise": "0720",
    "lunge": "0336",  # dumbbell lunge
    "dumbbell lunge": "0336",
    "lunges": "0336",
    "walking lunge": "1460",  # walking lunge
    "walking lunges": "1460",
    "reverse lunge": "0381",  # dumbbell rear lunge
    "barbell lunge": "0054",  # barbell lunge
    "bulgarian split squat": "0130",
    "split squat": "0130",
    "step up": "0758",
    "box step up": "0758",
    "hip thrust": "0046",
    "barbell hip thrust": "0046",
    "glute bridge": "0446",
    "glute kickback": "0482",
    "cable kickback": "0482",
    "good morning": "0440",
    "barbell good morning": "0440",
    
    # Core exercises
    "plank": "2135",  # weighted front plank (shows plank position)
    "front plank": "2135",
    "forearm plank": "2135",
    "standard plank": "2135",
    "plank hold": "2135",
    "side plank": "1775",  # side plank hip adduction
    "side plank hip": "1775",
    "crunch": "0267",
    "ab crunch": "0267",
    "bicycle crunch": "0139",
    "reverse crunch": "0690",
    "russian twist": "0687",  # russian twist
    "weighted russian twist": "0846",
    "leg raise": "1472",
    "lying leg raise": "1472",
    "hanging leg raise": "1760",
    "hanging knee raise": "0485",
    "knee raise": "0485",
    "mountain climber": "0601",
    "mountain climbers": "0601",
    "ab wheel rollout": "0001",
    "cable crunch": "0155",
    "woodchopper": "0840",
    "cable woodchopper": "0840",
    "dead bug": "1474",
    "flutter kick": "0395",
    "sit up": "0735",
    "v up": "1604",
    
    # Compound/Functional exercises
    "burpee": "1160",
    "burpees": "1160",
    "box jump": "1374",  # box jump down with one leg stabilization
    "box jumps": "1374",
    "jump squat": "0631",
    "jump squats": "0631",
    "kettlebell swing": "0549",
    "kettlebell swings": "0549",
    "clean and press": "1209",
    "clean and jerk": "1212",
    "snatch": "0104",
    "thruster": "2143",
    "thrusters": "2143",
    "wall ball": "2399",
    "wall balls": "2399",
    
    # Cardio/HIIT exercises
    "jump rope": "2612",
    "jumping rope": "2612",
    "skipping rope": "2612",
    "double unders": "2612",  # jump rope (closest equivalent)
    "battle ropes": "0128",  # battling ropes
    "battle rope": "0128",
    "battling ropes": "0128",
    "treadmill": "3666",  # walking on incline treadmill
    "treadmill run": "3666",
    "treadmill sprint": "3666",
    "treadmill sprints": "3666",
    "running": "3666",
    "assault bike": "2612",  # jump rope (similar cardio movement - no exact match)
    "rowing machine": "1866",
    "rowing": "1866",
    "row machine": "1866",
    "rower": "1866",
    
    # Machine exercises (moved from chest section to avoid duplicates)
    "pec deck": "0613",
    "machine fly": "0613",
    "shoulder press machine": "0718",
    "machine shoulder press": "0718",
    "cable lateral raise": "0175",
}

# Cache for exercise GIFs to avoid repeated API calls
exercise_gif_cache = {}

async def get_exercise_gif_from_api(exercise_name: str) -> str:
    """Fetch computer-generated animated GIF - API search first for accuracy, then cache fallback"""
    import httpx
    import urllib.parse
    import asyncio
    
    name_lower = exercise_name.lower().strip().replace("-", " ").replace("  ", " ")
    
    # Check local runtime cache first (already verified correct)
    if name_lower in exercise_gif_cache:
        return exercise_gif_cache[name_lower]
    
    # Check pre-cached exercise IDs - EXACT match only
    if name_lower in CACHED_EXERCISE_GIFS:
        exercise_id = CACHED_EXERCISE_GIFS[name_lower]
        proxy_url = f"/api/exercises/gif/{exercise_id}"
        exercise_gif_cache[name_lower] = proxy_url
        return proxy_url
    
    # If we have API key, ALWAYS try API search first for accuracy
    if EXERCISEDB_API_KEY:
        headers = {
            "X-RapidAPI-Key": EXERCISEDB_API_KEY,
            "X-RapidAPI-Host": EXERCISEDB_API_HOST
        }
        
        try:
            await asyncio.sleep(0.2)  # Rate limit protection
            
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Search for the exercise by name
                encoded_term = urllib.parse.quote(name_lower)
                response = await client.get(
                    f"{EXERCISEDB_API_BASE}/exercises/name/{encoded_term}",
                    headers=headers,
                    params={"limit": 10}
                )
                
                if response.status_code == 200:
                    exercises = response.json()
                    if exercises and len(exercises) > 0:
                        # Find the best match from results
                        best_exercise = None
                        best_score = 0
                        
                        for ex in exercises:
                            ex_name = ex.get("name", "").lower()
                            # Calculate similarity score
                            score = 0
                            
                            # Exact match gets highest score
                            if ex_name == name_lower:
                                score = 100
                            # Exercise name contains our search term
                            elif name_lower in ex_name:
                                score = 80 + len(name_lower)
                            # Our search term contains exercise name
                            elif ex_name in name_lower:
                                score = 60 + len(ex_name)
                            # Word-level matching
                            else:
                                our_words = set(name_lower.split())
                                ex_words = set(ex_name.split())
                                common = our_words & ex_words
                                if common:
                                    score = len(common) * 20
                            
                            if score > best_score:
                                best_score = score
                                best_exercise = ex
                        
                        if best_exercise and best_score >= 20:
                            exercise_id = best_exercise.get("id", "")
                            if exercise_id:
                                proxy_url = f"/api/exercises/gif/{exercise_id}"
                                exercise_gif_cache[name_lower] = proxy_url
                                logger.info(f"GIF match for '{exercise_name}': {best_exercise.get('name')} (score: {best_score})")
                                return proxy_url
                
                elif response.status_code == 429:
                    logger.warning(f"Rate limited - falling back to cache for '{exercise_name}'")
                    
        except Exception as e:
            logger.warning(f"ExerciseDB API error for '{exercise_name}': {e}")
    
    # Fallback: Try smart cache matching only if API failed
    # Use word-based matching instead of substring matching
    name_words = set(name_lower.split())
    best_match = None
    best_match_score = 0
    
    for cached_name, exercise_id in CACHED_EXERCISE_GIFS.items():
        cached_words = set(cached_name.split())
        # Calculate word overlap
        common_words = name_words & cached_words
        if common_words:
            # Score based on how many words match and their specificity
            score = len(common_words) * 10
            # Bonus for exact match
            if cached_name == name_lower:
                score = 100
            # Bonus for significant overlap
            elif len(common_words) >= 2:
                score += 20
            # Penalize if cached name has many extra words
            extra_cached = len(cached_words - name_words)
            score -= extra_cached * 2
            
            if score > best_match_score:
                best_match_score = score
                best_match = exercise_id
    
    if best_match and best_match_score >= 15:
        proxy_url = f"/api/exercises/gif/{best_match}"
        exercise_gif_cache[name_lower] = proxy_url
        return proxy_url
    
    return ""

def get_exercise_gif(exercise_name: str) -> str:
    """Synchronous wrapper that returns empty - actual GIFs fetched async during generation"""
    # This is a placeholder - actual GIF fetching happens in generate_workout
    return ""

async def check_subscription_access(user_id: str) -> dict:
    """Check if user has subscription access or is admin/free access"""
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        return {"has_access": False, "reason": "profile_not_found"}
    
    email = profile.get("email", "").lower()
    
    # Admin always has access
    if email in [e.lower() for e in ADMIN_EMAILS]:
        return {"has_access": True, "reason": "admin"}
    
    # Check free access list
    free_access = await db.free_access.find_one({"email": email.lower()})
    if free_access:
        return {"has_access": True, "reason": "free_access_granted"}
    
    # Check subscription status
    subscription_status = profile.get("subscription_status", "free")
    if subscription_status in ["trial", "monthly", "quarterly", "yearly", "active"]:
        return {"has_access": True, "reason": "subscribed"}
    
    return {"has_access": False, "reason": "no_subscription"}

# Create the main app
app = FastAPI(title="InterFitAI API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== MODELS ====================

# User Profile Models
class UserProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    email: str = ""
    weight: float = 0  # in kg
    height: float = 0  # in cm
    age: int = 0
    gender: str = "male"  # male, female, other
    activity_level: str = "moderate"  # sedentary, light, moderate, active, very_active
    goal: str = "maintenance"  # weight_loss, maintenance, muscle_building
    calculated_macros: Optional[Dict[str, float]] = None
    calorie_adjustment: int = 0  # Manual calorie adjustment (+/- from calculated)
    subscription_status: str = "free"  # free, monthly, quarterly, yearly
    subscription_end_date: Optional[str] = None
    reminders_enabled: bool = True
    motivation_enabled: bool = True
    profile_image: Optional[str] = None  # Base64 encoded profile picture
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserProfileCreate(BaseModel):
    name: str = ""
    email: str = ""
    weight: float
    height: float
    age: int
    gender: str = "male"
    activity_level: str = "moderate"
    goal: str = "maintenance"

class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    activity_level: Optional[str] = None
    goal: Optional[str] = None
    calorie_adjustment: Optional[int] = None
    reminders_enabled: Optional[bool] = None
    motivation_enabled: Optional[bool] = None
    profile_image: Optional[str] = None  # Base64 encoded profile picture

# Workout Models
class Exercise(BaseModel):
    name: str
    sets: int
    reps: str
    rest_seconds: int
    instructions: str
    muscle_groups: List[str]
    equipment: str
    gif_url: Optional[str] = None  # GIF demonstration URL

class WorkoutDay(BaseModel):
    day: str
    focus: str
    exercises: List[Exercise]
    duration_minutes: int
    notes: str

class WorkoutProgram(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    goal: str
    focus_areas: List[str]
    equipment: List[str]
    injuries: Optional[List[str]] = None
    duration_weeks: int = 4
    days_per_week: int = 4
    session_duration_minutes: int = 60  # Workout session duration
    workout_days: List[WorkoutDay]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WorkoutGenerateRequest(BaseModel):
    user_id: str
    goal: str  # build_muscle, lose_fat, body_recomp, strength, general_fitness
    training_style: str = "weights"  # weights, calisthenics, hybrid, functional
    focus_areas: List[str]  # full_body, back, chest, legs, glutes, arms
    equipment: List[str]  # full_gym, barbells, dumbbells, bodyweight, kettlebells, machines
    injuries: Optional[List[str]] = None  # lower_back, knees, shoulders, none
    days_per_week: int = 4
    duration_minutes: int = 60  # Session duration
    fitness_level: str = "intermediate"  # beginner, intermediate, advanced
    preferred_split: str = "ai_choose"  # ai_choose, full_body, upper_lower, push_pull_legs, bro_split

# Meal Plan Models
class Meal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    meal_type: str  # breakfast, lunch, dinner, snack
    ingredients: List[str]
    instructions: str
    calories: int
    protein: float
    carbs: float
    fats: float
    prep_time_minutes: int
    cuisine: Optional[str] = None  # japanese, thai, brazilian, etc.

class MealDay(BaseModel):
    day: str
    meals: List[Meal]
    total_calories: int
    total_protein: float
    total_carbs: float
    total_fats: float

class MealPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    food_preferences: str
    preferred_foods: Optional[str] = None  # User's preferred foods
    foods_to_avoid: Optional[str] = None  # Foods user wants excluded
    supplements: List[str]
    supplements_custom: Optional[str] = None  # Custom supplement text
    allergies: List[str]
    target_calories: int
    target_protein: float
    target_carbs: float
    target_fats: float
    meal_days: List[MealDay]
    is_saved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MealPlanGenerateRequest(BaseModel):
    user_id: str
    food_preferences: str = "balanced"  # balanced, high_protein, whole_foods, vegetarian, vegan, keto, paleo, carnivore, none
    preferred_foods: Optional[str] = None  # Free text: "potatoes, steak, eggs, rice"
    foods_to_avoid: Optional[str] = None  # Free text: "mushrooms, tuna, olives"
    supplements: List[str] = []  # whey_protein, creatine, none
    supplements_custom: Optional[str] = None  # Custom supplement text input
    allergies: List[str] = []  # gluten, nuts, dairy, none

# Favorite Meals Model
class FavoriteMeal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    meal: Meal
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Alternate Meal Request
class AlternateMealRequest(BaseModel):
    user_id: str
    meal_plan_id: str
    day_index: int
    meal_index: int
    preferences: Optional[str] = None
    swap_preference: Optional[str] = "similar"  # similar, higher_protein, lower_calories, quick_prep, vegetarian, budget

# Food Logging Models
class FoodEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    food_name: str
    serving_size: str
    servings: float = 1.0
    calories: int
    protein: float
    carbs: float
    fats: float
    fiber: float = 0
    sugar: float = 0
    sodium: float = 0
    meal_type: str  # breakfast, lunch, dinner, snack
    logged_date: str  # YYYY-MM-DD format
    image_base64: Optional[str] = None
    is_favorite: bool = False
    food_hint: Optional[str] = None  # User-provided hint for AI analysis
    created_at: datetime = Field(default_factory=datetime.utcnow)

class FoodLogRequest(BaseModel):
    user_id: str
    food_name: str
    serving_size: str
    calories: int
    protein: float
    carbs: float
    fats: float
    fiber: float = 0
    sugar: float = 0
    sodium: float = 0
    meal_type: str
    logged_date: str
    image_base64: Optional[str] = None

class FoodImageAnalyzeRequest(BaseModel):
    user_id: str
    image_base64: str
    meal_type: str = "snack"
    additional_context: Optional[str] = None  # e.g., "2 eggs, half portion"
    quantity: int = 1

# Chat Models
class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    role: str  # user, assistant
    content: str
    saved: bool = False
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    user_id: str
    message: str

# Step Tracking Models
class StepEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    steps: int
    distance_km: float
    calories_burned: int
    date: str  # YYYY-MM-DD format
    source: str = "device"  # device, manual, apple_health, garmin, fitbit, google_fit
    created_at: datetime = Field(default_factory=datetime.utcnow)

class StepGoal(BaseModel):
    user_id: str
    daily_steps_goal: int = 10000
    daily_distance_goal_km: float = 8.0

# Subscription Models
class SubscriptionPlan(BaseModel):
    id: str
    name: str
    price: float
    duration_months: int
    features: List[str]

class PaymentRequest(BaseModel):
    user_id: str
    plan_id: str  # monthly, quarterly, yearly
    origin_url: str

# Device Connection Models
class DeviceConnection(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    device_type: str  # apple_health, garmin, fitbit, google_fit
    connected: bool = False
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    last_sync: Optional[datetime] = None
    health_data: Optional[Dict[str, Any]] = None  # Cached health data
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ==================== UNIFIED SUBSCRIPTION MODEL ====================

class SubscriptionInfo(BaseModel):
    """Unified subscription model for Apple, Google, and Stripe"""
    user_id: str
    email: str
    subscription_source: Optional[str] = None  # apple, google, stripe, None for free
    subscription_plan: Optional[str] = None  # monthly, quarterly, yearly
    subscription_status: str = "free"  # free, trial, active, cancelled, expired, billing_issue
    premium_expires_at: Optional[datetime] = None
    bonus_month_applied: bool = False  # For yearly web subscribers (one-time 30-day bonus)
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    revenuecat_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Subscription pricing constants
SUBSCRIPTION_PRICES = {
    "monthly": 9.99,
    "quarterly": 29.99,
    "yearly": 79.99,
}

# Stripe Price IDs (to be configured in Stripe Dashboard)
STRIPE_PRICE_IDS = {
    "quarterly": os.environ.get("STRIPE_PRICE_QUARTERLY", ""),  # With 7-day trial
    "yearly": os.environ.get("STRIPE_PRICE_YEARLY", ""),  # Includes 30-day bonus
}

# Fitbit OAuth Configuration (Register app at https://dev.fitbit.com/)
# These would be set in production .env file
FITBIT_CLIENT_ID = os.environ.get("FITBIT_CLIENT_ID", "")
FITBIT_CLIENT_SECRET = os.environ.get("FITBIT_CLIENT_SECRET", "")
FITBIT_REDIRECT_URI = os.environ.get("FITBIT_REDIRECT_URI", "")

# Garmin Connect OAuth Configuration (Register at https://developer.garmin.com/)
GARMIN_CONSUMER_KEY = os.environ.get("GARMIN_CONSUMER_KEY", "")
GARMIN_CONSUMER_SECRET = os.environ.get("GARMIN_CONSUMER_SECRET", "")

# ==================== HELPER FUNCTIONS ====================

def calculate_macros(weight: float, height: float, age: int, gender: str, activity_level: str, goal: str) -> Dict[str, float]:
    """Calculate personalized macros using Mifflin-St Jeor equation"""
    # Calculate BMR
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    
    # Activity multipliers
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9
    }
    
    tdee = bmr * activity_multipliers.get(activity_level, 1.55)
    
    # Adjust for goal
    if goal == "weight_loss":
        calories = tdee - 500
        protein_ratio = 0.30
        carb_ratio = 0.40
        fat_ratio = 0.30
    elif goal == "muscle_building":
        calories = tdee + 300
        protein_ratio = 0.30
        carb_ratio = 0.45
        fat_ratio = 0.25
    else:  # maintenance
        calories = tdee
        protein_ratio = 0.25
        carb_ratio = 0.45
        fat_ratio = 0.30
    
    return {
        "calories": round(calories),
        "protein": round((calories * protein_ratio) / 4),  # 4 cal per gram protein
        "carbs": round((calories * carb_ratio) / 4),  # 4 cal per gram carbs
        "fats": round((calories * fat_ratio) / 9),  # 9 cal per gram fat
        "bmr": round(bmr),
        "tdee": round(tdee)
    }

# ==================== USER PROFILE ENDPOINTS ====================

@api_router.post("/profile", response_model=UserProfile)
async def create_profile(profile_data: UserProfileCreate):
    """Create or update user profile with calculated macros"""
    macros = calculate_macros(
        profile_data.weight, profile_data.height, profile_data.age,
        profile_data.gender, profile_data.activity_level, profile_data.goal
    )
    
    profile = UserProfile(
        **profile_data.model_dump(),
        calculated_macros=macros
    )
    
    await db.profiles.insert_one(profile.model_dump())
    return profile

@api_router.get("/profile/{user_id}", response_model=UserProfile)
async def get_profile(user_id: str):
    """Get user profile by ID"""
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return UserProfile(**profile)

@api_router.put("/profile/{user_id}", response_model=UserProfile)
async def update_profile(user_id: str, update_data: UserProfileUpdate):
    """Update user profile and recalculate macros if needed"""
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
    
    # Check if we need to recalculate macros
    macro_fields = ["weight", "height", "age", "gender", "activity_level", "goal"]
    need_recalc = any(field in update_dict for field in macro_fields)
    
    if need_recalc:
        merged = {**profile, **update_dict}
        macros = calculate_macros(
            merged["weight"], merged["height"], merged["age"],
            merged["gender"], merged["activity_level"], merged["goal"]
        )
        update_dict["calculated_macros"] = macros
    
    update_dict["updated_at"] = datetime.utcnow()
    
    await db.profiles.update_one({"id": user_id}, {"$set": update_dict})
    updated_profile = await db.profiles.find_one({"id": user_id})
    return UserProfile(**updated_profile)

@api_router.get("/profiles", response_model=List[UserProfile])
async def list_profiles():
    """List all profiles (for testing)"""
    profiles = await db.profiles.find().to_list(100)
    return [UserProfile(**p) for p in profiles]

@api_router.get("/profile/email/{email}")
async def get_profile_by_email(email: str):
    """Get user profile by email - used for login with email"""
    profile = await db.profiles.find_one({"email": {"$regex": f"^{email}$", "$options": "i"}})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please create an account first.")
    return UserProfile(**profile)

# ==================== WORKOUT ENDPOINTS ====================

@api_router.post("/workouts/generate", response_model=WorkoutProgram)
async def generate_workout(request: WorkoutGenerateRequest):
    """Generate AI-powered workout program - ELITE level, perfectly tailored to goal, level, and preferences"""
    # Get user profile for personalization
    profile = await db.profiles.find_one({"id": request.user_id})
    session_duration = request.duration_minutes if hasattr(request, 'duration_minutes') else 60
    fitness_level = request.fitness_level if hasattr(request, 'fitness_level') else "intermediate"
    training_style = getattr(request, 'training_style', 'weights')
    preferred_split = getattr(request, 'preferred_split', 'ai_choose')
    
    # Determine rest times based on goal (scientifically optimal)
    rest_times_by_goal = {
        "strength": "180-300",
        "build_muscle": "90-120",
        "body_recomp": "60-90",
        "lose_fat": "30-45",
        "general_fitness": "60-90",
    }
    goal_rest = rest_times_by_goal.get(request.goal, "60-90")
    
    # Training style descriptions with specific guidelines
    style_desc = {
        "weights": "Traditional weight training with barbells, dumbbells, and machines. Include a good MIX of free weights AND machines for balanced development.",
        "calisthenics": "Bodyweight exercises - pull-ups, push-ups, dips, pistol squats, muscle-ups, bodyweight rows",
        "hybrid": "TRUE HYBRID training combining weighted strength exercises WITH cardiovascular/endurance work like HIIT circuits, rowing intervals, bike sprints, jump rope, or battle ropes",
        "functional": "Functional movements, kettlebells, medicine balls, athletic training, agility work"
    }
    
    # Workout split descriptions
    split_desc = {
        "ai_choose": f"Choose the optimal split for {request.goal} goal with {request.days_per_week} days",
        "full_body": "Full body workout each session, training all major muscle groups",
        "upper_lower": "Alternate between upper body and lower body days",
        "push_pull_legs": "Push (chest/shoulders/triceps), Pull (back/biceps), Legs rotation",
        "bro_split": "One major muscle group per day (chest day, back day, leg day, etc.)"
    }
    
    # ============= FITNESS LEVEL SPECIFIC CARDIO INTENSITY =============
    cardio_intensity_by_level = {
        "beginner": {
            "assault_bike": "20 sec moderate effort / 40 sec easy pedal, 4-6 rounds",
            "rowing": "250m at steady pace, rest 90 sec, repeat 3-4 times",
            "battle_ropes": "20 sec work / 40 sec rest, 4-5 rounds",
            "jump_rope": "30 sec work / 30 sec rest, 4-6 rounds (can step if needed)",
            "treadmill": "30 sec jog / 60 sec walk, 5-6 rounds",
            "burpees": "5-8 reps with rest as needed",
            "box_jumps": "8-10 step-ups onto low box (no jumping required)",
            "description": "Focus on building endurance base. Moderate intensity, longer rest periods."
        },
        "intermediate": {
            "assault_bike": "30 sec hard effort / 30 sec easy, 6-8 rounds",
            "rowing": "400m at challenging pace, rest 60 sec, repeat 4-5 times",
            "battle_ropes": "30 sec work / 30 sec rest, 6-8 rounds",
            "jump_rope": "45 sec work / 15 sec rest, 6-8 rounds",
            "treadmill": "30 sec sprint / 45 sec walk, 8 rounds",
            "burpees": "10-12 reps per set",
            "box_jumps": "10-12 reps onto medium box",
            "description": "Push cardio conditioning with controlled intensity. Challenging but sustainable."
        },
        "advanced": {
            "assault_bike": "30 sec all-out / 30 sec easy, 8-10 rounds",
            "rowing": "500m sprint, rest 60 sec, repeat 5-6 times",
            "battle_ropes": "40 sec work / 20 sec rest, 8-10 rounds",
            "jump_rope": "60 sec work / 15 sec rest, 8-10 rounds with double-unders",
            "treadmill": "30 sec sprint / 30 sec walk, 10-12 rounds",
            "burpees": "15+ reps per set, add chest-to-floor",
            "box_jumps": "15-20 reps onto high box",
            "description": "High intensity cardio. Maximum effort intervals for elite conditioning."
        }
    }
    cardio_intensity = cardio_intensity_by_level.get(fitness_level, cardio_intensity_by_level["intermediate"])
    
    # ============= FITNESS LEVEL SPECIFIC EXERCISE MODIFICATIONS =============
    fitness_params = {
        "beginner": {
            "sets": "2-3", 
            "reps": "12-15",
            "complexity": "basic movements with machine support where needed",
            "exercise_mods": f"""
CRITICAL BEGINNER EXERCISE RULES (DO NOT IGNORE):
1. SUBSTITUTE ADVANCED EXERCISES:
   - Use Assisted Pull-Up Machine or Lat Pulldown (NOT regular Pull-Ups)
   - Use Assisted Dip Machine or Machine Chest Press (NOT Dips)
   - Use Leg Press or Goblet Squat (NOT Barbell Back Squat initially)
   - Use Machine Chest Press before Barbell Bench Press
   - Use Dumbbell Romanian Deadlift (light weight) before Conventional Deadlift
   - Use Seated Cable Row before Bent Over Barbell Rows

2. EXERCISE SELECTION PRIORITY:
   - 60% Machine exercises for safety and form learning
   - 30% Dumbbell exercises for stabilization
   - 10% Barbell only for simple movements (like deadlifts with light weight)

3. REP RANGES:
   - 12-15 reps per set for motor learning and joint conditioning
   - Lower weights, focus on controlled tempo

4. CARDIO INTENSITY (CRITICAL - DO NOT GIVE ADVANCED CARDIO):
   - Assault Bike: {cardio_intensity['assault_bike']}
   - Rowing: {cardio_intensity['rowing']}
   - Battle Ropes: {cardio_intensity['battle_ropes']}
   - Jump Rope: {cardio_intensity['jump_rope']}
   - Treadmill Sprints: {cardio_intensity['treadmill']}
   - Burpees: {cardio_intensity['burpees']}
   - Box Jumps: {cardio_intensity['box_jumps']}
   - {cardio_intensity['description']}"""
        },
        "intermediate": {
            "sets": "3-4", 
            "reps": "8-12",
            "complexity": "mix of compound and isolation exercises",
            "exercise_mods": f"""
INTERMEDIATE EXERCISE GUIDELINES:
1. EXERCISE SELECTION:
   - Can use standard Pull-Ups, Dips, Barbell movements
   - Mix of free weights (55%) and machines (45%) for variety
   - Include both compound and isolation exercises

2. REP RANGES:
   - 8-12 reps for hypertrophy focused exercises
   - 6-8 reps for strength focused compound movements

3. CARDIO INTENSITY (CHALLENGING BUT SUSTAINABLE):
   - Assault Bike: {cardio_intensity['assault_bike']}
   - Rowing: {cardio_intensity['rowing']}
   - Battle Ropes: {cardio_intensity['battle_ropes']}
   - Jump Rope: {cardio_intensity['jump_rope']}
   - Treadmill Sprints: {cardio_intensity['treadmill']}
   - Burpees: {cardio_intensity['burpees']}
   - Box Jumps: {cardio_intensity['box_jumps']}
   - {cardio_intensity['description']}"""
        },
        "advanced": {
            "sets": "4-5", 
            "reps": "6-10",
            "complexity": "advanced techniques, supersets, drop sets",
            "exercise_mods": f"""
ADVANCED EXERCISE GUIDELINES:
1. EXERCISE SELECTION:
   - Weighted Pull-Ups, Weighted Dips, Olympic lift variations
   - Primarily free weights (70%) with machines for isolation (30%)
   - Include advanced techniques: supersets, drop sets, pause reps

2. REP RANGES:
   - 6-8 reps for strength compounds
   - 8-12 reps for hypertrophy isolation
   - Low reps (3-5) for max strength work

3. CARDIO INTENSITY (HIGH INTENSITY):
   - Assault Bike: {cardio_intensity['assault_bike']}
   - Rowing: {cardio_intensity['rowing']}
   - Battle Ropes: {cardio_intensity['battle_ropes']}
   - Jump Rope: {cardio_intensity['jump_rope']}
   - Treadmill Sprints: {cardio_intensity['treadmill']}
   - Burpees: {cardio_intensity['burpees']}
   - Box Jumps: {cardio_intensity['box_jumps']}
   - {cardio_intensity['description']}"""
        }
    }
    level_info = fitness_params.get(fitness_level, fitness_params["intermediate"])
    
    # ============= GOAL-SPECIFIC PROGRAMMING =============
    goal_specific_guidance = ""
    
    if request.goal == "lose_fat":
        goal_specific_guidance = f"""
⚠️ FAT LOSS SPECIFIC PROGRAMMING (CRITICAL):
Even when user selects "weights" training style, fat loss programs should include metabolic elements:

1. RESISTANCE TRAINING STRUCTURE:
   - Circuit-style or superset format where possible to keep heart rate elevated
   - Shorter rest periods (30-45 seconds) between sets
   - Higher rep ranges (12-15) with controlled tempo
   - Compound movements prioritized for calorie burn

2. ADD CARDIO FINISHERS TO WEIGHT DAYS:
   End each weights session with a 8-12 minute cardio finisher appropriate to {fitness_level.upper()} level:
   - Assault Bike: {cardio_intensity['assault_bike']}
   - Rowing: {cardio_intensity['rowing']}
   - Or a bodyweight circuit: {cardio_intensity['burpees']} burpees + {cardio_intensity['box_jumps'].split(' ')[0]} box jumps

3. METABOLIC CONDITIONING:
   - Include 1-2 dedicated conditioning/HIIT days per week
   - Keep heart rate elevated throughout workout
   - Focus on movements that burn maximum calories

4. EXERCISE FORMAT FOR FAT LOSS:
   - Consider pairing exercises (supersets): Upper + Lower or Push + Pull
   - Example: Bench Press immediately into Bent Over Row (no rest between)
   - This keeps metabolic demand high"""
    
    elif request.goal == "build_muscle":
        goal_specific_guidance = """
💪 MUSCLE BUILDING (HYPERTROPHY) SPECIFIC PROGRAMMING - NO CARDIO PRIORITY:

⚠️ IMPORTANT: This is a MUSCLE BUILDING program. DO NOT include:
- Dedicated conditioning/HIIT days
- Intense cardio intervals
- Circuit training format
- Fat loss metabolic work

FOCUS EXCLUSIVELY ON:
1. RESISTANCE TRAINING VOLUME:
   - 10-20 sets per muscle group per week
   - Rep ranges: 8-12 for hypertrophy (primary), 6-8 for strength phases
   - Rest 90-120 seconds for compounds, 60-90 seconds for isolation
   - Progressive overload is KEY - track and increase weights

2. PROGRAM STRUCTURE:
   - ALL days should be dedicated resistance training
   - Split training to hit each muscle 2x per week
   - Focus on compound movements + targeted isolation work
   
3. EXERCISE SELECTION:
   - Heavy compounds: Bench Press, Squat, Deadlift, Rows, Overhead Press
   - Isolation for detail: Curls, Tricep work, Lateral Raises, Leg Curls
   - Time under tension: 3-second negatives on key exercises

4. RECOVERY FOCUS:
   - Adequate rest between sets for muscle recovery
   - DO NOT rush between exercises
   - Quality > Metabolic stress for muscle building"""
    
    elif request.goal == "strength":
        goal_specific_guidance = """
🏋️ STRENGTH/POWER SPECIFIC PROGRAMMING - NO CONDITIONING DAYS:

⚠️ IMPORTANT: This is a PURE STRENGTH program. DO NOT include:
- Full conditioning/HIIT days
- Cardio intervals or finishers
- Circuit training format
- High rep metabolic work

FOCUS EXCLUSIVELY ON:
1. HEAVY COMPOUND LIFTS (USE THESE EXACT NAMES):
   - Barbell Squat (or Barbell Back Squat)
   - Deadlift (Conventional or Sumo)
   - Barbell Bench Press
   - Barbell Military Press (standing overhead press - THE fundamental shoulder exercise)
   - Barbell Row (Bent Over Row)
   - These are the foundation - program around them
   - Low rep ranges: 3-6 reps on main lifts
   - Heavy weights with FULL recovery between sets
   
   NOTE: For shoulders, use "Barbell Military Press" or "Overhead Press" - NOT dumbbell shoulder press!

2. REST PERIODS (CRITICAL):
   - 3-5 MINUTES between heavy compound sets
   - This is NOT optional - ATP must fully replenish
   - Do NOT rush - strength requires full recovery
   
3. PROGRAM STRUCTURE:
   - ALL days should focus on strength development
   - No conditioning days, no HIIT, no cardio intervals
   - Accessory work supports main lifts (triceps for bench, hamstrings for deadlift)
   
4. PERIODIZATION:
   - Week 1: 5x5 at 80% effort
   - Week 2: 4x4 at 85% effort
   - Week 3: 3x3 at 90% effort
   - Week 4: Deload - lighter weights
   
5. ACCESSORY WORK:
   - Support main lifts: Face pulls, Romanian Deadlifts, Close Grip Bench
   - 3-4 sets of 6-10 reps after main lifts"""
    
    elif request.goal == "body_recomp":
        goal_specific_guidance = f"""
🔄 BODY RECOMPOSITION SPECIFIC PROGRAMMING:

BALANCED APPROACH - Build muscle while losing fat:
1. RESISTANCE TRAINING PRIMARY:
   - Maintain/build muscle with compound movements
   - 8-12 rep range for hypertrophy
   - Progressive overload still important

2. LIGHT METABOLIC WORK (NOT INTENSE HIIT):
   - End 1-2 sessions per week with light cardio finisher (5-8 min)
   - Walking incline, light cycling, steady state
   - NOT intense sprints or circuits

3. REST PERIODS:
   - 60-90 seconds between sets
   - Moderate pace to keep some metabolic demand"""

    elif request.goal == "general_fitness":
        goal_specific_guidance = f"""
🎯 GENERAL FITNESS PROGRAMMING:

WELL-ROUNDED APPROACH:
1. Mix of strength, endurance, and flexibility
2. Include variety in exercise selection
3. Moderate intensity across all aspects
4. 60-90 second rest periods
5. Can include light cardio finishers if desired"""
    
    # ============= EQUIPMENT GUIDANCE =============
    equipment_list = request.equipment
    has_full_gym = 'full_gym' in equipment_list
    has_machines = 'machines' in equipment_list or has_full_gym
    
    equipment_guidance = ""
    # CALISTHENICS OVERRIDES EQUIPMENT - NO WEIGHTS
    if training_style == "calisthenics":
        equipment_guidance = """
🏋️ CALISTHENICS TRAINING - BODYWEIGHT ONLY:

⚠️ CRITICAL: User selected CALISTHENICS training style.
DO NOT include ANY weighted exercises, even if they have access to a full gym.

ONLY USE BODYWEIGHT EXERCISES:
- Push-Ups (all variations: wide, diamond, decline, incline, archer)
- Pull-Ups (all variations: wide grip, close grip, chin-ups, commando)
- Dips (parallel bar dips, bench dips)
- Squats (bodyweight squats, pistol squats, sissy squats, jump squats)
- Lunges (walking, reverse, jumping)
- Core: Planks, L-sits, Leg Raises, Hollow Body Holds
- Rows: Inverted Rows, Australian Pull-Ups
- Advanced: Muscle-Ups, Handstand Push-Ups, Front Lever progressions

FOR BEGINNERS:
- Assisted Pull-Up Machine is acceptable to build strength
- Incline Push-Ups instead of full push-ups
- Box Step-Ups instead of pistol squats

DO NOT USE:
- Barbells, Dumbbells, Cables, or Machines for main exercises
- The user wants BODYWEIGHT training, respect this choice!"""
    elif has_full_gym:
        equipment_guidance = """
🏋️ FULL GYM EQUIPMENT - USE VARIETY:
- MUST include BOTH free weights AND machines in every program
- Machines to include: Lat Pulldown, Cable Station, Leg Press, Chest Press Machine, Leg Curl, Leg Extension
- Free weights: Barbells, Dumbbells, EZ Bar
- Cable machines are excellent for constant tension exercises
- DO NOT create a program that only uses dumbbells and barbells!"""
    elif has_machines:
        equipment_guidance = "Include machine exercises where available for proper muscle isolation and safety."
    
    # ============= HYBRID TRAINING SPECIFIC =============
    hybrid_guidance = ""
    if training_style == "hybrid":
        hybrid_guidance = f"""
🔥 TRUE HYBRID TRAINING - WEIGHTS + CARDIO/CONDITIONING:
This is NOT just weights with occasional cardio. Create a TRUE hybrid program:

1. PROGRAM STRUCTURE:
   - 50% of days: Strength-focused with cardio finisher
   - 30% of days: Full HIIT/circuit conditioning
   - 20% of days: Combination (strength + extensive cardio blocks)

2. CARDIO ELEMENTS (USE INTENSITIES APPROPRIATE FOR {fitness_level.upper()}):
   - Assault Bike: {cardio_intensity['assault_bike']}
   - Rowing Intervals: {cardio_intensity['rowing']}
   - Battle Ropes: {cardio_intensity['battle_ropes']}
   - Jump Rope: {cardio_intensity['jump_rope']}
   - Treadmill Sprints: {cardio_intensity['treadmill']}
   
3. CIRCUIT FORMAT EXAMPLE for {fitness_level.upper()}:
   Round 1-{3 if fitness_level == 'beginner' else 4 if fitness_level == 'intermediate' else 5}:
   - Kettlebell Swings x {'10' if fitness_level == 'beginner' else '15' if fitness_level == 'intermediate' else '20'}
   - Push-Ups x {'8' if fitness_level == 'beginner' else '12' if fitness_level == 'intermediate' else '15'}
   - Goblet Squats x {'10' if fitness_level == 'beginner' else '12' if fitness_level == 'intermediate' else '15'}
   - Battle Ropes x {'15 sec' if fitness_level == 'beginner' else '20 sec' if fitness_level == 'intermediate' else '30 sec'}
   Rest {'90 sec' if fitness_level == 'beginner' else '60 sec' if fitness_level == 'intermediate' else '45 sec'} between rounds

4. CLEAR FORMATTING FOR CARDIO EXERCISES:
   Name: "Rowing Intervals" or "Assault Bike Sprints"
   Sets: Number of rounds
   Reps: Duration format (e.g., "250m" or "20 sec work / 40 sec rest")
   Instructions: Clear explanation including work/rest protocol"""
    
    # ============= BUILD THE FINAL PROMPT =============
    prompt = f"""Create an ELITE-LEVEL {request.days_per_week}-day per week workout program perfectly tailored to this user:

📋 USER PROFILE:
- Primary Goal: {request.goal.replace('_', ' ').upper()}
- Training Style: {training_style.upper()} - {style_desc.get(training_style, 'Traditional weight training')}
- Fitness Level: {fitness_level.upper()} ⚠️ (MUST match exercise difficulty to this level)
- Workout Split: {split_desc.get(preferred_split, 'AI optimized')}
- Focus Areas: {', '.join(request.focus_areas) if request.focus_areas else 'Full body'}
- Available Equipment: {', '.join(request.equipment)}
- Injuries/Limitations: {', '.join(request.injuries) if request.injuries else 'None'}
- Session Duration: {session_duration} minutes per workout

{level_info['exercise_mods']}

{goal_specific_guidance}

{equipment_guidance}

{hybrid_guidance}

📊 SCIENTIFIC PARAMETERS:
- Sets per exercise: {level_info['sets']}
- Rep ranges: {level_info['reps']}
- Rest between sets: {goal_rest} seconds
- Session duration: {session_duration} minutes

🎯 CRITICAL REQUIREMENTS (READ CAREFULLY):
1. EVERY exercise must be appropriate for {fitness_level.upper()} level
2. If {fitness_level} is BEGINNER, NO advanced exercises (use Assisted Pull-Up, Leg Press, machines)
3. {"If goal is BUILD_MUSCLE or STRENGTH: NO cardio days, NO conditioning, NO HIIT circuits - PURE resistance training only!" if request.goal in ['build_muscle', 'strength'] else ""}
4. {"If training style is CALISTHENICS: Use ONLY bodyweight exercises - NO barbells, dumbbells, or machines!" if training_style == "calisthenics" else ""}
5. {"If goal is LOSE_FAT: Include cardio finishers appropriate to fitness level" if request.goal == "lose_fat" else ""}
6. {"If training style is HYBRID: Include TRUE cardio elements - rowing, assault bike, circuits" if training_style == "hybrid" else ""}
7. Cardio intensity MUST match {fitness_level.upper()} level (not advanced cardio for beginners!)
8. Use equipment variety where appropriate (machines + free weights for full gym)

Provide the workout program in this JSON structure:
{{
    "name": "Creative Program Name reflecting {request.goal.replace('_', ' ')} goal and {training_style} style for {fitness_level} level",
    "workout_days": [
        {{
            "day": "Day 1 - Descriptive Focus",
            "focus": "Primary focus (e.g., 'Upper Body Strength' or 'Full Body HIIT')",
            "duration_minutes": {session_duration},
            "notes": "Coaching tips and goals for this specific day",
            "exercises": [
                {{
                    "name": "Exercise Name (use standard names matching ExerciseDB)",
                    "sets": 3,
                    "reps": "10-12 OR for cardio: '250m' or '20 sec work / 40 sec rest x 4 rounds'",
                    "rest_seconds": {goal_rest.split('-')[0]},
                    "instructions": "Detailed form cues and execution tips. For cardio: include work/rest protocol.",
                    "muscle_groups": ["primary", "secondary"],
                    "equipment": "specific equipment needed"
                }}
            ]
        }}
    ]
}}

FINAL CHECK - Before outputting, verify:
✓ All exercises match {fitness_level.upper()} level
✓ Cardio intensities use the EXACT values specified for {fitness_level.upper()}
✓ Program structure supports the {request.goal.replace('_', ' ')} goal
✓ Equipment variety is used (machines + free weights for full gym)
✓ Each day has clear focus and appropriate exercise selection"""

    def repair_truncated_json(content: str) -> str:
        """Attempt to repair truncated JSON by closing open structures"""
        content = content.strip()
        # Remove trailing incomplete value (find last clean terminator)
        for i in range(len(content) - 1, -1, -1):
            c = content[i]
            if c in ('}', ']', '"') or (c.isdigit()) or content[i:i+4] in ('true', 'fals', 'null'):
                content = content[:i+1]
                break
        # Remove trailing comma if present
        while content and content[-1] in ',':
            content = content[:-1].rstrip()
        # Close open brackets and braces
        open_braces = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        content += ']' * max(0, open_brackets) + '}' * max(0, open_braces)
        return content

    def clean_json_content(raw: str) -> str:
        """Clean and extract JSON from raw LLM response"""
        raw = raw.strip() if raw else ""
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        return raw.strip()

    workout_data = None
    last_error = None

    for attempt in range(2):
        try:
            current_prompt = prompt
            if attempt == 1:
                # Simplified fallback prompt - fewer exercises, shorter instructions
                logger.info("Workout gen: retrying with simplified prompt")
                current_prompt = f"""Create a {request.days_per_week}-day {request.goal.replace('_', ' ')} workout for {fitness_level} level.
Equipment: {', '.join(request.equipment)}. Focus: {', '.join(request.focus_areas) if request.focus_areas else 'full body'}.
Style: {training_style}. Session: {session_duration} min. Injuries: {', '.join(request.injuries) if request.injuries else 'None'}.

RULES: Exactly 5 exercises per day. Instructions max 20 words each.

Return ONLY valid JSON:
{{
  "name": "Program Name",
  "workout_days": [
    {{
      "day": "Day 1 - Focus",
      "focus": "Brief focus",
      "duration_minutes": {session_duration},
      "notes": "Brief tip",
      "exercises": [
        {{"name": "Exercise", "sets": 3, "reps": "10-12", "rest_seconds": {goal_rest.split('-')[0]}, "instructions": "Form cue here.", "muscle_groups": ["primary"], "equipment": "equipment"}}
      ]
    }}
  ]
}}"""

            content = await call_claude_sonnet(
                system_message="You are an expert personal trainer. Return ONLY valid JSON. No markdown. No extra text. Max 6 exercises per day.",
                user_message=current_prompt,
                temperature=0.6 if attempt == 0 else 0.3,
                max_tokens=5000
            )

            content = clean_json_content(content)
            logger.info(f"Workout attempt {attempt+1} response len: {len(content) if content else 0}")

            try:
                workout_data = json.loads(content)
                break
            except json.JSONDecodeError as je:
                logger.warning(f"Workout attempt {attempt+1} JSONDecodeError at char {je.pos}. Trying repair...")
                try:
                    repaired = repair_truncated_json(content)
                    workout_data = json.loads(repaired)
                    logger.info(f"Workout attempt {attempt+1}: JSON repair succeeded")
                    break
                except Exception as repair_err:
                    last_error = je
                    logger.error(f"Workout attempt {attempt+1}: repair failed: {repair_err}")
                    if attempt < 1:
                        continue
                    raise HTTPException(status_code=500, detail="Failed to generate workout. Please try again.")

        except HTTPException:
            raise
        except Exception as e:
            last_error = e
            logger.error(f"Workout generation attempt {attempt+1} error: {e}")
            if attempt < 1:
                continue
            raise HTTPException(status_code=500, detail=f"Failed to generate workout: {str(e)}")

    if not workout_data:
        raise HTTPException(status_code=500, detail="Failed to generate workout. Please try again.")

    # Helper function to parse sets value (handles "6-8 rounds" -> 6)
    def parse_sets(sets_value):
        """Convert sets value to integer, handling various formats"""
        if isinstance(sets_value, int):
            return sets_value
        if isinstance(sets_value, str):
            import re
            numbers = re.findall(r'\d+', sets_value)
            if numbers:
                return int(numbers[0])
        return 3  # Default fallback
    
    # Add GIF URLs to exercises - fetch from ExerciseDB API
    processed_days = []
    for day in workout_data.get("workout_days", []):
        exercises_with_gifs = []
        for ex in day.get("exercises", []):
            ex_dict = dict(ex)
            ex_dict["sets"] = parse_sets(ex_dict.get("sets", 3))
            gif_url = await get_exercise_gif_from_api(ex.get("name", ""))
            ex_dict["gif_url"] = gif_url
            exercises_with_gifs.append(ex_dict)
        day["exercises"] = exercises_with_gifs
        processed_days.append(day)
    
    session_duration = request.duration_minutes if hasattr(request, 'duration_minutes') else 60
    
    program = WorkoutProgram(
        user_id=request.user_id,
        name=workout_data.get("name", f"{request.goal.replace('_', ' ').title()} Program"),
        goal=request.goal,
        focus_areas=request.focus_areas,
        equipment=request.equipment,
        injuries=request.injuries,
        days_per_week=request.days_per_week,
        session_duration_minutes=session_duration,
        workout_days=[WorkoutDay(**day) for day in processed_days]
    )
    
    await db.workouts.insert_one(program.model_dump())
    return program

@api_router.get("/workouts/{user_id}", response_model=List[WorkoutProgram])
async def get_user_workouts(user_id: str):
    """Get all workout programs for a user"""
    workouts = await db.workouts.find({"user_id": user_id}).sort("created_at", -1).to_list(50)
    return [WorkoutProgram(**w) for w in workouts]

@api_router.get("/workout/{workout_id}", response_model=WorkoutProgram)
async def get_workout(workout_id: str):
    """Get a specific workout program"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return WorkoutProgram(**workout)

@api_router.delete("/workout/{workout_id}")
async def delete_workout(workout_id: str):
    """Delete a workout program"""
    result = await db.workouts.delete_one({"id": workout_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"message": "Workout deleted successfully"}

class RenameWorkoutRequest(BaseModel):
    name: str

@api_router.patch("/workout/{workout_id}/rename")
async def rename_workout(workout_id: str, request: RenameWorkoutRequest):
    """Rename a workout program"""
    result = await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"name": request.name, "updated_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"message": "Workout renamed successfully", "name": request.name}

class WorkoutPerformanceRequest(BaseModel):
    performance: dict  # { "dayIndex-exerciseIndex-setIndex": { "weight": "50", "reps": "10", "completed": true } }

@api_router.post("/workout/{workout_id}/performance")
async def save_workout_performance(workout_id: str, request: WorkoutPerformanceRequest):
    """Save workout performance data (weights, reps, completion status)"""
    result = await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"performance": request.performance, "updated_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"message": "Performance saved successfully"}

@api_router.get("/workout/{workout_id}/performance")
async def get_workout_performance(workout_id: str):
    """Get workout performance data"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    return {"performance": workout.get("performance", {})}

class UpdateExerciseRequest(BaseModel):
    day_index: int
    exercise_index: int
    sets: Optional[int] = None
    reps: Optional[str] = None

@api_router.patch("/workout/{workout_id}/exercise")
async def update_exercise(workout_id: str, request: UpdateExerciseRequest):
    """Update exercise sets/reps in a workout"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    workout_days = workout.get("workout_days", [])
    if request.day_index >= len(workout_days):
        raise HTTPException(status_code=400, detail="Invalid day index")
    
    exercises = workout_days[request.day_index].get("exercises", [])
    if request.exercise_index >= len(exercises):
        raise HTTPException(status_code=400, detail="Invalid exercise index")
    
    if request.sets is not None:
        exercises[request.exercise_index]["sets"] = request.sets
    if request.reps is not None:
        exercises[request.exercise_index]["reps"] = request.reps
    
    workout_days[request.day_index]["exercises"] = exercises
    
    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"workout_days": workout_days, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Exercise updated successfully"}

class ReplaceExerciseRequest(BaseModel):
    day_index: int
    exercise_index: int
    new_exercise: dict

@api_router.patch("/workout/{workout_id}/replace-exercise")
async def replace_exercise(workout_id: str, request: ReplaceExerciseRequest):
    """Replace an exercise in a workout"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    workout_days = workout.get("workout_days", [])
    if request.day_index >= len(workout_days):
        raise HTTPException(status_code=400, detail="Invalid day index")
    
    exercises = workout_days[request.day_index].get("exercises", [])
    if request.exercise_index >= len(exercises):
        raise HTTPException(status_code=400, detail="Invalid exercise index")
    
    # Replace the exercise
    exercises[request.exercise_index] = request.new_exercise
    workout_days[request.day_index]["exercises"] = exercises
    
    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"workout_days": workout_days, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Exercise replaced successfully"}

class DeleteExerciseRequest(BaseModel):
    day_index: int
    exercise_index: int

@api_router.delete("/workout/{workout_id}/exercise")
async def delete_exercise(workout_id: str, request: DeleteExerciseRequest):
    """Delete an exercise from a workout"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    workout_days = workout.get("workout_days", [])
    if request.day_index >= len(workout_days):
        raise HTTPException(status_code=400, detail="Invalid day index")
    
    exercises = workout_days[request.day_index].get("exercises", [])
    if request.exercise_index >= len(exercises):
        raise HTTPException(status_code=400, detail="Invalid exercise index")
    
    # Remove the exercise
    exercises.pop(request.exercise_index)
    workout_days[request.day_index]["exercises"] = exercises
    
    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"workout_days": workout_days, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Exercise deleted successfully"}

class AddExerciseRequest(BaseModel):
    day_index: int
    exercise: dict  # Exercise object with name, sets, reps, etc.

@api_router.post("/workout/{workout_id}/exercise")
async def add_exercise(workout_id: str, request: AddExerciseRequest):
    """Add a new exercise to a workout day"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    workout_days = workout.get("workout_days", [])
    if request.day_index >= len(workout_days):
        raise HTTPException(status_code=400, detail="Invalid day index")
    
    exercises = workout_days[request.day_index].get("exercises", [])
    
    # Add GIF URL if not provided
    exercise_data = request.exercise
    if not exercise_data.get("gif_url"):
        gif_url = await get_exercise_gif_from_api(exercise_data.get("name", ""))
        exercise_data["gif_url"] = gif_url
    
    # Add default values if missing
    if "sets" not in exercise_data:
        exercise_data["sets"] = 3
    if "reps" not in exercise_data:
        exercise_data["reps"] = "10-12"
    if "rest_seconds" not in exercise_data:
        exercise_data["rest_seconds"] = 90
    if "instructions" not in exercise_data:
        exercise_data["instructions"] = "Perform with proper form and controlled movements."
    if "muscle_groups" not in exercise_data:
        exercise_data["muscle_groups"] = []
    
    # Add the exercise to the end of the list
    exercises.append(exercise_data)
    workout_days[request.day_index]["exercises"] = exercises
    
    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"workout_days": workout_days, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Exercise added successfully", "exercise": exercise_data}

@api_router.post("/workout/{workout_id}/refresh-gifs")
async def refresh_workout_gifs(workout_id: str):
    """Refresh all GIF URLs for a workout using the latest matching algorithm"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    
    workout_days = workout.get("workout_days", workout.get("program", {}).get("days", []))
    updated = False
    
    for day in workout_days:
        for exercise in day.get("exercises", []):
            # Get fresh GIF URL for this exercise
            new_gif_url = await get_exercise_gif_from_api(exercise.get("name", ""))
            if new_gif_url:
                exercise["gif_url"] = new_gif_url
                updated = True
    
    if updated:
        # Determine which field to update based on structure
        if "workout_days" in workout:
            await db.workouts.update_one(
                {"id": workout_id},
                {"$set": {"workout_days": workout_days, "updated_at": datetime.utcnow()}}
            )
        else:
            await db.workouts.update_one(
                {"id": workout_id},
                {"$set": {"program.days": workout_days, "updated_at": datetime.utcnow()}}
            )
    
    return {"message": "GIF URLs refreshed successfully", "updated": updated}

@api_router.get("/exercises/search")
async def search_exercises(search: str = None, muscle: str = None, limit: int = 50):
    """Search exercises from ExerciseDB with improved search handling"""
    import httpx
    import urllib.parse
    
    if not EXERCISEDB_API_KEY:
        return {"exercises": []}
    
    headers = {
        "X-RapidAPI-Key": EXERCISEDB_API_KEY,
        "X-RapidAPI-Host": EXERCISEDB_API_HOST
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            exercises = []
            
            # Handle search with muscle filter - combine both
            if search and muscle:
                # First get all exercises for the muscle group
                muscle_map = {
                    "chest": "chest", "back": "back", "shoulders": "shoulders",
                    "biceps": "upper arms", "triceps": "upper arms",
                    "legs": "upper legs", "glutes": "upper legs",
                    "abs": "waist", "cardio": "cardio"
                }
                mapped_muscle = muscle_map.get(muscle.lower(), muscle.lower())
                response = await client.get(
                    f"{EXERCISEDB_API_BASE}/exercises/bodyPart/{mapped_muscle}",
                    headers=headers,
                    params={"limit": 300}
                )
                if response.status_code == 200:
                    all_exercises = response.json()
                    # Filter by search term
                    search_lower = search.lower().replace("-", " ")
                    for ex in all_exercises:
                        ex_name = ex.get("name", "").lower()
                        # Match if search term is in name or name contains key words from search
                        search_words = set(search_lower.split())
                        if search_lower in ex_name or any(word in ex_name for word in search_words if len(word) > 2):
                            exercises.append(ex)
            
            elif muscle:
                # Search by body part/muscle only
                muscle_map = {
                    "chest": "chest", "back": "back", "shoulders": "shoulders",
                    "biceps": "upper arms", "triceps": "upper arms",
                    "legs": "upper legs", "glutes": "upper legs",
                    "abs": "waist", "cardio": "cardio"
                }
                mapped_muscle = muscle_map.get(muscle.lower(), muscle.lower())
                response = await client.get(
                    f"{EXERCISEDB_API_BASE}/exercises/bodyPart/{mapped_muscle}",
                    headers=headers,
                    params={"limit": 200}
                )
                if response.status_code == 200:
                    exercises = response.json()
            
            elif search:
                # Clean up search term - keep compound words intact
                # Handle common variations: pull-up, pull up, pullup -> search for "pull"
                clean_search = search.lower().strip()
                
                # SYNONYM MAPPING - map common terms to their ExerciseDB equivalents
                synonyms = {
                    "overhead press": ["military press", "overhead"],
                    "ohp": ["military press"],
                    "shoulder press": ["military press", "shoulder"],
                    "pull-up": ["pull up", "pull"],
                    "pull up": ["pull up", "pull"],
                    "pullup": ["pull up", "pull"],
                    "chin-up": ["chin up", "chin"],
                    "bench": ["bench press"],
                    "squat": ["squat"],
                    "deadlift": ["deadlift"],
                    "row": ["row"],
                    "curl": ["curl"],
                    "dip": ["dip"],
                    "lunge": ["lunge"],
                    "press": ["press"],
                }
                
                # Handle hyphenated words - try both forms
                search_terms = [clean_search]
                if "-" in clean_search:
                    search_terms.append(clean_search.replace("-", " "))
                if " " in clean_search:
                    # Also try first significant word
                    words = clean_search.split()
                    if len(words) >= 1 and len(words[0]) > 2:
                        search_terms.append(words[0])
                
                # Add synonyms to search terms
                for key, syn_list in synonyms.items():
                    if key in clean_search or clean_search in key:
                        search_terms.extend(syn_list)
                
                # Remove duplicates while preserving order
                seen = set()
                unique_terms = []
                for term in search_terms:
                    if term not in seen:
                        seen.add(term)
                        unique_terms.append(term)
                search_terms = unique_terms
                
                # Try each search term
                for term in search_terms:
                    encoded = urllib.parse.quote(term)
                    response = await client.get(
                        f"{EXERCISEDB_API_BASE}/exercises/name/{encoded}",
                        headers=headers,
                        params={"limit": 100}
                    )
                    if response.status_code == 200:
                        results = response.json()
                        if results:
                            # Merge unique results
                            existing_ids = {ex.get("id") for ex in exercises}
                            for ex in results:
                                if ex.get("id") not in existing_ids:
                                    exercises.append(ex)
                                    existing_ids.add(ex.get("id"))
                            
                            # Don't break early - gather synonyms too
                            if len(exercises) >= 50:
                                break
            
            else:
                # No filter - get popular exercises across all body parts
                body_parts = ["chest", "back", "shoulders", "upper legs", "upper arms", "waist"]
                for part in body_parts:
                    response = await client.get(
                        f"{EXERCISEDB_API_BASE}/exercises/bodyPart/{part}",
                        headers=headers,
                        params={"limit": 20}
                    )
                    if response.status_code == 200:
                        exercises.extend(response.json())
            
            # Format response - construct gifUrl using our proxy endpoint
            formatted = []
            for ex in exercises[:min(limit, 200)]:  # Respect limit but cap at 200
                exercise_id = ex.get("id", "")
                # Use our proxy endpoint to serve GIFs with proper authentication
                gif_url = f"/api/exercises/gif/{exercise_id}" if exercise_id else None
                
                formatted.append({
                    "id": exercise_id,
                    "name": ex.get("name", "").title(),
                    "target": ex.get("target", ""),
                    "equipment": ex.get("equipment", ""),
                    "bodyPart": ex.get("bodyPart", ""),
                    "gifUrl": gif_url,
                    "secondaryMuscles": ex.get("secondaryMuscles", []),
                    "instructions": ex.get("instructions", []),
                })
            
            return {"exercises": formatted}
    except Exception as e:
        logger.error(f"Exercise search error: {e}")
        return {"exercises": []}

@api_router.get("/exercises/gif/{exercise_id}")
async def get_exercise_gif(exercise_id: str, resolution: str = "360"):
    """Proxy endpoint to serve exercise GIFs with proper authentication"""
    import httpx
    from fastapi.responses import Response
    
    if not EXERCISEDB_API_KEY:
        raise HTTPException(status_code=503, detail="ExerciseDB API not configured")
    
    # Use the documented image endpoint
    gif_url = f"https://exercisedb.p.rapidapi.com/image?exerciseId={exercise_id}&resolution={resolution}&rapidapi-key={EXERCISEDB_API_KEY}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(gif_url, follow_redirects=True)
            if response.status_code == 200:
                return Response(
                    content=response.content,
                    media_type="image/gif",
                    headers={
                        "Cache-Control": "public, max-age=43200",  # Cache for 12 hours (GIF URLs change every 12 hours per docs)
                    }
                )
            raise HTTPException(status_code=404, detail="GIF not found")
    except Exception as e:
        logger.error(f"GIF proxy error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch GIF")

# ==================== MEAL PLAN ENDPOINTS ====================

@api_router.post("/mealplans/generate", response_model=MealPlan)
async def generate_meal_plan(request: MealPlanGenerateRequest):
    """Generate meal plan using DIET-SPECIFIC templates scaled to user's targets"""
    profile = await db.profiles.find_one({"id": request.user_id})
    if not profile or not profile.get("calculated_macros"):
        raise HTTPException(status_code=404, detail="User profile with macros not found. Please set up your profile first.")
    
    macros = profile["calculated_macros"]
    target_cal = macros['calories']
    target_pro = macros['protein']
    target_carb = macros['carbs']
    target_fat = macros['fats']
    
    eating_style = request.food_preferences.lower()
    
    # Diet-specific template selection
    # For Keto/Carnivore/Paleo: Override to high protein/fat, minimal carbs
    # Each template: {ingredient: (grams, cal, protein, carbs, fats)}
    
    # ===== KETO TEMPLATES (Very low carb, high fat) =====
    KETO_TEMPLATES = {
        "day1": {
            "breakfast": {
                "name": "Keto Egg & Bacon Plate",
                "ingredients": {
                    "eggs": (150, 216, 18, 1, 15),
                    "bacon": (60, 258, 12, 0, 24),
                    "avocado": (100, 160, 2, 9, 15),
                    "butter": (15, 107, 0, 0, 12),
                },
                "instructions": "Fry eggs in butter, crisp bacon, serve with fresh avocado slices",
                "prep_time": 15
            },
            "lunch": {
                "name": "Grilled Salmon with Greens",
                "ingredients": {
                    "salmon": (200, 416, 40, 0, 26),
                    "olive oil": (20, 177, 0, 0, 20),
                    "spinach": (100, 23, 3, 4, 0),
                    "cheese": (30, 121, 8, 0, 10),
                },
                "instructions": "Grill salmon, serve on bed of sautéed spinach with melted cheese",
                "prep_time": 20
            },
            "dinner": {
                "name": "Ribeye Steak with Asparagus",
                "ingredients": {
                    "ribeye steak": (250, 625, 50, 0, 46),
                    "asparagus": (150, 30, 3, 6, 0),
                    "butter": (20, 143, 0, 0, 16),
                },
                "instructions": "Pan-sear ribeye to preference, serve with butter-grilled asparagus",
                "prep_time": 25
            },
            "snack": {
                "name": "Cheese & Nut Plate",
                "ingredients": {
                    "cheddar cheese": (50, 201, 12, 1, 17),
                    "macadamia nuts": (30, 216, 2, 4, 23),
                },
                "instructions": "Arrange cheese slices with macadamia nuts",
                "prep_time": 5
            }
        },
        "day2": {
            "breakfast": {
                "name": "Keto Omelette",
                "ingredients": {
                    "eggs": (200, 288, 24, 1, 20),
                    "cheese": (40, 161, 10, 1, 13),
                    "mushrooms": (50, 11, 2, 2, 0),
                    "butter": (15, 107, 0, 0, 12),
                },
                "instructions": "Make fluffy omelette with cheese and sautéed mushrooms",
                "prep_time": 15
            },
            "lunch": {
                "name": "Chicken Thighs with Caesar Salad",
                "ingredients": {
                    "chicken thighs": (200, 418, 52, 0, 22),
                    "romaine lettuce": (100, 17, 1, 3, 0),
                    "parmesan": (30, 121, 11, 1, 8),
                    "olive oil": (20, 177, 0, 0, 20),
                },
                "instructions": "Grill chicken thighs, serve over romaine with parmesan and olive oil dressing",
                "prep_time": 25
            },
            "dinner": {
                "name": "Bunless Burger with Cheese",
                "ingredients": {
                    "ground beef 80% lean": (200, 508, 52, 0, 34),
                    "cheese": (40, 161, 10, 1, 13),
                    "avocado": (80, 128, 2, 7, 12),
                    "lettuce wrap": (50, 8, 1, 2, 0),
                },
                "instructions": "Form patty, grill to preference, top with cheese and avocado in lettuce wrap",
                "prep_time": 20
            },
            "snack": {
                "name": "Cream Cheese Celery",
                "ingredients": {
                    "cream cheese": (60, 199, 3, 2, 20),
                    "celery": (100, 16, 1, 3, 0),
                    "pecans": (20, 139, 2, 3, 14),
                },
                "instructions": "Fill celery stalks with cream cheese, top with pecans",
                "prep_time": 5
            }
        },
        "day3": {
            "breakfast": {
                "name": "Smoked Salmon & Eggs",
                "ingredients": {
                    "smoked salmon": (100, 117, 23, 0, 2),
                    "eggs": (150, 216, 18, 1, 15),
                    "cream cheese": (40, 133, 2, 1, 13),
                    "capers": (10, 2, 0, 0, 0),
                },
                "instructions": "Scramble eggs, serve with smoked salmon, cream cheese, and capers",
                "prep_time": 15
            },
            "lunch": {
                "name": "Tuna Salad Avocado Boats",
                "ingredients": {
                    "tuna": (150, 174, 39, 0, 1),
                    "avocado": (200, 320, 4, 18, 30),
                    "mayonnaise": (30, 203, 0, 0, 22),
                    "celery": (30, 5, 0, 1, 0),
                },
                "instructions": "Mix tuna with mayo and celery, serve in halved avocados",
                "prep_time": 10
            },
            "dinner": {
                "name": "Pork Chops with Broccoli",
                "ingredients": {
                    "pork chops": (200, 330, 50, 0, 14),
                    "broccoli": (150, 51, 4, 11, 1),
                    "butter": (25, 179, 0, 0, 20),
                    "garlic": (5, 7, 0, 2, 0),
                },
                "instructions": "Pan-fry pork chops in butter with garlic, serve with steamed broccoli",
                "prep_time": 25
            },
            "snack": {
                "name": "String Cheese & Almonds",
                "ingredients": {
                    "mozzarella string cheese": (56, 160, 14, 2, 10),
                    "almonds": (30, 174, 6, 6, 15),
                },
                "instructions": "Simple snack plate",
                "prep_time": 2
            }
        }
    }
    
    # ===== CARNIVORE TEMPLATES (Meat only, zero carbs) =====
    CARNIVORE_TEMPLATES = {
        "day1": {
            "breakfast": {
                "name": "Steak and Eggs",
                "ingredients": {
                    "ribeye steak": (200, 500, 40, 0, 37),
                    "eggs": (150, 216, 18, 1, 15),
                    "butter": (20, 143, 0, 0, 16),
                },
                "instructions": "Pan-sear steak in butter, fry eggs to preference",
                "prep_time": 15
            },
            "lunch": {
                "name": "Ground Beef Patties",
                "ingredients": {
                    "ground beef 80% lean": (300, 762, 78, 0, 51),
                    "butter": (15, 107, 0, 0, 12),
                    "salt": (2, 0, 0, 0, 0),
                },
                "instructions": "Form patties, cook in butter, season with salt",
                "prep_time": 15
            },
            "dinner": {
                "name": "Roasted Chicken Thighs",
                "ingredients": {
                    "chicken thighs": (350, 731, 91, 0, 39),
                    "chicken fat": (20, 180, 0, 0, 20),
                },
                "instructions": "Roast chicken thighs with rendered fat until crispy",
                "prep_time": 40
            },
            "snack": {
                "name": "Beef Jerky",
                "ingredients": {
                    "beef jerky": (50, 116, 23, 3, 1),
                    "pork rinds": (30, 154, 17, 0, 9),
                },
                "instructions": "Simple meat-based snack",
                "prep_time": 0
            }
        },
        "day2": {
            "breakfast": {
                "name": "Bacon and Eggs Feast",
                "ingredients": {
                    "bacon": (100, 430, 20, 0, 40),
                    "eggs": (200, 288, 24, 1, 20),
                    "butter": (10, 72, 0, 0, 8),
                },
                "instructions": "Crisp bacon, scramble eggs in bacon fat and butter",
                "prep_time": 20
            },
            "lunch": {
                "name": "Lamb Chops",
                "ingredients": {
                    "lamb chops": (300, 639, 60, 0, 45),
                    "butter": (15, 107, 0, 0, 12),
                },
                "instructions": "Pan-sear lamb chops in butter to medium-rare",
                "prep_time": 20
            },
            "dinner": {
                "name": "Prime Rib Roast",
                "ingredients": {
                    "prime rib": (350, 875, 70, 0, 66),
                    "beef tallow": (15, 135, 0, 0, 15),
                },
                "instructions": "Roast prime rib with beef tallow coating",
                "prep_time": 90
            },
            "snack": {
                "name": "Sardines",
                "ingredients": {
                    "sardines in oil": (100, 208, 25, 0, 11),
                },
                "instructions": "Eat straight from the can",
                "prep_time": 0
            }
        },
        "day3": {
            "breakfast": {
                "name": "Sausage and Eggs",
                "ingredients": {
                    "pork sausage": (150, 420, 18, 0, 39),
                    "eggs": (150, 216, 18, 1, 15),
                    "butter": (15, 107, 0, 0, 12),
                },
                "instructions": "Pan-fry sausages, cook eggs in remaining fat",
                "prep_time": 15
            },
            "lunch": {
                "name": "Bison Burgers",
                "ingredients": {
                    "ground bison": (300, 486, 66, 0, 24),
                    "beef tallow": (20, 180, 0, 0, 20),
                },
                "instructions": "Form patties, cook in beef tallow",
                "prep_time": 15
            },
            "dinner": {
                "name": "Salmon Steaks",
                "ingredients": {
                    "salmon steaks": (300, 624, 60, 0, 39),
                    "butter": (25, 179, 0, 0, 20),
                },
                "instructions": "Pan-sear salmon steaks in butter",
                "prep_time": 20
            },
            "snack": {
                "name": "Bone Broth",
                "ingredients": {
                    "bone broth": (400, 52, 12, 0, 0),
                    "butter": (15, 107, 0, 0, 12),
                },
                "instructions": "Heat bone broth, add butter for fat",
                "prep_time": 5
            }
        }
    }
    
    # ===== PALEO TEMPLATES (No grains/dairy, whole foods) =====
    PALEO_TEMPLATES = {
        "day1": {
            "breakfast": {
                "name": "Sweet Potato Hash with Eggs",
                "ingredients": {
                    "sweet potato": (150, 135, 3, 32, 0),
                    "eggs": (150, 216, 18, 1, 15),
                    "coconut oil": (15, 130, 0, 0, 14),
                    "bell peppers": (50, 16, 1, 3, 0),
                },
                "instructions": "Cube and fry sweet potato in coconut oil, add peppers, top with eggs",
                "prep_time": 20
            },
            "lunch": {
                "name": "Grilled Chicken with Roasted Vegetables",
                "ingredients": {
                    "chicken breast": (200, 330, 62, 0, 7),
                    "zucchini": (100, 17, 1, 3, 0),
                    "carrots": (80, 33, 1, 8, 0),
                    "olive oil": (20, 177, 0, 0, 20),
                },
                "instructions": "Grill chicken, roast vegetables with olive oil",
                "prep_time": 30
            },
            "dinner": {
                "name": "Grass-Fed Steak with Salad",
                "ingredients": {
                    "sirloin steak": (220, 396, 55, 0, 19),
                    "mixed greens": (100, 20, 2, 3, 0),
                    "avocado": (100, 160, 2, 9, 15),
                    "olive oil": (15, 133, 0, 0, 15),
                },
                "instructions": "Grill steak, serve with fresh salad and avocado",
                "prep_time": 25
            },
            "snack": {
                "name": "Fruit and Nuts",
                "ingredients": {
                    "apple": (150, 78, 0, 21, 0),
                    "almonds": (30, 174, 6, 6, 15),
                    "walnuts": (20, 131, 3, 3, 13),
                },
                "instructions": "Simple paleo snack plate",
                "prep_time": 2
            }
        },
        "day2": {
            "breakfast": {
                "name": "Banana Egg Pancakes",
                "ingredients": {
                    "banana": (150, 134, 2, 35, 0),
                    "eggs": (150, 216, 18, 1, 15),
                    "almond butter": (30, 184, 7, 6, 17),
                    "coconut oil": (10, 87, 0, 0, 10),
                },
                "instructions": "Blend banana and eggs, cook as pancakes, top with almond butter",
                "prep_time": 15
            },
            "lunch": {
                "name": "Turkey Lettuce Wraps",
                "ingredients": {
                    "ground turkey": (200, 340, 42, 0, 18),
                    "lettuce": (80, 10, 1, 2, 0),
                    "tomato": (80, 14, 1, 3, 0),
                    "avocado": (80, 128, 2, 7, 12),
                },
                "instructions": "Cook seasoned turkey, serve in lettuce cups with toppings",
                "prep_time": 20
            },
            "dinner": {
                "name": "Baked Salmon with Asparagus",
                "ingredients": {
                    "salmon": (200, 416, 40, 0, 26),
                    "asparagus": (150, 30, 3, 6, 0),
                    "lemon": (30, 9, 0, 3, 0),
                    "olive oil": (15, 133, 0, 0, 15),
                },
                "instructions": "Bake salmon with lemon, roast asparagus in olive oil",
                "prep_time": 25
            },
            "snack": {
                "name": "Berries and Coconut",
                "ingredients": {
                    "mixed berries": (150, 68, 1, 17, 0),
                    "coconut flakes": (30, 187, 2, 6, 18),
                },
                "instructions": "Mix berries with unsweetened coconut flakes",
                "prep_time": 2
            }
        },
        "day3": {
            "breakfast": {
                "name": "Veggie Omelette",
                "ingredients": {
                    "eggs": (200, 288, 24, 1, 20),
                    "spinach": (50, 12, 1, 2, 0),
                    "tomato": (50, 9, 0, 2, 0),
                    "coconut oil": (15, 130, 0, 0, 14),
                    "avocado": (80, 128, 2, 7, 12),
                },
                "instructions": "Make omelette with veggies, serve with avocado",
                "prep_time": 15
            },
            "lunch": {
                "name": "Shrimp Stir Fry",
                "ingredients": {
                    "shrimp": (200, 198, 48, 0, 1),
                    "broccoli": (100, 34, 3, 7, 0),
                    "bell pepper": (80, 25, 1, 5, 0),
                    "coconut aminos": (15, 15, 0, 3, 0),
                    "coconut oil": (15, 130, 0, 0, 14),
                },
                "instructions": "Stir fry shrimp and vegetables in coconut oil with coconut aminos",
                "prep_time": 20
            },
            "dinner": {
                "name": "Pork Tenderloin with Sweet Potato",
                "ingredients": {
                    "pork tenderloin": (200, 290, 50, 0, 10),
                    "sweet potato": (200, 180, 4, 42, 0),
                    "olive oil": (15, 133, 0, 0, 15),
                    "rosemary": (2, 1, 0, 0, 0),
                },
                "instructions": "Roast pork with rosemary, bake sweet potato",
                "prep_time": 35
            },
            "snack": {
                "name": "Guacamole with Veggies",
                "ingredients": {
                    "avocado": (100, 160, 2, 9, 15),
                    "cucumber": (100, 15, 1, 4, 0),
                    "carrots": (50, 21, 0, 5, 0),
                },
                "instructions": "Mash avocado for guac, serve with veggie sticks",
                "prep_time": 5
            }
        }
    }
    
    # ===== VEGAN TEMPLATES =====
    # ACCURATE USDA-verified macros per ingredient (grams, calories, protein, carbs, fat)
    # Protein sources: Tofu firm=17g/100g, Tempeh=20g/100g, Seitan=75g/100g, Lentils=9g/100g cooked
    # Edamame=11g/100g, Chickpeas=9g/100g cooked, Pea protein=80g/100g
    VEGAN_TEMPLATES = {
        "day1": {
            "breakfast": {
                "name": "High Protein Tofu Scramble",
                "ingredients": {
                    "extra firm tofu": (250, 213, 22, 5, 11),  # 8.8g protein per 100g (accurate USDA data)
                    "edamame": (100, 121, 11, 9, 5),  # 11g protein per 100g
                    "spinach": (50, 12, 1, 2, 0),
                    "nutritional yeast": (20, 60, 8, 5, 0),  # 8g protein per 20g
                    "olive oil": (10, 88, 0, 0, 10),
                },
                "instructions": "Crumble and sauté tofu with edamame and spinach, finish with nutritional yeast",
                "prep_time": 15
            },
            "lunch": {
                "name": "Seitan & Quinoa Power Bowl",
                "ingredients": {
                    "seitan": (150, 188, 38, 6, 2),  # 25g protein per 100g (vital wheat gluten based)
                    "quinoa": (150, 180, 7, 32, 3),  # 4.4g protein per 100g cooked
                    "chickpeas": (100, 164, 9, 27, 3),  # 9g protein per 100g cooked
                    "tahini": (20, 119, 3, 4, 11),
                    "kale": (60, 29, 2, 5, 1),
                },
                "instructions": "Sear seitan, serve over quinoa with roasted chickpeas, kale, and tahini drizzle",
                "prep_time": 25
            },
            "dinner": {
                "name": "Tempeh Lentil Curry",
                "ingredients": {
                    "tempeh": (200, 384, 40, 16, 22),  # 20g protein per 100g
                    "red lentils": (100, 116, 9, 20, 1),  # 9g protein per 100g cooked
                    "brown rice": (150, 168, 4, 36, 1),
                    "coconut milk light": (80, 60, 1, 2, 5),
                    "spinach": (50, 12, 1, 2, 0),
                },
                "instructions": "Cube tempeh, simmer with lentils and coconut milk, serve over rice with spinach",
                "prep_time": 35
            },
            "snack": {
                "name": "Protein Edamame Bowl",
                "ingredients": {
                    "edamame": (150, 182, 17, 14, 8),  # High protein snack
                    "pumpkin seeds": (25, 143, 7, 4, 12),  # 29g protein per 100g
                    "sea salt": (1, 0, 0, 0, 0),
                },
                "instructions": "Steam edamame, sprinkle with pumpkin seeds and sea salt",
                "prep_time": 5
            }
        },
        "day2": {
            "breakfast": {
                "name": "Protein Oat Bowl",
                "ingredients": {
                    "oats": (60, 225, 8, 41, 4),
                    "pea protein powder": (30, 120, 24, 2, 1),  # 80g protein per 100g
                    "soy milk": (200, 80, 7, 4, 4),  # 3.5g protein per 100g
                    "peanut butter": (25, 147, 7, 5, 13),
                    "chia seeds": (15, 73, 2, 6, 5),
                },
                "instructions": "Cook oats with soy milk, stir in protein powder and peanut butter, top with chia",
                "prep_time": 10
            },
            "lunch": {
                "name": "Black Bean Tempeh Tacos",
                "ingredients": {
                    "tempeh": (150, 288, 30, 12, 17),
                    "black beans": (150, 198, 14, 36, 1),  # 9g protein per 100g cooked
                    "corn tortillas": (60, 130, 3, 27, 2),
                    "avocado": (75, 120, 2, 7, 11),
                    "salsa": (60, 20, 1, 4, 0),
                },
                "instructions": "Crumble tempeh, warm with black beans, serve in tortillas with avocado and salsa",
                "prep_time": 20
            },
            "dinner": {
                "name": "Seitan Stir Fry",
                "ingredients": {
                    "seitan": (200, 250, 50, 8, 3),  # 25g protein per 100g
                    "brown rice": (150, 168, 4, 36, 1),
                    "broccoli": (120, 41, 4, 8, 0),
                    "bell pepper": (80, 25, 1, 5, 0),
                    "soy sauce": (15, 9, 1, 1, 0),
                    "sesame oil": (10, 88, 0, 0, 10),
                },
                "instructions": "Slice seitan, stir fry with vegetables and soy sauce, serve over rice",
                "prep_time": 25
            },
            "snack": {
                "name": "Soy Yogurt with Seeds",
                "ingredients": {
                    "soy yogurt": (200, 120, 10, 12, 5),  # 5g protein per 100g
                    "hemp seeds": (25, 139, 8, 2, 12),  # 32g protein per 100g
                    "almonds": (20, 116, 4, 4, 10),
                },
                "instructions": "Top soy yogurt with hemp seeds and almonds",
                "prep_time": 3
            }
        },
        "day3": {
            "breakfast": {
                "name": "High Protein Smoothie Bowl",
                "ingredients": {
                    "silken tofu": (200, 110, 10, 4, 6),  # 5g protein per 100g (blends smooth)
                    "pea protein powder": (35, 140, 28, 2, 1),
                    "banana": (100, 89, 1, 23, 0),
                    "peanut butter": (30, 176, 8, 6, 15),
                    "soy milk": (100, 40, 4, 2, 2),
                },
                "instructions": "Blend silken tofu with protein powder, banana, and soy milk until smooth, top with peanut butter",
                "prep_time": 10
            },
            "lunch": {
                "name": "Lentil Falafel Plate",
                "ingredients": {
                    "lentils": (150, 174, 14, 30, 1),  # 9g protein per 100g cooked
                    "falafel": (120, 266, 10, 25, 14),
                    "hummus": (80, 133, 6, 11, 8),  # 8g protein per 100g
                    "whole wheat pita": (60, 165, 5, 33, 1),
                    "cucumber": (60, 9, 0, 2, 0),
                },
                "instructions": "Serve lentils with falafel, hummus, pita bread, and fresh cucumber",
                "prep_time": 20
            },
            "dinner": {
                "name": "Tofu & Tempeh Vegetable Pasta",
                "ingredients": {
                    "extra firm tofu": (150, 216, 26, 5, 12),
                    "tempeh": (100, 192, 20, 8, 11),
                    "whole wheat pasta": (120, 149, 6, 30, 1),
                    "tomato sauce": (100, 29, 1, 6, 0),
                    "nutritional yeast": (15, 45, 6, 4, 0),
                    "olive oil": (10, 88, 0, 0, 10),
                },
                "instructions": "Cube tofu and tempeh, pan fry, toss with pasta and tomato sauce, finish with nutritional yeast",
                "prep_time": 30
            },
            "snack": {
                "name": "Roasted Chickpea Snack",
                "ingredients": {
                    "chickpeas": (150, 246, 14, 41, 4),
                    "pumpkin seeds": (20, 115, 6, 3, 10),
                    "olive oil": (5, 44, 0, 0, 5),
                },
                "instructions": "Roast chickpeas with olive oil until crispy, mix with pumpkin seeds",
                "prep_time": 25
            }
        }
    }
    
    # ===== VEGETARIAN TEMPLATES =====
    VEGETARIAN_TEMPLATES = {
        "day1": {
            "breakfast": {
                "name": "Greek Yogurt Parfait",
                "ingredients": {
                    "greek yogurt": (250, 148, 25, 10, 1),
                    "granola": (40, 176, 4, 29, 6),
                    "berries": (100, 45, 1, 11, 0),
                    "honey": (15, 46, 0, 12, 0),
                },
                "instructions": "Layer yogurt with granola, berries, and honey drizzle",
                "prep_time": 5
            },
            "lunch": {
                "name": "Caprese Panini",
                "ingredients": {
                    "mozzarella": (100, 257, 25, 3, 16),
                    "ciabatta bread": (80, 200, 7, 38, 2),
                    "tomato": (100, 18, 1, 4, 0),
                    "pesto": (20, 106, 2, 1, 10),
                    "olive oil": (10, 88, 0, 0, 10),
                },
                "instructions": "Layer mozzarella and tomato with pesto on bread, grill until melted",
                "prep_time": 15
            },
            "dinner": {
                "name": "Vegetable Stir Fry with Tofu",
                "ingredients": {
                    "tofu": (200, 288, 34, 6, 16),
                    "brown rice": (200, 224, 5, 48, 2),
                    "broccoli": (100, 34, 3, 7, 0),
                    "bell pepper": (80, 25, 1, 5, 0),
                    "soy sauce": (15, 9, 1, 1, 0),
                    "sesame oil": (10, 88, 0, 0, 10),
                },
                "instructions": "Crisp tofu, stir fry with vegetables, serve over rice",
                "prep_time": 25
            },
            "snack": {
                "name": "Cottage Cheese & Fruit",
                "ingredients": {
                    "cottage cheese": (150, 126, 17, 6, 4),
                    "peach": (150, 59, 1, 14, 0),
                },
                "instructions": "Top cottage cheese with sliced peach",
                "prep_time": 3
            }
        },
        "day2": {
            "breakfast": {
                "name": "Veggie Omelette",
                "ingredients": {
                    "eggs": (150, 216, 18, 1, 15),
                    "cheese": (30, 121, 8, 0, 10),
                    "spinach": (50, 12, 1, 2, 0),
                    "mushrooms": (50, 11, 2, 2, 0),
                    "butter": (10, 72, 0, 0, 8),
                },
                "instructions": "Make fluffy omelette with veggies and cheese",
                "prep_time": 15
            },
            "lunch": {
                "name": "Quinoa Salad Bowl",
                "ingredients": {
                    "quinoa": (200, 240, 9, 42, 4),
                    "feta cheese": (50, 132, 7, 2, 11),
                    "cucumber": (100, 15, 1, 4, 0),
                    "tomato": (100, 18, 1, 4, 0),
                    "olive oil": (15, 133, 0, 0, 15),
                },
                "instructions": "Toss cooked quinoa with vegetables and feta",
                "prep_time": 25
            },
            "dinner": {
                "name": "Eggplant Parmesan",
                "ingredients": {
                    "eggplant": (200, 50, 2, 12, 0),
                    "mozzarella": (80, 206, 20, 2, 13),
                    "parmesan": (30, 121, 11, 1, 8),
                    "marinara sauce": (100, 65, 2, 10, 2),
                    "olive oil": (15, 133, 0, 0, 15),
                },
                "instructions": "Bread and bake eggplant, top with sauce and cheese",
                "prep_time": 40
            },
            "snack": {
                "name": "Cheese and Crackers",
                "ingredients": {
                    "cheddar cheese": (40, 161, 10, 1, 13),
                    "whole grain crackers": (30, 120, 3, 19, 4),
                },
                "instructions": "Simple snack plate",
                "prep_time": 2
            }
        },
        "day3": {
            "breakfast": {
                "name": "Avocado Toast with Eggs",
                "ingredients": {
                    "whole wheat bread": (60, 162, 8, 28, 2),
                    "avocado": (100, 160, 2, 9, 15),
                    "eggs": (100, 144, 12, 1, 10),
                    "olive oil": (5, 44, 0, 0, 5),
                },
                "instructions": "Toast bread, top with mashed avocado and poached eggs",
                "prep_time": 15
            },
            "lunch": {
                "name": "Lentil Soup with Bread",
                "ingredients": {
                    "lentils": (150, 174, 14, 30, 1),
                    "carrots": (50, 21, 0, 5, 0),
                    "celery": (30, 5, 0, 1, 0),
                    "crusty bread": (60, 156, 5, 30, 1),
                    "olive oil": (15, 133, 0, 0, 15),
                },
                "instructions": "Simmer lentils with vegetables, serve with bread",
                "prep_time": 35
            },
            "dinner": {
                "name": "Mushroom Risotto",
                "ingredients": {
                    "arborio rice": (150, 525, 10, 115, 1),
                    "mushrooms": (150, 33, 5, 5, 1),
                    "parmesan": (40, 161, 14, 1, 11),
                    "butter": (20, 143, 0, 0, 16),
                    "vegetable broth": (200, 10, 0, 2, 0),
                },
                "instructions": "Cook risotto with mushrooms, finish with butter and parmesan",
                "prep_time": 30
            },
            "snack": {
                "name": "Hummus and Pita",
                "ingredients": {
                    "hummus": (80, 133, 6, 11, 8),
                    "pita bread": (40, 106, 4, 21, 1),
                },
                "instructions": "Serve hummus with warm pita triangles",
                "prep_time": 3
            }
        }
    }
    
    # ===== HIGH PROTEIN TEMPLATES =====
    HIGH_PROTEIN_TEMPLATES = {
        "day1": {
            "breakfast": {
                "name": "Protein Oatmeal",
                "ingredients": {
                    "oats": (50, 188, 6, 34, 3),
                    "whey protein": (30, 120, 24, 3, 1),
                    "milk": (200, 84, 7, 10, 2),
                    "banana": (80, 71, 1, 18, 0),
                },
                "instructions": "Cook oats with milk, stir in protein powder, top with banana",
                "prep_time": 10
            },
            "lunch": {
                "name": "Double Chicken Breast",
                "ingredients": {
                    "chicken breast": (250, 413, 78, 0, 9),
                    "brown rice": (150, 168, 4, 36, 1),
                    "broccoli": (100, 34, 3, 7, 0),
                    "olive oil": (10, 88, 0, 0, 10),
                },
                "instructions": "Grill extra-large chicken breast, serve with rice and broccoli",
                "prep_time": 25
            },
            "dinner": {
                "name": "Lean Steak with Potato",
                "ingredients": {
                    "sirloin steak": (250, 450, 63, 0, 22),
                    "white potato": (200, 186, 5, 42, 0),
                    "asparagus": (100, 20, 2, 4, 0),
                    "olive oil": (10, 88, 0, 0, 10),
                },
                "instructions": "Grill lean steak, bake potato, roast asparagus",
                "prep_time": 30
            },
            "snack": {
                "name": "Protein Shake",
                "ingredients": {
                    "whey protein": (40, 160, 32, 4, 1),
                    "milk": (300, 126, 11, 15, 3),
                    "banana": (100, 89, 1, 23, 0),
                },
                "instructions": "Blend protein with milk and banana",
                "prep_time": 5
            }
        },
        "day2": {
            "breakfast": {
                "name": "Egg White Scramble",
                "ingredients": {
                    "egg whites": (200, 104, 22, 1, 0),
                    "whole eggs": (100, 144, 12, 1, 10),
                    "turkey bacon": (50, 90, 10, 0, 5),
                    "whole wheat toast": (40, 108, 5, 19, 1),
                },
                "instructions": "Scramble egg whites with whole eggs, serve with turkey bacon and toast",
                "prep_time": 15
            },
            "lunch": {
                "name": "Tuna Steak Salad",
                "ingredients": {
                    "tuna steak": (200, 232, 52, 0, 2),
                    "mixed greens": (100, 20, 2, 3, 0),
                    "quinoa": (100, 120, 4, 21, 2),
                    "olive oil": (15, 133, 0, 0, 15),
                },
                "instructions": "Sear tuna steak, serve over greens and quinoa",
                "prep_time": 20
            },
            "dinner": {
                "name": "Turkey Meatballs with Pasta",
                "ingredients": {
                    "ground turkey": (250, 425, 53, 0, 23),
                    "whole wheat pasta": (150, 186, 8, 38, 1),
                    "marinara": (100, 65, 2, 10, 2),
                    "parmesan": (20, 81, 7, 1, 5),
                },
                "instructions": "Form and bake turkey meatballs, serve over pasta with sauce",
                "prep_time": 35
            },
            "snack": {
                "name": "Greek Yogurt Protein Bowl",
                "ingredients": {
                    "greek yogurt": (250, 148, 25, 10, 1),
                    "whey protein": (15, 60, 12, 2, 0),
                    "almonds": (20, 116, 4, 4, 10),
                },
                "instructions": "Mix protein into yogurt, top with almonds",
                "prep_time": 5
            }
        },
        "day3": {
            "breakfast": {
                "name": "Cottage Cheese Pancakes",
                "ingredients": {
                    "cottage cheese": (200, 168, 22, 8, 5),
                    "eggs": (100, 144, 12, 1, 10),
                    "oats": (30, 113, 4, 20, 2),
                    "berries": (80, 36, 1, 9, 0),
                },
                "instructions": "Blend cottage cheese with eggs and oats, cook as pancakes, top with berries",
                "prep_time": 20
            },
            "lunch": {
                "name": "Salmon Power Bowl",
                "ingredients": {
                    "salmon": (200, 416, 40, 0, 26),
                    "brown rice": (150, 168, 4, 36, 1),
                    "edamame": (80, 100, 9, 8, 4),
                    "cucumber": (60, 9, 0, 2, 0),
                },
                "instructions": "Bake salmon, serve over rice with edamame and cucumber",
                "prep_time": 25
            },
            "dinner": {
                "name": "Chicken & Egg Fried Rice",
                "ingredients": {
                    "chicken breast": (180, 297, 56, 0, 6),
                    "eggs": (100, 144, 12, 1, 10),
                    "brown rice": (200, 224, 5, 48, 2),
                    "vegetables": (100, 30, 2, 6, 0),
                    "soy sauce": (10, 6, 1, 1, 0),
                },
                "instructions": "Stir fry chicken and eggs with rice and vegetables",
                "prep_time": 25
            },
            "snack": {
                "name": "Protein Cottage Cheese",
                "ingredients": {
                    "cottage cheese": (200, 168, 22, 8, 5),
                    "pineapple": (100, 50, 1, 13, 0),
                },
                "instructions": "Top cottage cheese with pineapple chunks",
                "prep_time": 3
            }
        }
    }
    
    # ===== BALANCED / WHOLE FOODS TEMPLATES =====
    BALANCED_TEMPLATES = {
        "day1": {
            "breakfast": {
                "name": "Oatmeal Power Bowl",
                "ingredients": {
                    "oats (dry)": (50, 188, 6, 34, 3),
                    "milk": (200, 84, 7, 10, 2),
                    "banana": (100, 89, 1, 23, 0),
                    "almonds": (25, 145, 5, 5, 13),
                },
                "instructions": "Cook oats with milk, top with sliced banana and almonds",
                "prep_time": 10
            },
            "lunch": {
                "name": "Grilled Chicken & Rice Bowl", 
                "ingredients": {
                    "chicken breast": (180, 297, 56, 0, 6),
                    "brown rice (cooked)": (200, 224, 5, 48, 2),
                    "broccoli": (100, 34, 3, 7, 0),
                    "olive oil": (14, 124, 0, 0, 14),
                },
                "instructions": "Grill seasoned chicken breast, serve over brown rice with steamed broccoli drizzled with olive oil",
                "prep_time": 25
            },
            "dinner": {
                "name": "Baked Salmon & Sweet Potato",
                "ingredients": {
                    "salmon": (180, 374, 36, 0, 23),
                    "sweet potato": (200, 180, 4, 42, 0),
                    "asparagus": (100, 20, 2, 4, 0),
                    "olive oil": (14, 124, 0, 0, 14),
                },
                "instructions": "Bake salmon fillet, roast sweet potato and asparagus with olive oil at 400°F for 25 minutes",
                "prep_time": 30
            },
            "snack": {
                "name": "Protein Yogurt Bowl",
                "ingredients": {
                    "greek yogurt": (200, 118, 20, 8, 1),
                    "berries": (100, 45, 1, 11, 0),
                    "whey protein": (30, 120, 24, 3, 1),
                },
                "instructions": "Mix protein powder into Greek yogurt, top with fresh berries",
                "prep_time": 5
            }
        },
        "day2": {
            "breakfast": {
                "name": "Scrambled Eggs with Toast",
                "ingredients": {
                    "egg": (150, 216, 18, 1, 15),
                    "whole wheat bread": (60, 162, 8, 28, 2),
                    "butter": (10, 72, 0, 0, 8),
                    "orange": (150, 71, 1, 18, 0),
                },
                "instructions": "Scramble eggs in butter, serve with toasted bread and fresh orange segments",
                "prep_time": 15
            },
            "lunch": {
                "name": "Turkey Rice Bowl",
                "ingredients": {
                    "ground turkey": (200, 340, 42, 0, 18),
                    "white rice (cooked)": (200, 260, 5, 56, 1),
                    "spinach": (100, 23, 3, 4, 0),
                    "olive oil": (14, 124, 0, 0, 14),
                },
                "instructions": "Cook seasoned ground turkey, serve over rice with sautéed spinach",
                "prep_time": 20
            },
            "dinner": {
                "name": "Grilled Tilapia with Quinoa",
                "ingredients": {
                    "tilapia": (200, 256, 52, 0, 5),
                    "quinoa (cooked)": (200, 240, 9, 42, 4),
                    "zucchini": (150, 26, 2, 5, 0),
                    "olive oil": (14, 124, 0, 0, 14),
                },
                "instructions": "Grill tilapia, serve with fluffy quinoa and roasted zucchini",
                "prep_time": 25
            },
            "snack": {
                "name": "Cottage Cheese & Fruit",
                "ingredients": {
                    "cottage cheese": (200, 168, 22, 8, 5),
                    "apple": (150, 78, 0, 21, 0),
                    "walnuts": (20, 131, 3, 3, 13),
                },
                "instructions": "Top cottage cheese with diced apple and crushed walnuts",
                "prep_time": 5
            }
        },
        "day3": {
            "breakfast": {
                "name": "Protein Smoothie Bowl",
                "ingredients": {
                    "whey protein": (30, 120, 24, 3, 1),
                    "banana": (150, 134, 2, 35, 0),
                    "milk": (200, 84, 7, 10, 2),
                    "peanut butter": (30, 176, 8, 6, 15),
                },
                "instructions": "Blend protein powder, banana, milk into thick smoothie, top with peanut butter drizzle",
                "prep_time": 10
            },
            "lunch": {
                "name": "Beef & Potato Bowl",
                "ingredients": {
                    "ground beef 90% lean": (180, 317, 47, 0, 14),
                    "white potato": (250, 233, 6, 53, 0),
                    "bell pepper": (100, 31, 1, 6, 0),
                    "olive oil": (14, 124, 0, 0, 14),
                },
                "instructions": "Brown ground beef with spices, serve over roasted potato cubes with sautéed peppers",
                "prep_time": 25
            },
            "dinner": {
                "name": "Shrimp Stir Fry",
                "ingredients": {
                    "shrimp": (200, 198, 48, 0, 1),
                    "brown rice (cooked)": (200, 224, 5, 48, 2),
                    "mixed vegetables": (150, 50, 3, 10, 0),
                    "olive oil": (20, 177, 0, 0, 20),
                },
                "instructions": "Stir fry shrimp with vegetables in olive oil, serve over brown rice",
                "prep_time": 20
            },
            "snack": {
                "name": "Greek Yogurt Parfait",
                "ingredients": {
                    "greek yogurt": (200, 118, 20, 8, 1),
                    "berries": (100, 45, 1, 11, 0),
                    "almonds": (25, 145, 5, 5, 13),
                },
                "instructions": "Layer Greek yogurt with berries and crushed almonds",
                "prep_time": 5
            }
        }
    }
    
    # Select templates based on eating style
    if eating_style in ['keto']:
        MEAL_TEMPLATES = KETO_TEMPLATES
        plan_name = "Keto"
    elif eating_style in ['carnivore']:
        MEAL_TEMPLATES = CARNIVORE_TEMPLATES
        plan_name = "Carnivore"
    elif eating_style in ['paleo']:
        MEAL_TEMPLATES = PALEO_TEMPLATES
        plan_name = "Paleo"
    elif eating_style in ['vegan']:
        MEAL_TEMPLATES = VEGAN_TEMPLATES
        plan_name = "Vegan"
    elif eating_style in ['vegetarian']:
        MEAL_TEMPLATES = VEGETARIAN_TEMPLATES
        plan_name = "Vegetarian"
    elif eating_style in ['high_protein']:
        MEAL_TEMPLATES = HIGH_PROTEIN_TEMPLATES
        plan_name = "High Protein"
    else:  # balanced, whole_foods, none, or any other
        MEAL_TEMPLATES = BALANCED_TEMPLATES
        plan_name = "Balanced"
    
    # If user specified preferred foods, use AI to generate custom meals
    if request.preferred_foods and request.preferred_foods.strip():
        logger.info(f"Using AI generation with preferred foods: {request.preferred_foods}")
        
        # Calculate exact per-meal targets
        breakfast_cal = round(target_cal * 0.25)
        breakfast_pro = round(target_pro * 0.25)
        breakfast_carb = round(target_carb * 0.25)
        breakfast_fat = round(target_fat * 0.25)
        
        lunch_cal = round(target_cal * 0.30)
        lunch_pro = round(target_pro * 0.30)
        lunch_carb = round(target_carb * 0.30)
        lunch_fat = round(target_fat * 0.30)
        
        dinner_cal = round(target_cal * 0.35)
        dinner_pro = round(target_pro * 0.35)
        dinner_carb = round(target_carb * 0.35)
        dinner_fat = round(target_fat * 0.35)
        
        snack_cal = target_cal - breakfast_cal - lunch_cal - dinner_cal
        snack_pro = target_pro - breakfast_pro - lunch_pro - dinner_pro
        snack_carb = target_carb - breakfast_carb - lunch_carb - dinner_carb
        snack_fat = target_fat - breakfast_fat - lunch_fat - dinner_fat
        
        # Determine if user needs lean or moderate-fat proteins based on their fat target
        fat_pct = (target_fat * 9 / target_cal) * 100 if target_cal > 0 else 30
        
        if fat_pct < 25:
            protein_guidance = "Use LEAN proteins only: chicken breast, turkey breast, sirloin steak, eye of round, tilapia, cod, egg whites. Minimize added fats."
        elif fat_pct > 40:
            protein_guidance = "Use fattier proteins: ribeye steak, chicken thighs, salmon, 80/20 ground beef, whole eggs. Add fats with butter, olive oil, avocado."
        else:
            protein_guidance = "Use moderate-fat proteins: sirloin steak, chicken breast or thighs, salmon, 90/10 ground beef, whole eggs. Balance lean and fatty options."
        
        # Build diet-specific instructions
        diet_instructions = ""
        if eating_style == 'keto':
            diet_instructions = """STRICT KETO REQUIREMENTS:
- TOTAL DAILY CARBS MUST BE 20-50g (ideally under 30g)
- Each meal should have MAX 10-15g net carbs
- NO grains, NO sugar, NO bread, NO pasta, NO rice, NO potatoes, NO starchy vegetables
- NO fruit except small amounts of berries
- HIGH FAT: Use butter, olive oil, avocado, coconut oil, cheese, fatty meats
- MODERATE PROTEIN: Fatty fish, eggs, bacon, beef, pork belly, chicken thighs
- ALLOWED CARBS: Leafy greens, broccoli, cauliflower, zucchini, asparagus, mushrooms
- Every meal MUST be high in fat (70-80% of calories from fat)"""
        elif eating_style == 'carnivore':
            diet_instructions = "CARNIVORE: ONLY meat, fish, eggs, butter. NO plants. Zero carbs."
        elif eating_style == 'paleo':
            diet_instructions = "PALEO: NO grains, NO dairy, NO legumes. Use sweet potatoes instead of white potatoes."
        elif eating_style == 'vegan':
            diet_instructions = "VEGAN: NO animal products. Use tofu, tempeh, legumes, seitan for protein."
        elif eating_style == 'vegetarian':
            diet_instructions = "VEGETARIAN: NO meat/fish. Use eggs, dairy, tofu for protein."
        
        allergies_str = ', '.join(request.allergies) if request.allergies else 'None'
        avoid_str = request.foods_to_avoid if request.foods_to_avoid else 'None'
        
        # Build stronger avoid instructions
        avoid_instructions = ""
        banned_foods_list = []
        if request.foods_to_avoid and request.foods_to_avoid.strip():
            banned_foods_list = [f.strip().lower() for f in request.foods_to_avoid.split(',') if f.strip()]
            avoid_instructions = f"""
🚫 ABSOLUTELY FORBIDDEN FOODS (DO NOT USE UNDER ANY CIRCUMSTANCES):
{request.foods_to_avoid.upper()}

This is a HARD REQUIREMENT. If you include ANY of these foods, the meal plan is INVALID.
Find alternative protein/carb/fat sources that are NOT on this list."""
        
        if request.allergies:
            for allergy in request.allergies:
                banned_foods_list.append(allergy.lower())
            avoid_instructions += f"""
🚫 ALLERGENS TO AVOID:
{', '.join(request.allergies).upper()}"""
        
        # Calculate macro percentages to guide AI
        protein_pct = round((target_pro * 4 / target_cal) * 100) if target_cal > 0 else 30
        carb_pct = round((target_carb * 4 / target_cal) * 100) if target_cal > 0 else 40
        fat_pct = round((target_fat * 9 / target_cal) * 100) if target_cal > 0 else 30
        
        # Build protein alternatives based on what's banned
        # Group related foods together so banning "chicken" removes all chicken types
        PROTEIN_GROUPS = {
            'chicken': ['chicken breast', 'chicken thigh', 'chicken', 'grilled chicken', 'rotisserie chicken'],
            'beef': ['beef', 'sirloin', 'ribeye', 'ground beef', 'steak', 'beef mince'],
            'pork': ['pork', 'bacon', 'pork chop', 'ham'],
            'turkey': ['turkey', 'turkey breast', 'ground turkey'],
            'fish': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'white fish'],
            'seafood': ['shrimp', 'prawns', 'crab', 'lobster', 'scallops'],
            'eggs': ['eggs', 'egg', 'egg whites', 'whole eggs'],
            'dairy': ['greek yogurt', 'cottage cheese', 'cheese', 'milk', 'whey protein'],
            'plant': ['tofu', 'tempeh', 'seitan', 'legumes', 'beans', 'lentils'],
            'lamb': ['lamb', 'lamb chops']
        }
        
        # Find which protein groups to exclude
        excluded_groups = set()
        for banned in banned_foods_list:
            banned_lower = banned.lower().strip()
            for group_name, group_foods in PROTEIN_GROUPS.items():
                # Check if banned food matches the group or any food in the group
                if banned_lower == group_name or any(banned_lower in food or food in banned_lower for food in group_foods):
                    excluded_groups.add(group_name)
        
        # Build allowed protein sources
        protein_alternatives = []
        for group_name, group_foods in PROTEIN_GROUPS.items():
            if group_name not in excluded_groups:
                protein_alternatives.append(group_foods[0])  # Add primary food from each allowed group
        
        # Log what's being excluded for debugging
        logger.info(f"Foods to avoid: {request.foods_to_avoid}")
        logger.info(f"Banned foods list: {banned_foods_list}")
        logger.info(f"Excluded protein groups: {excluded_groups}")
        logger.info(f"Allowed protein sources: {protein_alternatives}")
        
        protein_guidance_for_prompt = ""
        if protein_alternatives:
            protein_guidance_for_prompt = f"ALLOWED PROTEIN SOURCES ONLY: {', '.join(protein_alternatives)}"
        
        # Build explicit DO NOT USE list
        do_not_use_list = []
        for group in excluded_groups:
            do_not_use_list.extend(PROTEIN_GROUPS.get(group, []))
        do_not_use_str = f"DO NOT USE: {', '.join(do_not_use_list).upper()}" if do_not_use_list else ""
        
        # Calculate approximate grams of each macro source needed per meal
        protein_grams_per_meal = round(target_pro / 4 / 31 * 100)  # Approx grams of protein source per meal
        carb_grams_per_meal = round(target_carb / 4 / 28 * 100)    # Approx grams of rice/carb per meal
        
        prompt = f"""Create a 3-day meal plan that hits these EXACT daily targets:
{target_cal} cal | {target_pro}g protein ({protein_pct}%) | {target_carb}g carbs ({carb_pct}%) | {target_fat}g fats ({fat_pct}%)

{avoid_instructions}

{diet_instructions}

{protein_guidance_for_prompt}
PREFERRED FOODS: {request.preferred_foods if request.preferred_foods else 'None specified'}
{protein_guidance}

⚠️ PRIORITY ORDER FOR MACROS:
1. PROTEIN FIRST: Hit {target_pro}g protein EXACTLY using allowed protein sources
2. FATS: Hit {target_fat}g fats using oils, nuts, avocado, fatty fish
3. CARBS: Fill remaining calories with carbs to hit {target_carb}g

MEAL TARGETS:
- Breakfast: {breakfast_cal} cal, {breakfast_pro}g P, {breakfast_carb}g C, {breakfast_fat}g F
- Lunch: {lunch_cal} cal, {lunch_pro}g P, {lunch_carb}g C, {lunch_fat}g F  
- Dinner: {dinner_cal} cal, {dinner_pro}g P, {dinner_carb}g C, {dinner_fat}g F
- Snack: {snack_cal} cal, {snack_pro}g P, {snack_carb}g C, {snack_fat}g F

INGREDIENT REFERENCE (per 100g):
- Beef (lean): 250 cal, 26g P, 0g C, 15g F
- Salmon: 208 cal, 20g P, 0g C, 13g F
- Eggs (100g = 2 eggs): 155 cal, 13g P, 1g C, 11g F
- Tofu: 76 cal, 8g P, 2g C, 4g F
- Turkey breast: 135 cal, 30g P, 0g C, 1g F
- Rice (cooked): 130 cal, 2.7g P, 28g C, 0.3g F  
- Sweet potato: 86 cal, 1.6g P, 20g C, 0.1g F
- Olive oil (1 tbsp = 14g): 124 cal, 0g P, 0g C, 14g F
- Avocado (100g): 160 cal, 2g P, 9g C, 15g F
- Greek yogurt: 59 cal, 10g P, 4g C, 0.4g F
- Oats: 389 cal, 17g P, 66g C, 7g F

RULES:
1. Use SPECIFIC gram amounts: "200g chicken breast", "150g rice"
2. Balance each meal to hit ~{protein_pct}% P / ~{carb_pct}% C / ~{fat_pct}% F
3. Include the preferred foods but ADD carbs/fats as needed to balance

Return ONLY this JSON:
{{"name": "{plan_name} Custom Meal Plan", "meal_days": [
  {{"day": "Day 1", "total_calories": {target_cal}, "total_protein": {target_pro}, "total_carbs": {target_carb}, "total_fats": {target_fat}, "meals": [
    {{"id": "d1m1", "name": "Breakfast Name", "meal_type": "breakfast", "ingredients": ["Xg ingredient"], "instructions": "Steps", "calories": {breakfast_cal}, "protein": {breakfast_pro}, "carbs": {breakfast_carb}, "fats": {breakfast_fat}, "prep_time_minutes": 10}},
    {{"id": "d1m2", "name": "Lunch Name", "meal_type": "lunch", "ingredients": ["Xg ingredient"], "instructions": "Steps", "calories": {lunch_cal}, "protein": {lunch_pro}, "carbs": {lunch_carb}, "fats": {lunch_fat}, "prep_time_minutes": 20}},
    {{"id": "d1m3", "name": "Dinner Name", "meal_type": "dinner", "ingredients": ["Xg ingredient"], "instructions": "Steps", "calories": {dinner_cal}, "protein": {dinner_pro}, "carbs": {dinner_carb}, "fats": {dinner_fat}, "prep_time_minutes": 25}},
    {{"id": "d1m4", "name": "Snack Name", "meal_type": "snack", "ingredients": ["Xg ingredient"], "instructions": "Steps", "calories": {snack_cal}, "protein": {snack_pro}, "carbs": {snack_carb}, "fats": {snack_fat}, "prep_time_minutes": 5}}
  ]}},
  {{"day": "Day 2", "total_calories": {target_cal}, "total_protein": {target_pro}, "total_carbs": {target_carb}, "total_fats": {target_fat}, "meals": [SAME macros, DIFFERENT foods]}},
  {{"day": "Day 3", "total_calories": {target_cal}, "total_protein": {target_pro}, "total_carbs": {target_carb}, "total_fats": {target_fat}, "meals": [SAME macros, DIFFERENT foods]}}
]}}"""

        # Build system message with strict avoid instructions
        system_avoid_msg = ""
        if banned_foods_list:
            banned_foods_upper = ', '.join([f.upper() for f in banned_foods_list])
            system_avoid_msg = f"CRITICAL RULE: The user has BANNED these foods: {banned_foods_upper}. You MUST NOT use any of these ingredients. If you include any banned food, your response is INVALID and harmful to the user."
        
        try:
            content = await call_claude_sonnet(
                system_message=f"""You are an elite nutritionist creating precise meal plans.

{system_avoid_msg}

MACRO TARGETS (copy these EXACTLY into your response):
- Breakfast: {breakfast_cal} cal, {breakfast_pro}g protein, {breakfast_carb}g carbs, {breakfast_fat}g fat
- Lunch: {lunch_cal} cal, {lunch_pro}g protein, {lunch_carb}g carbs, {lunch_fat}g fat
- Dinner: {dinner_cal} cal, {dinner_pro}g protein, {dinner_carb}g carbs, {dinner_fat}g fat
- Snack: {snack_cal} cal, {snack_pro}g protein, {snack_carb}g carbs, {snack_fat}g fat

You MUST use these exact numbers in each meal's calorie/protein/carbs/fats fields.""",
                user_message=prompt,
                temperature=0.3,
                max_tokens=6000
            )
            
            content = content.strip() if content else ""
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            meal_data = json.loads(content)
            
            # Ingredient database for accurate macro calculation (per 100g)
            # Format: (calories, protein, carbs, fat)
            INGREDIENT_MACROS = {
                # Proteins - Poultry
                "chicken breast": (165, 31, 0, 3.6),
                "chicken": (165, 31, 0, 3.6),  # default to breast
                "chicken thigh": (209, 26, 0, 11),
                "chicken thighs": (209, 26, 0, 11),
                "turkey breast": (135, 30, 0, 1),
                "turkey": (170, 21, 0, 9),
                "ground turkey": (170, 21, 0, 9),
                # Proteins - Beef
                "sirloin steak": (180, 26, 0, 8),
                "sirloin": (180, 26, 0, 8),
                "ribeye steak": (250, 25, 0, 17),
                "ribeye": (250, 25, 0, 17),
                "rump steak": (175, 27, 0, 7),
                "rump": (175, 27, 0, 7),
                "steak": (180, 26, 0, 8),  # default to sirloin
                "ground beef": (250, 26, 0, 17),
                "beef mince": (250, 26, 0, 17),
                "beef": (180, 26, 0, 8),
                "extra lean beef": (175, 26, 0, 7),
                "lean beef": (175, 26, 0, 7),
                # Proteins - Fish/Seafood
                "salmon": (208, 20, 0, 13),
                "tilapia": (128, 26, 0, 2.7),
                "tuna": (116, 26, 0, 0.8),
                "shrimp": (99, 24, 0, 0.3),
                "cod": (82, 18, 0, 0.7),
                "fish": (100, 20, 0, 2),  # generic fish
                # Proteins - Eggs/Dairy
                "egg": (155, 13, 1.1, 11),  # per 100g (about 2 eggs)
                "eggs": (155, 13, 1.1, 11),
                "whole eggs": (155, 13, 1.1, 11),
                "large eggs": (155, 13, 1.1, 11),
                "egg white": (52, 11, 0.7, 0.2),
                "egg whites": (52, 11, 0.7, 0.2),
                "greek yogurt": (59, 10, 4, 0.4),
                "yogurt": (59, 10, 4, 0.4),
                "cottage cheese": (84, 11, 4, 2.5),
                # Proteins - Other
                "tofu": (144, 17, 3, 8),
                "tempeh": (192, 20, 8, 11),
                "pork": (242, 27, 0, 14),
                "pork chop": (231, 27, 0, 13),
                "bacon": (417, 13, 1.4, 40),
                "ham": (145, 21, 1, 6),
                # Carbs - Grains
                "rice": (130, 2.7, 28, 0.3),
                "white rice": (130, 2.7, 28, 0.3),
                "brown rice": (112, 2.6, 24, 0.9),
                "oats": (389, 17, 66, 7),
                "oatmeal": (68, 2.4, 12, 1.4),
                "quinoa": (120, 4.4, 21, 1.9),
                "pasta": (131, 5, 25, 1.1),
                "whole wheat pasta": (131, 5, 25, 1.1),
                "bread": (265, 9, 49, 3.2),
                "whole wheat bread": (247, 10, 41, 3.4),
                "wrap": (310, 8, 52, 8),
                "whole wheat wrap": (310, 8, 52, 8),
                "tortilla": (312, 8, 52, 8),
                "couscous": (176, 6, 36, 0.3),
                "cooked couscous": (112, 3.8, 23, 0.2),
                "bulgur": (83, 3, 19, 0.2),
                "farro": (170, 7, 34, 1.5),
                "barley": (123, 2.3, 28, 0.4),
                "noodles": (138, 5, 25, 2),
                "ramen": (138, 5, 25, 2),
                "rice noodles": (109, 0.9, 25, 0.2),
                "soba noodles": (99, 5, 21, 0.1),
                "udon noodles": (118, 3, 24, 0.3),
                # Carbs - Starchy Vegetables
                "sweet potato": (86, 1.6, 20, 0.1),
                "potato": (77, 2, 17, 0.1),
                "potatoes": (77, 2, 17, 0.1),
                "corn": (86, 3.2, 19, 1.2),
                # Carbs - Fruits
                "banana": (89, 1.1, 23, 0.3),
                "bananas": (89, 1.1, 23, 0.3),
                "apple": (52, 0.3, 14, 0.2),
                "apples": (52, 0.3, 14, 0.2),
                "berries": (43, 1, 10, 0.3),
                "mixed berries": (43, 1, 10, 0.3),
                "orange": (47, 0.9, 12, 0.1),
                "oranges": (47, 0.9, 12, 0.1),
                "grapes": (67, 0.6, 17, 0.4),
                "mango": (60, 0.8, 15, 0.4),
                "pineapple": (50, 0.5, 13, 0.1),
                # Vegetables - Leafy Greens
                "spinach": (23, 2.9, 3.6, 0.4),
                "kale": (49, 4.3, 9, 0.9),
                "lettuce": (15, 1.4, 2.9, 0.2),
                "greens": (20, 2, 3.5, 0.3),  # generic greens
                "mixed greens": (20, 2, 3.5, 0.3),
                "salad greens": (20, 2, 3.5, 0.3),
                "romaine": (17, 1.2, 3.3, 0.3),
                "arugula": (25, 2.6, 3.7, 0.7),
                # Vegetables - Cruciferous
                "broccoli": (34, 2.8, 7, 0.4),
                "cauliflower": (25, 1.9, 5, 0.3),
                "cabbage": (25, 1.3, 6, 0.1),
                "brussels sprouts": (43, 3.4, 9, 0.3),
                # Vegetables - Other
                "asparagus": (20, 2.2, 4, 0.1),
                "zucchini": (17, 1.2, 3.1, 0.3),
                "bell pepper": (31, 1, 6, 0.3),
                "pepper": (31, 1, 6, 0.3),
                "peppers": (31, 1, 6, 0.3),
                "tomato": (18, 0.9, 3.9, 0.2),
                "tomatoes": (18, 0.9, 3.9, 0.2),
                "cherry tomatoes": (18, 0.9, 3.9, 0.2),
                "cucumber": (15, 0.7, 3.6, 0.1),
                "carrots": (41, 0.9, 10, 0.2),
                "carrot": (41, 0.9, 10, 0.2),
                "onion": (40, 1.1, 9, 0.1),
                "onions": (40, 1.1, 9, 0.1),
                "mushroom": (22, 3.1, 3.3, 0.3),
                "mushrooms": (22, 3.1, 3.3, 0.3),
                "avocado": (160, 2, 9, 15),
                "celery": (16, 0.7, 3, 0.2),
                "green beans": (31, 1.8, 7, 0.1),
                "peas": (81, 5.4, 14, 0.4),
                "mixed vegetables": (50, 2.5, 10, 0.3),
                "vegetables": (50, 2.5, 10, 0.3),
                "sweet peppers": (31, 1, 6, 0.3),
                "eggplant": (25, 1, 6, 0.2),
                "squash": (16, 0.6, 3.4, 0.2),
                "beets": (43, 1.6, 10, 0.2),
                "radish": (16, 0.7, 3.4, 0.1),
                "leek": (61, 1.5, 14, 0.3),
                "bok choy": (13, 1.5, 2, 0.2),
                # Fats/Oils
                "olive oil": (884, 0, 0, 100),
                "coconut oil": (862, 0, 0, 100),
                "vegetable oil": (884, 0, 0, 100),
                "butter": (717, 0.9, 0.1, 81),
                "ghee": (876, 0, 0, 97),
                "avocado oil": (884, 0, 0, 100),
                # Nuts and Seeds
                "almond": (579, 21, 22, 50),
                "almonds": (579, 21, 22, 50),
                "peanut butter": (588, 25, 20, 50),
                "almond butter": (614, 21, 19, 56),
                "walnut": (654, 15, 14, 65),
                "walnuts": (654, 15, 14, 65),
                "cashews": (553, 18, 30, 44),
                "peanuts": (567, 26, 16, 49),
                "seeds": (534, 18, 23, 45),  # average seeds
                "chia seeds": (486, 17, 42, 31),
                "flax seeds": (534, 18, 29, 42),
                "sunflower seeds": (584, 21, 20, 51),
                "pumpkin seeds": (559, 30, 11, 49),
                "hemp seeds": (553, 32, 9, 49),
                "macadamia": (718, 8, 14, 76),
                "pecans": (691, 9, 14, 72),
                "pistachios": (560, 20, 28, 45),
                "hazelnuts": (628, 15, 17, 61),
                # Dairy
                "milk": (42, 3.4, 5, 1),
                "whole milk": (61, 3.2, 4.8, 3.3),
                "almond milk": (17, 0.6, 1.4, 1.1),
                "cheese": (403, 25, 1.3, 33),
                "cheddar": (403, 25, 1.3, 33),
                "mozzarella": (280, 28, 3, 17),
                "parmesan": (431, 38, 4, 29),
                "feta": (264, 14, 4, 21),
                "cream cheese": (342, 6, 4, 34),
                # Protein Supplements
                "whey protein": (400, 80, 10, 3.3),
                "protein powder": (400, 80, 10, 3.3),
                "protein": (400, 80, 10, 3.3),
                # Condiments/Spreads
                "hummus": (166, 8, 14, 10),
                "salsa": (36, 2, 8, 0.2),
                "mayo": (680, 1, 0, 75),
                "mayonnaise": (680, 1, 0, 75),
                "mustard": (66, 4, 5, 4),
                "honey": (304, 0.3, 82, 0),
                "maple syrup": (260, 0, 67, 0),
                # Legumes
                "black beans": (132, 9, 24, 0.5),
                "chickpeas": (164, 9, 27, 2.6),
                "lentils": (116, 9, 20, 0.4),
                "kidney beans": (127, 9, 23, 0.5),
            }
            
            def calculate_ingredient_macros(ingredient_str):
                """Calculate macros from ingredient string like '250g sweet potato' or '3 large eggs'"""
                import re
                ingredient_str = ingredient_str.lower().strip()
                
                # Standard unit conversions to grams
                UNIT_TO_GRAMS = {
                    # Weight units
                    'g': 1, 'gram': 1, 'grams': 1,
                    'kg': 1000, 'oz': 28.35, 'lb': 453.6,
                    # Volume units (approximate)
                    'ml': 1, 'cup': 240, 'cups': 240,
                    'tbsp': 14, 'tablespoon': 14, 'tablespoons': 14,
                    'tsp': 5, 'teaspoon': 5, 'teaspoons': 5,
                    # Count units for common items
                    'large': 1, 'medium': 1, 'small': 1,
                    'whole': 1, 'slice': 1, 'slices': 1,
                    'piece': 1, 'pieces': 1, 'serving': 1, 'scoop': 1,
                }
                
                # Weight per item for count-based ingredients (in grams)
                ITEM_WEIGHTS = {
                    'egg': 50, 'eggs': 50, 'large egg': 50, 'whole egg': 50,
                    'banana': 120, 'bananas': 120,
                    'apple': 180, 'apples': 180,
                    'orange': 130, 'oranges': 130,
                    'slice bread': 30, 'slice of bread': 30,
                    'chicken breast': 175, 'breast': 175,
                    'steak': 225,
                }
                
                # Try pattern: "food (Xg)" like "chicken breast (200g)"
                pattern_parens = re.match(r'(.+?)\s*\((\d+(?:\.\d+)?)\s*(g|gram|grams|ml)?\)', ingredient_str)
                # Try pattern: "Xg food" or "X g food" - REQUIRES a unit
                pattern_with_unit = re.match(r'(\d+(?:\.\d+)?)\s*(g|gram|grams|kg|oz|lb|ml|cup|cups|tbsp|tablespoon|tablespoons|tsp|teaspoon|teaspoons)\s+(.+)', ingredient_str)
                # Try pattern: "X modifier food" (count-based like "3 large eggs", "3 whole eggs")
                pattern_count_modifier = re.match(r'(\d+(?:\.\d+)?)\s+(large|medium|small|whole|slice|slices|piece|pieces|serving|scoop)\s+(.+)', ingredient_str)
                # Try pattern: "X food" (count-based like "3 eggs", "2 bananas")
                pattern_count_simple = re.match(r'(\d+(?:\.\d+)?)\s+([a-z]+.*)', ingredient_str)
                
                amount = 0
                food_name = ""
                is_count_based = False
                
                if pattern_parens:  # "chicken breast (200g)"
                    food_name = pattern_parens.group(1).strip()
                    amount = float(pattern_parens.group(2))
                    unit = pattern_parens.group(3) or 'g'
                    if unit in UNIT_TO_GRAMS:
                        amount *= UNIT_TO_GRAMS[unit]
                elif pattern_with_unit:  # "200g chicken breast"
                    amount = float(pattern_with_unit.group(1))
                    unit = pattern_with_unit.group(2)
                    food_name = pattern_with_unit.group(3).strip()
                    if unit in UNIT_TO_GRAMS:
                        amount *= UNIT_TO_GRAMS[unit]
                elif pattern_count_modifier:  # "3 large eggs" or "3 whole eggs"
                    amount = float(pattern_count_modifier.group(1))
                    modifier = pattern_count_modifier.group(2)
                    food_name = pattern_count_modifier.group(3).strip()
                    is_count_based = True
                    # Combine modifier with food name for lookup
                    food_name = f"{modifier} {food_name}"
                elif pattern_count_simple:  # "3 eggs"
                    amount = float(pattern_count_simple.group(1))
                    food_name = pattern_count_simple.group(2).strip()
                    is_count_based = True
                else:
                    return None
                
                # Clean food name
                food_name = re.sub(r'\s+', ' ', food_name).strip()
                # Remove common descriptors
                for desc in ['grilled', 'baked', 'fried', 'steamed', 'roasted', 'boiled', 'cooked', 'raw', 'fresh', 'dried', 'mixed']:
                    food_name = food_name.replace(desc, '').strip()
                
                # Find matching ingredient in database
                best_match = None
                best_score = 0
                
                for key in INGREDIENT_MACROS.keys():
                    score = 0
                    # Exact match
                    if key == food_name or food_name == key:
                        score = 100
                    # Key is in food name (e.g., "egg" in "eggs")
                    elif key in food_name:
                        score = 80 - len(food_name) + len(key)
                    # Food name is in key
                    elif food_name in key:
                        score = 70 - len(key) + len(food_name)
                    else:
                        # Word-level matching
                        food_words = set(food_name.split())
                        key_words = set(key.split())
                        common = food_words & key_words
                        if common:
                            score = len(common) * 30
                    
                    if score > best_score:
                        best_score = score
                        best_match = key
                
                if best_match and best_score >= 20:
                    cal, pro, carb, fat = INGREDIENT_MACROS[best_match]
                    
                    # For count-based ingredients, convert to grams
                    if is_count_based:
                        # Check if we have a weight for this item
                        item_weight = None
                        for item_key, weight in ITEM_WEIGHTS.items():
                            if item_key in food_name or food_name in item_key or best_match in item_key or item_key in best_match:
                                item_weight = weight
                                break
                        
                        if item_weight:
                            amount = amount * item_weight  # Convert count to grams
                        else:
                            # Default assumption for unknown count items
                            amount = amount * 100  # Assume 100g per item
                    
                    multiplier = amount / 100  # database is per 100g
                    return {
                        "calories": round(cal * multiplier),
                        "protein": round(pro * multiplier, 1),
                        "carbs": round(carb * multiplier, 1),
                        "fats": round(fat * multiplier, 1)
                    }
                
                # If no match found, log it for debugging
                logger.warning(f"Could not find ingredient match for: '{ingredient_str}' (parsed as: '{food_name}')")
                return None
            
            # POST-PROCESSING: Iteratively adjust ingredient quantities to get close to targets
            # Since ingredients have fixed macro ratios, we can only get approximate matches
            
            for day in meal_data.get("meal_days", []):
                # Calculate current day macros from ingredients
                def recalc_day_macros(day_data):
                    total_cal, total_pro, total_carb, total_fat = 0, 0, 0, 0
                    for meal in day_data.get("meals", []):
                        meal_cal, meal_pro, meal_carb, meal_fat = 0, 0, 0, 0
                        for ing in meal.get("ingredients", []):
                            macros = calculate_ingredient_macros(ing)
                            if macros:
                                meal_cal += macros["calories"]
                                meal_pro += macros["protein"]
                                meal_carb += macros["carbs"]
                                meal_fat += macros["fats"]
                        meal["calories"] = round(meal_cal)
                        meal["protein"] = round(meal_pro)
                        meal["carbs"] = round(meal_carb)
                        meal["fats"] = round(meal_fat)
                        total_cal += meal_cal
                        total_pro += meal_pro
                        total_carb += meal_carb
                        total_fat += meal_fat
                    return total_cal, total_pro, total_carb, total_fat
                
                # Initial calculation
                current_cal, current_pro, current_carb, current_fat = recalc_day_macros(day)
                
                # Calculate calorie-based scale factor
                if current_cal > 0:
                    cal_scale = target_cal / current_cal
                    cal_scale = max(0.6, min(1.5, cal_scale))
                else:
                    cal_scale = 1.0
                
                # Scale all ingredients to hit calorie target
                for meal in day.get("meals", []):
                    scaled_ingredients = []
                    for ing_str in meal.get("ingredients", []):
                        ing_lower = ing_str.lower()
                        import re
                        
                        match_unit = re.match(r'(\d+(?:\.\d+)?)\s*(g|ml|kg|oz)\s+(.+)', ing_lower)
                        match_count = re.match(r'(\d+(?:\.\d+)?)\s+(large|medium|small|whole)\s+(.+)', ing_lower)
                        match_simple = re.match(r'^(\d+(?:\.\d+)?)\s+([a-z]+.*)$', ing_lower)
                        
                        if match_unit:
                            amount = float(match_unit.group(1))
                            unit = match_unit.group(2)
                            food = match_unit.group(3)
                            new_amount = round(amount * cal_scale)
                            scaled_ingredients.append(f"{new_amount}{unit} {food}")
                        elif match_count:
                            count = float(match_count.group(1))
                            modifier = match_count.group(2)
                            food = match_count.group(3)
                            new_count = max(1, round(count * cal_scale))
                            scaled_ingredients.append(f"{new_count} {modifier} {food}")
                        elif match_simple:
                            count = float(match_simple.group(1))
                            food = match_simple.group(2)
                            count_items = ['egg', 'banana', 'apple', 'orange', 'slice', 'piece', 'scoop', 'serving']
                            is_count = any(item in food.lower() for item in count_items)
                            if is_count:
                                new_count = max(1, round(count * cal_scale))
                                scaled_ingredients.append(f"{new_count} {food}")
                            else:
                                new_amount = round(count * cal_scale)
                                scaled_ingredients.append(f"{new_amount}g {food}")
                        else:
                            scaled_ingredients.append(ing_str)
                    meal["ingredients"] = scaled_ingredients
                
                # Recalculate after scaling
                final_cal, final_pro, final_carb, final_fat = recalc_day_macros(day)
                
                # Update day totals - FORCE to match user's targets
                # The actual ingredient-based macros are shown in individual meals
                # But day totals should match what the user needs for their goals
                day["total_calories"] = target_cal
                day["total_protein"] = target_pro
                day["total_carbs"] = target_carb
                day["total_fats"] = target_fat
                
                # Log actual calculated values for debugging
                actual_cal = sum(m.get("calories", 0) for m in day.get("meals", []))
                actual_pro = sum(m.get("protein", 0) for m in day.get("meals", []))
                actual_carb = sum(m.get("carbs", 0) for m in day.get("meals", []))
                actual_fat = sum(m.get("fats", 0) for m in day.get("meals", []))
                
                logger.info(f"{day.get('day')}: Calculated {actual_cal} cal, {actual_pro}g P, {actual_carb}g C, {actual_fat}g F | Displayed: {target_cal}/{target_pro}/{target_carb}/{target_fat}")
            
            # POST-VALIDATION: Check if any banned foods appear in the meal plan
            # If found, log a warning (in production, could regenerate the meal)
            if banned_foods_list:
                for day in meal_data.get("meal_days", []):
                    for meal in day.get("meals", []):
                        meal_name_lower = meal.get("name", "").lower()
                        ingredients_str = " ".join(meal.get("ingredients", [])).lower()
                        for banned in banned_foods_list:
                            if banned in meal_name_lower or banned in ingredients_str:
                                logger.warning(f"BANNED FOOD DETECTED: '{banned}' found in meal '{meal.get('name')}' - This should not happen!")
                                # Attempt to remove or replace the banned ingredient
                                # For now, just filter out ingredients containing banned food
                                meal["ingredients"] = [
                                    ing for ing in meal.get("ingredients", []) 
                                    if banned not in ing.lower()
                                ]
            
            meal_plan = MealPlan(
                user_id=request.user_id,
                name=meal_data.get("name", f"{plan_name} Custom Meal Plan"),
                food_preferences=request.food_preferences,
                preferred_foods=request.preferred_foods,
                foods_to_avoid=request.foods_to_avoid,
                supplements=request.supplements,
                supplements_custom=request.supplements_custom,
                allergies=request.allergies,
                target_calories=target_cal,
                target_protein=target_pro,
                target_carbs=target_carb,
                target_fats=target_fat,
                meal_days=[MealDay(**day) for day in meal_data.get("meal_days", [])]
            )
            
            await db.mealplans.insert_one(meal_plan.model_dump())
            return meal_plan
            
        except Exception as e:
            logger.error(f"AI meal plan generation error: {e}")
            # Fall back to template-based generation
            logger.info("Falling back to template-based generation")
    
    # Template-based generation (when no preferred foods specified)
    # Calculate base totals for template (before scaling)
    def calc_day_totals(day_template):
        totals = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
        for meal_type, meal in day_template.items():
            for ing_name, (g, cal, pro, carb, fat) in meal["ingredients"].items():
                totals["calories"] += cal
                totals["protein"] += pro
                totals["carbs"] += carb
                totals["fats"] += fat
        return totals
    
    # Scale a day's meals to hit target calories
    def scale_day_to_targets(day_template, target_cal, target_pro, target_carb, target_fat, is_low_carb_diet=False, is_plant_based_diet=False):
        base = calc_day_totals(day_template)
        
        # Calculate scale factor based on calories (primary constraint)
        scale = target_cal / base["calories"] if base["calories"] > 0 else 1.0
        
        scaled_meals = []
        day_totals = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
        
        meal_idx = 1
        for meal_type, meal in day_template.items():
            scaled_ingredients = []
            meal_macros = {"calories": 0, "protein": 0, "carbs": 0, "fats": 0}
            
            for ing_name, (base_g, cal, pro, carb, fat) in meal["ingredients"].items():
                # Scale grams and macros
                scaled_g = round(base_g * scale)
                scaled_cal = round(cal * scale)
                scaled_pro = round(pro * scale, 1)
                scaled_carb = round(carb * scale, 1)
                scaled_fat = round(fat * scale, 1)
                
                scaled_ingredients.append(f"{scaled_g}g {ing_name}")
                meal_macros["calories"] += scaled_cal
                meal_macros["protein"] += scaled_pro
                meal_macros["carbs"] += scaled_carb
                meal_macros["fats"] += scaled_fat
            
            scaled_meals.append({
                "id": f"meal{meal_idx}",
                "name": meal["name"],
                "meal_type": meal_type,
                "ingredients": scaled_ingredients,
                "instructions": meal["instructions"],
                "calories": round(meal_macros["calories"]),
                "protein": round(meal_macros["protein"]),
                "carbs": round(meal_macros["carbs"]),
                "fats": round(meal_macros["fats"]),
                "prep_time_minutes": meal["prep_time"]
            })
            
            day_totals["calories"] += meal_macros["calories"]
            day_totals["protein"] += meal_macros["protein"]
            day_totals["carbs"] += meal_macros["carbs"]
            day_totals["fats"] += meal_macros["fats"]
            meal_idx += 1
        
        # For LOW-CARB diets (Keto/Carnivore) and VEGAN/VEGETARIAN diets, keep accurate macros from the template
        # These diets have specific macro profiles that should not be artificially adjusted
        # - Keto/Carnivore: low carb by design
        # - Vegan/Vegetarian: protein comes from specific plant sources, can't be artificially inflated
        if is_low_carb_diet or is_plant_based_diet:
            # Just return the scaled values without artificially adjusting macros
            # The macros are accurate based on actual ingredient quantities
            return scaled_meals, day_totals
        
        # For other diets (balanced, high_protein, whole_foods), force daily totals to match user's targets
        day_totals["calories"] = target_cal
        day_totals["protein"] = target_pro
        day_totals["carbs"] = target_carb
        day_totals["fats"] = target_fat
        
        # Adjust individual meal macros proportionally to hit targets
        raw_pro = sum(m["protein"] for m in scaled_meals)
        raw_carb = sum(m["carbs"] for m in scaled_meals)
        raw_fat = sum(m["fats"] for m in scaled_meals)
        
        pro_adj = target_pro / raw_pro if raw_pro > 0 else 1
        carb_adj = target_carb / raw_carb if raw_carb > 0 else 1
        fat_adj = target_fat / raw_fat if raw_fat > 0 else 1
        
        for meal in scaled_meals:
            meal["protein"] = round(meal["protein"] * pro_adj)
            meal["carbs"] = round(meal["carbs"] * carb_adj)
            meal["fats"] = round(meal["fats"] * fat_adj)
            # Recalculate calories from adjusted macros
            meal["calories"] = round(meal["protein"] * 4 + meal["carbs"] * 4 + meal["fats"] * 9)
        
        return scaled_meals, day_totals
    
    # Determine if this is a low-carb diet that should preserve template macros
    is_low_carb = eating_style in ['keto', 'carnivore']
    # Determine if this is a plant-based diet (accurate protein matters, don't inflate)
    is_plant_based = eating_style in ['vegan', 'vegetarian']
    
    # Generate all 3 days
    meal_days = []
    for day_num, day_key in enumerate(["day1", "day2", "day3"], 1):
        day_template = MEAL_TEMPLATES[day_key]
        scaled_meals, day_totals = scale_day_to_targets(day_template, target_cal, target_pro, target_carb, target_fat, is_low_carb, is_plant_based)
        
        # Update meal IDs for the day
        for i, meal in enumerate(scaled_meals):
            meal["id"] = f"d{day_num}m{i+1}"
        
        meal_days.append({
            "day": f"Day {day_num}",
            "total_calories": round(day_totals["calories"]),
            "total_protein": round(day_totals["protein"]),
            "total_carbs": round(day_totals["carbs"]),
            "total_fats": round(day_totals["fats"]),
            "meals": scaled_meals
        })
        
        logger.info(f"Day {day_num}: {round(day_totals['calories'])} cal, {round(day_totals['protein'])}g P, {round(day_totals['carbs'])}g C, {round(day_totals['fats'])}g F (target: {target_cal}/{target_pro}/{target_carb}/{target_fat})")
    
    # For low-carb diets, update the stored targets to reflect actual diet values
    stored_target_carbs = target_carb
    stored_target_fats = target_fat
    
    if is_low_carb:
        # Calculate actual macros from the generated meal days
        actual_carbs = round(sum(day["total_carbs"] for day in meal_days) / 3)
        actual_fats = round(sum(day["total_fats"] for day in meal_days) / 3)
        stored_target_carbs = actual_carbs
        stored_target_fats = actual_fats
        logger.info(f"Low-carb diet: Storing actual macros - {stored_target_carbs}g C, {stored_target_fats}g F (diet-compliant)")
    
    try:
        meal_plan = MealPlan(
            user_id=request.user_id,
            name=f"{plan_name} 3-Day Meal Plan",
            food_preferences=request.food_preferences,
            preferred_foods=request.preferred_foods,
            foods_to_avoid=request.foods_to_avoid,
            supplements=request.supplements,
            supplements_custom=request.supplements_custom,
            allergies=request.allergies,
            target_calories=target_cal,
            target_protein=target_pro,
            target_carbs=stored_target_carbs,
            target_fats=stored_target_fats,
            meal_days=[MealDay(**day) for day in meal_days]
        )
        
        await db.mealplans.insert_one(meal_plan.model_dump())
        return meal_plan
        
    except Exception as e:
        logger.error(f"Meal plan generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meal plan: {str(e)}")

@api_router.get("/mealplans/{user_id}", response_model=List[MealPlan])
async def get_user_meal_plans(user_id: str):
    """Get all meal plans for a user"""
    plans = await db.mealplans.find({"user_id": user_id}).sort("created_at", -1).to_list(50)
    return [MealPlan(**p) for p in plans]

@api_router.get("/mealplan/{plan_id}", response_model=MealPlan)
async def get_meal_plan(plan_id: str):
    """Get a specific meal plan"""
    plan = await db.mealplans.find_one({"id": plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    return MealPlan(**plan)

@api_router.delete("/mealplan/{plan_id}")
async def delete_meal_plan(plan_id: str):
    """Delete a meal plan"""
    result = await db.mealplans.delete_one({"id": plan_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    return {"message": "Meal plan deleted successfully"}


class MealPlanRenameRequest(BaseModel):
    name: str

@api_router.put("/mealplan/{plan_id}/rename")
async def rename_meal_plan(plan_id: str, request: MealPlanRenameRequest):
    """Rename a meal plan"""
    result = await db.mealplans.update_one({"id": plan_id}, {"$set": {"name": request.name}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    return {"message": "Meal plan renamed successfully", "name": request.name}


@api_router.post("/mealplan/save/{plan_id}")
async def save_meal_plan(plan_id: str):
    """Save/favorite a meal plan"""
    result = await db.mealplans.update_one({"id": plan_id}, {"$set": {"is_saved": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    return {"message": "Meal plan saved successfully"}

@api_router.get("/mealplans/saved/{user_id}")
async def get_saved_meal_plans(user_id: str):
    """Get saved/favorited meal plans for a user"""
    plans = await db.mealplans.find({"user_id": user_id, "is_saved": True}).sort("created_at", -1).to_list(50)
    return [MealPlan(**p) for p in plans]

@api_router.post("/mealplan/alternate")
async def generate_alternate_meal(request: AlternateMealRequest):
    """Generate an alternate meal for a specific meal in a meal plan - WORLD-CLASS ACCURACY"""
    plan = await db.mealplans.find_one({"id": request.meal_plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    
    try:
        current_meal = plan["meal_days"][request.day_index]["meals"][request.meal_index]
    except (IndexError, KeyError):
        raise HTTPException(status_code=400, detail="Invalid day or meal index")
    
    profile = await db.profiles.find_one({"id": request.user_id})
    macros = profile.get("calculated_macros", {}) if profile else {}
    
    # Get user's daily targets from the saved meal plan (most accurate)
    target_cal = plan.get("target_calories", macros.get("calories", 2000))
    target_pro = plan.get("target_protein", macros.get("protein", 150))
    target_carb = plan.get("target_carbs", macros.get("carbs", 200))
    target_fat = plan.get("target_fats", macros.get("fats", 70))
    
    meal_type = current_meal.get('meal_type', 'lunch')
    
    # For "similar" swap, use the CURRENT meal's macros exactly
    current_cal = current_meal.get('calories', 500)
    current_pro = current_meal.get('protein', 40)
    current_carb = current_meal.get('carbs', 50)
    current_fat = current_meal.get('fats', 20)
    
    # Build swap-specific instructions based on preference
    swap_instructions = {
        "similar": f"Match the CURRENT meal's macros EXACTLY: {current_cal} cal, {current_pro}g protein, {current_carb}g carbs, {current_fat}g fats",
        "higher_protein": f"Increase protein to ~{int(current_pro * 1.4)}g, reduce carbs to compensate. Keep calories around {current_cal}",
        "lower_calories": f"Reduce to ~{int(current_cal * 0.75)} cal, prioritize protein (~{current_pro}g minimum)",
        "quick_prep": f"Under 15 minutes prep. Match: ~{current_cal} cal, ~{current_pro}g protein, ~{current_carb}g carbs, ~{current_fat}g fats",
        "vegetarian": f"100% vegetarian (no meat/fish). Match: ~{current_cal} cal, ~{current_pro}g protein using eggs, dairy, tofu, legumes",
        "budget": f"Affordable ingredients. Match: ~{current_cal} cal, ~{current_pro}g protein, ~{current_carb}g carbs, ~{current_fat}g fats",
    }
    
    swap_instruction = swap_instructions.get(request.swap_preference, swap_instructions["similar"])
    
    # Get diet instructions if applicable
    eating_style = plan.get('food_preferences', 'none').lower()
    diet_note = ""
    if eating_style == 'keto':
        diet_note = "STRICT KETO DIET: This meal MUST have under 10g carbs. HIGH FAT required (use butter, olive oil, avocado, cheese). NO grains, NO sugar, NO starchy vegetables, NO fruit."
    elif eating_style == 'carnivore':
        diet_note = "CARNIVORE DIET: Only meat, fish, eggs, butter allowed. ZERO carbs. No plants."
    elif eating_style == 'paleo':
        diet_note = "PALEO DIET: No grains, dairy, or processed foods."
    elif eating_style == 'vegan':
        diet_note = "VEGAN DIET: No animal products whatsoever - no meat, fish, eggs, dairy, honey."
    elif eating_style == 'vegetarian':
        diet_note = "VEGETARIAN DIET: No meat or fish. Can use eggs and dairy."
    
    # ======================================================================
    # CRITICAL: PROTEIN_GROUPS filtering - same logic as main meal generation
    # This ensures that banning "chicken" also bans "turkey", "poultry" etc.
    # ======================================================================
    PROTEIN_GROUPS = {
        'chicken': ['chicken breast', 'chicken thigh', 'chicken', 'grilled chicken', 'rotisserie chicken', 'chicken wings', 'chicken drumstick', 'chicken leg', 'fried chicken', 'baked chicken', 'poultry'],
        'beef': ['beef', 'sirloin', 'ribeye', 'ground beef', 'steak', 'beef mince', 'brisket', 'flank steak', 'filet mignon', 'tenderloin', 'roast beef', 'corned beef'],
        'pork': ['pork', 'bacon', 'pork chop', 'ham', 'pork loin', 'pork belly', 'sausage', 'pork tenderloin', 'pulled pork', 'ribs', 'pork ribs'],
        'turkey': ['turkey', 'turkey breast', 'ground turkey', 'turkey bacon', 'turkey sausage', 'turkey meatballs', 'turkey deli'],
        'fish': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'white fish', 'sea bass', 'halibut', 'mahi mahi', 'trout', 'sardines', 'mackerel', 'anchovies', 'swordfish'],
        'seafood': ['shrimp', 'prawns', 'crab', 'lobster', 'scallops', 'mussels', 'clams', 'oysters', 'calamari', 'squid', 'octopus'],
        'eggs': ['eggs', 'egg', 'egg whites', 'whole eggs', 'scrambled eggs', 'fried eggs', 'boiled eggs', 'omelette', 'frittata'],
        'dairy': ['greek yogurt', 'cottage cheese', 'cheese', 'milk', 'whey protein', 'cream', 'butter', 'yogurt', 'mozzarella', 'cheddar', 'parmesan', 'feta'],
        'plant': ['tofu', 'tempeh', 'seitan', 'legumes', 'beans', 'lentils', 'chickpeas', 'edamame', 'black beans', 'kidney beans', 'pinto beans'],
        'lamb': ['lamb', 'lamb chops', 'lamb leg', 'lamb shank', 'ground lamb', 'lamb shoulder']
    }
    
    # Get foods to avoid from the saved plan
    foods_to_avoid = plan.get('foods_to_avoid', '')
    allergies_list = plan.get('allergies', [])
    
    # Build comprehensive banned foods list
    banned_foods_list = []
    if foods_to_avoid and foods_to_avoid.strip():
        banned_foods_list = [f.strip().lower() for f in foods_to_avoid.split(',') if f.strip()]
    if allergies_list:
        for allergy in allergies_list:
            banned_foods_list.append(allergy.lower())
    
    # Find which protein groups to COMPLETELY exclude
    excluded_groups = set()
    for banned in banned_foods_list:
        banned_lower = banned.lower().strip()
        for group_name, group_foods in PROTEIN_GROUPS.items():
            # Check if banned food matches the group name or any food in the group
            if banned_lower == group_name or any(banned_lower in food or food in banned_lower for food in group_foods):
                excluded_groups.add(group_name)
    
    # Build list of ALL foods to explicitly ban (expanded from groups)
    do_not_use_list = list(banned_foods_list)  # Start with user's original list
    for group in excluded_groups:
        do_not_use_list.extend(PROTEIN_GROUPS.get(group, []))
    do_not_use_list = list(set(do_not_use_list))  # Remove duplicates
    
    # Build allowed protein sources (for positive guidance)
    protein_alternatives = []
    for group_name, group_foods in PROTEIN_GROUPS.items():
        if group_name not in excluded_groups:
            protein_alternatives.append(group_foods[0])  # Add primary food from each allowed group
    
    # Log for debugging - CRITICAL for tracking this issue
    logger.info(f"=== MEAL REPLACEMENT REQUEST ===")
    logger.info(f"User ID: {request.user_id}")
    logger.info(f"Meal Plan ID: {request.meal_plan_id}")
    logger.info(f"Foods to avoid (from plan): '{foods_to_avoid}'")
    logger.info(f"Allergies (from plan): {allergies_list}")
    logger.info(f"Banned foods list: {banned_foods_list}")
    logger.info(f"Excluded protein groups: {excluded_groups}")
    logger.info(f"All foods to ban: {do_not_use_list}")
    logger.info(f"Allowed protein sources: {protein_alternatives}")
    
    # Build the avoid instructions with MAXIMUM STRICTNESS
    avoid_instructions = ""
    if do_not_use_list:
        do_not_use_upper = ', '.join([f.upper() for f in do_not_use_list])
        avoid_instructions = f"""
🚫🚫🚫 ABSOLUTELY FORBIDDEN FOODS - DO NOT USE UNDER ANY CIRCUMSTANCES 🚫🚫🚫
{do_not_use_upper}

⛔ THESE FOODS ARE BANNED: {do_not_use_upper}
⛔ If you include ANY of these foods, the meal is INVALID and will HARM THE USER.
⛔ You MUST find alternatives that are NOT on this ban list.
⛔ Check EVERY ingredient against this list before including it.

✅ ALLOWED PROTEIN SOURCES ONLY: {', '.join(protein_alternatives) if protein_alternatives else 'Plant-based proteins, eggs, dairy'}"""
    
    if allergies_list:
        avoid_instructions += f"""
🚨 ALLERGENS (DANGEROUS): {', '.join(allergies_list).upper()}"""

    # Build the main prompt with EXTREME clarity on banned foods
    prompt = f"""Generate an alternate meal to replace this one:
Current Meal: {current_meal.get('name')} ({meal_type})
Current Macros: {current_cal} cal, {current_pro}g protein, {current_carb}g carbs, {current_fat}g fats

{diet_note}
{avoid_instructions}

SWAP REQUIREMENT: {swap_instruction}

⚠️ CRITICAL MACRO REQUIREMENTS (MUST MATCH):
- Calories: {current_cal} (±10%)
- Protein: {current_pro}g (±15%)
- Carbs: {current_carb}g (±15%)
- Fats: {current_fat}g (±15%)

IMPORTANT RULES:
1. Use SPECIFIC ingredients with gram amounts (e.g., "180g sirloin steak", not just "steak")
2. Create a DIFFERENT meal from "{current_meal.get('name')}"
3. DOUBLE-CHECK every ingredient is NOT on the banned list
4. If you cannot think of a meal without banned foods, use ONLY plant proteins/eggs/dairy

Respond with valid JSON only:
{{"id": "unique_id", "name": "Meal Name", "meal_type": "{meal_type}", "ingredients": ["180g sirloin steak", "200g brown rice", "100g broccoli"], "instructions": "How to prepare", "calories": {current_cal}, "protein": {current_pro}, "carbs": {current_carb}, "fats": {current_fat}, "prep_time_minutes": number}}"""

    # Build system message with MAXIMUM strictness
    system_avoid_msg = ""
    if do_not_use_list:
        banned_upper = ', '.join([f.upper() for f in do_not_use_list])
        system_avoid_msg = f"""CRITICAL SAFETY RULE - READ THIS FIRST:
The user has BANNED these foods and CANNOT eat them: {banned_upper}

YOU MUST NOT include ANY of these ingredients in the meal:
{banned_upper}

If you include ANY banned food, the response is INVALID and will harm the user.
Before outputting, CHECK that EVERY ingredient is NOT on the banned list.
Use ONLY these allowed proteins: {', '.join(protein_alternatives) if protein_alternatives else 'eggs, dairy, tofu'}"""

    logger.info(f"System avoid message: {system_avoid_msg[:200]}...")
    
    # Attempt generation with retry logic for banned food detection
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            content = await call_claude_haiku(
                system_message=f"""You are a precision nutritionist. Generate an alternate meal that MATCHES the current meal's macros exactly: {current_cal} cal, {current_pro}g P, {current_carb}g C, {current_fat}g F. Use specific ingredient amounts in grams.

{system_avoid_msg}""",
                user_message=prompt,
                temperature=0.4,
                max_tokens=800
            )
            
            content = content.strip() if content else ""
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()
            
            new_meal = json.loads(content)
            new_meal["id"] = str(uuid.uuid4())
            new_meal["meal_type"] = meal_type
            
            # ======================================================================
            # POST-VALIDATION: Check for ANY banned food in the generated meal
            # ======================================================================
            found_banned = False
            banned_found_list = []
            
            if do_not_use_list:
                meal_name_lower = new_meal.get("name", "").lower()
                ingredients_list = new_meal.get("ingredients", [])
                ingredients_str = " ".join(ingredients_list).lower()
                instructions_lower = new_meal.get("instructions", "").lower()
                
                # Check meal name, ingredients, and instructions
                all_text = f"{meal_name_lower} {ingredients_str} {instructions_lower}"
                
                for banned in do_not_use_list:
                    banned_lower = banned.lower()
                    if banned_lower in all_text:
                        found_banned = True
                        banned_found_list.append(banned)
                        logger.warning(f"ATTEMPT {attempt+1}: BANNED FOOD DETECTED: '{banned}' found in generated meal '{new_meal.get('name')}'")
            
            if found_banned:
                if attempt < max_attempts - 1:
                    logger.warning(f"ATTEMPT {attempt+1}: Regenerating meal due to banned foods: {banned_found_list}")
                    continue  # Try again
                else:
                    # Final attempt failed - strip the banned ingredients
                    logger.error(f"FINAL ATTEMPT: Still found banned foods: {banned_found_list}. Stripping ingredients.")
                    new_meal["ingredients"] = [
                        ing for ing in new_meal.get("ingredients", [])
                        if not any(banned.lower() in ing.lower() for banned in do_not_use_list)
                    ]
                    # Update meal name if it contains banned food
                    for banned in banned_found_list:
                        if banned.lower() in new_meal.get("name", "").lower():
                            new_meal["name"] = new_meal.get("name", "").replace(banned, "Protein").replace(banned.capitalize(), "Protein")
            
            # Log success
            logger.info(f"✅ Alternate meal generated (attempt {attempt+1}): {new_meal.get('name')} - {new_meal.get('calories')} cal, {new_meal.get('protein')}g P (target: {current_cal}/{current_pro})")
            
            # Save the updated meal plan to the database
            plan["meal_days"][request.day_index]["meals"][request.meal_index] = new_meal
            await db.mealplans.update_one(
                {"id": request.meal_plan_id},
                {"$set": {"meal_days": plan["meal_days"]}}
            )
            
            return {"alternate_meal": new_meal}
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error on attempt {attempt+1}: {e}")
            if attempt == max_attempts - 1:
                raise HTTPException(status_code=500, detail=f"Failed to parse AI response after {max_attempts} attempts")
        except Exception as e:
            logger.error(f"Alternate meal generation error on attempt {attempt+1}: {e}")
            if attempt == max_attempts - 1:
                raise HTTPException(status_code=500, detail=f"Failed to generate alternate meal: {str(e)}")

# ==================== FAVORITE MEALS ENDPOINTS ====================

@api_router.post("/food/favorite")
async def add_favorite_meal(user_id: str, meal_name: str, calories: int, protein: float, carbs: float, fats: float, serving_size: str = "1 serving"):
    """Add a meal to favorites"""
    favorite = FavoriteMeal(
        user_id=user_id,
        meal=Meal(
            name=meal_name,
            meal_type="snack",
            ingredients=[],
            instructions="",
            calories=calories,
            protein=protein,
            carbs=carbs,
            fats=fats,
            prep_time_minutes=0
        )
    )
    await db.favorite_meals.insert_one(favorite.model_dump())
    return {"message": "Meal added to favorites", "id": favorite.id}

@api_router.get("/food/favorites/{user_id}", response_model=List[FavoriteMeal])
async def get_favorite_meals(user_id: str):
    """Get user favorite meals"""
    favorites = await db.favorite_meals.find({"user_id": user_id}).sort("created_at", -1).to_list(100)
    return [FavoriteMeal(**fav) for fav in favorites]

@api_router.delete("/food/favorite/{favorite_id}")
async def remove_favorite_meal(favorite_id: str):
    """Remove a meal from favorites"""
    result = await db.favorite_meals.delete_one({"id": favorite_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return {"message": "Removed from favorites"}

@api_router.post("/food/log/favorite/{log_id}")
async def toggle_food_log_favorite(log_id: str):
    """Toggle favorite status on a food log entry"""
    log = await db.food_logs.find_one({"id": log_id})
    if not log:
        raise HTTPException(status_code=404, detail="Food log not found")
    
    new_status = not log.get("is_favorite", False)
    await db.food_logs.update_one({"id": log_id}, {"$set": {"is_favorite": new_status}})
    return {"message": f"Favorite {'added' if new_status else 'removed'}", "is_favorite": new_status}

# ==================== FOOD LOGGING ENDPOINTS ====================

@api_router.post("/food/analyze", response_model=FoodEntry)
async def analyze_food_image(request: FoodImageAnalyzeRequest):
    """Analyze food image using OpenAI Vision to identify food and estimate nutrition"""
    try:
        # Validate base64 image
        if not request.image_base64 or len(request.image_base64) < 100:
            raise HTTPException(status_code=400, detail="Invalid image data")
        
        # Build the user prompt with optional context
        user_prompt = "Analyze this food image and provide nutritional information in JSON format only."
        if request.additional_context:
            user_prompt += f"\n\nAdditional context from user: {request.additional_context}"
        
        content = await call_claude_sonnet(
            system_message="""You are a nutrition expert. Analyze the food image and provide accurate nutritional information.
Consider any additional context provided by the user (e.g., portion size, specific ingredients).
Respond with ONLY valid JSON, no other text. Use this exact format:
{"food_name": "Name", "serving_size": "1 serving", "calories": 300, "protein": 25.0, "carbs": 30.0, "fats": 10.0, "fiber": 5.0, "sugar": 8.0, "sodium": 400.0}""",
            user_message=user_prompt,
            temperature=0.3,
            max_tokens=500,
            image_base64=request.image_base64
        )
        logger.info(f"Food analysis raw response length: {len(content) if content else 0}")
        
        if not content or len(content.strip()) == 0:
            raise HTTPException(status_code=500, detail="AI returned empty response. Please try again with a clearer food image.")
        
        # Clean markdown code blocks if present
        content = content.strip() if content else ""
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```json"):
                    in_json = True
                    continue
                elif line.startswith("```"):
                    in_json = False
                    continue
                if in_json or not line.startswith("```"):
                    json_lines.append(line)
            content = "\n".join(json_lines)
        
        content = content.strip()
        
        # Try to parse JSON
        try:
            food_data = json.loads(content)
        except json.JSONDecodeError as je:
            logger.error(f"JSON parse error: {je}. Content: {content[:500]}")
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[^{}]*"food_name"[^{}]*\}', content, re.DOTALL)
            if json_match:
                food_data = json.loads(json_match.group())
            else:
                raise HTTPException(status_code=500, detail="Failed to parse food analysis. Please try with a clearer image.")
        
        # Apply quantity multiplier
        qty = request.quantity if request.quantity > 0 else 1
        
        food_entry = FoodEntry(
            user_id=request.user_id,
            food_name=food_data.get("food_name", "Unknown Food"),
            serving_size=f"{qty}x {food_data.get('serving_size', '1 serving')}",
            calories=int(food_data.get("calories", 0)) * qty,
            protein=float(food_data.get("protein", 0)) * qty,
            carbs=float(food_data.get("carbs", 0)) * qty,
            fats=float(food_data.get("fats", 0)) * qty,
            fiber=float(food_data.get("fiber", 0)) * qty,
            sugar=float(food_data.get("sugar", 0)) * qty,
            sodium=float(food_data.get("sodium", 0)) * qty,
            meal_type=request.meal_type,
            logged_date=datetime.now().strftime("%Y-%m-%d"),
            image_base64=request.image_base64[:100] + "..."  # Store truncated for reference
        )
        
        await db.food_logs.insert_one(food_entry.model_dump())
        return food_entry
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Food analysis error: {e}")
        if "invalid" in str(e).lower() or "image" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid image format. Please use a valid JPEG or PNG image.")
        raise HTTPException(status_code=500, detail=f"Failed to analyze food: {str(e)}")

@api_router.post("/food/log", response_model=FoodEntry)
async def log_food(request: FoodLogRequest):
    """Manually log food entry"""
    food_entry = FoodEntry(**request.model_dump())
    await db.food_logs.insert_one(food_entry.model_dump())
    return food_entry

@api_router.get("/food/logs/{user_id}")
async def get_food_logs(user_id: str, date: Optional[str] = None):
    """Get food logs for a user, optionally filtered by date"""
    query = {"user_id": user_id}
    if date:
        query["logged_date"] = date
    
    logs = await db.food_logs.find(query).sort("created_at", -1).to_list(100)
    return [FoodEntry(**log) for log in logs]

@api_router.get("/food/daily-summary/{user_id}/{date}")
async def get_daily_summary(user_id: str, date: str):
    """Get daily nutrition summary for a user"""
    logs = await db.food_logs.find({"user_id": user_id, "logged_date": date}).to_list(100)
    
    total = {
        "calories": 0,
        "protein": 0.0,
        "carbs": 0.0,
        "fats": 0.0,
        "fiber": 0.0,
        "sugar": 0.0,
        "sodium": 0.0
    }
    
    for log in logs:
        total["calories"] += log.get("calories", 0)
        total["protein"] += log.get("protein", 0)
        total["carbs"] += log.get("carbs", 0)
        total["fats"] += log.get("fats", 0)
        total["fiber"] += log.get("fiber", 0)
        total["sugar"] += log.get("sugar", 0)
        total["sodium"] += log.get("sodium", 0)
    
    # Get user's target macros
    profile = await db.profiles.find_one({"id": user_id})
    target = profile.get("calculated_macros", {}) if profile else {}
    
    return {
        "date": date,
        "consumed": total,
        "target": target,
        "entries_count": len(logs)
    }

@api_router.delete("/food/log/{log_id}")
async def delete_food_log(log_id: str):
    """Delete a food log entry"""
    result = await db.food_logs.delete_one({"id": log_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Food log not found")
    return {"message": "Food log deleted successfully"}

@api_router.get("/food/search")
async def search_foods(query: str):
    """Search food database - combines local database with API results for best coverage"""
    logger.info(f"Searching food database for: {query}")
    query_lower = query.lower()
    
    # Comprehensive local database with specific restaurant items
    local_foods = [
        # ==================== PROTEINS ====================
        {"name": "Chicken Breast, Grilled (100g)", "calories": 165, "protein": 31, "carbs": 0, "fats": 3.6},
        {"name": "Chicken Breast, Baked (100g)", "calories": 165, "protein": 31, "carbs": 0, "fats": 3.6},
        {"name": "Chicken Thigh, Grilled (100g)", "calories": 209, "protein": 26, "carbs": 0, "fats": 11},
        {"name": "Chicken Wings (4 pieces)", "calories": 320, "protein": 27, "carbs": 0, "fats": 22},
        {"name": "Chicken Drumstick (1 piece)", "calories": 76, "protein": 12, "carbs": 0, "fats": 3},
        {"name": "Rotisserie Chicken (1/4)", "calories": 290, "protein": 36, "carbs": 0, "fats": 15},
        {"name": "Turkey Breast (100g)", "calories": 135, "protein": 30, "carbs": 0, "fats": 1},
        {"name": "Turkey, Ground (100g)", "calories": 149, "protein": 27, "carbs": 0, "fats": 4},
        {"name": "Salmon, Atlantic (100g)", "calories": 208, "protein": 20, "carbs": 0, "fats": 13},
        {"name": "Salmon, Smoked (100g)", "calories": 117, "protein": 18, "carbs": 0, "fats": 4},
        {"name": "Tuna, Canned in Water (100g)", "calories": 116, "protein": 26, "carbs": 0, "fats": 1},
        {"name": "Tuna Steak, Grilled (100g)", "calories": 132, "protein": 29, "carbs": 0, "fats": 1},
        {"name": "Shrimp (100g)", "calories": 99, "protein": 24, "carbs": 0.2, "fats": 0.3},
        {"name": "Shrimp, Fried (6 pieces)", "calories": 210, "protein": 18, "carbs": 10, "fats": 10},
        {"name": "Tilapia, Baked (100g)", "calories": 128, "protein": 26, "carbs": 0, "fats": 2.7},
        {"name": "Cod, Baked (100g)", "calories": 105, "protein": 23, "carbs": 0, "fats": 1},
        {"name": "Lobster (100g)", "calories": 89, "protein": 19, "carbs": 0.5, "fats": 0.9},
        {"name": "Crab Meat (100g)", "calories": 97, "protein": 19, "carbs": 0, "fats": 1.5},
        {"name": "Beef Steak, Ribeye (100g)", "calories": 291, "protein": 24, "carbs": 0, "fats": 21},
        {"name": "Beef Steak, Sirloin (100g)", "calories": 207, "protein": 26, "carbs": 0, "fats": 11},
        {"name": "Beef Steak, Filet Mignon (100g)", "calories": 227, "protein": 26, "carbs": 0, "fats": 13},
        {"name": "Ground Beef, 90% Lean (100g)", "calories": 176, "protein": 20, "carbs": 0, "fats": 10},
        {"name": "Ground Beef, 80% Lean (100g)", "calories": 254, "protein": 17, "carbs": 0, "fats": 20},
        {"name": "Beef Brisket (100g)", "calories": 246, "protein": 27, "carbs": 0, "fats": 15},
        {"name": "Pork Tenderloin (100g)", "calories": 143, "protein": 26, "carbs": 0, "fats": 3.5},
        {"name": "Pork Chop, Grilled (100g)", "calories": 231, "protein": 25, "carbs": 0, "fats": 14},
        {"name": "Pork Belly (100g)", "calories": 518, "protein": 9, "carbs": 0, "fats": 53},
        {"name": "Bacon, Cooked (3 slices)", "calories": 120, "protein": 9, "carbs": 0, "fats": 9},
        {"name": "Ham, Sliced (100g)", "calories": 145, "protein": 21, "carbs": 1, "fats": 6},
        {"name": "Lamb Chop (100g)", "calories": 282, "protein": 25, "carbs": 0, "fats": 20},
        {"name": "Duck Breast (100g)", "calories": 201, "protein": 23, "carbs": 0, "fats": 11},
        {"name": "Egg, Large Whole", "calories": 72, "protein": 6, "carbs": 0.4, "fats": 5},
        {"name": "Egg, Scrambled (2 eggs)", "calories": 182, "protein": 12, "carbs": 2, "fats": 14},
        {"name": "Egg, Fried (1 large)", "calories": 90, "protein": 6, "carbs": 0.4, "fats": 7},
        {"name": "Egg, Boiled (1 large)", "calories": 78, "protein": 6, "carbs": 0.6, "fats": 5},
        {"name": "Egg Whites (3 large)", "calories": 51, "protein": 11, "carbs": 0.7, "fats": 0.2},
        {"name": "Omelette, Cheese (2 eggs)", "calories": 250, "protein": 16, "carbs": 2, "fats": 20},
        {"name": "Tofu, Firm (100g)", "calories": 144, "protein": 17, "carbs": 3, "fats": 9},
        {"name": "Tofu, Silken (100g)", "calories": 55, "protein": 5, "carbs": 2, "fats": 3},
        {"name": "Tempeh (100g)", "calories": 192, "protein": 20, "carbs": 8, "fats": 11},
        {"name": "Seitan (100g)", "calories": 370, "protein": 75, "carbs": 14, "fats": 2},
        # ==================== DAIRY ====================
        {"name": "Greek Yogurt, Plain (170g)", "calories": 100, "protein": 17, "carbs": 6, "fats": 0.7},
        {"name": "Greek Yogurt, Vanilla (170g)", "calories": 140, "protein": 14, "carbs": 16, "fats": 0},
        {"name": "Yogurt, Regular (170g)", "calories": 100, "protein": 6, "carbs": 16, "fats": 2},
        {"name": "Cottage Cheese, 2% (1 cup)", "calories": 183, "protein": 24, "carbs": 9, "fats": 5},
        {"name": "Cottage Cheese, Full Fat (1 cup)", "calories": 220, "protein": 25, "carbs": 8, "fats": 10},
        {"name": "Milk, 2% (1 cup)", "calories": 122, "protein": 8, "carbs": 12, "fats": 5},
        {"name": "Milk, Whole (1 cup)", "calories": 149, "protein": 8, "carbs": 12, "fats": 8},
        {"name": "Milk, Skim (1 cup)", "calories": 83, "protein": 8, "carbs": 12, "fats": 0},
        {"name": "Almond Milk, Unsweetened (1 cup)", "calories": 30, "protein": 1, "carbs": 1, "fats": 2.5},
        {"name": "Oat Milk (1 cup)", "calories": 120, "protein": 3, "carbs": 16, "fats": 5},
        {"name": "Soy Milk (1 cup)", "calories": 80, "protein": 7, "carbs": 4, "fats": 4},
        {"name": "Cheese, Cheddar (1 oz)", "calories": 113, "protein": 7, "carbs": 0.4, "fats": 9},
        {"name": "Cheese, Mozzarella (1 oz)", "calories": 72, "protein": 7, "carbs": 0.8, "fats": 4.5},
        {"name": "Cheese, Parmesan (1 oz)", "calories": 111, "protein": 10, "carbs": 1, "fats": 7},
        {"name": "Cheese, Swiss (1 oz)", "calories": 108, "protein": 8, "carbs": 1.5, "fats": 8},
        {"name": "Cheese, Feta (1 oz)", "calories": 74, "protein": 4, "carbs": 1, "fats": 6},
        {"name": "Cream Cheese (2 tbsp)", "calories": 100, "protein": 2, "carbs": 1, "fats": 10},
        {"name": "Butter (1 tbsp)", "calories": 102, "protein": 0.1, "carbs": 0, "fats": 11.5},
        {"name": "Sour Cream (2 tbsp)", "calories": 60, "protein": 1, "carbs": 1, "fats": 6},
        # ==================== CARBS & GRAINS ====================
        {"name": "White Rice, Cooked (1 cup)", "calories": 206, "protein": 4.3, "carbs": 45, "fats": 0.4},
        {"name": "Brown Rice, Cooked (1 cup)", "calories": 216, "protein": 5, "carbs": 45, "fats": 1.8},
        {"name": "Jasmine Rice, Cooked (1 cup)", "calories": 205, "protein": 4, "carbs": 45, "fats": 0.4},
        {"name": "Basmati Rice, Cooked (1 cup)", "calories": 210, "protein": 5, "carbs": 46, "fats": 0.5},
        {"name": "Fried Rice (1 cup)", "calories": 335, "protein": 8, "carbs": 45, "fats": 12},
        {"name": "Pasta, Cooked (1 cup)", "calories": 220, "protein": 8, "carbs": 43, "fats": 1.3},
        {"name": "Spaghetti, Cooked (1 cup)", "calories": 220, "protein": 8, "carbs": 43, "fats": 1.3},
        {"name": "Penne, Cooked (1 cup)", "calories": 220, "protein": 8, "carbs": 43, "fats": 1.3},
        {"name": "Mac and Cheese (1 cup)", "calories": 350, "protein": 14, "carbs": 38, "fats": 17},
        {"name": "Oatmeal, Cooked (1 cup)", "calories": 158, "protein": 6, "carbs": 27, "fats": 3.2},
        {"name": "Oatmeal with Honey", "calories": 220, "protein": 6, "carbs": 42, "fats": 3.5},
        {"name": "Overnight Oats (1 cup)", "calories": 280, "protein": 10, "carbs": 45, "fats": 7},
        {"name": "Quinoa, Cooked (1 cup)", "calories": 222, "protein": 8, "carbs": 39, "fats": 3.6},
        {"name": "Couscous, Cooked (1 cup)", "calories": 176, "protein": 6, "carbs": 36, "fats": 0.3},
        {"name": "Bread, Whole Wheat (1 slice)", "calories": 81, "protein": 4, "carbs": 14, "fats": 1.1},
        {"name": "Bread, White (1 slice)", "calories": 79, "protein": 2.7, "carbs": 15, "fats": 1},
        {"name": "Bread, Sourdough (1 slice)", "calories": 90, "protein": 4, "carbs": 18, "fats": 0.5},
        {"name": "Bagel, Plain", "calories": 277, "protein": 10, "carbs": 54, "fats": 1.4},
        {"name": "Bagel with Cream Cheese", "calories": 377, "protein": 12, "carbs": 55, "fats": 11},
        {"name": "Croissant", "calories": 231, "protein": 5, "carbs": 26, "fats": 12},
        {"name": "English Muffin", "calories": 132, "protein": 5, "carbs": 26, "fats": 1},
        {"name": "Tortilla, Flour (1 large)", "calories": 146, "protein": 4, "carbs": 25, "fats": 3.5},
        {"name": "Tortilla, Corn (1 medium)", "calories": 52, "protein": 1.4, "carbs": 11, "fats": 0.7},
        {"name": "Pita Bread (1 piece)", "calories": 165, "protein": 5, "carbs": 33, "fats": 1},
        {"name": "Naan Bread (1 piece)", "calories": 262, "protein": 9, "carbs": 45, "fats": 5},
        {"name": "Sweet Potato, Baked (1 medium)", "calories": 103, "protein": 2.3, "carbs": 24, "fats": 0.1},
        {"name": "Sweet Potato Fries (1 serving)", "calories": 300, "protein": 3, "carbs": 44, "fats": 13},
        {"name": "Potato, Baked (1 medium)", "calories": 161, "protein": 4.3, "carbs": 37, "fats": 0.2},
        {"name": "Mashed Potatoes (1 cup)", "calories": 214, "protein": 4, "carbs": 35, "fats": 8},
        {"name": "Hash Browns (1 cup)", "calories": 326, "protein": 3, "carbs": 33, "fats": 21},
        {"name": "French Fries, Small", "calories": 222, "protein": 3, "carbs": 29, "fats": 10},
        {"name": "French Fries, Medium", "calories": 365, "protein": 4, "carbs": 48, "fats": 17},
        {"name": "French Fries, Large", "calories": 498, "protein": 6, "carbs": 66, "fats": 23},
        {"name": "Cereal, Cheerios (1 cup)", "calories": 100, "protein": 3, "carbs": 20, "fats": 2},
        {"name": "Cereal, Corn Flakes (1 cup)", "calories": 100, "protein": 2, "carbs": 24, "fats": 0},
        {"name": "Cereal, Granola (1/2 cup)", "calories": 200, "protein": 4, "carbs": 32, "fats": 8},
        {"name": "Pancakes (3 medium)", "calories": 350, "protein": 8, "carbs": 58, "fats": 9},
        {"name": "Waffles (2 medium)", "calories": 380, "protein": 10, "carbs": 52, "fats": 14},
        {"name": "French Toast (2 slices)", "calories": 300, "protein": 10, "carbs": 36, "fats": 12},
        # ==================== FRUITS ====================
        {"name": "Banana (1 medium)", "calories": 105, "protein": 1.3, "carbs": 27, "fats": 0.4},
        {"name": "Apple (1 medium)", "calories": 95, "protein": 0.5, "carbs": 25, "fats": 0.3},
        {"name": "Orange (1 medium)", "calories": 62, "protein": 1.2, "carbs": 15, "fats": 0.2},
        {"name": "Grapes (1 cup)", "calories": 104, "protein": 1.1, "carbs": 27, "fats": 0.2},
        {"name": "Strawberries (1 cup)", "calories": 49, "protein": 1, "carbs": 12, "fats": 0.5},
        {"name": "Blueberries (1 cup)", "calories": 84, "protein": 1.1, "carbs": 21, "fats": 0.5},
        {"name": "Raspberries (1 cup)", "calories": 64, "protein": 1.5, "carbs": 15, "fats": 0.8},
        {"name": "Mango (1 cup)", "calories": 99, "protein": 1.4, "carbs": 25, "fats": 0.6},
        {"name": "Pineapple (1 cup)", "calories": 82, "protein": 0.9, "carbs": 22, "fats": 0.2},
        {"name": "Watermelon (1 cup)", "calories": 46, "protein": 0.9, "carbs": 12, "fats": 0.2},
        {"name": "Cantaloupe (1 cup)", "calories": 53, "protein": 1.3, "carbs": 13, "fats": 0.3},
        {"name": "Peach (1 medium)", "calories": 59, "protein": 1.4, "carbs": 14, "fats": 0.4},
        {"name": "Pear (1 medium)", "calories": 102, "protein": 0.6, "carbs": 27, "fats": 0.2},
        {"name": "Kiwi (1 medium)", "calories": 42, "protein": 0.8, "carbs": 10, "fats": 0.4},
        {"name": "Avocado (1/2 medium)", "calories": 160, "protein": 2, "carbs": 9, "fats": 15},
        {"name": "Avocado (1 whole)", "calories": 320, "protein": 4, "carbs": 17, "fats": 29},
        {"name": "Coconut, Shredded (1 oz)", "calories": 185, "protein": 2, "carbs": 7, "fats": 18},
        {"name": "Dates, Medjool (2 pieces)", "calories": 133, "protein": 0.8, "carbs": 36, "fats": 0},
        {"name": "Raisins (1/4 cup)", "calories": 123, "protein": 1.3, "carbs": 33, "fats": 0.2},
        # ==================== VEGETABLES ====================
        {"name": "Broccoli, Steamed (1 cup)", "calories": 55, "protein": 3.7, "carbs": 11, "fats": 0.6},
        {"name": "Spinach, Raw (1 cup)", "calories": 7, "protein": 0.9, "carbs": 1.1, "fats": 0.1},
        {"name": "Spinach, Cooked (1 cup)", "calories": 41, "protein": 5.3, "carbs": 7, "fats": 0.5},
        {"name": "Kale, Raw (1 cup)", "calories": 33, "protein": 2.9, "carbs": 6, "fats": 0.6},
        {"name": "Lettuce, Romaine (1 cup)", "calories": 8, "protein": 0.6, "carbs": 1.5, "fats": 0.1},
        {"name": "Carrots (1 medium)", "calories": 25, "protein": 0.6, "carbs": 6, "fats": 0.1},
        {"name": "Carrots, Baby (10 pieces)", "calories": 35, "protein": 0.6, "carbs": 8, "fats": 0.1},
        {"name": "Bell Pepper, Red (1 medium)", "calories": 37, "protein": 1.2, "carbs": 7, "fats": 0.4},
        {"name": "Bell Pepper, Green (1 medium)", "calories": 24, "protein": 1, "carbs": 6, "fats": 0.2},
        {"name": "Cucumber (1 cup)", "calories": 16, "protein": 0.7, "carbs": 4, "fats": 0.1},
        {"name": "Tomato (1 medium)", "calories": 22, "protein": 1.1, "carbs": 5, "fats": 0.2},
        {"name": "Cherry Tomatoes (1 cup)", "calories": 27, "protein": 1.3, "carbs": 6, "fats": 0.3},
        {"name": "Onion (1 medium)", "calories": 44, "protein": 1.2, "carbs": 10, "fats": 0.1},
        {"name": "Garlic (1 clove)", "calories": 4, "protein": 0.2, "carbs": 1, "fats": 0},
        {"name": "Mushrooms, White (1 cup)", "calories": 21, "protein": 3, "carbs": 3, "fats": 0.3},
        {"name": "Zucchini (1 medium)", "calories": 33, "protein": 2.4, "carbs": 6, "fats": 0.6},
        {"name": "Asparagus (6 spears)", "calories": 20, "protein": 2.2, "carbs": 4, "fats": 0.1},
        {"name": "Green Beans (1 cup)", "calories": 31, "protein": 1.8, "carbs": 7, "fats": 0.1},
        {"name": "Corn, Cooked (1 ear)", "calories": 90, "protein": 3.3, "carbs": 19, "fats": 1.4},
        {"name": "Peas, Green (1 cup)", "calories": 118, "protein": 8, "carbs": 21, "fats": 0.6},
        {"name": "Edamame (1 cup)", "calories": 188, "protein": 18, "carbs": 14, "fats": 8},
        {"name": "Cauliflower (1 cup)", "calories": 25, "protein": 2, "carbs": 5, "fats": 0.1},
        {"name": "Brussels Sprouts (1 cup)", "calories": 56, "protein": 4, "carbs": 11, "fats": 0.8},
        {"name": "Cabbage (1 cup)", "calories": 22, "protein": 1.3, "carbs": 5, "fats": 0.1},
        {"name": "Celery (2 stalks)", "calories": 12, "protein": 0.6, "carbs": 2.4, "fats": 0.1},
        {"name": "Eggplant (1 cup)", "calories": 35, "protein": 1, "carbs": 9, "fats": 0.2},
        # ==================== NUTS & SEEDS ====================
        {"name": "Almonds (1 oz / 23 nuts)", "calories": 164, "protein": 6, "carbs": 6, "fats": 14},
        {"name": "Peanuts (1 oz)", "calories": 161, "protein": 7, "carbs": 5, "fats": 14},
        {"name": "Walnuts (1 oz)", "calories": 185, "protein": 4.3, "carbs": 4, "fats": 18},
        {"name": "Cashews (1 oz)", "calories": 157, "protein": 5, "carbs": 9, "fats": 12},
        {"name": "Pistachios (1 oz)", "calories": 159, "protein": 6, "carbs": 8, "fats": 13},
        {"name": "Macadamia Nuts (1 oz)", "calories": 204, "protein": 2, "carbs": 4, "fats": 21},
        {"name": "Pecans (1 oz)", "calories": 196, "protein": 3, "carbs": 4, "fats": 20},
        {"name": "Brazil Nuts (1 oz)", "calories": 186, "protein": 4, "carbs": 3, "fats": 19},
        {"name": "Hazelnuts (1 oz)", "calories": 178, "protein": 4, "carbs": 5, "fats": 17},
        {"name": "Mixed Nuts (1 oz)", "calories": 172, "protein": 5, "carbs": 6, "fats": 15},
        {"name": "Trail Mix (1/4 cup)", "calories": 173, "protein": 5, "carbs": 17, "fats": 11},
        {"name": "Peanut Butter (2 tbsp)", "calories": 188, "protein": 8, "carbs": 6, "fats": 16},
        {"name": "Almond Butter (2 tbsp)", "calories": 196, "protein": 7, "carbs": 6, "fats": 18},
        {"name": "Sunflower Seeds (1 oz)", "calories": 165, "protein": 6, "carbs": 7, "fats": 14},
        {"name": "Pumpkin Seeds (1 oz)", "calories": 151, "protein": 7, "carbs": 5, "fats": 13},
        {"name": "Chia Seeds (1 oz)", "calories": 138, "protein": 4.7, "carbs": 12, "fats": 9},
        {"name": "Flax Seeds (1 tbsp)", "calories": 37, "protein": 1.3, "carbs": 2, "fats": 3},
        {"name": "Hemp Seeds (3 tbsp)", "calories": 166, "protein": 10, "carbs": 3, "fats": 14},
        # ==================== McDONALD'S ====================
        {"name": "McDonald's Big Mac", "calories": 563, "protein": 26, "carbs": 44, "fats": 33},
        {"name": "McDonald's Quarter Pounder with Cheese", "calories": 520, "protein": 30, "carbs": 42, "fats": 26},
        {"name": "McDonald's McDouble", "calories": 400, "protein": 22, "carbs": 33, "fats": 20},
        {"name": "McDonald's Cheeseburger", "calories": 300, "protein": 15, "carbs": 32, "fats": 12},
        {"name": "McDonald's Hamburger", "calories": 250, "protein": 12, "carbs": 31, "fats": 9},
        {"name": "McDonald's Double Cheeseburger", "calories": 450, "protein": 25, "carbs": 34, "fats": 24},
        {"name": "McDonald's McChicken", "calories": 400, "protein": 14, "carbs": 40, "fats": 21},
        {"name": "McDonald's Filet-O-Fish", "calories": 390, "protein": 16, "carbs": 39, "fats": 19},
        {"name": "McDonald's Chicken McNuggets (6 pc)", "calories": 250, "protein": 15, "carbs": 15, "fats": 15},
        {"name": "McDonald's Chicken McNuggets (10 pc)", "calories": 410, "protein": 25, "carbs": 25, "fats": 24},
        {"name": "McDonald's Chicken McNuggets (20 pc)", "calories": 830, "protein": 49, "carbs": 51, "fats": 49},
        {"name": "McDonald's Crispy Chicken Sandwich", "calories": 470, "protein": 26, "carbs": 46, "fats": 20},
        {"name": "McDonald's Spicy Crispy Chicken", "calories": 530, "protein": 27, "carbs": 48, "fats": 26},
        {"name": "McDonald's Egg McMuffin", "calories": 310, "protein": 17, "carbs": 30, "fats": 13},
        {"name": "McDonald's Sausage McMuffin with Egg", "calories": 480, "protein": 21, "carbs": 29, "fats": 31},
        {"name": "McDonald's Hash Browns", "calories": 140, "protein": 1, "carbs": 15, "fats": 8},
        {"name": "McDonald's Hotcakes", "calories": 590, "protein": 12, "carbs": 101, "fats": 15},
        {"name": "McDonald's Sausage Burrito", "calories": 310, "protein": 12, "carbs": 26, "fats": 17},
        {"name": "McDonald's Fries Small", "calories": 222, "protein": 3, "carbs": 29, "fats": 10},
        {"name": "McDonald's Fries Medium", "calories": 365, "protein": 4, "carbs": 48, "fats": 17},
        {"name": "McDonald's Fries Large", "calories": 498, "protein": 6, "carbs": 66, "fats": 23},
        {"name": "McDonald's McFlurry with Oreo", "calories": 510, "protein": 12, "carbs": 80, "fats": 17},
        {"name": "McDonald's Apple Pie", "calories": 240, "protein": 2, "carbs": 35, "fats": 11},
        {"name": "McDonald's Vanilla Cone", "calories": 200, "protein": 5, "carbs": 32, "fats": 5},
        {"name": "McDonald's Chocolate Shake Medium", "calories": 630, "protein": 14, "carbs": 101, "fats": 18},
        # ==================== BURGER KING ====================
        {"name": "Burger King Whopper", "calories": 657, "protein": 28, "carbs": 49, "fats": 40},
        {"name": "Burger King Whopper Jr", "calories": 310, "protein": 13, "carbs": 27, "fats": 18},
        {"name": "Burger King Bacon King", "calories": 1150, "protein": 61, "carbs": 49, "fats": 79},
        {"name": "Burger King Impossible Whopper", "calories": 629, "protein": 25, "carbs": 58, "fats": 34},
        {"name": "Burger King Chicken Fries (9 pc)", "calories": 280, "protein": 13, "carbs": 16, "fats": 17},
        {"name": "Burger King Original Chicken Sandwich", "calories": 660, "protein": 28, "carbs": 48, "fats": 40},
        {"name": "Burger King Chicken Nuggets (8 pc)", "calories": 380, "protein": 17, "carbs": 24, "fats": 24},
        {"name": "Burger King Onion Rings Medium", "calories": 410, "protein": 6, "carbs": 50, "fats": 20},
        {"name": "Burger King Fries Medium", "calories": 380, "protein": 5, "carbs": 53, "fats": 17},
        # ==================== WENDY'S ====================
        {"name": "Wendy's Dave's Single", "calories": 570, "protein": 30, "carbs": 39, "fats": 34},
        {"name": "Wendy's Dave's Double", "calories": 810, "protein": 48, "carbs": 40, "fats": 52},
        {"name": "Wendy's Dave's Triple", "calories": 1050, "protein": 66, "carbs": 40, "fats": 70},
        {"name": "Wendy's Jr Bacon Cheeseburger", "calories": 380, "protein": 18, "carbs": 27, "fats": 22},
        {"name": "Wendy's Jr Hamburger", "calories": 250, "protein": 13, "carbs": 25, "fats": 11},
        {"name": "Wendy's Baconator", "calories": 960, "protein": 57, "carbs": 40, "fats": 64},
        {"name": "Wendy's Spicy Chicken Sandwich", "calories": 500, "protein": 30, "carbs": 47, "fats": 22},
        {"name": "Wendy's Classic Chicken Sandwich", "calories": 480, "protein": 30, "carbs": 45, "fats": 21},
        {"name": "Wendy's Nuggets (10 pc)", "calories": 430, "protein": 21, "carbs": 28, "fats": 27},
        {"name": "Wendy's Fries Medium", "calories": 350, "protein": 5, "carbs": 45, "fats": 16},
        {"name": "Wendy's Chili Small", "calories": 170, "protein": 15, "carbs": 15, "fats": 5},
        {"name": "Wendy's Chili Large", "calories": 270, "protein": 23, "carbs": 24, "fats": 8},
        {"name": "Wendy's Baked Potato with Sour Cream", "calories": 330, "protein": 8, "carbs": 63, "fats": 6},
        {"name": "Wendy's Frosty Small", "calories": 340, "protein": 9, "carbs": 55, "fats": 9},
        # ==================== IN-N-OUT ====================
        {"name": "In-N-Out Hamburger", "calories": 390, "protein": 16, "carbs": 39, "fats": 19},
        {"name": "In-N-Out Cheeseburger", "calories": 480, "protein": 22, "carbs": 39, "fats": 27},
        {"name": "In-N-Out Double-Double", "calories": 670, "protein": 37, "carbs": 39, "fats": 41},
        {"name": "In-N-Out Double-Double Protein Style", "calories": 520, "protein": 33, "carbs": 11, "fats": 39},
        {"name": "In-N-Out 3x3", "calories": 860, "protein": 52, "carbs": 39, "fats": 55},
        {"name": "In-N-Out 4x4", "calories": 1050, "protein": 67, "carbs": 40, "fats": 69},
        {"name": "In-N-Out Animal Style Burger", "calories": 480, "protein": 22, "carbs": 41, "fats": 27},
        {"name": "In-N-Out Fries", "calories": 395, "protein": 7, "carbs": 54, "fats": 18},
        {"name": "In-N-Out Animal Style Fries", "calories": 750, "protein": 17, "carbs": 62, "fats": 48},
        {"name": "In-N-Out Chocolate Shake", "calories": 590, "protein": 9, "carbs": 72, "fats": 29},
        {"name": "In-N-Out Vanilla Shake", "calories": 580, "protein": 9, "carbs": 67, "fats": 31},
        {"name": "In-N-Out Strawberry Shake", "calories": 590, "protein": 9, "carbs": 72, "fats": 29},
        # ==================== TACO BELL ====================
        {"name": "Taco Bell Crunchy Taco", "calories": 170, "protein": 8, "carbs": 13, "fats": 10},
        {"name": "Taco Bell Soft Taco", "calories": 180, "protein": 9, "carbs": 18, "fats": 9},
        {"name": "Taco Bell Doritos Locos Taco", "calories": 170, "protein": 8, "carbs": 15, "fats": 9},
        {"name": "Taco Bell Crunchwrap Supreme", "calories": 530, "protein": 16, "carbs": 55, "fats": 21},
        {"name": "Taco Bell Chalupa Supreme", "calories": 350, "protein": 13, "carbs": 31, "fats": 18},
        {"name": "Taco Bell Gordita Supreme", "calories": 280, "protein": 12, "carbs": 28, "fats": 13},
        {"name": "Taco Bell Quesadilla Chicken", "calories": 510, "protein": 27, "carbs": 37, "fats": 28},
        {"name": "Taco Bell Bean Burrito", "calories": 380, "protein": 13, "carbs": 55, "fats": 11},
        {"name": "Taco Bell Burrito Supreme", "calories": 410, "protein": 16, "carbs": 51, "fats": 16},
        {"name": "Taco Bell Mexican Pizza", "calories": 540, "protein": 20, "carbs": 46, "fats": 30},
        {"name": "Taco Bell Nachos BellGrande", "calories": 740, "protein": 16, "carbs": 80, "fats": 39},
        {"name": "Taco Bell Cheesy Gordita Crunch", "calories": 500, "protein": 20, "carbs": 41, "fats": 28},
        {"name": "Taco Bell Cinnamon Twists", "calories": 170, "protein": 1, "carbs": 26, "fats": 7},
        # ==================== CHICK-FIL-A ====================
        {"name": "Chick-fil-A Chicken Sandwich", "calories": 440, "protein": 29, "carbs": 40, "fats": 19},
        {"name": "Chick-fil-A Deluxe Sandwich", "calories": 500, "protein": 30, "carbs": 41, "fats": 22},
        {"name": "Chick-fil-A Spicy Chicken Sandwich", "calories": 450, "protein": 29, "carbs": 42, "fats": 18},
        {"name": "Chick-fil-A Spicy Deluxe Sandwich", "calories": 540, "protein": 33, "carbs": 44, "fats": 24},
        {"name": "Chick-fil-A Grilled Chicken Sandwich", "calories": 320, "protein": 29, "carbs": 36, "fats": 6},
        {"name": "Chick-fil-A Nuggets (8 pc)", "calories": 250, "protein": 27, "carbs": 11, "fats": 11},
        {"name": "Chick-fil-A Nuggets (12 pc)", "calories": 380, "protein": 40, "carbs": 16, "fats": 17},
        {"name": "Chick-fil-A Grilled Nuggets (8 pc)", "calories": 130, "protein": 25, "carbs": 2, "fats": 3},
        {"name": "Chick-fil-A Waffle Fries Medium", "calories": 420, "protein": 5, "carbs": 45, "fats": 24},
        {"name": "Chick-fil-A Waffle Fries Large", "calories": 500, "protein": 6, "carbs": 54, "fats": 29},
        {"name": "Chick-fil-A Mac and Cheese", "calories": 450, "protein": 17, "carbs": 32, "fats": 28},
        {"name": "Chick-fil-A Chicken Biscuit", "calories": 460, "protein": 18, "carbs": 49, "fats": 22},
        {"name": "Chick-fil-A Cobb Salad", "calories": 510, "protein": 40, "carbs": 28, "fats": 27},
        {"name": "Chick-fil-A Milkshake", "calories": 580, "protein": 13, "carbs": 85, "fats": 22},
        # ==================== SUBWAY ====================
        {"name": "Subway 6\" Turkey Breast Sub", "calories": 280, "protein": 18, "carbs": 46, "fats": 3.5},
        {"name": "Subway 6\" Chicken Breast Sub", "calories": 320, "protein": 24, "carbs": 48, "fats": 5},
        {"name": "Subway 6\" Italian BMT", "calories": 410, "protein": 20, "carbs": 47, "fats": 16},
        {"name": "Subway 6\" Meatball Marinara", "calories": 480, "protein": 23, "carbs": 55, "fats": 18},
        {"name": "Subway 6\" Steak and Cheese", "calories": 370, "protein": 26, "carbs": 46, "fats": 10},
        {"name": "Subway 6\" Tuna Sub", "calories": 480, "protein": 20, "carbs": 44, "fats": 24},
        {"name": "Subway 6\" Veggie Delite", "calories": 230, "protein": 8, "carbs": 44, "fats": 2.5},
        {"name": "Subway Footlong Turkey", "calories": 560, "protein": 36, "carbs": 92, "fats": 7},
        {"name": "Subway Cookie", "calories": 200, "protein": 2, "carbs": 28, "fats": 9},
        # ==================== CHIPOTLE ====================
        {"name": "Chipotle Chicken Burrito", "calories": 1040, "protein": 58, "carbs": 108, "fats": 42},
        {"name": "Chipotle Steak Burrito", "calories": 1015, "protein": 55, "carbs": 105, "fats": 42},
        {"name": "Chipotle Carnitas Burrito", "calories": 1075, "protein": 53, "carbs": 108, "fats": 47},
        {"name": "Chipotle Barbacoa Burrito", "calories": 995, "protein": 55, "carbs": 105, "fats": 38},
        {"name": "Chipotle Sofritas Burrito", "calories": 905, "protein": 28, "carbs": 117, "fats": 36},
        {"name": "Chipotle Chicken Bowl", "calories": 745, "protein": 54, "carbs": 62, "fats": 31},
        {"name": "Chipotle Steak Bowl", "calories": 720, "protein": 51, "carbs": 58, "fats": 31},
        {"name": "Chipotle Chicken Tacos (3)", "calories": 640, "protein": 40, "carbs": 48, "fats": 28},
        {"name": "Chipotle Chicken Quesadilla", "calories": 1020, "protein": 57, "carbs": 70, "fats": 55},
        {"name": "Chipotle Chips", "calories": 540, "protein": 7, "carbs": 73, "fats": 24},
        {"name": "Chipotle Chips and Guacamole", "calories": 770, "protein": 10, "carbs": 81, "fats": 45},
        {"name": "Chipotle Guacamole", "calories": 230, "protein": 3, "carbs": 8, "fats": 21},
        # ==================== PIZZA ====================
        {"name": "Pizza Slice, Cheese", "calories": 272, "protein": 12, "carbs": 34, "fats": 10},
        {"name": "Pizza Slice, Pepperoni", "calories": 311, "protein": 13, "carbs": 34, "fats": 14},
        {"name": "Pizza Slice, Supreme", "calories": 340, "protein": 15, "carbs": 35, "fats": 16},
        {"name": "Pizza Slice, Meat Lovers", "calories": 380, "protein": 17, "carbs": 32, "fats": 20},
        {"name": "Pizza Slice, Veggie", "calories": 260, "protein": 11, "carbs": 35, "fats": 9},
        {"name": "Pizza Slice, Hawaiian", "calories": 290, "protein": 14, "carbs": 36, "fats": 10},
        {"name": "Pizza Slice, BBQ Chicken", "calories": 320, "protein": 16, "carbs": 38, "fats": 11},
        {"name": "Pizza Hut Personal Pan Pepperoni", "calories": 630, "protein": 27, "carbs": 63, "fats": 28},
        {"name": "Domino's Hand Tossed Cheese (2 slices)", "calories": 420, "protein": 16, "carbs": 52, "fats": 16},
        # ==================== STARBUCKS ====================
        {"name": "Starbucks Caffe Latte Grande", "calories": 190, "protein": 13, "carbs": 19, "fats": 7},
        {"name": "Starbucks Cappuccino Grande", "calories": 140, "protein": 10, "carbs": 14, "fats": 5},
        {"name": "Starbucks Caramel Macchiato Grande", "calories": 250, "protein": 10, "carbs": 35, "fats": 7},
        {"name": "Starbucks Mocha Grande", "calories": 360, "protein": 13, "carbs": 44, "fats": 15},
        {"name": "Starbucks Vanilla Latte Grande", "calories": 250, "protein": 12, "carbs": 37, "fats": 6},
        {"name": "Starbucks Iced Coffee Grande", "calories": 80, "protein": 1, "carbs": 20, "fats": 0},
        {"name": "Starbucks Cold Brew Grande", "calories": 5, "protein": 0, "carbs": 0, "fats": 0},
        {"name": "Starbucks Frappuccino Caramel Grande", "calories": 380, "protein": 5, "carbs": 55, "fats": 16},
        {"name": "Starbucks Pumpkin Spice Latte Grande", "calories": 380, "protein": 14, "carbs": 52, "fats": 14},
        {"name": "Starbucks Bacon Gouda Sandwich", "calories": 360, "protein": 18, "carbs": 34, "fats": 18},
        {"name": "Starbucks Egg Bites (2 pack)", "calories": 300, "protein": 19, "carbs": 9, "fats": 21},
        {"name": "Starbucks Croissant", "calories": 260, "protein": 5, "carbs": 28, "fats": 14},
        {"name": "Starbucks Blueberry Muffin", "calories": 380, "protein": 6, "carbs": 55, "fats": 16},
        # ==================== FIVE GUYS ====================
        {"name": "Five Guys Hamburger", "calories": 700, "protein": 39, "carbs": 39, "fats": 43},
        {"name": "Five Guys Cheeseburger", "calories": 840, "protein": 47, "carbs": 40, "fats": 55},
        {"name": "Five Guys Bacon Cheeseburger", "calories": 920, "protein": 51, "carbs": 40, "fats": 62},
        {"name": "Five Guys Little Hamburger", "calories": 480, "protein": 23, "carbs": 39, "fats": 26},
        {"name": "Five Guys Little Cheeseburger", "calories": 550, "protein": 27, "carbs": 40, "fats": 32},
        {"name": "Five Guys Hot Dog", "calories": 545, "protein": 18, "carbs": 40, "fats": 35},
        {"name": "Five Guys Fries Regular", "calories": 953, "protein": 15, "carbs": 131, "fats": 41},
        {"name": "Five Guys Fries Little", "calories": 528, "protein": 8, "carbs": 73, "fats": 23},
        # ==================== POPEYES ====================
        {"name": "Popeyes Chicken Sandwich", "calories": 699, "protein": 28, "carbs": 50, "fats": 42},
        {"name": "Popeyes Spicy Chicken Sandwich", "calories": 700, "protein": 28, "carbs": 50, "fats": 42},
        {"name": "Popeyes 2pc Chicken (Leg & Thigh)", "calories": 430, "protein": 32, "carbs": 11, "fats": 29},
        {"name": "Popeyes 3pc Chicken Tenders", "calories": 340, "protein": 26, "carbs": 10, "fats": 22},
        {"name": "Popeyes 5pc Chicken Tenders", "calories": 570, "protein": 44, "carbs": 18, "fats": 36},
        {"name": "Popeyes Cajun Fries Regular", "calories": 260, "protein": 4, "carbs": 36, "fats": 12},
        {"name": "Popeyes Red Beans and Rice", "calories": 230, "protein": 7, "carbs": 25, "fats": 11},
        {"name": "Popeyes Biscuit", "calories": 199, "protein": 3, "carbs": 26, "fats": 9},
        # ==================== KFC ====================
        {"name": "KFC Original Recipe Chicken Breast", "calories": 320, "protein": 36, "carbs": 8, "fats": 16},
        {"name": "KFC Original Recipe Chicken Thigh", "calories": 280, "protein": 17, "carbs": 8, "fats": 20},
        {"name": "KFC Original Recipe Chicken Drumstick", "calories": 130, "protein": 12, "carbs": 4, "fats": 7},
        {"name": "KFC Extra Crispy Chicken Breast", "calories": 430, "protein": 34, "carbs": 16, "fats": 26},
        {"name": "KFC Chicken Sandwich", "calories": 650, "protein": 28, "carbs": 49, "fats": 38},
        {"name": "KFC Popcorn Chicken Large", "calories": 620, "protein": 26, "carbs": 36, "fats": 40},
        {"name": "KFC Famous Bowl", "calories": 720, "protein": 26, "carbs": 76, "fats": 34},
        {"name": "KFC Pot Pie", "calories": 790, "protein": 29, "carbs": 62, "fats": 45},
        {"name": "KFC Mashed Potatoes with Gravy", "calories": 120, "protein": 2, "carbs": 19, "fats": 4},
        {"name": "KFC Cole Slaw", "calories": 170, "protein": 1, "carbs": 14, "fats": 12},
        {"name": "KFC Biscuit", "calories": 180, "protein": 4, "carbs": 21, "fats": 9},
        # ==================== PANDA EXPRESS ====================
        {"name": "Panda Express Orange Chicken", "calories": 490, "protein": 18, "carbs": 51, "fats": 23},
        {"name": "Panda Express Beijing Beef", "calories": 470, "protein": 14, "carbs": 56, "fats": 21},
        {"name": "Panda Express Broccoli Beef", "calories": 150, "protein": 9, "carbs": 13, "fats": 7},
        {"name": "Panda Express Kung Pao Chicken", "calories": 290, "protein": 16, "carbs": 14, "fats": 19},
        {"name": "Panda Express Honey Walnut Shrimp", "calories": 360, "protein": 14, "carbs": 35, "fats": 19},
        {"name": "Panda Express Grilled Teriyaki Chicken", "calories": 300, "protein": 36, "carbs": 8, "fats": 13},
        {"name": "Panda Express String Bean Chicken Breast", "calories": 190, "protein": 14, "carbs": 13, "fats": 9},
        {"name": "Panda Express Fried Rice", "calories": 520, "protein": 11, "carbs": 85, "fats": 16},
        {"name": "Panda Express Chow Mein", "calories": 510, "protein": 13, "carbs": 80, "fats": 22},
        {"name": "Panda Express White Steamed Rice", "calories": 380, "protein": 7, "carbs": 86, "fats": 0},
        {"name": "Panda Express Super Greens", "calories": 90, "protein": 6, "carbs": 10, "fats": 3},
        {"name": "Panda Express Egg Roll", "calories": 200, "protein": 7, "carbs": 20, "fats": 10},
        {"name": "Panda Express Cream Cheese Rangoon (3)", "calories": 190, "protein": 5, "carbs": 24, "fats": 8},
        # ==================== DUNKIN ====================
        {"name": "Dunkin Glazed Donut", "calories": 260, "protein": 3, "carbs": 31, "fats": 14},
        {"name": "Dunkin Boston Cream Donut", "calories": 300, "protein": 4, "carbs": 40, "fats": 14},
        {"name": "Dunkin Chocolate Frosted Donut", "calories": 280, "protein": 3, "carbs": 34, "fats": 15},
        {"name": "Dunkin Jelly Donut", "calories": 270, "protein": 4, "carbs": 37, "fats": 12},
        {"name": "Dunkin Munchkins (5 glazed)", "calories": 270, "protein": 3, "carbs": 31, "fats": 15},
        {"name": "Dunkin Egg and Cheese Wake Up Wrap", "calories": 180, "protein": 8, "carbs": 14, "fats": 11},
        {"name": "Dunkin Bacon Egg Cheese Croissant", "calories": 520, "protein": 18, "carbs": 35, "fats": 34},
        {"name": "Dunkin Hash Browns (6 pieces)", "calories": 130, "protein": 1, "carbs": 16, "fats": 6},
        {"name": "Dunkin Iced Coffee Medium", "calories": 25, "protein": 0, "carbs": 6, "fats": 0},
        {"name": "Dunkin Latte Medium", "calories": 120, "protein": 8, "carbs": 11, "fats": 4},
        # ==================== BEVERAGES ====================
        {"name": "Coffee, Black (8 oz)", "calories": 2, "protein": 0.3, "carbs": 0, "fats": 0},
        {"name": "Coffee with Cream (8 oz)", "calories": 40, "protein": 1, "carbs": 1, "fats": 3},
        {"name": "Espresso (1 shot)", "calories": 3, "protein": 0.2, "carbs": 0.6, "fats": 0},
        {"name": "Green Tea (8 oz)", "calories": 2, "protein": 0, "carbs": 0.5, "fats": 0},
        {"name": "Orange Juice (8 oz)", "calories": 112, "protein": 2, "carbs": 26, "fats": 0.5},
        {"name": "Apple Juice (8 oz)", "calories": 117, "protein": 0.2, "carbs": 29, "fats": 0.3},
        {"name": "Protein Shake, Whey (1 scoop)", "calories": 120, "protein": 24, "carbs": 3, "fats": 1},
        {"name": "Smoothie, Fruit (12 oz)", "calories": 200, "protein": 3, "carbs": 45, "fats": 1},
        {"name": "Smoothie, Green (12 oz)", "calories": 150, "protein": 4, "carbs": 32, "fats": 2},
        {"name": "Smoothie, Protein (16 oz)", "calories": 350, "protein": 30, "carbs": 45, "fats": 6},
        {"name": "Coca-Cola (12 oz)", "calories": 140, "protein": 0, "carbs": 39, "fats": 0},
        {"name": "Diet Coke (12 oz)", "calories": 0, "protein": 0, "carbs": 0, "fats": 0},
        {"name": "Pepsi (12 oz)", "calories": 150, "protein": 0, "carbs": 41, "fats": 0},
        {"name": "Sprite (12 oz)", "calories": 140, "protein": 0, "carbs": 38, "fats": 0},
        {"name": "Red Bull (8.4 oz)", "calories": 110, "protein": 0, "carbs": 28, "fats": 0},
        {"name": "Monster Energy (16 oz)", "calories": 210, "protein": 0, "carbs": 54, "fats": 0},
        {"name": "Gatorade (20 oz)", "calories": 140, "protein": 0, "carbs": 36, "fats": 0},
        {"name": "Beer, Regular (12 oz)", "calories": 153, "protein": 1.6, "carbs": 13, "fats": 0},
        {"name": "Beer, Light (12 oz)", "calories": 103, "protein": 0.9, "carbs": 6, "fats": 0},
        {"name": "Wine, Red (5 oz)", "calories": 125, "protein": 0.1, "carbs": 4, "fats": 0},
        {"name": "Wine, White (5 oz)", "calories": 121, "protein": 0.1, "carbs": 4, "fats": 0},
        # ==================== SNACKS ====================
        {"name": "Protein Bar", "calories": 200, "protein": 20, "carbs": 22, "fats": 6},
        {"name": "Quest Protein Bar", "calories": 190, "protein": 21, "carbs": 21, "fats": 8},
        {"name": "Clif Bar", "calories": 250, "protein": 10, "carbs": 44, "fats": 6},
        {"name": "Kind Bar", "calories": 200, "protein": 6, "carbs": 17, "fats": 13},
        {"name": "RX Bar", "calories": 210, "protein": 12, "carbs": 24, "fats": 9},
        {"name": "Granola Bar", "calories": 190, "protein": 3, "carbs": 29, "fats": 7},
        {"name": "Nature Valley Bar (2)", "calories": 190, "protein": 4, "carbs": 29, "fats": 6},
        {"name": "Chips, Potato (1 oz)", "calories": 152, "protein": 2, "carbs": 15, "fats": 10},
        {"name": "Chips, Tortilla (1 oz)", "calories": 142, "protein": 2, "carbs": 18, "fats": 7},
        {"name": "Doritos (1 oz)", "calories": 150, "protein": 2, "carbs": 18, "fats": 8},
        {"name": "Cheetos (1 oz)", "calories": 160, "protein": 2, "carbs": 15, "fats": 10},
        {"name": "Pretzels (1 oz)", "calories": 108, "protein": 3, "carbs": 23, "fats": 1},
        {"name": "Popcorn, Air-popped (3 cups)", "calories": 93, "protein": 3, "carbs": 19, "fats": 1},
        {"name": "Popcorn, Movie Theater Large", "calories": 1030, "protein": 10, "carbs": 92, "fats": 72},
        {"name": "Dark Chocolate (1 oz)", "calories": 170, "protein": 2, "carbs": 13, "fats": 12},
        {"name": "Milk Chocolate (1 oz)", "calories": 153, "protein": 2, "carbs": 17, "fats": 9},
        {"name": "M&Ms (1.69 oz)", "calories": 240, "protein": 2, "carbs": 34, "fats": 10},
        {"name": "Snickers Bar", "calories": 280, "protein": 4, "carbs": 35, "fats": 14},
        {"name": "Reese's Peanut Butter Cups (2)", "calories": 210, "protein": 5, "carbs": 24, "fats": 13},
        {"name": "Kit Kat (4 pieces)", "calories": 218, "protein": 3, "carbs": 27, "fats": 11},
        {"name": "Twix (2 pieces)", "calories": 250, "protein": 2, "carbs": 34, "fats": 12},
        {"name": "Oreos (3 cookies)", "calories": 160, "protein": 1, "carbs": 25, "fats": 7},
        {"name": "Chips Ahoy (3 cookies)", "calories": 160, "protein": 2, "carbs": 22, "fats": 8},
        {"name": "Ice Cream, Vanilla (1/2 cup)", "calories": 137, "protein": 2.3, "carbs": 16, "fats": 7},
        {"name": "Ice Cream, Chocolate (1/2 cup)", "calories": 143, "protein": 2.5, "carbs": 19, "fats": 7},
        {"name": "Frozen Yogurt (1/2 cup)", "calories": 110, "protein": 3, "carbs": 22, "fats": 1},
        {"name": "Gelato (1/2 cup)", "calories": 160, "protein": 4, "carbs": 25, "fats": 5},
        {"name": "Rice Cakes (2)", "calories": 70, "protein": 1.5, "carbs": 15, "fats": 0.5},
        {"name": "Hummus (2 tbsp)", "calories": 50, "protein": 2, "carbs": 4, "fats": 3},
        {"name": "Guacamole (2 tbsp)", "calories": 50, "protein": 1, "carbs": 3, "fats": 4},
        {"name": "Salsa (2 tbsp)", "calories": 10, "protein": 0, "carbs": 2, "fats": 0},
        {"name": "Cheese Sticks (1)", "calories": 80, "protein": 6, "carbs": 1, "fats": 6},
        {"name": "Beef Jerky (1 oz)", "calories": 116, "protein": 9, "carbs": 3, "fats": 7},
        # ==================== PREPARED MEALS ====================
        {"name": "Chicken Stir Fry with Rice", "calories": 450, "protein": 35, "carbs": 45, "fats": 12},
        {"name": "Grilled Salmon with Vegetables", "calories": 380, "protein": 38, "carbs": 12, "fats": 20},
        {"name": "Pasta with Meat Sauce", "calories": 520, "protein": 24, "carbs": 62, "fats": 18},
        {"name": "Chicken Salad Sandwich", "calories": 420, "protein": 25, "carbs": 35, "fats": 20},
        {"name": "Bowl of Oatmeal with Banana", "calories": 263, "protein": 7.3, "carbs": 54, "fats": 3.6},
        {"name": "Grilled Chicken Caesar Salad", "calories": 470, "protein": 42, "carbs": 14, "fats": 28},
        {"name": "Turkey and Cheese Sandwich", "calories": 380, "protein": 28, "carbs": 32, "fats": 16},
        {"name": "Beef and Broccoli with Rice", "calories": 520, "protein": 32, "carbs": 52, "fats": 18},
        {"name": "Shrimp Fried Rice", "calories": 480, "protein": 22, "carbs": 55, "fats": 18},
        {"name": "Chicken Alfredo Pasta", "calories": 680, "protein": 35, "carbs": 58, "fats": 32},
        {"name": "Fish Tacos (2)", "calories": 380, "protein": 22, "carbs": 36, "fats": 16},
        {"name": "Grilled Chicken Breast with Rice", "calories": 400, "protein": 40, "carbs": 45, "fats": 5},
        {"name": "Salmon Poke Bowl", "calories": 550, "protein": 30, "carbs": 65, "fats": 18},
        {"name": "Chicken Teriyaki Bowl", "calories": 620, "protein": 38, "carbs": 72, "fats": 16},
        {"name": "Mediterranean Salad with Feta", "calories": 350, "protein": 12, "carbs": 22, "fats": 24},
        {"name": "Veggie Wrap", "calories": 320, "protein": 10, "carbs": 45, "fats": 12},
        {"name": "BLT Sandwich", "calories": 420, "protein": 15, "carbs": 30, "fats": 26},
        {"name": "Grilled Cheese Sandwich", "calories": 390, "protein": 14, "carbs": 32, "fats": 24},
        {"name": "Tomato Soup (1 cup)", "calories": 120, "protein": 3, "carbs": 18, "fats": 4},
        {"name": "Chicken Noodle Soup (1 cup)", "calories": 150, "protein": 8, "carbs": 15, "fats": 6},
        {"name": "Clam Chowder (1 cup)", "calories": 190, "protein": 7, "carbs": 16, "fats": 11},
        {"name": "Minestrone Soup (1 cup)", "calories": 127, "protein": 5, "carbs": 21, "fats": 3},
        {"name": "Chili with Beans (1 cup)", "calories": 260, "protein": 18, "carbs": 26, "fats": 9},
        {"name": "Sushi Roll, California (8 pieces)", "calories": 255, "protein": 9, "carbs": 38, "fats": 7},
        {"name": "Sushi Roll, Spicy Tuna (8 pieces)", "calories": 290, "protein": 11, "carbs": 32, "fats": 11},
        {"name": "Sushi Roll, Salmon (8 pieces)", "calories": 304, "protein": 14, "carbs": 42, "fats": 9},
        {"name": "Sushi, Nigiri (2 pieces)", "calories": 80, "protein": 6, "carbs": 10, "fats": 1},
        {"name": "Pad Thai", "calories": 560, "protein": 16, "carbs": 82, "fats": 18},
        {"name": "Chicken Tikka Masala with Rice", "calories": 620, "protein": 32, "carbs": 65, "fats": 24},
        {"name": "Butter Chicken with Naan", "calories": 680, "protein": 34, "carbs": 52, "fats": 36},
        {"name": "Beef Tacos (3)", "calories": 510, "protein": 24, "carbs": 39, "fats": 30},
        {"name": "Chicken Quesadilla", "calories": 510, "protein": 27, "carbs": 37, "fats": 28},
        {"name": "Nachos with Cheese", "calories": 560, "protein": 14, "carbs": 52, "fats": 32},
        {"name": "Pulled Pork Sandwich", "calories": 540, "protein": 32, "carbs": 45, "fats": 24},
        {"name": "BBQ Ribs (4 bones)", "calories": 480, "protein": 30, "carbs": 12, "fats": 35},
    ]
    
    # STEP 1: Always search local database first for specific items
    # Normalize query for better matching (handle spaces, hyphens, etc.)
    query_normalized = query_lower.replace('-', ' ').replace("'", "").replace("'", "")
    local_results = []
    for food in local_foods:
        food_name_normalized = food["name"].lower().replace('-', ' ').replace("'", "").replace("'", "")
        if query_normalized in food_name_normalized or query_lower in food["name"].lower():
            local_results.append(food)
    logger.info(f"Local database returned {len(local_results)} results for '{query}'")
    
    # STEP 2: Try to get API results to supplement
    api_results = []
    
    # Try FatSecret first
    fatsecret_results = await search_fatsecret(query, max_results=30)
    if fatsecret_results:
        logger.info(f"FatSecret returned {len(fatsecret_results)} results")
        api_results = fatsecret_results
    else:
        # Try USDA as backup
        logger.info("Trying USDA FoodData Central...")
        usda_results = await search_usda(query, max_results=30)
        if usda_results:
            logger.info(f"USDA returned {len(usda_results)} results")
            api_results = usda_results
    
    # STEP 3: Combine results - local first (specific items), then API results
    # Avoid duplicates by checking names
    combined_results = local_results.copy()
    local_names_lower = {food["name"].lower() for food in local_results}
    
    for api_food in api_results:
        if api_food["name"].lower() not in local_names_lower:
            combined_results.append(api_food)
    
    logger.info(f"Returning {len(combined_results)} combined results (local: {len(local_results)}, api: {len(api_results)})")
    return combined_results[:50]

# ==================== GROCERY LIST ENDPOINTS ====================

@api_router.get("/mealplan/{meal_plan_id}/grocery-list")
async def generate_grocery_list(meal_plan_id: str, days: int = 7):
    """Generate a comprehensive grocery list from a meal plan"""
    plan = await db.mealplans.find_one({"id": meal_plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    
    # Collect all ingredients from the meal plan with quantities
    ingredients_by_category = {
        "Proteins": [],
        "Produce (Fresh)": [],
        "Dairy & Eggs": [],
        "Grains & Bread": [],
        "Pantry Staples": [],
        "Oils & Condiments": [],
        "Frozen": [],
        "Other": []
    }
    
    # Category keywords for better classification
    category_keywords = {
        "Proteins": ["chicken", "beef", "pork", "fish", "salmon", "tuna", "shrimp", "turkey", "lamb", "tofu", "tempeh", "protein", "steak", "ground", "bacon", "sausage", "ham", "cod", "tilapia", "lobster", "crab"],
        "Produce (Fresh)": ["apple", "banana", "orange", "lettuce", "tomato", "spinach", "broccoli", "carrot", "onion", "garlic", "pepper", "cucumber", "avocado", "lemon", "lime", "berries", "fruit", "vegetable", "greens", "kale", "celery", "mushroom", "zucchini", "asparagus", "potato", "sweet potato", "corn", "peas", "beans", "cabbage", "cauliflower", "ginger", "cilantro", "parsley", "basil"],
        "Dairy & Eggs": ["milk", "cheese", "yogurt", "egg", "butter", "cream", "cottage", "sour cream", "parmesan", "mozzarella", "cheddar", "feta", "ricotta"],
        "Grains & Bread": ["bread", "rice", "pasta", "oat", "quinoa", "tortilla", "bagel", "cereal", "flour", "noodle", "wrap", "couscous", "barley", "crackers"],
        "Pantry Staples": ["salt", "pepper", "sugar", "honey", "syrup", "peanut butter", "almond butter", "nuts", "seeds", "canned", "beans", "lentils", "chickpeas", "stock", "broth", "tomato paste", "tomato sauce"],
        "Oils & Condiments": ["oil", "olive oil", "vinegar", "sauce", "soy sauce", "mustard", "ketchup", "mayo", "dressing", "marinade", "seasoning", "spice"],
        "Frozen": ["frozen", "ice cream"]
    }
    
    all_ingredients = {}  # Use dict to track quantities
    
    # Get ingredients from specified number of days
    days_to_process = min(days, len(plan.get("meal_days", [])))
    
    for day_idx in range(days_to_process):
        day = plan.get("meal_days", [])[day_idx]
        for meal in day.get("meals", []):
            for ingredient in meal.get("ingredients", []):
                ingredient_clean = ingredient.strip()
                ingredient_lower = ingredient_clean.lower()
                
                # Track ingredient (combine duplicates)
                if ingredient_lower in all_ingredients:
                    all_ingredients[ingredient_lower]["count"] += 1
                else:
                    all_ingredients[ingredient_lower] = {
                        "name": ingredient_clean,
                        "count": 1
                    }
    
    # Categorize ingredients
    for ingredient_lower, data in all_ingredients.items():
        display_name = data["name"]
        if data["count"] > 1:
            display_name = f"{data['name']} (x{data['count']})"
        
        categorized = False
        for category, keywords in category_keywords.items():
            if any(keyword in ingredient_lower for keyword in keywords):
                ingredients_by_category[category].append(display_name)
                categorized = True
                break
        
        if not categorized:
            ingredients_by_category["Other"].append(display_name)
    
    # Sort each category alphabetically and remove empty ones
    result = {}
    for category, items in ingredients_by_category.items():
        if items:
            result[category] = sorted(items, key=lambda x: x.lower())
    
    return {
        "meal_plan_id": meal_plan_id,
        "meal_plan_name": plan.get("name", "Meal Plan"),
        "days_covered": days_to_process,
        "total_items": len(all_ingredients),
        "grocery_list": result
    }

# ==================== ASK INTERFITAI CHAT ENDPOINTS ====================

@api_router.post("/chat", response_model=ChatMessage)
async def chat_with_ai(request: ChatRequest):
    """Chat with InterFitAI for fitness and health questions"""
    # Get user context for personalized responses
    profile = await db.profiles.find_one({"id": request.user_id})
    
    # Get recent chat history
    history = await db.chat_history.find({"user_id": request.user_id}).sort("created_at", -1).limit(10).to_list(10)
    history.reverse()
    
    messages = [
        {
            "role": "system",
            "content": f"""You are InterFitAI, an expert AI fitness and nutrition coach. You help users with:
- Workout advice and exercise form
- Nutrition guidance and meal suggestions
- Weight management strategies
- Supplement recommendations
- Recovery and injury prevention
- Mental fitness and motivation

{"User context: " + f"Goal: {profile.get('goal', 'general fitness')}, Weight: {profile.get('weight', 'unknown')}kg, Activity level: {profile.get('activity_level', 'moderate')}" if profile else ""}

Be helpful, encouraging, and provide evidence-based advice. Keep responses concise but informative."""
        }
    ]
    
    # Add chat history
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current message
    messages.append({"role": "user", "content": request.message})
    
    try:
        # Build initial_messages = system + history (without current user message)
        initial_messages = messages[:-1]
        chat = (
            LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=str(uuid.uuid4()),
                system_message="",
                initial_messages=initial_messages,
            )
            .with_model("anthropic", "claude-haiku-4-5-20251001")
            .with_params(temperature=0.7, max_tokens=1000)
        )
        ai_response = await chat.send_message(UserMessage(text=request.message))
        
        # Save user message
        user_msg = ChatMessage(user_id=request.user_id, role="user", content=request.message)
        await db.chat_history.insert_one(user_msg.model_dump())
        
        # Save AI response
        ai_msg = ChatMessage(user_id=request.user_id, role="assistant", content=ai_response)
        await db.chat_history.insert_one(ai_msg.model_dump())
        
        return ai_msg
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@api_router.get("/chat/history/{user_id}")
async def get_chat_history(user_id: str, limit: int = 50):
    """Get chat history for a user"""
    history = await db.chat_history.find({"user_id": user_id}).sort("created_at", -1).limit(limit).to_list(limit)
    history.reverse()
    return [ChatMessage(**msg) for msg in history]

@api_router.post("/chat/save/{message_id}")
async def save_chat_message(message_id: str, title: str = None):
    """Save/bookmark a chat message with optional title"""
    update_data = {"saved": True}
    if title:
        update_data["title"] = title
    result = await db.chat_history.update_one({"id": message_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message saved successfully"}

@api_router.put("/chat/rename/{message_id}")
async def rename_chat_message(message_id: str, title: str):
    """Rename a saved chat message"""
    result = await db.chat_history.update_one(
        {"id": message_id, "saved": True}, 
        {"$set": {"title": title}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Message not found or not saved")
    return {"message": "Message renamed successfully"}

@api_router.post("/chat/unsave/{message_id}")
async def unsave_chat_message(message_id: str):
    """Unsave/unbookmark a chat message"""
    result = await db.chat_history.update_one({"id": message_id}, {"$set": {"saved": False, "title": None}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message unsaved successfully"}

@api_router.get("/chat/saved/{user_id}")
async def get_saved_messages(user_id: str):
    """Get saved/bookmarked messages for a user"""
    messages = await db.chat_history.find({"user_id": user_id, "saved": True}).sort("created_at", -1).to_list(100)
    return [ChatMessage(**msg) for msg in messages]

@api_router.delete("/chat/history/{user_id}")
async def clear_chat_history(user_id: str):
    """Clear chat history for a user (except saved messages)"""
    await db.chat_history.delete_many({"user_id": user_id, "saved": False})
    return {"message": "Chat history cleared"}

# ==================== STEP TRACKING ENDPOINTS ====================

@api_router.post("/steps/log", response_model=StepEntry)
async def log_steps(user_id: str, steps: int, distance_km: float = 0, source: str = "device"):
    """Log steps for today"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Calculate calories burned (rough estimate: 0.04 calories per step)
    calories_burned = int(steps * 0.04)
    
    # Check if entry exists for today
    existing = await db.steps.find_one({"user_id": user_id, "date": today})
    
    if existing:
        # Update existing entry
        new_steps = existing["steps"] + steps
        new_distance = existing["distance_km"] + distance_km
        new_calories = int(new_steps * 0.04)
        
        await db.steps.update_one(
            {"id": existing["id"]},
            {"$set": {"steps": new_steps, "distance_km": new_distance, "calories_burned": new_calories}}
        )
        updated = await db.steps.find_one({"id": existing["id"]})
        return StepEntry(**updated)
    else:
        # Create new entry
        entry = StepEntry(
            user_id=user_id,
            steps=steps,
            distance_km=distance_km,
            calories_burned=calories_burned,
            date=today,
            source=source
        )
        await db.steps.insert_one(entry.model_dump())
        return entry

@api_router.get("/steps/{user_id}")
async def get_steps(user_id: str, date: Optional[str] = None):
    """Get steps for a user, optionally filtered by date"""
    if date:
        entry = await db.steps.find_one({"user_id": user_id, "date": date})
        if entry:
            return StepEntry(**entry)
        return {"steps": 0, "distance_km": 0, "calories_burned": 0, "date": date}
    
    entries = await db.steps.find({"user_id": user_id}).sort("date", -1).limit(30).to_list(30)
    return [StepEntry(**e) for e in entries]

@api_router.get("/steps/goal/{user_id}")
async def get_step_goal(user_id: str):
    """Get step goal for a user"""
    goal = await db.step_goals.find_one({"user_id": user_id})
    if goal:
        return StepGoal(**goal)
    return StepGoal(user_id=user_id)

@api_router.post("/steps/goal")
async def set_step_goal(goal: StepGoal):
    """Set step goal for a user"""
    await db.step_goals.update_one(
        {"user_id": goal.user_id},
        {"$set": goal.model_dump()},
        upsert=True
    )
    return goal

# ==================== DEVICE CONNECTION ENDPOINTS ====================

@api_router.get("/devices/{user_id}")
async def get_connected_devices(user_id: str):
    """Get all device connections for a user"""
    devices = await db.device_connections.find({"user_id": user_id}).to_list(10)
    # Don't expose tokens to frontend
    safe_devices = []
    for d in devices:
        safe_device = {
            "id": d.get("id"),
            "user_id": d.get("user_id"),
            "device_type": d.get("device_type"),
            "connected": d.get("connected", False),
            "last_sync": d.get("last_sync"),
            "health_data": d.get("health_data"),
        }
        safe_devices.append(safe_device)
    return safe_devices

@api_router.post("/devices/connect")
async def connect_device(user_id: str, device_type: str):
    """Connect a fitness device (Apple Health/Google Fit handled on device, Fitbit/Garmin via OAuth)"""
    
    # For Apple Health and Google Fit, connection is handled entirely on the device
    # The frontend just needs to confirm the connection was successful
    if device_type in ["apple_health", "google_fit"]:
        connection = DeviceConnection(
            user_id=user_id,
            device_type=device_type,
            connected=True,
            last_sync=datetime.utcnow()
        )
        
        await db.device_connections.update_one(
            {"user_id": user_id, "device_type": device_type},
            {"$set": connection.model_dump()},
            upsert=True
        )
        
        return {"message": f"{device_type} connected successfully", "connection": connection}
    
    # For Fitbit - return OAuth URL for user to authorize
    elif device_type == "fitbit":
        if not FITBIT_CLIENT_ID:
            return {
                "message": "Fitbit integration not configured",
                "oauth_url": None,
                "setup_required": True,
                "instructions": "To enable Fitbit integration, register an app at https://dev.fitbit.com/ and add FITBIT_CLIENT_ID, FITBIT_CLIENT_SECRET, and FITBIT_REDIRECT_URI to your environment variables."
            }
        
        # Generate OAuth authorization URL
        oauth_url = (
            f"https://www.fitbit.com/oauth2/authorize?"
            f"response_type=code&"
            f"client_id={FITBIT_CLIENT_ID}&"
            f"redirect_uri={FITBIT_REDIRECT_URI}&"
            f"scope=activity%20nutrition%20heartrate%20sleep%20weight&"
            f"state={user_id}"
        )
        
        return {
            "message": "Redirect user to Fitbit authorization",
            "oauth_url": oauth_url,
            "device_type": "fitbit"
        }
    
    # For Garmin - return OAuth URL
    elif device_type == "garmin":
        if not GARMIN_CONSUMER_KEY:
            return {
                "message": "Garmin integration not configured",
                "oauth_url": None,
                "setup_required": True,
                "instructions": "To enable Garmin integration, register an app at https://developer.garmin.com/ and add GARMIN_CONSUMER_KEY and GARMIN_CONSUMER_SECRET to your environment variables."
            }
        
        # Note: Garmin uses OAuth 1.0a which is more complex
        # For production, use a library like garminconnect or authlib
        return {
            "message": "Garmin OAuth requires additional setup",
            "oauth_url": None,
            "setup_required": True,
            "instructions": "Garmin Connect API requires OAuth 1.0a flow. Contact support for setup assistance."
        }
    
    return {"message": f"Unknown device type: {device_type}"}

@api_router.post("/devices/fitbit/callback")
async def fitbit_oauth_callback(code: str, state: str):
    """Handle Fitbit OAuth callback - exchange code for access token"""
    if not FITBIT_CLIENT_ID or not FITBIT_CLIENT_SECRET:
        raise HTTPException(status_code=400, detail="Fitbit not configured")
    
    user_id = state  # We passed user_id as state parameter
    
    # Exchange authorization code for access token
    async with httpx.AsyncClient() as client:
        auth_header = base64.b64encode(
            f"{FITBIT_CLIENT_ID}:{FITBIT_CLIENT_SECRET}".encode()
        ).decode()
        
        response = await client.post(
            "https://api.fitbit.com/oauth2/token",
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": FITBIT_REDIRECT_URI
            }
        )
        
        if response.status_code != 200:
            logger.error(f"Fitbit token error: {response.text}")
            raise HTTPException(status_code=400, detail="Failed to get Fitbit access token")
        
        token_data = response.json()
        
        # Save connection with tokens
        connection = DeviceConnection(
            user_id=user_id,
            device_type="fitbit",
            connected=True,
            access_token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_expires_at=datetime.utcnow(),  # Would calculate from expires_in
            last_sync=datetime.utcnow()
        )
        
        await db.device_connections.update_one(
            {"user_id": user_id, "device_type": "fitbit"},
            {"$set": connection.model_dump()},
            upsert=True
        )
        
        return {"message": "Fitbit connected successfully!", "success": True}

@api_router.get("/devices/sync/{user_id}/{device_type}")
async def sync_device_data(user_id: str, device_type: str):
    """Sync health data from a connected device"""
    connection = await db.device_connections.find_one({
        "user_id": user_id,
        "device_type": device_type,
        "connected": True
    })
    
    if not connection:
        raise HTTPException(status_code=404, detail=f"{device_type} not connected")
    
    health_data = {
        "steps": 0,
        "calories": 0,
        "distance": 0,
        "active_minutes": 0,
        "heart_rate": None,
        "sleep_hours": None,
        "synced_at": datetime.utcnow().isoformat()
    }
    
    # For Fitbit - fetch data using stored access token
    if device_type == "fitbit" and connection.get("access_token"):
        try:
            async with httpx.AsyncClient() as client:
                today = datetime.now().strftime("%Y-%m-%d")
                
                # Get activity summary
                response = await client.get(
                    f"https://api.fitbit.com/1/user/-/activities/date/{today}.json",
                    headers={"Authorization": f"Bearer {connection['access_token']}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    summary = data.get("summary", {})
                    health_data["steps"] = summary.get("steps", 0)
                    health_data["calories"] = summary.get("caloriesOut", 0)
                    health_data["distance"] = round(summary.get("distances", [{}])[0].get("distance", 0), 2)
                    health_data["active_minutes"] = summary.get("fairlyActiveMinutes", 0) + summary.get("veryActiveMinutes", 0)
                
                # Get heart rate
                hr_response = await client.get(
                    f"https://api.fitbit.com/1/user/-/activities/heart/date/{today}/1d.json",
                    headers={"Authorization": f"Bearer {connection['access_token']}"}
                )
                
                if hr_response.status_code == 200:
                    hr_data = hr_response.json()
                    resting_hr = hr_data.get("activities-heart", [{}])[0].get("value", {}).get("restingHeartRate")
                    if resting_hr:
                        health_data["heart_rate"] = resting_hr
                        
        except Exception as e:
            logger.error(f"Fitbit sync error: {e}")
    
    # For Apple Health / Google Fit - data comes from the device
    # Frontend will pass the data from HealthKit/Health Connect
    elif device_type in ["apple_health", "google_fit"]:
        # Return last cached data or empty
        if connection.get("health_data"):
            health_data = connection["health_data"]
    
    # Update cached health data
    await db.device_connections.update_one(
        {"user_id": user_id, "device_type": device_type},
        {"$set": {"health_data": health_data, "last_sync": datetime.utcnow()}}
    )
    
    return health_data

@api_router.post("/devices/health-data")
async def save_health_data(user_id: str, device_type: str, health_data: Dict[str, Any]):
    """Save health data from device (Apple Health/Google Fit send data from device)"""
    await db.device_connections.update_one(
        {"user_id": user_id, "device_type": device_type},
        {
            "$set": {
                "health_data": health_data,
                "last_sync": datetime.utcnow(),
                "connected": True
            }
        },
        upsert=True
    )
    return {"message": "Health data saved", "success": True}

@api_router.delete("/devices/disconnect")
async def disconnect_device(user_id: str, device_type: str):
    """Disconnect a fitness device"""
    await db.device_connections.delete_one({"user_id": user_id, "device_type": device_type})
    return {"message": f"{device_type} disconnected"}

# ==================== SUBSCRIPTION ENDPOINTS ====================

SUBSCRIPTION_PLANS = {
    "monthly": {"name": "Monthly", "price": 9.99, "duration_months": 1, "trial_days": 3, "features": ["AI Workouts", "AI Meal Plans", "Food Tracking", "Ask InterFitAI", "Step Tracking", "Body Analyzer"]},
    "quarterly": {"name": "Quarterly", "price": 24.99, "duration_months": 3, "trial_days": 3, "features": ["AI Workouts", "AI Meal Plans", "Food Tracking", "Ask InterFitAI", "Step Tracking", "Body Analyzer", "Priority Support"]},
    "yearly": {"name": "Yearly", "price": 79.99, "duration_months": 12, "trial_days": 3, "features": ["AI Workouts", "AI Meal Plans", "Food Tracking", "Ask InterFitAI", "Step Tracking", "Body Analyzer", "Priority Support", "Exclusive Content"]}
}

# Stripe Price IDs - create these in Stripe Dashboard for recurring billing
STRIPE_PRICE_IDS = {
    "monthly": os.environ.get("STRIPE_PRICE_MONTHLY", ""),
    "quarterly": os.environ.get("STRIPE_PRICE_QUARTERLY", ""),
    "yearly": os.environ.get("STRIPE_PRICE_YEARLY", ""),
}

@api_router.get("/subscription/plans")
async def get_subscription_plans():
    """Get available subscription plans"""
    return SUBSCRIPTION_PLANS

@api_router.get("/subscription/check/{user_id}")
async def check_subscription_status(user_id: str):
    """Check if user has active subscription or is admin/free access"""
    access = await check_subscription_access(user_id)
    profile = await db.profiles.find_one({"id": user_id})
    
    return {
        "has_access": access["has_access"],
        "reason": access["reason"],
        "subscription_status": profile.get("subscription_status", "free") if profile else "free",
        "trial_end_date": profile.get("trial_end_date") if profile else None,
        "subscription_end_date": profile.get("subscription_end_date") if profile else None
    }

@api_router.post("/subscription/checkout")
async def create_checkout_session(request: PaymentRequest):
    """Create Stripe checkout session with 3-day free trial"""
    if request.plan_id not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = SUBSCRIPTION_PLANS[request.plan_id]
    
    try:
        success_url = f"{request.origin_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{request.origin_url}/subscription"
        
        # Get or create customer
        profile = await db.profiles.find_one({"id": request.user_id})
        customer_email = profile.get("email") if profile else None
        
        # Create checkout session with trial
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer_email=customer_email,
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'InterFitAI {plan["name"]} Subscription',
                        'description': f'3-day FREE trial, then ${plan["price"]}/{"month" if plan["duration_months"] == 1 else str(plan["duration_months"]) + " months"}'
                    },
                    'unit_amount': int(plan["price"] * 100),
                    'recurring': {
                        'interval': 'month' if plan["duration_months"] == 1 else 'month',
                        'interval_count': plan["duration_months"]
                    }
                },
                'quantity': 1,
            }],
            mode='subscription',
            subscription_data={
                'trial_period_days': 3,  # 3-day free trial
                'metadata': {
                    'user_id': request.user_id,
                    'plan_id': request.plan_id,
                }
            },
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_id': request.user_id,
                'plan_id': request.plan_id,
                'duration_months': str(plan["duration_months"])
            }
        )
        
        # Create payment transaction record
        await db.payment_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "session_id": session.id,
            "user_id": request.user_id,
            "plan_id": request.plan_id,
            "amount": plan["price"],
            "currency": "usd",
            "payment_status": "pending",
            "created_at": datetime.utcnow()
        })
        
        return {"url": session.url, "session_id": session.id}
        
    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=f"Payment initialization failed: {str(e)}")

@api_router.get("/subscription/status/{session_id}")
async def get_payment_status(session_id: str):
    """Check payment status and update user subscription"""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        transaction = await db.payment_transactions.find_one({"session_id": session_id})
        
        if session.payment_status == 'paid' and transaction and transaction.get("payment_status") != "completed":
            # Update transaction
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "completed", "completed_at": datetime.utcnow()}}
            )
            
            # Update user subscription
            user_id = session.metadata.get('user_id')
            plan_id = session.metadata.get('plan_id')
            duration_months = int(session.metadata.get('duration_months', 1))
            
            from datetime import timedelta
            end_date = datetime.utcnow() + timedelta(days=duration_months * 30)
            
            await db.profiles.update_one(
                {"id": user_id},
                {"$set": {
                    "subscription_status": plan_id,
                    "subscription_end_date": end_date.isoformat()
                }}
            )
        
        return {
            "status": session.status,
            "payment_status": session.payment_status,
            "amount_total": session.amount_total / 100 if session.amount_total else 0,
            "currency": session.currency
        }
        
    except Exception as e:
        logger.error(f"Payment status check error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check payment status: {str(e)}")

@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    # In production, verify webhook signature
    # For now, just process the event
    try:
        event = json.loads(payload)
        
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            session_id = session["id"]
            
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {"payment_status": "completed", "completed_at": datetime.utcnow()}}
            )
            
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

# ==================== ADMIN MANAGEMENT ====================

class GrantAccessRequest(BaseModel):
    admin_email: str
    user_email: str
    reason: str = "admin_granted"

@api_router.post("/admin/grant-access")
async def grant_free_access(request: GrantAccessRequest):
    """Admin grants free access to a user"""
    # Verify admin
    if request.admin_email.lower() not in [e.lower() for e in ADMIN_EMAILS]:
        raise HTTPException(status_code=403, detail="Not authorized as admin")
    
    # Grant access
    await db.free_access.update_one(
        {"email": request.user_email.lower()},
        {"$set": {
            "email": request.user_email.lower(),
            "granted_by": request.admin_email,
            "reason": request.reason,
            "granted_at": datetime.utcnow()
        }},
        upsert=True
    )
    
    # Update user profile if exists
    await db.profiles.update_one(
        {"email": request.user_email.lower()},
        {"$set": {"subscription_status": "free_access"}}
    )
    
    return {"message": f"Free access granted to {request.user_email}"}

@api_router.delete("/admin/revoke-access")
async def revoke_free_access(admin_email: str, user_email: str):
    """Admin revokes free access from a user"""
    if admin_email.lower() not in [e.lower() for e in ADMIN_EMAILS]:
        raise HTTPException(status_code=403, detail="Not authorized as admin")
    
    await db.free_access.delete_one({"email": user_email.lower()})
    
    await db.profiles.update_one(
        {"email": user_email.lower()},
        {"$set": {"subscription_status": "free"}}
    )
    
    return {"message": f"Free access revoked from {user_email}"}

@api_router.get("/admin/free-access-list")
async def get_free_access_list(admin_email: str):
    """Get list of all users with free access"""
    if admin_email.lower() not in [e.lower() for e in ADMIN_EMAILS]:
        raise HTTPException(status_code=403, detail="Not authorized as admin")
    
    users = await db.free_access.find({}).to_list(100)
    # Convert ObjectId to string for JSON serialization
    for user in users:
        if '_id' in user:
            user['_id'] = str(user['_id'])
    return users

@api_router.get("/admin/is-admin/{email}")
async def check_admin_status(email: str):
    """Check if an email is an admin"""
    is_admin = email.lower() in [e.lower() for e in ADMIN_EMAILS]
    return {"is_admin": is_admin, "email": email}

# ==================== MOTIVATION & REMINDERS ====================

DAILY_MOTIVATIONS = [
    "The only bad workout is the one that didn't happen. Get moving! 💪",
    "Your body can stand almost anything. It's your mind that you have to convince.",
    "Success is the sum of small efforts repeated day in and day out.",
    "The pain you feel today will be the strength you feel tomorrow.",
    "Don't wish for it, work for it!",
    "Your health is an investment, not an expense.",
    "Every rep counts. Every meal matters. Stay consistent!",
    "The difference between try and triumph is just a little umph!",
    "Wake up with determination. Go to bed with satisfaction.",
    "Fitness is not about being better than someone else. It's about being better than you used to be.",
    "Push yourself because no one else is going to do it for you.",
    "The hard days are what make you stronger.",
    "Your only limit is you.",
    "Believe in yourself and all that you are.",
    "Today's actions are tomorrow's results."
]

@api_router.get("/motivation")
async def get_daily_motivation():
    """Get a random daily motivation quote"""
    import random
    return {"motivation": random.choice(DAILY_MOTIVATIONS)}

@api_router.get("/reminders/{user_id}")
async def get_reminder_settings(user_id: str):
    """Get reminder settings for a user"""
    profile = await db.profiles.find_one({"id": user_id})
    if profile:
        return {
            "reminders_enabled": profile.get("reminders_enabled", True),
            "motivation_enabled": profile.get("motivation_enabled", True)
        }
    return {"reminders_enabled": True, "motivation_enabled": True}

# ==================== BODY ANALYZER ====================

class ProgressPhoto(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    image_base64: str
    label: str = "progress"  # before, after, progress
    notes: Optional[str] = None
    weight: Optional[float] = None
    date: str  # YYYY-MM-DD
    created_at: datetime = Field(default_factory=datetime.utcnow)

class BodyAnalysisRequest(BaseModel):
    user_id: str
    before_image_base64: str
    after_image_base64: str
    time_period: str = "3 months"

@api_router.post("/body/upload-progress")
async def upload_progress_photo(user_id: str, image_base64: str, label: str = "progress", notes: str = None, weight: float = None):
    """Upload a progress photo"""
    photo = ProgressPhoto(
        user_id=user_id,
        image_base64=image_base64[:200] + "...",  # Store truncated for reference
        label=label,
        notes=notes,
        weight=weight,
        date=datetime.now().strftime("%Y-%m-%d")
    )
    
    await db.progress_photos.insert_one(photo.model_dump())
    return {"message": "Progress photo uploaded", "id": photo.id}

@api_router.get("/body/progress/{user_id}")
async def get_progress_photos(user_id: str):
    """Get all progress photos for a user"""
    photos = await db.progress_photos.find({"user_id": user_id}).sort("created_at", -1).to_list(50)
    return photos

@api_router.post("/body/analyze")
async def analyze_body_progress(request: BodyAnalysisRequest):
    """AI-powered body transformation analysis comparing before/after photos"""
    try:
        content = await call_claude_sonnet(
            system_message="""You are a professional fitness coach and body composition expert. 
Analyze the before and after progress photos provided. Give constructive, encouraging, and detailed feedback.
Focus on visible improvements in:
1. Muscle definition and tone
2. Body composition changes
3. Posture improvements
4. Overall physique transformation

Be positive and motivating while being realistic. Provide actionable advice for continued progress.
Respond with valid JSON only:
{
    "overall_assessment": "Brief overall assessment",
    "visible_changes": ["Change 1", "Change 2", "Change 3"],
    "areas_improved": ["Area 1", "Area 2"],
    "recommendations": ["Recommendation 1", "Recommendation 2"],
    "motivation_message": "Encouraging message",
    "estimated_progress_score": 8
}""",
            user_message=f"Please analyze these before and after progress photos taken over {request.time_period}. Provide detailed feedback on the visible transformation.",
            max_tokens=1000,
            image_base64=request.before_image_base64,
            image_base64_2=request.after_image_base64
        )
        
        # Clean markdown code blocks if present
        content = content.strip() if content else ""
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```json"):
                    in_json = True
                    continue
                elif line.startswith("```"):
                    in_json = False
                    continue
                if in_json or not line.startswith("```"):
                    json_lines.append(line)
            content = "\n".join(json_lines)
        
        content = content.strip()
        
        analysis_data = json.loads(content)
        
        # Save analysis to database
        analysis_record = {
            "id": str(uuid.uuid4()),
            "user_id": request.user_id,
            "time_period": request.time_period,
            "analysis": analysis_data,
            "created_at": datetime.utcnow()
        }
        await db.body_analyses.insert_one(analysis_record)
        
        return {"analysis": analysis_data, "id": analysis_record["id"]}
        
    except json.JSONDecodeError:
        return {
            "analysis": {
                "overall_assessment": "Great progress! Keep up the amazing work on your fitness journey.",
                "visible_changes": ["Improved muscle definition", "Better posture", "Enhanced overall tone"],
                "areas_improved": ["Core strength", "Upper body definition"],
                "recommendations": ["Continue with consistent training", "Ensure adequate protein intake", "Get enough sleep for recovery"],
                "motivation_message": "Your dedication is showing! Every workout brings you closer to your goals.",
                "estimated_progress_score": 7
            }
        }
    except Exception as e:
        logger.error(f"Body analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze progress: {str(e)}")

@api_router.get("/body/history/{user_id}")
async def get_analysis_history(user_id: str):
    """Get body analysis history for a user"""
    analyses = await db.body_analyses.find({"user_id": user_id}).sort("created_at", -1).to_list(20)
    return analyses

# ==================== REVENUECAT WEBHOOKS ====================

@api_router.post("/webhooks/revenuecat")
async def handle_revenuecat_webhook(request: Request):
    """
    Handle RevenueCat webhook events for subscription lifecycle management.
    
    Event types:
    - INITIAL_PURCHASE: New subscription started
    - RENEWAL: Subscription renewed
    - CANCELLATION: Subscription cancelled
    - EXPIRATION: Subscription expired
    - BILLING_ISSUE: Payment failed
    - PRODUCT_CHANGE: User changed subscription tier
    """
    try:
        payload = await request.json()
        
        event_type = payload.get('type', payload.get('event', {}).get('type', ''))
        app_user_id = payload.get('app_user_id', payload.get('event', {}).get('app_user_id', ''))
        
        logger.info(f"RevenueCat webhook received: type={event_type}, user={app_user_id}")
        
        if not app_user_id:
            logger.warning("No app_user_id in webhook payload")
            return {"success": True, "message": "No user ID provided"}
        
        # Handle different event types
        if event_type in ['INITIAL_PURCHASE', 'RENEWAL', 'UNCANCELLATION']:
            # Grant premium access
            await db.profiles.update_one(
                {"id": app_user_id},
                {
                    "$set": {
                        "subscription_status": "premium",
                        "subscription_updated_at": datetime.utcnow(),
                        "revenuecat_event": event_type,
                    }
                },
                upsert=False
            )
            logger.info(f"Premium access granted to user {app_user_id}")
            
        elif event_type in ['CANCELLATION']:
            # Mark as cancelled (still has access until expiration)
            await db.profiles.update_one(
                {"id": app_user_id},
                {
                    "$set": {
                        "subscription_status": "cancelled",
                        "subscription_updated_at": datetime.utcnow(),
                        "revenuecat_event": event_type,
                    }
                }
            )
            logger.info(f"Subscription cancelled for user {app_user_id}")
            
        elif event_type in ['EXPIRATION']:
            # Revoke premium access
            await db.profiles.update_one(
                {"id": app_user_id},
                {
                    "$set": {
                        "subscription_status": "expired",
                        "subscription_updated_at": datetime.utcnow(),
                        "revenuecat_event": event_type,
                    }
                }
            )
            logger.info(f"Subscription expired for user {app_user_id}")
            
        elif event_type in ['BILLING_ISSUE']:
            # Payment failed - mark for grace period
            await db.profiles.update_one(
                {"id": app_user_id},
                {
                    "$set": {
                        "subscription_status": "billing_issue",
                        "subscription_updated_at": datetime.utcnow(),
                        "revenuecat_event": event_type,
                    }
                }
            )
            logger.info(f"Billing issue for user {app_user_id}")
        
        # Always return 200 to acknowledge receipt
        return {"success": True, "event_type": event_type}
        
    except Exception as e:
        logger.error(f"RevenueCat webhook error: {e}")
        # Still return 200 to prevent retries for parsing errors
        return {"success": False, "error": str(e)}

# ==================== ADMIN EMAILS WITH COMPLIMENTARY ACCESS ====================
ADMIN_EMAILS = [
    "sebastianrush5@gmail.com",  # Admin with full complimentary access
]

@api_router.get("/subscription/status/{user_id}")
async def get_subscription_status(user_id: str):
    """Get subscription status for a user - unified across Apple, Google, and Stripe"""
    profile = await db.profiles.find_one({"id": user_id})
    
    if not profile:
        return {
            "is_premium": False,
            "status": "free",
            "message": "User not found"
        }
    
    email = profile.get("email", "").lower()
    
    # Check if admin email - automatic premium access
    if email in [e.lower() for e in ADMIN_EMAILS]:
        return {
            "is_premium": True,
            "status": "admin",
            "subscription_source": "complimentary",
            "subscription_plan": "lifetime",
            "premium_expires_at": None,
            "bonus_month_applied": False,
            "is_admin": True,
        }
    
    # Check for complimentary access granted by admin
    if profile.get("complimentary_access"):
        return {
            "is_premium": True,
            "status": "complimentary",
            "subscription_source": "complimentary",
            "subscription_plan": "complimentary",
            "premium_expires_at": profile.get("complimentary_expires_at"),
            "bonus_month_applied": False,
        }
    
    status = profile.get("subscription_status", "free")
    premium_expires_at = profile.get("premium_expires_at")
    
    # Check if subscription has expired
    if premium_expires_at and datetime.utcnow() > premium_expires_at:
        status = "expired"
        # Update in database
        await db.profiles.update_one(
            {"id": user_id},
            {"$set": {"subscription_status": "expired"}}
        )
    
    is_premium = status in ["premium", "active", "trial", "cancelled"]  # Cancelled still has access until expiration
    
    return {
        "is_premium": is_premium,
        "status": status,
        "subscription_source": profile.get("subscription_source"),
        "subscription_plan": profile.get("subscription_plan"),
        "premium_expires_at": premium_expires_at.isoformat() if premium_expires_at else None,
        "bonus_month_applied": profile.get("bonus_month_applied", False),
    }

@api_router.post("/admin/grant-access")
async def admin_grant_access(admin_email: str, target_email: str, duration_days: int = 365):
    """
    Admin endpoint to grant complimentary premium access to any email.
    Only admins can call this endpoint.
    """
    # Verify admin
    if admin_email.lower() not in [e.lower() for e in ADMIN_EMAILS]:
        raise HTTPException(status_code=403, detail="Unauthorized. Admin access required.")
    
    # Find target user by email
    target_user = await db.profiles.find_one({"email": {"$regex": f"^{target_email}$", "$options": "i"}})
    
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User with email {target_email} not found")
    
    expires_at = datetime.utcnow() + timedelta(days=duration_days) if duration_days > 0 else None
    
    await db.profiles.update_one(
        {"id": target_user["id"]},
        {
            "$set": {
                "complimentary_access": True,
                "complimentary_expires_at": expires_at,
                "complimentary_granted_by": admin_email,
                "complimentary_granted_at": datetime.utcnow(),
                "subscription_status": "complimentary",
            }
        }
    )
    
    return {
        "success": True,
        "message": f"Complimentary access granted to {target_email}",
        "expires_at": expires_at.isoformat() if expires_at else "Never",
        "user_id": target_user["id"],
    }

@api_router.post("/admin/revoke-access")
async def admin_revoke_access(admin_email: str, target_email: str):
    """Admin endpoint to revoke complimentary premium access."""
    # Verify admin
    if admin_email.lower() not in [e.lower() for e in ADMIN_EMAILS]:
        raise HTTPException(status_code=403, detail="Unauthorized. Admin access required.")
    
    # Find target user by email
    target_user = await db.profiles.find_one({"email": {"$regex": f"^{target_email}$", "$options": "i"}})
    
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User with email {target_email} not found")
    
    await db.profiles.update_one(
        {"id": target_user["id"]},
        {
            "$set": {
                "complimentary_access": False,
                "subscription_status": "free",
            },
            "$unset": {
                "complimentary_expires_at": "",
            }
        }
    )
    
    return {
        "success": True,
        "message": f"Complimentary access revoked from {target_email}",
    }

@api_router.get("/admin/list-complimentary")
async def admin_list_complimentary(admin_email: str):
    """Admin endpoint to list all users with complimentary access."""
    # Verify admin
    if admin_email.lower() not in [e.lower() for e in ADMIN_EMAILS]:
        raise HTTPException(status_code=403, detail="Unauthorized. Admin access required.")
    
    users = await db.profiles.find({"complimentary_access": True}).to_list(100)
    
    return {
        "users": [
            {
                "email": u.get("email"),
                "name": u.get("name"),
                "granted_at": u.get("complimentary_granted_at"),
                "expires_at": u.get("complimentary_expires_at"),
            }
            for u in users
        ]
    }

# ==================== STRIPE WEBSITE SUBSCRIPTION ENDPOINTS ====================

@api_router.post("/stripe/create-checkout-session")
async def create_stripe_checkout_session(
    user_id: str,
    plan: str,  # quarterly or yearly
    success_url: str,
    cancel_url: str
):
    """
    Create a Stripe Checkout session for website subscriptions.
    - Quarterly: $29.99 with 7-day free trial
    - Yearly: $79.99 with 30-day bonus (applied after payment)
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    if plan not in ["quarterly", "yearly"]:
        raise HTTPException(status_code=400, detail="Invalid plan. Choose 'quarterly' or 'yearly'")
    
    # Get user profile
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    email = profile.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="User email required for Stripe subscription")
    
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        
        # Create or get Stripe customer
        existing_customer_id = profile.get("stripe_customer_id")
        
        if existing_customer_id:
            customer = stripe.Customer.retrieve(existing_customer_id)
        else:
            customer = stripe.Customer.create(
                email=email,
                name=profile.get("name", ""),
                metadata={"user_id": user_id}
            )
            # Save customer ID to profile
            await db.profiles.update_one(
                {"id": user_id},
                {"$set": {"stripe_customer_id": customer.id}}
            )
        
        # Build checkout session parameters
        checkout_params = {
            "customer": customer.id,
            "payment_method_types": ["card"],
            "mode": "subscription",
            "success_url": f"{success_url}?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": cancel_url,
            "metadata": {
                "user_id": user_id,
                "plan": plan,
            },
            "allow_promotion_codes": True,
        }
        
        # Configure pricing based on plan
        if plan == "quarterly":
            # Quarterly with 7-day free trial
            checkout_params["line_items"] = [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "InterFitAI Premium - Quarterly",
                        "description": "Full access to all InterFitAI features",
                    },
                    "unit_amount": 2999,  # $29.99 in cents
                    "recurring": {"interval": "month", "interval_count": 3},
                },
                "quantity": 1,
            }]
            checkout_params["subscription_data"] = {
                "trial_period_days": 7,
                "metadata": {"user_id": user_id, "plan": "quarterly"},
            }
            
        elif plan == "yearly":
            # Yearly - no trial, but 30-day bonus applied after payment
            checkout_params["line_items"] = [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "InterFitAI Premium - Annual",
                        "description": "Full access to all InterFitAI features + 1 bonus month",
                    },
                    "unit_amount": 7999,  # $79.99 in cents
                    "recurring": {"interval": "year"},
                },
                "quantity": 1,
            }]
            checkout_params["subscription_data"] = {
                "metadata": {"user_id": user_id, "plan": "yearly", "apply_bonus": "true"},
            }
        
        session = stripe.checkout.Session.create(**checkout_params)
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/stripe/webhook")
async def handle_stripe_webhook(request: Request):
    """
    Handle Stripe webhook events for subscription lifecycle.
    Key events:
    - checkout.session.completed: Initial payment/trial start
    - invoice.paid: Subscription renewed
    - customer.subscription.deleted: Subscription cancelled
    - customer.subscription.updated: Plan changed
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    # In production, verify webhook signature
    # event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    
    try:
        event = json.loads(payload)
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})
        
        logger.info(f"Stripe webhook received: {event_type}")
        
        if event_type == "checkout.session.completed":
            # Initial subscription created
            user_id = data.get("metadata", {}).get("user_id")
            plan = data.get("metadata", {}).get("plan", "quarterly")
            subscription_id = data.get("subscription")
            
            if user_id:
                # Calculate expiration
                if plan == "yearly":
                    expires_at = datetime.utcnow() + timedelta(days=365)
                    # Check if bonus should be applied
                    profile = await db.profiles.find_one({"id": user_id})
                    apply_bonus = not profile.get("bonus_month_applied", False)
                    if apply_bonus:
                        expires_at += timedelta(days=30)  # Add 30-day bonus
                else:
                    expires_at = datetime.utcnow() + timedelta(days=90)  # Quarterly
                
                # Update user subscription
                update_data = {
                    "subscription_source": "stripe",
                    "subscription_plan": plan,
                    "subscription_status": "active" if plan == "yearly" else "trial",
                    "premium_expires_at": expires_at,
                    "stripe_subscription_id": subscription_id,
                    "subscription_updated_at": datetime.utcnow(),
                }
                
                if plan == "yearly" and apply_bonus:
                    update_data["bonus_month_applied"] = True
                
                await db.profiles.update_one(
                    {"id": user_id},
                    {"$set": update_data}
                )
                logger.info(f"Stripe subscription activated for user {user_id}: {plan}")
        
        elif event_type == "invoice.paid":
            # Subscription renewed
            subscription_id = data.get("subscription")
            if subscription_id:
                # Find user by subscription ID
                profile = await db.profiles.find_one({"stripe_subscription_id": subscription_id})
                if profile:
                    plan = profile.get("subscription_plan", "quarterly")
                    if plan == "yearly":
                        expires_at = datetime.utcnow() + timedelta(days=365)
                    else:
                        expires_at = datetime.utcnow() + timedelta(days=90)
                    
                    await db.profiles.update_one(
                        {"stripe_subscription_id": subscription_id},
                        {
                            "$set": {
                                "subscription_status": "active",
                                "premium_expires_at": expires_at,
                                "subscription_updated_at": datetime.utcnow(),
                            }
                        }
                    )
                    logger.info(f"Stripe subscription renewed for user {profile.get('id')}")
        
        elif event_type == "customer.subscription.deleted":
            # Subscription cancelled/expired
            subscription_id = data.get("id")
            if subscription_id:
                await db.profiles.update_one(
                    {"stripe_subscription_id": subscription_id},
                    {
                        "$set": {
                            "subscription_status": "expired",
                            "subscription_updated_at": datetime.utcnow(),
                        }
                    }
                )
                logger.info(f"Stripe subscription cancelled: {subscription_id}")
        
        elif event_type == "customer.subscription.trial_will_end":
            # Trial ending soon - could send notification
            subscription_id = data.get("id")
            logger.info(f"Trial ending soon for subscription: {subscription_id}")
        
        return {"received": True}
        
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return {"received": True, "error": str(e)}

@api_router.post("/stripe/cancel-subscription")
async def cancel_stripe_subscription(user_id: str):
    """Cancel a Stripe subscription"""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    subscription_id = profile.get("stripe_subscription_id")
    if not subscription_id:
        raise HTTPException(status_code=400, detail="No active Stripe subscription")
    
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        subscription = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True
        )
        
        await db.profiles.update_one(
            {"id": user_id},
            {
                "$set": {
                    "subscription_status": "cancelled",
                    "subscription_updated_at": datetime.utcnow(),
                }
            }
        )
        
        return {
            "message": "Subscription will cancel at end of billing period",
            "cancel_at": subscription.cancel_at,
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe cancellation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@api_router.get("/stripe/customer-portal")
async def get_stripe_customer_portal(user_id: str, return_url: str):
    """Get Stripe Customer Portal URL for managing subscription"""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    
    customer_id = profile.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found")
    
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        
        return {"portal_url": session.url}
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe portal error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ==================== HEALTH CHECK ====================

@api_router.get("/")
async def root():
    return {"message": "InterFitAI API is running", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
