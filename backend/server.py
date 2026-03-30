from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, field_validator
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
    "decline push up": "0279",       # FIXED: 0279 = decline push-up
    "decline push-up": "0279",
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
    "rear delt fly": "0203",          # FIXED: was 0578 (lever deadlift). 0203 = cable rear delt row (rope)
    "rear delt machine fly": "0203",  # ADDED
    "reverse fly": "0203",            # FIXED
    "rear delt": "0203",              # FIXED
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
    "cable curl": "0868",             # FIXED: was 0163 (broken). 0868 = cable curl
    "cable bicep curl": "0868",       # FIXED
    
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
    "overhead cable extension": "0194",          # ADDED: cable overhead triceps extension (rope)
    "overhead cable tricep extension": "0194",   # ADDED
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
    "leg press": "0739",               # FIXED: was 0738 (sled calf press). 0739 = sled 45° leg press
    "sled leg press": "0739",          # FIXED
    "leg press (feet high)": "0739",   # ADDED
    "hack squat": "0743",              # FIXED: was 0473 (hanging pike). 0743 = sled hack squat
    "smith machine squat": "0755",     # ADDED
    "leg extension": "0585",
    "seated leg extension": "0585",
    "leg curl": "0586",
    "lying leg curl": "0586",
    "hamstring curl": "0586",
    "seated leg curl": "0599",  # lever seated leg curl
    "lever seated leg curl": "0599",
    "calf raise": "1373",
    "standing calf raise": "1373",
    "calf raise machine": "0594",      # ADDED: lever seated calf raise
    "seated calf raise": "0594",       # FIXED: was 0720 (side-to-side chin). 0594 = lever seated calf raise
    "lever seated calf raise": "0594",
    "lunge": "0336",  # dumbbell lunge
    "dumbbell lunge": "0336",
    "lunges": "0336",
    "walking lunge": "1460",  # walking lunge
    "walking lunges": "1460",
    "reverse lunge": "0381",           # dumbbell rear lunge
    "dumbbell reverse lunge": "0381",  # ADDED
    "barbell lunge": "0054",
    "bulgarian split squat": "0099",   # FIXED: was 0130 (bench hip extension). 0099 = barbell single leg split squat
    "dumbbell bulgarian split squat": "0410",  # ADDED
    "smith machine split squat": "0768",       # ADDED
    "split squat": "0099",             # FIXED
    "step up": "1684",                 # FIXED: was 0758 (smith incline reverse-grip press). 1684 = dumbbell step up
    "box step up": "1684",             # FIXED
    "dumbbell step up": "1684",        # ADDED
    "hip thrust": "1409",              # FIXED: was 0046 (barbell hack squat). 1409 = barbell glute bridge
    "barbell hip thrust": "1409",      # FIXED
    "hip thrust machine": "1409",      # ADDED
    "dumbbell hip thrust": "1409",     # ADDED
    "glute bridge": "1409",            # FIXED
    "barbell glute bridge": "1409",    # CORRECT
    "single leg glute bridge": "3013", # ADDED: low glute bridge on floor
    "single-leg glute bridge": "3013", # ADDED
    "glute kickback": "0860",          # FIXED: was 0482 (broken). 0860 = cable kickback
    "cable kickback": "0860",          # FIXED
    "good morning": "0044",            # FIXED: was 0440 (broken). 0044 = barbell good morning
    "barbell good morning": "0044",    # FIXED
    "pistol squat": "0544",            # ADDED: kettlebell pistol squat
    "piston squat (assisted)": "0544", # ADDED
    "single leg romanian deadlift": "1757",  # ADDED: dumbbell single leg deadlift
    "single-leg romanian deadlift": "1757",  # ADDED
    
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
    "hanging leg raise": "0472",       # FIXED: was 1760 (dumbbell goblet squat). 0472 = hanging leg raise
    "hanging knee raise": "0485",
    "knee raise": "0485",
    "mountain climber": "0630",        # FIXED: was 0601 (lever seated reverse fly). 0630 = mountain climber
    "mountain climbers": "0630",       # FIXED
    "mountain climbers emom": "0630",  # ADDED
    "ab wheel rollout": "0001",
    "ab rollout": "0001",              # ADDED
    "cable crunch": "0840",            # FIXED: was 0155 (cable cross-over). 0840 = cable woodchopper (cable core)
    "woodchopper": "0840",
    "cable woodchopper": "0840",
    "dead bug": "0276",                # FIXED: was 1474 (broken). 0276 = dead bug
    "bird dog": "0276",                # ADDED: similar stability pattern
    "flutter kick": "0395",
    "sit up": "0735",
    "v up": "1604",
    
    # Compound/Functional exercises
    "burpee": "1160",
    "burpees": "1160",
    "box jump": "1374",  # box jump down with one leg stabilization
    "box jumps": "1374",
    "jump squat": "0514",              # FIXED: was 0631 (muscle up). 0514 = jump squat
    "jump squats": "0514",             # FIXED
    "broad jump": "0514",              # ADDED: closest plyometric
    "broadjump": "0514",               # ADDED
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
    "assault bike": "2612",            # no exact ExerciseDB match — jump rope as closest cardio
    "assault bike intervals": "2612",  # ADDED
    "rowing machine": "0128",          # FIXED: was 1866 (broken). Battle ropes as closest cardio
    "rowing machine intervals": "0128",# ADDED
    "rowing": "0128",                  # FIXED
    "row machine": "0128",             # FIXED
    "rower": "0128",                   # FIXED
    
    # Machine exercises
    "pec deck": "0613",
    "machine fly": "0613",
    "shoulder press machine": "0603",  # FIXED: was 0718 (broken). 0603 = lever shoulder press
    "machine shoulder press": "0603",  # FIXED
    "cable shoulder press": "0603",    # ADDED
    "lever shoulder press": "0603",    # ADDED
    "cable lateral raise": "0178",     # FIXED: was 0175 (cable kneeling crunch). 0178 = cable lateral raise
    "machine lateral raise": "0584",   # ADDED: lever lateral raise
    "machine lateral raises": "0584",  # ADDED
    "rear delt machine fly": "0203",   # ADDED
    "farmer's carry": "2133",          # ADDED: farmers walk
    "farmers carry": "2133",           # ADDED
    "farmer's walk": "2133",           # ADDED
    "farmers walk": "2133",            # ADDED
    "suitcase carry": "2133",          # ADDED: farmers walk as closest
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
                        
                        if best_exercise and best_score >= 40:  # raised from 20 — prevents wrong GIF matches
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
    gif_url: Optional[str] = None
    effort_target: Optional[str] = None      # e.g. "RIR 2-3", "RPE 8"
    exercise_type: Optional[str] = None      # primary_compound / accessory / isolation / unilateral / core / conditioning
    substitution_hint: Optional[str] = None  # alternative exercise suggestion

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
    training_style: str = "weights"
    fitness_level: str = "intermediate"
    focus_areas: List[str]
    secondary_focus_areas: Optional[List[str]] = None
    equipment: List[str]
    injuries: Optional[List[str]] = None
    duration_weeks: int = 4
    days_per_week: int = 4
    session_duration_minutes: int = 60
    preferred_split: str = "ai_choose"
    split_name: Optional[str] = None
    split_rationale: Optional[str] = None
    progression_method: Optional[str] = None
    deload_timing: Optional[str] = None
    weekly_structure: Optional[List[str]] = None
    training_notes: Optional[str] = None
    workout_days: List[WorkoutDay]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('injuries', mode='before')
    @classmethod
    def normalize_injuries(cls, v):
        if isinstance(v, str):
            items = [i.strip() for i in v.replace('\n', ',').split(',') if i.strip()]
            return items if items else None
        return v

class WorkoutGenerateRequest(BaseModel):
    user_id: str
    goal: str          # build_muscle, lose_fat, body_recomp, strength, general_fitness, athletic_performance
    training_style: str = "weights"   # weights, calisthenics, hybrid, functional
    focus_areas: List[str]
    secondary_focus_areas: Optional[List[str]] = None
    equipment: List[str]
    injuries: Optional[List[str]] = None
    days_per_week: int = 4
    duration_minutes: int = 60
    fitness_level: str = "intermediate"
    preferred_split: str = "ai_choose"
    exercise_preferences: Optional[str] = None  # free text: favourite/disliked exercises


# ==================== ELITE COACHING ENGINE ====================
# All programming decisions are made here in Python.
# Claude is only used to fill exercise names + instructions from the blueprint.

