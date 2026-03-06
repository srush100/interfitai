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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'interfitai')]

# OpenAI configuration
openai.api_key = os.environ.get('OPENAI_API_KEY', '')

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
    "cable fly": "0160",
    "cable crossover": "0160",
    "push up": "0662",
    "push-up": "0662",
    "pushup": "0662",
    "wide push up": "0672",
    "diamond push up": "0279",
    "decline push up": "1302",
    "chest dip": "0251",
    "dip": "0251",
    "parallel bar dip": "0251",
    
    # Back exercises
    "pull up": "0652",
    "pull-up": "0652",
    "pullup": "0652",
    "wide grip pull up": "0655",
    "chin up": "0253",
    "chin-up": "0253",
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
    "t bar row": "1356",
    "deadlift": "0032",
    "barbell deadlift": "0032",
    "conventional deadlift": "0032",
    "romanian deadlift": "0085",
    "stiff leg deadlift": "0116",
    "sumo deadlift": "0118",
    
    # Shoulder exercises
    "overhead press": "0431",
    "shoulder press": "0431",
    "barbell shoulder press": "0431",
    "military press": "0431",
    "standing military press": "0431",
    "dumbbell shoulder press": "0405",
    "seated dumbbell press": "0405",
    "arnold press": "0251",
    "lateral raise": "0334",
    "dumbbell lateral raise": "0334",
    "side lateral raise": "0334",
    "front raise": "0310",
    "dumbbell front raise": "0310",
    "rear delt fly": "0578",
    "reverse fly": "0578",
    "face pull": "0174",
    "cable face pull": "0174",
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
    "ez bar curl": "0028",
    "hammer curl": "0301",
    "dumbbell hammer curl": "0301",
    "preacher curl": "0672",
    "concentration curl": "0274",
    "incline dumbbell curl": "0313",
    "cable curl": "0163",
    "cable bicep curl": "0163",
    
    # Arm exercises - Triceps
    "tricep pushdown": "0242",
    "cable pushdown": "0242",
    "tricep rope pushdown": "0242",
    "rope pushdown": "0242",
    "tricep extension": "0860",
    "overhead tricep extension": "0860",
    "dumbbell tricep extension": "0860",
    "skull crusher": "0055",
    "lying tricep extension": "0055",
    "barbell skull crusher": "0055",
    "tricep dip": "0353",
    "bench dip": "0353",
    "tricep kickback": "0347",
    "dumbbell kickback": "0347",
    "close grip bench press": "0031",
    "diamond push up": "0279",
    
    # Leg exercises
    "squat": "0043",
    "barbell squat": "0043",
    "back squat": "0043",
    "front squat": "0037",
    "barbell front squat": "0037",
    "goblet squat": "0441",
    "dumbbell goblet squat": "0441",
    "leg press": "0738",
    "sled leg press": "0738",
    "hack squat": "0473",
    "leg extension": "0585",
    "seated leg extension": "0585",
    "leg curl": "0586",
    "lying leg curl": "0586",
    "hamstring curl": "0586",
    "seated leg curl": "0594",
    "calf raise": "1373",
    "standing calf raise": "1373",
    "seated calf raise": "0720",
    "lunge": "0333",
    "dumbbell lunge": "0333",
    "walking lunge": "1466",
    "reverse lunge": "0689",
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
    "plank": "0628",
    "front plank": "0628",
    "forearm plank": "0628",
    "side plank": "0709",
    "crunch": "0267",
    "ab crunch": "0267",
    "bicycle crunch": "0139",
    "reverse crunch": "0690",
    "russian twist": "0703",
    "leg raise": "1472",
    "lying leg raise": "1472",
    "hanging leg raise": "1760",
    "hanging knee raise": "0485",
    "knee raise": "0485",
    "mountain climber": "0601",
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
    "box jump": "1487",
    "kettlebell swing": "0509",
    "power clean": "0068",
    "clean and press": "1209",
    "clean and jerk": "1212",
    "snatch": "0104",
    "thruster": "2143",
    "wall ball": "2399",
    
    # Machine exercises
    "chest press machine": "0152",
    "machine chest press": "0152",
    "pec deck": "0613",
    "machine fly": "0613",
    "shoulder press machine": "0718",
    "machine shoulder press": "0718",
    "cable lateral raise": "0175",
    "rowing machine": "1866",
}

# Cache for exercise GIFs to avoid repeated API calls
exercise_gif_cache = {}

