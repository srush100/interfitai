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

# Exercise GIF mapping - using ExerciseDB style URLs
EXERCISE_GIFS = {
    "bench press": "https://images.ctfassets.net/4xhc7g6uowz1/6l1n19ORY2qxpqS4mxefGg/3c7c86f8fee41e99f5d4e1ef8cfc5ebb/bench_press.gif",
    "squat": "https://images.ctfassets.net/4xhc7g6uowz1/4qzl7HL0Z2xyP8eFTPzJXu/b66e5f46e5d9aec7cd3fe04ec3a75d8e/squat.gif",
    "deadlift": "https://images.ctfassets.net/4xhc7g6uowz1/2d2p4R8CRmwkY6C2y4xJhV/6f8c89c94c8e39e4b8c76d8f8d4e6e4a/deadlift.gif",
    "pull up": "https://images.ctfassets.net/4xhc7g6uowz1/1Yj1kz5v2M8K0wE8qYqEyS/a7f3c89c94c8e39e4b8c76d8f8d4e6e4a/pullup.gif",
    "push up": "https://images.ctfassets.net/4xhc7g6uowz1/3Xj2kz5v2M8K0wE8qYqEyS/b8f4c89c94c8e39e4b8c76d8f8d4e6e4a/pushup.gif",
    "lat pulldown": "https://images.ctfassets.net/4xhc7g6uowz1/4Zj3kz5v2M8K0wE8qYqEyS/c9f5c89c94c8e39e4b8c76d8f8d4e6e4a/latpulldown.gif",
    "shoulder press": "https://images.ctfassets.net/4xhc7g6uowz1/5Aj4kz5v2M8K0wE8qYqEyS/d0f6c89c94c8e39e4b8c76d8f8d4e6e4a/shoulderpress.gif",
    "bicep curl": "https://images.ctfassets.net/4xhc7g6uowz1/6Bj5kz5v2M8K0wE8qYqEyS/e1f7c89c94c8e39e4b8c76d8f8d4e6e4a/bicepcurl.gif",
    "tricep": "https://images.ctfassets.net/4xhc7g6uowz1/7Cj6kz5v2M8K0wE8qYqEyS/f2f8c89c94c8e39e4b8c76d8f8d4e6e4a/tricep.gif",
    "row": "https://images.ctfassets.net/4xhc7g6uowz1/8Dj7kz5v2M8K0wE8qYqEyS/g3f9c89c94c8e39e4b8c76d8f8d4e6e4a/row.gif",
    "lunge": "https://images.ctfassets.net/4xhc7g6uowz1/9Ej8kz5v2M8K0wE8qYqEyS/h4f0c89c94c8e39e4b8c76d8f8d4e6e4a/lunge.gif",
    "leg press": "https://images.ctfassets.net/4xhc7g6uowz1/0Fj9kz5v2M8K0wE8qYqEyS/i5f1c89c94c8e39e4b8c76d8f8d4e6e4a/legpress.gif",
    "calf raise": "https://images.ctfassets.net/4xhc7g6uowz1/1Gj0kz5v2M8K0wE8qYqEyS/j6f2c89c94c8e39e4b8c76d8f8d4e6e4a/calfraise.gif",
    "plank": "https://images.ctfassets.net/4xhc7g6uowz1/2Hj1kz5v2M8K0wE8qYqEyS/k7f3c89c94c8e39e4b8c76d8f8d4e6e4a/plank.gif",
    "crunch": "https://images.ctfassets.net/4xhc7g6uowz1/3Ij2kz5v2M8K0wE8qYqEyS/l8f4c89c94c8e39e4b8c76d8f8d4e6e4a/crunch.gif",
    "dumbbell": "https://images.ctfassets.net/4xhc7g6uowz1/4Jj3kz5v2M8K0wE8qYqEyS/m9f5c89c94c8e39e4b8c76d8f8d4e6e4a/dumbbell.gif",
    "cable": "https://images.ctfassets.net/4xhc7g6uowz1/5Kj4kz5v2M8K0wE8qYqEyS/n0f6c89c94c8e39e4b8c76d8f8d4e6e4a/cable.gif",
    "fly": "https://images.ctfassets.net/4xhc7g6uowz1/6Lj5kz5v2M8K0wE8qYqEyS/o1f7c89c94c8e39e4b8c76d8f8d4e6e4a/fly.gif",
    "hip thrust": "https://images.ctfassets.net/4xhc7g6uowz1/7Mj6kz5v2M8K0wE8qYqEyS/p2f8c89c94c8e39e4b8c76d8f8d4e6e4a/hipthrust.gif",
    "glute": "https://images.ctfassets.net/4xhc7g6uowz1/8Nj7kz5v2M8K0wE8qYqEyS/q3f9c89c94c8e39e4b8c76d8f8d4e6e4a/glute.gif",
}

def get_exercise_gif(exercise_name: str) -> Optional[str]:
    """Get GIF URL for an exercise based on name matching"""
    name_lower = exercise_name.lower()
    for key, url in EXERCISE_GIFS.items():
        if key in name_lower:
            return url
    return None

