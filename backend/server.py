from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import logging
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Any, Literal
import uuid
from datetime import datetime, date, timedelta
import openai
import stripe
import base64
import json
import httpx
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from passlib.context import CryptContext
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'interfitai')]

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

# Admin emails - these users get free full access (comma-separated, from environment)
def is_admin(email: str) -> bool:
    """Check if an email is in the admin allowlist (ADMIN_EMAILS env var)."""
    env_admins = os.getenv("ADMIN_EMAILS", "")
    all_admins = {e.strip().lower() for e in env_admins.split(",") if e.strip()}
    return bool(email) and email.strip().lower() in all_admins

# Free access emails - can be granted by admin
FREE_ACCESS_EMAILS = []

# Exercise demonstration - using ExerciseDB RapidAPI for computer-generated animated GIFs
EXERCISEDB_API_KEY = os.getenv("EXERCISEDB_API_KEY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
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
    "decline dumbbell press": "0301",  # dumbbell decline bench press
    "dumbbell fly": "0308",
    "flat dumbbell fly": "0308",
    "incline dumbbell fly": "0316",
    "decline dumbbell fly": "0302",
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
    "wide push up": "1311",
    "diamond push up": "0283",
    "decline push up": "0279",       # FIXED: 0279 = decline push-up
    "decline push-up": "0279",
    "incline push up": "0493",
    "knee push up": "0670",
    "chest dip": "0251",
    "parallel bar dip": "0251",
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
    "close grip lat pulldown": "0245",  # cable underhand pulldown
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
    "sumo deadlift": "0117",
    
    # Shoulder exercises - OVERHEAD PRESS is standing barbell military press
    "overhead press": "1457",              # barbell standing wide military press (standard grip)
    "standing overhead press": "1457",
    "barbell overhead press": "1457",
    "barbell shoulder press": "1457",
    "military press": "1457",
    "standing military press": "1457",
    "shoulder press": "1457",
    "ohp": "1457",                         # common abbreviation
    "barbell military press": "1457",
    "wide grip overhead press": "1457",    # barbell standing wide military press
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
    "arnold press": "2137",
    "dumbbell arnold press": "2137",
    "lateral raise": "0334",
    "dumbbell lateral raise": "0334",
    "side lateral raise": "0334",
    "side raise": "0334",
    "front raise": "0310",
    "dumbbell front raise": "0310",
    "rear delt fly": "0620",          # reverse pec deck (machine rear delt fly)
    "rear delt machine fly": "0620",  # reverse pec deck (the actual machine rear delt fly)
    "reverse fly": "0620",            # machine version as default
    "rear delt": "0620",              # machine version as default
    "face pull": "0233",  # cable standing rear delt row (with rope) - the face pull movement
    "cable face pull": "0233",
    "cable face pulls": "0233",
    "face pulls": "0233",
    "rope face pull": "0233",
    "upright row": "0121",
    "barbell upright row": "0121",
    "shrug": "0095",
    "barbell shrug": "0095",
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
    "preacher curl": "0070",  # barbell preacher curl
    "concentration curl": "0297",
    "incline dumbbell curl": "0318",  # FIXED: dumbbell incline curl
    "incline curl": "0318",            # ADDED
    "cable curl": "0868",             # FIXED: was 0163 (broken). 0868 = cable curl
    "cable bicep curl": "0868",       # FIXED
    
    # Arm exercises - Triceps
    "tricep pushdown": "0241",  # cable triceps pushdown (v-bar)
    "cable pushdown": "0201",  # cable pushdown
    "tricep rope pushdown": "0200",  # cable pushdown (with rope attachment)
    "rope pushdown": "0200",
    "cable tricep pushdown": "0241",
    "triceps pushdown": "0241",
    "tricep extension": "0352",
    "overhead tricep extension": "0092",   # barbell seated overhead tricep extension
    "dumbbell tricep extension": "0352",
    "overhead cable extension": "0194",          # ADDED: cable overhead triceps extension (rope)
    "overhead cable tricep extension": "0194",   # ADDED
    "skull crusher": "0060",              # barbell lying triceps extension skull crusher (not 0055 which is close-grip bench)
    "lying tricep extension": "0060",
    "barbell skull crusher": "0060",
    "tricep dip": "0814",
    "triceps dip": "0814",
    "dips": "0814",
    "weighted dip": "1755",  # weighted tricep dips
    "weighted dips": "1755",
    "bench dip": "0129",
    "bench dips": "0129",
    "tricep kickback": "0333",
    "dumbbell kickback": "0333",
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
    "glute kickback": "0228",          # cable standing hip extension – glutes (0860 was triceps)
    "cable kickback": "0228",          # cable standing hip extension – glutes
    "cable glute kickback": "0228",    # cable standing hip extension – glutes
    "good morning": "0044",            # FIXED: was 0440 (broken). 0044 = barbell good morning
    "barbell good morning": "0044",    # FIXED
    "pistol squat": "0544",            # ADDED: kettlebell pistol squat
    "pistol squat (assisted)": "0544", # ADDED
    "single leg romanian deadlift": "1757",  # ADDED: dumbbell single leg deadlift
    "single-leg romanian deadlift": "1757",  # ADDED
    
    # Core exercises
    "plank": "2135",  # weighted front plank (shows plank position)
    "front plank": "2135",
    "forearm plank": "2135",
    "standard plank": "2135",
    "plank hold": "2135",
    "side plank": "3544",                 # bodyweight incline side plank (not 1775 which is side plank hip adduction)
    "side plank hip": "1775",
    "crunch": "0274",
    "ab crunch": "0274",
    "bicycle crunch": "0972",             # band bicycle crunch
    "reverse crunch": "0872",             # reverse crunch
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
    "ab wheel rollout": "0857",        # FIXED: wheel rollout (correct exercise)
    "ab rollout": "0857",              # FIXED: was 0001 (sit-up)
    "cable crunch": "0175",
    "dead bug": "0276",                # FIXED: was 1474 (broken). 0276 = dead bug
    "bird dog": "0276",                # dead bug (same stability pattern)
    "flutter kick": "0459",
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
    "clean and press": "0028",
    "clean and jerk": "0648",    # power clean (barbell clean and jerk)
    "snatch": "0067",             # barbell one arm snatch
    "thruster": "2143",
    "thrusters": "2143",
    "wall ball": "2399",
    "wall balls": "2399",
    
    # Cardio/HIIT exercises
    "jump rope": "2612",
    "jumping rope": "2612",
    "skipping rope": "2612",
    "double unders": "2612",          # jump rope (closest equivalent)
    "battle ropes": "0128",  # battling ropes
    "battle rope": "0128",
    "battling ropes": "0128",
    "treadmill": "3666",  # walking on incline treadmill
    "treadmill run": "3666",
    "treadmill sprint": "3666",
    "treadmill sprints": "3666",
    "running": "3666",
    "assault bike": "2331",            # cycle cross trainer
    "assault bike intervals": "2331",  # cycle cross trainer
    "cycle cross trainer": "2331",     # ExerciseDB API name for assault bike
    # rowing machine — no match in ExerciseDB; intentionally unmapped so UI shows exercise without GIF
    
    # Machine exercises
    "pec deck": "0613",
    "machine fly": "0613",
    "shoulder press machine": "0587",  # lever military press (leverage machine, seated)
    "machine shoulder press": "0587",
    "cable shoulder press": "0587",
    "lever shoulder press": "0587",
    "cable lateral raise": "0178",     # FIXED: was 0175 (cable kneeling crunch). 0178 = cable lateral raise
    "machine lateral raise": "0584",   # ADDED: lever lateral raise
    "machine lateral raises": "0584",  # ADDED
    "farmer's carry": "2133",          # ADDED: farmers walk
    "farmers carry": "2133",           # ADDED
    "farmer's walk": "2133",           # ADDED
    "farmers walk": "2133",            # ADDED
    "suitcase carry": "2133",          # ADDED: farmers walk as closest

    # ── Additional PATTERNS coverage ────────────────────────────────
    # Bodyweight / Calisthenics
    "archer push up": "3294",
    # "pike push up" intentionally omitted — no accurate GIF in ExerciseDB
    "australian pull up": "0499",      # alias kept for legacy programs; not used in new gen
    "inverted row": "0499",
    "nordic hamstring curl": "1766",
    "sissy squat": "1489",             # sissy squat
    "plyo push up": "1306",
    "bodyweight squat": "0413",        # dumbbell squat (same pattern)
    "bodyweight calf raise": "1373",
    "single leg calf raise": "1373",
    "lateral lunge": "1410",           # barbell lateral lunge
    "swiss ball leg curl": "2403",
    "supinated row": "0499",
    "handstand push up (wall assisted)": "0473",  # hanging pike

    # Cable exercises
    "cable pull through": "0196",
    "cable hip extension": "0196",
    "cable rear delt fly": "0203",
    "cable leg curl": "3235",           # cable assisted inverse leg curl
    "high to low cable fly": "0225",    # cable standing cross-over high reverse fly
    "single arm cable row": "0189",
    "single arm lat pulldown": "0007",  # alternate lateral pulldown
    "ab pulldown": "0175",

    # Machine exercises
    "machine row": "1350",
    "machine preacher curl": "0579",
    "machine incline press": "0583",
    "face pull machine": "0203",
    "reverse pec deck": "0620",
    "assisted pull up machine": "0017",

    # Dumbbell exercises
    "dumbbell incline press": "0314",
    "dumbbell romanian deadlift": "1459",
    "dumbbell front squat": "0413",     # dumbbell squat (same movement)
    "dumbbell rear delt fly": "0378",   # dumbbell rear fly
    "dumbbell calf raise": "1373",
    "dumbbell leg curl": "0331",        # dumbbell lying leg curl
    "dumbbell pullover": "0375",        # dumbbell pullover
    "overhead dumbbell extension": "0340",  # dumbbell lying extension
    "chest supported row": "0327",
    "bent over rear delt raise": "0329",   # dumbbell lying rear delt raise

    # Barbell exercises
    "incline barbell press": "0047",
    "barbell bulgarian split squat": "0099",  # barbell single leg split squat (5331 doesn't exist in ExerciseDB)
    "barbell calf raise": "1372",
    "pause squat": "0043",
    "pendlay row": "3017",
    "push press": "1700",              # dumbbell push press
    "trap bar farmer's carry": "2133",

    # Kettlebell exercises
    "kettlebell floor press": "1298",  # kettlebell one arm floor press
    "kettlebell press": "0541",
    "kettlebell row": "0545",
    "kettlebell lunge": "0542",
    "kettlebell step up": "0546",
    "kettlebell romanian deadlift": "1455",
    "kettlebell farmer's carry": "2133",
    "kettlebell farmers carry": "2133",
    "kettlebell overhead carry": "2133",

    # Stability / Core
    "pallof press": "0979",    # band horizontal pallof press
    "plank walk": "3239",      # kneeling plank tap shoulder

    # Conditioning
    "medicine ball slam": "1354",
    "burpee intervals": "1160",
    "rowing machine intervals": "1161",
    "kettlebell swing intervals": "0549",
    "incline walking intervals": "3666",  # treadmill incline walk
    "ski erg intervals": "2142",          # ski ergometer
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
    if is_admin(email):
        return {"has_access": True, "reason": "admin"}
    
    # Check free access list
    free_access = await db.free_access.find_one({"email": email.lower()})
    if free_access:
        return {"has_access": True, "reason": "free_access_granted"}
    
    # Check subscription status
    subscription_status = profile.get("subscription_status", "free")
    if subscription_status in ["trial", "monthly", "quarterly", "yearly", "active", "free_access", "complimentary"]:
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
    has_password: bool = False
    unit_preference: Literal["kg", "lbs"] = "kg"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserProfileCreate(BaseModel):
    name: str = ""
    email: str = ""
    password: str = ""
    weight: float
    height: float
    age: int
    gender: str = "male"
    activity_level: str = "moderate"
    goal: str = "maintenance"

class LoginRequest(BaseModel):
    email: str
    password: str

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
    unit_preference: Optional[Literal["kg", "lbs"]] = None

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
    weekly_progression: Optional[List[dict]] = None
    preferred_start_day: str = "Monday"
    current_week_override: Optional[int] = None
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
    preferred_start_day: str = "Monday"          # Day of week to anchor the schedule

    # Accept legacy / alternate field names from frontend
    split_type: Optional[str] = None        # alias for preferred_split
    style: Optional[str] = None             # alias for training_style
    experience_level: Optional[str] = None  # alias for fitness_level
    limitations: Optional[List[str]] = None # alias for injuries

    @model_validator(mode="after")
    def _apply_aliases(self) -> "WorkoutGenerateRequest":
        if self.split_type and self.preferred_split == "ai_choose":
            self.preferred_split = self.split_type
        if self.style and self.training_style == "weights":
            self.training_style = self.style
        if self.experience_level and self.fitness_level == "intermediate":
            self.fitness_level = self.experience_level
        if self.limitations and not self.injuries:
            self.injuries = self.limitations
        return self


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
            "bodyweight":["Pull-Up", "Chin-Up"],
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
            "bodyweight":["Prone Y Raise", "Superman Row"],
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
            "barbells":  ["Back Squat", "Front Squat", "Pause Squat", "Hack Squat"],
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
            "full_gym":  ["Barbell Hip Thrust", "Cable Glute Kickback", "Leg Press (feet high)"],
            "beginner_gym": ["Hip Thrust Machine", "Dumbbell Hip Thrust", "Cable Glute Kickback"],
            "barbells":  ["Barbell Hip Thrust", "Barbell Glute Bridge"],
            "dumbbells": ["Dumbbell Hip Thrust", "Single-Leg Glute Bridge"],
            "machines":  ["Hip Thrust Machine", "Cable Glute Kickback"],
            "bodyweight":["Hip Thrust", "Glute Bridge", "Single-Leg Glute Bridge"],
            "cables":    ["Cable Glute Kickback", "Cable Hip Extension"],
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
            "full_gym":  ["Rowing Machine Intervals", "Assault Bike Intervals", "Ski Erg Intervals"],
            "barbells":  ["Barbell Complex Intervals", "Thruster Intervals"],
            "dumbbells": ["Dumbbell Thruster Intervals", "Devil Press Intervals"],
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
        "full_body_heavy_b": {
            "label": "Full Body D",
            "focus": "Full Body – Posterior Chain & Overhead Emphasis",
            "slots": [
                ("hip_hinge",        "primary_compound",   "deadlift variation – posterior chain dominance"),
                ("vertical_push",    "primary_compound",   "overhead press – shoulder strength and stability"),
                ("vertical_pull",    "primary_compound",   "pull-up or pulldown – lat width and upper back"),
                ("lunge",            "secondary_compound",  "unilateral lower – single-leg strength and balance"),
                ("lateral_raise",    "accessory",           "medial delt isolation – shoulder width"),
                ("core_flexion",     "core",                "core flexion – direct ab work"),
            ],
            "optional_slots": [],
        },
        "full_body_moderate_b": {
            "label": "Full Body E",
            "focus": "Full Body – Volume & Isolation Emphasis",
            "slots": [
                ("squat",            "primary_compound",   "squat variation – quad and glute development"),
                ("horizontal_pull",  "primary_compound",   "row variation – mid-back thickness"),
                ("incline_push",     "secondary_compound",  "incline press – upper chest volume"),
                ("glute",            "accessory",           "hip thrust or bridge – glute isolation"),
                ("tricep_push",      "isolation",           "tricep isolation – lockout and arm mass"),
                ("core_stability",   "core",                "anti-rotation core – plank or Pallof variation"),
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
        "calisthenics_skill": {
            "label": "Calisthenics Skill",
            "focus": "Progressions, Holds & Skill Work",
            "slots": [
                ("horizontal_push",  "primary_compound",   "push-up progression – planche prep, deficit, or weighted"),
                ("vertical_pull",    "primary_compound",   "pull-up skill – weighted, archer, or one-arm progression"),
                ("core_stability",   "primary_compound",   "front lever, L-sit, or dragon flag progression – static strength"),
                ("squat",            "secondary_compound",  "pistol squat or shrimp squat progression – single-leg mastery"),
                ("horizontal_pull",  "accessory",           "row variation – slow eccentrics for pulling strength"),
            ],
            "optional_slots": [],
        },
        "calisthenics_conditioning": {
            "label": "Calisthenics Conditioning",
            "focus": "Muscular Endurance & Work Capacity",
            "slots": [
                ("horizontal_push",  "secondary_compound",  "push-up volume – high rep submaximal sets"),
                ("vertical_pull",    "secondary_compound",  "pull-up volume – submaximal rep accumulation"),
                ("lunge",            "secondary_compound",  "lunge variation – lower body endurance"),
                ("core_flexion",     "accessory",           "core endurance – time under tension and reps"),
                ("conditioning",     "conditioning",        "bodyweight circuit or EMOM – sustained work capacity"),
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
        "functional_power_endurance": {
            "label": "Functional C – Power & Endurance",
            "focus": "Explosive Power, Rotational Strength & Sustained Output",
            "slots": [
                ("explosive",        "primary_compound",   "plyometric power – box jump, broad jump, or med ball throw"),
                ("hip_hinge",        "primary_compound",   "hinge pattern – posterior chain power and strength"),
                ("carry",            "accessory",           "loaded carry – trunk integrity under fatigue"),
                ("horizontal_push",  "secondary_compound",  "push pattern – upper body pressing capacity"),
                ("core_flexion",     "core",                "rotational core – anti-rotation or chop pattern"),
                ("conditioning",     "conditioning",        "high-intensity intervals – sustain power output"),
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
        "bro_chest_shoulders": {
            "label": "Chest & Shoulders Day",
            "focus": "Chest, Shoulders & Triceps",
            "slots": [
                ("horizontal_push",  "primary_compound",   "flat pressing – chest mass and strength foundation"),
                ("incline_push",     "secondary_compound",  "incline angle – upper chest focus and fullness"),
                ("vertical_push",    "secondary_compound",  "overhead press – shoulder strength and mass"),
                ("lateral_raise",    "accessory",           "lateral raise – medial delt width and roundness"),
                ("tricep_push",      "isolation",           "tricep isolation – full elbow extension and lockout"),
            ],
            "optional_slots": [
                ("rear_delt",        "accessory",           "rear delt – shoulder health and balanced development"),
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
            4: ["full_body_heavy", "full_body_moderate", "full_body_light", "full_body_heavy_b"],
            5: ["full_body_heavy", "full_body_moderate", "full_body_light", "full_body_heavy_b", "full_body_moderate_b"],
            6: ["full_body_heavy", "full_body_moderate", "full_body_light", "full_body_heavy_b", "full_body_moderate_b", "full_body_light"],
        },
        "upper_lower": {
            2: ["upper_full", "lower_full"],
            3: ["upper_push_heavy", "lower_quad_focus", "upper_pull_heavy"],
            4: ["upper_push_heavy", "lower_quad_focus", "upper_pull_heavy", "lower_hip_focus"],
            5: ["upper_push_heavy", "lower_quad_focus", "upper_pull_heavy", "lower_hip_focus", "upper_full"],
            6: ["upper_push_heavy", "lower_quad_focus", "upper_pull_heavy", "lower_hip_focus", "upper_full", "lower_full"],
        },
        "push_pull_legs": {
            3: ["push_session", "pull_session", "legs_session"],
            4: ["push_session", "pull_session", "legs_session", "upper_full"],
            5: ["push_session", "pull_session", "legs_session", "upper_full", "lower_full"],
            6: ["push_session", "pull_session", "legs_session", "upper_push_volume", "upper_pull_volume", "lower_full"],
        },
        "bro_split": {
            3: ["bro_chest_shoulders", "bro_back", "bro_legs"],
            4: ["bro_chest", "bro_back", "bro_legs", "bro_shoulders"],
            5: ["bro_chest", "bro_back", "bro_shoulders", "bro_legs", "bro_arms"],
            6: ["bro_chest", "bro_back", "bro_shoulders", "bro_legs", "bro_arms", "bro_back"],
        },
        "athletic_split": {
            2: ["full_body_heavy", "athletic_conditioning"],
            3: ["full_body_heavy", "athletic_conditioning", "lower_full"],
            4: ["full_body_heavy", "athletic_conditioning", "upper_full", "lower_full"],
            5: ["full_body_heavy", "athletic_conditioning", "upper_full", "lower_full", "athletic_conditioning"],
            6: ["full_body_heavy", "athletic_conditioning", "upper_push_heavy", "lower_quad_focus", "athletic_conditioning", "lower_hip_focus"],
        },
        "functional_split": {
            2: ["functional_movement_quality", "functional_strength_capacity"],
            3: ["functional_movement_quality", "functional_strength_capacity", "functional_movement_quality"],
            4: ["functional_movement_quality", "functional_strength_capacity", "functional_power_endurance", "functional_movement_quality"],
            5: ["functional_movement_quality", "functional_strength_capacity", "functional_power_endurance", "functional_movement_quality", "functional_strength_capacity"],
            6: ["functional_movement_quality", "functional_strength_capacity", "functional_power_endurance", "functional_movement_quality", "functional_strength_capacity", "functional_power_endurance"],
        },
        "hybrid_split": {
            2: ["hybrid_strength_push", "hybrid_strength_lower"],
            3: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_power_conditioning"],
            4: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_strength_pull", "hybrid_power_conditioning"],
            5: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_strength_pull", "hybrid_power_conditioning", "hybrid_strength_lower"],
            6: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_strength_pull", "hybrid_power_conditioning", "hybrid_strength_push", "hybrid_strength_pull"],
        },
        "calisthenics_split": {
            2: ["calisthenics_upper", "calisthenics_lower"],
            3: ["calisthenics_upper", "calisthenics_lower", "calisthenics_upper"],
            4: ["calisthenics_upper", "calisthenics_lower", "calisthenics_skill", "calisthenics_conditioning"],
            5: ["calisthenics_upper", "calisthenics_lower", "calisthenics_skill", "calisthenics_upper", "calisthenics_conditioning"],
            6: ["calisthenics_upper", "calisthenics_lower", "calisthenics_skill", "calisthenics_upper", "calisthenics_lower", "calisthenics_conditioning"],
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
            "conditioning":       {"sets": 1, "reps": "10-15 min — steady pace",  "rest": 0,   "effort": "Zone 2 — low intensity only"},
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
            "conditioning":       {"sets": 1, "reps": "10-15 min — steady pace",  "rest": 0,   "effort": "Zone 2-3 — light cardio only"},
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
            "conditioning":       {"sets": 1, "reps": "10-20 min — 30s hard / 30s easy, repeat",  "rest": 0,   "effort": "High intensity — intervals or HIIT"},
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
            "conditioning":       {"sets": 1, "reps": "10-15 min — 40s work / 40s easy, repeat",  "rest": 0,   "effort": "Moderate-high — efficient cardio"},
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
            "conditioning":       {"sets": 1, "reps": "10-20 min — steady enjoyable pace",  "rest": 0,   "effort": "Moderate — enjoyable pace"},
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
            "conditioning":       {"sets": 1, "reps": "15-20 min — 30s sprint / 30s recovery, repeat",  "rest": 0,   "effort": "High intensity — sport-specific intervals"},
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
    # ── Injury synonym map ──────────────────────────────────────────────────
    # Maps free-text phrasings (lowercase substrings) → canonical key in
    # LIMITATION_EXCLUSIONS. Ordered longest-first to prevent shorter phrases
    # matching before more-specific ones.
    LIMITATION_SYNONYMS: dict = {
        # lower_back
        "herniated disc":       "lower_back",
        "herniated disk":       "lower_back",
        "slipped disc":         "lower_back",
        "disc herniation":      "lower_back",
        "disk herniation":      "lower_back",
        "sciatica":             "lower_back",
        "sciatic":              "lower_back",
        "lower back":           "lower_back",
        "lumbar":               "lower_back",
        "sacral":               "lower_back",
        "herniated":            "lower_back",
        "disc":                 "lower_back",
        "disk":                 "lower_back",
        "l4":                   "lower_back",
        "l5":                   "lower_back",
        "spondylosis":          "lower_back",
        "spondylolisthesis":    "lower_back",
        # knee
        "runner's knee":        "knee",
        "runners knee":         "knee",
        "runner knee":          "knee",
        "patellofemoral":       "knee",
        "chondromalacia":       "knee",
        "patellar":             "knee",
        "patella":              "knee",
        "meniscus":             "knee",
        "acl":                  "knee",
        "mcl":                  "knee",
        "pcl":                  "knee",
        "lcl":                  "knee",
        "knee pain":            "knee",
        "knee injury":          "knee",
        "knee replacement":     "knee",
        # shoulder
        "rotator cuff":         "shoulder",
        "frozen shoulder":      "shoulder",
        "ac joint":             "shoulder",
        "shoulder impingement": "shoulder",
        "shoulder bursitis":    "shoulder",
        "labral tear":          "shoulder",
        "labrum":               "shoulder",
        "labral":               "shoulder",
        "impingement":          "shoulder",
        "bursitis":             "shoulder",
        "rotator":              "shoulder",
        "shoulder pain":        "shoulder",
        "shoulder injury":      "shoulder",
        # elbow
        "tennis elbow":         "elbow",
        "golfer's elbow":       "elbow",
        "golfers elbow":        "elbow",
        "lateral epicondylitis":"elbow",
        "medial epicondylitis": "elbow",
        "epicondylitis":        "elbow",
        "elbow tendonitis":     "elbow",
        "elbow tendinitis":     "elbow",
        "elbow pain":           "elbow",
        "elbow injury":         "elbow",
        # wrist
        "carpal tunnel":        "wrist",
        "tfcc":                 "wrist",
        "wrist tendonitis":     "wrist",
        "wrist pain":           "wrist",
        "wrist injury":         "wrist",
        # ankle
        "plantar fasciitis":    "ankle",
        "plantar fascitis":     "ankle",
        "achilles tendon":      "ankle",
        "achilles":             "ankle",
        "plantar":              "ankle",
        "ankle sprain":         "ankle",
        "ankle pain":           "ankle",
        "ankle injury":         "ankle",
        # hip
        "hip flexor":           "hip",
        "femoroacetabular":     "hip",
        "fai":                  "hip",
        "hip impingement":      "hip",
        "groin strain":         "hip",
        "groin":                "hip",
        "psoas":                "hip",
        "hip pain":             "hip",
        "hip injury":           "hip",
        # neck
        "cervical":             "neck",
        "whiplash":             "neck",
        "neck pain":            "neck",
        "neck injury":          "neck",
    }

    LIMITATION_EXCLUSIONS = {
        "lower_back":    ["Conventional Deadlift", "Sumo Deadlift", "Good Morning", "Back Squat",
                          "T-Bar Row", "Barbell Row"],
        "knee":          ["Back Squat", "Hack Squat", "Goblet Squat", "Smith Machine Squat",
                          "Leg Press", "Leg Press (feet high)",
                          "Barbell Bulgarian Split Squat", "Dumbbell Bulgarian Split Squat",
                          "Bulgarian Split Squat", "Smith Machine Split Squat",
                          "Dumbbell Reverse Lunge", "Walking Lunge", "Reverse Lunge",
                          "Barbell Lunge", "Dumbbell Lunge", "Lateral Lunge",
                          "Kettlebell Lunge", "Band Lunge",
                          "Dumbbell Step-Up", "Step-Up",
                          "Jump Squat", "Running"],
        "shoulder":      ["Barbell Overhead Press", "Push Press", "Upright Row",
                          "Behind-the-Neck Press", "Barbell Bench Press"],
        "wrist":         ["Barbell Curl", "Barbell Overhead Press", "Push-Up", "Barbell Bench Press"],
        "elbow":         ["Skull Crusher", "Dip", "Barbell Curl"],
        "hip":           ["Barbell Hip Thrust", "Barbell Bulgarian Split Squat",
                          "Leg Press", "Leg Press (feet high)"],
        "ankle":         ["Calf Raise", "Calf Raise Machine", "Seated Calf Raise",
                          "Leg Press Calf Raise", "Bodyweight Calf Raise", "Single-Leg Calf Raise",
                          "Jump Squat", "Broad Jump"],
        "neck":          ["Barbell Back Squat", "Barbell Overhead Press"],
    }

    @classmethod
    def _normalize_limitations(cls, limitations: list) -> set:
        """Expand free-text limitation strings to canonical LIMITATION_EXCLUSIONS keys.
        Synonym map is checked first (handles 'sciatica', 'rotator cuff', etc.),
        then falls back to direct substring match against the 8 canonical keys."""
        canonical_keys: set = set()
        for lim in (limitations or []):
            lim_lower = lim.lower()
            # 1. Synonym map (longest phrases first to avoid false substring matches)
            for phrase, key in cls.LIMITATION_SYNONYMS.items():
                if phrase in lim_lower:
                    canonical_keys.add(key)
            # 2. Direct substring match against the 8 canonical keys
            normalised = lim_lower.replace(' ', '_').replace('-', '_')
            for excl_key in cls.LIMITATION_EXCLUSIONS:
                if excl_key in normalised:
                    canonical_keys.add(excl_key)
        return canonical_keys

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

    # ── Secondary focus synergy map ──────────────────────────────────────────
    # Per session type: which secondary focuses are synergistic (i.e. safe to
    # add as a finisher without conflicting with the primary session goal).
    # "any" means the session is generic enough to accept any secondary focus.
    # Unlisted session types also default to "any" (see get call below).
    SECONDARY_SYNERGY: dict = {
        # ── Bro split ────────────────────────────────────────────────────────
        "bro_chest":              ["core", "triceps", "shoulders", "arms"],
        "bro_back":               ["core", "biceps", "shoulders", "arms"],
        "bro_shoulders":          ["core", "chest", "triceps", "arms"],
        "bro_arms":               ["core", "shoulders"],
        "bro_legs":               ["core", "glutes", "calves", "hamstrings", "quads", "legs"],
        "bro_chest_shoulders":    ["core", "triceps", "arms"],
        # ── Push / Pull / Legs ───────────────────────────────────────────────
        "push_session":           ["core", "chest", "triceps", "shoulders", "arms"],
        "pull_session":           ["core", "back", "biceps", "shoulders", "arms"],
        "legs_session":           ["core", "glutes", "calves", "hamstrings", "quads", "legs"],
        "upper_push_volume":      ["core", "shoulders", "triceps", "chest", "arms"],
        "upper_pull_volume":      ["core", "back", "biceps", "shoulders", "arms"],
        # ── Upper / Lower ────────────────────────────────────────────────────
        "upper_full":             ["core", "chest", "back", "shoulders", "arms", "biceps", "triceps"],
        "upper_push_heavy":       ["core", "shoulders", "triceps", "chest", "arms"],
        "upper_pull_heavy":       ["core", "back", "biceps", "shoulders", "arms"],
        "lower_quad_focus":       ["core", "glutes", "calves", "hamstrings", "legs", "quads"],
        "lower_hip_focus":        ["core", "quads", "calves", "legs", "glutes"],
        "lower_full":             ["core", "glutes", "calves", "hamstrings", "quads", "legs"],
        # ── Full body ────────────────────────────────────────────────────────
        "full_body_heavy":        "any",
        "full_body_moderate":     "any",
        "full_body_light":        "any",
        "full_body_heavy_b":      "any",
        "full_body_moderate_b":   "any",
        # ── Athletic ─────────────────────────────────────────────────────────
        "athletic_conditioning":  "any",
        # ── Hybrid ───────────────────────────────────────────────────────────
        "hybrid_strength_push":   ["core", "shoulders", "triceps", "chest"],
        "hybrid_strength_lower":  ["core", "glutes", "calves", "hamstrings", "legs"],
        "hybrid_strength_pull":   ["core", "back", "biceps", "shoulders"],
        "hybrid_power_conditioning": "any",
        # ── Functional ───────────────────────────────────────────────────────
        "functional_movement_quality":  "any",
        "functional_strength_capacity": "any",
        "functional_power_endurance":   "any",
        # ── Calisthenics ─────────────────────────────────────────────────────
        "calisthenics_upper":     ["core", "shoulders", "chest", "back", "arms"],
        "calisthenics_lower":     ["core", "glutes", "calves", "legs"],
        "calisthenics_skill":     "any",
        "calisthenics_conditioning": "any",
    }

    # Primary focus → preferred split when AI is choosing (ai_choose mode only)
    # Keys match focus_area slugs; value is the preferred split_id.
    FOCUS_SPLIT_PREFERENCE: dict = {
        'chest':        'push_pull_legs',   # dedicated push day = more chest frequency
        'back':         'push_pull_legs',   # dedicated pull day = more back frequency
        'shoulders':    'push_pull_legs',   # push day + isolation session
        'arms':         'push_pull_legs',   # arms on push/pull days twice per rotation
        'legs':         'upper_lower',      # 2× lower per week = most leg volume
        'glutes':       'upper_lower',      # 2× lower per week = most glute frequency
        'hamstrings':   'upper_lower',      # lower day twice hits hamstrings optimally
        'quads':        'upper_lower',      # lower day twice hits quads optimally
        'calves':       'upper_lower',      # lower day twice = calf frequency
        'core':         'full_body',        # core every session = maximum frequency
        'upper_body':   'upper_lower',      # upper day twice per week
        'lower_body':   'upper_lower',      # lower day twice per week
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
        "Australian Pull-Up": 2, "Inverted Row": 2, "Prone Y Raise": 1, "Superman Row": 1, "Nordic Hamstring Curl": 2,
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

        # ── Weighted split selection — considers the full context hierarchy ────
        # Focus area influences but never overrides goal / level / days / style.
        # Every split is scored across all dimensions; highest score wins.
        focus_key = (focus_areas[0] if focus_areas else '').lower().replace(' ', '_')

        # Hard minimum: ≤2 days only makes Full Body viable
        if days <= 2:
            return 'full_body', 'Full Body', \
                f"{days}-day training requires Full Body sessions — the only split that achieves minimum weekly stimulus across all muscle groups."

        # ── Viable splits per day count ───────────────────────────────────────
        # These are the structurally appropriate options; weights rank among them.
        VIABLE_BY_DAYS = {
            3: ['full_body', 'push_pull_legs'],
            4: ['upper_lower', 'push_pull_legs', 'full_body'],
            5: ['push_pull_legs', 'upper_lower', 'bro_split'],
            6: ['push_pull_legs', 'upper_lower', 'bro_split'],
        }
        viable = VIABLE_BY_DAYS.get(days, ['push_pull_legs'])
        # Frequency correction: PPL at 3 days trains each muscle only 1×/week,
        # which is suboptimal for hypertrophy (Schoenfeld 2016 — 2×/week ≥ 1×/week
        # at matched volume). For muscle/recomp goals at 3 days, enforce Full Body
        # (3×/week frequency per muscle).
        if days == 3 and goal in ('build_muscle', 'body_recomp'):
            viable = [s for s in viable if s != 'push_pull_legs'] or ['full_body']

        # 6-day hypertrophy correction: force PPL for muscle/recomp at 6 days unless
        # the user has explicitly chosen a lower-body focus area (in which case UL's
        # 3 lower sessions are warranted). Gives each muscle 2x/week frequency with
        # high per-session volume — the PPL×2 standard for advanced hypertrophy.
        LOWER_BODY_FOCUS = {'lower_body', 'legs', 'glutes', 'hamstrings', 'quads', 'calves'}
        if days == 6 and goal in ('build_muscle', 'body_recomp') \
                and focus_key not in LOWER_BODY_FOCUS \
                and 'push_pull_legs' in viable:
            viable = ['push_pull_legs']

        # ── Goal affinity (0-4 pts) ───────────────────────────────────────────
        # How well each split structurally serves the training goal.
        GOAL_SCORE = {
            'full_body':      {'build_muscle': 2, 'body_recomp': 3, 'lose_fat': 4, 'strength': 3, 'general_fitness': 4, 'athletic_performance': 3},
            'upper_lower':    {'build_muscle': 4, 'body_recomp': 4, 'lose_fat': 3, 'strength': 4, 'general_fitness': 3, 'athletic_performance': 3},
            'push_pull_legs': {'build_muscle': 4, 'body_recomp': 3, 'lose_fat': 3, 'strength': 3, 'general_fitness': 3, 'athletic_performance': 3},
            'bro_split':      {'build_muscle': 3, 'body_recomp': 2, 'lose_fat': 1, 'strength': 1, 'general_fitness': 2, 'athletic_performance': 1},
        }

        # ── Level affinity (0-2 pts) ──────────────────────────────────────────
        # More advanced athletes benefit from higher specialisation.
        LEVEL_SCORE = {
            'full_body':      {'beginner': 2, 'intermediate': 1, 'advanced': 0},
            'upper_lower':    {'beginner': 1, 'intermediate': 2, 'advanced': 2},
            'push_pull_legs': {'beginner': 0, 'intermediate': 2, 'advanced': 2},
            'bro_split':      {'beginner': 0, 'intermediate': 1, 'advanced': 2},
        }

        # ── Focus bias (0-2 pts) ──────────────────────────────────────────────
        # Focus area nudges the split decision but does not override goal or level.
        # Max 2 pts — cannot dominate a goal/level mismatch (max 6 pts there).
        FOCUS_BIAS = {
            'chest':        {'push_pull_legs': 2},
            'back':         {'push_pull_legs': 2},
            'shoulders':    {'push_pull_legs': 2},
            'arms':         {'push_pull_legs': 1, 'bro_split': 2},
            'biceps':       {'push_pull_legs': 1, 'bro_split': 2},
            'triceps':      {'push_pull_legs': 1, 'bro_split': 2},
            'legs':         {'upper_lower': 2, 'push_pull_legs': 1},
            'glutes':       {'upper_lower': 2, 'push_pull_legs': 1},
            'hamstrings':   {'upper_lower': 2, 'push_pull_legs': 1},
            'quads':        {'upper_lower': 2, 'push_pull_legs': 1},
            'calves':       {'upper_lower': 1},
            'core':         {'full_body': 2, 'upper_lower': 1},
            'upper_body':   {'upper_lower': 2, 'push_pull_legs': 1},
            'lower_body':   {'upper_lower': 2, 'push_pull_legs': 1},
            'full_body':    {'full_body': 2, 'upper_lower': 1},
            'conditioning': {'full_body': 1, 'push_pull_legs': 1},
            'power':        {'upper_lower': 1, 'push_pull_legs': 1},
        }

        # ── Score and rank ────────────────────────────────────────────────────
        scored = sorted(
            viable,
            key=lambda sid: (
                GOAL_SCORE.get(sid, {}).get(goal, 2) +
                LEVEL_SCORE.get(sid, {}).get(level, 1) +
                FOCUS_BIAS.get(focus_key, {}).get(sid, 0)
            ),
            reverse=True
        )
        best = scored[0]

        # ── Generate contextual rationale ─────────────────────────────────────
        focus_label = focus_key.replace('_', ' ') if focus_key else goal.replace('_', ' ')
        goal_label  = goal.replace('_', ' ')
        RATIONALE = {
            'full_body': (
                f"Full Body sessions give {focus_label} maximum weekly frequency — every session trains the whole body, "
                f"ideal for {goal_label} and your {days}-day schedule."
            ),
            'upper_lower': (
                f"Upper/Lower gives {focus_label} twice-weekly dedicated sessions with the clearest structural division. "
                f"The gold standard for {goal_label} at {days} days per week."
            ),
            'push_pull_legs': (
                f"Push/Pull/Legs gives {focus_label} a dedicated training session each rotation with full recovery before revisiting. "
                f"The highest-volume option for {goal_label} at {days} days."
            ),
            'bro_split': (
                f"Bro Split gives {focus_label} a fully dedicated training day with maximum isolation volume. "
                f"Appropriate for {goal_label} at advanced level across {days} sessions per week."
            ),
        }
        return best, {
            'full_body': 'Full Body',
            'upper_lower': 'Upper / Lower',
            'push_pull_legs': 'Push / Pull / Legs',
            'bro_split': 'Bro Split',
        }.get(best, best), RATIONALE.get(best, '')

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
        for key in self._normalize_limitations(limitations):
            excluded.update(self.LIMITATION_EXCLUSIONS.get(key, []))
        filtered = [e for e in unique if e not in excluded]
        # Safe fallback: NEVER serve contraindicated exercises.
        # If all candidates are excluded, use bodyweight or any options from the same pattern.
        if filtered:
            result = filtered
        else:
            safe_fallback = [
                e for e in (opts.get('bodyweight', []) + opts.get('any', []))
                if e not in excluded
            ]
            result = safe_fallback if safe_fallback else ["Bodyweight Exercise"]

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

        # Beginner conditioning: Incline Walking instead of Assault Bike
        # Lower impact, easier to pace, gentler entry to conditioning.
        if pattern == 'conditioning' and level == 'beginner':
            swapped = []
            for e in result:
                e = 'Incline Walking Intervals' if e == 'Assault Bike Intervals' else e
                if e not in swapped:
                    swapped.append(e)
            result = swapped

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

    @staticmethod
    def assign_days_of_week(training_labels: list, start_day: str,
                            fitness_level: str) -> list:
        """
        Build a 7-day weekly schedule with rest days placed optimally.
        Returns strings like "Monday: Push — Chest…", "Thursday: Rest".
        """
        WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        n = min(len(training_labels), 6)
        if n == 0:
            return []
        start_idx = next((i for i, d in enumerate(WEEK) if d.lower() == start_day.lower()), 0)

        # Optimal training-slot bitmap: 1 = train, 0 = rest
        # Patterns chosen to: spread evenly, avoid 3+ consecutive for beginners,
        # and naturally place a rest day after Wed/Legs in 5-day PPL.
        PATTERNS = {
            1: [1, 0, 0, 0, 0, 0, 0],
            2: [1, 0, 0, 1, 0, 0, 0],   # Mon + Thu
            3: [1, 0, 1, 0, 1, 0, 0],   # Mon Wed Fri
            4: [1, 1, 0, 1, 1, 0, 0],   # Mon Tue · Thu Fri
            5: [1, 1, 1, 0, 1, 1, 0],   # Mon-Wed · Fri-Sat  (Thu/Sun rest)
            6: [1, 1, 1, 0, 1, 1, 1],   # Mon-Wed · Fri-Sun  (Thu rest)
        }
        # Beginners: never more than 2 consecutive training days
        if fitness_level == 'beginner' and n == 4:
            pattern = [1, 0, 1, 0, 1, 0, 1]
        else:
            pattern = PATTERNS.get(n, PATTERNS[min(n, 6)])

        result = []
        train_idx = 0
        for slot in range(7):
            day_name = WEEK[(start_idx + slot) % 7]
            if pattern[slot] and train_idx < n:
                result.append(f"{day_name}: {training_labels[train_idx]}")
                train_idx += 1
            else:
                result.append(f"{day_name}: Rest")
        return result

    @staticmethod
    def generate_weekly_progression(goal: str) -> list:
        """Returns a 12-week (3 × 4-week block) progression plan tailored to goal."""
        block_names = ["Block 1 — Adapt", "Block 2 — Develop", "Block 3 — Peak"]
        block_templates = {
            "strength": [
                # Block 1 — Foundation
                {"label": "Foundation",     "instruction": "Follow the program as written. Focus on form and hitting prescribed rep ranges with 3-4 RIR."},
                {"label": "Push",            "instruction": "Add 1-2 reps per set, or increase compounds by 2.5 kg. Chase progressive overload."},
                {"label": "Overreach",       "instruction": "Increase load by 2.5-5 kg on compounds. Push to 1-2 RIR — this is the hardest week."},
                {"label": "Deload",          "instruction": "Cut working sets by 50%. Maintain the same weight. Recover and consolidate."},
                # Block 2 — Load
                {"label": "Block 2 — Start", "instruction": "Start 2.5 kg above your Block 1 working weights. Beat your Week 1-3 rep records."},
                {"label": "Push",            "instruction": "Add 2.5-5 kg on compounds. Your baseline is higher — keep chasing overload."},
                {"label": "Overreach",       "instruction": "Heaviest week of Block 2. Push all compounds to 1-2 RIR. New PRs are on the table."},
                {"label": "Deload",          "instruction": "Cut volume by 50%. Maintain load. You've earned this — recovery drives adaptation."},
                # Block 3 — Peak
                {"label": "Block 3 — Start", "instruction": "Start 2.5 kg above Block 2 weights. Hardest block yet — this is the final push."},
                {"label": "Push",            "instruction": "Relentless progression. Add load wherever possible. Every session should be a PR attempt."},
                {"label": "Peak",            "instruction": "Max effort. Heaviest week of the entire 12-week program. Leave nothing in the tank."},
                {"label": "Final Deload",    "instruction": "Cut volume by 50%. Reflect on your progress — you should be markedly stronger than Week 1."},
            ],
            "build_muscle": [
                {"label": "Foundation",     "instruction": "Learn the movements. Train at 3-4 RIR. Log all weights and reps precisely."},
                {"label": "Build",           "instruction": "Add 1-2 reps per set where possible, or slightly increase weight. Maintain strict form."},
                {"label": "Overreach",       "instruction": "Add 1 set to each compound exercise. Push to 1-2 RIR — highest volume of Block 1."},
                {"label": "Deload",          "instruction": "Cut working sets by 50%. Keep the same load. Let the body consolidate the adaptations."},
                {"label": "Block 2 — Start", "instruction": "Start 2.5 kg above Block 1 working weights. Reset rep targets — aim to beat Block 1 top sets."},
                {"label": "Build",           "instruction": "Add 1-2 reps or bump weight. Your muscle memory from Block 1 will accelerate progress."},
                {"label": "Overreach",       "instruction": "Highest volume week of Block 2. Add a set to every compound. Push to true 1-2 RIR."},
                {"label": "Deload",          "instruction": "50% volume reduction. This deload is critical — don't skip it before the final block."},
                {"label": "Block 3 — Start", "instruction": "Start 2.5 kg above Block 2. Final block — this is where maximum hypertrophy happens."},
                {"label": "Build",           "instruction": "Continue progressive overload. Push rep ranges on every set. Volume is at its peak."},
                {"label": "Overreach",       "instruction": "Highest volume of the entire program. Drop sets, rest-pause, or extra reps — go all in."},
                {"label": "Final Deload",    "instruction": "Deload and reflect. You should look and feel noticeably different from Week 1. Time for a new program."},
            ],
            "lose_fat": [
                {"label": "Foundation",     "instruction": "Build the habit. Stay in your rep ranges. Focus on consistency over intensity."},
                {"label": "Build",           "instruction": "Maintain all weights. Reduce rest by 10 s on accessories to keep heart rate elevated."},
                {"label": "Intensify",       "instruction": "Reduce rest by another 10 s. Add a 10-min cardio finisher post-session if energy allows."},
                {"label": "Active Recovery", "instruction": "Cut total volume by 40%. Light cardio on rest days. Let the body adapt to the calorie deficit."},
                {"label": "Block 2 — Dial In","instruction": "Nutrition should be dialled by now. Maintain or slightly increase weights — muscle preservation is priority."},
                {"label": "Push",            "instruction": "Add reps wherever possible. Intensity beats volume in a deficit — keep lifting heavy."},
                {"label": "High Intensity",  "instruction": "Shortest rest periods of the program. Keep weights up. Fat loss happens in recovery."},
                {"label": "Active Recovery", "instruction": "Reduce volume 40%. Keep protein intake high. Sleep and stress management matter as much as training."},
                {"label": "Block 3 — Final Phase","instruction": "Final 4 weeks. Stay the course — body composition changes are compounding now."},
                {"label": "Push",            "instruction": "Maintain all lifts from Blocks 1-2. Add cardio intensity if scale is stalled."},
                {"label": "Peak Intensity",  "instruction": "Most demanding week. High training density, short rests, full sessions. Dig in."},
                {"label": "Final Week",      "instruction": "You've completed 12 weeks. Review your before stats — the results should be clear."},
            ],
            "body_recomp": [
                {"label": "Foundation",     "instruction": "Set your baseline. Focus on compound lifts with controlled tempo. Log everything."},
                {"label": "Build",           "instruction": "Increase compounds by 2.5 kg where form allows. Maintain accessories volume."},
                {"label": "Overreach",       "instruction": "Max effort across the board. Push both intensity and volume — this drives body composition shifts."},
                {"label": "Deload",          "instruction": "Reduce volume by 40%. Maintain load. Allow muscle protein synthesis to peak during recovery."},
                {"label": "Block 2 — Recomp","instruction": "Start 2.5 kg above Block 1 on compounds. Recomp accelerates as training age grows."},
                {"label": "Build",           "instruction": "Increase load or reps. Visual changes may be subtle — trust the process and stay consistent."},
                {"label": "Overreach",       "instruction": "Highest effort of Block 2. Push compounds hard. Recomp results are built in weeks like this."},
                {"label": "Deload",          "instruction": "Active rest. Light movement, high protein, great sleep. The work is done — recovery is the reward."},
                {"label": "Block 3 — Final", "instruction": "Final block. Strongest version of you yet. Aim to beat every Block 2 working weight."},
                {"label": "Build",           "instruction": "Sustained intensity. You're past the initial adaptation — every rep now drives pure recomp."},
                {"label": "Overreach",       "instruction": "Peak week. Maximum effort on all lifts. This is the week that defines the program."},
                {"label": "Final Deload",    "instruction": "Program complete. Compare body composition to Week 1 — the compound effect of 12 weeks should be visible."},
            ],
            "athletic_performance": [
                {"label": "Foundation",      "instruction": "Focus on movement quality and bar speed. Build the base patterns with controlled effort."},
                {"label": "Load",            "instruction": "Increase intensity by 5-10%. Prioritise power output and explosiveness on all movements."},
                {"label": "Peak",            "instruction": "Maximum effort on key lifts. Chase speed, power, and top-end performance."},
                {"label": "Taper",           "instruction": "Cut volume by 50%. Maintain intensity. Nervous system reset before Block 2."},
                {"label": "Block 2 — Load",  "instruction": "Baseline all lifts 5% above Block 1. Power output is the metric — not just load."},
                {"label": "Accumulate",      "instruction": "Increase training density. Shorter rest, more explosive effort. Sport-specific conditioning."},
                {"label": "Peak",            "instruction": "Peak week of Block 2. Max effort, max speed. Test any lifts you're chasing new PRs on."},
                {"label": "Taper",           "instruction": "Full taper. 50% volume, maintain intensity. Physically and neurally prepared for Block 3."},
                {"label": "Block 3 — Peak",  "instruction": "Final block — hardest of the program. Fastest, strongest, most conditioned you'll be."},
                {"label": "Accumulate",      "instruction": "Highest training density of the program. Every set should be executed with intent and speed."},
                {"label": "Peak Performance","instruction": "Ultimate performance week. Test yourself on key lifts and drills. No excuses."},
                {"label": "Final Taper",     "instruction": "Reduce volume 50%. Reflect on 12 weeks of athletic development — the gains are real."},
            ],
            "general_fitness": [
                {"label": "Foundation",      "instruction": "Get familiar with the movements. Prioritise full range of motion and consistent effort."},
                {"label": "Progress",        "instruction": "Add 1-2 reps per set or a small weight increase. Aim for noticeable improvement."},
                {"label": "Challenge",       "instruction": "Push slightly harder on at least 2 exercises per session. Embrace the discomfort."},
                {"label": "Active Recovery", "instruction": "Reduce sets by 30%. Stay active. Prioritise sleep and recovery nutrition this week."},
                {"label": "Block 2 — Elevate","instruction": "Bring your Block 1 weights forward and add 2.5 kg. You know the movements — now load them."},
                {"label": "Build",           "instruction": "Consistent overload. Add reps or weight every session. Habits are now automatic — push harder."},
                {"label": "Push",            "instruction": "Highest effort of Block 2. Don't leave reps in the tank on the big lifts."},
                {"label": "Active Recovery", "instruction": "Easy week. You've earned it. 30-40% volume reduction, same movements, light effort."},
                {"label": "Block 3 — Final", "instruction": "Final 4 weeks. You're a different athlete than Week 1. Train like it."},
                {"label": "Build",           "instruction": "Push all working weights above Block 2. You have 3 weeks to post your best performance."},
                {"label": "Challenge",       "instruction": "Peak week. Hardest effort of the entire program. Every rep counts."},
                {"label": "Final Week",      "instruction": "12 weeks complete — regenerate your program to keep progressing with fresh targets."},
            ],
        }
        template = block_templates.get(goal, block_templates["general_fitness"])
        result = []
        for i in range(3):
            for j in range(4):
                entry = template[i * 4 + j]
                result.append({
                    "week":        i * 4 + j + 1,
                    "block":       block_names[i],
                    "label":       entry["label"],
                    "instruction": entry["instruction"],
                })
        return result

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

        used_primary_options = set()  # Track first-choice exercises to avoid cross-day repeats
        secondary_injections_this_week = 0
        MAX_SECONDARY_INJECTIONS = 2

        for i, session_type in enumerate(session_types):
            archetype = self.SESSION_ARCHETYPES.get(session_type, self.SESSION_ARCHETYPES['full_body_heavy'])
            # Start with all slots (base + optional) — deduplication happens via session_native gate
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
            has_existing_cond = any(s[1] == 'conditioning' for s in slots)
            will_inject_cond = (
                not has_existing_cond
                and style not in ('hybrid', 'functional')
                and (
                    (goal == 'lose_fat')
                    or (goal == 'body_recomp' and i % 2 == 0)
                    or (goal == 'general_fitness' and i % 3 == 0)
                    or (goal == 'athletic_performance' and i % 2 == 0)
                )
            )
            if will_inject_cond:
                max_ex = max(3, max_ex - 1)   # reserve one slot for finisher
                max_sets = max(min_sets, max_sets - 2)  # reduce set budget slightly
                target_sets = (min_sets + max_sets) // 2

            # ── Primary focus: prioritise slots before trimming ──────────────
            # Sort BEFORE the max_ex trim so primary focus patterns survive cuts.
            def _slot_importance(s_tuple):
                pattern, ex_type, _ = s_tuple
                if ex_type == 'primary_compound':       return 0
                if pattern in primary_patterns:         return 1   # primary focus survives trim
                if ex_type == 'secondary_compound':     return 2
                if ex_type == 'conditioning' and style in ('hybrid', 'functional'):
                    return 2   # conditioning is core to hybrid/functional — protect from trim
                if pattern in secondary_patterns:       return 3
                return 4
            slots.sort(key=_slot_importance)
            slots = slots[:max_ex]

            # ── Inject missing primary focus slots (SESSION-NATIVE ONLY) ─────────
            # Only inject a primary focus pattern if it already appears in this
            # session archetype's natural slot list. This preserves session identity:
            # push days stay push, pull days stay pull, leg days stay leg.
            # If the focus cannot be expressed naturally in this session, the weekly
            # structure (split selection) already handles the distribution.
            session_native = {s[0] for s in archetype['slots']}
            focus_slot_count = sum(1 for p, _, _ in slots if p in primary_patterns)
            if primary_patterns and focus_slot_count < len(primary_patterns) and len(slots) < max_ex:
                max_inject = min(2, len(primary_patterns))
                injected = 0
                for fp in primary_patterns:
                    if injected >= max_inject or len(slots) >= max_ex:
                        break
                    if fp not in [s[0] for s in slots] and fp in session_native:
                        slots.append((fp, 'accessory', f'primary focus — {fp.replace("_", " ")} direct volume'))
                        injected += 1

            # ── Build slot specs with budget-aware set allocation ────────────
            excluded_exercises = set()
            for key in self._normalize_limitations(limitations):
                excluded_exercises.update(self.LIMITATION_EXCLUSIONS.get(key, []))

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

                def _round_rest(val: int) -> int:
                    """Round rest to nearest 5s for clean presentation."""
                    return int(round(val / 5) * 5)

                if dur_bucket <= 30:
                    if ex_type == 'primary_compound' and goal == 'strength':
                        rest = _round_rest(max(floor, int(base_rest * 0.85)))
                    elif ex_type in ('primary_compound', 'secondary_compound'):
                        rest = _round_rest(max(floor, int(base_rest * 0.65)))
                    else:
                        rest = _round_rest(max(30, int(base_rest * 0.55)))
                elif dur_bucket <= 45:
                    if ex_type == 'primary_compound' and goal == 'strength':
                        rest = _round_rest(max(floor, int(base_rest * 0.90)))
                    elif ex_type in ('primary_compound', 'secondary_compound'):
                        rest = _round_rest(max(floor, int(base_rest * 0.80)))
                    else:
                        rest = _round_rest(max(45, int(base_rest * 0.70)))
                else:
                    rest = _round_rest(base_rest)

                options = self.get_exercise_options(pattern, equipment, style, limitations, level)
                # If every option for this pattern is contraindicated by the user's
                # limitations (e.g. all lunge variants excluded by a knee injury),
                # skip the slot entirely rather than show a "Bodyweight Exercise"
                # placeholder. Remaining slots still cover the session.
                if options == ["Bodyweight Exercise"]:
                    continue
                # Rotate options to avoid cross-day exercise duplication
                if len(options) > 1:
                    # Move any already-used exercise to the back of the list
                    fresh = [o for o in options if o not in used_primary_options]
                    stale = [o for o in options if o in used_primary_options]
                    options = fresh + stale

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
                # Track the first-choice exercise to avoid repeating it cross-day
                if options:
                    used_primary_options.add(options[0])

                if ex_type != 'primary_compound' and total_sets_allocated >= target_sets:
                    break

            # ── Minimum set floors ────────────────────────────────────────────
            MIN_SETS_FLOOR = {
                "primary_compound":   3,
                "secondary_compound": 2,
                "accessory":          2,
                "isolation":          2,
                "unilateral":         2,
                "core":               2,
                "explosive":          2,
                "conditioning":       1,
            }
            slot_specs = [s for s in slot_specs if s['sets'] >= MIN_SETS_FLOOR.get(s['type'], 2)]
            total_sets_allocated = sum(s['sets'] for s in slot_specs)

            # ── Focus area expression: clean, controlled volume emphasis ─────
            # PRIMARY focus: elevate ONE primary compound that best represents it.
            # Personalization expressed through order and +1 set — not crude inflation.
            # SECONDARY focus: +1 set on existing matching slots for visible refinement.
            # Neither should push any slot past 5 sets for accessories / 6 for compounds.
            focus_boost_headroom = 2
            primary_boost_count = 0
            max_primary_boosts = 2  # boost up to 2 matching slots, not just 1
            for slot in slot_specs:
                if (slot['pattern'] in primary_patterns
                        and primary_boost_count < max_primary_boosts
                        and slot['type'] in ('primary_compound', 'secondary_compound')):
                    cap = 6 if slot['type'] == 'primary_compound' else 5
                    boosted = min(slot['sets'] + 1, cap)
                    if total_sets_allocated - slot['sets'] + boosted <= max_sets + focus_boost_headroom:
                        total_sets_allocated += (boosted - slot['sets'])
                        slot['sets'] = boosted
                        slot['coaching_note'] += ' [primary focus — elevated priority]'
                        primary_boost_count += 1
                elif slot['pattern'] in secondary_patterns:
                    if total_sets_allocated <= max_sets:
                        boosted = min(slot['sets'] + 1, 4)
                        total_sets_allocated += (boosted - slot['sets'])
                        slot['sets'] = boosted
                        slot['coaching_note'] += ' [secondary emphasis]'

            # ── Secondary focus: synergy-gated injection, max 2/week ────────────
            # Replace the session_native gate with SECONDARY_SYNERGY: a secondary
            # focus is only injected into a session where it makes coaching sense.
            # e.g. core on chest day = synergistic finisher; chest on back day = not.
            if (secondary and secondary_injections_this_week < MAX_SECONDARY_INJECTIONS):
                # Allow one extra slot beyond max_ex for secondary finisher
                secondary_cap = max_ex + 1
                synergy_list = self.SECONDARY_SYNERGY.get(session_type, "any")  # default "any" for unlisted session types
                already_covered = {s['pattern'] for s in slot_specs}
                _pattern_to_sf: dict = {}
                for sf in secondary:
                    sf_key = sf.lower().replace(' ', '_')
                    for p in self.FOCUS_AREA_PATTERNS.get(sf_key, []):
                        _pattern_to_sf.setdefault(p, sf_key)

                for sf in secondary:
                    if secondary_injections_this_week >= MAX_SECONDARY_INJECTIONS:
                        break
                    sf_key = sf.lower().replace(' ', '_')
                    compatible = (synergy_list == "any") or (sf_key in synergy_list)
                    if not compatible:
                        continue
                    sf_patterns = self.FOCUS_AREA_PATTERNS.get(sf_key, [])
                    for sp in sf_patterns:
                        if sp in already_covered or len(slot_specs) >= secondary_cap:
                            continue
                        if sp not in session_native:   # don't inject push patterns into pull sessions, etc.
                            continue
                        sec_opts = self.get_exercise_options(sp, equipment, style, limitations, level)
                        if not sec_opts:
                            continue
                        sec_base = goal_params.get('accessory', {})
                        slot_specs.append({
                            "pattern":       sp,
                            "type":          "accessory",
                            "coaching_note": f"secondary focus — {sp.replace('_', ' ')} [{sf_key.replace('_', ' ')} emphasis]",
                            "sets":          2,   # finisher: always 2 working sets
                            "reps":          sec_base.get('reps', '10-15'),
                            "rest_seconds":  60,
                            "effort":        sec_base.get('effort', 'RPE 7'),
                            "options":       sec_opts,
                        })
                        total_sets_allocated += 2
                        already_covered.add(sp)
                        secondary_injections_this_week += 1
                        break  # one pattern per secondary focus per session

            # ── Superset pairing for time-constrained sessions ───────────────
            # When session ≤ 45 min AND secondary focus is active, pair secondary
            # isolation/accessory slots as supersets to save time.
            # Main compounds are NEVER supersetted — straight sets only.
            if dur_bucket <= 45 and secondary_patterns:
                secondary_iso = [
                    s for s in slot_specs
                    if s['pattern'] in secondary_patterns
                    and s['type'] in ('accessory', 'isolation', 'unilateral')
                ]
                for idx in range(0, len(secondary_iso) - 1, 2):
                    secondary_iso[idx]['superset_note'] = 'A'
                    secondary_iso[idx + 1]['superset_note'] = 'B'

            # Reorder slots: primary compounds first → secondary compounds → focus accessories
            # → other accessories → ARM ISOLATION LAST → CORE LAST → conditioning finisher
            # This gives clean coach-built session flow: big lifts first, finish with arms/core.
            ARM_ISO  = {'bicep_curl', 'tricep_push'}
            CORE_PAT = {'core_stability', 'core_flexion', 'carry'}
            def _slot_priority(s: dict) -> int:
                if s['type'] == 'conditioning':            return 99  # always last
                if s['pattern'] in CORE_PAT:               return 6   # core just before conditioning
                if s['pattern'] in ARM_ISO:                return 5   # arm isolation before core
                if s['type'] == 'primary_compound':        return 0   # heavy main lifts first
                if s['type'] == 'secondary_compound':      return 1   # secondary heavy movements
                if s['pattern'] in primary_patterns:       return 2   # primary focus accessories
                if s['pattern'] in secondary_patterns:     return 3   # secondary focus accessories
                return 4                                              # other accessories / isolation
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

            # ── Label consistency validation ───────────────────────────────────
            # If a session archetype labelled "Upper" picks up lower-body compounds
            # (e.g. squat via full_body FOCUS_AREA_PATTERNS), or vice-versa, update
            # the day label so users never see a mismatch.
            # Only COMPOUND mismatches trigger relabelling — arm isolation
            # (bicep_curl, tricep_push) added to a leg day is normal and expected.
            LOWER_COMPOUNDS = {'squat', 'hip_hinge', 'lunge'}
            UPPER_COMPOUNDS = {'horizontal_push', 'incline_push', 'vertical_push',
                               'vertical_pull', 'horizontal_pull'}
            day_patterns = {s['pattern'] for s in slot_specs}
            has_lower_compound = bool(day_patterns & LOWER_COMPOUNDS)
            has_upper_compound = bool(day_patterns & UPPER_COMPOUNDS)
            day_label = archetype['label']
            day_focus = archetype['focus']
            if session_type.startswith('upper_') and has_lower_compound:
                # Upper session picked up a lower compound — relabel
                if 'push' in session_type:
                    day_label = 'Full Body — Push-Led'
                    day_focus = archetype['focus'] + ', Lower Compound Cross-Pattern'
                elif 'pull' in session_type:
                    day_label = 'Full Body — Pull-Led'
                    day_focus = archetype['focus'] + ', Lower Compound Cross-Pattern'
                else:
                    day_label = 'Full Body — Upper-Led'
                    day_focus = archetype['focus'] + ', Lower Compound Cross-Pattern'
            elif session_type.startswith('lower_') and has_upper_compound:
                # Lower session picked up an upper compound — relabel
                if 'quad' in session_type:
                    day_label = 'Full Body — Quad-Led'
                    day_focus = archetype['focus'] + ', Upper Compound Cross-Pattern'
                elif 'hip' in session_type:
                    day_label = 'Full Body — Hip-Led'
                    day_focus = archetype['focus'] + ', Upper Compound Cross-Pattern'
                else:
                    day_label = 'Full Body — Lower-Led'
                    day_focus = archetype['focus'] + ', Upper Compound Cross-Pattern'

            day_blueprints.append({
                "session_number": i + 1,
                "archetype_id":   session_type,
                "label":          day_label,
                "focus":          day_focus,
                "slots":          slot_specs,
            })

        # ═══════════════════════════════════════════════════════════════════════
        # FINAL STRUCTURAL VALIDATION — runs after ALL days are built
        # Purpose: catch any structural violations BEFORE the program reaches the user.
        # This is a guard, not an injection engine. It does NOT add exercises to
        # sessions where they don't belong. It only enforces minimum set floors on
        # exercises that are already in the right sessions.
        # ═══════════════════════════════════════════════════════════════════════
        for d in day_blueprints:
            clean_slots = []
            for slot in d['slots']:
                # Rule: no single-set lifting exercises (conditioning finishers exempt)
                if slot['type'] != 'conditioning' and slot['sets'] < 2:
                    slot['sets'] = 2  # floor to minimum rather than remove
                clean_slots.append(slot)
            d['slots'] = clean_slots

        # ═══════════════════════════════════════════════════════════════════════
        # TIME-ESTIMATION VALIDATION — trim sessions that exceed the target duration.
        # Estimates: ~40s per working set (work + transitions) + rest between sets.
        # Conditioning finishers estimated at 10 min. Warm-up: 5 min overhead.
        # If estimated time exceeds target by >15%, trim lowest-priority slots.
        # ═══════════════════════════════════════════════════════════════════════
        target_minutes = req.duration_minutes
        WORK_PER_SET_SEC = 40  # avg set execution + transition time
        WARMUP_SEC = 300       # 5 min warm-up overhead
        COND_FINISHER_SEC = 600  # 10 min conditioning finisher estimate

        for d in day_blueprints:
            slots = d['slots']
            est_sec = WARMUP_SEC
            for slot in slots:
                if slot['type'] == 'conditioning':
                    est_sec += COND_FINISHER_SEC
                else:
                    est_sec += slot['sets'] * (WORK_PER_SET_SEC + slot['rest_seconds'])
            est_minutes = est_sec / 60.0
            overflow_threshold = target_minutes * 1.15
            while est_minutes > overflow_threshold and len(slots) > 3:
                removable = [
                    (idx, s) for idx, s in enumerate(slots)
                    if s['type'] not in ('primary_compound', 'conditioning')
                ]
                if not removable:
                    break
                remove_idx = removable[-1][0]
                removed = slots.pop(remove_idx)
                est_sec = WARMUP_SEC
                for slot in slots:
                    if slot['type'] == 'conditioning':
                        est_sec += COND_FINISHER_SEC
                    else:
                        est_sec += slot['sets'] * (WORK_PER_SET_SEC + slot['rest_seconds'])
                est_minutes = est_sec / 60.0
            d['slots'] = slots

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
            "weekly_structure": EliteCoachingEngine.assign_days_of_week(
                training_labels=[f"{d['label']} — {d['focus']}" for d in day_blueprints],
                start_day=getattr(req, 'preferred_start_day', 'Monday'),
                fitness_level=level,
            ),
            "weekly_progression": EliteCoachingEngine.generate_weekly_progression(goal),
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
    preview: bool = False  # True = analyze only, don't log — user reviews first

# Chat Models
class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    role: str  # user, assistant
    content: str
    saved: bool = False
    title: Optional[str] = None
    chat_visible: bool = True
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

# Fitbit OAuth Configuration — removed (iOS launch: Apple Health only)
# FITBIT_CLIENT_ID = os.environ.get("FITBIT_CLIENT_ID", "")
# FITBIT_CLIENT_SECRET = os.environ.get("FITBIT_CLIENT_SECRET", "")
# FITBIT_REDIRECT_URI = os.environ.get("FITBIT_REDIRECT_URI", "")

# Garmin Connect OAuth Configuration — removed (iOS launch: Apple Health only)
# GARMIN_CONSUMER_KEY = os.environ.get("GARMIN_CONSUMER_KEY", "")
# GARMIN_CONSUMER_SECRET = os.environ.get("GARMIN_CONSUMER_SECRET", "")

# ==================== HELPER FUNCTIONS ====================

def calculate_macros(weight: float, height: float, age: int, gender: str, activity_level: str, goal: str) -> Dict[str, float]:
    """Calculate personalized macros using Mifflin-St Jeor equation.

    Protein is prescribed from bodyweight (g/kg) per ISSN guidelines — not as
    a % of calories — to ensure adequate lean mass preservation during a
    deficit. Calorie adjustments are percentage-based off TDEE so they scale
    correctly across body sizes.
    """
    # ── BMR: Mifflin-St Jeor ──────────────────────────────────────────
    if gender == "male":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    elif gender == "female":
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    else:
        # Non-binary / "other" — average of male and female constants (-78)
        bmr = 10 * weight + 6.25 * height - 5 * age - 78

    # ── TDEE ──────────────────────────────────────────────────────────
    activity_multipliers = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very_active": 1.9,
    }
    tdee = bmr * activity_multipliers.get(activity_level, 1.55)

    # ── Calorie target (percentage-based off TDEE) ────────────────────
    if goal == "weight_loss":
        calories = tdee * 0.80              # 20% deficit
        protein_per_kg = 2.2                # high — preserve LBM in deficit
    elif goal == "muscle_building":
        calories = tdee * 1.10              # 10% surplus (lean bulk)
        protein_per_kg = 2.0                # industry standard for hypertrophy (RP/MacroFactor)
    else:  # maintenance
        calories = tdee
        protein_per_kg = 1.8                # above MPS ceiling with comfortable margin

    # Safety floor — never prescribe below BMR
    calories = max(calories, bmr * 1.1)

    # ── Macro split: protein from bodyweight, fat at 25% of cals, rest carbs ──
    protein_g = round(min(weight * protein_per_kg, 220))
    fat_g     = round((calories * 0.25) / 9)    # 25% of cals from fat (hormonal minimum)
    remaining_cals = calories - (protein_g * 4) - (fat_g * 9)
    carbs_g   = round(max(remaining_cals, 0) / 4)

    return {
        "calories": round(calories),
        "protein":  protein_g,
        "carbs":    carbs_g,
        "fats":     fat_g,
        "bmr":      round(bmr),
        "tdee":     round(tdee),
    }

# ==================== USER PROFILE ENDPOINTS ====================

@api_router.post("/profile", response_model=UserProfile)
async def create_profile(profile_data: UserProfileCreate):
    """Create a new user profile with password hashing and duplicate email check"""
    # Check for duplicate email
    existing = await db.profiles.find_one(
        {"email": {"$regex": f"^{profile_data.email}$", "$options": "i"}}
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Please sign in instead."
        )

    profile_dict = profile_data.model_dump()

    # Pop password, hash it, store as password_hash
    raw_password = profile_dict.pop("password", "")
    if raw_password:
        profile_dict["password_hash"] = pwd_context.hash(raw_password)

    profile_dict["id"] = str(uuid.uuid4())
    profile_dict["calculated_macros"] = calculate_macros(
        profile_dict["weight"], profile_dict["height"], profile_dict["age"],
        profile_dict["gender"], profile_dict["activity_level"], profile_dict["goal"]
    )
    profile_dict["created_at"] = datetime.utcnow()
    profile_dict["updated_at"] = datetime.utcnow()

    # Check free access list
    free_access_entry = await db.free_access.find_one({"email": profile_data.email.lower()})
    if free_access_entry:
        profile_dict["subscription_status"] = "free_access"

    await db.profiles.insert_one(profile_dict)
    profile_dict["has_password"] = bool(profile_dict.get("password_hash", ""))
    return UserProfile(**profile_dict)

@api_router.get("/profile/{user_id}", response_model=UserProfile)
async def get_profile(user_id: str):
    """Get user profile by ID"""
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile["has_password"] = bool(profile.get("password_hash", ""))
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
    profile["has_password"] = bool(profile.get("password_hash", ""))
    return UserProfile(**profile)

# ==================== AUTH ENDPOINTS ====================

@api_router.post("/auth/login")
async def login_with_password(credentials: LoginRequest):
    """Authenticate user with email and password"""
    profile = await db.profiles.find_one(
        {"email": {"$regex": f"^{credentials.email}$", "$options": "i"}}
    )
    if not profile:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    stored_hash = profile.get("password_hash", "")
    if not stored_hash:
        raise HTTPException(
            status_code=401,
            detail="This account was created before passwords were required. Please contact support at srush@interfitai.com to set a password."
        )

    if not pwd_context.verify(credentials.password, stored_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    profile["has_password"] = True
    return UserProfile(**profile)

@api_router.post("/auth/change-password")
async def change_password(user_id: str, current_password: str, new_password: str):
    """Change user's password"""
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    stored_hash = profile.get("password_hash", "")
    if stored_hash and not pwd_context.verify(current_password, stored_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    await db.profiles.update_one(
        {"id": user_id},
        {"$set": {
            "password_hash": pwd_context.hash(new_password),
            "updated_at": datetime.utcnow(),
        }}
    )
    return {"message": "Password updated successfully"}

# ==================== WORKOUT ENDPOINTS ====================

@api_router.post("/workouts/generate", response_model=WorkoutProgram)
async def generate_workout(request: WorkoutGenerateRequest):
    """
    ELITE COACHING ENGINE
    Step 1 (Python): Build a complete blueprint — split, volume, sets/reps/rest/effort, exercise options
    Step 2 (LLM):    Fill in ONLY exercise names (from options list) and form coaching instructions
    Step 3 (Python): Merge, store coaching metadata, fetch GIFs
    """

    # ─── QUOTA CHECK ─────────────────────────────────────────────────────────
    profile_doc = await db.profiles.find_one({"id": request.user_id})
    user_email = profile_doc.get("email", "") if profile_doc else ""

    if not is_admin(user_email):
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used = await db.generation_events.count_documents({
            "user_id": request.user_id,
            "created_at": {"$gte": month_start},
        })
        if used >= 3:
            # First day of next month
            if now.month == 12:
                reset_dt = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                reset_dt = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            reset_date = reset_dt.date().isoformat()
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "generation_limit",
                    "message": (
                        f"You've used your 3 program generations this month. "
                        f"They reset on {reset_date}. "
                        "Stick with your current program — consistency beats the perfect program."
                    ),
                    "reset_date": reset_date,
                    "used": used,
                    "limit": 3,
                },
            )

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
        weekly_progression=blueprint.get('weekly_progression'),
        preferred_start_day=getattr(request, 'preferred_start_day', 'Monday'),
        training_notes=(
            f"Goal: {request.goal.replace('_',' ').title()} | "
            f"Style: {request.training_style.title()} | "
            f"Split: {blueprint['split_name']} | "
            f"{request.days_per_week} days/week @ {request.duration_minutes}min"
        ),
        workout_days=[WorkoutDay(**day) for day in processed_days],
    )

    await db.workouts.insert_one(program.model_dump())

    # Record generation event for quota tracking (non-admin users only)
    if not is_admin(user_email):
        await db.generation_events.insert_one({
            "user_id": request.user_id,
            "email": user_email,
            "created_at": datetime.utcnow(),
        })

    return program


# ─── Generation Quota endpoint (must be before /workouts/{user_id}) ──────────

@api_router.get("/workouts/generation-quota/{user_id}")
async def get_generation_quota(user_id: str):
    """Returns the user's monthly program generation quota status."""
    profile_doc = await db.profiles.find_one({"id": user_id})
    user_email = profile_doc.get("email", "") if profile_doc else ""
    admin = is_admin(user_email)

    now = datetime.utcnow()
    if now.month == 12:
        reset_dt = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        reset_dt = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    reset_date = reset_dt.date().isoformat()

    if admin:
        return {"used": 0, "limit": None, "remaining": None, "reset_date": reset_date, "is_admin": True}

    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = await db.generation_events.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": month_start},
    })
    limit = 3
    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used),
        "reset_date": reset_date,
        "is_admin": False,
    }

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

class WeekOverrideRequest(BaseModel):
    current_week_override: Optional[int] = None

@api_router.patch("/workout/{workout_id}/week-override")
async def update_workout_week_override(workout_id: str, request: WeekOverrideRequest):
    """Set or clear a manual week override for the 4-week progression block."""
    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"current_week_override": request.current_week_override}}
    )
    return {"success": True, "current_week_override": request.current_week_override}


# ── Week Completion ───────────────────────────────────────────────────────────

import base64 as _b64, io as _io
from PIL import Image as _PILImage, ImageOps as _ImageOps

def _make_thumbnail(photo_b64: str, max_px: int = 300) -> Optional[str]:
    """Return a compressed JPEG thumbnail (~50 KB) from a full-resolution base64 photo."""
    try:
        raw = photo_b64.split(",", 1)[-1]           # strip data-URL prefix if present
        img = _PILImage.open(_io.BytesIO(_b64.b64decode(raw)))
        img = _ImageOps.exif_transpose(img)          # honour EXIF orientation before thumbnailing
        img.thumbnail((max_px, max_px), _PILImage.LANCZOS)
        buf = _io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=55, optimize=True)
        return "data:image/jpeg;base64," + _b64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None