async def get_exercise_gif_from_api(exercise_name: str) -> str:
    """Fetch computer-generated animated GIF - uses cache first, then API"""
    import httpx
    import urllib.parse
    import asyncio
    
    name_lower = exercise_name.lower().strip().replace("-", " ")
    
    # Check local cache first
    if name_lower in exercise_gif_cache:
        return exercise_gif_cache[name_lower]
    
    # Check pre-cached exercise IDs - exact match first
    if name_lower in CACHED_EXERCISE_GIFS:
        exercise_id = CACHED_EXERCISE_GIFS[name_lower]
        proxy_url = f"/api/exercises/gif/{exercise_id}"
        exercise_gif_cache[name_lower] = proxy_url
        return proxy_url
    
    # Try smart matching - prioritize longer/more specific matches
    best_match = None
    best_match_len = 0
    for cached_name, exercise_id in CACHED_EXERCISE_GIFS.items():
        # Exact substring match - the cached name should be IN the exercise name
        # or exercise name should be IN cached name
        if cached_name == name_lower:
            best_match = exercise_id
            break
        elif cached_name in name_lower and len(cached_name) > best_match_len:
            best_match = exercise_id
            best_match_len = len(cached_name)
        elif name_lower in cached_name and len(name_lower) > best_match_len:
            best_match = exercise_id
            best_match_len = len(name_lower)
    
    if best_match:
        proxy_url = f"/api/exercises/gif/{best_match}"
        exercise_gif_cache[name_lower] = proxy_url
        return proxy_url
    
    # If no API key or quota exceeded, return empty
    if not EXERCISEDB_API_KEY:
        return ""
    
    headers = {
        "X-RapidAPI-Key": EXERCISEDB_API_KEY,
        "X-RapidAPI-Host": EXERCISEDB_API_HOST
    }
    
    # Normalize and map exercise names for API search
    exercise_mappings = {
        "pull-up": "pull up", "pullup": "pull up",
        "chin-up": "chin up",
        "push-up": "push up", "pushup": "push up",
        "bench press": "barbell bench press", 
        "squat": "barbell squat",
        "deadlift": "barbell deadlift", 
        "overhead press": "barbell shoulder press",
        "military press": "barbell shoulder press", 
        "lat pulldown": "cable lat pulldown",
        "bicep curl": "dumbbell bicep curl", 
        "tricep pushdown": "cable pushdown",
        "leg press": "sled leg press", 
        "calf raise": "standing calf raise",
        "hip thrust": "barbell hip thrust", 
        "lateral raise": "dumbbell lateral raise",
        "plank": "front plank", 
        "lunge": "dumbbell lunge",
        "row": "barbell bent over row",
        "fly": "dumbbell fly",
        "extension": "tricep extension",
        "curl": "dumbbell curl",
    }
    
    search_term = name_lower
    for key, mapped in exercise_mappings.items():
        if key in name_lower:
            search_term = mapped
            break
    
    try:
        await asyncio.sleep(0.3)  # Rate limit protection
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            encoded_term = urllib.parse.quote(search_term)
            response = await client.get(
                f"{EXERCISEDB_API_BASE}/exercises/name/{encoded_term}",
                headers=headers
            )
            
            if response.status_code == 429:
                logger.warning(f"Rate limited - using fallback for '{exercise_name}'")
                return ""
            
            if response.status_code == 200:
                exercises = response.json()
                if exercises and len(exercises) > 0:
                    # Try to find the best match from results
                    exercise_id = None
                    for ex in exercises:
                        ex_name = ex.get("name", "").lower()
                        if name_lower in ex_name or ex_name in name_lower:
                            exercise_id = ex.get("id", "")
                            break
                    # Fallback to first result
                    if not exercise_id:
                        exercise_id = exercises[0].get("id", "")
                    
                    if exercise_id:
                        proxy_url = f"/api/exercises/gif/{exercise_id}"
                        exercise_gif_cache[name_lower] = proxy_url
                        return proxy_url
    except Exception as e:
        logger.warning(f"ExerciseDB API error for '{exercise_name}': {e}")
    
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
    subscription_status: str = "free"  # free, monthly, quarterly, yearly
    subscription_end_date: Optional[str] = None
    reminders_enabled: bool = True
    motivation_enabled: bool = True
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
    reminders_enabled: Optional[bool] = None
    motivation_enabled: Optional[bool] = None

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
    injuries: Optional[str] = None
    duration_weeks: int = 4
    days_per_week: int = 4
    session_duration_minutes: int = 60  # Workout session duration
    workout_days: List[WorkoutDay]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WorkoutGenerateRequest(BaseModel):
    user_id: str
    goal: str  # build_muscle, lose_fat, general_fitness, strength
    focus_areas: List[str]  # full_body, back, chest, legs, glutes, arms
    equipment: List[str]  # full_gym, barbells, dumbbells, bodyweight, kettlebells, machines
    injuries: Optional[str] = None  # lower_back, knees, shoulders, none
    days_per_week: int = 4
    duration_minutes: int = 60  # Session duration
    fitness_level: str = "intermediate"  # beginner, intermediate, advanced

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
    supplements: List[str]
    supplements_custom: Optional[str] = None  # Custom supplement text
    allergies: List[str]
    cuisine_preference: Optional[str] = None  # Preferred cuisine
    target_calories: int
    target_protein: float
    target_carbs: float
    target_fats: float
    meal_days: List[MealDay]
    is_saved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MealPlanGenerateRequest(BaseModel):
    user_id: str
    food_preferences: str = "whole_foods"  # whole_foods, vegan, vegetarian, keto, none
    supplements: List[str] = []  # whey_protein, creatine, none
    supplements_custom: Optional[str] = None  # Custom supplement text input
    allergies: List[str] = []  # gluten, nuts, dairy, none
    cuisine_preference: Optional[str] = None  # japanese, thai, brazilian, italian, mexican, indian, american, mediterranean

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
    last_sync: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

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

# ==================== WORKOUT ENDPOINTS ====================