@api_router.post("/workouts/generate", response_model=WorkoutProgram)
async def generate_workout(request: WorkoutGenerateRequest):
    """Generate AI-powered workout program"""
    # Get user profile for personalization
    profile = await db.profiles.find_one({"id": request.user_id})
    session_duration = request.duration_minutes if hasattr(request, 'duration_minutes') else 60
    
    prompt = f"""Create a detailed {request.days_per_week}-day per week workout program for someone with the following goals and constraints:

Goal: {request.goal.replace('_', ' ')}
Focus Areas: {', '.join(request.focus_areas)}
Available Equipment: {', '.join(request.equipment)}
Injuries/Limitations: {request.injuries or 'None'}
Session Duration: {session_duration} minutes per workout

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
                    "name": "Exercise Name",
                    "sets": 4,
                    "reps": "8-12",
                    "rest_seconds": 90,
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
- Make it progressive and appropriate for intermediate fitness level"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert personal trainer and fitness program designer. Always respond with valid JSON only, no additional text."},
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
        
        # Add GIF URLs to exercises
        processed_days = []
        for day in workout_data.get("workout_days", []):
            exercises_with_gifs = []
            for ex in day.get("exercises", []):
                ex_dict = dict(ex)
                ex_dict["gif_url"] = get_exercise_gif(ex.get("name", ""))
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
    
    prompt = f"""Create a 7-day meal plan for someone with the following requirements:

Daily Macros Target (MUST match closely):
- Calories: {macros['calories']} kcal
- Protein: {macros['protein']}g
- Carbs: {macros['carbs']}g
- Fats: {macros['fats']}g

Food Preferences: {request.food_preferences}
{cuisine_str}
Supplements Used: {supplements_str}
Food Allergies/Sensitivities: {', '.join(request.allergies) if request.allergies else 'None'}

Please provide a structured meal plan in JSON format:
{{
    "name": "Meal Plan Name",
    "meal_days": [
        {{
            "day": "Day 1",
            "total_calories": {macros['calories']},
            "total_protein": {macros['protein']},
            "total_carbs": {macros['carbs']},
            "total_fats": {macros['fats']},
            "meals": [
                {{
                    "id": "unique_id",
                    "name": "Meal Name",
                    "meal_type": "breakfast",
                    "ingredients": ["ingredient 1 with amount", "ingredient 2 with amount"],
                    "instructions": "Detailed cooking instructions",
                    "calories": 500,
                    "protein": 30,
                    "carbs": 50,
                    "fats": 15,
                    "prep_time_minutes": 15,
                    "cuisine": "{request.cuisine_preference or 'international'}"
                }}
            ]
        }}
    ]
}}

Requirements:
- Include 4-5 meals per day (breakfast, lunch, dinner, and 1-2 snacks)
- CRITICAL: Daily totals MUST match target macros within 5%
- Include precise ingredient amounts
- Make meals practical, delicious, and varied
- Each meal should have accurate macro calculations
- If cuisine preference specified, align 70% of meals to that cuisine"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert nutritionist and meal planning specialist. Create accurate, macro-aligned meal plans. Always respond with valid JSON only, no additional text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=6000
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
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are a nutrition expert. Analyze the food image and provide accurate nutritional information.
Respond with ONLY valid JSON, no other text. Use this exact format:
{"food_name": "Name", "serving_size": "1 serving", "calories": 300, "protein": 25.0, "carbs": 30.0, "fats": 10.0, "fiber": 5.0, "sugar": 8.0, "sodium": 400.0}"""
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this food image and provide nutritional information in JSON format only:"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{request.image_base64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        content = response.choices[0].message.content
        logger.info(f"Food analysis raw response length: {len(content) if content else 0}")
        
        if not content or len(content.strip()) == 0:
            raise HTTPException(status_code=500, detail="OpenAI returned empty response. Please try again with a clearer food image.")
        
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
        
        food_entry = FoodEntry(
            user_id=request.user_id,
            food_name=food_data.get("food_name", "Unknown Food"),
            serving_size=food_data.get("serving_size", "1 serving"),
            calories=int(food_data.get("calories", 0)),
            protein=float(food_data.get("protein", 0)),
            carbs=float(food_data.get("carbs", 0)),
            fats=float(food_data.get("fats", 0)),
            fiber=float(food_data.get("fiber", 0)),
            sugar=float(food_data.get("sugar", 0)),
            sodium=float(food_data.get("sodium", 0)),
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
    "monthly": {"name": "Monthly", "price": 9.99, "duration_months": 1, "features": ["AI Workouts", "AI Meal Plans", "Food Tracking", "Ask InterFitAI", "Step Tracking"]},
    "quarterly": {"name": "Quarterly", "price": 24.99, "duration_months": 3, "features": ["AI Workouts", "AI Meal Plans", "Food Tracking", "Ask InterFitAI", "Step Tracking", "Priority Support"]},
    "yearly": {"name": "Yearly", "price": 79.99, "duration_months": 12, "features": ["AI Workouts", "AI Meal Plans", "Food Tracking", "Ask InterFitAI", "Step Tracking", "Priority Support", "Exclusive Content"]}
}

@api_router.get("/subscription/plans")
async def get_subscription_plans():
    """Get available subscription plans"""
    return SUBSCRIPTION_PLANS

@api_router.post("/subscription/checkout")
async def create_checkout_session(request: PaymentRequest):
    """Create Stripe checkout session for subscription"""
    if request.plan_id not in SUBSCRIPTION_PLANS:
        raise HTTPException(status_code=400, detail="Invalid plan")
    
    plan = SUBSCRIPTION_PLANS[request.plan_id]
    
    try:
        success_url = f"{request.origin_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{request.origin_url}/subscription"
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': f'InterFitAI {plan["name"]} Subscription',
                        'description': f'{plan["duration_months"]} month(s) access to all premium features'
                    },
                    'unit_amount': int(plan["price"] * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
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