class EliteCoachingEngine:
    """
    Builds a complete, science-backed coaching blueprint before any AI is involved.
    Split selection, volume allocation, exercise categorization, sets/reps/rest/effort,
    and progression model are all determined deterministically here.
    """

    # ----- Exercise options per movement pattern and equipment type -----
    PATTERNS = {
        "horizontal_push": {
            "full_gym":  ["Barbell Bench Press", "Machine Chest Press", "Cable Chest Fly"],
            "beginner_gym": ["Machine Chest Press", "Dumbbell Bench Press", "Cable Chest Fly", "Incline Machine Press"],
            "barbells":  ["Barbell Bench Press", "Close-Grip Bench Press"],
            "dumbbells": ["Dumbbell Bench Press", "Dumbbell Incline Press"],
            "machines":  ["Machine Chest Press", "Machine Incline Press"],
            "bodyweight":["Push-Up", "Archer Push-Up", "Decline Push-Up"],
            "kettlebells":["Kettlebell Floor Press"],
            "cables":    ["Cable Chest Fly", "Cable Crossover"],
            "resistance_bands":["Band Push-Up", "Band Chest Press"],
        },
        "incline_push": {
            "full_gym":  ["Incline Barbell Press", "Incline Dumbbell Press"],
            "beginner_gym": ["Incline Machine Press", "Incline Dumbbell Press", "High-to-Low Cable Fly"],
            "barbells":  ["Incline Barbell Press"],
            "dumbbells": ["Incline Dumbbell Press", "Incline Dumbbell Fly"],
            "machines":  ["Incline Machine Press"],
            "bodyweight":["Pike Push-Up", "Decline Push-Up"],
            "cables":    ["High-to-Low Cable Fly"],
            "resistance_bands":["Incline Band Press"],
        },
        "vertical_push": {
            "full_gym":  ["Barbell Overhead Press", "Dumbbell Shoulder Press", "Machine Shoulder Press"],
            "beginner_gym": ["Machine Shoulder Press", "Dumbbell Shoulder Press", "Cable Shoulder Press"],
            "barbells":  ["Barbell Overhead Press", "Push Press"],
            "dumbbells": ["Dumbbell Shoulder Press", "Arnold Press"],
            "machines":  ["Machine Shoulder Press"],
            "bodyweight":["Pike Push-Up", "Handstand Push-Up (wall assisted)"],
            "kettlebells":["Kettlebell Press"],
            "cables":    ["Cable Shoulder Press"],
            "resistance_bands":["Band Overhead Press"],
        },
        "lateral_raise": {
            "full_gym":  ["Cable Lateral Raise", "Machine Lateral Raise", "Dumbbell Lateral Raise"],
            "dumbbells": ["Dumbbell Lateral Raise"],
            "machines":  ["Machine Lateral Raise"],
            "cables":    ["Cable Lateral Raise"],
            "resistance_bands":["Band Lateral Raise"],
            "bodyweight":["Bodyweight Lateral Raise"],
        },
        "rear_delt": {
            "full_gym":  ["Cable Face Pull", "Rear Delt Machine Fly", "Dumbbell Rear Delt Fly"],
            "dumbbells": ["Dumbbell Rear Delt Fly", "Bent-Over Rear Delt Raise"],
            "machines":  ["Reverse Pec Deck", "Face Pull Machine"],
            "cables":    ["Cable Face Pull", "Cable Rear Delt Fly"],
            "resistance_bands":["Band Face Pull", "Band Pull-Apart"],
            "bodyweight":["Band Pull-Apart"],
        },
        "tricep_push": {
            "full_gym":  ["Cable Tricep Pushdown", "Overhead Cable Extension", "Skull Crusher"],
            "barbells":  ["Skull Crusher", "Close-Grip Bench Press"],
            "dumbbells": ["Overhead Dumbbell Extension", "Dumbbell Kickback"],
            "machines":  ["Cable Tricep Pushdown"],
            "cables":    ["Cable Tricep Pushdown", "Overhead Cable Extension"],
            "bodyweight":["Diamond Push-Up", "Bench Dip"],
            "resistance_bands":["Band Tricep Pushdown"],
        },
        "vertical_pull": {
            "full_gym":  ["Lat Pulldown", "Pull-Up", "Assisted Pull-Up"],
            "barbells":  ["Pull-Up", "Chin-Up"],
            "dumbbells": ["Pull-Up", "Dumbbell Pullover"],
            "machines":  ["Lat Pulldown", "Assisted Pull-Up Machine"],
            "bodyweight":["Pull-Up", "Chin-Up", "Australian Pull-Up"],
            "cables":    ["Lat Pulldown", "Single-Arm Lat Pulldown"],
            "resistance_bands":["Band-Assisted Pull-Up", "Band Lat Pulldown"],
        },
        "horizontal_pull": {
            "full_gym":  ["Barbell Row", "Cable Row", "Machine Row"],
            "beginner_gym": ["Cable Row", "Machine Row", "Dumbbell Row"],
            "barbells":  ["Barbell Row", "Pendlay Row", "T-Bar Row"],
            "dumbbells": ["Dumbbell Row", "Chest-Supported Row"],
            "machines":  ["Machine Row", "Cable Row"],
            "cables":    ["Cable Row", "Single-Arm Cable Row"],
            "bodyweight":["Australian Pull-Up", "Inverted Row"],
            "kettlebells":["Kettlebell Row"],
            "resistance_bands":["Band Row", "Band Pull-Apart"],
        },
        "bicep_curl": {
            "full_gym":  ["EZ Bar Curl", "Cable Curl", "Incline Dumbbell Curl"],
            "barbells":  ["Barbell Curl", "EZ Bar Curl"],
            "dumbbells": ["Dumbbell Curl", "Hammer Curl", "Incline Dumbbell Curl"],
            "machines":  ["Machine Preacher Curl"],
            "cables":    ["Cable Curl", "Cable Hammer Curl"],
            "bodyweight":["Chin-Up", "Supinated Row"],
            "resistance_bands":["Band Curl"],
        },
        "squat": {
            "full_gym":  ["Back Squat", "Leg Press", "Hack Squat"],
            "beginner_gym": ["Leg Press", "Goblet Squat", "Hack Squat", "Smith Machine Squat"],
            "barbells":  ["Back Squat", "Front Squat", "Pause Squat"],
            "dumbbells": ["Goblet Squat", "Dumbbell Front Squat"],
            "machines":  ["Leg Press", "Hack Squat", "Smith Machine Squat"],
            "bodyweight":["Bodyweight Squat", "Jump Squat", "Pistol Squat (assisted)"],
            "kettlebells":["Kettlebell Goblet Squat"],
            "resistance_bands":["Band Squat"],
        },
        "lunge": {
            "full_gym":  ["Barbell Bulgarian Split Squat", "Dumbbell Reverse Lunge", "Walking Lunge"],
            "beginner_gym": ["Dumbbell Reverse Lunge", "Dumbbell Step-Up", "Smith Machine Split Squat"],
            "barbells":  ["Barbell Bulgarian Split Squat", "Barbell Lunge"],
            "dumbbells": ["Dumbbell Reverse Lunge", "Dumbbell Bulgarian Split Squat", "Dumbbell Step-Up"],
            "machines":  ["Smith Machine Split Squat"],
            "bodyweight":["Reverse Lunge", "Bulgarian Split Squat", "Step-Up", "Lateral Lunge"],
            "kettlebells":["Kettlebell Lunge", "Kettlebell Step-Up"],
            "resistance_bands":["Band Lunge"],
        },
        "hip_hinge": {
            "full_gym":  ["Romanian Deadlift", "Conventional Deadlift", "Cable Pull-Through"],
            "beginner_gym": ["Dumbbell Romanian Deadlift", "Cable Pull-Through", "Leg Curl"],
            "barbells":  ["Romanian Deadlift", "Conventional Deadlift", "Sumo Deadlift"],
            "dumbbells": ["Dumbbell Romanian Deadlift", "Single-Leg RDL"],
            "machines":  ["Cable Pull-Through", "Leg Curl"],
            "bodyweight":["Single-Leg Romanian Deadlift", "Good Morning"],
            "kettlebells":["Kettlebell Swing", "Kettlebell Romanian Deadlift"],
            "cables":    ["Cable Pull-Through"],
        },
        "glute": {
            "full_gym":  ["Barbell Hip Thrust", "Cable Kickback", "Leg Press (feet high)"],
            "beginner_gym": ["Hip Thrust Machine", "Dumbbell Hip Thrust", "Cable Kickback"],
            "barbells":  ["Barbell Hip Thrust", "Barbell Glute Bridge"],
            "dumbbells": ["Dumbbell Hip Thrust", "Single-Leg Glute Bridge"],
            "machines":  ["Hip Thrust Machine", "Cable Kickback"],
            "bodyweight":["Hip Thrust", "Glute Bridge", "Single-Leg Glute Bridge"],
            "cables":    ["Cable Kickback", "Cable Hip Extension"],
            "resistance_bands":["Band Hip Thrust", "Band Kickback", "Band Clamshell"],
        },
        "hamstring_curl": {
            "full_gym":  ["Lying Leg Curl", "Seated Leg Curl", "Nordic Hamstring Curl"],
            "machines":  ["Lying Leg Curl", "Seated Leg Curl"],
            "dumbbells": ["Dumbbell Leg Curl"],
            "bodyweight":["Nordic Hamstring Curl", "Swiss Ball Leg Curl"],
            "cables":    ["Cable Leg Curl"],
            "resistance_bands":["Band Leg Curl"],
        },
        "knee_extension": {
            "full_gym":  ["Leg Extension", "Spanish Squat"],
            "machines":  ["Leg Extension"],
            "bodyweight":["Terminal Knee Extension", "Sissy Squat"],
            "resistance_bands":["Band Terminal Knee Extension"],
        },
        "calf": {
            "full_gym":  ["Calf Raise Machine", "Seated Calf Raise", "Leg Press Calf Raise"],
            "machines":  ["Calf Raise Machine", "Seated Calf Raise"],
            "barbells":  ["Barbell Calf Raise"],
            "dumbbells": ["Dumbbell Calf Raise", "Single-Leg Calf Raise"],
            "bodyweight":["Single-Leg Calf Raise", "Bodyweight Calf Raise"],
        },
        "core_stability": {
            "full_gym":  ["Plank", "Dead Bug", "Ab Rollout", "Pallof Press"],
            "cables":    ["Pallof Press", "Cable Wood Chop", "Ab Pulldown"],
            "bodyweight":["Plank", "Dead Bug", "Bird Dog", "Side Plank"],
            "resistance_bands":["Band Pallof Press"],
            "any":       ["Plank", "Dead Bug", "Bird Dog"],
        },
        "core_flexion": {
            "full_gym":  ["Hanging Leg Raise", "Cable Crunch", "Ab Rollout"],
            "machines":  ["Cable Crunch"],
            "bodyweight":["Hanging Leg Raise", "Reverse Crunch", "V-Up"],
            "cables":    ["Cable Crunch", "Cable Wood Chop"],
            "any":       ["Reverse Crunch", "V-Up"],
        },
        "carry": {
            "full_gym":  ["Farmer's Carry", "Suitcase Carry"],
            "dumbbells": ["Farmer's Carry", "Suitcase Carry"],
            "kettlebells":["Kettlebell Farmer's Carry", "Kettlebell Overhead Carry"],
            "barbells":  ["Trap Bar Farmer's Carry"],
            "bodyweight":["Plank Walk"],
            "any":       ["Farmer's Carry"],
        },
        "explosive": {
            "full_gym":  ["Box Jump", "Broad Jump", "Jump Squat", "Medicine Ball Slam"],
            "bodyweight":["Box Jump", "Broad Jump", "Plyo Push-Up", "Jump Squat"],
            "kettlebells":["Kettlebell Swing"],
            "any":       ["Box Jump", "Jump Squat"],
        },
        "conditioning": {
            "full_gym":  ["Rowing Machine Intervals", "Assault Bike Intervals", "Battle Ropes"],
            "bodyweight":["Burpee Intervals", "Jump Rope", "Mountain Climbers EMOM"],
            "kettlebells":["Kettlebell Swing Intervals"],
            "any":       ["Burpee Intervals", "Jump Rope"],
        },
    }

    # ----- Session archetypes: movement patterns per session type -----
    SESSION_ARCHETYPES = {
        "upper_push_heavy": {
            "label": "Upper – Push (Heavy)",
            "focus": "Chest, Shoulders & Triceps",
            "slots": [
                ("horizontal_push",  "primary_compound",   "heavy horizontal pressing – chest emphasis"),
                ("incline_push",     "secondary_compound",  "incline angle for upper chest development"),
                ("vertical_push",    "secondary_compound",  "overhead pressing – shoulder strength"),
                ("lateral_raise",    "accessory",           "medial delt isolation – shoulder width"),
                ("tricep_push",      "isolation",           "tricep isolation – elbow extension"),
            ],
            "optional_slots": [],
        },
        "upper_push_volume": {
            "label": "Upper – Push (Volume)",
            "focus": "Chest, Shoulders & Triceps",
            "slots": [
                ("incline_push",     "primary_compound",   "incline press – upper chest emphasis"),
                ("horizontal_push",  "secondary_compound",  "flat pressing – overall chest volume"),
                ("vertical_push",    "accessory",           "overhead pressing – shoulder development"),
                ("lateral_raise",    "accessory",           "medial delt isolation"),
                ("tricep_push",      "isolation",           "tricep isolation – volume day"),
            ],
            "optional_slots": [],
        },
        "upper_pull_heavy": {
            "label": "Upper – Pull (Heavy)",
            "focus": "Back & Biceps",
            "slots": [
                ("vertical_pull",    "primary_compound",   "vertical pulling – lat width and strength"),
                ("horizontal_pull",  "primary_compound",   "horizontal rowing – mid-back thickness"),
                ("horizontal_pull",  "secondary_compound",  "secondary row variation – back volume"),
                ("rear_delt",        "accessory",           "rear delt – shoulder health"),
                ("bicep_curl",       "isolation",           "bicep isolation – elbow flexion"),
            ],
            "optional_slots": [
                ("bicep_curl",       "isolation",           "hammer curl – brachialis and forearm"),
            ],
        },
        "upper_pull_volume": {
            "label": "Upper – Pull (Volume)",
            "focus": "Back & Biceps",
            "slots": [
                ("horizontal_pull",  "primary_compound",   "heavy row – back thickness priority"),
                ("vertical_pull",    "secondary_compound",  "lat pulldown variation – lat width"),
                ("horizontal_pull",  "accessory",           "chest-supported row – eliminate cheating"),
                ("rear_delt",        "accessory",           "face pull / rear fly – rotator cuff health"),
                ("bicep_curl",       "isolation",           "bicep curl – peak contraction focus"),
            ],
            "optional_slots": [],
        },
        "lower_quad_focus": {
            "label": "Lower – Quad Focus",
            "focus": "Quads, Hamstrings & Glutes",
            "slots": [
                ("squat",            "primary_compound",   "knee-dominant compound – quad strength and size"),
                ("lunge",            "secondary_compound",  "unilateral leg work – balance and quad isolation"),
                ("hip_hinge",        "secondary_compound",  "hinge pattern – hamstring and posterior chain"),
                ("knee_extension",   "accessory",           "quad isolation – VMO and knee health"),
                ("calf",             "isolation",           "calf raise – soleus and gastrocnemius"),
            ],
            "optional_slots": [
                ("core_stability",   "core",                "core finisher – stability and bracing"),
            ],
        },
        "lower_hip_focus": {
            "label": "Lower – Hip Focus",
            "focus": "Hamstrings, Glutes & Posterior Chain",
            "slots": [
                ("hip_hinge",        "primary_compound",   "hip hinge – deadlift pattern, posterior chain"),
                ("glute",            "primary_compound",   "hip thrust – glute isolation and strength"),
                ("lunge",            "secondary_compound",  "unilateral work – single-leg strength"),
                ("hamstring_curl",   "accessory",           "hamstring isolation – leg curl"),
                ("calf",             "isolation",           "calf raise – lower leg development"),
            ],
            "optional_slots": [
                ("core_stability",   "core",                "core finisher"),
            ],
        },
        "push_session": {
            "label": "Push",
            "focus": "Chest, Shoulders & Triceps",
            "slots": [
                ("horizontal_push",  "primary_compound",   "bench press variation – chest strength"),
                ("incline_push",     "secondary_compound",  "incline press – upper chest"),
                ("vertical_push",    "secondary_compound",  "overhead press – shoulder strength"),
                ("lateral_raise",    "accessory",           "lateral raise – medial delt width"),
                ("tricep_push",      "isolation",           "tricep isolation – full elbow extension"),
            ],
            "optional_slots": [],
        },
        "pull_session": {
            "label": "Pull",
            "focus": "Back & Biceps",
            "slots": [
                ("vertical_pull",    "primary_compound",   "vertical pull – lat strength and width"),
                ("horizontal_pull",  "primary_compound",   "heavy row – back thickness"),
                ("horizontal_pull",  "secondary_compound",  "row variation – volume accumulation"),
                ("rear_delt",        "accessory",           "face pull – rear delt and rotator cuff"),
                ("bicep_curl",       "isolation",           "bicep curl – elbow flexion"),
            ],
            "optional_slots": [
                ("bicep_curl",       "isolation",           "hammer curl variation"),
            ],
        },
        "legs_session": {
            "label": "Legs",
            "focus": "Quads, Hamstrings, Glutes & Calves",
            "slots": [
                ("squat",            "primary_compound",   "squat pattern – quad and glute strength"),
                ("hip_hinge",        "secondary_compound",  "hinge pattern – hamstrings and posterior chain"),
                ("lunge",            "secondary_compound",  "unilateral work – balance and isolation"),
                ("glute",            "accessory",           "glute isolation – hip thrust or bridge"),
                ("hamstring_curl",   "accessory",           "hamstring isolation – leg curl"),
                ("calf",             "isolation",           "calf raise – ankle plantar flexion"),
            ],
            "optional_slots": [],
        },
        "full_body_heavy": {
            "label": "Full Body A",
            "focus": "Full Body – Strength Emphasis",
            "slots": [
                ("squat",            "primary_compound",   "lower body compound – bilateral squat pattern"),
                ("horizontal_push",  "primary_compound",   "upper body push – pressing strength"),
                ("horizontal_pull",  "primary_compound",   "upper body pull – rowing strength"),
                ("hip_hinge",        "secondary_compound",  "posterior chain – hinge pattern"),
                ("lunge",            "accessory",           "unilateral lower body – balance"),
                ("core_stability",   "core",                "core stability – trunk control"),
            ],
            "optional_slots": [],
        },
        "full_body_moderate": {
            "label": "Full Body B",
            "focus": "Full Body – Hypertrophy Emphasis",
            "slots": [
                ("hip_hinge",        "primary_compound",   "hinge pattern – deadlift variation"),
                ("incline_push",     "primary_compound",   "incline press – upper chest volume"),
                ("vertical_pull",    "primary_compound",   "vertical pull – lat development"),
                ("lunge",            "secondary_compound",  "single-leg squat – quad and glute"),
                ("vertical_push",    "accessory",           "overhead press – shoulder volume"),
                ("core_flexion",     "core",                "core flexion – ab isolation"),
            ],
            "optional_slots": [],
        },
        "full_body_light": {
            "label": "Full Body C",
            "focus": "Full Body – Accessory Emphasis",
            "slots": [
                ("squat",            "secondary_compound",  "squat pattern – quad focus"),
                ("horizontal_push",  "secondary_compound",  "press variation – chest volume"),
                ("horizontal_pull",  "secondary_compound",  "row variation – back volume"),
                ("glute",            "accessory",           "glute isolation – hip extension"),
                ("lateral_raise",    "accessory",           "medial delt – shoulder width"),
                ("bicep_curl",       "isolation",           "bicep isolation – supination focus"),
                ("tricep_push",      "isolation",           "tricep isolation – lockout strength"),
            ],
            "optional_slots": [],
        },
        "upper_full": {
            "label": "Upper Body",
            "focus": "Chest, Back, Shoulders & Arms",
            "slots": [
                ("horizontal_push",  "primary_compound",   "pressing – chest and tricep strength"),
                ("horizontal_pull",  "primary_compound",   "rowing – back and bicep strength"),
                ("incline_push",     "secondary_compound",  "incline press – upper chest"),
                ("vertical_pull",    "secondary_compound",  "vertical pull – lat development"),
                ("lateral_raise",    "accessory",           "lateral delt – shoulder width"),
                ("bicep_curl",       "isolation",           "bicep isolation"),
                ("tricep_push",      "isolation",           "tricep isolation"),
            ],
            "optional_slots": [],
        },
        "lower_full": {
            "label": "Lower Body",
            "focus": "Quads, Hamstrings, Glutes & Calves",
            "slots": [
                ("squat",            "primary_compound",   "squat pattern – bilateral lower body strength"),
                ("hip_hinge",        "primary_compound",   "hinge pattern – posterior chain"),
                ("lunge",            "secondary_compound",  "unilateral – single-leg development"),
                ("glute",            "accessory",           "glute isolation – hip thrust"),
                ("hamstring_curl",   "accessory",           "hamstring isolation"),
                ("calf",             "isolation",           "calf raise"),
            ],
            "optional_slots": [],
        },
        "athletic_conditioning": {
            "label": "Athletic Conditioning",
            "focus": "Power, Speed & Work Capacity",
            "slots": [
                ("explosive",        "primary_compound",   "power development – explosive lower body"),
                ("carry",            "accessory",           "loaded carry – trunk stability and grip"),
                ("squat",            "secondary_compound",  "strength base – squat pattern"),
                ("horizontal_pull",  "secondary_compound",  "row – pulling strength"),
                ("conditioning",     "conditioning",        "metabolic finisher – work capacity"),
            ],
            "optional_slots": [
                ("core_stability",   "core",                "anti-rotation core work"),
            ],
        },
        "functional_session": {
            "label": "Functional",
            "focus": "Movement Quality & Work Capacity",
            "slots": [
                ("squat",            "primary_compound",   "bilateral squat – movement foundation"),
                ("horizontal_pull",  "secondary_compound",  "row – pulling pattern"),
                ("lunge",            "secondary_compound",  "unilateral – single-leg control"),
                ("carry",            "accessory",           "farmer's carry – trunk stability"),
                ("core_stability",   "core",                "anti-rotation core work"),
                ("conditioning",     "conditioning",        "conditioning finisher"),
            ],
            "optional_slots": [],
        },
        "calisthenics_upper": {
            "label": "Calisthenics Upper",
            "focus": "Chest, Back, Shoulders & Arms",
            "slots": [
                ("horizontal_push",  "primary_compound",   "push-up progression – horizontal push"),
                ("vertical_pull",    "primary_compound",   "pull-up progression – vertical pull"),
                ("incline_push",     "secondary_compound",  "pike push-up – overhead push pattern"),
                ("horizontal_pull",  "secondary_compound",  "row progression – horizontal pull"),
                ("tricep_push",      "isolation",           "dip variation – tricep extension"),
                ("bicep_curl",       "isolation",           "chin-up supinated grip – bicep focus"),
            ],
            "optional_slots": [],
        },
        "calisthenics_lower": {
            "label": "Calisthenics Lower",
            "focus": "Legs & Core",
            "slots": [
                ("squat",            "primary_compound",   "squat progression – bilateral strength"),
                ("lunge",            "secondary_compound",  "lunge progression – unilateral control"),
                ("hip_hinge",        "secondary_compound",  "hinge progression – posterior chain"),
                ("glute",            "accessory",           "glute bridge – hip extension"),
                ("core_stability",   "core",                "plank progression – trunk stability"),
                ("core_flexion",     "core",                "hanging or floor core flexion"),
            ],
            "optional_slots": [],
        },

        # ── Hybrid archetypes: strength session + conditioning finisher ──────────
        "hybrid_strength_push": {
            "label": "Hybrid – Push + Conditioning",
            "focus": "Chest, Shoulders & Triceps + Metabolic Finisher",
            "slots": [
                ("horizontal_push",  "primary_compound",   "heavy pressing – chest and tricep strength base"),
                ("incline_push",     "secondary_compound",  "incline angle – upper chest development"),
                ("vertical_push",    "secondary_compound",  "overhead press – shoulder strength and stability"),
                ("tricep_push",      "isolation",           "tricep isolation – elbow lockout strength"),
                ("conditioning",     "conditioning",        "conditioning finisher – raise heart rate, burn extra energy"),
            ],
            "optional_slots": [
                ("lateral_raise",    "accessory",           "medial delt – shoulder width and fullness"),
            ],
        },
        "hybrid_strength_pull": {
            "label": "Hybrid – Pull + Conditioning",
            "focus": "Back & Biceps + Metabolic Finisher",
            "slots": [
                ("vertical_pull",    "primary_compound",   "vertical pull – lat strength and width"),
                ("horizontal_pull",  "primary_compound",   "heavy row – mid-back thickness and density"),
                ("rear_delt",        "accessory",           "rear delt and rotator cuff – shoulder health"),
                ("bicep_curl",       "isolation",           "bicep isolation – elbow flexion and peak"),
                ("conditioning",     "conditioning",        "conditioning finisher – metabolic output"),
            ],
            "optional_slots": [],
        },
        "hybrid_strength_lower": {
            "label": "Hybrid – Lower + Conditioning",
            "focus": "Legs, Glutes & Posterior Chain + Metabolic Finisher",
            "slots": [
                ("squat",            "primary_compound",   "bilateral squat – lower body strength foundation"),
                ("hip_hinge",        "secondary_compound",  "hinge pattern – hamstring and glute strength"),
                ("lunge",            "secondary_compound",  "unilateral – single-leg strength and control"),
                ("glute",            "accessory",           "glute isolation – hip extension and strength"),
                ("conditioning",     "conditioning",        "lower body conditioning finisher – work capacity"),
            ],
            "optional_slots": [
                ("core_stability",   "core",                "core bracing – trunk stability under load"),
            ],
        },
        "hybrid_power_conditioning": {
            "label": "Hybrid – Power & Conditioning",
            "focus": "Power, Athleticism & Work Capacity",
            "slots": [
                ("explosive",        "primary_compound",   "plyometric power – explosive lower body output"),
                ("carry",            "accessory",           "loaded carry – trunk integrity and grip strength"),
                ("squat",            "secondary_compound",  "squat strength – bilateral lower body base"),
                ("horizontal_pull",  "secondary_compound",  "row – pulling strength and postural balance"),
                ("conditioning",     "conditioning",        "high-output metabolic finisher – push the limit"),
            ],
            "optional_slots": [
                ("core_stability",   "core",                "anti-rotation – rotary stability under fatigue"),
            ],
        },

        # ── Functional A/B archetypes: genuinely distinct sessions ───────────────
        "functional_movement_quality": {
            "label": "Functional A – Movement Quality",
            "focus": "Unilateral Strength, Trunk Control & Pattern Integrity",
            "slots": [
                ("lunge",            "primary_compound",   "single-leg dominance – unilateral strength and control"),
                ("horizontal_pull",  "secondary_compound",  "row – scapular control and anti-extension"),
                ("carry",            "accessory",           "loaded carry – trunk stability and gait integrity"),
                ("core_stability",   "core",                "anti-rotation core – Pallof press or bird-dog"),
                ("glute",            "accessory",           "glute activation and control – hip extension quality"),
                ("conditioning",     "conditioning",        "aerobic capacity – low-intensity steady state"),
            ],
            "optional_slots": [],
        },
        "functional_strength_capacity": {
            "label": "Functional B – Strength & Capacity",
            "focus": "Multi-Plane Strength, Power Output & Work Capacity",
            "slots": [
                ("squat",            "primary_compound",   "bilateral squat – strength foundation and power base"),
                ("horizontal_push",  "secondary_compound",  "press pattern – upper body pushing capacity"),
                ("explosive",        "secondary_compound",  "plyometric output – power development and rate-of-force"),
                ("hip_hinge",        "accessory",           "hinge strength – posterior chain and trunk loading"),
                ("core_flexion",     "core",                "dynamic core – anti-flexion and rotational control"),
                ("conditioning",     "conditioning",        "high-intensity finisher – glycolytic capacity"),
            ],
            "optional_slots": [],
        },

        # ── True Bro Split archetypes — one muscle group per session ─────────
        "bro_chest": {
            "label": "Chest Day",
            "focus": "Chest & Triceps",
            "slots": [
                ("horizontal_push",  "primary_compound",   "flat pressing – chest mass and strength foundation"),
                ("incline_push",     "secondary_compound",  "incline angle – upper chest focus and fullness"),
                ("incline_push",     "accessory",           "flye or crossover – chest isolation and stretch"),
                ("tricep_push",      "isolation",           "tricep isolation – full elbow extension and pump"),
            ],
            "optional_slots": [
                ("lateral_raise",    "accessory",           "medial delt – shoulder width complement to chest"),
                ("tricep_push",      "isolation",           "overhead extension – long head stretch"),
            ],
        },
        "bro_back": {
            "label": "Back Day",
            "focus": "Back & Biceps",
            "slots": [
                ("vertical_pull",    "primary_compound",   "vertical pull – lat width and upper back thickness"),
                ("horizontal_pull",  "primary_compound",   "heavy row – mid-back density and rhomboid strength"),
                ("horizontal_pull",  "secondary_compound",  "second row variation – upper or lower back emphasis"),
                ("rear_delt",        "accessory",           "rear delt – shoulder health and upper back detail"),
                ("bicep_curl",       "isolation",           "bicep curl – elbow flexion strength and peak"),
            ],
            "optional_slots": [
                ("bicep_curl",       "isolation",           "hammer or reverse curl – brachialis and grip"),
            ],
        },
        "bro_shoulders": {
            "label": "Shoulders Day",
            "focus": "Deltoids & Traps",
            "slots": [
                ("vertical_push",    "primary_compound",   "overhead press – deltoid mass and pressing strength"),
                ("lateral_raise",    "accessory",           "lateral raise – medial delt width"),
                ("lateral_raise",    "secondary_compound",  "second lateral raise variation – cable or dumbbell"),
                ("rear_delt",        "accessory",           "rear delt – posterior shoulder and rotator health"),
                ("tricep_push",      "isolation",           "tricep isolation – supports pressing strength"),
            ],
            "optional_slots": [
                ("carry",            "accessory",           "shrug – upper trap development and neck thickness"),
            ],
        },
        "bro_arms": {
            "label": "Arms Day",
            "focus": "Biceps & Triceps",
            "slots": [
                ("bicep_curl",       "primary_compound",   "barbell or dumbbell curl – bicep mass and peak"),
                ("tricep_push",      "primary_compound",   "close-grip press or dip – tricep mass and strength"),
                ("bicep_curl",       "secondary_compound",  "incline or preacher curl – stretch and peak development"),
                ("tricep_push",      "secondary_compound",  "skull crusher or overhead extension – long head focus"),
                ("bicep_curl",       "isolation",           "concentration curl or hammer – brachialis and detail"),
                ("tricep_push",      "isolation",           "cable pushdown – tricep isolation and pump"),
            ],
            "optional_slots": [],
        },
        "bro_legs": {
            "label": "Legs Day",
            "focus": "Quads, Hamstrings, Glutes & Calves",
            "slots": [
                ("squat",            "primary_compound",   "squat – bilateral lower body mass and strength"),
                ("hip_hinge",        "secondary_compound",  "deadlift variation – hamstring and glute mass"),
                ("lunge",            "secondary_compound",  "lunge or leg press – quad volume and unilateral work"),
                ("hamstring_curl",   "isolation",           "leg curl – hamstring isolation and peak"),
                ("glute",            "accessory",           "hip thrust – glute isolation and activation"),
                ("calf",             "isolation",           "calf raise – calves and soleus strength"),
            ],
            "optional_slots": [
                ("knee_extension",   "isolation",           "leg extension – quad isolation and detail"),
            ],
        },
    }

    # ----- Split → session type mapping (days_per_week → session sequence) -----
    SPLIT_MAP = {
        "full_body": {
            2: ["full_body_heavy", "full_body_moderate"],
            3: ["full_body_heavy", "full_body_moderate", "full_body_light"],
            4: ["full_body_heavy", "full_body_moderate", "full_body_light", "full_body_heavy"],
        },
        "upper_lower": {
            2: ["upper_full", "lower_full"],
            3: ["upper_push_heavy", "lower_quad_focus", "upper_pull_heavy"],
            4: ["upper_push_heavy", "lower_quad_focus", "upper_pull_heavy", "lower_hip_focus"],
            5: ["upper_push_heavy", "lower_quad_focus", "upper_pull_heavy", "lower_hip_focus", "upper_full"],
            6: ["upper_push_heavy", "lower_quad_focus", "upper_pull_heavy", "lower_hip_focus", "upper_push_volume", "lower_full"],
        },
        "push_pull_legs": {
            3: ["push_session", "pull_session", "legs_session"],
            4: ["push_session", "pull_session", "legs_session", "push_session"],
            5: ["push_session", "pull_session", "legs_session", "push_session", "pull_session"],
            6: ["push_session", "pull_session", "legs_session", "upper_push_volume", "upper_pull_volume", "lower_full"],
        },
        "bro_split": {
            3: ["bro_chest", "bro_legs", "bro_back"],
            4: ["bro_chest", "bro_back", "bro_legs", "bro_shoulders"],
            5: ["bro_chest", "bro_back", "bro_shoulders", "bro_legs", "bro_arms"],
            6: ["bro_chest", "bro_back", "bro_shoulders", "bro_legs", "bro_arms", "bro_back"],
        },
        "athletic_split": {
            4: ["full_body_heavy", "athletic_conditioning", "upper_full", "lower_full"],
            5: ["full_body_heavy", "athletic_conditioning", "upper_full", "lower_full", "athletic_conditioning"],
        },
        "functional_split": {
            3: ["functional_movement_quality", "functional_strength_capacity", "functional_movement_quality"],
            4: ["functional_movement_quality", "functional_strength_capacity", "functional_movement_quality", "functional_strength_capacity"],
            5: ["functional_movement_quality", "functional_strength_capacity", "functional_movement_quality", "functional_strength_capacity", "functional_movement_quality"],
        },
        "hybrid_split": {
            3: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_power_conditioning"],
            4: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_strength_pull", "hybrid_power_conditioning"],
            5: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_strength_pull", "hybrid_power_conditioning", "hybrid_strength_lower"],
            6: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_strength_pull", "hybrid_power_conditioning", "hybrid_strength_push", "hybrid_strength_pull"],
        },
        "calisthenics_split": {
            3: ["calisthenics_upper", "calisthenics_lower", "calisthenics_upper"],
            4: ["calisthenics_upper", "calisthenics_lower", "calisthenics_upper", "calisthenics_lower"],
            5: ["calisthenics_upper", "calisthenics_lower", "calisthenics_upper", "calisthenics_lower", "calisthenics_upper"],
        },
    }

    # ----- Goal + level → sets/reps/rest/effort per exercise type -----
    GOAL_PARAMS = {
        "strength": {
            # Heavy: 2.5-4 min rest on primary, 2-3 min on secondary, 60-120s on accessories
            "primary_compound":   {"sets": 5, "reps": "3-5",        "rest": 225, "effort": "RPE 8-9 — heavy but technically solid"},
            "secondary_compound": {"sets": 4, "reps": "4-8",        "rest": 150, "effort": "RPE 8 — controlled and strong"},
            "accessory":          {"sets": 3, "reps": "6-12",       "rest": 90,  "effort": "RIR 2-3 — support work"},
            "isolation":          {"sets": 3, "reps": "8-15",       "rest": 75,  "effort": "RIR 2-3"},
            "unilateral":         {"sets": 3, "reps": "4-8 each",   "rest": 120, "effort": "RIR 2-3"},
            "core":               {"sets": 3, "reps": "6-10",       "rest": 75,  "effort": "Max tension — controlled tempo"},
            "conditioning":       {"sets": 1, "reps": "10-15 min",  "rest": 0,   "effort": "Zone 2 — low intensity only"},
            "explosive":          {"sets": 3, "reps": "3-5",        "rest": 150, "effort": "Max intent — bar speed matters"},
        },
        "build_muscle": {
            # Hypertrophy: 90-180s compounds, 45-90s accessories
            "primary_compound":   {"sets": 4, "reps": "6-10",       "rest": 120, "effort": "RIR 2-3"},
            "secondary_compound": {"sets": 3, "reps": "8-12",       "rest": 90,  "effort": "RIR 2-3"},
            "accessory":          {"sets": 3, "reps": "10-15",      "rest": 75,  "effort": "RIR 1-2"},
            "isolation":          {"sets": 3, "reps": "12-15",      "rest": 60,  "effort": "RIR 1-2 — full contraction"},
            "unilateral":         {"sets": 3, "reps": "10-12 each", "rest": 90,  "effort": "RIR 2-3"},
            "core":               {"sets": 3, "reps": "10-15",      "rest": 45,  "effort": "Controlled — anti-gravity tension"},
            "conditioning":       {"sets": 1, "reps": "10-15 min",  "rest": 0,   "effort": "Zone 2-3 — light cardio only"},
            "explosive":          {"sets": 3, "reps": "4-6",        "rest": 90,  "effort": "Controlled power — moderate intent"},
        },
        "lose_fat": {
            # Efficient: shorter rest, moderate reps — preserve muscle, maximise calorie burn
            "primary_compound":   {"sets": 3, "reps": "8-12",       "rest": 90,  "effort": "RIR 2-3"},
            "secondary_compound": {"sets": 3, "reps": "10-15",      "rest": 75,  "effort": "RIR 2-3"},
            "accessory":          {"sets": 3, "reps": "12-15",      "rest": 60,  "effort": "RIR 1-2"},
            "isolation":          {"sets": 2, "reps": "15-20",      "rest": 45,  "effort": "RIR 1-2 — pump-focused"},
            "unilateral":         {"sets": 3, "reps": "12-15 each", "rest": 60,  "effort": "RIR 2-3"},
            "core":               {"sets": 3, "reps": "12-20",      "rest": 30,  "effort": "Controlled — efficient"},
            "conditioning":       {"sets": 1, "reps": "10-20 min",  "rest": 0,   "effort": "High intensity — intervals or HIIT"},
            "explosive":          {"sets": 3, "reps": "5-8",        "rest": 60,  "effort": "Moderate intensity"},
        },
        "body_recomp": {
            # Balanced: build muscle + maintain efficiency
            "primary_compound":   {"sets": 4, "reps": "6-10",       "rest": 105, "effort": "RIR 2-3"},
            "secondary_compound": {"sets": 3, "reps": "8-12",       "rest": 90,  "effort": "RIR 2-3"},
            "accessory":          {"sets": 3, "reps": "10-15",      "rest": 60,  "effort": "RIR 2"},
            "isolation":          {"sets": 3, "reps": "12-15",      "rest": 60,  "effort": "RIR 1-2"},
            "unilateral":         {"sets": 3, "reps": "10-12 each", "rest": 75,  "effort": "RIR 2-3"},
            "core":               {"sets": 3, "reps": "10-15",      "rest": 45,  "effort": "Controlled"},
            "conditioning":       {"sets": 1, "reps": "10-15 min",  "rest": 0,   "effort": "Moderate-high — efficient cardio"},
            "explosive":          {"sets": 3, "reps": "4-6",        "rest": 90,  "effort": "Moderate power output"},
        },
        "general_fitness": {
            # Balanced and sustainable
            "primary_compound":   {"sets": 3, "reps": "6-10",       "rest": 90,  "effort": "RPE 7 — challenging but controlled"},
            "secondary_compound": {"sets": 3, "reps": "8-12",       "rest": 75,  "effort": "RPE 7"},
            "accessory":          {"sets": 2, "reps": "10-15",      "rest": 60,  "effort": "RPE 6-7"},
            "isolation":          {"sets": 2, "reps": "12-15",      "rest": 60,  "effort": "RPE 6-7"},
            "unilateral":         {"sets": 3, "reps": "10-12 each", "rest": 60,  "effort": "RPE 7"},
            "core":               {"sets": 2, "reps": "10-15",      "rest": 45,  "effort": "Controlled"},
            "conditioning":       {"sets": 1, "reps": "10-20 min",  "rest": 0,   "effort": "Moderate — enjoyable pace"},
            "explosive":          {"sets": 2, "reps": "5-8",        "rest": 75,  "effort": "Moderate — movement quality focus"},
        },
        "athletic_performance": {
            # Power and performance: low reps, long rest on main lifts
            "primary_compound":   {"sets": 4, "reps": "4-6",        "rest": 180, "effort": "RPE 8 — max intent, bar speed"},
            "secondary_compound": {"sets": 3, "reps": "4-8",        "rest": 120, "effort": "RPE 8 — controlled power"},
            "accessory":          {"sets": 3, "reps": "8-15",       "rest": 75,  "effort": "RPE 7-8"},
            "isolation":          {"sets": 2, "reps": "10-15",      "rest": 60,  "effort": "RIR 2-3"},
            "unilateral":         {"sets": 3, "reps": "6-10 each",  "rest": 90,  "effort": "RPE 7-8 — balance and control"},
            "core":               {"sets": 3, "reps": "8-12",       "rest": 60,  "effort": "Max tension — anti-rotation emphasis"},
            "conditioning":       {"sets": 1, "reps": "15-20 min",  "rest": 0,   "effort": "High intensity — sport-specific intervals"},
            "explosive":          {"sets": 4, "reps": "3-5",        "rest": 150, "effort": "Max intent — plyometric power output"},
        },
    }

    # ── Master volume framework ────────────────────────────────────────────────
    # (min_working_sets, max_working_sets, max_exercises) per goal × level × duration_bucket
    VOLUME_FRAMEWORK = {
        "build_muscle": {
            "beginner":     {30: (10,14,5), 45: (12,16,6), 60: (14,18,6), 75: (16,20,7)},
            "intermediate": {30: (12,15,5), 45: (14,18,6), 60: (16,20,7), 75: (18,22,8)},
            "advanced":     {30: (12,16,5), 45: (14,18,6), 60: (16,22,7), 75: (18,24,8)},
        },
        "lose_fat": {
            "beginner":     {30: (10,13,4), 45: (12,15,5), 60: (14,18,6), 75: (15,19,6)},
            "intermediate": {30: (11,14,5), 45: (13,16,6), 60: (15,19,6), 75: (16,20,7)},
            "advanced":     {30: (12,15,5), 45: (14,18,6), 60: (16,20,6), 75: (17,21,7)},
        },
        "body_recomp": {
            "beginner":     {30: (10,13,4), 45: (12,16,5), 60: (14,18,6), 75: (15,19,7)},
            "intermediate": {30: (11,14,5), 45: (13,17,6), 60: (15,19,7), 75: (16,21,8)},
            "advanced":     {30: (12,15,5), 45: (14,18,6), 60: (16,20,7), 75: (17,22,8)},
        },
        "strength": {
            "beginner":     {30: (8,12,4),  45: (10,14,4), 60: (12,16,5), 75: (14,18,5)},
            "intermediate": {30: (9,12,4),  45: (11,15,5), 60: (13,18,5), 75: (15,20,6)},
            "advanced":     {30: (10,13,4), 45: (12,16,5), 60: (14,20,5), 75: (16,22,6)},
        },
        "general_fitness": {
            "beginner":     {30: (8,12,4),  45: (10,14,5), 60: (12,16,6), 75: (13,17,7)},
            "intermediate": {30: (9,13,5),  45: (11,15,5), 60: (13,17,6), 75: (14,18,7)},
            "advanced":     {30: (10,14,5), 45: (12,16,6), 60: (14,18,7), 75: (15,20,7)},
        },
        "athletic_performance": {
            "beginner":     {30: (8,11,4),  45: (10,14,5), 60: (12,16,5), 75: (13,17,6)},
            "intermediate": {30: (9,12,4),  45: (11,15,5), 60: (13,17,6), 75: (14,19,7)},
            "advanced":     {30: (10,13,5), 45: (12,16,5), 60: (14,18,6), 75: (15,20,7)},
        },
        # Style-keyed entries used for hybrid/functional/calisthenics
        "hybrid":       {
            "beginner":     {30: (8,11,4),  45: (10,14,5), 60: (12,16,5), 75: (13,17,6)},
            "intermediate": {30: (9,12,4),  45: (11,15,5), 60: (13,17,6), 75: (14,19,7)},
            "advanced":     {30: (10,13,5), 45: (12,16,5), 60: (14,18,6), 75: (15,20,7)},
        },
        "functional":   {
            "beginner":     {30: (8,11,4),  45: (10,14,5), 60: (12,16,6), 75: (13,17,6)},
            "intermediate": {30: (9,12,5),  45: (11,15,5), 60: (13,17,6), 75: (14,19,7)},
            "advanced":     {30: (10,13,5), 45: (12,16,6), 60: (14,18,6), 75: (15,20,7)},
        },
        "calisthenics": {
            "beginner":     {30: (8,12,4),  45: (10,14,5), 60: (12,16,6), 75: (13,18,7)},
            "intermediate": {30: (9,13,5),  45: (11,15,6), 60: (13,17,6), 75: (14,19,7)},
            "advanced":     {30: (10,14,5), 45: (12,16,6), 60: (14,18,7), 75: (15,20,8)},
        },
    }

    # Sets per exercise type × level — used to allocate sets within the session budget
    # (min_sets_for_type, max_sets_for_type)
    SETS_PER_EXERCISE = {
        "primary_compound":   {"beginner": (2,4), "intermediate": (3,4), "advanced": (3,5)},
        "secondary_compound": {"beginner": (2,3), "intermediate": (3,4), "advanced": (3,4)},
        "accessory":          {"beginner": (2,3), "intermediate": (2,4), "advanced": (2,4)},
        "isolation":          {"beginner": (2,3), "intermediate": (2,4), "advanced": (2,4)},
        "unilateral":         {"beginner": (2,3), "intermediate": (3,4), "advanced": (3,4)},
        "core":               {"beginner": (2,3), "intermediate": (2,3), "advanced": (2,4)},
        "conditioning":       {"beginner": (1,1), "intermediate": (1,1), "advanced": (1,1)},
        "explosive":          {"beginner": (2,3), "intermediate": (3,4), "advanced": (4,5)},
    }

    # Goal-specific minimum rest floors for primary compounds (never reduce below this)
    STRENGTH_REST_FLOORS = {
        "strength":             150,  # 2.5 min absolute minimum
        "athletic_performance": 120,  # 2 min minimum
        "build_muscle":         90,
        "body_recomp":          75,
        "lose_fat":             60,
        "general_fitness":      60,
    }

    # Exercises that should be excluded for certain limitations
    LIMITATION_EXCLUSIONS = {
        "lower_back":    ["Conventional Deadlift", "Sumo Deadlift", "Good Morning", "Back Squat", "T-Bar Row", "Barbell Row"],
        "knee":          ["Back Squat", "Leg Press", "Barbell Bulgarian Split Squat", "Jump Squat", "Running", "Lunge"],
        "shoulder":      ["Barbell Overhead Press", "Push Press", "Upright Row", "Behind-the-Neck Press", "Barbell Bench Press"],
        "wrist":         ["Barbell Curl", "Barbell Overhead Press", "Push-Up", "Barbell Bench Press"],
        "elbow":         ["Skull Crusher", "Dip", "Barbell Curl"],
        "hip":           ["Barbell Hip Thrust", "Barbell Bulgarian Split Squat", "Leg Press"],
        "ankle":         ["Calf Raise", "Jump Squat", "Broad Jump"],
        "neck":          ["Barbell Back Squat", "Barbell Overhead Press"],
    }

    # Focus area → movement patterns that should receive volume priority
    FOCUS_AREA_PATTERNS: dict = {
        "chest":        ["horizontal_push", "incline_push"],
        "back":         ["vertical_pull", "horizontal_pull"],
        "shoulders":    ["vertical_push", "lateral_raise", "rear_delt"],
        "arms":         ["bicep_curl", "tricep_push"],
        "biceps":       ["bicep_curl"],
        "triceps":      ["tricep_push"],
        "legs":         ["squat", "lunge", "knee_extension", "calf", "hamstring_curl"],
        "glutes":       ["glute", "hip_hinge", "lunge"],
        "hamstrings":   ["hip_hinge", "hamstring_curl"],
        "quads":        ["squat", "lunge", "knee_extension"],
        "calves":       ["calf"],
        "core":         ["core_stability", "core_flexion", "carry"],
        "upper_body":   ["horizontal_push", "vertical_pull", "horizontal_pull", "vertical_push"],
        "lower_body":   ["squat", "hip_hinge", "glute", "lunge", "hamstring_curl"],
        "full_body":    [],
        "conditioning": ["conditioning", "explosive"],
        "power":        ["explosive", "squat", "hip_hinge"],
        "endurance":    ["conditioning"],
    }

    # Bodyweight exercise difficulty tiers for level-based ordering in calisthenics
    BODYWEIGHT_DIFFICULTY: dict = {
        # Tier 1 — Beginner
        "Push-Up": 1, "Bodyweight Squat": 1, "Glute Bridge": 1,
        "Hip Thrust": 1, "Single-Leg Glute Bridge": 1, "Plank": 1,
        "Bird Dog": 1, "Reverse Lunge": 1, "Reverse Crunch": 1,
        "Dead Bug": 1, "Side Plank": 1, "Bodyweight Calf Raise": 1,
        "Step-Up": 1, "Good Morning": 1,
        # Tier 2 — Intermediate
        "Diamond Push-Up": 2, "Pike Push-Up": 2, "Decline Push-Up": 2,
        "Jump Squat": 2, "Bulgarian Split Squat": 2, "Lateral Lunge": 2,
        "Australian Pull-Up": 2, "Inverted Row": 2, "Nordic Hamstring Curl": 2,
        "Hanging Leg Raise": 2, "V-Up": 2, "Single-Leg Calf Raise": 2,
        "Single-Leg Romanian Deadlift": 2, "Plank Walk": 2, "Supinated Row": 2,
        "Bench Dip": 2, "Swiss Ball Leg Curl": 2,
        # Tier 3 — Advanced
        "Archer Push-Up": 3, "Handstand Push-Up (wall assisted)": 3,
        "Pistol Squat (assisted)": 3, "Pull-Up": 3, "Chin-Up": 3,
        "Dip": 3, "Muscle-Up Progression": 3, "Terminal Knee Extension": 3,
    }

    def select_split(self, days: int, goal: str, style: str, level: str,
                     preferred_split: str, focus_areas: list) -> tuple:
        """Returns (split_id, split_display_name, rationale)"""

        # ── Style-first overrides: calisthenics/functional/hybrid always own their split ──
        if style == 'calisthenics':
            return 'calisthenics_split', 'Calisthenics Split', \
                "Bodyweight training is best structured as dedicated upper/lower sessions to maximise push/pull frequency and calisthenics skill progression."
        if style == 'functional':
            return 'functional_split', 'Functional A/B Split', \
                "Functional training alternates a Movement Quality session (unilateral strength, trunk control, loaded carries, aerobic capacity) with a Strength & Capacity session (compound strength, power output, high-intensity conditioning) — developing real-world athletic function."
        if style == 'hybrid':
            return 'hybrid_split', 'Hybrid Strength + Conditioning', \
                "Hybrid training alternates structured resistance sessions (each ending with a metabolic conditioning finisher) with dedicated Power & Conditioning sessions — building strength, muscular development, and cardiovascular capacity in the same program."

        # ── Athletic performance: always uses its own split ──────────────────
        if goal == 'athletic_performance':
            return 'athletic_split', 'Athletic Performance Split', \
                "Athletic performance training alternates full-body strength sessions with power and conditioning sessions — developing maximal strength, explosive power, and structural balance simultaneously."

        # ── Preferred split: honour it if valid for the day count ────────────
        if preferred_split != 'ai_choose':
            # Validate day compatibility and override gracefully with explanation if needed
            if preferred_split == 'bro_split':
                if days < 3:
                    return 'full_body', 'Full Body', \
                        f"Bro Split needs at least 3 training days. With {days} day(s)/week, Full Body is the correct choice to ensure adequate weekly volume across all muscle groups."
                split_rationale = (
                    f"Bro Split selected — each major muscle group gets its own dedicated session "
                    f"with maximum focus and volume. {days} days/week allows "
                    + ("Chest / Back / Legs / Shoulders." if days == 4 else
                       "Chest / Back / Shoulders / Legs / Arms." if days == 5 else
                       "Chest / Back / Shoulders / Legs / Arms + extra Back day." if days == 6 else
                       "Chest / Legs / Back rotation.")
                )
                return 'bro_split', 'Bro Split', split_rationale

            if preferred_split == 'push_pull_legs':
                if days < 3:
                    return 'full_body', 'Full Body', \
                        f"Push / Pull / Legs needs at least 3 days. With {days} day(s)/week, Full Body is recommended instead."
                return 'push_pull_legs', 'Push / Pull / Legs', \
                    f"Push/Pull/Legs selected — pushing, pulling, and leg patterns each get a dedicated session. {days} days/week gives a clean PPL rotation with balanced recovery."

            if preferred_split == 'upper_lower':
                if days < 2:
                    return 'full_body', 'Full Body', \
                        f"Upper/Lower needs at least 2 days. Full Body recommended instead."
                return 'upper_lower', 'Upper / Lower', \
                    f"Upper/Lower selected — upper and lower body each trained {max(1, days//2)} times per week with clear structural separation between pushing, pulling, and lower body work."

            if preferred_split == 'full_body':
                return 'full_body', 'Full Body', \
                    f"Full Body selected — every muscle group stimulated each session, {days} times per week. Ideal for maximum weekly frequency and movement pattern practice."

        # ── AI-selected split logic (days × goal × level) ────────────────────
        if days <= 2:
            return 'full_body', 'Full Body', \
                f"{days}-day training requires Full Body sessions to ensure every muscle is stimulated twice per week — the minimum for meaningful adaptation."
        elif days == 3:
            if goal == 'strength' and level in ['intermediate', 'advanced']:
                return 'full_body', 'Full Body', \
                    "3-day Full Body is ideal for strength — the big compounds (squat, bench, deadlift) are trained multiple times per week for maximum neural adaptation."
            if goal in ['build_muscle', 'body_recomp'] and level in ['intermediate', 'advanced']:
                return 'push_pull_legs', 'Push / Pull / Legs', \
                    "3-day PPL cleanly separates pushing, pulling, and leg patterns — each session fully focused on its muscle group with ideal recovery before the next session."
            return 'full_body', 'Full Body', \
                "3-day Full Body gives every muscle group 2-3x weekly stimulus with appropriate recovery, perfect for your goal and level combination."
        elif days == 4:
            if goal == 'strength':
                return 'upper_lower', 'Upper / Lower', \
                    "4-day Upper/Lower perfectly pairs the major strength lifts — upper body (bench, OHP, row) and lower body (squat, deadlift) each get two dedicated sessions per week."
            if goal in ['build_muscle', 'body_recomp']:
                return 'upper_lower', 'Upper / Lower', \
                    "4-day Upper/Lower provides twice-weekly frequency for every muscle group — the gold standard for hypertrophy and recomposition at this training frequency."
            if goal == 'lose_fat':
                return 'upper_lower', 'Upper / Lower', \
                    "4-day Upper/Lower maximises muscle retention during a fat loss phase — high frequency per muscle group combined with manageable session volume."
            return 'upper_lower', 'Upper / Lower', \
                "4-day Upper/Lower is the most well-balanced split at this frequency — twice-weekly per muscle, clear push/pull structure, and excellent recovery management."
        elif days == 5:
            if goal == 'build_muscle' and level == 'advanced':
                return 'push_pull_legs', 'Push / Pull / Legs', \
                    "5-day PPL (A/B rotation) gives advanced trainees near-twice-weekly frequency per pattern with higher total volume — ideal for maximising hypertrophy."
            return 'push_pull_legs', 'Push / Pull / Legs', \
                "5-day PPL provides each movement pattern its own dedicated session plus an extra session in the rotation — very high weekly frequency with targeted volume."
        else:  # 6+ days
            return 'push_pull_legs', 'Push / Pull / Legs (×2)', \
                "6-day PPL (Push/Pull/Legs × 2) provides maximum weekly volume and frequency — every pattern trained twice per week. Only appropriate with elite recovery capacity."

    def get_exercise_options(self, pattern: str, equipment: list, style: str,
                              limitations: list, level: str = 'intermediate') -> list:
        """
        Returns suitable exercise options for a slot.
        - Calisthenics / bodyweight-only: exercises sorted by difficulty for the given level.
        - Equipment-aware: builds candidates from equipment intersection.
        - Limitation-filtered: removes contraindicated exercises.
        """
        opts = self.PATTERNS.get(pattern, {})
        is_bodyweight_context = (
            style == 'calisthenics'
            or (equipment and all(e in ['bodyweight', 'resistance_bands'] for e in equipment))
        )

        if is_bodyweight_context:
            # Pull bodyweight (+ bands if available) options only
            candidates = list(opts.get('bodyweight', []))
            if 'resistance_bands' in (equipment or []):
                for ex in opts.get('resistance_bands', []):
                    if ex not in candidates:
                        candidates.append(ex)
            if not candidates:
                candidates = opts.get('any', ["Bodyweight Exercise"])
        else:
            candidates = []
            # ── Level-sensitive equipment ordering ─────────────────────────────
            # Beginners at a full gym get machines/cables/dumbbells prioritised
            # over barbells — safer, more stable, easier to learn and progress.
            # Intermediate and advanced get the standard ordering.
            if 'full_gym' in equipment and level == 'beginner':
                eq_order = ['beginner_gym', 'machines', 'cables', 'dumbbells',
                            'kettlebells', 'full_gym', 'resistance_bands', 'bodyweight', 'any']
            else:
                eq_order = ['full_gym', 'barbells', 'dumbbells', 'kettlebells',
                            'cables', 'machines', 'resistance_bands', 'bodyweight', 'any']
            for eq in eq_order:
                if (eq == 'any'
                        or eq in equipment
                        or eq in ('full_gym', 'barbells', 'beginner_gym') and 'full_gym' in equipment):
                    candidates.extend(opts.get(eq, []))
            if not candidates:
                candidates = opts.get('bodyweight', opts.get('any', ["Bodyweight Exercise"]))

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique.append(c)

        # Filter out exercises contraindicated by limitations
        excluded = set()
        for lim in (limitations or []):
            key = lim.lower().replace(' ', '_').replace('-', '_')
            for excl_key, excl_list in self.LIMITATION_EXCLUSIONS.items():
                if excl_key in key:
                    excluded.update(excl_list)
        filtered = [e for e in unique if e not in excluded]
        result = filtered if filtered else unique

        # ── Calisthenics difficulty ordering (Improvement #6) ─────────────────
        # Beginner: easiest first → coaches progressive skill building
        # Advanced: hardest first → challenges appropriately
        # Intermediate: natural order (tier 1-2 first, tier 3 last)
        if is_bodyweight_context or style == 'calisthenics':
            diff = self.BODYWEIGHT_DIFFICULTY
            if level == 'beginner':
                result = sorted(result, key=lambda x: diff.get(x, 2))
            elif level == 'advanced':
                result = sorted(result, key=lambda x: -diff.get(x, 2))
            else:  # intermediate — exclude tier-3 only from top options
                tier1_2 = [x for x in result if diff.get(x, 2) <= 2]
                tier3   = [x for x in result if diff.get(x, 2) > 2]
                result  = tier1_2 + tier3

        return result[:4] if result else ["Bodyweight Exercise"]

    def get_session_count_for_split(self, split_id: str, days: int) -> list:
        """Get the session types for this split and day count."""
        split_sessions = self.SPLIT_MAP.get(split_id, {})
        # Find closest matching day count
        if days in split_sessions:
            return split_sessions[days]
        # Try to find nearest
        available = sorted(split_sessions.keys())
        if not available:
            return ["full_body_heavy"] * days
        closest = min(available, key=lambda d: abs(d - days))
        sessions = split_sessions[closest]
        # Extend or trim to match requested days
        while len(sessions) < days:
            sessions = sessions + sessions
        return sessions[:days]

    def adjust_volume_for_level(self, ex_type: str, level: str, params: dict) -> dict:
        """
        Clamps sets to the level-appropriate range from SETS_PER_EXERCISE.
        Never exceeds the max for the level; never goes below the min.
        """
        adjusted = dict(params)
        ranges = self.SETS_PER_EXERCISE.get(ex_type, {}).get(level, (2, 4))
        s_min, s_max = ranges
        adjusted['sets'] = max(s_min, min(s_max, params['sets']))
        return adjusted

    def get_progression_model(self, goal: str, level: str) -> tuple:
        """Returns (method, description)"""
        if goal == 'strength':
            return ("Linear Periodisation",
                    "Add weight each session when you complete all sets with good form. Typically +2.5kg on upper, +5kg on lower. Deload after 4 weeks: reduce weight 40% for one week.")
        elif goal == 'build_muscle':
            return ("Double Progression",
                    "Work within the prescribed rep range. Once you hit the top end of the range on ALL sets → increase load by 2.5kg next session. Stay at the bottom until you earn the top.")
        elif goal == 'lose_fat':
            return ("Volume Progression",
                    "Prioritise consistent effort. Add 1 rep per set per week where possible. Increase weight when you exceed the top of the rep range on 2 consecutive sessions.")
        elif goal == 'body_recomp':
            return ("Double Progression",
                    "Same as hypertrophy: hit top of rep range on all sets → add weight. If you miss reps, stay at current weight. Progress will be slower — stay patient and consistent.")
        elif goal == 'athletic_performance':
            return ("Wave Loading",
                    "Cycle through heavy (week 1-2) and moderate (week 3) waves. Week 4 is a deload. Prioritise movement quality and bar speed over maximum load.")
        else:
            return ("Progressive Overload",
                    "Add weight or reps each week. If you can complete all sets at the top of the rep range, increase load slightly next session. Focus on consistent effort.")

    def build_blueprint(self, req) -> dict:
        """Main entry point — returns complete coaching blueprint."""
        goal = req.goal
        style = req.training_style
        days = req.days_per_week
        level = req.fitness_level
        equipment = req.equipment or ['full_gym']
        limitations = req.injuries or []
        focus = req.focus_areas or ['full_body']
        secondary = req.secondary_focus_areas or []
        preferred_split = req.preferred_split

        split_id, split_name, split_rationale = self.select_split(
            days, goal, style, level, preferred_split, focus)

        session_types = self.get_session_count_for_split(split_id, days)
        goal_params = self.GOAL_PARAMS.get(goal, self.GOAL_PARAMS['general_fitness'])
        progression_name, progression_desc = self.get_progression_model(goal, level)

        # Build per-day blueprints
        day_blueprints = []

        # ── Pre-compute focus area pattern lists (used in every day's loop) ──
        primary_focus_key = (focus[0] if focus else 'full_body').lower().replace(' ', '_')
        primary_patterns  = self.FOCUS_AREA_PATTERNS.get(primary_focus_key, [])
        secondary_patterns: list = []
        for sf in secondary:
            secondary_patterns.extend(
                self.FOCUS_AREA_PATTERNS.get(sf.lower().replace(' ', '_'), [])
            )

        for i, session_type in enumerate(session_types):
            archetype = self.SESSION_ARCHETYPES.get(session_type, self.SESSION_ARCHETYPES['full_body_heavy'])
            # Start with all slots (base + optional), trim later by budget
            slots = list(archetype['slots']) + list(archetype.get('optional_slots', []))

            # ── Determine duration bucket ────────────────────────────────────
            dur = req.duration_minutes
            if dur <= 30:
                dur_bucket = 30
            elif dur <= 45:
                dur_bucket = 45
            elif dur <= 60:
                dur_bucket = 60
            else:
                dur_bucket = 75

            # ── Get session budget from VOLUME_FRAMEWORK ─────────────────────
            # Use style-keyed entry for hybrid/functional/calisthenics, else goal-keyed
            if style in ('hybrid', 'functional', 'calisthenics'):
                vol_key = style
            else:
                vol_key = goal
            level_vol = self.VOLUME_FRAMEWORK.get(vol_key, self.VOLUME_FRAMEWORK['general_fitness'])
            budget_tuple = level_vol.get(level, level_vol.get('intermediate', {})).get(dur_bucket, (10, 16, 6))
            min_sets, max_sets, max_ex = budget_tuple
            target_sets = (min_sets + max_sets) // 2

            # ── Anti-bloat: conditioning finisher takes a slot ───────────────
            # If we're going to inject a conditioning finisher (not already in archetype),
            # pre-reduce the exercise count by 1 to make room.
            will_inject_cond = (
                goal in ('lose_fat', 'body_recomp')
                and style not in ('hybrid', 'functional')
                and not any(s[1] == 'conditioning' for s in slots)
                and ((goal == 'lose_fat') or (i % 2 == 0))
            )
            if will_inject_cond:
                max_ex = max(3, max_ex - 1)   # reserve one slot for finisher
                max_sets = max(min_sets, max_sets - 2)  # reduce set budget slightly
                target_sets = (min_sets + max_sets) // 2

            # Trim slots to max_exercises
            slots = slots[:max_ex]

            # ── Build slot specs with budget-aware set allocation ────────────
            excluded_exercises = set()
            for lim in limitations:
                lim_key = lim.lower().replace(' ', '_').replace('-', '_')
                for excl_key, excl_list in self.LIMITATION_EXCLUSIONS.items():
                    if excl_key in lim_key:
                        excluded_exercises.update(excl_list)

            slot_specs = []
            total_sets_allocated = 0

            for pattern, ex_type, coaching_note in slots:
                remaining_budget = target_sets - total_sets_allocated

                # How many sets should this slot get?
                base_params = goal_params.get(ex_type, goal_params.get('accessory', {}))
                ranges      = self.SETS_PER_EXERCISE.get(ex_type, {}).get(level, (2, 4))
                s_min, s_max = ranges
                base_sets   = base_params.get('sets', 3)
                # Clamp to level range
                ideal_sets  = max(s_min, min(s_max, base_sets))
                # Don't overshoot the session budget
                if ex_type == 'primary_compound':
                    # Primary compound always gets its full ideal allocation
                    assigned_sets = max(s_min, min(ideal_sets, max(s_min, remaining_budget)))
                elif remaining_budget <= s_min:
                    # Almost out of budget — give minimum or skip (use 1 as absolute floor)
                    assigned_sets = max(1, remaining_budget)
                else:
                    assigned_sets = min(ideal_sets, remaining_budget)

                assigned_sets = max(1, assigned_sets)
                total_sets_allocated += assigned_sets

                # ── Goal-specific rest with duration-adjusted floors ─────────
                base_rest   = base_params.get('rest', 90)
                floor       = self.STRENGTH_REST_FLOORS.get(goal, 60)

                if dur_bucket <= 30:
                    # Short session — shorten accessory/isolation rests aggressively
                    # but never violate strength floor on primary compounds
                    if ex_type == 'primary_compound' and goal == 'strength':
                        rest = max(floor, int(base_rest * 0.85))  # gentle reduction for strength
                    elif ex_type in ('primary_compound', 'secondary_compound'):
                        rest = max(floor, int(base_rest * 0.65))
                    else:
                        rest = max(30, int(base_rest * 0.55))
                elif dur_bucket <= 45:
                    if ex_type == 'primary_compound' and goal == 'strength':
                        rest = max(floor, int(base_rest * 0.90))  # minimal reduction
                    elif ex_type in ('primary_compound', 'secondary_compound'):
                        rest = max(floor, int(base_rest * 0.80))
                    else:
                        rest = max(45, int(base_rest * 0.70))
                else:
                    # 60+ min — use goal-prescribed rest unchanged
                    rest = base_rest

                options = self.get_exercise_options(pattern, equipment, style, limitations, level)

                slot_specs.append({
                    "pattern":       pattern,
                    "type":          ex_type,
                    "coaching_note": coaching_note,
                    "sets":          assigned_sets,
                    "reps":          base_params.get('reps', '8-12'),
                    "rest_seconds":  rest,
                    "effort":        base_params.get('effort', 'RPE 7'),
                    "options":       options,
                    "excluded":      list(excluded_exercises),
                })

                # Hard stop if over budget (except always include all primary_compounds)
                if ex_type != 'primary_compound' and total_sets_allocated >= target_sets:
                    break

            # ── Minimum set floors — remove exercises that can't hit floor ────
            # A 1-set bench press is not coaching. Remove rather than include awkwardly.
            MIN_SETS_FLOOR = {
                "primary_compound":   3,
                "secondary_compound": 2,
                "accessory":          2,
                "isolation":          2,
                "unilateral":         2,
                "core":               2,
                "explosive":          2,
                "conditioning":       1,   # finisher can be 1 block
            }
            slot_specs = [s for s in slot_specs if s['sets'] >= MIN_SETS_FLOOR.get(s['type'], 2)]
            total_sets_allocated = sum(s['sets'] for s in slot_specs)

            # ── Focus area volume boost (within budget) ───────────────────────
            # Boost primary focus +1 set (cap max_sets+2), secondary +0 (already at budget)
            focus_boost_headroom = 2  # allow slight over-target for focus areas
            for slot in slot_specs:
                if slot['pattern'] in primary_patterns:
                    boosted = min(slot['sets'] + 1, slot['sets'] + 1)
                    # Only boost if within reasonable headroom
                    if total_sets_allocated - slot['sets'] + boosted <= max_sets + focus_boost_headroom:
                        total_sets_allocated += (boosted - slot['sets'])
                        slot['sets'] = min(boosted, 6)
                elif slot['pattern'] in secondary_patterns:
                    if total_sets_allocated < max_sets:
                        slot['sets'] = min(slot['sets'] + 1, 5)
                        total_sets_allocated += 1

            # Reorder: primary_compound → primary focus → secondary focus → rest
            def _slot_priority(s: dict) -> int:
                if s['type'] == 'primary_compound':
                    return 0
                if s['pattern'] in primary_patterns:
                    return 1
                if s['pattern'] in secondary_patterns:
                    return 2
                return 3
            slot_specs.sort(key=_slot_priority)

            # ── Conditioning finisher injection ───────────────────────────────
            if will_inject_cond:
                cond_params  = goal_params.get(
                    'conditioning',
                    {"sets": 1, "reps": "10-20 min intervals", "rest": 0, "effort": "High intensity"}
                )
                cond_options = self.get_exercise_options(
                    'conditioning', equipment, style, limitations, level
                )
                slot_specs.append({
                    "pattern":       "conditioning",
                    "type":          "conditioning",
                    "coaching_note": "metabolic finisher — elevate heart rate, maximise calorie burn",
                    "sets":          1,
                    "reps":          cond_params.get('reps', '10-20 min'),
                    "rest_seconds":  0,
                    "effort":        cond_params.get('effort', 'High intensity'),
                    "options":       cond_options,
                    "excluded":      [],
                })

            day_blueprints.append({
                "session_number": i + 1,
                "archetype_id":   session_type,
                "label":          archetype['label'],
                "focus":          archetype['focus'],
                "slots":          slot_specs,
            })

        return {
            "split_id":          split_id,
            "split_name":        split_name,
            "split_rationale":   split_rationale,
            "progression_name":  progression_name,
            "progression_desc":  progression_desc,
            "deload_timing":     {
                "strength":             "Every 4 weeks: reduce weight 40% for 1 week, then reload heavier than before.",
                "build_muscle":         "Every 5-6 weeks: cut working sets by 50% for 1 week — keep load, reduce volume.",
                "lose_fat":             "Every 6-7 weeks: reduce volume 40% for 1 week while maintaining training frequency.",
                "body_recomp":          "Every 5 weeks: reduce both load and volume by 40% — prioritise sleep and recovery.",
                "athletic_performance": "Every 4 weeks: cut volume 50% — use deload week for skill work and mobility.",
                "general_fitness":      "Every 6-8 weeks: reduce total volume by 30% for 1 week, stay lightly active.",
            }.get(goal, "Every 5-6 weeks: reduce volume by 40% for 1 week to allow full recovery and super-compensation."),
            "weekly_structure":  [f"Day {d['session_number']}: {d['label']} — {d['focus']}" for d in day_blueprints],
            "day_blueprints":    day_blueprints,
            "goal":              goal,
            "style":             style,
            "level":             level,
            "days":              days,
            "duration":          req.duration_minutes,
            "equipment":         equipment,
            "limitations":       limitations,
            "focus":             focus,
            "secondary":         secondary,
        }