class CompleteWeekRequest(BaseModel):
    user_id: str
    week: int
    photo_base64: Optional[str] = None
    notes: Optional[str] = None

class WeekCompletion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workout_id: str
    user_id: str
    week: int
    completed_at: datetime = Field(default_factory=datetime.utcnow)
    photo_base64: Optional[str] = None
    photo_thumbnail: Optional[str] = None   # ~50 KB compressed thumbnail
    notes: Optional[str] = None

@api_router.post("/workout/{workout_id}/complete-week")
async def complete_week(workout_id: str, request: CompleteWeekRequest):
    """Mark a specific week of a workout as completed."""
    thumbnail = _make_thumbnail(request.photo_base64) if request.photo_base64 else None
    completion = WeekCompletion(
        workout_id=workout_id,
        user_id=request.user_id,
        week=request.week,
        photo_base64=request.photo_base64,
        photo_thumbnail=thumbnail,
        notes=request.notes,
    )
    await db.week_completions.replace_one(
        {"workout_id": workout_id, "user_id": request.user_id, "week": request.week},
        completion.model_dump(),
        upsert=True,
    )
    return {"success": True, "week": request.week, "has_photo": bool(request.photo_base64)}

@api_router.delete("/workout/{workout_id}/complete-week/{week}")
async def undo_week_completion(workout_id: str, week: int, user_id: str):
    """Remove a week completion (undo)."""
    await db.week_completions.delete_one(
        {"workout_id": workout_id, "user_id": user_id, "week": week}
    )
    return {"success": True}