@api_router.post("/workouts/generate", response_model=WorkoutProgram)
async def generate_workout(request: WorkoutGenerateRequest):
    """Generate AI-powered workout program"""
    # Get user profile for personalization
    profile = await db.profiles.find_one({"id": request.user_id})
    session_duration = request.duration_minutes if hasattr(request, 'duration_minutes') else 60
    fitness_level = request.fitness_level if hasattr(request, 'fitness_level') else "intermediate"
    
    # Define fitness level parameters
    # Determine rest times based on goal (scientifically optimal)
    rest_times_by_goal = {
        "strength": "180-300",  # 3-5 minutes for strength
        "build_muscle": "90-120",  # 1.5-2 minutes for hypertrophy
        "weight_loss": "30-60",  # Shorter rest for metabolic conditioning
        "endurance": "30-45",  # Short rest for endurance
        "general_fitness": "60-90",
    }
    goal_rest = rest_times_by_goal.get(request.goal, "60-90")
    
    fitness_params = {
        "beginner": {"sets": "2-3", "complexity": "basic compound movements, focus on form"},
        "intermediate": {"sets": "3-4", "complexity": "mix of compound and isolation exercises"},
        "advanced": {"sets": "4-5", "complexity": "advanced techniques, supersets, drop sets"}
    }
    level_info = fitness_params.get(fitness_level, fitness_params["intermediate"])
    
    prompt = f"""Create a scientifically-optimized {request.days_per_week}-day per week workout program for someone with the following goals and constraints:

Goal: {request.goal.replace('_', ' ')}
Focus Areas: {', '.join(request.focus_areas)}
Available Equipment: {', '.join(request.equipment)}
Injuries/Limitations: {request.injuries or 'None'}
Session Duration: {session_duration} minutes per workout
Fitness Level: {fitness_level.upper()} - {level_info['complexity']}

IMPORTANT SCIENTIFIC GUIDELINES:
- For STRENGTH/POWER goals: Use 180-300 seconds rest between sets (3-5 mins) for full ATP recovery
- For MUSCLE BUILDING (hypertrophy): Use 90-120 seconds rest between sets (1.5-2 mins)
- For WEIGHT LOSS/FAT BURNING: Use 30-60 seconds rest to maintain elevated heart rate
- For ENDURANCE: Use 30-45 seconds rest

Please provide a structured workout program in JSON format with the following structure:
{{
    "name": "Program Name",
    "workout_days": [
        {{
            "day": "Day 1 - Focus Area",
            "focus": "Primary muscle group",
            "duration_minutes": {session_duration},
            "notes": "Tips for this day",
            "exercises": [
                {{
                    "name": "Exercise Name (use common names like: Pull-Up, Bench Press, Barbell Squat, Deadlift, etc.)",
                    "sets": 4,
                    "reps": "8-12",
                    "rest_seconds": {goal_rest.split('-')[0]},
                    "instructions": "Step-by-step instructions on how to perform the exercise correctly with form cues",
                    "muscle_groups": ["primary", "secondary"],
                    "equipment": "equipment needed"
                }}
            ]
        }}
    ]
}}

Requirements:
- Each workout should be approximately {session_duration} minutes
- Include 5-8 exercises per day depending on duration
- Focus on compound movements first, then isolation
- Include proper warm-up notes
- Provide detailed form cues for each exercise
- Use SCIENTIFICALLY OPTIMAL rest times for the goal ({request.goal}): {goal_rest} seconds
- For strength goals: prioritize heavier weights (3-6 reps), longer rest (180-300s)
- For muscle building: moderate weights (8-12 reps), moderate rest (90-120s)
- For fat loss: lighter weights (12-15 reps), minimal rest (30-60s)
- Adjust difficulty for {fitness_level.upper()} level: {level_info['sets']} sets per exercise
- Use standard exercise names that match ExerciseDB (e.g., "Pull-Up" not "Wide Grip Pulldown")"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert personal trainer. Create workout programs in valid JSON format only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content
        
        # Clean the response - remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        workout_data = json.loads(content)
        
        # Add GIF URLs to exercises - fetch from ExerciseDB API
        processed_days = []
        for day in workout_data.get("workout_days", []):
            exercises_with_gifs = []
            for ex in day.get("exercises", []):
                ex_dict = dict(ex)
                # Fetch animated GIF from ExerciseDB API
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
        
    except Exception as e:
        logger.error(f"Workout generation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate workout: {str(e)}")

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

@api_router.get("/exercises/search")
async def search_exercises(search: str = None, muscle: str = None):
    """Search exercises from ExerciseDB"""
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
            
            if muscle:
                # Search by body part/muscle
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
                    params={"limit": 100}
                )
                if response.status_code == 200:
                    exercises = response.json()
            
            elif search:
                # Search by name
                encoded = urllib.parse.quote(search)
                response = await client.get(
                    f"{EXERCISEDB_API_BASE}/exercises/name/{encoded}",
                    headers=headers,
                    params={"limit": 50}
                )
                if response.status_code == 200:
                    exercises = response.json()
            
            # Format response - construct gifUrl using our proxy endpoint
            formatted = []
            for ex in exercises[:100]:  # Increased limit to 100
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
    """Generate AI-powered meal plan based on user's macros"""
    profile = await db.profiles.find_one({"id": request.user_id})
    if not profile or not profile.get("calculated_macros"):
        raise HTTPException(status_code=404, detail="User profile with macros not found. Please set up your profile first.")
    
    macros = profile["calculated_macros"]
    
    # Build supplements string including custom text
    supplements_str = ', '.join(request.supplements) if request.supplements else 'None'
    if request.supplements_custom:
        supplements_str += f", {request.supplements_custom}"
    
    # Cuisine preference
    cuisine_str = f"Preferred Cuisine: {request.cuisine_preference}" if request.cuisine_preference else "No specific cuisine preference"
    
    prompt = f"""Create a 3-day meal plan with these macros:
- Calories: {macros['calories']} kcal, Protein: {macros['protein']}g, Carbs: {macros['carbs']}g, Fats: {macros['fats']}g

Preferences: {request.food_preferences}
{cuisine_str}
Allergies: {', '.join(request.allergies) if request.allergies else 'None'}

Return JSON only:
{{"name": "Plan Name", "meal_days": [{{"day": "Day 1", "total_calories": {macros['calories']}, "total_protein": {macros['protein']}, "total_carbs": {macros['carbs']}, "total_fats": {macros['fats']}, "meals": [{{"id": "m1", "name": "Meal", "meal_type": "breakfast", "ingredients": ["item"], "instructions": "steps", "calories": 400, "protein": 30, "carbs": 40, "fats": 15, "prep_time_minutes": 10}}]}}]}}

Include 4 meals per day (breakfast, lunch, dinner, snack). Match macros within 10%."""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert nutritionist. Create meal plans in valid JSON format only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        content = response.choices[0].message.content
        
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        meal_data = json.loads(content)
        
        meal_plan = MealPlan(
            user_id=request.user_id,
            name=meal_data.get("name", "Custom Meal Plan"),
            food_preferences=request.food_preferences,
            supplements=request.supplements,
            supplements_custom=request.supplements_custom,
            allergies=request.allergies,
            cuisine_preference=request.cuisine_preference,
            target_calories=macros['calories'],
            target_protein=macros['protein'],
            target_carbs=macros['carbs'],
            target_fats=macros['fats'],
            meal_days=[MealDay(**day) for day in meal_data.get("meal_days", [])]
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
    """Generate an alternate meal for a specific meal in a meal plan"""
    plan = await db.mealplans.find_one({"id": request.meal_plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    
    try:
        current_meal = plan["meal_days"][request.day_index]["meals"][request.meal_index]
    except (IndexError, KeyError):
        raise HTTPException(status_code=400, detail="Invalid day or meal index")
    
    profile = await db.profiles.find_one({"id": request.user_id})
    macros = profile.get("calculated_macros", {}) if profile else {}
    
    prompt = f"""Generate an alternate meal to replace this one:
Current Meal: {current_meal.get('name')} ({current_meal.get('meal_type')})
Target Macros: {current_meal.get('calories')} cal, {current_meal.get('protein')}g protein, {current_meal.get('carbs')}g carbs, {current_meal.get('fats')}g fats
Food Preferences: {plan.get('food_preferences', 'none')}
Allergies: {', '.join(plan.get('allergies', [])) or 'None'}
Additional preferences: {request.preferences or 'None'}

Respond with valid JSON only:
{{"id": "unique_id", "name": "Meal Name", "meal_type": "{current_meal.get('meal_type')}", "ingredients": ["ingredient 1", "ingredient 2"], "instructions": "How to prepare", "calories": {current_meal.get('calories', 400)}, "protein": {current_meal.get('protein', 30)}, "carbs": {current_meal.get('carbs', 40)}, "fats": {current_meal.get('fats', 15)}, "prep_time_minutes": 15}}"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a nutritionist. Generate a healthy alternate meal with similar macros. Respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        new_meal = json.loads(content)
        new_meal["id"] = str(uuid.uuid4())
        
        return {"alternate_meal": new_meal}
        
    except Exception as e:
        logger.error(f"Alternate meal generation error: {e}")
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

@api_router.get("/food/favorites/{user_id}")
async def get_favorite_meals(user_id: str):
    """Get user's favorite meals"""
    favorites = await db.favorite_meals.find({"user_id": user_id}).sort("created_at", -1).to_list(100)
    return favorites

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
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are a nutrition expert. Analyze the food image and provide accurate nutritional information.
Consider any additional context provided by the user (e.g., portion size, specific ingredients).
Respond with ONLY valid JSON, no other text. Use this exact format:
{"food_name": "Name", "serving_size": "1 serving", "calories": 300, "protein": 25.0, "carbs": 30.0, "fats": 10.0, "fiber": 5.0, "sugar": 8.0, "sodium": 400.0}"""
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{request.image_base64}"}
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        logger.info(f"Food analysis raw response length: {len(content) if content else 0}")
        
        if not content or len(content.strip()) == 0:
            raise HTTPException(status_code=500, detail="AI returned empty response. Please try again with a clearer food image.")
        
        # Clean markdown code blocks if present
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
    except openai.BadRequestError as e:
        logger.error(f"OpenAI BadRequestError: {e}")
        raise HTTPException(status_code=400, detail="Invalid image format. Please use a valid JPEG or PNG image.")
    except Exception as e:
        logger.error(f"Food analysis error: {e}")
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
    """Search comprehensive foods database - similar to MyFitnessPal"""
    # Comprehensive foods database with accurate nutritional data
    common_foods = [
        # Proteins
        {"name": "Chicken Breast, Grilled (100g)", "calories": 165, "protein": 31, "carbs": 0, "fats": 3.6, "fiber": 0, "sugar": 0},
        {"name": "Chicken Breast, Raw (100g)", "calories": 120, "protein": 23, "carbs": 0, "fats": 2.6, "fiber": 0, "sugar": 0},
        {"name": "Chicken Thigh, Boneless (100g)", "calories": 209, "protein": 26, "carbs": 0, "fats": 11, "fiber": 0, "sugar": 0},
        {"name": "Salmon, Atlantic (100g)", "calories": 208, "protein": 20, "carbs": 0, "fats": 13, "fiber": 0, "sugar": 0},
        {"name": "Salmon, Smoked (100g)", "calories": 117, "protein": 18, "carbs": 0, "fats": 4.3, "fiber": 0, "sugar": 0},
        {"name": "Beef Steak, Sirloin (100g)", "calories": 271, "protein": 26, "carbs": 0, "fats": 18, "fiber": 0, "sugar": 0},
        {"name": "Beef, Ground 85% Lean (100g)", "calories": 250, "protein": 26, "carbs": 0, "fats": 15, "fiber": 0, "sugar": 0},
        {"name": "Beef, Ground 93% Lean (100g)", "calories": 170, "protein": 26, "carbs": 0, "fats": 7, "fiber": 0, "sugar": 0},
        {"name": "Turkey Breast, Sliced (100g)", "calories": 104, "protein": 17, "carbs": 4.2, "fats": 1.7, "fiber": 0, "sugar": 2},
        {"name": "Pork Chop, Bone-In (100g)", "calories": 231, "protein": 25, "carbs": 0, "fats": 14, "fiber": 0, "sugar": 0},
        {"name": "Tuna, Canned in Water (100g)", "calories": 116, "protein": 26, "carbs": 0, "fats": 0.8, "fiber": 0, "sugar": 0},
        {"name": "Shrimp, Cooked (100g)", "calories": 99, "protein": 24, "carbs": 0.2, "fats": 0.3, "fiber": 0, "sugar": 0},
        {"name": "Cod, Baked (100g)", "calories": 105, "protein": 23, "carbs": 0, "fats": 0.9, "fiber": 0, "sugar": 0},
        {"name": "Tilapia, Cooked (100g)", "calories": 128, "protein": 26, "carbs": 0, "fats": 2.7, "fiber": 0, "sugar": 0},
        {"name": "Tofu, Firm (100g)", "calories": 144, "protein": 17, "carbs": 3, "fats": 8, "fiber": 2, "sugar": 0},
        {"name": "Tempeh (100g)", "calories": 192, "protein": 20, "carbs": 8, "fats": 11, "fiber": 7, "sugar": 0},
        
        # Eggs & Dairy
        {"name": "Egg, Large Whole", "calories": 72, "protein": 6, "carbs": 0.4, "fats": 5, "fiber": 0, "sugar": 0.4},
        {"name": "Egg White, Large", "calories": 17, "protein": 3.6, "carbs": 0.2, "fats": 0.1, "fiber": 0, "sugar": 0.2},
        {"name": "Egg Yolk, Large", "calories": 55, "protein": 2.7, "carbs": 0.6, "fats": 4.5, "fiber": 0, "sugar": 0.1},
        {"name": "Greek Yogurt, Plain, Nonfat (170g)", "calories": 100, "protein": 17, "carbs": 6, "fats": 0.7, "fiber": 0, "sugar": 4},
        {"name": "Greek Yogurt, 2% Fat (170g)", "calories": 150, "protein": 15, "carbs": 8, "fats": 6, "fiber": 0, "sugar": 6},
        {"name": "Cottage Cheese, Low Fat (1 cup)", "calories": 163, "protein": 28, "carbs": 6, "fats": 2.3, "fiber": 0, "sugar": 6},
        {"name": "Cottage Cheese, Full Fat (1 cup)", "calories": 220, "protein": 25, "carbs": 8, "fats": 10, "fiber": 0, "sugar": 6},
        {"name": "Milk, Whole (1 cup)", "calories": 149, "protein": 8, "carbs": 12, "fats": 8, "fiber": 0, "sugar": 12},
        {"name": "Milk, 2% (1 cup)", "calories": 122, "protein": 8, "carbs": 12, "fats": 5, "fiber": 0, "sugar": 12},
        {"name": "Milk, Skim (1 cup)", "calories": 83, "protein": 8, "carbs": 12, "fats": 0.2, "fiber": 0, "sugar": 12},
        {"name": "Almond Milk, Unsweetened (1 cup)", "calories": 30, "protein": 1, "carbs": 1, "fats": 2.5, "fiber": 0, "sugar": 0},
        {"name": "Oat Milk (1 cup)", "calories": 120, "protein": 3, "carbs": 16, "fats": 5, "fiber": 2, "sugar": 7},
        {"name": "Cheddar Cheese (1 oz)", "calories": 113, "protein": 7, "carbs": 0.4, "fats": 9, "fiber": 0, "sugar": 0.1},
        {"name": "Mozzarella Cheese (1 oz)", "calories": 85, "protein": 6, "carbs": 0.6, "fats": 6, "fiber": 0, "sugar": 0.2},
        {"name": "Parmesan Cheese, Grated (1 tbsp)", "calories": 22, "protein": 2, "carbs": 0.2, "fats": 1.5, "fiber": 0, "sugar": 0},
        {"name": "Cream Cheese (1 oz)", "calories": 99, "protein": 2, "carbs": 1, "fats": 10, "fiber": 0, "sugar": 0.5},
        
        # Carbohydrates
        {"name": "White Rice, Cooked (1 cup)", "calories": 206, "protein": 4.3, "carbs": 45, "fats": 0.4, "fiber": 0.6, "sugar": 0},
        {"name": "Brown Rice, Cooked (1 cup)", "calories": 216, "protein": 5, "carbs": 45, "fats": 1.8, "fiber": 3.5, "sugar": 0},
        {"name": "Jasmine Rice, Cooked (1 cup)", "calories": 205, "protein": 4.2, "carbs": 45, "fats": 0.4, "fiber": 0.6, "sugar": 0},
        {"name": "Quinoa, Cooked (1 cup)", "calories": 222, "protein": 8, "carbs": 39, "fats": 3.5, "fiber": 5, "sugar": 2},
        {"name": "Oatmeal, Cooked (1 cup)", "calories": 158, "protein": 6, "carbs": 27, "fats": 3.2, "fiber": 4, "sugar": 1},
        {"name": "Sweet Potato, Baked (1 medium)", "calories": 103, "protein": 2.3, "carbs": 24, "fats": 0.1, "fiber": 4, "sugar": 7},
        {"name": "White Potato, Baked (1 medium)", "calories": 161, "protein": 4, "carbs": 37, "fats": 0.2, "fiber": 4, "sugar": 2},
        {"name": "Pasta, Cooked (1 cup)", "calories": 221, "protein": 8, "carbs": 43, "fats": 1.3, "fiber": 2.5, "sugar": 1},
        {"name": "Whole Wheat Pasta, Cooked (1 cup)", "calories": 174, "protein": 7.5, "carbs": 37, "fats": 0.8, "fiber": 6, "sugar": 1},
        {"name": "Bread, White (1 slice)", "calories": 79, "protein": 2.7, "carbs": 15, "fats": 1, "fiber": 0.6, "sugar": 1.5},
        {"name": "Bread, Whole Wheat (1 slice)", "calories": 81, "protein": 4, "carbs": 14, "fats": 1, "fiber": 2, "sugar": 1.5},
        {"name": "Tortilla, Flour (1 medium)", "calories": 144, "protein": 4, "carbs": 24, "fats": 3.5, "fiber": 1.5, "sugar": 1},
        {"name": "Tortilla, Corn (1 medium)", "calories": 52, "protein": 1.4, "carbs": 11, "fats": 0.7, "fiber": 1.5, "sugar": 0.2},
        
        # Fruits
        {"name": "Banana (1 medium)", "calories": 105, "protein": 1.3, "carbs": 27, "fats": 0.4, "fiber": 3, "sugar": 14},
        {"name": "Apple (1 medium)", "calories": 95, "protein": 0.5, "carbs": 25, "fats": 0.3, "fiber": 4.4, "sugar": 19},
        {"name": "Orange (1 medium)", "calories": 62, "protein": 1.2, "carbs": 15, "fats": 0.2, "fiber": 3, "sugar": 12},
        {"name": "Strawberries (1 cup)", "calories": 49, "protein": 1, "carbs": 12, "fats": 0.5, "fiber": 3, "sugar": 7},
        {"name": "Blueberries (1 cup)", "calories": 84, "protein": 1.1, "carbs": 21, "fats": 0.5, "fiber": 4, "sugar": 15},
        {"name": "Grapes (1 cup)", "calories": 104, "protein": 1.1, "carbs": 27, "fats": 0.2, "fiber": 1.4, "sugar": 23},
        {"name": "Mango (1 cup, diced)", "calories": 99, "protein": 1.4, "carbs": 25, "fats": 0.6, "fiber": 3, "sugar": 23},
        {"name": "Pineapple (1 cup, chunks)", "calories": 82, "protein": 0.9, "carbs": 22, "fats": 0.2, "fiber": 2.3, "sugar": 16},
        {"name": "Watermelon (1 cup, diced)", "calories": 46, "protein": 0.9, "carbs": 12, "fats": 0.2, "fiber": 0.6, "sugar": 9},
        {"name": "Avocado (1 whole)", "calories": 322, "protein": 4, "carbs": 17, "fats": 29, "fiber": 13, "sugar": 1},
        {"name": "Avocado (1/2)", "calories": 161, "protein": 2, "carbs": 8.5, "fats": 14.5, "fiber": 6.5, "sugar": 0.5},
        
        # Vegetables
        {"name": "Broccoli, Steamed (1 cup)", "calories": 55, "protein": 3.7, "carbs": 11, "fats": 0.6, "fiber": 5, "sugar": 2},
        {"name": "Spinach, Raw (1 cup)", "calories": 7, "protein": 0.9, "carbs": 1.1, "fats": 0.1, "fiber": 0.7, "sugar": 0.1},
        {"name": "Spinach, Cooked (1 cup)", "calories": 41, "protein": 5, "carbs": 7, "fats": 0.5, "fiber": 4, "sugar": 1},
        {"name": "Kale, Raw (1 cup)", "calories": 33, "protein": 2.9, "carbs": 6, "fats": 0.6, "fiber": 2.6, "sugar": 1.6},
        {"name": "Carrots, Raw (1 medium)", "calories": 25, "protein": 0.6, "carbs": 6, "fats": 0.1, "fiber": 1.7, "sugar": 3},
        {"name": "Bell Pepper, Red (1 medium)", "calories": 37, "protein": 1.2, "carbs": 7, "fats": 0.4, "fiber": 2.5, "sugar": 5},
        {"name": "Tomato (1 medium)", "calories": 22, "protein": 1.1, "carbs": 5, "fats": 0.2, "fiber": 1.5, "sugar": 3},
        {"name": "Cucumber (1 cup, sliced)", "calories": 16, "protein": 0.7, "carbs": 4, "fats": 0.1, "fiber": 0.5, "sugar": 2},
        {"name": "Zucchini (1 medium)", "calories": 33, "protein": 2.4, "carbs": 6, "fats": 0.6, "fiber": 2, "sugar": 5},
        {"name": "Asparagus (6 spears)", "calories": 20, "protein": 2.2, "carbs": 4, "fats": 0.1, "fiber": 2, "sugar": 1},
        {"name": "Green Beans (1 cup)", "calories": 31, "protein": 1.8, "carbs": 7, "fats": 0.1, "fiber": 2.7, "sugar": 3},
        {"name": "Cauliflower (1 cup)", "calories": 25, "protein": 2, "carbs": 5, "fats": 0.3, "fiber": 2, "sugar": 2},
        {"name": "Mushrooms, White (1 cup)", "calories": 15, "protein": 2.2, "carbs": 2, "fats": 0.2, "fiber": 0.7, "sugar": 1},
        {"name": "Onion (1 medium)", "calories": 44, "protein": 1.2, "carbs": 10, "fats": 0.1, "fiber": 1.9, "sugar": 5},
        
        # Nuts & Seeds
        {"name": "Almonds (1 oz, 23 nuts)", "calories": 164, "protein": 6, "carbs": 6, "fats": 14, "fiber": 3.5, "sugar": 1},
        {"name": "Peanuts (1 oz)", "calories": 161, "protein": 7, "carbs": 5, "fats": 14, "fiber": 2.4, "sugar": 1},
        {"name": "Cashews (1 oz)", "calories": 157, "protein": 5, "carbs": 9, "fats": 12, "fiber": 0.9, "sugar": 2},
        {"name": "Walnuts (1 oz)", "calories": 185, "protein": 4, "carbs": 4, "fats": 18, "fiber": 2, "sugar": 1},
        {"name": "Peanut Butter (2 tbsp)", "calories": 188, "protein": 8, "carbs": 6, "fats": 16, "fiber": 2, "sugar": 3},
        {"name": "Almond Butter (2 tbsp)", "calories": 196, "protein": 7, "carbs": 6, "fats": 18, "fiber": 3, "sugar": 2},
        {"name": "Chia Seeds (1 oz)", "calories": 138, "protein": 5, "carbs": 12, "fats": 9, "fiber": 10, "sugar": 0},
        {"name": "Flax Seeds (1 tbsp)", "calories": 37, "protein": 1.3, "carbs": 2, "fats": 3, "fiber": 2, "sugar": 0},
        {"name": "Sunflower Seeds (1 oz)", "calories": 165, "protein": 5.5, "carbs": 7, "fats": 14, "fiber": 3, "sugar": 1},
        {"name": "Pumpkin Seeds (1 oz)", "calories": 151, "protein": 7, "carbs": 5, "fats": 13, "fiber": 1.7, "sugar": 0},
        
        # Fats & Oils
        {"name": "Olive Oil (1 tbsp)", "calories": 119, "protein": 0, "carbs": 0, "fats": 13.5, "fiber": 0, "sugar": 0},
        {"name": "Coconut Oil (1 tbsp)", "calories": 121, "protein": 0, "carbs": 0, "fats": 13.5, "fiber": 0, "sugar": 0},
        {"name": "Butter (1 tbsp)", "calories": 102, "protein": 0.1, "carbs": 0, "fats": 11.5, "fiber": 0, "sugar": 0},
        
        # Fast Food & Restaurant
        {"name": "McDonald's Big Mac", "calories": 563, "protein": 26, "carbs": 44, "fats": 33, "fiber": 3, "sugar": 9},
        {"name": "McDonald's McChicken", "calories": 400, "protein": 14, "carbs": 41, "fats": 21, "fiber": 2, "sugar": 5},
        {"name": "McDonald's French Fries, Medium", "calories": 320, "protein": 5, "carbs": 43, "fats": 15, "fiber": 4, "sugar": 0},
        {"name": "McDonald's Egg McMuffin", "calories": 310, "protein": 17, "carbs": 30, "fats": 13, "fiber": 2, "sugar": 3},
        {"name": "Chipotle Chicken Burrito Bowl", "calories": 665, "protein": 52, "carbs": 47, "fats": 25, "fiber": 11, "sugar": 6},
        {"name": "Chipotle Steak Burrito", "calories": 945, "protein": 55, "carbs": 92, "fats": 36, "fiber": 13, "sugar": 9},
        {"name": "Subway 6\" Turkey Sub", "calories": 280, "protein": 18, "carbs": 46, "fats": 3.5, "fiber": 5, "sugar": 7},
        {"name": "Starbucks Caffe Latte, Grande", "calories": 190, "protein": 13, "carbs": 18, "fats": 7, "fiber": 0, "sugar": 17},
        {"name": "Starbucks Cappuccino, Grande", "calories": 120, "protein": 8, "carbs": 12, "fats": 4, "fiber": 0, "sugar": 10},
        {"name": "Pizza, Pepperoni (1 slice)", "calories": 298, "protein": 13, "carbs": 34, "fats": 12, "fiber": 2, "sugar": 4},
        {"name": "Pizza, Cheese (1 slice)", "calories": 272, "protein": 12, "carbs": 34, "fats": 10, "fiber": 2, "sugar": 4},
        
        # Supplements & Shakes
        {"name": "Whey Protein Shake (1 scoop)", "calories": 120, "protein": 24, "carbs": 3, "fats": 1, "fiber": 0, "sugar": 1},
        {"name": "Casein Protein (1 scoop)", "calories": 120, "protein": 24, "carbs": 3, "fats": 1, "fiber": 0, "sugar": 1},
        {"name": "Mass Gainer Shake (1 serving)", "calories": 650, "protein": 50, "carbs": 85, "fats": 10, "fiber": 5, "sugar": 15},
        {"name": "Protein Bar, Average", "calories": 200, "protein": 20, "carbs": 22, "fats": 7, "fiber": 3, "sugar": 5},
        
        # Snacks
        {"name": "Rice Cakes (1 cake)", "calories": 35, "protein": 0.7, "carbs": 7, "fats": 0.3, "fiber": 0.4, "sugar": 0},
        {"name": "Popcorn, Air-Popped (3 cups)", "calories": 93, "protein": 3, "carbs": 19, "fats": 1, "fiber": 3.6, "sugar": 0},
        {"name": "Dark Chocolate (1 oz)", "calories": 170, "protein": 2, "carbs": 13, "fats": 12, "fiber": 3, "sugar": 7},
        {"name": "Hummus (2 tbsp)", "calories": 50, "protein": 2, "carbs": 4, "fats": 3, "fiber": 1, "sugar": 0},
        {"name": "Trail Mix (1 oz)", "calories": 131, "protein": 4, "carbs": 13, "fats": 8, "fiber": 2, "sugar": 6},
        
        # Beverages
        {"name": "Orange Juice (1 cup)", "calories": 112, "protein": 2, "carbs": 26, "fats": 0.5, "fiber": 0.5, "sugar": 21},
        {"name": "Apple Juice (1 cup)", "calories": 114, "protein": 0.2, "carbs": 28, "fats": 0.3, "fiber": 0.5, "sugar": 24},
        {"name": "Coca-Cola (12 oz)", "calories": 140, "protein": 0, "carbs": 39, "fats": 0, "fiber": 0, "sugar": 39},
        {"name": "Gatorade (20 oz)", "calories": 140, "protein": 0, "carbs": 36, "fats": 0, "fiber": 0, "sugar": 34},
        {"name": "Coffee, Black (8 oz)", "calories": 2, "protein": 0.3, "carbs": 0, "fats": 0, "fiber": 0, "sugar": 0},
        {"name": "Green Tea, Unsweetened (8 oz)", "calories": 2, "protein": 0, "carbs": 0, "fats": 0, "fiber": 0, "sugar": 0},
    ]
    
    query_lower = query.lower()
    results = [food for food in common_foods if query_lower in food["name"].lower()]
    
    # If no exact matches, try partial matching
    if not results:
        results = [food for food in common_foods if any(word in food["name"].lower() for word in query_lower.split())]
    
    return results[:20]  # Return up to 20 results

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
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        ai_response = response.choices[0].message.content
        
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
async def save_chat_message(message_id: str):
    """Save/bookmark a chat message"""
    result = await db.chat_history.update_one({"id": message_id}, {"$set": {"saved": True}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message saved successfully"}

@api_router.post("/chat/unsave/{message_id}")
async def unsave_chat_message(message_id: str):
    """Unsave/unbookmark a chat message"""
    result = await db.chat_history.update_one({"id": message_id}, {"$set": {"saved": False}})
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
    return [DeviceConnection(**d) for d in devices]

@api_router.post("/devices/connect")
async def connect_device(user_id: str, device_type: str):
    """Connect a fitness device (placeholder for actual device OAuth)"""
    # In production, this would initiate OAuth flow with the device provider
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
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are a professional fitness coach and body composition expert. 
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
}"""
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Please analyze these before and after progress photos taken over {request.time_period}. Provide detailed feedback on the visible transformation."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{request.before_image_base64}"}
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{request.after_image_base64}"}
                        }
                    ]
                }
            ],
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        
        # Clean markdown code blocks if present
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