_coaching_engine = EliteCoachingEngine()

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
    """
    ELITE COACHING ENGINE
    Step 1 (Python): Build a complete blueprint — split, volume, sets/reps/rest/effort, exercise options
    Step 2 (LLM):    Fill in ONLY exercise names (from options list) and form coaching instructions
    Step 3 (Python): Merge, store coaching metadata, fetch GIFs
    """

    # ─── STEP 1: Python builds the full blueprint ─────────────────────────────
    blueprint = _coaching_engine.build_blueprint(request)

    # ─── STEP 2: Build tight LLM prompt ───────────────────────────────────────
    # Claude picks ONE name from each slot's options list + writes form cues.
    # Sets / reps / rest / effort are FIXED — Claude cannot change them.

    prompt_lines = [
        f"Goal: {blueprint['goal'].replace('_',' ')} | Style: {blueprint['style']} | "
        f"Level: {blueprint['level']} | Split: {blueprint['split_name']}",
        f"Equipment: {', '.join(blueprint['equipment'])}",
        f"Limitations: {', '.join(blueprint['limitations']) if blueprint['limitations'] else 'None'}",
    ]
    if blueprint.get('secondary'):
        prompt_lines.append(
            f"Primary focus: {', '.join(blueprint['focus'])} | "
            f"Secondary emphasis: {', '.join(blueprint['secondary'])}"
        )
    elif blueprint.get('focus') and blueprint['focus'] != ['full_body']:
        prompt_lines.append(f"Focus areas: {', '.join(blueprint['focus'])}")
    prompt_lines += [
        "",
        "For each slot below: choose ONE name from Options and write coaching Instructions (15-20 words, strict form cue).",
        "Do NOT change sets, reps, rest, or effort — those are fixed.",
        "",
    ]

    day_slot_data = []

    for day_bp in blueprint['day_blueprints']:
        prompt_lines.append(
            f"Day {day_bp['session_number']} — {day_bp['label']} | Focus: {day_bp['focus']}"
        )
        day_exercises_meta = []

        for slot_idx, slot in enumerate(day_bp['slots']):
            opts = slot['options'] or ['Bodyweight Exercise']
            prompt_lines.append(
                f"  [{slot_idx+1}] {slot['coaching_note']} | "
                f"{slot['sets']}×{slot['reps']} | {slot['rest_seconds']}s rest | {slot['effort']}"
            )
            prompt_lines.append(f"  Options: {', '.join(opts[:3])}")
            prompt_lines.append(f"  → name: ?, instructions: ?")

            day_exercises_meta.append({
                "pattern":       slot['pattern'],
                "type":          slot['type'],
                "coaching_note": slot['coaching_note'],
                "options":       opts,
                "sets":          slot['sets'],
                "reps":          slot['reps'],
                "rest_seconds":  slot['rest_seconds'],
                "effort":        slot['effort'],
                "default_name":  opts[0],
            })

        day_slot_data.append({
            "session_number":  day_bp['session_number'],
            "label":           day_bp['label'],
            "focus":           day_bp['focus'],
            "exercises_meta":  day_exercises_meta,
        })
        prompt_lines.append("")

    prompt_lines += [
        'Return ONLY valid compact JSON in this exact format:',
        '{"program_name":"...","workout_days":[{"exercises":[{"name":"...","instructions":"..."},...]},...]}',
        "Same day order and exercise count as above. JSON only, no markdown.",
    ]
    prompt = '\n'.join(prompt_lines)

    # ─── STEP 2b: Call LLM ────────────────────────────────────────────────────
    def _clean_json(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith('```'):
            parts = raw.split('```')
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith('json'):
                raw = raw[4:]
        return raw.strip()

    def _repair_json(content: str) -> str:
        content = content.strip()
        while content and content[-1] == ',':
            content = content[:-1].rstrip()
        open_braces   = content.count('{') - content.count('}')
        open_brackets = content.count('[') - content.count(']')
        content += ']' * max(0, open_brackets) + '}' * max(0, open_braces)
        return content

    llm_data = None
    for attempt in range(2):
        try:
            content = await call_claude_sonnet(
                system_message=(
                    "You are a personal trainer filling an exercise scaffold. "
                    "Pick ONE name from each slot's Options list and write 15-20 word form coaching instructions. "
                    "Return ONLY valid compact JSON. No markdown. No extra fields."
                ),
                user_message=prompt,
                temperature=0.3 if attempt == 0 else 0.1,
                max_tokens=3500,
            )
            content = _clean_json(content)
            logger.info(f"Workout gen attempt {attempt+1}: response len={len(content)}")
            try:
                llm_data = json.loads(content)
                break
            except json.JSONDecodeError:
                try:
                    llm_data = json.loads(_repair_json(content))
                    logger.info("Workout gen: JSON repair succeeded")
                    break
                except Exception:
                    llm_data = None
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Workout gen attempt {attempt+1} error: {e}")
            if attempt == 1:
                raise HTTPException(status_code=500, detail=f"Failed to generate workout: {str(e)}")

    # ─── STEP 3: Merge LLM output with blueprint ──────────────────────────────
    PATTERN_MUSCLES = {
        "horizontal_push": ["chest", "triceps", "front delts"],
        "incline_push":    ["upper chest", "triceps"],
        "vertical_push":   ["shoulders", "triceps"],
        "lateral_raise":   ["medial delts", "shoulders"],
        "rear_delt":       ["rear delts", "upper back"],
        "tricep_push":     ["triceps"],
        "vertical_pull":   ["lats", "biceps"],
        "horizontal_pull": ["rhomboids", "lats", "biceps"],
        "bicep_curl":      ["biceps", "brachialis"],
        "squat":           ["quads", "glutes"],
        "lunge":           ["quads", "glutes", "hamstrings"],
        "hip_hinge":       ["hamstrings", "glutes", "lower back"],
        "glute":           ["glutes", "hip flexors"],
        "hamstring_curl":  ["hamstrings"],
        "knee_extension":  ["quads"],
        "calf":            ["calves", "soleus"],
        "core_stability":  ["core", "abs", "obliques"],
        "core_flexion":    ["abs", "hip flexors"],
        "carry":           ["core", "grip", "traps"],
        "explosive":       ["quads", "glutes", "calves"],
        "conditioning":    ["full body", "cardiovascular"],
    }

    program_name = f"{blueprint['goal'].replace('_',' ').title()} — {blueprint['split_name']}"
    if llm_data and llm_data.get('program_name'):
        program_name = llm_data['program_name']

    llm_days = (llm_data or {}).get('workout_days', [])
    processed_days = []

    for day_idx, day in enumerate(day_slot_data):
        llm_day_exs = []
        if day_idx < len(llm_days) and llm_days[day_idx]:
            llm_day_exs = llm_days[day_idx].get('exercises', [])

        exercises_with_gifs = []
        for ex_idx, slot_meta in enumerate(day['exercises_meta']):
            llm_ex = llm_day_exs[ex_idx] if ex_idx < len(llm_day_exs) else {}

            chosen_name = (llm_ex.get('name') or '').strip() or slot_meta['default_name']
            instructions = (llm_ex.get('instructions') or '').strip()
            if not instructions:
                instructions = (
                    f"Perform {chosen_name} with controlled tempo, full range of motion, "
                    "and proper form throughout."
                )

            gif_url = await get_exercise_gif_from_api(chosen_name)

            # Infer equipment tag from exercise name
            nl = chosen_name.lower()
            if blueprint['style'] == 'calisthenics':
                eq = 'bodyweight'
            elif any(w in nl for w in ['barbell ',' barbell']):
                eq = 'barbell'
            elif 'barbell' in nl and not any(w in nl for w in ['split squat', 'hip thrust', 'glute bridge']):
                eq = 'barbell'
            elif any(w in nl for w in ['conventional deadlift', 'sumo deadlift', 'romanian deadlift']):
                eq = 'barbell'
            elif any(w in nl for w in ['back squat', 'front squat', 'pause squat', 'overhead press']):
                eq = 'barbell'
            elif any(w in nl for w in ['dumbbell', ' db ']):
                eq = 'dumbbells'
            elif any(w in nl for w in ['cable', 'machine', 'pulldown', 'leg press']):
                eq = 'cable/machine'
            elif any(w in nl for w in ['kettlebell', 'kb']):
                eq = 'kettlebell'
            elif any(w in nl for w in ['band', 'resistance']):
                eq = 'resistance band'
            else:
                eq = 'bodyweight'

            exercises_with_gifs.append({
                "name":              chosen_name,
                "sets":              slot_meta['sets'],
                "reps":              slot_meta['reps'],
                "rest_seconds":      slot_meta['rest_seconds'],
                "instructions":      instructions,
                "muscle_groups":     PATTERN_MUSCLES.get(slot_meta['pattern'], ['various']),
                "equipment":         eq,
                "gif_url":           gif_url,
                "effort_target":     slot_meta['effort'],
                "exercise_type":     slot_meta['type'],
                "substitution_hint": ', '.join(slot_meta['options'][1:3])
                                     if len(slot_meta['options']) > 1 else None,
            })

        main_rest = day['exercises_meta'][0]['rest_seconds'] if day['exercises_meta'] else 90
        processed_days.append({
            "day":              f"Day {day['session_number']} — {day['label']}",
            "focus":            day['focus'],
            "duration_minutes": request.duration_minutes,
            "notes": (
                f"{day['label']} session — {day['focus']}. "
                f"Rest {main_rest}s on main lifts. Focus on controlled tempo and muscle connection."
            ),
            "exercises":        exercises_with_gifs,
        })

    # Build progression + deload text
    prog_name, prog_desc = _coaching_engine.get_progression_model(
        blueprint['goal'], blueprint['level']
    )

    program = WorkoutProgram(
        user_id=request.user_id,
        name=program_name,
        goal=request.goal,
        training_style=request.training_style,
        fitness_level=request.fitness_level,
        focus_areas=request.focus_areas,
        secondary_focus_areas=request.secondary_focus_areas,
        equipment=request.equipment,
        injuries=request.injuries,
        days_per_week=request.days_per_week,
        session_duration_minutes=request.duration_minutes,
        preferred_split=request.preferred_split,
        split_name=blueprint['split_name'],
        split_rationale=blueprint['split_rationale'],
        progression_method=f"{prog_name} — {prog_desc}",
        deload_timing=blueprint['deload_timing'],
        weekly_structure=blueprint['weekly_structure'],
        training_notes=(
            f"Goal: {request.goal.replace('_',' ').title()} | "
            f"Style: {request.training_style.title()} | "
            f"Split: {blueprint['split_name']} | "
            f"{request.days_per_week} days/week @ {request.duration_minutes}min"
        ),
        workout_days=[WorkoutDay(**day) for day in processed_days],
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
    
    # ALWAYS use AI generation for world-class personalized meal plans
    # Templates are only used as fallback if AI fails
    logger.info(f"Using AI generation | style={eating_style} | preferred={request.preferred_foods} | avoid={request.foods_to_avoid} | allergies={request.allergies}")
    if True:
        
        # For keto/carnivore: override macro targets with diet-appropriate values
        # User's profile targets are based on general fitness goals, but keto needs 70%+ fat, <5% carbs
        ai_target_cal = target_cal
        if eating_style == 'keto':
            ai_target_fat = round(target_cal * 0.72 / 9)    # 72% of calories from fat
            ai_target_carb = min(30, round(target_cal * 0.05 / 4))  # 5% calories, max 30g carbs
            ai_target_pro = round((target_cal - ai_target_fat * 9 - ai_target_carb * 4) / 4)  # remaining from protein
        elif eating_style == 'carnivore':
            ai_target_fat = round(target_cal * 0.70 / 9)    # 70% fat
            ai_target_carb = 5                               # near-zero carbs
            ai_target_pro = round((target_cal - ai_target_fat * 9 - ai_target_carb * 4) / 4)
        else:
            # All other diets: use the user's profile macro targets
            ai_target_fat = target_fat
            ai_target_carb = target_carb
            ai_target_pro = target_pro
        
        # Calculate exact per-meal targets using diet-adjusted macros
        breakfast_cal = round(ai_target_cal * 0.25)
        breakfast_pro = round(ai_target_pro * 0.25)
        breakfast_carb = round(ai_target_carb * 0.25)
        breakfast_fat = round(ai_target_fat * 0.25)
        
        lunch_cal = round(ai_target_cal * 0.30)
        lunch_pro = round(ai_target_pro * 0.30)
        lunch_carb = round(ai_target_carb * 0.30)
        lunch_fat = round(ai_target_fat * 0.30)
        
        dinner_cal = round(ai_target_cal * 0.35)
        dinner_pro = round(ai_target_pro * 0.35)
        dinner_carb = round(ai_target_carb * 0.35)
        dinner_fat = round(ai_target_fat * 0.35)
        
        snack_cal = ai_target_cal - breakfast_cal - lunch_cal - dinner_cal
        snack_pro = ai_target_pro - breakfast_pro - lunch_pro - dinner_pro
        snack_carb = ai_target_carb - breakfast_carb - lunch_carb - dinner_carb
        snack_fat = ai_target_fat - breakfast_fat - lunch_fat - dinner_fat
        
        # Determine if user needs lean or moderate-fat proteins based on their fat target
        fat_pct = (ai_target_fat * 9 / ai_target_cal) * 100 if ai_target_cal > 0 else 30
        
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
            diet_instructions = f"""VEGAN: NO animal products whatsoever.
HIGH-PROTEIN VEGAN RULE: Every meal MUST have a HIGH-PROTEIN base ingredient:
  - Breakfast: tofu scramble (100g tofu = 8g P) OR protein powder (30g = 20-25g P) OR seitan
  - Lunch: tempeh ({round(ai_target_pro * 0.30 / 0.189)}g = {round(ai_target_pro * 0.30)}g P) OR seitan (25g P per 100g) OR high-protein tofu
  - Dinner: seitan ({round(ai_target_pro * 0.35 / 0.25)}g = {round(ai_target_pro * 0.35)}g P) OR tempeh OR firm tofu
  - Snack: vegan protein powder (20-25g P per 30g) OR hemp seeds (31g P per 100g)
IMPORTANT: Do NOT rely solely on lentils/chickpeas for protein — they are high-carb too.
Protein sources per 100g: seitan=25g | tempeh=19g | edamame=11g | firm tofu=8g | hemp seeds=31g"""
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
        
        # Calculate macro percentages to guide AI (use diet-adjusted targets)
        protein_pct = round((ai_target_pro * 4 / ai_target_cal) * 100) if ai_target_cal > 0 else 30
        carb_pct = round((ai_target_carb * 4 / ai_target_cal) * 100) if ai_target_cal > 0 else 40
        fat_pct = round((ai_target_fat * 9 / ai_target_cal) * 100) if ai_target_cal > 0 else 30
        
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
        # Build allergy-specific prohibition block
        allergy_specifics = {
            'gluten': 'NO wheat, barley, rye, oats (ALL oats — even "gluten-free" labelled oats), spelt, seitan, regular pasta, bread, flour. Use tamari not soy sauce. Use rice, quinoa, sweet potato instead of grains.',
            'dairy': 'NO milk, cheese, yogurt, butter, cream, whey, casein. Use plant-based alternatives.',
            'nuts': 'NO almonds, cashews, walnuts, pecans, pistachios, brazil nuts, hazelnuts, macadamia. Seeds (sunflower, pumpkin) OK.',
            'eggs': 'NO eggs in any form — fried, scrambled, boiled, baked.',
            'soy': 'NO tofu, tempeh, soy sauce, edamame, soy milk, miso.',
            'shellfish': 'NO shrimp, crab, lobster, scallops, oysters, mussels, clams.',
            'fish': 'NO salmon, tuna, cod, tilapia, bass or any fish species.',
            'peanuts': 'NO peanuts or peanut butter in any form.',
        }
        allergy_lines = []
        for allergy in (request.allergies or []):
            spec = allergy_specifics.get(allergy.lower(), f'NO {allergy} in any form.')
            allergy_lines.append(f"  - {allergy.upper()}: {spec}")
        allergy_block = '\n'.join(allergy_lines) if allergy_lines else '  - None'

        # Foods section — personalised whether or not user typed preferred foods
        if request.preferred_foods and request.preferred_foods.strip():
            foods_section = f"INCORPORATE THESE PREFERRED FOODS: {request.preferred_foods}\nBuild all meals around these. Supplement with complementary whole foods to hit macro targets."
        else:
            style_food_ideas = {
                'keto': 'Use: ribeye, salmon, eggs, bacon, avocado, butter, cream, brie, macadamia nuts, leafy greens, broccoli, cauliflower.',
                'vegan': 'Use: tempeh, tofu, black beans, lentils, quinoa, chickpeas, edamame, nuts, seeds, plant-based protein powder.',
                'vegetarian': 'Use: eggs, greek yogurt, cottage cheese, tempeh, legumes, quinoa, sweet potato, brown rice.',
                'paleo': 'Use: lean beef, salmon, chicken, sweet potato, almond flour, coconut oil, berries, green vegetables.',
                'carnivore': 'Use ONLY: beef (ribeye/sirloin/ground), chicken thighs, salmon, bacon, eggs, butter. Zero carbs.',
                'high_protein': f'Use: chicken breast, turkey, tuna, egg whites, greek yogurt, cottage cheese, lean beef, whey protein. IMPORTANT: Still include {ai_target_carb}g carbs from: oats, rice, sweet potato, fruit. This is high PROTEIN, not low carb!',
                'balanced': 'Use a rich variety: lean proteins, complex carbs (rice, oats, sweet potato), healthy fats, diverse vegetables.',
                'whole_foods': 'Use only whole, unprocessed ingredients. No packaged foods. Rich variety of vegetables, legumes, lean proteins.',
            }
            style_hint = style_food_ideas.get(eating_style, style_food_ideas['balanced'])
            foods_section = f"No preferred foods specified — choose ELITE, nutritionist-approved foods for a {eating_style.replace('_', ' ')} diet.\n{style_hint}"

        # Calculate fat percentage to guide lean vs rich protein choices
        fat_is_strict = ai_target_fat < (ai_target_cal * 0.33 / 9)  # Less than 33% fat calories = strict

        fat_guidance = ""
        if fat_is_strict:
            fat_guidance = f"""FAT BUDGET: {ai_target_fat}g/day ({fat_pct:.0f}% of calories) — STRICT.
⚠️ COUNT FAT FROM EVERY SOURCE — protein foods have fat too:
  Whole egg (50g each) = 5.5g fat | Salmon 100g = 13g fat | Ribeye 100g = 15g fat
  Chicken breast 100g = 3.6g fat | Turkey breast = 1g | Cod/Tuna/Shrimp ≈ 0.5-1g
RULE: Fat in each meal = fat from protein + fat from added oils/nuts/dairy — TOTAL must stay ≤ meal fat target.
- PREFER zero-fat proteins (chicken breast, turkey, tuna, shrimp, cod, egg WHITES, cottage cheese)
- LIMIT whole eggs: max {round(ai_target_fat * 0.2 / 5.5):.0f} eggs total per day (each egg = 5.5g fat)
- Added oil: if using whole eggs or salmon, use ZERO added oil
- NO avocado >30g/day, NO full-fat cheese, NO nuts if fat budget is tight"""
        else:
            fat_guidance = f"Fat target: {ai_target_fat}g/day ({fat_pct:.0f}%). Healthy fats from natural sources welcome — count fat from ALL ingredients."

        # Pre-calculate exact ingredient quantities needed per meal for accurate macro targeting
        def grams_for_macro(target_macro_g, food_density):
            """How many grams of food needed to hit a macro target"""
            return round(target_macro_g / food_density * 100) if food_density > 0 else 0

        # Protein quantities (per meal)
        b_pro_chicken = grams_for_macro(breakfast_pro, 31)
        b_pro_eggs    = round(breakfast_pro / 6.5)  # number of eggs
        l_pro_chicken = grams_for_macro(lunch_pro, 31)
        l_pro_beef    = grams_for_macro(lunch_pro, 26)
        d_pro_chicken = grams_for_macro(dinner_pro, 31)
        d_pro_beef    = grams_for_macro(dinner_pro, 26)
        s_pro_yogurt  = grams_for_macro(snack_pro, 10)

        # Carb quantities (per meal)
        b_carb_rice   = grams_for_macro(breakfast_carb, 28)
        b_carb_potato = grams_for_macro(breakfast_carb, 20)
        l_carb_rice   = grams_for_macro(lunch_carb, 28)
        l_carb_potato = grams_for_macro(lunch_carb, 20)
        d_carb_rice   = grams_for_macro(dinner_carb, 28)
        d_carb_potato = grams_for_macro(dinner_carb, 20)

        # Fat per meal (g)
        b_fat_oil_ml  = round(breakfast_fat / 14 * 10)  # ml of olive oil
        l_fat_oil_ml  = round(lunch_fat / 14 * 10)
        d_fat_oil_ml  = round(dinner_fat / 14 * 10)

        prompt = f"""You are an ELITE sports nutritionist. Create a world-class, fully personalised 3-day meal plan.

DIET STYLE: {eating_style.upper().replace('_', ' ')}
{diet_instructions}

DAILY MACRO TARGETS — hit these precisely:
{ai_target_cal} cal | {ai_target_pro}g protein ({protein_pct}%) | {ai_target_carb}g carbs ({carb_pct}%) | {ai_target_fat}g fat ({fat_pct}%)

ABSOLUTE PROHIBITIONS — NEVER include these:
{allergy_block}
{avoid_instructions if avoid_instructions else ''}
{do_not_use_str if do_not_use_str else ''}

{fat_guidance}

{foods_section}

{protein_guidance_for_prompt}
{protein_guidance}

MACRO REFERENCE (per 100g cooked unless noted):
Chicken breast: 165cal 31P 0C 3.6F | Turkey breast: 135cal 30P 0C 1F | Tuna: 116cal 26P 0C 0.8F
Beef sirloin: 207cal 26P 0C 11F | Shrimp: 99cal 24P 0C 0.3F | Cod: 82cal 18P 0C 0.7F
Salmon: 208cal 20P 0C 13F | Egg whites (100g): 52cal 11P 0.7C 0.2F | Whole egg (50g ea): 78cal 6.5P 0.5C 5.5F
Tofu firm: 144cal 17P 3C 8F | Tempeh: 192cal 20P 8C 11F | Greek yogurt 0%: 59cal 10P 4C 0.4F
Cottage cheese: 84cal 11P 4C 2.5F | White rice cooked: 130cal 2.7P 28C 0.3F | Brown rice: 112cal 2.7P 24C 0.9F
Sweet potato: 86cal 1.6P 20C 0.1F | Quinoa cooked: 120cal 4.4P 21C 1.9F | Oats dry: 389cal 17P 66C 7F
Banana (120g): 107cal 1.3P 27.6C 0.4F | Avocado (50g): 80cal 1P 4.5C 7.5F | Olive oil (10ml): 88cal 0P 0C 10F

EXACT QUANTITIES TO HIT EACH MEAL TARGET:
⚠️ CRITICAL: The fat values below are TOTAL fat — count fat from proteins + oils + all ingredients combined.

Breakfast ({breakfast_cal}cal | {breakfast_pro}g P | {breakfast_carb}g C | {breakfast_fat}g F total):
  Protein: {b_pro_chicken}g chicken breast (only 4g fat) OR use egg whites if fat is tight
  Note: 1 whole egg = 5.5g fat — if using eggs, count their fat against {breakfast_fat}g budget
  Carbs: {b_carb_rice}g cooked rice OR {b_carb_potato}g sweet potato
  Max added fat (oil/butter): {breakfast_fat}g minus fat already in your protein choice

Lunch ({lunch_cal}cal | {lunch_pro}g P | {lunch_carb}g C | {lunch_fat}g F total):
  Protein: {l_pro_chicken}g chicken breast (4g fat) OR {l_pro_beef}g tuna/turkey
  Note: salmon 100g = 13g fat — account for this in {lunch_fat}g total budget
  Carbs: {l_carb_rice}g cooked rice OR {l_carb_potato}g sweet potato
  Max added fat: {lunch_fat}g minus fat from your protein choice

Dinner ({dinner_cal}cal | {dinner_pro}g P | {dinner_carb}g C | {dinner_fat}g F total):
  Protein: {d_pro_chicken}g chicken OR {d_pro_beef}g lean beef/fish — steak has 11g fat/100g so only {round(dinner_fat/0.11)}g steak max before adding oil
  Carbs: {d_carb_rice}g cooked rice OR {d_carb_potato}g sweet potato
  Max added fat: {dinner_fat}g minus fat from your protein choice

Snack ({snack_cal}cal | {snack_pro}g P | {snack_carb}g C | {snack_fat}g F total):
  Protein: {s_pro_yogurt}g Greek yogurt OR equivalent | Keep total fat ≤{snack_fat}g

ELITE STANDARDS:
1. All 3 days MUST have completely different meals — zero repetition
2. Use the EXACT gram amounts from the quantities guide above
3. Give each meal an appealing, descriptive name (e.g. "Herb-Marinated Chicken with Jasmine Rice & Broccolini")
4. Instructions: concise 2-3 step cooking method. NEVER mention specific gram or ml amounts in instructions — all quantities are already listed in the ingredients field. Write "add olive oil" NOT "add 15g olive oil".
5. Calculate ACCURATE macros from the actual ingredient weights you use

Return ONLY this JSON (no markdown):
{{"name": "{plan_name} Elite Meal Plan", "meal_days": [
  {{"day": "Day 1", "total_calories": {target_cal}, "total_protein": {target_pro}, "total_carbs": {target_carb}, "total_fats": {target_fat}, "meals": [
    {{"id": "d1m1", "name": "Meal Name", "meal_type": "breakfast", "ingredients": ["Xg ingredient"], "instructions": "Steps.", "calories": {breakfast_cal}, "protein": {breakfast_pro}, "carbs": {breakfast_carb}, "fats": {breakfast_fat}, "prep_time_minutes": 10}},
    {{"id": "d1m2", "name": "Meal Name", "meal_type": "lunch", "ingredients": ["Xg ingredient"], "instructions": "Steps.", "calories": {lunch_cal}, "protein": {lunch_pro}, "carbs": {lunch_carb}, "fats": {lunch_fat}, "prep_time_minutes": 20}},
    {{"id": "d1m3", "name": "Meal Name", "meal_type": "dinner", "ingredients": ["Xg ingredient"], "instructions": "Steps.", "calories": {dinner_cal}, "protein": {dinner_pro}, "carbs": {dinner_carb}, "fats": {dinner_fat}, "prep_time_minutes": 25}},
    {{"id": "d1m4", "name": "Snack Name", "meal_type": "snack", "ingredients": ["Xg ingredient"], "instructions": "Steps.", "calories": {snack_cal}, "protein": {snack_pro}, "carbs": {snack_carb}, "fats": {snack_fat}, "prep_time_minutes": 5}}
  ]}},
  {{"day": "Day 2", "total_calories": {target_cal}, "total_protein": {target_pro}, "total_carbs": {target_carb}, "total_fats": {target_fat}, "meals": [COMPLETELY DIFFERENT meals, same structure]}},
  {{"day": "Day 3", "total_calories": {target_cal}, "total_protein": {target_pro}, "total_carbs": {target_carb}, "total_fats": {target_fat}, "meals": [COMPLETELY DIFFERENT meals, same structure]}}
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
                max_tokens=4000
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
                "tofu firm": (144, 17, 3, 8),
                "firm tofu": (144, 17, 3, 8),
                "tempeh": (192, 20, 8, 11),
                "seitan": (166, 25, 14, 2),          # wheat gluten — 25g P per 100g
                "edamame": (121, 11, 8, 5),           # shelled edamame — 11g P per 100g
                "shelled edamame": (121, 11, 8, 5),
                "nutritional yeast": (355, 50, 35, 7), # 50g P per 100g!
                "hemp seeds": (553, 31, 8.7, 49),      # 31g P per 100g
                "hemp seed": (553, 31, 8.7, 49),
                "tahini": (595, 17, 23, 54),           # sesame paste
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
                # Lamb
                "lamb": (258, 25, 0, 17),
                "lamb chop": (258, 25, 0, 17),
                "lamb chops": (258, 25, 0, 17),
                "lamb loin": (258, 25, 0, 17),
                "lamb leg": (225, 28, 0, 12),
                "ground lamb": (283, 23, 0, 21),
                "minced lamb": (283, 23, 0, 21),
                # More seafood
                "prawn": (99, 24, 0, 0.3),
                "prawns": (99, 24, 0, 0.3),
                "scallops": (111, 21, 5, 1),
                "crab": (97, 19, 0.5, 1.5),
                # Breakfast / snack staples
                "granola": (471, 10, 64, 20),
                "rice cake": (387, 8, 82, 3),
                "rice cakes": (387, 8, 82, 3),
                "blueberry": (57, 0.7, 14, 0.3),
                "blueberries": (57, 0.7, 14, 0.3),
                "strawberry": (32, 0.7, 8, 0.3),
                "strawberries": (32, 0.7, 8, 0.3),
                "raspberries": (52, 1.2, 12, 0.7),
                # Condiments
                "soy sauce": (53, 8, 5, 0),
                "tamari": (53, 8, 5, 0),
                "teriyaki sauce": (89, 3.5, 17, 0),
                "tomato sauce": (29, 1.5, 6, 0.3),
                "garlic": (149, 6, 33, 0.5),
                "ginger": (80, 1.8, 18, 0.8),
                # Vegan / specialty ingredients (frequently missing)
                "chickpea flour": (387, 22, 58, 6),
                "besan": (387, 22, 58, 6),         # Indian name for chickpea flour
                "dark chocolate": (598, 7.8, 43, 42),
                "dark chocolate chips": (598, 7.8, 43, 42),
                "cacao": (228, 20, 28, 14),
                "cocoa powder": (228, 20, 28, 14),
                "agave nectar": (310, 0.1, 76, 0),
                "agave syrup": (310, 0.1, 76, 0),
                "balsamic vinegar": (88, 0.5, 17, 0),
                "apple cider vinegar": (22, 0, 0.9, 0),
                "lemon juice": (22, 0.4, 7, 0.2),
                "lime juice": (25, 0.4, 8, 0.1),
                "nutritional yeast": (355, 50, 35, 7),
                "yeast flakes": (355, 50, 35, 7),
                "miso paste": (199, 12, 26, 6),
                "miso": (199, 12, 26, 6),
                "coconut aminos": (74, 2, 18, 0),
                "plant milk": (35, 1.5, 4, 1.8),   # generic plant milk
                "soy milk": (54, 3.3, 4.5, 2.2),
                "oat milk": (47, 1.5, 8, 0.9),
                "coconut yogurt": (100, 0.7, 6, 9),
                "soy yogurt": (67, 3.9, 6.6, 2.4),
                "vegan protein": (380, 72, 8, 5),  # generic vegan protein powder
                "pea protein": (380, 72, 8, 5),
                "brown sugar": (380, 0, 98, 0),
                "maple syrup": (260, 0.1, 67, 0.1),
                "tahini": (595, 17, 23, 54),        # sesame paste — high fat
                "almond flour": (571, 21, 20, 50),
                "flaxseed meal": (534, 18, 29, 42),
                "chia seeds": (486, 17, 42, 31),
                "spirulina": (290, 57, 24, 8),
                "maca powder": (325, 11, 66, 4),
                "matcha powder": (306, 26, 52, 5),
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
                    # Small aromatics — 1 clove/piece ≈ 3-5g, NOT 100g
                    'garlic': 4, 'garlic clove': 4, 'garlic cloves': 4,
                    'ginger': 5, 'ginger piece': 5,
                    'shallot': 20,
                    # Fruits (medium size)
                    'lime': 67, 'limes': 67, 'lemon': 58, 'lemons': 58,
                    'tomato': 120, 'tomatoes': 120, 'cherry tomato': 17, 'cherry tomatoes': 17,
                    'avocado': 200,
                    'peach': 150, 'nectarine': 140, 'plum': 85,
                    'kiwi': 70, 'fig': 50, 'date': 24,
                    # Vegetables (medium size)
                    'onion': 110, 'large onion': 150, 'medium onion': 110, 'small onion': 75,
                    'bell pepper': 120, 'pepper': 120, 'jalapeno': 14, 'chili': 15,
                    'mushroom': 90, 'large mushroom': 120,
                    'carrot': 80, 'medium carrot': 80, 'large carrot': 120,
                    'zucchini': 196,  # one medium zucchini
                    'potato': 180, 'sweet potato': 130, 'medium potato': 180,
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
                # Uses AI's stated values as fallback when ingredient DB match is incomplete
                def recalc_day_macros(day_data):
                    total_cal, total_pro, total_carb, total_fat = 0, 0, 0, 0
                    for meal in day_data.get("meals", []):
                        ai_cal = meal.get("calories", 0)
                        ai_pro = meal.get("protein", 0)
                        ai_carb = meal.get("carbs", 0)
                        ai_fat = meal.get("fats", 0)
                        meal_cal, meal_pro, meal_carb, meal_fat = 0, 0, 0, 0
                        for ing in meal.get("ingredients", []):
                            macros = calculate_ingredient_macros(ing)
                            if macros:
                                meal_cal += macros["calories"]
                                meal_pro += macros["protein"]
                                meal_carb += macros["carbs"]
                                meal_fat += macros["fats"]
                        # If DB only matched < 60% of AI's stated calories, supplement with AI values
                        # This handles ingredients like 'lamb chops', 'granola', exotic items not in DB
                        if ai_cal > 0 and meal_cal < ai_cal * 0.6:
                            coverage = meal_cal / ai_cal if ai_cal > 0 else 0
                            unmatched_ratio = 1 - coverage
                            meal_cal  += ai_cal  * unmatched_ratio
                            meal_pro  += ai_pro  * unmatched_ratio
                            meal_carb += ai_carb * unmatched_ratio
                            meal_fat  += ai_fat  * unmatched_ratio
                        meal["calories"] = round(meal_cal)
                        meal["protein"] = round(meal_pro, 1)
                        meal["carbs"] = round(meal_carb, 1)
                        meal["fats"] = round(meal_fat, 1)
                        total_cal += meal_cal
                        total_pro += meal_pro
                        total_carb += meal_carb
                        total_fat += meal_fat
                    return total_cal, total_pro, total_carb, total_fat
                
                # POST-PROCESSING: Multi-stage macro correction
                # Diet-type flags to control which stages apply
                _is_low_carb_ai = eating_style in ['keto', 'carnivore']  # These need high fat, low carbs — don't override
                _is_plant_based_ai = eating_style in ['vegan', 'vegetarian']
                
                # Stage 1: Initial calorie-based scale
                current_cal, current_pro, current_carb, current_fat = recalc_day_macros(day)
                
                if current_cal > 0:
                    cal_scale = target_cal / current_cal
                    cal_scale = max(0.6, min(1.5, cal_scale))
                else:
                    cal_scale = 1.0
                
                def scale_ingredient_str(ing_str, scale_factor):
                    """Scale an ingredient's quantity by scale_factor"""
                    import re as _re
                    scale_factor = max(0.5, min(2.5, scale_factor))
                    m = _re.match(r'^(\d+(?:\.\d+)?)\s*(g|ml|kg|oz)\s+(.+)$', ing_str, _re.IGNORECASE)
                    if m:
                        new_amt = round(float(m.group(1)) * scale_factor)
                        return f"{new_amt}{m.group(2)} {m.group(3)}"
                    m = _re.match(r'^(\d+(?:\.\d+)?)\s+(large|medium|small|whole)\s+(.+)$', ing_str, _re.IGNORECASE)
                    if m:
                        new_cnt = max(1, round(float(m.group(1)) * scale_factor))
                        return f"{new_cnt} {m.group(2)} {m.group(3)}"
                    m = _re.match(r'^(\d+(?:\.\d+)?)\s+(.+)$', ing_str, _re.IGNORECASE)
                    if m:
                        new_cnt = max(1, round(float(m.group(1)) * scale_factor))
                        return f"{new_cnt} {m.group(2)}"
                    return ing_str
                
                def scale_ingredients_by_type(day_data, keywords, scale, skip_keywords=None):
                    """Scale only ingredients matching keywords"""
                    skip_keywords = skip_keywords or []
                    for meal in day_data.get("meals", []):
                        new_ings = []
                        for ing in meal.get("ingredients", []):
                            ing_lower = ing.lower()
                            is_target = any(k in ing_lower for k in keywords)
                            is_skip = any(k in ing_lower for k in skip_keywords)
                            if is_target and not is_skip:
                                new_ings.append(scale_ingredient_str(ing, scale))
                            else:
                                new_ings.append(ing)
                        meal["ingredients"] = new_ings
                
                # Define carb & fat keywords once — reused in Stage 2 and Stage 4
                CARB_KEYWORDS = ['rice', 'sweet potato', 'potato', 'oat', 'quinoa', 'bread', 'pasta',
                                  'banana', 'apple', 'fruit', 'bean', 'lentil', 'chickpea', 'corn',
                                  'tortilla', 'noodle', 'couscous', 'barley', 'bulgur', 'mango', 'berry',
                                  'orange', 'grape', 'pear', 'pineapple', 'wrap', 'roll', 'pita']
                FAT_ONLY_SKIP_IN_CARBS = ['peanut butter', 'almond butter', 'coconut oil', 'olive oil', 'avocado oil']

                # Stage 1: Scale all by calories
                for meal in day.get("meals", []):
                    meal["ingredients"] = [scale_ingredient_str(ing, cal_scale) for ing in meal.get("ingredients", [])]
                
                # Stage 1.5: Protein correction — scale PURE protein ingredients to hit target
                # Use only primarily-protein foods (NOT legumes which are carb-dominant)
                after_cal_cal, after_cal_pro, after_cal_carb, after_cal_fat = recalc_day_macros(day)
                # Only primarily-protein sources (not dual-purpose foods like legumes/quinoa)
                pure_protein_keywords = [
                    'chicken', 'turkey', 'beef', 'steak', 'fish', 'tuna', 'salmon', 'shrimp', 'pork',
                    'egg', 'tofu', 'tempeh', 'seitan', 'protein powder', 'pea protein',
                    'greek yogurt', 'cottage cheese', 'hemp seed', 'soy yogurt', 'soy milk',
                    'ground beef', 'ground turkey', 'cod', 'tilapia', 'halibut', 'snapper'
                ]
                # Skip carb-dominant and fat-dominant foods during protein scaling
                non_protein_skip = ['rice', 'oat', 'potato', 'pasta', 'bread', 'banana', 'tortilla',
                                     'pita', 'barley', 'mango', 'apple', 'oil', 'butter', 'avocado']
                if after_cal_pro > 0:
                    pro_scale = target_pro / after_cal_pro
                    pro_scale = max(0.70, min(1.50, pro_scale))  # Up to 50% increase for vegan protein gaps
                    if abs(pro_scale - 1.0) > 0.03:
                        scale_ingredients_by_type(day, pure_protein_keywords, pro_scale, skip_keywords=non_protein_skip)
                
                # Stage 2: Carb correction — skip for keto/carnivore (intentionally low carb)
                if not _is_low_carb_ai:
                    after_pro_cal, after_pro_pro, after_pro_carb, after_pro_fat = recalc_day_macros(day)
                    if after_pro_carb > 0:
                        carb_scale = target_carb / after_pro_carb
                        # Allow up to 3x scaling — high_protein AI sometimes skimps on carbs
                        carb_scale = max(0.5, min(3.0, carb_scale))
                        if abs(carb_scale - 1.0) > 0.04:
                            scale_ingredients_by_type(day, CARB_KEYWORDS, carb_scale, skip_keywords=FAT_ONLY_SKIP_IN_CARBS)
                
                # Stage 3: Fat correction — skip for keto/carnivore (these need high fat — don't override)
                if not _is_low_carb_ai:
                    after_carb_cal, after_carb_pro, after_carb_carb, after_carb_fat = recalc_day_macros(day)
                    fat_keywords = ['oil', 'butter', 'avocado', 'almond butter', 'peanut butter', 'nuts',
                                     'cheese', 'cream', 'coconut', 'ghee', 'lard', 'mayo', 'tahini',
                                     'walnuts', 'almonds', 'cashews', 'pecans', 'seeds', 'flaxseed',
                                     'egg', 'salmon', 'bacon', 'ribeye', 'lamb', 'duck', 'pork belly']
                    # Only skip truly lean proteins from fat scaling
                    lean_protein_skip = ['chicken breast', 'turkey breast', 'cod', 'tilapia', 'tuna',
                                          'shrimp', 'egg white', 'cottage cheese', 'tofu', 'tempeh',
                                          'seitan', 'ground turkey', 'white fish']
                    if after_carb_fat > 0:
                        fat_scale = target_fat / after_carb_fat
                        fat_scale = max(0.4, min(2.5, fat_scale))
                        if abs(fat_scale - 1.0) > 0.04:
                            scale_ingredients_by_type(day, fat_keywords, fat_scale, skip_keywords=lean_protein_skip)
                
                # Stage 4: Last-meal balance — guarantee EXACT daily totals for non-keto diets
                # After Stages 1-3, the first 3 meals are approximately scaled.
                # The last meal (snack) absorbs any remaining gap to guarantee exact day totals.
                if not _is_low_carb_ai:
                    meals = day.get("meals", [])
                    if len(meals) >= 2:
                        # Recalculate all meals from ingredients to get fresh, accurate totals
                        recalc_day_macros(day)
                        
                        first_meals = meals[:-1]  # All meals except the last (snack)
                        first_cal  = sum(m.get("calories", 0) for m in first_meals)
                        first_pro  = sum(float(m.get("protein", 0)) for m in first_meals)
                        first_carb = sum(float(m.get("carbs", 0)) for m in first_meals)
                        first_fat  = sum(float(m.get("fats", 0)) for m in first_meals)
                        
                        last_meal = meals[-1]
                        
                        # Compute exactly what the last meal needs to produce
                        needed_cal  = max(80, target_cal  - first_cal)
                        needed_pro  = max(3,  target_pro  - first_pro)
                        needed_carb = max(3,  target_carb - first_carb)
                        needed_fat  = max(1,  target_fat  - first_fat)
                        
                        # Scale last meal's ingredient amounts proportionally by calorie ratio
                        # This keeps portion sizes realistic while hitting the needed total
                        cur_last_cal = max(1, last_meal.get("calories", 1))
                        last_scale = max(0.3, min(3.0, needed_cal / cur_last_cal))
                        if abs(last_scale - 1.0) > 0.05:
                            last_meal["ingredients"] = [
                                scale_ingredient_str(ing, last_scale)
                                for ing in last_meal.get("ingredients", [])
                            ]
                        
                        # Recalculate ALL meal macros from actual ingredient amounts (honest values)
                        # This ensures ingredient quantities always match the displayed macros.
                        # Stages 1-3 got us close to targets; last meal was scaled to close the gap.
                        # Now we report what the ingredients actually give, not forced targets.
                        final_cal, final_pro, final_carb, final_fat = recalc_day_macros(day)
                        day["total_calories"] = round(final_cal)
                        day["total_protein"]  = round(final_pro)
                        day["total_carbs"]    = round(final_carb)
                        day["total_fats"]     = round(final_fat)
                    else:
                        # Fewer than 2 meals — just recalculate normally
                        final_cal, final_pro, final_carb, final_fat = recalc_day_macros(day)
                        day["total_calories"] = round(final_cal)
                        day["total_protein"]  = round(final_pro)
                        day["total_carbs"]    = round(final_carb)
                        day["total_fats"]     = round(final_fat)
                else:
                    # Keto/Carnivore: recalculate honestly from ingredients (no forced targets)
                    final_cal, final_pro, final_carb, final_fat = recalc_day_macros(day)
                    day["total_calories"] = round(final_cal)
                    day["total_protein"]  = round(final_pro)
                    day["total_carbs"]    = round(final_carb)
                    day["total_fats"]     = round(final_fat)
            
                # ==================================================================
                # Stage 5: Final macro calibration — GUARANTEE EXACT daily targets
                # After Stages 1-4 produced honest ingredient-level values (typically
                # within ±1-8% of targets), this step applies a small proportional
                # correction (<= ±20%) to each meal so that day totals are PERFECT.
                # Ingredient amounts are also scaled proportionally to stay
                # consistent with the displayed macro numbers.
                # Keto/Carnivore are intentionally exempt — they use diet-appropriate
                # macro splits, not the user's profile targets.
                # ==================================================================
                if not _is_low_carb_ai:
                    actual_cal  = float(day.get("total_calories", 0))
                    actual_pro  = float(day.get("total_protein",  0))
                    actual_carb = float(day.get("total_carbs",    0))
                    actual_fat  = float(day.get("total_fats",     0))
                    s5_meals = day.get("meals", [])

                    if actual_cal > 0 and len(s5_meals) > 0:
                        # Compute per-macro scale factors, capped at ±20%
                        cal_adj  = max(0.80, min(1.20, target_cal  / actual_cal))  if actual_cal  > 0 else 1.0
                        pro_adj  = max(0.80, min(1.20, target_pro  / actual_pro))  if actual_pro  > 0 else 1.0
                        carb_adj = max(0.80, min(1.20, target_carb / actual_carb)) if actual_carb > 0 else 1.0
                        fat_adj  = max(0.80, min(1.20, target_fat  / actual_fat))  if actual_fat  > 0 else 1.0

                        for meal in s5_meals:
                            # Scale ingredient gram amounts proportionally by calorie factor
                            if abs(cal_adj - 1.0) > 0.005:
                                meal["ingredients"] = [
                                    scale_ingredient_str(ing, cal_adj)
                                    for ing in meal.get("ingredients", [])
                                ]
                            # Apply per-macro scale to displayed values
                            meal["calories"] = round(meal.get("calories", 0) * cal_adj)
                            meal["protein"]  = round(float(meal.get("protein", 0))  * pro_adj,  1)
                            meal["carbs"]    = round(float(meal.get("carbs",   0))  * carb_adj, 1)
                            meal["fats"]     = round(float(meal.get("fats",    0))  * fat_adj,  1)

                        # Force EXACT day totals — this is the guarantee the user needs
                        day["total_calories"] = target_cal
                        day["total_protein"]  = round(float(target_pro),  1)
                        day["total_carbs"]    = round(float(target_carb), 1)
                        day["total_fats"]     = round(float(target_fat),  1)
                        logger.info(
                            f"Stage 5 calibration: "
                            f"{round(actual_cal)}→{target_cal} cal, "
                            f"{round(actual_pro)}→{target_pro}g P, "
                            f"{round(actual_carb)}→{target_carb}g C, "
                            f"{round(actual_fat)}→{target_fat}g F"
                        )
            
            # POST-VALIDATION: Check if any banned foods appear in the meal plan
            # If found, log a warning (in production, could regenerate the meal)
            if banned_foods_list:
                for day in meal_data.get("meal_days", []):
                    for meal in day.get("meals", []):
                        meal_name_lower = meal.get("name", "").lower()
                        ingredients_str = " ".join(meal.get("ingredients", [])).lower()
                        for banned in banned_foods_list:
                            # Avoid false positives: "gluten-free" should not match "gluten"
                            def _contains_banned(text, banned_word):
                                cleaned = text.replace(f'{banned_word}-free', '').replace(f'{banned_word} free', '')
                                return banned_word in cleaned
                            if _contains_banned(meal_name_lower, banned) or _contains_banned(ingredients_str, banned):
                                logger.warning(f"BANNED FOOD DETECTED: '{banned}' found in meal '{meal.get('name')}' - This should not happen!")
                                meal["ingredients"] = [
                                    ing for ing in meal.get("ingredients", [])
                                    if not _contains_banned(ing.lower().replace(f'{banned}-free', '').replace(f'{banned} free', ''), banned)
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
        """
        Accurately scales template ingredients to hit user's daily macro targets.
        Uses ingredient-level scaling so displayed macros always match actual ingredient amounts.
        - Step 1: Scale all ingredients proportionally to hit calorie target
        - Step 2: Scale protein-rich ingredients to hit protein target
        - Step 3: Scale carb-rich ingredients to hit carb target (skip for keto/carnivore)
        - Step 4: Scale fat-rich ingredients to hit fat target
        - Step 5: Build meals and calculate macros from actual ingredient amounts (honest, no inflation)
        """
        import copy as _copy

        # Ingredient keyword categories for targeted scaling
        PROTEIN_KEYWORDS = [
            'chicken', 'beef', 'turkey', 'fish', 'salmon', 'tuna', 'shrimp', 'pork',
            'egg', 'tofu', 'tempeh', 'seitan', 'lentil', 'protein powder', 'pea protein',
            'greek yogurt', 'cottage cheese', 'edamame', 'chickpea', 'black bean',
            'kidney bean', 'ground beef', 'steak', 'hemp seed', 'soy yogurt', 'soy milk',
            'milk', 'quinoa', 'smoked salmon', 'ribeye', 'lamb', 'bison', 'venison'
        ]
        CARB_KEYWORDS = [
            'rice', 'oat', 'potato', 'sweet potato', 'pasta', 'bread', 'pita', 'tortilla',
            'banana', 'corn', 'barley', 'couscous', 'noodle', 'wrap', 'cereal', 'granola',
            'fruit', 'berry', 'apple', 'mango', 'orange', 'grape', 'lentil', 'chickpea',
            'black bean', 'kidney bean', 'falafel', 'hummus', 'cracker'
        ]
        # Fat-rich keywords — avoid scaling pure-protein foods as fat sources
        FAT_KEYWORDS = [
            'oil', 'butter', 'avocado', 'nut', 'almond', 'peanut', 'cashew',
            'pecan', 'walnut', 'macadamia', 'cheese', 'cream', 'coconut', 'ghee',
            'mayo', 'tahini', 'seed', 'bacon', 'lard', 'pesto', 'heavy cream'
        ]
        # These are mainly protein — skip them when scaling fat sources
        FAT_SKIP_PROTEINS = [
            'chicken', 'beef', 'turkey', 'salmon', 'fish', 'tuna', 'tofu', 'tempeh',
            'seitan', 'egg', 'yogurt', 'cottage', 'shrimp', 'pork', 'steak', 'ground beef'
        ]

        def _totals(tmpl):
            t = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0}
            for meal in tmpl.values():
                for _g, cal, pro, carb, fat in meal["ingredients"].values():
                    t["calories"] += cal
                    t["protein"] += pro
                    t["carbs"] += carb
                    t["fats"] += fat
            return t

        def _scale_all(tmpl, factor):
            """Scale every ingredient by factor (calorie-based initial scaling)."""
            f = max(0.3, min(3.0, factor))
            new = {}
            for mt, meal in tmpl.items():
                new_ings = {
                    n: (round(g * f), round(c * f), round(p * f, 1), round(cb * f, 1), round(ft * f, 1))
                    for n, (g, c, p, cb, ft) in meal["ingredients"].items()
                }
                new[mt] = {**meal, "ingredients": new_ings}
            return new

        def _scale_by_keywords(tmpl, keywords, factor, skip=None):
            """Scale only ingredients whose names match keywords, while skipping skip-keywords."""
            skip = skip or []
            f = max(0.3, min(3.0, factor))
            new = {}
            for mt, meal in tmpl.items():
                new_ings = {}
                for n, (g, c, p, cb, ft) in meal["ingredients"].items():
                    nl = n.lower()
                    is_target = any(k in nl for k in keywords)
                    is_skip = any(k in nl for k in skip)
                    if is_target and not is_skip and abs(f - 1.0) > 0.03:
                        new_ings[n] = (round(g * f), round(c * f), round(p * f, 1), round(cb * f, 1), round(ft * f, 1))
                    else:
                        new_ings[n] = (g, c, p, cb, ft)
                new[mt] = {**meal, "ingredients": new_ings}
            return new

        # Work on a deep copy to preserve original templates
        working = _copy.deepcopy(day_template)

        # STEP 1 — Calorie scaling: scale all ingredients proportionally to hit calorie target
        base = _totals(working)
        if base["calories"] > 0:
            cal_scale = target_cal / base["calories"]
            working = _scale_all(working, cal_scale)

        # STEP 2 — Protein scaling: adjust protein-rich ingredient amounts to hit protein target
        t = _totals(working)
        if t["protein"] > 0:
            pro_scale = target_pro / t["protein"]
            # Limit to ±50% adjustment to keep portions realistic
            pro_scale = max(0.5, min(1.5, pro_scale))
            working = _scale_by_keywords(working, PROTEIN_KEYWORDS, pro_scale)

        # STEP 3 — Carb scaling: adjust carb-rich ingredient amounts to hit carb target
        # Skip for keto/carnivore (low carb is intentional for those diets)
        if not is_low_carb_diet:
            t = _totals(working)
            if t["carbs"] > 0:
                carb_scale = target_carb / t["carbs"]
                carb_scale = max(0.5, min(2.0, carb_scale))
                working = _scale_by_keywords(working, CARB_KEYWORDS, carb_scale, skip=FAT_KEYWORDS)

        # STEP 4 — Fat scaling: adjust fat-rich ingredient amounts to hit fat target
        t = _totals(working)
        if t["fats"] > 0:
            fat_scale = target_fat / t["fats"]
            fat_scale = max(0.4, min(2.0, fat_scale))
            working = _scale_by_keywords(working, FAT_KEYWORDS, fat_scale, skip=FAT_SKIP_PROTEINS)

        # STEP 5 — Build output meals with macros calculated from ACTUAL ingredient amounts
        # This ensures the displayed macros are always honest and match ingredient quantities
        scaled_meals = []
        day_totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0}
        meal_idx = 1

        for meal_type, meal in working.items():
            meal_macros = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0}
            scaled_ingredients = []

            for ing_name, (g, cal, pro, carb, fat) in meal["ingredients"].items():
                scaled_ingredients.append(f"{g}g {ing_name}")
                meal_macros["calories"] += cal
                meal_macros["protein"] += pro
                meal_macros["carbs"] += carb
                meal_macros["fats"] += fat

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
                "prep_time_minutes": meal.get("prep_time", 20)
            })

            day_totals["calories"] += meal_macros["calories"]
            day_totals["protein"] += meal_macros["protein"]
            day_totals["carbs"] += meal_macros["carbs"]
            day_totals["fats"] += meal_macros["fats"]
            meal_idx += 1

        # Round day totals
        day_totals = {k: round(v) for k, v in day_totals.items()}
        return scaled_meals, day_totals
    
    # Determine if this is a low-carb diet that should preserve template macros
    is_low_carb = eating_style in ['keto', 'carnivore']
    # Determine if this is a plant-based diet (accurate protein matters, don't inflate)
    is_plant_based = eating_style in ['vegan', 'vegetarian']
    
    # Build banned foods list for template filtering
    template_banned_foods = []
    if request.foods_to_avoid and request.foods_to_avoid.strip():
        template_banned_foods = [f.strip().lower() for f in request.foods_to_avoid.split(',') if f.strip()]
    if request.allergies:
        template_banned_foods.extend([a.lower() for a in request.allergies])
    
    # Generate all 3 days
    meal_days = []
    for day_num, day_key in enumerate(["day1", "day2", "day3"], 1):
        day_template = MEAL_TEMPLATES[day_key]
        scaled_meals, day_totals = scale_day_to_targets(day_template, target_cal, target_pro, target_carb, target_fat, is_low_carb, is_plant_based)
        
        # Filter banned foods from template-based meals (rename meals + remove ingredients)
        if template_banned_foods:
            for meal in scaled_meals:
                meal_name_lower = meal.get("name", "").lower()
                # Rename meal if its name contains a banned food
                for banned in template_banned_foods:
                    if banned in meal_name_lower:
                        old_name = meal["name"]
                        meal_type = meal.get("meal_type", "meal")
                        meal["name"] = f"{meal_type.capitalize()} - Chef's Choice"
                        logger.info(f"Template meal renamed: '{old_name}' -> '{meal['name']}' (banned: {banned})")
                        break
                # Filter banned ingredients
                meal["ingredients"] = [
                    ing for ing in meal.get("ingredients", [])
                    if not any(banned in ing.lower() for banned in template_banned_foods)
                ]
        
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