@api_router.get("/workout/{workout_id}/completions")
async def get_week_completions(workout_id: str, user_id: str):
    """Return all completed week numbers for a workout."""
    docs = await db.week_completions.find(
        {"workout_id": workout_id, "user_id": user_id},
        {"_id": 0, "week": 1, "completed_at": 1, "notes": 1}
    ).to_list(20)
    return {"completions": docs}

@api_router.get("/workout/{workout_id}/week-photo/{week}")
async def get_week_photo(workout_id: str, week: int, user_id: str):
    """Return the progress photo for a specific completed week."""
    doc = await db.week_completions.find_one(
        {"workout_id": workout_id, "user_id": user_id, "week": week}
    )
    if not doc or not doc.get("photo_base64"):
        raise HTTPException(status_code=404, detail="No photo for this week")
    return {"photo_base64": doc["photo_base64"]}

@api_router.get("/workout/{workout_id}/completion-details")
async def get_completion_details(workout_id: str, user_id: str):
    """Return all completions with thumbnail photos for the progress timeline."""
    docs = await db.week_completions.find(
        {"workout_id": workout_id, "user_id": user_id},
        {"_id": 0, "week": 1, "completed_at": 1, "notes": 1, "photo_thumbnail": 1}
    ).sort("week", -1).to_list(20)
    return {
        "completions": [
            {
                "week":            d["week"],
                "completed_at":    d.get("completed_at"),
                "notes":           d.get("notes"),
                "has_photo":       bool(d.get("photo_thumbnail")),
                "photo_thumbnail": d.get("photo_thumbnail"),
            }
            for d in docs
        ]
    }

class WorkoutPerformanceRequest(BaseModel):
    performance: dict  # { "dayIndex-exerciseIndex-setIndex": { "weight": "50", "reps": "10", "completed": true } }

# ── Session History Models ────────────────────────────────────────────────────

class SessionSet(BaseModel):
    set_number: int
    weight: Optional[float] = None
    reps: Optional[int] = None
    completed: bool = False

class SessionExercise(BaseModel):
    exercise_name: str
    muscle_groups: List[str] = []
    sets: List[SessionSet] = []

class CompleteSessionRequest(BaseModel):
    user_id: str
    day_index: int
    day_focus: str = ""
    duration_minutes: Optional[int] = None
    completed_exercises: List[SessionExercise] = []
    notes: Optional[str] = None
    photo_base64: Optional[str] = None

class WorkoutSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    workout_id: str
    day_index: int
    day_focus: str = ""
    date: datetime = Field(default_factory=datetime.utcnow)
    duration_minutes: Optional[int] = None
    completed_exercises: List[SessionExercise] = []
    total_volume: float = 0.0
    notes: Optional[str] = None
    photo_base64: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

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

# ── Session History Endpoints ──────────────────────────────────────────────────

@api_router.post("/workout/{workout_id}/session/complete")
async def complete_workout_session(workout_id: str, request: CompleteSessionRequest):
    """Record a completed workout session, detect PRs, return session + PR data"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    # Compute total volume (weight × reps across all completed sets)
    total_volume = 0.0
    for ex in request.completed_exercises:
        for s in ex.sets:
            if s.completed and s.weight and s.reps:
                total_volume += s.weight * s.reps

    # ── Detect Personal Records (fetch prior sessions ONCE before the loop) ──
    personal_records = []
    prior_cursor = (
        db.workout_sessions.find(
            {"user_id": request.user_id},
            {"completed_exercises": 1, "date": 1},
        )
        .sort("date", -1)
        .limit(100)
    )
    prior_sessions = await prior_cursor.to_list(100)

    for ex in request.completed_exercises:
        name_lower = ex.exercise_name.lower().strip()

        prior_best_weight = 0.0
        prior_best_reps_at_weight: Dict[float, int] = {}
        for ps in prior_sessions:
            for pex in ps.get("completed_exercises", []):
                if pex.get("exercise_name", "").lower().strip() == name_lower:
                    for pset in pex.get("sets", []):
                        if pset.get("completed") and pset.get("weight") and pset.get("reps"):
                            w = float(pset["weight"])
                            r = int(pset["reps"])
                            if w > prior_best_weight:
                                prior_best_weight = w
                            if w not in prior_best_reps_at_weight or r > prior_best_reps_at_weight[w]:
                                prior_best_reps_at_weight[w] = r

        pr_found = False
        for s in ex.sets:
            if pr_found:
                break
            if not s.completed or not s.weight or not s.reps:
                continue
            if s.weight > prior_best_weight:
                personal_records.append({
                    "exercise_name": ex.exercise_name,
                    "type": "weight",
                    "new_value": s.weight,
                    "previous_value": prior_best_weight if prior_best_weight > 0 else None,
                    "reps": s.reps,
                })
                pr_found = True
            elif prior_best_weight > 0 and s.weight == prior_best_weight:
                prev_reps = prior_best_reps_at_weight.get(s.weight, 0)
                if s.reps > prev_reps:
                    personal_records.append({
                        "exercise_name": ex.exercise_name,
                        "type": "reps",
                        "new_value": s.reps,
                        "previous_value": prev_reps,
                        "reps": s.reps,
                    })
                    pr_found = True

    session = WorkoutSession(
        user_id=request.user_id,
        workout_id=workout_id,
        day_index=request.day_index,
        day_focus=request.day_focus,
        duration_minutes=request.duration_minutes,
        completed_exercises=request.completed_exercises,
        total_volume=round(total_volume, 1),
        notes=request.notes,
        photo_base64=request.photo_base64,
    )
    session_dict = session.model_dump()
    await db.workout_sessions.insert_one(session_dict)

    # Blank slate: clear weight, reps, AND checkboxes for this day (full reset for next session)
    workout_doc = await db.workouts.find_one({"id": workout_id})
    if workout_doc:
        current_perf = workout_doc.get("performance", {})
        prefix = f"{request.day_index}-"
        cleared_perf = {
            k: ({"weight": "", "reps": "", "completed": False}) if k.startswith(prefix) else v
            for k, v in current_perf.items()
        }
        await db.workouts.update_one(
            {"id": workout_id},
            {"$set": {"performance": cleared_perf}}
        )

    session_dict.pop("_id", None)
    session_dict["personal_records"] = personal_records
    return session_dict

@api_router.get("/workout/sessions/{user_id}")
async def get_user_sessions(user_id: str, limit: int = 20, workout_id: Optional[str] = None):
    """Get all workout sessions for a user, sorted by date descending"""
    query: dict = {"user_id": user_id}
    if workout_id:
        query["workout_id"] = workout_id
    cursor = db.workout_sessions.find(query).sort("date", -1).limit(limit)
    sessions = await cursor.to_list(limit)
    for s in sessions:
        s.pop("_id", None)
    return sessions

@api_router.get("/workout/{workout_id}/last-session")
async def get_last_session(workout_id: str, day_index: int = 0, user_id: Optional[str] = None):
    """Get the most recent session for a workout + day_index pair, optionally filtered by user_id"""
    query: dict = {"workout_id": workout_id, "day_index": day_index}
    if user_id:
        query["user_id"] = user_id
    session = await db.workout_sessions.find_one(query, sort=[("date", -1)])
    if not session:
        return None
    session.pop("_id", None)
    return session

class UpdateExerciseRequest(BaseModel):
    day_index: int
    exercise_index: int
    sets: Optional[int] = None
    reps: Optional[str] = None

# ── Streak & Stats ─────────────────────────────────────────────────────────────

@api_router.get("/workout/stats/{user_id}")
async def get_workout_stats(user_id: str):
    """Streak, weekly adherence, and total session counts for a user"""
    cursor = db.workout_sessions.find({"user_id": user_id}).sort("date", -1)
    sessions = await cursor.to_list(None)
    total_sessions = len(sessions)

    # Weekly target from the user's most recent workout program
    user_workouts = await db.workouts.find({"user_id": user_id}).sort("updated_at", -1).limit(1).to_list(1)
    days_per_week = int(user_workouts[0].get("days_per_week", 4)) if user_workouts else 4

    if not sessions:
        return {
            "current_streak": 0,
            "best_streak": 0,
            "sessions_this_week": 0,
            "weekly_target": days_per_week,
            "total_sessions": 0,
        }

    today = datetime.utcnow().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    sessions_this_week = sum(
        1 for s in sessions
        if s.get("date") and monday <= s["date"].date() <= sunday
    )

    # Unique training dates sorted newest-first
    training_dates = sorted(
        {s["date"].date() for s in sessions if s.get("date")},
        reverse=True,
    )

    # Max gap (calendar days) that still keeps the streak alive
    max_gap = (7 + days_per_week - 1) // days_per_week + 1  # ceil(7/dpw) + 1

    # Grace rule: streak is alive if the last session was today or yesterday
    last_date = training_dates[0]
    streak_alive = (today - last_date).days <= 1

    current_streak = 0
    if streak_alive:
        current_streak = 1
        for i in range(1, len(training_dates)):
            gap = (training_dates[i - 1] - training_dates[i]).days
            if gap <= max_gap:
                current_streak += 1
            else:
                break

    best_streak = current_streak
    temp = 1
    for i in range(1, len(training_dates)):
        gap = (training_dates[i - 1] - training_dates[i]).days
        if gap <= max_gap:
            temp += 1
        else:
            best_streak = max(best_streak, temp)
            temp = 1
    best_streak = max(best_streak, temp)

    return {
        "current_streak": current_streak,
        "best_streak": best_streak,
        "sessions_this_week": sessions_this_week,
        "weekly_target": days_per_week,
        "total_sessions": total_sessions,
    }


# ── All-time Personal Records ──────────────────────────────────────────────────

@api_router.get("/workout/personal-records/{user_id}")
async def get_personal_records(user_id: str):
    """All-time best weight and best reps per exercise for a user"""
    cursor = (
        db.workout_sessions.find({"user_id": user_id}, {"completed_exercises": 1})
        .sort("date", -1)
        .limit(200)
    )
    sessions = await cursor.to_list(200)
    records: Dict[str, Any] = {}
    for s in sessions:
        for ex in s.get("completed_exercises", []):
            name = ex.get("exercise_name", "")
            if not name:
                continue
            key = name.lower().strip()
            if key not in records:
                records[key] = {
                    "exercise_name": name,
                    "best_weight": 0.0,
                    "best_reps_at_weight": 0,
                }
            for set_ in ex.get("sets", []):
                if set_.get("completed") and set_.get("weight") and set_.get("reps"):
                    w = float(set_["weight"])
                    r = int(set_["reps"])
                    if w > records[key]["best_weight"]:
                        records[key]["best_weight"] = w
                        records[key]["best_reps_at_weight"] = r
                    elif w == records[key]["best_weight"] and r > records[key]["best_reps_at_weight"]:
                        records[key]["best_reps_at_weight"] = r
    return list(records.values())


# ── Session Photo ─────────────────────────────────────────────────────────────

class AddPhotoRequest(BaseModel):
    photo_base64: str

@api_router.post("/workout/session/{session_id}/photo")
async def add_session_photo(session_id: str, request: AddPhotoRequest):
    """Add or update a photo for a completed workout session"""
    result = await db.workout_sessions.update_one(
        {"id": session_id},
        {"$set": {"photo_base64": request.photo_base64}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Photo updated", "session_id": session_id}


# ── Exercise Updates ───────────────────────────────────────────────────────────

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

class ReorderExercisesRequest(BaseModel):
    day_index: int
    exercise_order: List[int]  # New order as list of original indices

@api_router.patch("/workout/{workout_id}/reorder-exercises")
async def reorder_exercises(workout_id: str, request: ReorderExercisesRequest):
    """Reorder exercises within a workout day"""
    workout = await db.workouts.find_one({"id": workout_id})
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")
    workout_days = workout.get("workout_days", [])
    if request.day_index >= len(workout_days):
        raise HTTPException(status_code=400, detail="Invalid day index")
    exercises = workout_days[request.day_index].get("exercises", [])
    if len(request.exercise_order) != len(exercises):
        raise HTTPException(status_code=400, detail="Order length mismatch")
    workout_days[request.day_index]["exercises"] = [exercises[i] for i in request.exercise_order]
    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"workout_days": workout_days, "updated_at": datetime.utcnow()}}
    )
    return {"message": "Exercises reordered successfully"}



def _params_for_added_exercise(name: str, goal: str) -> dict:
    """Goal-appropriate sets/reps/rest for a manually-added exercise.
    Classifies the exercise (conditioning / core / compound / isolation) from its
    name, then pulls the matching scheme from the program goal's GOAL_PARAMS so an
    added exercise always matches the program it's added to (e.g. a compound in a
    strength program -> low reps, long rest - not a generic 10-12)."""
    goal_params = EliteCoachingEngine.GOAL_PARAMS.get(
        goal, EliteCoachingEngine.GOAL_PARAMS.get('general_fitness', {})
    )
    n = (name or "").lower()
    if any(k in n for k in ['interval', 'sprint', 'jump rope', 'skipping', 'burpee',
                            'mountain climber', 'rowing machine', 'assault bike',
                            'ski erg', 'incline walk', 'cardio', 'emom', 'jog', 'run']):
        ex_type = 'conditioning'
    elif any(k in n for k in ['plank', 'crunch', 'sit-up', 'sit up', 'dead bug',
                              'bird dog', 'leg raise', 'russian twist', 'pallof',
                              'hollow', 'wood chop', 'woodchop', 'ab wheel', 'ab rollout']):
        ex_type = 'core'
    elif any(k in n for k in ['squat', 'deadlift', 'bench', 'press', 'row',
                              'pull-up', 'pull up', 'chin-up', 'chin up', 'pulldown',
                              'pull-down', 'lunge', 'thrust', 'clean', 'snatch',
                              'dip', 'romanian', 'rdl', 'hip hinge', 'step-up', 'step up']):
        ex_type = 'secondary_compound'
    else:
        ex_type = 'isolation'
    p = goal_params.get(ex_type) or goal_params.get('accessory') or {}
    return {
        'sets':         p.get('sets', 3),
        'reps':         p.get('reps', '10-12'),
        'rest_seconds': p.get('rest', 90),
        'effort':       p.get('effort', ''),
    }


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
    
    # Goal-appropriate sets/reps/rest
    # Match the added exercise to THIS program's goal and movement type, overriding
    # any generic client-supplied defaults (the client always sends 3x10-12). This
    # ensures e.g. a compound added to a strength program gets low reps / long rest.
    _added = _params_for_added_exercise(
        exercise_data.get("name", ""),
        workout.get("goal", "general_fitness"),
    )
    exercise_data["sets"]         = _added["sets"]
    exercise_data["reps"]         = _added["reps"]
    exercise_data["rest_seconds"] = _added["rest_seconds"]
    if _added.get("effort") and not exercise_data.get("effort"):
        exercise_data["effort"] = _added["effort"]
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
            elif exercise.get("gif_url"):
                # Clear any existing (potentially broken) GIF URL if no valid one found
                exercise["gif_url"] = ""
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

# ── Exercise Name Overrides ──────────────────────────────────────────────────
# Maps ExerciseDB raw name (lowercase) → clean gym-standard display name.
# Applied at response time only — DB records keep original names (GIF proxy keys off them).
EXERCISE_NAME_OVERRIDES: dict = {
    # Lower body / Squats
    "barbell full squat":                       "Barbell Back Squat",
    "barbell hack squat":                       "Barbell Hack Squat",
    "barbell front squat":                      "Front Squat",
    "barbell low bar squat":                    "Low Bar Back Squat",
    "barbell box squat":                        "Box Squat",
    "barbell pause squat":                      "Pause Squat",
    "barbell split squat":                      "Split Squat",
    "barbell bulgarian split squat":            "Bulgarian Split Squat",
    "barbell sumo squat":                       "Sumo Squat",
    "dumbbell goblet squat":                    "Goblet Squat",
    "lever hack squat":                         "Machine Hack Squat",
    "lever leg press":                          "Leg Press Machine",
    "lever seated leg press":                   "Seated Leg Press",
    "sled 45° leg press":                       "Leg Press",
    "sled 45 degrees one leg press":            "Single Leg Press",
    "smith leg press":                          "Smith Machine Leg Press",
    "smith machine squat":                      "Smith Machine Squat",
    # Hip hinges
    "barbell romanian deadlift":                "Romanian Deadlift",
    "barbell stiff-leg deadlift":               "Stiff-Leg Deadlift",
    "barbell conventional deadlift":            "Conventional Deadlift",
    "barbell sumo deadlift":                    "Sumo Deadlift",
    "barbell deadlift":                         "Deadlift",
    "barbell hex deadlift":                     "Hex Bar Deadlift",
    "barbell rack pull":                        "Rack Pull",
    "barbell good morning":                     "Good Morning",
    "smith machine romanian deadlift":          "Smith Machine RDL",
    # Hip thrusts
    "barbell hip thrust":                       "Barbell Hip Thrust",
    "lever hip thrust":                         "Hip Thrust Machine",
    # Lunges
    "dumbbell lunge":                           "Dumbbell Lunge",
    "barbell lunge":                            "Barbell Lunge",
    "barbell walking lunge":                    "Walking Lunge",
    "dumbbell step-up":                         "Dumbbell Step-Up",
    "barbell step-up":                          "Barbell Step-Up",
    # Leg isolation machines
    "lever leg extension":                      "Leg Extension Machine",
    "lever seated leg curl":                    "Seated Leg Curl Machine",
    "lever lying leg curl":                     "Lying Leg Curl Machine",
    "lever standing leg curl":                  "Standing Leg Curl Machine",
    "lever seated calf raise":                  "Seated Calf Raise Machine",
    "lever standing calf raise":                "Standing Calf Raise Machine",
    # Chest
    "barbell incline bench press":              "Incline Barbell Bench Press",
    "barbell decline bench press":              "Decline Barbell Bench Press",
    "dumbbell incline bench press":             "Incline Dumbbell Bench Press",
    "dumbbell fly":                             "Dumbbell Fly",
    "dumbbell incline fly":                     "Incline Dumbbell Fly",
    "lever (plate loaded) decline chest press": "Decline Chest Press Machine",
    "lever chest press":                        "Chest Press Machine",
    "lever incline chest press":                "Incline Chest Press Machine",
    "smith machine bench press":                "Smith Machine Bench Press",
    "smith machine incline bench press":        "Smith Machine Incline Bench Press",
    # Back
    "barbell bent over row":                    "Barbell Row",
    "barbell bent over row, overhand":          "Overhand Barbell Row",
    "barbell pendlay row":                      "Pendlay Row",
    "dumbbell bent over row":                   "Dumbbell Row",
    "cable seated row":                         "Seated Cable Row",
    "lever seated row":                         "Seated Row Machine",
    "lever t-bar row":                          "T-Bar Row Machine",
    "barbell t-bar row":                        "T-Bar Row",
    "lever lat pulldown":                       "Lat Pulldown Machine",
    "cable lat pulldown":                       "Cable Lat Pulldown",
    "lever reverse grip lat pulldown":          "Reverse Grip Lat Pulldown",
    "lever one arm lat pulldown":               "Single-Arm Lat Pulldown",
    "lever back extension":                     "Back Extension Machine",
    "cable straight arm pulldown":              "Straight Arm Pulldown",
    # Shoulders
    "barbell overhead press":                   "Barbell Overhead Press",
    "barbell seated overhead press":            "Seated Barbell Press",
    "dumbbell overhead press":                  "Dumbbell Shoulder Press",
    "dumbbell seated overhead press":           "Seated Dumbbell Press",
    "lever seated military press":              "Machine Shoulder Press",
    "cable lateral raise":                      "Cable Lateral Raise",
    "dumbbell lateral raise":                   "Dumbbell Lateral Raise",
    "dumbbell front raise":                     "Dumbbell Front Raise",
    "cable front raise":                        "Cable Front Raise",
    "dumbbell bent over rear delt row":         "Rear Delt Row",
    "cable reverse fly":                        "Cable Rear Delt Fly",
    "barbell upright row":                      "Barbell Upright Row",
    "smith machine overhead press":             "Smith Machine Shoulder Press",
    "cable face pull":                          "Cable Face Pull",
    # Arms
    "barbell preacher curl":                    "Preacher Curl",
    "ez bar curl":                              "EZ Bar Curl",
    "dumbbell alternate bicep curl":            "Alternating Dumbbell Curl",
    "dumbbell hammer curl":                     "Hammer Curl",
    "cable hammer curl (with rope)":            "Cable Hammer Curl",
    "barbell lying triceps extension":          "Skull Crushers",
    "barbell lying close grip triceps press":   "Close Grip Bench Press",
    "ez bar lying triceps extension":           "EZ Bar Skull Crushers",
    "dumbbell triceps extension":               "Dumbbell Triceps Extension",
    "cable triceps pushdown (v-bar)":           "Triceps Pushdown",
    "cable overhead triceps extension (rope)":  "Overhead Triceps Extension",
    "lever triceps dip":                        "Tricep Dip Machine",
    "lever preacher curl":                      "Preacher Curl Machine",
    # Olympic / Power
    "barbell power clean":                      "Power Clean",
    "barbell power snatch":                     "Power Snatch",
    "barbell clean and jerk":                   "Clean and Jerk",
    # Cardio / Conditioning
    "cycle cross trainer":                      "Assault Bike",
    "walking on incline treadmill":             "Incline Treadmill Walk",
}

# ── Exercise Target Overrides ────────────────────────────────────────────────
# Maps raw exercise name (lowercase) → list of muscle chip IDs this exercise
# meaningfully trains, beyond what ExerciseDB's single "target" field captures.
# Values must be keys from MUSCLE_TARGET_MAP.
EXERCISE_TARGET_OVERRIDES: dict = {
    # Squats — ExerciseDB inconsistently tags "glutes" vs "quads"
    "barbell full squat":               ["legs", "glutes"],
    "barbell hack squat":               ["legs", "glutes"],
    "barbell front squat":              ["legs", "glutes"],
    "barbell low bar squat":            ["legs", "glutes"],
    "barbell box squat":                ["legs", "glutes"],
    "barbell pause squat":              ["legs", "glutes"],
    "barbell split squat":              ["legs", "glutes"],
    "barbell bulgarian split squat":    ["legs", "glutes"],
    "barbell sumo squat":               ["legs", "glutes"],
    "dumbbell goblet squat":            ["legs", "glutes"],
    "lever hack squat":                 ["legs", "glutes"],
    "smith machine squat":              ["legs", "glutes"],
    # Hip hinges / Deadlifts
    "barbell romanian deadlift":        ["glutes", "legs"],
    "barbell stiff-leg deadlift":       ["glutes", "legs"],
    "barbell conventional deadlift":    ["glutes", "legs", "back"],
    "barbell sumo deadlift":            ["glutes", "legs"],
    "barbell deadlift":                 ["glutes", "legs", "back"],
    "barbell hex deadlift":             ["glutes", "legs", "back"],
    "barbell rack pull":                ["back", "glutes"],
    "barbell good morning":             ["glutes", "legs"],
    "smith machine romanian deadlift":  ["glutes", "legs"],
    "dumbbell romanian deadlift":       ["glutes", "legs"],
    # Hip thrusts / glute bridges
    "barbell hip thrust":               ["glutes", "legs"],
    "lever hip thrust":                 ["glutes", "legs"],
    "dumbbell hip thrust":              ["glutes", "legs"],
    "barbell glute bridge":             ["glutes", "legs"],
    # Leg press & lunges
    "lever leg press":                  ["legs", "glutes"],
    "lever seated leg press":           ["legs", "glutes"],
    "sled 45° leg press":               ["legs", "glutes"],
    "sled 45 degrees one leg press":    ["legs", "glutes"],
    "sled 45° leg wide press":          ["legs", "glutes"],
    "smith leg press":                  ["legs", "glutes"],
    "dumbbell lunge":                   ["legs", "glutes"],
    "barbell lunge":                    ["legs", "glutes"],
    "barbell walking lunge":            ["legs", "glutes"],
    "dumbbell step-up":                 ["legs", "glutes"],
    "barbell step-up":                  ["legs", "glutes"],
    # Bench press family — chest primary, triceps secondary
    "barbell bench press":              ["chest", "triceps"],
    "barbell incline bench press":      ["chest", "triceps", "shoulders"],
    "barbell decline bench press":      ["chest", "triceps"],
    "dumbbell bench press":             ["chest", "triceps"],
    "dumbbell incline bench press":     ["chest", "triceps", "shoulders"],
    "lever chest press":                ["chest", "triceps"],
    "lever incline chest press":        ["chest", "triceps", "shoulders"],
    "smith machine bench press":        ["chest", "triceps"],
    "smith machine incline bench press": ["chest", "triceps", "shoulders"],
    # Dips
    "chest dip":                        ["chest", "triceps"],
    "triceps dip":                      ["triceps", "chest"],
    "parallel bar dip":                 ["triceps", "chest"],
    # Rows — back primary, biceps secondary
    "barbell bent over row":            ["back", "biceps"],
    "barbell pendlay row":              ["back", "biceps"],
    "dumbbell bent over row":           ["back", "biceps"],
    "cable seated row":                 ["back", "biceps"],
    "lever seated row":                 ["back", "biceps"],
    "lever t-bar row":                  ["back", "biceps"],
    "barbell t-bar row":                ["back", "biceps"],
    # Pull-ups / pulldowns
    "pull-up":                          ["back", "biceps"],
    "chin-up":                          ["back", "biceps"],
    "lever lat pulldown":               ["back", "biceps"],
    "cable lat pulldown":               ["back", "biceps"],
    # OHP — shoulders primary, triceps secondary
    "barbell overhead press":           ["shoulders", "triceps"],
    "barbell seated overhead press":    ["shoulders", "triceps"],
    "dumbbell overhead press":          ["shoulders", "triceps"],
    "dumbbell seated overhead press":   ["shoulders", "triceps"],
    "lever seated military press":      ["shoulders", "triceps"],
    "smith machine overhead press":     ["shoulders", "triceps"],
    # Skull crushers / close grip
    "barbell lying triceps extension":       ["triceps"],
    "barbell lying close grip triceps press": ["triceps", "chest"],
    "ez bar lying triceps extension":        ["triceps"],
    # Upright row
    "barbell upright row":              ["shoulders", "back"],
    "dumbbell upright row":             ["shoulders", "back"],
    # Olympic lifts
    "barbell power clean":              ["legs", "back", "shoulders"],
    "barbell power snatch":             ["legs", "back", "shoulders"],
    "barbell clean and jerk":           ["legs", "back", "shoulders"],
    # Deadlifts also useful in back context
    "barbell conventional deadlift":    ["back", "glutes", "legs"],
    "barbell deadlift":                 ["back", "glutes", "legs"],
}


def _display_name(raw_name: str) -> str:
    """Return the user-facing display name for an exercise."""
    return EXERCISE_NAME_OVERRIDES.get(raw_name.lower(), raw_name.title())


@api_router.get("/exercises/search")
async def search_exercises(
    search: str = None,
    muscle: str = None,
    equipment: str = None,
    body_part: str = None,
    limit: int = 50,
    offset: int = 0,
):
    """Search exercises from local MongoDB exercise_library (fast, no rate-limit)."""

    # Frontend chip-id → exact ExerciseDB target field values
    MUSCLE_TARGET_MAP: dict = {
        "biceps":    ["biceps"],
        "triceps":   ["triceps"],
        "chest":     ["pectorals"],
        "back":      ["lats", "upper back", "lower back", "traps", "spine", "serratus anterior"],
        "shoulders": ["delts"],
        "legs":      ["quads", "hamstrings", "calves", "adductors", "abductors"],
        "glutes":    ["glutes"],
        "abs":       ["abs", "obliques"],
        "cardio":    ["cardiovascular system"],
    }

    query_parts: list = []

    # ── Text search ──────────────────────────────────────────────────────────
    if search and search.strip():
        s = search.strip()
        text_conditions: list = [{"name": {"$regex": s, "$options": "i"}}]
        # Reverse override lookup: searching "back squat" → also finds "barbell full squat"
        rev_lookup = [
            raw for raw, display in EXERCISE_NAME_OVERRIDES.items()
            if s.lower() in display.lower() or s.lower() in raw.lower()
        ]
        if rev_lookup:
            text_conditions.append({"name": {"$in": rev_lookup}})
        query_parts.append({"$or": text_conditions} if len(text_conditions) > 1 else text_conditions[0])

    # ── Muscle chip filter ───────────────────────────────────────────────────
    if muscle:
        chip = muscle.lower()
        targets = MUSCLE_TARGET_MAP.get(chip)
        muscle_conditions: list = []

        if targets:
            # (a) Primary target match
            muscle_conditions.append(
                {"target": {"$in": targets}} if len(targets) > 1 else {"target": targets[0]}
            )
            # (b) Secondary muscles array contains any of the targets
            muscle_conditions.append({"secondary_muscles": {"$in": targets}})
        else:
            muscle_conditions.append({"target": chip})
            muscle_conditions.append({"secondary_muscles": chip})

        # (c) Compound exercises from EXERCISE_TARGET_OVERRIDES
        override_names = [
            raw for raw, chips in EXERCISE_TARGET_OVERRIDES.items()
            if chip in chips
        ]
        if override_names:
            muscle_conditions.append({"name": {"$in": override_names}})

        query_parts.append({"$or": muscle_conditions})

    # ── Optional extra filters ───────────────────────────────────────────────
    if equipment:
        query_parts.append({"equipment": {"$regex": equipment.strip(), "$options": "i"}})
    if body_part:
        query_parts.append({"body_part": {"$regex": body_part.strip(), "$options": "i"}})

    # Combine all parts with $and
    query: dict = {"$and": query_parts} if query_parts else {}

    # Check if library is populated
    total_count = await db.exercise_library.count_documents(query)
    if total_count == 0 and not search and not muscle:
        lib_total = await db.exercise_library.count_documents({})
        if lib_total == 0:
            logger.warning("exercise_library collection is empty — run import_exercises.py to seed it")
            return {"exercises": [], "total_count": 0, "offset": offset, "limit": limit,
                    "message": "Exercise library not yet seeded. Run the import script."}

    cursor = (
        db.exercise_library.find(query, {"_id": 0})
        .sort("name", 1)
        .skip(offset)
        .limit(limit)
    )
    raw_docs = await cursor.to_list(length=limit)

    exercises = [
        {
            "id":               ex.get("exercisedb_id", ""),
            "name":             _display_name(ex.get("name", "")),
            "target":           ex.get("target", ""),
            "equipment":        ex.get("equipment", ""),
            "bodyPart":         ex.get("body_part", ""),
            "gifUrl":           f"/api/exercises/gif/{ex['gif_id']}" if ex.get("gif_id") else None,
            "secondaryMuscles": ex.get("secondary_muscles", []),
            "instructions":     ex.get("instructions", []),
        }
        for ex in raw_docs
    ]

    return {
        "exercises":   exercises,
        "total_count": total_count,
        "offset":      offset,
        "limit":       limit,
    }


class ImportExercisesRequest(BaseModel):
    force_refresh: bool = False

@api_router.post("/admin/import-exercises")
async def admin_import_exercises(request: ImportExercisesRequest = ImportExercisesRequest()):
    """Re-runnable endpoint to seed/refresh the exercise_library from ExerciseDB.
    Safe to call multiple times — uses upsert by exercisedb_id.
    """
    import httpx as _httpx

    if not EXERCISEDB_API_KEY:
        raise HTTPException(status_code=503, detail="EXERCISEDB_API_KEY not configured")

    # Skip if already populated and not forced
    existing_count = await db.exercise_library.count_documents({})
    if existing_count > 500 and not request.force_refresh:
        return {"message": "Library already populated", "total": existing_count, "skipped": True}

    headers = {
        "X-RapidAPI-Key": EXERCISEDB_API_KEY,
        "X-RapidAPI-Host": EXERCISEDB_API_HOST,
    }

    all_exercises = []
    batch_size = 100
    offset = 0

    async with _httpx.AsyncClient(timeout=30.0) as http:
        while True:
            resp = await http.get(
                f"{EXERCISEDB_API_BASE}/exercises",
                headers=headers,
                params={"limit": batch_size, "offset": offset},
            )
            if resp.status_code != 200:
                logger.error(f"ExerciseDB import error at offset {offset}: {resp.status_code}")
                break
            batch = resp.json()
            if not batch:
                break
            all_exercises.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
            import asyncio as _asyncio
            await _asyncio.sleep(1.2)

    upserted = 0
    for ex in all_exercises:
        eid = ex.get("id", "")
        doc = {
            "exercisedb_id":    eid,
            "name":             ex.get("name", "").strip(),
            "target":           ex.get("target", "").strip(),
            "secondary_muscles": ex.get("secondaryMuscles", []),
            "body_part":        ex.get("bodyPart", "").strip(),
            "equipment":        ex.get("equipment", "").strip(),
            "gif_id":           eid,
            "instructions":     ex.get("instructions", []),
        }
        await db.exercise_library.update_one(
            {"exercisedb_id": eid}, {"$set": doc}, upsert=True
        )
        upserted += 1

    # Ensure indexes exist
    await db.exercise_library.create_index("target")
    await db.exercise_library.create_index("body_part")
    await db.exercise_library.create_index("equipment")
    await db.exercise_library.create_index([("name", 1)])
    await db.exercise_library.create_index("secondary_muscles")

    total = await db.exercise_library.count_documents({})
    targets = sorted(await db.exercise_library.distinct("target"))
    logger.info(f"exercise_library import done: {upserted} upserted, {total} total")

    return {
        "message":  "Import complete",
        "upserted": upserted,
        "total":    total,
        "targets":  targets,
    }

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
            raise HTTPException(status_code=response.status_code, detail="GIF not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GIF proxy error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch GIF")

# ==================== MEAL PLAN ENDPOINTS ====================

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
    "extra lean beef mince": (153, 25, 0, 6),
    "premium beef mince": (153, 25, 0, 6),
    "premium ground beef": (153, 25, 0, 6),
    "5 star beef mince": (153, 25, 0, 6),
    "five star beef mince": (153, 25, 0, 6),
    "lean beef mince": (170, 26, 0, 8),
    "extra lean ground beef": (153, 25, 0, 6),
    "lean ground beef": (170, 26, 0, 8),
    "fatty beef mince": (250, 26, 0, 17),
    "regular beef mince": (250, 26, 0, 17),
    "fatty ground beef": (250, 26, 0, 17),
    "regular ground beef": (250, 26, 0, 17),
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

# ==================== ALLERGEN SYNONYM EXPANSION & BANNED-FOOD MATCHING ====================
ALLERGEN_SYNONYMS = {
    "gluten": ["wheat", "flour", "bread", "pasta", "barley", "rye", "couscous", "semolina", "cracker"],
    "nuts": ["almond", "cashew", "peanut", "walnut", "pecan", "hazelnut", "pistachio", "macadamia", "brazil nut", "nut butter", "nut milk"],
    "soy": ["tofu", "tempeh", "edamame", "soy sauce", "miso"],
    "lactose": ["milk", "cheese", "yogurt", "cream", "butter", "whey", "casein"],
    "dairy": ["milk", "cheese", "yogurt", "cream", "butter", "whey", "casein"],
    "eggs": ["egg", "mayonnaise", "mayo", "aioli"],
    "shellfish": ["prawn", "shrimp", "crab", "lobster", "oyster", "mussel", "scallop"],
}


def _stem_word(w: str) -> str:
    """Very light stemmer: singular/plural match both ways (mushrooms <-> mushroom)."""
    w = w.lower()
    if len(w) > 3 and w.endswith("s"):
        return w[:-1]
    return w


def _words_match(a: str, b: str) -> bool:
    sa, sb = _stem_word(a), _stem_word(b)
    if sa == sb:
        return True
    # prefix match for stem variants like tomato/tomatoes -> tomato/tomatoe
    if len(sa) >= 4 and len(sb) >= 4 and (sa.startswith(sb) or sb.startswith(sa)):
        return True
    return False


def expand_banned_terms(banned_list):
    """Expand banned terms with allergen synonyms/derivatives (nuts -> almond, cashew...)."""
    expanded = []
    for term in banned_list or []:
        t = str(term).lower().strip()
        if not t:
            continue
        if t not in expanded:
            expanded.append(t)
        syns = ALLERGEN_SYNONYMS.get(t)
        if syns is None:
            # try stem/plural variants of the key ("nut" -> "nuts", "egg" -> "eggs")
            syns = ALLERGEN_SYNONYMS.get(t + "s") or ALLERGEN_SYNONYMS.get(_stem_word(t)) or ALLERGEN_SYNONYMS.get(_stem_word(t) + "s")
        if syns:
            for s in syns:
                if s not in expanded:
                    expanded.append(s)
    return expanded


def contains_banned_food(text: str, banned_term: str) -> bool:
    """Word-stem matching of a banned term (single word or phrase) inside text.
    'mushrooms' catches 'mushroom' and vice versa. Ignores 'gluten-free' style mentions."""
    t = (text or "").lower()
    bt = (banned_term or "").lower().strip()
    if not t or not bt:
        return False
    # Avoid false positives: "gluten-free" should not match banned "gluten"
    for variant in (bt, _stem_word(bt), bt + "s"):
        t = t.replace(f"{variant}-free", "").replace(f"{variant} free", "")
    tokens = re.findall(r"[a-z]+", t)
    phrase = re.findall(r"[a-z]+", bt)
    if not phrase:
        return False
    n = len(phrase)
    for i in range(len(tokens) - n + 1):
        if all(_words_match(tokens[i + j], phrase[j]) for j in range(n)):
            return True
    return False


def scrub_banned_mentions(text: str, banned_terms) -> str:
    """Remove mentions of banned terms (with stem/plural variants) from prose text
    like meal names and instructions. Multi-word phrases are removed as a whole."""
    if not text:
        return text
    for b in banned_terms:
        words = re.findall(r"[a-z]+", str(b).lower())
        if not words:
            continue
        pattern = r"\b" + r"[\s-]+".join(rf"{re.escape(_stem_word(w))}[a-z]*" for w in words) + r"\b"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.;])", r"\1", text)
    return text.strip(" ,-–&")


def strip_banned_and_recompute(meal: dict, banned_terms) -> list:
    """Remove ingredients containing banned terms, then recompute the meal's macros
    from the remaining ingredients via the ingredient database. Returns removed ingredients."""
    ingredients = meal.get("ingredients", [])
    removed = [ing for ing in ingredients if any(contains_banned_food(str(ing), b) for b in banned_terms)]
    if not removed:
        return []
    meal["ingredients"] = [ing for ing in ingredients if ing not in removed]
    total_cal = total_pro = total_carb = total_fat = 0.0
    matched_any = False
    for ing in meal["ingredients"]:
        m = calculate_ingredient_macros(str(ing))
        if m:
            matched_any = True
            total_cal += m["calories"]
            total_pro += m["protein"]
            total_carb += m["carbs"]
            total_fat += m["fats"]
    if matched_any:
        meal["calories"] = round(total_cal)
        meal["protein"] = round(total_pro, 1)
        meal["carbs"] = round(total_carb, 1)
        meal["fats"] = round(total_fat, 1)
    return removed



@api_router.post("/mealplans/generate", response_model=MealPlan)
async def generate_meal_plan(request: MealPlanGenerateRequest):
    """Generate meal plan using DIET-SPECIFIC templates scaled to user's targets"""
    profile = await db.profiles.find_one({"id": request.user_id})
    if not profile or not profile.get("calculated_macros"):
        raise HTTPException(status_code=404, detail="User profile with macros not found. Please set up your profile first.")
    
    macros = profile["calculated_macros"]
    # Honour the user's manual calorie adjustment (Macro Targets screen) so the
    # plan is built for the same daily target the food log displays.
    # Carbs absorb the adjustment (cal/4), matching the food log's display logic.
    manual_cal_adj = int(profile.get("calorie_adjustment", 0) or 0)
    target_cal = macros['calories'] + manual_cal_adj
    target_pro = macros['protein']
    target_carb = max(0, macros['carbs'] + round(manual_cal_adj / 4))
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
                    "arborio rice": (150, 525, 