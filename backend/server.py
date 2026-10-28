from fastapi import FastAPI, APIRouter, HTTPException, Request
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
import math
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
import asyncio
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

# ==================== TRANSACTIONAL EMAIL (Resend) ====================
async def send_email(to: str, subject: str, html: str) -> bool:
    """Send one transactional email via Resend. Never raises — returns False on
    failure so callers (e.g. signup) are never blocked by email problems."""
    if not RESEND_API_KEY:
        logger.warning(f"Email skipped (no RESEND_API_KEY): '{subject}' -> {to}")
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                         "Content-Type": "application/json"},
                json={"from": MAIL_FROM, "to": [to], "subject": subject, "html": html},
            )
        if resp.status_code >= 400:
            logger.error(f"Resend error {resp.status_code} for '{subject}': {resp.text[:300]}")
            return False
        return True
    except Exception as e:
        logger.error(f"Email send failed for '{subject}' -> {to}: {e}")
        return False

def _email_shell(inner: str) -> str:
    """Branded black/gold InterFitAI wrapper. Inline styles only (email-safe)."""
    return f"""<!doctype html><html><body style="margin:0;padding:0;background:#000000;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#000000;padding:32px 0;">
  <tr><td align="center">
    <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background:#111111;border-radius:16px;border:1px solid #262626;overflow:hidden;">
      <tr><td align="center" style="padding:32px 32px 8px;">
        <div style="font-size:26px;font-weight:800;letter-spacing:1px;color:#ffffff;font-family:Arial,Helvetica,sans-serif;">
          INTERFIT<span style="color:#FFD700;">AI</span>
        </div>
      </td></tr>
      <tr><td style="padding:8px 32px 32px;font-family:Arial,Helvetica,sans-serif;color:#d4d4d4;font-size:15px;line-height:1.6;">
        {inner}
      </td></tr>
      <tr><td style="padding:20px 32px;border-top:1px solid #262626;font-family:Arial,Helvetica,sans-serif;color:#737373;font-size:12px;line-height:1.5;">
        You're receiving this because you have an InterFitAI account.<br>
        Need help? Contact {APP_SUPPORT_EMAIL}.
      </td></tr>
    </table>
  </td></tr>
</table></body></html>"""

def welcome_email_html(name: str) -> str:
    greeting = f"Welcome, {name}!" if name and name.strip() else "Welcome!"
    return _email_shell(f"""
        <h1 style="color:#ffffff;font-size:22px;margin:0 0 16px;">{greeting}</h1>
        <p style="margin:0 0 16px;">Your account is ready. InterFitAI builds elite, fully personalised training programs and meal plans around your goals, equipment and preferences — and adapts as you progress.</p>
        <p style="margin:0 0 8px;color:#ffffff;font-weight:700;">To get started:</p>
        <ul style="margin:0 0 16px;padding-left:20px;">
          <li style="margin-bottom:6px;">Generate your first workout program</li>
          <li style="margin-bottom:6px;">Create a meal plan matched to your macros</li>
          <li style="margin-bottom:6px;">Log food by search, photo, or AI</li>
        </ul>
        <p style="margin:0;">Let's get to work. 💪</p>
    """)

def reset_code_email_html(code: str) -> str:
    return _email_shell(f"""
        <h1 style="color:#ffffff;font-size:22px;margin:0 0 16px;">Reset your password</h1>
        <p style="margin:0 0 20px;">Enter this code in the app to set a new password. It expires in 15 minutes.</p>
        <div style="text-align:center;margin:0 0 20px;">
          <span style="display:inline-block;font-size:34px;font-weight:800;letter-spacing:10px;color:#FFD700;background:#000000;border:1px solid #333;border-radius:12px;padding:16px 28px;font-family:'Courier New',monospace;">{code}</span>
        </div>
        <p style="margin:0;color:#a3a3a3;font-size:13px;">If you didn't request this, you can safely ignore this email — your password won't change.</p>
    """)


# OpenAI configuration (kept for fallback/vision)
openai.api_key = os.environ.get('OPENAI_API_KEY', '')

# Claude via Emergent LLM Key
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Models — set in the environment to switch without a code change
# (e.g. back to claude-sonnet-4-5-20250929 / claude-haiku-4-5-20251001).
CLAUDE_SONNET_MODEL = os.environ.get('CLAUDE_SONNET_MODEL', 'claude-sonnet-5-5')
CLAUDE_HAIKU_MODEL = os.environ.get('CLAUDE_HAIKU_MODEL', 'claude-haiku-5-5')
# Sonnet 5.5 / Haiku 5.5 think before answering, and that thinking counts toward
# max_tokens — extra room so long JSON answers (meal plans, programs) aren't cut off.
SONNET_THINKING_HEADROOM = 4000
HAIKU_THINKING_HEADROOM = 2000

async def call_claude_sonnet(
    system_message: str,
    user_message: str,
    temperature: float = 0.7,
    max_tokens: int = 2500,
    image_base64: str = None,
    image_base64_2: str = None
) -> str:
    """Call Claude Sonnet (5.5 by default) via emergentintegrations - for complex
    generation and vision tasks. `temperature` is accepted for older callers but not
    sent: Sonnet 5.5 rejects non-default sampling settings."""
    chat = (
        LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message=system_message,
        )
        .with_model("anthropic", CLAUDE_SONNET_MODEL)
        .with_params(max_tokens=max_tokens + SONNET_THINKING_HEADROOM, timeout=240)
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
    """Call Claude Haiku (5.5 by default) via emergentintegrations - for fast,
    lightweight tasks. `temperature` is accepted for older callers but not sent:
    Haiku 5.5 rejects non-default sampling settings."""
    chat = (
        LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=str(uuid.uuid4()),
            system_message=system_message,
        )
        .with_model("anthropic", CLAUDE_HAIKU_MODEL)
        .with_params(max_tokens=max_tokens + HAIKU_THINKING_HEADROOM, timeout=90)
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
STRIPE_SECRET_KEY = os.environ.get('STRIPE_API_KEY', '')

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
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "InterFitAI <onboarding@resend.dev>")
APP_SUPPORT_EMAIL = "srush@interfitai.com"
EXERCISEDB_API_HOST = "exercisedb.p.rapidapi.com"
EXERCISEDB_API_BASE = "https://exercisedb.p.rapidapi.com"

# USDA FoodData Central API (free, no IP restrictions)
USDA_API_KEY = os.environ.get("USDA_API_KEY", "DEMO_KEY")
USDA_API_BASE = "https://api.nal.usda.gov/fdc/v1"

async def search_usda(query: str, max_results: int = 50, branded: bool = True):
    """Search USDA FoodData Central database (free, no IP restrictions).
    branded=False leaves out USDA's brand list, which only has US products."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{USDA_API_BASE}/foods/search",
                params={
                    "api_key": USDA_API_KEY,
                    "query": query,
                    "pageSize": max_results,
                    "dataType": (["Branded"] if branded else []) + ["Foundation", "SR Legacy"]
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
                # Energy is listed twice for many foods (kcal and kJ) under the
                # same name; keeping the last one showed kJ as calories
                # (boiled broccoli 146 "cal"). Use kcal, else convert kJ.
                nutrients, kcal, kj = {}, None, None
                for n in food.get("foodNutrients", []):
                    name, unit = n.get("nutrientName", ""), str(n.get("unitName", "")).upper()
                    value = float(n.get("value") or 0)
                    if name.startswith("Energy"):
                        if unit == "KCAL" and kcal is None:
                            kcal = value
                        elif unit == "KJ" and kj is None:
                            kj = value
                    else:
                        nutrients.setdefault(name, value)
                calories = kcal if kcal is not None else round(kj / 4.184) if kj else 0
                protein = nutrients.get("Protein", 0)
                carbs = nutrients.get("Carbohydrate, by difference", 0)
                fats = nutrients.get("Total lipid (fat)", 0)
                
                # Search results give nutrients per 100 g (or 100 ml) for every
                # data type. A branded food's label serving ("45g") is shown,
                # so its numbers are scaled to that serving to match the label.
                base_g, unit = 100.0, "g"
                try:
                    serving = float(food.get("servingSize") or 0)
                except (TypeError, ValueError):
                    serving = 0
                serving_unit = str(food.get("servingSizeUnit") or "").lower()
                serving_unit = {"grm": "g", "gm": "g", "mlt": "ml", "mlit": "ml"}.get(serving_unit, serving_unit)
                if food.get("dataType") == "Branded" and serving > 0 and serving_unit in ("g", "ml"):
                    base_g, unit = round(serving, 1), serving_unit
                factor = base_g / 100.0
                base_txt = f"{int(base_g) if float(base_g).is_integer() else base_g}{unit}"

                brand = food.get("brandName", "") or food.get("brandOwner", "")
                food_name = food.get("description", "Unknown")

                # Clean up the name
                if brand and brand.lower() not in food_name.lower():
                    display_name = f"{brand} - {food_name}"
                else:
                    display_name = food_name

                results.append({
                    "name": f"{display_name} ({base_txt})",
                    "brand": brand,
                    "calories": round(calories * factor, 0),
                    "protein": round(protein * factor, 1),
                    "carbs": round(carbs * factor, 1),
                    "fats": round(fats * factor, 1),
                    "serving_g": base_g,
                    "serving_unit": unit,
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
    "knee push up": "3211",           # kneeling push-up
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
    "wide grip pull up": "1429",      # wide grip pull-up
    "wide grip pull-up": "1429",      # wide grip pull-up
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
    "rear delt fly": "0602",          # lever seated reverse fly (reverse pec deck)
    "rear delt machine fly": "0602",  # lever seated reverse fly (reverse pec deck)
    "reverse fly": "0602",            # lever seated reverse fly (machine version as default)
    "rear delt": "0602",              # lever seated reverse fly (machine version as default)
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
    "tricep extension": "0430",       # dumbbell standing triceps extension
    "overhead tricep extension": "0092",   # barbell seated overhead tricep extension
    "dumbbell tricep extension": "0430",  # dumbbell standing triceps extension
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
    "leg raise": "0620",              # lying leg raise flat bench
    "lying leg raise": "0620",        # lying leg raise flat bench
    "hanging leg raise": "0472",       # FIXED: was 1760 (dumbbell goblet squat). 0472 = hanging leg raise
    "hanging knee raise": "0011",     # assisted hanging knee raise
    "knee raise": "0011",             # assisted hanging knee raise
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
    "broadjump": "1472",               # forward jump (broad jump)
    "kettlebell swing": "0549",
    "kettlebell swings": "0549",
    "clean and press": "0028",
    "clean and jerk": "0648",    # power clean (barbell clean and jerk)
    "snatch": "0067",             # barbell one arm snatch
    "thruster": "3305",               # barbell thruster
    "thrusters": "3305",              # barbell thruster
    "wall ball": "1353",              # medicine ball catch and overhead throw
    "wall balls": "1353",             # medicine ball catch and overhead throw
    
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
    "pec deck": "0596",               # lever seated fly
    "machine fly": "0596",            # lever seated fly
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
    "supinated row": "0499",
    "handstand push up (wall assisted)": "0471",  # handstand push-up

    # Cable exercises
    "cable pull through": "0196",
    "cable hip extension": "0228",    # cable standing hip extension
    "cable rear delt fly": "0203",
    "cable leg curl": "3235",           # cable assisted inverse leg curl
    "high to low cable fly": "0225",    # cable standing cross-over high reverse fly
    "single arm cable row": "0189",
    "single arm lat pulldown": "0007",  # alternate lateral pulldown
    "ab pulldown": "0175",

    # Machine exercises
    "machine row": "1350",
    "machine preacher curl": "0592",  # lever preacher curl
    "machine incline press": "1299",  # lever incline chest press
    "face pull machine": "0203",
    "reverse pec deck": "0602",       # lever seated reverse fly
    "assisted pull up machine": "0017",

    # Dumbbell exercises
    "dumbbell incline press": "0314",
    "dumbbell romanian deadlift": "1459",
    "dumbbell front squat": "0413",     # dumbbell squat (same movement)
    "dumbbell rear delt fly": "0378",   # dumbbell rear fly
    "dumbbell calf raise": "1373",
    "dumbbell leg curl": "0331",        # dumbbell lying leg curl
    "dumbbell pullover": "0375",        # dumbbell pullover
    # Fix: 0340 was actually "dumbbell lying hammer press" (a CHEST exercise).
    # The correct skull-crusher-style movement is 0351 "dumbbell lying triceps
    # extension" (two-arm dumbbell skullcrusher). Also alias the common
    # spellings so meal-plan / workout AI variations all hit the right GIF.
    "overhead dumbbell extension":       "0351",  # dumbbell lying triceps extension (skullcrusher)
    "dumbbell skullcrusher":             "0351",
    "dumbbell skull crusher":            "0351",
    "dumbbell skullcrushers":            "0351",
    "dumbbell skull crushers":           "0351",
    "dumbbell lying triceps extension":  "0351",
    "lying dumbbell triceps extension":  "0351",
    "chest supported row": "0327",
    "bent over rear delt raise": "0380",   # dumbbell rear lateral raise

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
    "kettlebell farmer's carry": "2133",
    "kettlebell farmers carry": "2133",
    "kettlebell overhead carry": "2133",

    # Stability / Core
    "pallof press": "0979",    # band horizontal pallof press
    "plank walk": "3239",      # kneeling plank tap shoulder

    # Conditioning
    "medicine ball slam": "1354",
    "burpee intervals": "1160",
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
    # Asked only when BMI is over 30: True = "my weight is mostly muscle"
    mostly_muscle: Optional[bool] = None
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
    mostly_muscle: Optional[bool] = None

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
    mostly_muscle: Optional[bool] = None
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
            "full_gym":  ["Barbell Bench Press", "Dumbbell Bench Press", "Machine Chest Press", "Cable Chest Fly"],
            "beginner_gym": ["Machine Chest Press", "Dumbbell Bench Press", "Cable Chest Fly", "Incline Machine Press"],
            "barbells":  ["Barbell Bench Press"],
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
            "bodyweight":["Decline Push-Up"],   # upper chest; pike push-up is a shoulder press (vertical_push)
            "cables":    ["High-to-Low Cable Fly"],
            "resistance_bands":["Incline Band Press"],
        },
        "chest_fly": {
            "full_gym":  ["Cable Chest Fly", "Pec Deck", "Incline Dumbbell Fly", "Cable Crossover"],
            "dumbbells": ["Dumbbell Fly", "Incline Dumbbell Fly"],
            "machines":  ["Pec Deck"],
            "cables":    ["Cable Chest Fly", "Cable Crossover"],
            "bodyweight":["Push-Up", "Decline Push-Up"],
            "resistance_bands":["Band Chest Fly"],
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
            "bodyweight":["Prone Y-T Raise", "Reverse Snow Angel"],
        },
        "tricep_compound": {
            "full_gym":  ["Close-Grip Bench Press", "Dip", "Assisted Dip"],
            "barbells":  ["Close-Grip Bench Press"],
            "dumbbells": ["Close-Grip Dumbbell Press"],
            "machines":  ["Assisted Dip"],
            "bodyweight":["Dip", "Diamond Push-Up"],
            "resistance_bands":["Diamond Push-Up"],
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
        "lat_isolation": {
            "full_gym":  ["Straight Arm Pulldown", "Dumbbell Pullover"],
            "dumbbells": ["Dumbbell Pullover"],
            "cables":    ["Straight Arm Pulldown"],
            "machines":  ["Straight Arm Pulldown"],
            "resistance_bands":["Band Straight Arm Pulldown"],
        },
        "shrug": {
            "full_gym":  ["Dumbbell Shrug", "Barbell Shrug"],
            "dumbbells": ["Dumbbell Shrug"],
            "barbells":  ["Barbell Shrug"],
            "kettlebells":["Kettlebell Shrug"],
            "resistance_bands":["Band Shrug"],
        },
        "horizontal_pull": {
            "full_gym":  ["Barbell Row", "Cable Row", "Machine Row"],
            "beginner_gym": ["Cable Row", "Machine Row", "Dumbbell Row"],
            "barbells":  ["Barbell Row", "Pendlay Row", "T-Bar Row"],
            "dumbbells": ["Dumbbell Row", "Chest-Supported Row"],
            "machines":  ["Machine Row", "Cable Row"],
            "cables":    ["Cable Row", "Single-Arm Cable Row"],
            "bodyweight":["Inverted Row", "Prone Y Raise", "Superman Row"],
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
        "hammer_curl": {
            "full_gym":  ["Hammer Curl", "Cable Hammer Curl", "Machine Preacher Curl"],
            "dumbbells": ["Hammer Curl"],
            "cables":    ["Cable Hammer Curl"],
            "machines":  ["Machine Preacher Curl"],
            "bodyweight":["Chin-Up"],
            "resistance_bands":["Band Hammer Curl"],
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
            "full_gym":  ["Romanian Deadlift", "Conventional Deadlift", "Cable Pull-Through",
                          "Dumbbell Romanian Deadlift", "Back Extension Machine"],
            "beginner_gym": ["Dumbbell Romanian Deadlift", "Cable Pull-Through", "Leg Curl"],
            "barbells":  ["Romanian Deadlift", "Conventional Deadlift", "Sumo Deadlift"],
            "dumbbells": ["Dumbbell Romanian Deadlift", "Single-Leg RDL"],
            "machines":  ["Cable Pull-Through", "Leg Curl", "Back Extension Machine"],
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
            "full_gym":  ["Plank", "Dead Bug", "Ab Rollout", "Pallof Press", "Cable Wood Chop"],
            "dumbbells": ["Weighted Dead Bug", "Renegade Row"],
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
                ("hammer_curl",      "isolation",           "hammer curl – brachialis and forearm"),
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
                ("hammer_curl",      "isolation",           "hammer curl variation"),
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
        # Upper A / Upper B: both days train push AND pull, so a 3-4 day
        # Upper/Lower week hits chest, back, shoulders and arms twice.
        "upper_a": {
            "label": "Upper A",
            "focus": "Chest, Back, Shoulders & Arms – Strength",
            "slots": [
                ("horizontal_push",  "primary_compound",   "flat pressing – chest and tricep strength"),
                ("horizontal_pull",  "primary_compound",   "heavy row – back thickness"),
                ("vertical_push",    "secondary_compound",  "overhead press – shoulder strength"),
                ("vertical_pull",    "secondary_compound",  "vertical pull – lat width"),
                ("lateral_raise",    "accessory",           "lateral delt – shoulder width"),
                ("tricep_push",      "isolation",           "tricep isolation"),
                ("bicep_curl",       "isolation",           "bicep isolation"),
            ],
            "optional_slots": [],
        },
        "upper_b": {
            "label": "Upper B",
            "focus": "Chest, Back, Shoulders & Arms – Volume",
            "slots": [
                ("incline_push",     "primary_compound",   "incline press – upper chest"),
                ("vertical_pull",    "primary_compound",   "pull-up or pulldown – lat strength"),
                ("horizontal_pull",  "secondary_compound",  "row variation – mid-back volume"),
                ("horizontal_push",  "secondary_compound",  "press variation – chest volume"),
                ("rear_delt",        "accessory",           "rear delt – shoulder health"),
                ("bicep_curl",       "isolation",           "bicep curl variation"),
                ("tricep_push",      "isolation",           "overhead tricep extension – long head"),
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
                ("horizontal_push",  "secondary_compound",  "press – upper-body pushing strength"),
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
                ("horizontal_push",  "secondary_compound",  "press – upper-body pushing strength"),
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
            "focus": "Chest",
            "slots": [
                ("horizontal_push",  "primary_compound",   "flat pressing – chest mass and strength foundation"),
                ("incline_push",     "secondary_compound",  "incline angle – upper chest focus and fullness"),
                ("horizontal_push",  "accessory",           "second press – dumbbell or machine for extra chest volume"),
                ("chest_fly",        "isolation",           "flye – chest stretch and squeeze"),
            ],
            "optional_slots": [
                ("chest_fly",        "isolation",           "crossover or pec deck – inner chest and pump"),
            ],
            # Only when the week has no Arms Day (4-day bro split)
            "arm_finisher": [
                ("tricep_push",      "isolation",           "tricep isolation – full elbow extension"),
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
            "focus": "Back & Rear Delts",
            "slots": [
                ("vertical_pull",    "primary_compound",   "vertical pull – lat width and upper back thickness"),
                ("horizontal_pull",  "primary_compound",   "heavy row – mid-back density and rhomboid strength"),
                ("horizontal_pull",  "secondary_compound",  "second row variation – upper or lower back emphasis"),
                ("lat_isolation",    "accessory",           "straight-arm pulldown or pullover – lats without biceps"),
                ("rear_delt",        "accessory",           "rear delt – shoulder health and upper back detail"),
            ],
            "optional_slots": [],
            "arm_finisher": [
                ("bicep_curl",       "isolation",           "bicep curl – elbow flexion strength and peak"),
            ],
        },
        "bro_shoulders": {
            "label": "Shoulders Day",
            "focus": "Deltoids & Traps",
            "slots": [
                ("vertical_push",    "primary_compound",   "overhead press – deltoid mass and pressing strength"),
                ("vertical_push",    "secondary_compound",  "second press – dumbbell or machine for shoulder volume"),
                ("lateral_raise",    "accessory",           "lateral raise – medial delt width"),
                ("rear_delt",        "accessory",           "rear delt – posterior shoulder and rotator health"),
                ("lateral_raise",    "isolation",           "second lateral raise variation – cable or machine"),
            ],
            "optional_slots": [
                ("shrug",            "isolation",           "shrug – upper trap development"),
            ],
        },
        "bro_arms": {
            "label": "Arms Day",
            "focus": "Biceps & Triceps",
            "slots": [
                ("tricep_compound",  "secondary_compound",  "close-grip press or dip – tricep mass and strength"),
                ("bicep_curl",       "secondary_compound",  "barbell or EZ-bar curl – bicep mass"),
                ("tricep_push",      "accessory",           "skull crusher or overhead extension – long head focus"),
                ("bicep_curl",       "accessory",           "incline or cable curl – stretch and peak development"),
                ("tricep_push",      "isolation",           "cable pushdown – tricep isolation and pump"),
                ("hammer_curl",      "isolation",           "hammer or preacher curl – brachialis and detail"),
            ],
            "optional_slots": [],
        },
        "bro_legs": {
            "label": "Legs Day",
            "focus": "Quads, Hamstrings, Glutes & Calves",
            "slots": [
                ("squat",            "primary_compound",   "squat – bilateral lower body mass and strength"),
                ("hip_hinge",        "secondary_compound",  "deadlift variation – hamstring and glute mass"),
                ("lunge",            "secondary_compound",  "lunge or split squat – quad volume and unilateral work"),
                ("glute",            "accessory",           "hip thrust – glute strength"),
                ("knee_extension",   "isolation",           "leg extension – quad isolation and detail"),
                ("hamstring_curl",   "isolation",           "leg curl – hamstring isolation"),
                ("calf",             "isolation",           "calf raise – calves and soleus strength"),
            ],
            "optional_slots": [],
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
            3: ["upper_a", "lower_full", "upper_b"],
            4: ["upper_a", "lower_quad_focus", "upper_b", "lower_hip_focus"],
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
            5: ["athletic_conditioning", "full_body_heavy", "upper_full", "athletic_conditioning", "lower_full"],
            6: ["athletic_conditioning", "lower_quad_focus", "upper_push_heavy", "athletic_conditioning", "lower_hip_focus", "upper_full"],
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
            6: ["hybrid_strength_push", "hybrid_strength_lower", "hybrid_strength_pull", "hybrid_power_conditioning", "hybrid_strength_lower", "hybrid_strength_pull"],
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
            "primary_compound":   {"sets": 4, "reps": "6-10",       "rest": 150, "effort": "RIR 2-3"},
            "secondary_compound": {"sets": 3, "reps": "8-12",       "rest": 120, "effort": "RIR 2-3"},
            "accessory":          {"sets": 3, "reps": "10-15",      "rest": 75,  "effort": "RIR 1-2"},
            "isolation":          {"sets": 3, "reps": "12-15",      "rest": 60,  "effort": "RIR 1-2 — full contraction"},
            "unilateral":         {"sets": 3, "reps": "10-12 each", "rest": 90,  "effort": "RIR 2-3"},
            "core":               {"sets": 3, "reps": "10-15",      "rest": 45,  "effort": "Controlled — anti-gravity tension"},
            "conditioning":       {"sets": 1, "reps": "10-15 min — steady pace",  "rest": 0,   "effort": "Zone 2-3 — light cardio only"},
            "explosive":          {"sets": 3, "reps": "4-6",        "rest": 90,  "effort": "Controlled power — moderate intent"},
        },
        "lose_fat": {
            # Efficient: shorter rest, moderate reps — preserve muscle, maximise calorie burn
            "primary_compound":   {"sets": 3, "reps": "8-12",       "rest": 120, "effort": "RIR 2-3"},
            "secondary_compound": {"sets": 3, "reps": "10-15",      "rest": 90,  "effort": "RIR 2-3"},
            "accessory":          {"sets": 3, "reps": "12-15",      "rest": 60,  "effort": "RIR 1-2"},
            "isolation":          {"sets": 2, "reps": "15-20",      "rest": 45,  "effort": "RIR 1-2 — pump-focused"},
            "unilateral":         {"sets": 3, "reps": "12-15 each", "rest": 60,  "effort": "RIR 2-3"},
            "core":               {"sets": 3, "reps": "12-20",      "rest": 30,  "effort": "Controlled — efficient"},
            "conditioning":       {"sets": 1, "reps": "10-20 min — 30s hard / 30s easy, repeat",  "rest": 0,   "effort": "High intensity — intervals or HIIT"},
            "explosive":          {"sets": 3, "reps": "5-8",        "rest": 60,  "effort": "Moderate intensity"},
        },
        "body_recomp": {
            # Balanced: build muscle + maintain efficiency
            "primary_compound":   {"sets": 4, "reps": "6-10",       "rest": 150, "effort": "RIR 2-3"},
            "secondary_compound": {"sets": 3, "reps": "8-12",       "rest": 120, "effort": "RIR 2-3"},
            "accessory":          {"sets": 3, "reps": "10-15",      "rest": 60,  "effort": "RIR 2"},
            "isolation":          {"sets": 3, "reps": "12-15",      "rest": 60,  "effort": "RIR 1-2"},
            "unilateral":         {"sets": 3, "reps": "10-12 each", "rest": 75,  "effort": "RIR 2-3"},
            "core":               {"sets": 3, "reps": "10-15",      "rest": 45,  "effort": "Controlled"},
            "conditioning":       {"sets": 1, "reps": "10-15 min — 40s work / 40s easy, repeat",  "rest": 0,   "effort": "Moderate-high — efficient cardio"},
            "explosive":          {"sets": 3, "reps": "4-6",        "rest": 90,  "effort": "Moderate power output"},
        },
        "general_fitness": {
            # Balanced and sustainable
            "primary_compound":   {"sets": 3, "reps": "6-10",       "rest": 120, "effort": "RPE 7 — challenging but controlled"},
            "secondary_compound": {"sets": 3, "reps": "8-12",       "rest": 90,  "effort": "RPE 7"},
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
        "bulging disc":         "lower_back",
        "back pain":            "lower_back",
        "back injury":          "lower_back",
        "back strain":          "lower_back",
        "back spasm":           "lower_back",
        "back problem":         "lower_back",
        "back issue":           "lower_back",
        "bad back":             "lower_back",
        "sore back":            "lower_back",
        # pregnancy / postpartum
        "pregnan":              "pregnancy",
        "expecting a baby":     "pregnancy",
        "prenatal":             "pregnancy",
        "antenatal":            "pregnancy",
        "trimester":            "pregnancy",
        "postpartum":           "pregnancy",
        "post-partum":          "pregnancy",
        "postnatal":            "pregnancy",
        "diastasis":            "pregnancy",
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
                          "T-Bar Row", "Barbell Row", "Romanian Deadlift", "Pendlay Row",
                          "Front Squat", "Pause Squat", "Kettlebell Swing",
                          "Kettlebell Swing Intervals", "Barbell Complex Intervals"],
        "knee":          ["Back Squat", "Hack Squat", "Goblet Squat", "Smith Machine Squat",
                          "Front Squat", "Pause Squat", "Dumbbell Front Squat",
                          "Kettlebell Goblet Squat", "Pistol Squat (assisted)", "Band Squat",
                          "Leg Extension", "Sissy Squat", "Kettlebell Step-Up",
                          "Box Jump", "Broad Jump", "Thruster Intervals",
                          "Dumbbell Thruster Intervals", "Burpee Intervals",
                          "Leg Press", "Leg Press (feet high)",
                          "Barbell Bulgarian Split Squat", "Dumbbell Bulgarian Split Squat",
                          "Bulgarian Split Squat", "Smith Machine Split Squat",
                          "Dumbbell Reverse Lunge", "Walking Lunge", "Reverse Lunge",
                          "Barbell Lunge", "Dumbbell Lunge", "Lateral Lunge",
                          "Kettlebell Lunge", "Band Lunge",
                          "Dumbbell Step-Up", "Step-Up",
                          "Jump Squat", "Running"],
        "shoulder":      ["Barbell Overhead Press", "Push Press", "Upright Row",
                          "Behind-the-Neck Press", "Barbell Bench Press", "Dip", "Assisted Dip"],
        "wrist":         ["Barbell Curl", "Barbell Overhead Press", "Push-Up", "Barbell Bench Press"],
        "elbow":         ["Skull Crusher", "Dip", "Assisted Dip", "Barbell Curl"],
        "hip":           ["Barbell Hip Thrust", "Barbell Bulgarian Split Squat",
                          "Leg Press", "Leg Press (feet high)"],
        "ankle":         ["Calf Raise", "Calf Raise Machine", "Seated Calf Raise",
                          "Leg Press Calf Raise", "Bodyweight Calf Raise", "Single-Leg Calf Raise",
                          "Jump Squat", "Broad Jump"],
        "neck":          ["Barbell Back Squat", "Barbell Overhead Press"],
        # Conservative defaults; the program also tells the user to get clearance.
        "pregnancy":     ["Conventional Deadlift", "Sumo Deadlift", "Back Squat", "Front Squat",
                          "Pause Squat", "Barbell Hip Thrust", "Barbell Glute Bridge",
                          "Box Jump", "Broad Jump", "Jump Squat", "Plyo Push-Up",
                          "Medicine Ball Slam", "Burpee Intervals", "Devil Press Intervals",
                          "Barbell Complex Intervals", "Thruster Intervals",
                          "Hanging Leg Raise", "V-Up", "Cable Crunch", "Ab Rollout",
                          "Reverse Crunch", "Ab Pulldown", "Running"],
    }

    # Joint-friendly options offered first when a limitation removes the usual ones
    LIMITATION_SUBSTITUTES = {
        "knee": {"squat": ["Box Squat (pain-free depth)", "Spanish Squat", "Wall Sit"]},
    }

    # "No squats", "avoid deadlifts", "can't do lunges": a movement the user names
    # is removed by name (every variation of it), on top of the injury lists above
    MOVEMENT_LIMITS = [
        # Specific phrases first: they are removed from the text so the general
        # word ("squat") doesn't also remove the machine and dumbbell versions
        (r"barbell squats?|bar squats?",
                                  ["back squat", "front squat", "pause squat", "barbell squat",
                                   "barbell bulgarian split squat", "thruster"]),
        (r"squat",                ["squat", "thruster"]),
        (r"dead ?lift|rdl",       ["deadlift", "rdl"]),
        (r"lunge",                ["lunge", "split squat", "step-up"]),
        (r"bench",                ["bench press"]),
        (r"overhead|shoulder press|military press",
                                  ["overhead press", "shoulder press", "push press", "arnold press"]),
        (r"pull ?-?ups?|chin ?-?ups?", ["pull-up", "chin-up"]),
        (r"\bdips?\b",            ["dip"]),
        (r"hip thrust",           ["hip thrust"]),
        (r"\brun|running",        ["running", "sprint"]),
        (r"jump|plyo",            ["jump", "bound", "plyo"]),
        (r"burpee",               ["burpee"]),
    ]

    @staticmethod
    def _plain(text: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())

    @classmethod
    def _blocked_movements(cls, limitations: list) -> list:
        """Name fragments of exercises the user asked to leave out."""
        text = f" {cls._plain(' '.join(limitations or []))} "
        frags = []
        # 1. Exact exercise names ("no barbell bench press", "no leg extensions")
        #    leave out just that exercise, not the whole movement
        names = {cls._plain(n) for p in cls.PATTERNS.values() for lst in p.values() for n in lst}
        for name in sorted(names, key=len, reverse=True):
            m = re.search(rf" {re.escape(name)}(?:e?s)? ", text)
            if m:
                frags.append(name)
                text = text.replace(m.group(0), " ")
        # 2. Whole movements ("no squats", "can't deadlift") from what's left
        for pat, fs in cls.MOVEMENT_LIMITS:
            if re.search(pat, text):
                frags += [cls._plain(f) for f in fs]
                text = re.sub(pat, " ", text)
        return frags

    @classmethod
    def _is_blocked(cls, name: str, fragments: list) -> bool:
        n = f" {cls._plain(name)} "
        return any(f" {f}" in n for f in fragments)

    # Fly / raise / curl style moves: fine as accessories, but never the main
    # heavy lift of a session (they would get 5x3-5 compound prescriptions).
    ISOLATION_MOVES = {
        "Cable Chest Fly", "Cable Crossover", "Incline Dumbbell Fly", "High-to-Low Cable Fly",
        "Prone Y Raise", "Superman Row", "Band Pull-Apart", "Leg Curl",
        "Cable Glute Kickback", "Cable Hip Extension", "Band Kickback", "Band Clamshell",
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
        "chest":        ["horizontal_push", "incline_push", "chest_fly"],
        "back":         ["vertical_pull", "horizontal_pull", "lat_isolation"],
        "shoulders":    ["vertical_push", "lateral_raise", "rear_delt"],
        "arms":         ["bicep_curl", "tricep_push", "hammer_curl", "tricep_compound"],
        "biceps":       ["bicep_curl", "hammer_curl"],
        "triceps":      ["tricep_push", "tricep_compound"],
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
        "upper_a":                ["core", "chest", "back", "shoulders", "arms", "biceps", "triceps"],
        "upper_b":                ["core", "chest", "back", "shoulders", "arms", "biceps", "triceps"],
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
        "Prone Y-T Raise": 1, "Reverse Snow Angel": 1, "Wall Sit": 1,
        "Box Squat (pain-free depth)": 1,
        # Tier 3 — Advanced
        "Archer Push-Up": 3, "Handstand Push-Up (wall assisted)": 3,
        "Pistol Squat (assisted)": 3, "Pull-Up": 3, "Chin-Up": 3,
        "Dip": 3, "Muscle-Up Progression": 3, "Terminal Knee Extension": 3,
    }

    # Exercises measured in time, distance or per side, not plain reps: the slot's
    # rep range ("10-15") becomes a timed hold, a carry distance or "each side".
    HOLD_EXERCISES = {"Plank": "hold", "Side Plank": "hold each side", "Wall Sit": "hold",
                      "Hollow Hold": "hold", "L-Sit": "hold"}
    CARRY_EXERCISES = {"Farmer's Carry", "Kettlebell Farmer's Carry", "Trap Bar Farmer's Carry",
                       "Suitcase Carry", "Kettlebell Overhead Carry"}
    PER_SIDE_EXERCISES = {"Dead Bug", "Weighted Dead Bug", "Renegade Row", "Bird Dog", "Pallof Press", "Band Pallof Press", "Cable Wood Chop",
                          "Single-Leg RDL", "Single-Leg Romanian Deadlift", "Single-Leg Glute Bridge",
                          "Single-Leg Calf Raise", "Single-Arm Cable Row", "Single-Arm Lat Pulldown"}
    HOLD_TIMES = {"beginner": "20-30s", "intermediate": "30-45s", "advanced": "45-60s"}

    # Above 4 sets of one main lift mostly adds fatigue for muscle / recomp / fat-loss
    # goals; extra volume goes to other exercises. Strength and athletic keep 5.
    FIVE_SET_GOALS = {"strength", "athletic_performance"}

    def _set_range(self, ex_type: str, level: str, goal: str) -> tuple:
        s_min, s_max = self.SETS_PER_EXERCISE.get(ex_type, {}).get(level, (2, 4))
        if ex_type == 'primary_compound' and goal not in self.FIVE_SET_GOALS:
            s_max = min(s_max, 4)
        return s_min, s_max

    @classmethod
    def reps_for_exercise(cls, name: str, reps: str, level: str) -> str:
        """The slot's reps, adjusted to how this exercise is measured."""
        if name in cls.HOLD_EXERCISES:
            return f"{cls.HOLD_TIMES.get(level, '30-45s')} {cls.HOLD_EXERCISES[name]}"
        if name in cls.CARRY_EXERCISES:
            return "30-40 m walk" + (" each side" if name in ("Suitcase Carry", "Kettlebell Overhead Carry") else "")
        if name in cls.PER_SIDE_EXERCISES and 'each' not in str(reps) and 'min' not in str(reps):
            return f"{reps} each side"
        return reps

    BEGINNER_REGRESSIONS: dict = {
        "Pull-Up": "Negative Pull-Up (slow lowering)",
        "Chin-Up": "Negative Chin-Up (slow lowering)",
        "Muscle-Up Progression": "Negative Pull-Up (slow lowering)",
        "Dip": "Bench Dip",
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
                ul_sessions = self.get_session_count_for_split('upper_lower', days)
                n_upper = sum(1 for st in ul_sessions if st.startswith('upper_'))
                n_lower = len(ul_sessions) - n_upper
                return 'upper_lower', 'Upper / Lower', \
                    f"Upper/Lower selected — upper body trained {n_upper}× and lower body {n_lower}× per week."

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
        # "full_body" is the no-focus default — say "every muscle group", not "full body"
        focus_label = (focus_key.replace('_', ' ') if focus_key and focus_key != 'full_body'
                       else 'every muscle group')
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
                              limitations: list, level: str = 'intermediate',
                              ex_type: str = None, goal: str = None) -> list:
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
        limitation_keys = self._normalize_limitations(limitations)
        for key in limitation_keys:
            excluded.update(self.LIMITATION_EXCLUSIONS.get(key, []))
        substitutes = []
        for key in limitation_keys:
            for sub in self.LIMITATION_SUBSTITUTES.get(key, {}).get(pattern, []):
                if sub == "Spanish Squat" and is_bodyweight_context:
                    continue   # needs a fixed band or strap
                substitutes.append(sub)
        if substitutes:
            unique = substitutes + [e for e in unique if e not in substitutes]
        blocked = self._blocked_movements(limitations)
        excluded.update(e for e in unique if self._is_blocked(e, blocked))
        filtered = [e for e in unique if e not in excluded]
        # Main lifts must be real compound movements
        if ex_type in ('primary_compound', 'secondary_compound'):
            compound_only = [e for e in filtered if e not in self.ISOLATION_MOVES]
            if compound_only:
                filtered = compound_only
        # Safe fallback: NEVER serve contraindicated exercises.
        # If all candidates are excluded, use bodyweight or any options from the same pattern.
        if filtered:
            result = filtered
        else:
            safe_fallback = [
                e for e in (opts.get('bodyweight', []) + opts.get('any', []))
                if e not in excluded and not self._is_blocked(e, blocked)
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
                # Drop advanced skills when easier options exist; otherwise
                # swap in the standard beginner regression
                easier = [x for x in result if diff.get(x, 2) <= 2]
                if easier:
                    result = easier
                else:
                    result = list(dict.fromkeys(
                        self.BEGINNER_REGRESSIONS.get(x, x) for x in result))
            elif level == 'advanced':
                result = sorted(result, key=lambda x: -diff.get(x, 2))
            else:  # intermediate — exclude tier-3 only from top options
                tier1_2 = [x for x in result if diff.get(x, 2) <= 2]
                tier3   = [x for x in result if diff.get(x, 2) > 2]
                result  = tier1_2 + tier3

        # Past beginner, with equipment: loaded, progressive core work comes before
        # the plank and dead bug (a plank stops progressing once you can hold it)
        # (beginners the other way round: learn to brace with the plank first)
        if pattern == 'core_stability' and not is_bodyweight_context:
            easy = [e for e in result if e in ('Plank', 'Dead Bug', 'Bird Dog', 'Side Plank')]
            hard = [e for e in result if e not in easy]
            result = easy + hard if level == 'beginner' else hard + easy

        # Heavy floor deadlifts at 6-15 reps are mostly fatigue for muscle-building
        # goals: Romanian-style hinges first, conventional/sumo for strength work
        if pattern == 'hip_hinge' and goal and goal not in self.FIVE_SET_GOALS:
            floor_pulls = [e for e in result if e in ('Conventional Deadlift', 'Sumo Deadlift')]
            result = [e for e in result if e not in floor_pulls] + floor_pulls

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
                    "Add weight each session when you complete all sets with good form. Typically +2.5kg on upper, +5kg on lower. Every 4th week is a lighter deload week (see the weekly plan).")
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

    # Conditioning length in minutes, by session length: a finisher at the end of a
    # lifting session vs. the main block of a dedicated conditioning session.
    COND_MINUTES = {
        "finisher":  {30: (5, 6),  45: (8, 10),  60: (10, 12), 75: (12, 15)},
        "dedicated": {30: (8, 10), 45: (12, 15), 60: (15, 20), 75: (20, 25)},
    }
    CONDITIONING_SESSIONS = {"athletic_conditioning", "hybrid_power_conditioning",
                             "calisthenics_conditioning"}
    STEADY_CARDIO_OPTIONS = {
        "gym":     ["Rowing Machine", "Stationary Bike", "Incline Treadmill Walk"],
        "outdoor": ["Brisk Walk", "Easy Jog", "Jump Rope (easy pace)"],
    }

    def _conditioning_spec(self, goal: str, style: str, level: str, dur_bucket: int,
                           session_type: str, coaching_note: str, equipment: list,
                           limitations: list, injected: bool) -> dict:
        """Conditioning slot sized to the session length, with a label that matches
        the prescription (steady cardio vs. intervals)."""
        base = self.GOAL_PARAMS.get(goal, self.GOAL_PARAMS['general_fitness'])['conditioning']
        kind = 'dedicated' if session_type in self.CONDITIONING_SESSIONS else 'finisher'
        lo, hi = self.COND_MINUTES[kind][dur_bucket]
        note_l = coaching_note.lower()
        if 'steady' in note_l or 'aerobic' in note_l:
            steady = True
        elif injected:
            steady = 'steady' in base['reps']
        else:
            steady = False   # hybrid / functional / calisthenics conditioning = intervals

        if steady:
            reps = f"{lo}-{hi} min — steady pace"
            effort = base['effort'] if 'steady' in base['reps'] else "Zone 2 — conversational pace"
            gym = any(e in ('full_gym', 'machines', 'cables') for e in (equipment or []))
            options = list(self.STEADY_CARDIO_OPTIONS['gym' if gym else 'outdoor'])
            if self._normalize_limitations(limitations) & {'knee', 'ankle', 'pregnancy'}:
                options = [o for o in options if o not in ('Easy Jog', 'Jump Rope (easy pace)')]
            if injected:
                coaching_note = "cardio finisher — steady pace, builds aerobic fitness"
        else:
            if level == 'beginner':
                pattern = "20s hard / 40s easy, repeat"
            elif '/' in base['reps'] and '—' in base['reps']:
                pattern = base['reps'].split('—', 1)[1].strip()
            else:
                pattern = "30s hard / 30s easy, repeat"
            reps = f"{lo}-{hi} min — {pattern}"
            if level == 'beginner':
                effort = "Moderate-hard — stay in control"
            elif 'steady' in base['reps'] or 'light' in base['effort'].lower():
                effort = "Hard but repeatable — same pace every round"
            else:
                effort = base['effort']
            options = self.get_exercise_options('conditioning', equipment, style, limitations, level)
            if injected:
                coaching_note = "metabolic finisher — elevate heart rate, maximise calorie burn"
        return {
            "pattern":       "conditioning",
            "type":          "conditioning",
            "coaching_note": coaching_note,
            "sets":          1,
            "reps":          reps,
            "rest_seconds":  0,
            "effort":        effort,
            "options":       options or ["Brisk Walk"],
            "excluded":      [],
        }

    # Accessories the time fit keeps while the day has only one of them
    PROTECTED_ACCESSORIES = ('bicep_curl', 'tricep_push', 'lateral_raise')

    WORK_PER_SET_SEC = 40   # avg set execution + transition time
    WARMUP_SEC = 300        # 5 min general warm-up
    RAMP_UP_SEC = 120       # lighter warm-up sets before each main lift

    @classmethod
    def _estimate_minutes(cls, slots: list) -> float:
        sec = cls.WARMUP_SEC
        for s in slots:
            if s['type'] == 'conditioning':
                nums = re.findall(r'\d+', str(s['reps']))
                mins = int(nums[1]) if len(nums) > 1 else (int(nums[0]) if nums else 10)
                sec += mins * 60
            else:
                work = cls.WORK_PER_SET_SEC * (1.5 if 'each' in str(s['reps']) else 1)
                sec += s['sets'] * (work + s['rest_seconds'])
                if s['type'] == 'primary_compound':
                    sec += cls.RAMP_UP_SEC
        return sec / 60.0

    def _fit_to_duration(self, slots: list, target_minutes: int, goal: str,
                         primary_patterns: list) -> list:
        """Trim a session until its estimated time is within 10% of the target.
        Order: secondary lifts to 3 sets → finisher a step shorter → drop extra
        accessories (keeping one biceps, triceps and side-delt exercise) → shortest finisher → fewer sets on support work → main-lift rest
        to the goal's floor → main lifts down to 3 sets → drop remaining lifts
        (always keeping at least 2 lifts and the conditioning block)."""
        limit = target_minutes * 1.10
        # Muscle goals keep at least 2 min on main lifts even when time is tight
        rest_floor = max(self.STRENGTH_REST_FLOORS.get(goal, 60),
                         120 if goal in ('build_muscle', 'body_recomp') else 0)

        def over() -> bool:
            return self._estimate_minutes(slots) > limit

        def lifts() -> list:
            return [s for s in slots if s['type'] != 'conditioning']

        def shorten_finisher(floor_minutes: int) -> bool:
            # A finisher at the end of a lifting day can run a step shorter;
            # dedicated conditioning days keep their full block
            for s in slots:
                if s['type'] != 'conditioning' or 'finisher' not in s['coaching_note']:
                    continue
                m = re.match(r'(\d+)-(\d+) min', str(s['reps']))
                if not m:
                    continue
                steps = [(lo, hi) for lo, hi in self.COND_MINUTES['finisher'].values()
                         if hi < int(m.group(2)) and hi >= floor_minutes]
                if steps:
                    lo, hi = max(steps, key=lambda x: x[1])
                    s['reps'] = f"{lo}-{hi} min" + str(s['reps'])[m.end():]
                    return True
            return False

        # 0. Secondary lifts down to 3 sets before any exercise is dropped
        while over():
            cands = [s for s in slots if s['type'] == 'secondary_compound' and s['sets'] > 3]
            if not cands:
                break
            cands[-1]['sets'] -= 1
        # 0b. A finisher may lose a few minutes (not below 8-10) before any lifting goes
        while over() and shorten_finisher(10):
            pass
        # 1. Drop lowest-priority accessories (non-focus first), keep at least 3 lifts
        #    and the day's only biceps, triceps and side-delt exercises
        while over() and len(lifts()) > 3:
            cands = [s for s in slots if s['type'] not in
                     ('primary_compound', 'secondary_compound', 'conditioning')]
            for pat in self.PROTECTED_ACCESSORIES:
                only = [s for s in slots if s['pattern'] == pat]
                if len(only) == 1 and only[0] in cands:
                    cands.remove(only[0])
            if not cands:
                break
            non_focus = [s for s in cands if s['pattern'] not in primary_patterns]
            slots.remove((non_focus or cands)[-1])
        # 1b. Finisher down to its shortest (5-6 min)
        while over() and shorten_finisher(6):
            pass
        # 2. Fewer sets on everything except the main lifts (minimum 2)
        while over():
            cands = [s for s in slots if s['type'] not in ('primary_compound', 'conditioning')
                     and s['sets'] > 2]
            if not cands:
                break
            most = max(s['sets'] for s in cands)
            [s for s in cands if s['sets'] == most][-1]['sets'] -= 1
        # 3. Main-lift rest down to the goal's floor
        if over():
            for s in slots:
                if s['type'] == 'primary_compound' and s['rest_seconds'] > rest_floor:
                    s['rest_seconds'] = rest_floor
        # 4. Main lifts down to 3 sets
        while over():
            cands = [s for s in slots if s['type'] == 'primary_compound' and s['sets'] > 3]
            if not cands:
                break
            most = max(s['sets'] for s in cands)
            [s for s in cands if s['sets'] == most][-1]['sets'] -= 1
        # 5. Drop remaining lifts from the end, keeping at least 2
        while over() and len(lifts()) > 2:
            cands = [s for s in slots if s['type'] not in ('primary_compound', 'conditioning')]
            if not cands:
                cands = [s for s in slots if s['type'] == 'primary_compound'][1:]
            if not cands:
                break
            slots.remove(cands[-1])
        return slots

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
            # Bro split: arms get their own day at 5+ days, so chest/back days
            # only carry a tricep/bicep finisher when there is no Arms Day
            if 'bro_arms' not in session_types:
                slots += list(archetype.get('arm_finisher', []))

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

            def _level_target(lo: int, hi: int) -> int:
                # Beginners near the bottom of the range, advanced near the top
                if level == 'beginner':
                    return lo + 1
                if level == 'advanced':
                    return hi - 1
                return (lo + hi) // 2
            target_sets = _level_target(min_sets, max_sets)

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
                # The time fit (_fit_to_duration) shortens the finisher or trims
                # accessories if the day runs long; only the set budget eases here
                max_sets = max(min_sets, max_sets - 2)  # reduce set budget slightly
                target_sets = _level_target(min_sets, max_sets)

            # Conditioning blocks are set aside so the lifting budget and the
            # max-exercise trim can never squeeze them out; re-added after.
            cond_slots = [s for s in slots if s[1] == 'conditioning']
            slots = [s for s in slots if s[1] != 'conditioning']
            lift_cap = max(2, max_ex - len(cond_slots))

            # ── Primary focus: prioritise slots before trimming ──────────────
            # Sort BEFORE the max_ex trim so primary focus patterns survive cuts.
            def _slot_importance(s_tuple):
                pattern, ex_type, _ = s_tuple
                if ex_type == 'primary_compound':       return 0
                if pattern in primary_patterns:         return 1   # primary focus survives trim
                if ex_type == 'secondary_compound':     return 2
                if pattern in secondary_patterns:       return 3
                return 4
            slots.sort(key=_slot_importance)
            slots = slots[:lift_cap]

            # ── Inject missing primary focus slots ───────────────────────────────
            # A focus pattern is added only where it fits the session's identity:
            # patterns already native to the archetype, lower-body patterns on days
            # that train legs, upper-body patterns on days that train both push and
            # pull (push days stay push, pull days stay pull). When the day is full,
            # the focus slot replaces the lowest-priority non-focus accessory.
            session_native = {s[0] for s in archetype['slots']}
            LOWER_P = {'squat', 'lunge', 'hip_hinge', 'glute', 'hamstring_curl',
                       'knee_extension', 'calf'}
            PUSH_P  = {'horizontal_push', 'incline_push', 'vertical_push', 'lateral_raise',
                       'tricep_push'}
            PULL_P  = {'vertical_pull', 'horizontal_pull', 'rear_delt', 'bicep_curl'}
            CORE_P  = {'core_stability', 'core_flexion', 'carry'}

            def _fits_session(fp: str) -> bool:
                if fp == 'conditioning':
                    return False   # conditioning is handled separately
                if fp in session_native:
                    return True
                if fp in LOWER_P:
                    return bool(session_native & LOWER_P)
                if fp in PUSH_P | PULL_P:
                    return bool(session_native & PUSH_P) and bool(session_native & PULL_P)
                return fp in CORE_P

            focus_slot_count = sum(1 for p, _, _ in slots if p in primary_patterns)
            if primary_patterns and focus_slot_count < len(primary_patterns):
                max_inject = min(2, len(primary_patterns))
                injected = 0
                for fp in primary_patterns:
                    if injected >= max_inject:
                        break
                    if fp in [s[0] for s in slots] or not _fits_session(fp):
                        continue
                    new_slot = (fp, 'accessory', f'primary focus — {fp.replace("_", " ")} direct volume')
                    if len(slots) < lift_cap:
                        slots.append(new_slot)
                    else:
                        replaceable = [k for k, (p, t, _) in enumerate(slots)
                                       if t in ('accessory', 'isolation', 'core')
                                       and p not in primary_patterns
                                       and p not in secondary_patterns]
                        if not replaceable:
                            break
                        slots[replaceable[-1]] = new_slot
                    injected += 1

            # ── Build slot specs with budget-aware set allocation ────────────
            excluded_exercises = set()
            for key in self._normalize_limitations(limitations):
                excluded_exercises.update(self.LIMITATION_EXCLUSIONS.get(key, []))

            slot_specs = []
            used_today = set()
            total_sets_allocated = 0
            # Sets may run a little past the target so later slots (arms, delts)
            # still get 2 sets instead of being starved; the time fit trims later.
            set_ceiling = max_sets if level == 'advanced' else min(max_sets, target_sets + 2)

            for slot_idx, (pattern, ex_type, coaching_note) in enumerate(slots):
                # Keep 2 sets in reserve for each slot still to come
                reserve = 2 * (len(slots) - slot_idx - 1)
                remaining_budget = max(0, set_ceiling - total_sets_allocated - reserve)

                # How many sets should this slot get?
                base_params = goal_params.get(ex_type, goal_params.get('accessory', {}))
                # Jumps and core work keep their own reps and rest even when they
                # lead the day (no 6-10 box jumps or planks with 2:30 rest)
                if pattern == 'explosive' and 'explosive' in goal_params:
                    base_params = goal_params['explosive']
                elif pattern.startswith('core_') and 'core' in goal_params:
                    base_params = goal_params['core']
                s_min, s_max = self._set_range(ex_type, level, goal)
                base_sets   = base_params.get('sets', 3)
                # Clamp to level range
                ideal_sets  = max(s_min, min(s_max, base_sets))
                # Level shapes main-lift volume: advanced +1 set, beginners -1 on 4+ set lifts
                if ex_type in ('primary_compound', 'secondary_compound'):
                    if level == 'advanced':
                        ideal_sets = max(s_min, min(s_max, base_sets + 1))
                    elif level == 'beginner' and base_sets >= 4:
                        ideal_sets = max(s_min, min(s_max, base_sets - 1))
                # Don't overshoot the session budget
                if ex_type == 'primary_compound':
                    # Primary compound always gets its full ideal allocation
                    assigned_sets = ideal_sets
                elif set_ceiling - total_sets_allocated < 2:
                    break   # budget spent
                elif remaining_budget <= s_min:
                    # Almost out of budget — give the 2-set minimum
                    assigned_sets = max(2, remaining_budget)
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

                options = self.get_exercise_options(pattern, equipment, style, limitations,
                                                    level, ex_type, goal)
                # If every option for this pattern is contraindicated by the user's
                # limitations (e.g. all lunge variants excluded by a knee injury),
                # skip the slot entirely rather than show a "Bodyweight Exercise"
                # placeholder. Remaining slots still cover the session.
                if options == ["Bodyweight Exercise"]:
                    continue
                # Rotate options to avoid cross-day exercise duplication
                if len(options) > 1:
                    # Move any already-used exercise to the back of the top 3 (the
                    # choices the AI sees) so lower-ranked options, e.g. barbells
                    # for beginners, never jump to the front. Main lifts only avoid
                    # repeats within the same day: benching or squatting twice a
                    # week is how a main lift progresses.
                    used = used_today if ex_type == 'primary_compound' else used_primary_options
                    top = options[:3]
                    fresh = [o for o in top if o not in used]
                    stale = [o for o in top if o in used]
                    options = fresh + stale + options[3:]

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
                    used_today.add(options[0])

                if ex_type != 'primary_compound' and total_sets_allocated >= set_ceiling:
                    break

            # Calves go after the other leg work (before core and finishers)
            calves = [sp for sp in slot_specs if sp['pattern'] == 'calf']
            if calves:
                rest_specs = [sp for sp in slot_specs if sp['pattern'] != 'calf']
                at = next((k for k, sp in enumerate(rest_specs) if sp['type'] == 'core'), len(rest_specs))
                slot_specs = rest_specs[:at] + calves + rest_specs[at:]

            for _, _, cond_note in cond_slots:
                slot_specs.append(self._conditioning_spec(
                    goal, style, level, dur_bucket, session_type, cond_note,
                    equipment, limitations, injected=False))

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
                    # Never above the level's own per-exercise maximum
                    cap = self._set_range(slot['type'], level, goal)[1]
                    boosted = min(slot['sets'] + 1, cap)
                    if (boosted > slot['sets']
                            and total_sets_allocated - slot['sets'] + boosted <= max_sets + focus_boost_headroom):
                        total_sets_allocated += (boosted - slot['sets'])
                        slot['sets'] = boosted
                        slot['coaching_note'] += ' [primary focus — elevated priority]'
                        primary_boost_count += 1
                elif slot['pattern'] in secondary_patterns:
                    cap = self._set_range(slot['type'], level, goal)[1]
                    boosted = min(slot['sets'] + 1, cap)
                    if total_sets_allocated <= max_sets and boosted > slot['sets']:
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
                        if not _fits_session(sp):   # don't inject push patterns into pull sessions, etc.
                            continue
                        sec_opts = self.get_exercise_options(sp, equipment, style, limitations, level,
                                                             'accessory', goal)
                        if not sec_opts or sec_opts == ["Bodyweight Exercise"]:
                            continue   # every option excluded by the user's limitations
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
            ARM_ISO  = {'bicep_curl', 'tricep_push', 'hammer_curl'}
            CORE_PAT = {'core_stability', 'core_flexion', 'carry'}
            def _slot_priority(s: dict) -> int:
                if s['type'] == 'conditioning':            return 99  # always last
                if s['pattern'] in CORE_PAT:               return 6   # core just before conditioning
                if (s['pattern'] in ARM_ISO               # arm isolation before core
                        and s['type'] not in ('primary_compound', 'secondary_compound')):
                    return 5   # (on Arms Day the heavy curl still leads)
                if s['type'] == 'primary_compound':        return 0   # heavy main lifts first
                if s['type'] == 'secondary_compound':      return 1   # secondary heavy movements
                if s['pattern'] in primary_patterns:       return 2   # primary focus accessories
                if s['pattern'] in secondary_patterns:     return 3   # secondary focus accessories
                return 4                                              # other accessories / isolation
            slot_specs.sort(key=_slot_priority)

            # ── Conditioning finisher injection ───────────────────────────────
            if will_inject_cond:
                slot_specs.append(self._conditioning_spec(
                    goal, style, level, dur_bucket, session_type, "", equipment,
                    limitations, injected=True))

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

            # One exercise once per day: each slot leads with an option not used
            # earlier that day, and a slot with nothing new to offer is dropped.
            # Short menus (bodyweight) otherwise repeated an exercise: Pike Push-Up
            # as both the incline push and the overhead press.
            chosen, deduped = set(), []
            for sp in slot_specs:
                if sp['type'] == 'conditioning' or not sp.get('options'):
                    deduped.append(sp)
                    continue
                fresh = [o for o in sp['options'] if o.lower() not in chosen]
                if not fresh:
                    continue
                sp['options'] = fresh + [o for o in sp['options'] if o.lower() in chosen]
                chosen.add(fresh[0].lower())
                deduped.append(sp)
            slot_specs = deduped

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
        # TIME FIT — every session must fit the user's chosen session length.
        # Estimate: 5 min warm-up + sets × (~40s work + rest) + conditioning minutes.
        # ═══════════════════════════════════════════════════════════════════════
        dur = req.duration_minutes
        dur_bucket = 30 if dur <= 30 else 45 if dur <= 45 else 60 if dur <= 60 else 75
        for d in day_blueprints:
            # Well under time on general fitness → use the spare time for a finisher
            # (fat loss already has one every day; recomp alternates, 2-3 a week)
            if (goal == 'general_fitness'
                    and not any(s['type'] == 'conditioning' for s in d['slots'])
                    and self._estimate_minutes(d['slots']) < dur * 0.8):
                d['slots'].append(self._conditioning_spec(
                    goal, style, level, dur_bucket, d['archetype_id'], "", equipment,
                    limitations, injected=True))
            d['slots'] = self._fit_to_duration(d['slots'], dur, goal, primary_patterns)

        return {
            "split_id":          split_id,
            "split_name":        split_name,
            "split_rationale":   split_rationale,
            "progression_name":  progression_name,
            "progression_desc":  progression_desc,
            "deload_timing":     {
                # Matches the deload weeks in generate_weekly_progression
                "strength":             "Weeks 4, 8 and 12: cut working sets by 50% and keep the same weight, then come back heavier.",
                "build_muscle":         "Weeks 4, 8 and 12: cut working sets by 50% — keep the load, reduce the volume.",
                "lose_fat":             "Weeks 4 and 8: reduce volume by 40% while keeping your training days.",
                "body_recomp":          "Weeks 4, 8 and 12: reduce volume by about 40% and keep the load — prioritise sleep and recovery.",
                "athletic_performance": "Weeks 4, 8 and 12: cut volume by 50% and keep the intensity — use the week for skill work and mobility.",
                "general_fitness":      "Weeks 4 and 8: reduce sets by about 30% and stay lightly active.",
            }.get(goal, "Weeks 4 and 8: reduce sets by about 30% and stay lightly active."),
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
    on_target: Optional[bool] = None  # every macro within 5% of the plan's targets

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
    # Where the numbers came from: "database", "usda", "ai", "snap", "manual",
    # "saved". Only AI estimates (or older apps that don't say) are corrected.
    source: Optional[str] = None

SNAP_DAILY_LIMIT = 15          # photo analyses per user per 24 hours (fair use)


class FoodImageAnalyzeRequest(BaseModel):
    user_id: str
    image_base64: str
    meal_type: str = "snack"
    # The description box: corrections for the AI ("no dressing") and/or the
    # amount eaten ("200g", "half", "4 eggs and 3 slices sourdough").
    additional_context: Optional[str] = None
    # Still accepted from older app builds and API clients — worked out by the
    # same parser: the typed text, a structured amount, or grams.
    portion_text: Optional[str] = None
    portion_amount: Optional[float] = None
    logged_date: Optional[str] = None   # the user's local day; server date if missing
    portion_unit: Optional[str] = None  # "grams" | "servings" | "count" | a unit noun ("egg")
    portion_g: Optional[float] = None
    quantity: int = 1
    preview: bool = False  # True = analyze only, don't log — user reviews first


class SnapItemRequest(BaseModel):
    text: str                          # "150g", "3 eggs", "30g cheddar"
    key: Optional[str] = None          # editing: the item's database food
    name: Optional[str] = None
    per_100g: Optional[dict] = None    # editing an estimated (non-database) item

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
    country: Optional[str] = None   # phone region, e.g. "AU" — matches saved food lookups

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
    "monthly": 14.99,
    "yearly": 99.99,
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

def calculate_macros(weight: float, height: float, age: int, gender: str, activity_level: str, goal: str,
                     mostly_muscle: Optional[bool] = False) -> Dict[str, float]:
    """Calculate personalized macros using Mifflin-St Jeor equation.

    Protein is prescribed from estimated lean mass (g/kg) per ISSN guidelines —
    not as a % of calories — to ensure adequate lean mass preservation during a
    deficit. Calorie adjustments are percentage-based off TDEE so they scale
    correctly across body sizes.
    """
    # "Female", "F", "woman" etc. all count: an unrecognised value would
    # otherwise give men and women the same in-between numbers
    g = (gender or "").strip().lower()
    gender = ("male" if g in ("male", "m", "man") else
              "female" if g in ("female", "f", "woman") else g)

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
    floor_applied = False
    if goal == "weight_loss":
        calories = tdee * 0.80              # 20% deficit
        protein_per_kg = 2.2                # high — preserve LBM in deficit
        protein_per_kg_lean = 2.6
        # Safety floor: never below BMR or the usual unsupervised minimum
        # (1,200 women / 1,500 men), and never above maintenance. Small or
        # older people then sit near maintenance — their loss comes from activity.
        floor = max(bmr, {"male": 1500, "female": 1200}.get(gender, 1350))
        if calories < floor:
            calories, floor_applied = min(floor, tdee), True
    elif goal == "muscle_building":
        calories = tdee * 1.10              # 10% surplus (lean bulk)
        protein_per_kg = 2.0                # industry standard for hypertrophy (RP/MacroFactor)
        protein_per_kg_lean = 2.4
    else:  # maintenance
        calories = tdee
        protein_per_kg = 1.8                # above MPS ceiling with comfortable margin
        protein_per_kg_lean = 2.2

    # ── Macro split: protein from lean mass, fat at 25% of cals, rest carbs ──
    # g/kg targets are really for lean mass: body fat doesn't need protein, so
    # total weight overshoots for women and anyone with fat to lose (85 kg
    # woman: 187g). Lean mass is estimated from height, weight and sex (Boer);
    # protein is the lower of that and the body-weight target (with a BMI
    # over 30, the weight at BMI 25), so it is only ever brought down.
    # A user whose weight is mostly muscle gets full weight, higher cap.
    height_m = height / 100
    bmi = weight / (height_m ** 2) if height_m > 0 else 0
    lbm_male = 0.407 * weight + 0.267 * height - 19.2
    lbm_female = 0.252 * weight + 0.473 * height - 48.3
    lean_mass = {"male": lbm_male, "female": lbm_female}.get(gender, (lbm_male + lbm_female) / 2)
    lean_mass = max(0.0, min(lean_mass, weight))
    if mostly_muscle:
        protein_g = round(min(weight * protein_per_kg, 260))
        from_lean = False
    else:
        protein_weight = min(weight, 25 * height_m ** 2) if bmi > 30 else weight
        by_weight = protein_weight * protein_per_kg
        by_lean = lean_mass * protein_per_kg_lean
        protein_g = round(min(by_weight, by_lean or by_weight, 220))
        from_lean = bool(by_lean) and by_lean < by_weight
    # Protein never takes more than 40% of the calories: an unlikely "mostly
    # muscle" answer (150cm, 110kg on a deficit) left only 13% for carbs
    protein_g = min(protein_g, round(calories * 0.40 / 4))
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
        "calorie_floor_applied": floor_applied,   # target held at the safe minimum
        "protein_from_lean_mass": from_lean,      # True: set from estimated lean mass
        "lean_mass_kg": round(lean_mass, 1),
    }

# ==================== USER PROFILE ENDPOINTS ====================


CAL_ADJUST_MAX = 1000


def safe_calorie_adjustment(macros: dict, adjustment) -> int:
    """The user's manual calorie change (Daily Targets screen), kept inside that
    screen's limits: never below their BMR or under 50g carbs, at most +1,000, in
    50-calorie steps. Re-checked on the server whenever targets change — weight
    loss lowers the base, so a saved −300 could otherwise drop below the floor."""
    adj = int(adjustment or 0)
    if not macros or not macros.get("calories"):
        return adj
    carbs = macros.get("carbs")
    lo = max(-(float(carbs) - 50) * 4 if carbs is not None else float("-inf"),
             min(0.0, float(macros.get("bmr") or 1200) - float(macros["calories"])))
    lo = min(0, math.ceil(lo / 50) * 50)     # a limit, never a forced increase
    return int(max(lo, min(CAL_ADJUST_MAX, adj)))

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
        profile_dict["gender"], profile_dict["activity_level"], profile_dict["goal"],
        profile_dict.get("mostly_muscle"),
    )
    profile_dict["created_at"] = datetime.utcnow()
    profile_dict["updated_at"] = datetime.utcnow()

    # Check free access list
    free_access_entry = await db.free_access.find_one({"email": profile_data.email.lower()})
    if free_access_entry:
        profile_dict["subscription_status"] = "free_access"

    await db.profiles.insert_one(profile_dict)
    # Welcome email — fire-and-forget; never block or fail signup on email issues.
    if profile_dict.get("email"):
        try:
            await send_email(
                to=profile_dict["email"],
                subject="Welcome to InterFitAI 💪",
                html=welcome_email_html(profile_dict.get("name", "")),
            )
        except Exception as _we:
            logger.error(f"Welcome email failed for {profile_dict.get('email')}: {_we}")
    profile_dict["has_password"] = bool(profile_dict.get("password_hash", ""))
    return UserProfile(**profile_dict)

@api_router.get("/profile/{user_id}", response_model=UserProfile)
async def get_profile(user_id: str):
    """Get user profile by ID"""
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile["has_password"] = bool(profile.get("password_hash", ""))
    # A change saved before the targets dropped is shown within today's limits
    profile["calorie_adjustment"] = safe_calorie_adjustment(
        profile.get("calculated_macros"), profile.get("calorie_adjustment"))
    return UserProfile(**profile)

@api_router.put("/profile/{user_id}", response_model=UserProfile)
async def update_profile(user_id: str, update_data: UserProfileUpdate):
    """Update user profile and recalculate macros if needed"""
    profile = await db.profiles.find_one({"id": user_id})
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
    
    # Check if we need to recalculate macros
    macro_fields = ["weight", "height", "age", "gender", "activity_level", "goal", "mostly_muscle"]
    need_recalc = any(field in update_dict for field in macro_fields)
    
    if need_recalc:
        merged = {**profile, **update_dict}
        macros = calculate_macros(
            merged["weight"], merged["height"], merged["age"],
            merged["gender"], merged["activity_level"], merged["goal"],
            merged.get("mostly_muscle"),
        )
        update_dict["calculated_macros"] = macros
    if need_recalc or "calorie_adjustment" in update_dict:
        update_dict["calorie_adjustment"] = safe_calorie_adjustment(
            update_dict.get("calculated_macros") or profile.get("calculated_macros"),
            update_dict.get("calorie_adjustment", profile.get("calorie_adjustment")))
    
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

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

@api_router.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """Email a 6-digit reset code. Always returns 200 — never reveals whether an
    account exists (prevents email enumeration)."""
    import random as _random
    email = (req.email or "").strip().lower()
    generic = {"message": "If an account exists for that email, a reset code has been sent."}
    if not email:
        return generic
    profile = await db.profiles.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
    if not profile:
        return generic
    # Rate limit: max 3 codes per email per 15 minutes
    window_start = datetime.utcnow() - timedelta(minutes=15)
    recent = await db.password_resets.count_documents({"email": email, "created_at": {"$gte": window_start}})
    if recent >= 3:
        return generic
    code = f"{_random.randint(0, 999999):06d}"
    await db.password_resets.insert_one({
        "email": email,
        "code_hash": pwd_context.hash(code),
        "expires_at": datetime.utcnow() + timedelta(minutes=15),
        "attempts": 0,
        "used": False,
        "created_at": datetime.utcnow(),
    })
    await send_email(to=profile["email"], subject="Your InterFitAI reset code",
                     html=reset_code_email_html(code))
    return generic

@api_router.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """Verify the 6-digit code and set a new password."""
    email = (req.email or "").strip().lower()
    code = (req.code or "").strip()
    if len(req.new_password or "") < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    rec = await db.password_resets.find_one(
        {"email": email, "used": False}, sort=[("created_at", -1)]
    )
    if not rec:
        raise HTTPException(status_code=400, detail="No active reset request. Please request a new code.")
    if rec.get("attempts", 0) >= 5:
        raise HTTPException(status_code=429, detail="Too many attempts. Please request a new code.")
    if rec["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This code has expired. Please request a new one.")
    if not pwd_context.verify(code, rec["code_hash"]):
        await db.password_resets.update_one({"_id": rec["_id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(status_code=400, detail="Incorrect code. Please try again.")
    await db.profiles.update_one(
        {"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}},
        {"$set": {"password_hash": pwd_context.hash(req.new_password), "updated_at": datetime.utcnow()}},
    )
    await db.password_resets.update_one({"_id": rec["_id"]}, {"$set": {"used": True}})
    return {"message": "Password reset successfully. You can now sign in."}

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
        "Never choose the same exercise twice in one day.",
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
        "hammer_curl":     ["brachialis", "biceps", "forearms"],
        "tricep_compound": ["triceps", "chest"],
        "chest_fly":       ["chest"],
        "lat_isolation":   ["lats"],
        "shrug":           ["traps"],
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
        names_today = set()
        for ex_idx, slot_meta in enumerate(day['exercises_meta']):
            llm_ex = llm_day_exs[ex_idx] if ex_idx < len(llm_day_exs) else {}

            chosen_name = (llm_ex.get('name') or '').strip() or slot_meta['default_name']
            if chosen_name.lower() in names_today:
                # Same exercise twice in one day → next unused option for this slot
                unused = [o for o in slot_meta['options'] if o.lower() not in names_today]
                if unused:
                    chosen_name = unused[0]
                    llm_ex = {}   # the AI's cues were written for the duplicate
            names_today.add(chosen_name.lower())
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
                "reps":              EliteCoachingEngine.reps_for_exercise(
                                         chosen_name, slot_meta['reps'], blueprint['level']),
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
            + (" | Pregnancy or postpartum: get clearance from your doctor or midwife first, "
               "and stop any exercise that causes pain, dizziness or bleeding."
               if 'pregnancy' in EliteCoachingEngine._normalize_limitations(request.injuries or [])
               else "")
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
    local_date: Optional[str] = None          # the user's calendar day, YYYY-MM-DD
    tz_offset_minutes: Optional[int] = None   # minutes ahead of UTC (Sydney summer = 660)

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
    local_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


def _session_day(s: dict, tz_offset_minutes: int = 0):
    """The calendar day a session belongs to for the user: the day their app
    sent, otherwise the stored UTC time shifted to their time zone."""
    ld = s.get("local_date")
    if ld:
        try:
            return datetime.strptime(ld, "%Y-%m-%d").date()
        except ValueError:
            pass
    d = s.get("date")
    return (d + timedelta(minutes=tz_offset_minutes)).date() if d else None


def _has_completed_set(s: dict) -> bool:
    return any(st.get("completed") for ex in s.get("completed_exercises", []) for st in ex.get("sets", []))


def _session_bests(sessions: list) -> Dict[str, dict]:
    """Best results per exercise (lower-cased name) across sessions:
    heaviest weight (+ most reps at it), most reps at every weight, and most
    reps for bodyweight sets (no weight entered)."""
    bests: Dict[str, dict] = {}
    for ps in sessions:
        for pex in ps.get("completed_exercises", []):
            key = (pex.get("exercise_name") or "").lower().strip()
            if not key:
                continue
            b = bests.setdefault(key, {"name": pex.get("exercise_name"), "best_weight": 0.0,
                                       "reps_at": {}, "bodyweight_reps": 0, "date": None})
            for st in pex.get("sets", []):
                if not st.get("completed") or not st.get("reps"):
                    continue
                r = int(st["reps"])
                w = float(st.get("weight") or 0)
                if w <= 0:
                    if r > b["bodyweight_reps"]:
                        b["bodyweight_reps"] = r
                    continue
                if w > b["best_weight"]:
                    b["best_weight"], b["date"] = w, ps.get("local_date") or ps.get("date")
                if r > b["reps_at"].get(w, 0):
                    b["reps_at"][w] = r
    return bests


def _detect_prs(prior_sessions: list, exercises: List["SessionExercise"]) -> list:
    """New personal records in this session. An exercise done for the first
    time sets a baseline, not a record. Weight PR: heavier than ever. Rep PR:
    more reps than ever at this weight or heavier. Bodyweight PR: more reps."""
    bests = _session_bests(prior_sessions)
    prs = []
    for ex in exercises:
        b = bests.get(ex.exercise_name.lower().strip())
        if not b:
            continue   # first time — nothing to beat yet
        best_pr = None
        for st in ex.sets:
            if not st.completed or not st.reps:
                continue
            w = float(st.weight or 0)
            if w <= 0:
                if b["bodyweight_reps"] and st.reps > b["bodyweight_reps"]:
                    cand = {"type": "reps", "new_value": st.reps, "previous_value": b["bodyweight_reps"],
                            "reps": st.reps, "weight": None}
                else:
                    continue
            elif b["best_weight"] and w > b["best_weight"]:
                cand = {"type": "weight", "new_value": round(w, 2), "previous_value": round(b["best_weight"], 2),
                        "reps": st.reps, "weight": round(w, 2)}
            else:
                prev = max([r for bw, r in b["reps_at"].items() if bw >= w] or [0])
                if not prev or st.reps <= prev:
                    continue
                cand = {"type": "reps", "new_value": st.reps, "previous_value": prev,
                        "reps": st.reps, "weight": round(w, 2)}
            # keep the most impressive: weight PRs beat rep PRs, then bigger numbers
            rank = (cand["type"] == "weight", cand["new_value"])
            if best_pr is None or rank > (best_pr["type"] == "weight", best_pr["new_value"]):
                best_pr = cand
        if best_pr:
            prs.append({"exercise_name": ex.exercise_name, **best_pr})
    return prs


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

    # Weights arrive in kg; keep 2 decimals (lb → kg conversions are long)
    for ex in request.completed_exercises:
        for s in ex.sets:
            if s.weight is not None:
                s.weight = round(s.weight, 2) if s.weight > 0 else None
    if not any(s.completed for ex in request.completed_exercises for s in ex.sets):
        raise HTTPException(status_code=422, detail={
            "error": "no_sets_completed",
            "message": "Tick at least one set before finishing the workout."})

    # Compute total volume (weight × reps across all completed sets)
    total_volume = 0.0
    for ex in request.completed_exercises:
        for s in ex.sets:
            if s.completed and s.weight and s.reps:
                total_volume += s.weight * s.reps

    # ── Personal records: compared with the user's whole history ──
    names = [ex.exercise_name for ex in request.completed_exercises if ex.exercise_name]
    prior_sessions = await db.workout_sessions.find(
        {"user_id": request.user_id,
         "completed_exercises.exercise_name": {"$in": names}},
        {"completed_exercises": 1, "date": 1, "local_date": 1},
    ).to_list(None)
    personal_records = _detect_prs(prior_sessions, request.completed_exercises)

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
        local_date=request.local_date,
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
async def get_workout_stats(user_id: str, tz_offset_minutes: int = 0):
    """Streak, weekly adherence, and total session counts for a user.
    Days and weeks are the user's own (tz_offset_minutes = minutes ahead of UTC)."""
    cursor = db.workout_sessions.find(
        {"user_id": user_id},
        {"date": 1, "local_date": 1, "duration_minutes": 1, "total_volume": 1, "completed_exercises": 1},
    ).sort("date", -1)
    sessions = [s for s in await cursor.to_list(None) if _has_completed_set(s)]
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

    today = (datetime.utcnow() + timedelta(minutes=tz_offset_minutes)).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    days = [d for d in (_session_day(s, tz_offset_minutes) for s in sessions) if d]
    sessions_this_week = sum(1 for d in days if monday <= d <= sunday)

    # Unique training dates sorted newest-first
    training_dates = sorted(set(days), reverse=True)
    if not training_dates:
        return {"current_streak": 0, "best_streak": 0, "sessions_this_week": 0,
                "weekly_target": days_per_week, "total_sessions": total_sessions}

    # Max gap (calendar days) that still keeps the streak alive
    max_gap = (7 + days_per_week - 1) // days_per_week + 1  # ceil(7/dpw) + 1

    # The streak stays alive through planned rest days: same gap rule as
    # between sessions (a Mon/Wed/Fri plan keeps its streak over the weekend)
    last_date = training_dates[0]
    streak_alive = (today - last_date).days <= max_gap

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
    """All-time best per exercise: heaviest weight (with reps at it), or most
    reps for bodyweight exercises, and the day it was set. Weights in kg."""
    sessions = await db.workout_sessions.find(
        {"user_id": user_id}, {"completed_exercises": 1, "date": 1, "local_date": 1}
    ).sort("date", 1).to_list(None)
    out = []
    for key, b in _session_bests(sessions).items():
        if not b["best_weight"] and not b["bodyweight_reps"]:
            continue
        d = b["date"]
        out.append({
            "exercise_name": b["name"],
            "best_weight": round(b["best_weight"], 2),
            "best_reps_at_weight": b["reps_at"].get(b["best_weight"], 0),
            "best_bodyweight_reps": b["bodyweight_reps"],
            "date": d if isinstance(d, str) else (d.strftime("%Y-%m-%d") if d else None),
        })
    out.sort(key=lambda r: r["exercise_name"].lower())
    return out


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

def _remap_day_performance(perf: dict, day_index: int, mapping: Dict[int, Optional[int]]) -> dict:
    """Saved sets are keyed "day-exercise-set". When a day's exercises move,
    move their saved sets too: mapping is old exercise index → new index
    (None drops it, e.g. a replaced or deleted exercise)."""
    out = {}
    prefix = f"{day_index}-"
    for k, v in (perf or {}).items():
        if not k.startswith(prefix):
            out[k] = v
            continue
        try:
            _, ex, st = k.split("-")
            ex = int(ex)
        except ValueError:
            out[k] = v
            continue
        new = mapping.get(ex, ex)
        if new is not None:
            out[f"{day_index}-{new}-{st}"] = v
    return out


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
    
    # Replace the exercise (the new one starts with no saved sets)
    exercises[request.exercise_index] = request.new_exercise
    workout_days[request.day_index]["exercises"] = exercises
    perf = _remap_day_performance(workout.get("performance", {}), request.day_index,
                                  {request.exercise_index: None})

    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"workout_days": workout_days, "performance": perf, "updated_at": datetime.utcnow()}}
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
    
    # Remove the exercise; later exercises' saved sets move up with them
    n = len(exercises)
    exercises.pop(request.exercise_index)
    workout_days[request.day_index]["exercises"] = exercises
    mapping = {i: (None if i == request.exercise_index else i - 1 if i > request.exercise_index else i)
               for i in range(n)}
    perf = _remap_day_performance(workout.get("performance", {}), request.day_index, mapping)

    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"workout_days": workout_days, "performance": perf, "updated_at": datetime.utcnow()}}
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
    if sorted(request.exercise_order) != list(range(len(exercises))):
        raise HTTPException(status_code=400, detail="Order must list every exercise once")
    workout_days[request.day_index]["exercises"] = [exercises[i] for i in request.exercise_order]
    perf = _remap_day_performance(workout.get("performance", {}), request.day_index,
                                  {old: new for new, old in enumerate(request.exercise_order)})
    await db.workouts.update_one(
        {"id": workout_id},
        {"$set": {"workout_days": workout_days, "performance": perf, "updated_at": datetime.utcnow()}}
    )
    return {"message": "Exercises reordered successfully"}



def _params_for_added_exercise(name: str, goal: str, level: str = 'intermediate') -> dict:
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
        'reps':         EliteCoachingEngine.reps_for_exercise(name, p.get('reps', '10-12'), level),
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
        workout.get("fitness_level", "intermediate"),
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
# Every number in a meal plan is calculated by nutrition_engine from the
# listed ingredients (food + grams). The AI only chooses foods and grams.
from food_database import INGREDIENT_MACROS  # noqa: E402  (also used by the food-log reference check)
from nutrition_engine import (  # noqa: E402
    DIET_BANNED_TERMS, FoodRules, MACRO_KEYS, balance_day, build_day, build_safe_meal,
    day_totals, finalize_meal, is_on_target, items_from_raw, make_draft, max_deviation, meal_targets, reconcile_instructions,
    optimise_portions, prompt_food_names, template_draft,
    build_plate, grams_in_text, is_composite_name, parse_portions, plate_totals, portion_grams, resolve_food,
    snap_item_from_text,
    snap_item,
    food_matches,
    calculate_meal_text, meal_summary, split_foods,
)
import food_lookup as FoodLookup  # noqa: E402
from meal_templates import TEMPLATES_BY_STYLE  # noqa: E402

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]
PLAN_NAMES = {"keto": "Keto", "carnivore": "Carnivore", "paleo": "Paleo", "vegan": "Vegan",
              "vegetarian": "Vegetarian", "high_protein": "High Protein", "balanced": "Balanced"}
# Banning a protein family by name bans every member ("beef" → sirloin, ribeye…)
PROTEIN_GROUPS = {
    'chicken': ['chicken breast', 'chicken thigh', 'chicken', 'chicken wings', 'chicken drumstick', 'poultry'],
    'beef': ['beef', 'sirloin', 'ribeye', 'ground beef', 'steak', 'beef mince', 'brisket', 'flank steak', 'filet mignon', 'tenderloin', 'roast beef', 'corned beef', 'prime rib', 'eye of round'],
    'pork': ['pork', 'bacon', 'pork chop', 'ham', 'pork loin', 'pork belly', 'sausage', 'pork tenderloin', 'pulled pork', 'ribs', 'chorizo', 'prosciutto'],
    'turkey': ['turkey', 'turkey breast', 'ground turkey', 'turkey bacon', 'turkey mince'],
    'fish': ['fish', 'salmon', 'tuna', 'cod', 'tilapia', 'white fish', 'sea bass', 'halibut', 'mahi mahi', 'trout', 'sardines', 'mackerel', 'anchovies', 'swordfish', 'haddock', 'snapper'],
    'seafood': ['shrimp', 'prawns', 'crab', 'lobster', 'scallops', 'mussels', 'clams', 'oysters', 'calamari', 'squid', 'octopus'],
    'eggs': ['eggs', 'egg', 'egg whites', 'omelette', 'frittata'],
    'dairy': ['greek yogurt', 'cottage cheese', 'cheese', 'milk', 'whey protein', 'cream', 'butter', 'yogurt'],
    'lamb': ['lamb', 'lamb chops', 'lamb leg', 'lamb shank', 'ground lamb', 'lamb shoulder'],
}
TEMPLATE_POOLS = {"vegan": ["vegan"], "vegetarian": ["vegetarian", "vegan"], "keto": ["keto"],
                  "carnivore": ["carnivore"], "paleo": ["paleo"], "high_protein": ["high_protein", "balanced"],
                  "balanced": ["balanced", "high_protein", "vegetarian", "vegan", "paleo"]}
DIET_INSTRUCTIONS = {
    "keto": "STRICT KETO: total carbs at or under the carb target. No grains, sugar, bread, pasta, rice, potatoes, "
            "legumes or fruit (small amounts of berries only). High fat from butter, olive oil, avocado, cheese, fatty meats.",
    "carnivore": "CARNIVORE: ONLY meat, fish, eggs, butter/ghee/tallow, cheese, salt. NO plants at all.",
    "paleo": "PALEO: no grains (incl. oats, rice, corn), no dairy (ghee is fine), no legumes (incl. peanuts, soy), "
             "no refined sugar. Sweet potato instead of grains.",
    "vegan": "VEGAN: no animal products whatsoever (no meat, fish, eggs, dairy, honey). Every meal needs a high-protein "
             "base: seitan, tempeh, extra firm tofu, edamame, pea protein powder, lentils or beans.",
    "vegetarian": "VEGETARIAN: no meat or fish. Eggs and dairy are fine. Build protein from eggs, Greek yogurt, "
                  "cottage cheese, tofu, tempeh and legumes.",
    "high_protein": "HIGH PROTEIN: lean proteins at every meal, but STILL hit the carb target from rice, oats, potatoes, fruit.",
}
STYLE_FOOD_IDEAS = {
    'keto': 'ribeye, salmon, eggs, bacon, avocado, butter, heavy cream, cheese, macadamia nuts, leafy greens, broccoli, cauliflower.',
    'vegan': 'tempeh, seitan, extra firm tofu, black beans, lentils, quinoa, chickpeas, edamame, nuts, seeds, pea protein powder.',
    'vegetarian': 'eggs, greek yogurt, cottage cheese, tempeh, legumes, quinoa, sweet potato, brown rice.',
    'paleo': 'lean beef, salmon, chicken, sweet potato, almond flour, coconut oil, berries, green vegetables.',
    'carnivore': 'beef (ribeye/sirloin/mince), chicken thighs, salmon, bacon, eggs, butter.',
    'high_protein': 'chicken breast, turkey, tuna, egg whites, greek yogurt, cottage cheese, lean beef, whey protein, plus oats, rice, potatoes and fruit for carbs.',
    'balanced': 'a rich variety: lean proteins, complex carbs (rice, oats, sweet potato), healthy fats, diverse vegetables.',
    'whole_foods': 'only whole, unprocessed ingredients: vegetables, legumes, lean proteins, whole grains.',
}
ALLERGY_SPECIFICS = {
    'gluten': 'NO wheat, barley, rye, oats (any), spelt, seitan, pasta, noodles, couscous, bulgur, orzo, bread, bagels, naan, granola, soy sauce (use tamari).',
    'dairy': 'NO milk, cheese (incl. parmesan, mozzarella, ricotta, halloumi, paneer), yogurt, skyr, kefir, butter, ghee, cream, whey, casein.',
    'lactose': 'NO milk, cheese, yogurt, skyr, kefir, butter, ghee, cream, whey, casein.',
    'nuts': 'NO almonds, cashews, walnuts, pecans, pistachios, brazil nuts, hazelnuts, macadamia, peanuts, nut butters, nut milks, pesto.',
    'eggs': 'NO eggs in any form, no mayonnaise or aioli.',
    'soy': 'NO tofu, tempeh, edamame, soy sauce, tamari, soy milk, miso.',
    'shellfish': 'NO shrimp, prawns, crab, lobster, scallops, oysters, mussels, clams, squid.',
    'fish': 'NO fish of any kind, no fish sauce.',
}


def _style_key(eating_style: str) -> str:
    return eating_style if eating_style in TEMPLATES_BY_STYLE else "balanced"


def diet_macro_targets(eating_style: str, cal, pro, carb, fat) -> dict:
    """Keto/carnivore keep the user's calories but use the diet's own split."""
    if eating_style == 'keto':
        fat = round(cal * 0.72 / 9)
        carb = min(30, round(cal * 0.05 / 4))
        pro = round((cal - fat * 9 - carb * 4) / 4)
    elif eating_style == 'carnivore':
        fat = round(cal * 0.70 / 9)
        carb = 5
        pro = round((cal - fat * 9 - carb * 4) / 4)
    return {"calories": cal, "protein": pro, "carbs": carb, "fats": fat}


def _avoid_terms(foods_to_avoid: str) -> list:
    terms = [f.strip().lower() for f in (foods_to_avoid or "").split(",") if f.strip()]
    for t in list(terms):
        if t in PROTEIN_GROUPS:
            terms.extend(PROTEIN_GROUPS[t])
    return list(dict.fromkeys(terms))


def _parse_json_obj(content: str):
    text = (content or "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in AI response")
    return json.loads(text[start:end + 1])


def _food_list_text(rules: FoodRules) -> str:
    rows = []
    for name in prompt_food_names(rules):
        c, p, cb, f = INGREDIENT_MACROS[name]
        rows.append(f"{name} {c:g}/{p:g}/{cb:g}/{f:g}")
    return "; ".join(rows)


def _prohibitions_text(allergies, foods_to_avoid) -> str:
    lines = [f"  - {a.upper()}: {ALLERGY_SPECIFICS.get(a.lower(), f'NO {a} in any form.')}" for a in allergies]
    if foods_to_avoid and foods_to_avoid.strip():
        lines.append(f"  - FOODS TO AVOID: {foods_to_avoid.upper()}")
    return "\n".join(lines) if lines else "  - None"


_INGREDIENT_RULES = """INGREDIENT RULES (critical):
- Every ingredient is an object {"food": "<exact name from FOOD LIST>", "grams": <number>}.
- GRAMS ONLY. Never cups, ml, scoops, slices or counts: 2 eggs -> 100g eggs, a scoop of whey -> 30g whey protein,
  15ml honey -> 21g honey, 2 rice cakes -> 18g rice cakes.
- Whole-unit foods in whole units' weight: eggs 50g each, bread 30g per slice, wraps 60g, rice cakes 9g.
- Meat, fish, rice, pasta, grains and legumes are COOKED weights. Oats are DRY weight ("rolled oats").
- Pick grams so the meal lands near its target using the per-100g values (kcal/protein/carbs/fat).
  Protein, carbs and fat come from EVERY food (grains, legumes, dairy and bread add protein too) —
  add them all up and do NOT overshoot the protein or calorie target.
  Do NOT output any calorie or macro numbers — they are calculated from your foods and grams.
- Beef mince must be "beef mince 95/5" (extra lean/premium/5-star), "beef mince 90/10" (lean) or "beef mince 80/20" (regular/fatty).
- Instructions: 2-3 short steps, never mention gram amounts.
- Every food the instructions mention MUST be in the ingredient list with grams. If the meal is cooked in fat,
  list that fat (e.g. 5g butter or 5g olive oil); otherwise write "use a non-stick pan"."""


async def _ai_plan_drafts(eating_style, plan_name, targets, rules, allergies, request):
    """One Sonnet call for the full 3-day plan. Returns (days, plan_title) where
    days = [ {meal_type: (draft, problems)} ×3 ], or (None, None) on failure."""
    per_meal = {mt: meal_targets(targets, mt, MEAL_TYPES) for mt in MEAL_TYPES}
    per_meal_txt = "\n".join(
        f"  {mt.capitalize()}: ~{round(t['calories'])} kcal | {round(t['protein'])}g P | {round(t['carbs'])}g C | {round(t['fats'])}g F"
        for mt, t in per_meal.items())
    fat_pct = targets["fats"] * 9 / targets["calories"] * 100 if targets["calories"] else 30
    protein_guidance = ("Prefer LEAN proteins (chicken breast, turkey breast, white fish, egg whites); minimise added fats."
                        if fat_pct < 25 else
                        "Use fattier proteins (ribeye, chicken thighs, salmon, beef mince 80/20, whole eggs) and added fats."
                        if fat_pct > 40 else
                        "Balance lean and moderate-fat proteins (sirloin, chicken, salmon, beef mince 90/10, whole eggs).")
    if request.preferred_foods and request.preferred_foods.strip():
        foods_section = (f"PREFERRED FOODS: {request.preferred_foods}. EVERY preferred food must appear at least once on EVERY day "
                         "where it fits the diet, using the closest FOOD LIST name. Respect the exact variant the user names "
                         "(e.g. 'fatty beef mince' = beef mince 80/20, 'extra lean' = beef mince 95/5).")
    else:
        foods_section = f"No preferred foods given — choose elite, nutritionist-approved foods. Ideas: {STYLE_FOOD_IDEAS.get(eating_style, STYLE_FOOD_IDEAS['balanced'])}"
    prompt = f"""You are an ELITE sports nutritionist. Create a fully personalised 3-day meal plan: breakfast, lunch, dinner and snack every day.

DIET STYLE: {eating_style.upper().replace('_', ' ')}
{DIET_INSTRUCTIONS.get(eating_style, '')}

DAILY TARGETS: {targets['calories']} kcal | {targets['protein']}g protein | {targets['carbs']}g carbs | {targets['fats']}g fat
PER-MEAL TARGETS:
{per_meal_txt}

ABSOLUTE PROHIBITIONS — never include these, not even as a garnish:
{_prohibitions_text(allergies, request.foods_to_avoid)}

{foods_section}
{protein_guidance}

FOOD LIST (name kcal/protein/carbs/fat per 100g) — use ONLY these exact names:
{_food_list_text(rules)}

{_INGREDIENT_RULES}
- All 3 days must have completely different meals with appealing, descriptive names.

Return ONLY this JSON (no markdown):
{{"name": "<plan name>", "meal_days": [
  {{"day": "Day 1", "meals": [
    {{"meal_type": "breakfast", "name": "<meal name>", "ingredients": [{{"food": "<food name>", "grams": <number>}}], "instructions": "<steps>", "prep_time_minutes": <number>}},
    {{"meal_type": "lunch", ...same structure}}, {{"meal_type": "dinner", ...}}, {{"meal_type": "snack", ...}}
  ]}},
  {{"day": "Day 2", "meals": [...]}},
  {{"day": "Day 3", "meals": [...]}}
]}}"""
    try:
        content = await call_claude_sonnet(
            system_message="You are an elite nutritionist. You choose foods and gram amounts only; "
                           "nutrition numbers are calculated by code. Never use a prohibited food.",
            user_message=prompt, temperature=0.4, max_tokens=7000)
        data = _parse_json_obj(content)
    except Exception as e:
        logger.error(f"AI meal plan generation error: {e}")
        return None, None
    days = []
    for d in (data.get("meal_days") or [])[:3]:
        by_type = {}
        for m in d.get("meals") or []:
            mt = str(m.get("meal_type", "")).lower().strip()
            if mt not in MEAL_TYPES or mt in by_type:
                continue
            by_type[mt] = _draft_with_problems(m, mt, rules)
        days.append(by_type)
    if not days:
        return None, None
    return days, data.get("name")


def _draft_with_problems(m: dict, meal_type: str, rules: FoodRules):
    items, unknown = items_from_raw(m.get("ingredients"))
    big_unknown = [u for u in unknown if not (u[1] and u[1] <= 10)]
    if unknown:
        logger.info(f"Meal '{m.get('name')}': unresolved ingredients {unknown}")
    draft = make_draft(m.get("name"), meal_type, items, m.get("instructions"), m.get("prep_time_minutes"))
    problems = rules.violations(draft["name"], items, draft["instructions"])
    problems += reconcile_instructions(draft, rules)
    problems += [f"unknown:{u[0]}" for u in big_unknown]
    if not items:
        problems.append("no ingredients")
    return draft, problems


async def _ai_single_meal(meal_type, rules, target, eating_style, allergies, foods_to_avoid, avoid_names, notes="", attempts=3):
    """Generate ONE rule-compliant meal (grams only). Retries with feedback
    when a banned or unknown food appears. Returns a draft or None."""
    feedback = ""
    for attempt in range(attempts):
        prompt = f"""Create ONE {meal_type} for a {eating_style.replace('_', ' ')} meal plan.
TARGET for this meal: ~{round(target['calories'])} kcal | {round(target['protein'])}g protein | {round(target['carbs'])}g carbs | {round(target['fats'])}g fat
{DIET_INSTRUCTIONS.get(eating_style, '')}
{notes}

ABSOLUTE PROHIBITIONS — never include these, not even as a garnish:
{_prohibitions_text(allergies, foods_to_avoid)}

Do not reuse any of these meal names: {', '.join(sorted(set(avoid_names))) or 'none'}

FOOD LIST (name kcal/protein/carbs/fat per 100g) — use ONLY these exact names:
{_food_list_text(rules)}

{_INGREDIENT_RULES}
{feedback}
Return ONLY this JSON: {{"name": "<meal name>", "meal_type": "{meal_type}", "ingredients": [{{"food": "<food name>", "grams": <number>}}], "instructions": "<steps>", "prep_time_minutes": <number>}}"""
        try:
            content = await call_claude_haiku(
                system_message="You are a precision nutritionist. You choose foods and gram amounts only; "
                               "nutrition numbers are calculated by code. Never use a prohibited food.",
                user_message=prompt, temperature=0.5, max_tokens=900)
            data = _parse_json_obj(content)
        except Exception as e:
            logger.warning(f"Single-meal attempt {attempt + 1} failed: {e}")
            continue
        draft, problems = _draft_with_problems(data, meal_type, rules)
        if not problems:
            return draft
        logger.warning(f"Single-meal attempt {attempt + 1} rejected '{draft['name']}': {problems}")
        feedback = (f"Your previous answer '{draft['name']}' was REJECTED because of: {', '.join(problems)}. "
                    "Create a completely different meal using only allowed FOOD LIST names.")
    return None


def _template_replacement(style_key, meal_type, rules, used_names):
    for st in TEMPLATE_POOLS.get(style_key, ["balanced"]):
        for day in TEMPLATES_BY_STYLE[st].values():
            tpl = day.get(meal_type)
            if not tpl or tpl["name"] in used_names:
                continue
            d = template_draft(meal_type, tpl)
            if not rules.violations(d["name"], d["items"], d["instructions"]) and not reconcile_instructions(d, rules):
                return d
    return None


async def _replacement_meal(meal_type, rules, target, eating_style, allergies, foods_to_avoid, used_names, use_ai=True, notes=""):
    """A NEW meal for a slot whose meal broke the rules: AI → template → safe meal."""
    draft = None
    if use_ai:
        draft = await _ai_single_meal(meal_type, rules, target, eating_style, allergies, foods_to_avoid, used_names, notes)
    if draft is None:
        draft = _template_replacement(_style_key(eating_style), meal_type, rules, used_names)
    if draft is None:
        draft = build_safe_meal(meal_type, rules)
    used_names.add(draft["name"])
    return draft


@api_router.post("/mealplans/generate", response_model=MealPlan)
async def generate_meal_plan(request: MealPlanGenerateRequest):
    """Generate a 3-day meal plan. The AI picks foods + grams; code checks every
    meal against allergies/avoid list/diet, tunes portions to the targets and
    calculates every displayed number from the listed ingredients."""
    profile = await db.profiles.find_one({"id": request.user_id})
    if not profile or not profile.get("calculated_macros"):
        raise HTTPException(status_code=404, detail="User profile with macros not found. Please set up your profile first.")

    # ── Monthly generation limit (mirrors workout programs: cost + adherence) ──
    MEAL_PLAN_MONTHLY_LIMIT = 4
    if not is_admin(profile.get("email", "")):
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        used = await db.meal_generation_events.count_documents({
            "user_id": request.user_id,
            "created_at": {"$gte": month_start},
        })
        if used >= MEAL_PLAN_MONTHLY_LIMIT:
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
                        f"You've used your {MEAL_PLAN_MONTHLY_LIMIT} meal plan generations this month. "
                        f"They reset on {reset_date}. "
                        "You can still swap individual meals anytime — consistency with your plan beats a new plan."
                    ),
                    "reset_date": reset_date,
                    "used": used,
                    "limit": MEAL_PLAN_MONTHLY_LIMIT,
                },
            )

    macros = profile["calculated_macros"]
    # Honour the user's manual calorie adjustment (Macro Targets screen) so the
    # plan is built for the same daily target the food log displays.
    # Carbs absorb the adjustment (cal/4), matching the food log's display logic.
    manual_cal_adj = safe_calorie_adjustment(macros, profile.get("calorie_adjustment"))
    target_cal = macros['calories'] + manual_cal_adj
    target_pro = macros['protein']
    target_carb = max(0, macros['carbs'] + round(manual_cal_adj / 4))
    target_fat = macros['fats']

    eating_style = (request.food_preferences or "balanced").lower()
    style_key = _style_key(eating_style)
    plan_name = PLAN_NAMES[style_key]
    targets = diet_macro_targets(eating_style, target_cal, target_pro, target_carb, target_fat)
    allergies = [a for a in (request.allergies or []) if a and a.lower() != "none"]
    rules = FoodRules(allergies, _avoid_terms(request.foods_to_avoid), eating_style)
    logger.info(f"Meal plan | style={eating_style} | targets={targets} | preferred={request.preferred_foods} "
                f"| avoid={request.foods_to_avoid} | allergies={allergies}")

    ai_days, ai_title = await _ai_plan_drafts(eating_style, plan_name, targets, rules, allergies, request)
    use_ai = ai_days is not None
    if not use_ai:
        logger.info("Falling back to template-based generation")
    templates = TEMPLATES_BY_STYLE[style_key]

    # Assemble 3 days × 4 slots; every slot that breaks a rule gets a NEW meal.
    day_slots, used_names, repairs = [], set(), []
    for di in range(3):
        slots = {}
        for mt in MEAL_TYPES:
            if use_ai:
                draft, problems = (ai_days[di].get(mt) if di < len(ai_days) else None) or (None, ["missing"])
            else:
                draft = template_draft(mt, templates[f"day{di + 1}"][mt])
                problems = rules.violations(draft["name"], draft["items"], draft["instructions"])
                problems += reconcile_instructions(draft, rules)
            if draft is not None and not problems:
                used_names.add(draft["name"])
            else:
                logger.warning(f"Day {di + 1} {mt}: replacing meal ({problems})")
                repairs.append((di, mt))
            slots[mt] = draft if not problems else None
        day_slots.append(slots)

    async def _repair(di, mt):
        day_slots[di][mt] = await _replacement_meal(
            mt, rules, meal_targets(targets, mt, MEAL_TYPES), eating_style, allergies,
            request.foods_to_avoid, used_names, use_ai=use_ai)
    if repairs:
        await asyncio.gather(*[_repair(di, mt) for di, mt in repairs])

    meal_days = []
    for di, slots in enumerate(day_slots):
        drafts = [slots[mt] for mt in MEAL_TYPES]
        balance_day(drafts, targets, rules)
        finals = [finalize_meal(d, f"d{di + 1}m{i + 1}") for i, d in enumerate(drafts)]
        day = build_day(f"Day {di + 1}", finals, targets)
        meal_days.append(day)
        logger.info(f"Day {di + 1}: {day['total_calories']} cal, {day['total_protein']}P, {day['total_carbs']}C, "
                    f"{day['total_fats']}F (target {targets}) on_target={day['on_target']}")

    try:
        meal_plan = MealPlan(
            user_id=request.user_id,
            name=(ai_title if use_ai and ai_title else f"{plan_name} 3-Day Meal Plan"),
            food_preferences=request.food_preferences,
            preferred_foods=request.preferred_foods,
            foods_to_avoid=request.foods_to_avoid,
            supplements=request.supplements,
            supplements_custom=request.supplements_custom,
            allergies=request.allergies,
            target_calories=targets["calories"],
            target_protein=targets["protein"],
            target_carbs=targets["carbs"],
            target_fats=targets["fats"],
            meal_days=[MealDay(**d) for d in meal_days],
        )
        await db.mealplans.insert_one(meal_plan.model_dump())
        await db.meal_generation_events.insert_one({
            "user_id": request.user_id,
            "created_at": datetime.utcnow(),
        })
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
    """Swap one meal. The new meal's numbers are calculated from its own
    ingredients, and its portions are tuned so the day stays on target."""
    plan = await db.mealplans.find_one({"id": request.meal_plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Meal plan not found")
    try:
        day = plan["meal_days"][request.day_index]
        current_meal = day["meals"][request.meal_index]
    except (IndexError, KeyError):
        raise HTTPException(status_code=400, detail="Invalid day or meal index")

    profile = await db.profiles.find_one({"id": request.user_id})
    macros = profile.get("calculated_macros", {}) if profile else {}
    plan_targets = {
        "calories": float(plan.get("target_calories") or macros.get("calories", 2000)),
        "protein": float(plan.get("target_protein") or macros.get("protein", 150)),
        "carbs": float(plan.get("target_carbs") or macros.get("carbs", 200)),
        "fats": float(plan.get("target_fats") or macros.get("fats", 70)),
    }
    meal_type = current_meal.get("meal_type", "lunch")
    eating_style = (plan.get("food_preferences") or "balanced").lower()
    allergies = [a for a in (plan.get("allergies") or []) if a and a.lower() != "none"]
    foods_to_avoid = plan.get("foods_to_avoid") or ""
    avoid = _avoid_terms(foods_to_avoid)
    pref = request.swap_preference or "similar"
    if pref == "vegetarian":
        avoid += DIET_BANNED_TERMS["vegetarian"]
    rules = FoodRules(allergies, avoid, eating_style)

    # Target = what this slot needs for the DAY to land on target (falls back
    # to the current meal's macros if the rest of the day is far off).
    def _f(v):
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return 0.0
    others = [m for i, m in enumerate(day["meals"]) if i != request.meal_index]
    remainder = {k: plan_targets[k] - sum(_f(m.get(k)) for m in others) for k in MACRO_KEYS}
    current = {k: _f(current_meal.get(k)) for k in MACRO_KEYS}
    use_remainder = all(remainder[k] >= 0 for k in MACRO_KEYS) and current["calories"] > 0 and \
        0.5 * current["calories"] <= remainder["calories"] <= 1.6 * current["calories"]
    base = remainder if use_remainder else current
    target = dict(base)
    notes = "Similar macros to the current meal but a DIFFERENT dish."
    if pref == "higher_protein":
        target["protein"] = base["protein"] * 1.4
        target["carbs"] = max(0.0, base["carbs"] - (target["protein"] - base["protein"]))
        notes = "Noticeably HIGHER in protein than the current meal, fewer carbs, similar calories."
    elif pref == "lower_calories":
        cut = base["calories"] * 0.25
        ck, fk = base["carbs"] * 4, base["fats"] * 9
        share_c = ck / (ck + fk) if (ck + fk) > 0 else 0.5
        target["calories"] = base["calories"] * 0.75
        target["carbs"] = max(0.0, base["carbs"] - cut * share_c / 4)
        target["fats"] = max(0.0, base["fats"] - cut * (1 - share_c) / 9)
        notes = "About 25% FEWER calories than the current meal while keeping the protein."
    elif pref == "quick_prep":
        notes = "Must take UNDER 15 minutes to prepare. Similar macros to the current meal."
    elif pref == "vegetarian":
        notes = "100% vegetarian — no meat or fish. Similar macros to the current meal."
    elif pref == "budget":
        notes = "Affordable, everyday supermarket ingredients. Similar macros to the current meal."

    used_names = {m.get("name", "") for d in plan["meal_days"] for m in d.get("meals", [])}
    logger.info(f"=== MEAL SWAP === plan={request.meal_plan_id} day={request.day_index} meal={request.meal_index} "
                f"pref={pref} target={ {k: round(v) for k, v in target.items()} } allergies={allergies} avoid='{foods_to_avoid}'")
    others_items = [items_from_raw(m.get("ingredients"))[0] for m in others]

    def _tune(draft) -> float:
        """Tune the candidate's grams; returns its worst miss (≤ 1.0 = on target)."""
        if pref in ("higher_protein", "lower_calories"):
            # deliberately different macros: tune the new meal to its own target
            drafts, goal, idx, shares = [draft], target, [0], {meal_type: 1.0}
        else:
            # tune ONLY the new meal's grams so the whole DAY lands on target;
            # the user's other meals stay exactly as they are
            drafts = [make_draft(m.get("name"), m.get("meal_type", "meal"), [dict(it) for it in its])
                      for m, its in zip(others, others_items)] + [draft]
            goal, idx, shares = plan_targets, [len(others)], None
        if not optimise_portions(drafts, goal, adjustable=idx, shares=shares):
            optimise_portions(drafts, goal, widen=True, adjustable=idx, shares=shares)
        return max_deviation(drafts, goal)

    # Some dishes can't fit the day however the grams are tuned (e.g. a fatty
    # snack when the day is already at its fat limit) — try other dishes.
    best = None
    for n in (1, 2, 2):
        cands = await asyncio.gather(*[_replacement_meal(meal_type, rules, target, eating_style, allergies, foods_to_avoid,
                                                         used_names, use_ai=True, notes=notes) for _ in range(n)])
        for cand in cands:
            miss = _tune(cand)
            if best is None or miss < best[1]:
                best = (cand, miss)
        if best[1] <= 1.0:
            break
        logger.info(f"Swap candidates missed the target (worst {best[1]:.2f}× tolerance) — trying other dishes")
    draft = best[0]
    new_meal = finalize_meal(draft, str(uuid.uuid4()))
    if pref == "quick_prep":
        new_meal["prep_time_minutes"] = min(new_meal["prep_time_minutes"], 15)

    day["meals"][request.meal_index] = new_meal
    totals = day_totals(day["meals"])
    day.update(totals)
    day["on_target"] = is_on_target(totals, plan_targets)
    await db.mealplans.update_one({"id": request.meal_plan_id}, {"$set": {"meal_days": plan["meal_days"]}})
    logger.info(f"✅ Swap: {new_meal['name']} — {new_meal['calories']} cal {new_meal['protein']}P "
                f"{new_meal['carbs']}C {new_meal['fats']}F | day on_target={day['on_target']}")
    return {"alternate_meal": new_meal, "day_totals": {**totals, "on_target": day["on_target"]}}

# ==================== FAVORITE MEALS ENDPOINTS ====================

@api_router.post("/food/favorite")
async def add_favorite_meal(user_id: str, meal_name: str, calories: int, protein: float, carbs: float, fats: float, serving_size: str = "1 serving"):
    """Add a meal to favorites"""
    # Premium gate — same pattern as meal-plan / workout generation.
    access = await check_subscription_access(user_id)
    if not access.get("has_access"):
        raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Nutrition Tracking",
                                                     "message": "Nutrition tracking is a premium feature. Subscribe to unlock food search, logging, and photo analysis."})
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
    # Premium gate — resolve user from the log doc.
    log_user_id = log.get("user_id")
    if log_user_id:
        access = await check_subscription_access(log_user_id)
        if not access.get("has_access"):
            raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Nutrition Tracking",
                                                         "message": "Nutrition tracking is a premium feature. Subscribe to unlock food search, logging, and photo analysis."})

    new_status = not log.get("is_favorite", False)
    await db.food_logs.update_one({"id": log_id}, {"$set": {"is_favorite": new_status}})
    return {"message": f"Favorite {'added' if new_status else 'removed'}", "is_favorite": new_status}

# ==================== FOOD LOGGING ENDPOINTS ====================

# ------------------------------------------------------------------------
# Nutrition-accuracy safety net — applied to EVERY food-entry-creating path
# (photo scan, text search results, AI lookup, manual entry).
#
# Purpose: catch systemic misreads (impossible macros, wrong reference values,
# unreconciled calories) before they hit the DB. Every entry that reaches
# storage has been checked against:
#   Fix 1 — deterministic calorie reconciliation (10% threshold, overwrite on breach)
#   Fix 2 — physical plausibility (mass-conservation, energy-density, per-macro ceiling)
#   Fix 4 — reference-table cross-check (per-100g divergence >30% => flag)
# The helper NEVER raises — it returns a sanitised dict plus a list of
# structured warnings so callers can decide whether to retry (AI paths) or
# accept the corrected values (manual entry).
# ------------------------------------------------------------------------
import re as _nutre

def _norm_food_name(name: str) -> str:
    """Lowercase, strip parenthetical qualifiers, remove common state words.
    Enough to match 'Beef Mince, 5% (raw, 100g)' against 'beef mince'."""
    n = (name or "").lower()
    n = _nutre.sub(r"\([^)]*\)", " ", n)         # remove parentheticals
    n = _nutre.sub(r"[,\.]", " ", n)              # drop punctuation
    n = _nutre.sub(
        r"\b(raw|cooked|grilled|baked|boiled|fried|roasted|pan[- ]?browned|steamed|large|medium|small|whole|per|serving|100g|1kg|1lb)\b",
        " ",
        n,
    )
    n = _nutre.sub(r"\s+", " ", n).strip()
    return n

def _is_physically_plausible_per_100g(per_100g: dict) -> tuple[bool, str]:
    """Physical-laws-only plausibility check for a per-100g nutrition block.
    No reference table involved — this is Atwater + basic conservation.

    Returns (ok, reason). Rejects impossible values no legitimate food label
    could produce:
      • any macro > 100g per 100g
      • protein+carbs+fats mass exceeds 100g
      • calories ∉ [0, 900] (900 = pure fat upper bound)
      • calories vs P*4+C*4+F*9 diverges more than 30% (widened for label
        food-specific Atwater factors; catches 596cal/100g claimed for eggs
        where derived is 143)

    This is the SAFETY NET for correctly-read labels — it never false-positives
    on legitimate composite dishes (which pass 4/4/9 perfectly) but catches
    the model returning fabricated calorie numbers on a real label."""
    if not isinstance(per_100g, dict):
        return False, "not_a_dict"
    try:
        cal = float(per_100g.get("calories") or 0)
        p   = float(per_100g.get("protein")  or 0)
        c   = float(per_100g.get("carbs")    or 0)
        f   = float(per_100g.get("fats")     or 0)
    except (TypeError, ValueError):
        return False, "non_numeric"
    if p < 0 or c < 0 or f < 0 or cal < 0:
        return False, "negative"
    if p > 100 or c > 100 or f > 100:
        return False, f"macro_over_100g p={p} c={c} f={f}"
    if p + c + f > 100.5:  # tiny slack for rounding
        return False, f"mass_sum_over_100g sum={p+c+f:.1f}"
    if cal > 900:
        return False, f"cal_over_900 cal={cal}"
    derived = p * 4 + c * 4 + f * 9
    if cal > 0 and derived > 0:
        gap = abs(cal - derived) / max(cal, derived, 1.0)
        if gap > 0.30:  # 30% is generous for legit Atwater variance
            return False, f"cal_atwater_mismatch stated={cal:.0f} derived={derived:.0f} gap={gap:.0%}"
    return True, "ok"


def _lookup_reference(food_name: str):
    """Return (cal, p, c, f) per 100g when the food is a single database food,
    else None. Branded / composite / prepared names ("Youfoodz Chicken
    Teriyaki") return None instead of a wrong single-ingredient match."""
    if not food_name or is_composite_name(food_name):
        return None
    key = resolve_food(_norm_food_name(food_name))
    return INGREDIENT_MACROS[key] if key else None

# ── Composite-product safety guard ─────────────────────────────────────
# The reference table (INGREDIENT_MACROS) contains SINGLE INGREDIENT whole
# foods. It must NEVER substitute nutrition for a branded / packaged /
# composite product, because a substring match on the product name will
# silently corrupt the total by hundreds of calories.
#
# Concrete failure that motivated this guard:
#   "Youfoodz Chicken Teriyaki Meal" → _lookup_reference matched "chicken"
#   → returned chicken-breast macros (165/31/0/3.6) → scaled to 430g
#   → recorded 710 cal / 133g protein / 0g carbs / 15g fat.
#   Correct value from the label: 718 / 44.9 / 86.5 / 19.9.
#
# Rule: reference fallback is only allowed for an EXACT normalised match
# against this allow-list. Anything else → fail visibly with 422 and prompt
# the user to try a clearer photo or enter manually.
_SAFE_FALLBACK_FOODS = {
    # Fruits (single whole item)
    "apple", "banana", "orange", "pear", "peach", "plum", "kiwi", "mango",
    "grapes", "strawberries", "blueberries", "raspberries", "watermelon",
    "pineapple", "avocado",
    # Vegetables (plain, single item)
    "broccoli", "spinach", "kale", "carrot", "carrots", "tomato", "tomatoes",
    "cucumber", "lettuce", "capsicum", "bell pepper", "zucchini",
    "cauliflower", "sweet potato", "potato", "green beans",
    # Grains / starches (plain, cooked)
    "white rice", "brown rice", "rice", "oats", "oatmeal", "quinoa", "pasta",
    "bread", "wholemeal bread",
    # Proteins (plain, unseasoned)
    "chicken breast", "chicken thigh", "egg", "eggs", "salmon", "tuna",
    "sirloin steak", "beef mince", "extra lean beef mince", "lean beef mince",
    "ground beef",
    # Dairy (plain)
    "milk", "greek yogurt", "greek yogurt plain", "cottage cheese", "butter",
    "cheddar cheese",
    # Nuts / legumes (plain)
    "almonds", "peanut butter", "black beans", "chickpeas", "lentils",
    # Fats
    "olive oil",
}

def _is_safe_reference_fallback(food_name: str) -> bool:
    """Return True only when the food name is an unambiguous single-ingredient
    whole food that is safe to substitute a reference value for.

    Two hard rules (both must hold):
      1. Contains NO composite / branded / prepared indicator word.
      2. Its normalised form is an EXACT match to `_SAFE_FALLBACK_FOODS`
         (no substring / fuzzy match — that's exactly how the Youfoodz-vs-
         chicken-breast confusion happened).
    """
    if not food_name or is_composite_name(food_name):
        return False
    n = _norm_food_name(food_name)
    if not n:
        return False
    return n in _SAFE_FALLBACK_FOODS

# Drinks whose calories come mostly from alcohol (7 kcal/g, not in P/C/F):
# their calories can't be checked against protein/carbs/fat.
_ALCOHOL_RE = re.compile(
    r"\b(beer|lager|ale|stout|ipa|pilsner|cider|wine|champagne|prosecco|sparkling wine|vodka|gin|rum|"
    r"whisk(?:e)?y|bourbon|scotch|tequila|brandy|cognac|liqueur|sake|soju|cocktail|margarita|mojito|"
    r"martini|negroni|daiquiri|spritz|aperol|sangria|seltzer|alcoholic|rtd|bacardi|smirnoff|jack daniel)s?\b",
    re.I)


def _is_alcoholic(name: str) -> bool:
    n = name or ""
    return bool(_ALCOHOL_RE.search(n)) and not re.search(r"\b(vinegar|non[- ]?alcoholic|alcohol[- ]free|0\.0%?|ginger)\b", n, re.I)


def sanitize_food_entry(entry: dict, food_name: str = None, portion_g: float = None,
                        reconcile: bool = True) -> tuple[dict, list[str]]:
    """Guardrail applied to every food entry before it's saved / returned.

    Applies Fix 1 (deterministic calorie reconciliation), Fix 2 (physical
    plausibility), and Fix 4 (reference cross-check). Mutates the input dict
    in place with corrections and returns (sanitised_entry, warnings).
    """
    warnings: list[str] = []
    if not isinstance(entry, dict):
        return entry, warnings

    def _f(key, default=0.0):
        try:
            return float(entry.get(key, default) or 0)
        except (TypeError, ValueError):
            return float(default)

    # Some upstream endpoints label protein/carbs/fats as *_g — normalise here
    # (non-destructively) so we can operate on a single canonical shape.
    protein = _f("protein", _f("protein_g"))
    carbs   = _f("carbs",   _f("carbs_g"))
    fats    = _f("fats",    _f("fat_g"))
    stated  = _f("calories")
    fname   = food_name or entry.get("food_name") or entry.get("name") or ""

    # ── Fix 1: deterministic calorie reconciliation ─────────────────────
    # Label-transcribed energies (energy_source=="label") are treated as
    # ground truth — printed labels use food-specific Atwater factors and
    # exclude fibre from carbs, so a legitimate label energy can differ
    # from the 4/4/9 sum by 10–20% (e.g. yogurt prints 62 kcal/100g while
    # P*4+C*4+F*9 = 53). We keep a wide 30% "gross-error" safety net so
    # a truly misread label (e.g. a bogus 500 kcal on a 20g/1P/1F snack)
    # still gets corrected — but the everyday Atwater deltas the whole
    # Fix 8 structured-portion path was built to honour are preserved.
    is_label = str(entry.get("energy_source", "")).lower() == "label"
    _cal_tol = 0.30 if is_label else 0.10
    fiber = _f("fiber", _f("fiber_g"))
    # Fibre counts ~2 kcal/g, not 4 (high-fibre bars, vegetables)
    if 0 < fiber <= carbs:
        derived = protein * 4 + (carbs - fiber) * 4 + fiber * 2 + fats * 9
    else:
        derived = protein * 4 + carbs * 4 + fats * 9
    if _is_alcoholic(fname):
        reconcile = False   # alcohol calories aren't in protein/carbs/fat
    if derived > 0 and reconcile:
        gap = abs(stated - derived) / max(stated, 1.0)
        if gap > _cal_tol:
            corrected = round(derived)
            warnings.append(
                f"reconcile_calories food='{fname}' stated={stated:.0f} derived={derived:.0f} → set {corrected}"
            )
            entry["calories"] = int(corrected)
            stated = float(corrected)

    # ── Fix 2: physical plausibility ────────────────────────────────────
    total_macros_g = protein + carbs + fats
    if portion_g and portion_g > 0:
        if total_macros_g > portion_g * 1.02:  # 2% tolerance for rounding
            warnings.append(
                f"plausibility_mass food='{fname}' macros={total_macros_g:.1f}g > portion={portion_g:.0f}g"
            )
        if stated > 0:
            density = stated / portion_g
            if density < 0.1 or density > 9.0:
                warnings.append(
                    f"plausibility_density food='{fname}' {density:.2f} cal/g outside [0.1, 9.0]"
                )
        # Single-macro ceiling only meaningful when portion is known
        for macro_name, macro_val in (("protein", protein), ("carbs", carbs), ("fats", fats)):
            per_100g = (macro_val / portion_g) * 100 if portion_g else 0
            if per_100g > 90:
                warnings.append(
                    f"plausibility_macro_ceiling food='{fname}' {macro_name}={per_100g:.1f}g/100g > 90"
                )

    # ── Fix 4: reference cross-check (per-100g divergence) ──────────────
    ref = _lookup_reference(fname)
    if ref and portion_g and portion_g > 0:
        ref_cal, ref_p, ref_c, ref_f = ref
        p100 = protein / portion_g * 100
        c100 = carbs   / portion_g * 100
        f100 = fats    / portion_g * 100
        cal100 = stated / portion_g * 100
        def _div(a, b): return abs(a - b) / max(b, 1.0)
        divergences = {
            "calories": _div(cal100, ref_cal),
            "protein":  _div(p100,   ref_p),
            "carbs":    _div(c100,   ref_c),
            "fats":     _div(f100,   ref_f),
        }
        big = {k: v for k, v in divergences.items() if v > 0.30}
        if big:
            warnings.append(
                f"reference_divergence food='{fname}' per100g cal={cal100:.0f}/{ref_cal} "
                f"p={p100:.1f}/{ref_p} c={c100:.1f}/{ref_c} f={f100:.1f}/{ref_f} "
                f"(off: {','.join(f'{k}={v:.0%}' for k, v in big.items())})"
            )

    if warnings:
        for w in warnings:
            logger.warning(f"[nutrition-guard] {w}")

    return entry, warnings

def derive_per_100g(entry: dict, serving_g: float | None) -> dict | None:
    """Derive a per-100g reference from a per-serving entry + known serving mass.

    Used when the AI returned per-serving values but no explicit per_100g block.
    Only produces a usable result when the serving mass is a positive number of
    grams — otherwise returns None so the caller can skip the deterministic
    scaling step.
    """
    if not isinstance(entry, dict):
        return None
    try:
        s = float(serving_g or 0)
    except (TypeError, ValueError):
        return None
    if s <= 0:
        return None
    def _fx(key):
        for k in (key, f"{key}_g"):
            if k in entry:
                try:
                    return float(entry[k] or 0)
                except (TypeError, ValueError):
                    return 0.0
        return 0.0
    cal = _fx("calories")
    p, c, f = _fx("protein"), _fx("carbs"), _fx("fats")
    if cal <= 0 and p <= 0 and c <= 0 and f <= 0:
        return None
    scale = 100.0 / s
    return {
        "calories": round(cal * scale, 2),
        "protein":  round(p   * scale, 2),
        "carbs":    round(c   * scale, 2),
        "fats":     round(f   * scale, 2),
    }

def detect_hallucination(per_100g: dict, food_name: str) -> tuple[bool, dict | None, float]:
    """Compare a candidate per_100g block against the reference table.

    Returns (is_hallucination, reference_tuple_or_None, max_divergence_ratio).
    A per-100g value that is more than 100% off a matched reference on ANY
    macro is treated as a hallucination (product variation stays within ~90%
    even across sub-types like whole vs skim milk or 95/5 vs 80/20 mince;
    only truly invented values (e.g. 31g P / 100g yogurt) exceed 100%).

    Note: `_lookup_reference` now returns None for composite / branded product
    names, so this check only ever fires against single-ingredient references
    where the comparison is semantically meaningful.
    """
    ref = _lookup_reference(food_name)
    if not ref or not isinstance(per_100g, dict):
        return False, ref, 0.0
    ref_cal, ref_p, ref_c, ref_f = ref
    try:
        v_cal = float(per_100g.get("calories") or 0)
        v_p   = float(per_100g.get("protein")  or 0)
        v_c   = float(per_100g.get("carbs")    or 0)
        v_f   = float(per_100g.get("fats")     or 0)
    except (TypeError, ValueError):
        return False, ref, 0.0
    def _rel(a, b): return abs(a - b) / max(abs(b), 1.0)
    divs = [_rel(v_cal, ref_cal), _rel(v_p, ref_p), _rel(v_c, ref_c), _rel(v_f, ref_f)]
    max_div = max(divs)
    return (max_div > 1.0), ref, max_div

def _round_portion(g: float):
    g = round(float(g), 1)
    return int(g) if g.is_integer() else g


async def _log_plated_meal(request, food_data: dict, raw_items: list, specs: list, qty: int):
    """Plated meal with no label: every part is calculated from its grams with
    the same nutrition engine the meal plans use. Typed amounts ('4 eggs',
    '3 pieces of sourdough') replace the AI's estimate for that item."""
    items, problems = build_plate(raw_items, specs, qty)
    if problems:
        raise HTTPException(status_code=422, detail={
            "error": "portion_unresolvable", "message": " ".join(problems),
            "food_name_guess": food_data.get("food_name"),
        })
    if not items:
        raise HTTPException(status_code=422, detail={
            "error": "no_food_detected",
            "message": "We couldn't recognise any food in that photo. Try a closer, well-lit shot of the plate "
                       "or the nutrition panel — or log it manually.",
        })
    tot = plate_totals(items)
    logger.info(f"[snap-plate] '{food_data.get('food_name')}' specs={specs} → "
                f"{[(i['display'], i['grams'], i['calories']) for i in items]} total={tot}")
    food_entry = FoodEntry(
        user_id=request.user_id,
        food_name=food_data.get("food_name") or "Meal",
        serving_size=f"{tot['grams']}g",
        calories=tot["calories"], protein=tot["protein"], carbs=tot["carbs"], fats=tot["fats"],
        meal_type=request.meal_type,
        logged_date=request.logged_date or datetime.now().strftime("%Y-%m-%d"),
        image_base64=request.image_base64[:100] + "...",
    )
    if not request.preview:
        await db.food_logs.insert_one(food_entry.model_dump())
    result = food_entry.model_dump()
    result.update({
        "items": items, "summary": None, "label_per_100g": None, "portion_g_applied": tot["grams"],
        "per_100g_source": "items", "hallucination_fallback": False, "portion_source": "plate",
        "portion_debug": {"specs": specs, "ai_items": raw_items},
    })
    return result


@api_router.post("/food/analyze")
async def analyze_food_image(request: FoodImageAnalyzeRequest):
    """Analyze food image using OpenAI Vision to identify food and estimate nutrition"""
    try:
        # Premium gate — snapping food is a paid action.
        access = await check_subscription_access(request.user_id)
        if not access.get("has_access"):
            raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Nutrition Tracking",
                                                         "message": "Nutrition tracking is a premium feature. Subscribe to unlock food search, logging, and photo analysis."})
        # Validate base64 image
        if not request.image_base64 or len(request.image_base64) < 100:
            raise HTTPException(status_code=400, detail="Invalid image data")
        # Fair-use cap: photo analysis is the app's most expensive AI call. Far
        # above normal use (3-5 meals a day, plus re-analyses); stops one
        # account costing more than its subscription.
        used = await db.snap_usage.count_documents({
            "user_id": request.user_id, "created_at": {"$gte": datetime.utcnow() - timedelta(hours=24)}})
        if used >= SNAP_DAILY_LIMIT:
            raise HTTPException(status_code=429, detail={
                "error": "daily_limit",
                "message": f"You've used today's {SNAP_DAILY_LIMIT} photo analyses. It resets within 24 hours "
                           "\u2014 you can still search for food or add it manually."})
        await db.snap_usage.insert_one({"user_id": request.user_id, "created_at": datetime.utcnow()})
        
        # The description goes to the AI as a hint about WHAT is in the photo
        # ("no dressing", "grilled not fried", "4 eggs and 3 slices sourdough").
        # Amounts are worked out in code from the same text (parse_portions).
        description = (request.additional_context or request.portion_text or "").strip()
        user_prompt = (
            "Analyze this food image and return nutritional information as JSON. "
            "If a nutrition label is visible, read its per-100g values; if not, list each part of "
            "the meal with its estimated grams. DO NOT compute the user's portion — the app does that."
        )
        if description:
            user_prompt += (
                f"\n\nThe user's description: \"{description}\". Use it to adjust what you identify "
                "(e.g. 'no dressing' → leave the dressing out, 'grilled not fried' → no frying oil, "
                "'extra cheese' → more cheese). If it names foods (e.g. '4 eggs and 3 slices sourdough'), "
                "make sure every named food is one of the items."
            )
        food_list = ", ".join(prompt_food_names())

        vision_prompt = """You are an expert nutritionist analysing a food photo. Your only job is to identify the food and return accurate PER-100G nutrition values plus the label's own portion reference points — the app applies portion scaling itself.

═══════════════════════════════════════════════════════════════════════
WHEN A NUTRITION LABEL / INFO PANEL IS VISIBLE (the printed panel overrides general knowledge):

A. USE THE PER-100G COLUMN VERBATIM. Return exactly what the label prints in that column. Never blend the per-serving column into it.
B. If the label shows ONLY a per-serving column (no per-100g), read the per-serving values AND the serving mass in grams — the app derives per-100g automatically.
C. Row mapping is exact:
   • protein  ← ONLY the "Protein" row
   • carbs    ← ONLY the "Carbohydrate" / "Total carbohydrate" row (NEVER "Saturated", "Sugars", "Fibre", "Sodium", or any fat row)
   • fats     ← ONLY the "Fat, total" row (never "Saturated" or "Trans" alone)
   • "<1.0g"  ← record as 1.0 or lower, never blank
D. ENERGY IS TRANSCRIBED, NEVER DERIVED. Copy the printed kJ or Cal value (convert kJ ÷ 4.184 if needed) and set `energy_source: "label"`. Do NOT compute calories from P*4 + C*4 + F*9 when a label energy row exists — AU/EU labels use food-specific Atwater factors and exclude fibre from carbs.
E. If a per-100g energy row is illegible, set `energy_source: "derived"`.

F. PORTION REFERENCE POINTS — you MUST also return these three fields so the app can convert any portion the user states into grams:
   • `serving_size_g` — the numeric grams of ONE serving as printed on the label (e.g. label says "Serving size: 104g" → 104; label says "Serving size: 40g (2 biscuits)" → 40).
   • `units_per_serving` — how many countable items make up one serving, as stated on the label (e.g. "Edible Portion of 2 Eggs" → 2; "2 biscuits per serving" → 2; "1 slice" → 1). If the label does NOT state a countable item, return null.
   • `unit_name` — the singular noun for one item (e.g. "egg", "biscuit", "slice", "piece", "bar", "cookie"). If not applicable, return null.
   • `servings_per_package` — "Servings per package" as printed (e.g. 4), else null.
   • `package_size_g` — the pack's net weight/volume in grams or ml as printed (e.g. "Net 500g" → 500; "12 eggs, 700g" → 700), else null.
   • If the label prints no serving size and the pack is a single serve, set `serving_size_g` to the pack's net weight.
   • DO NOT COMPUTE the total portion. Never multiply. Just report what the label prints.
   • Set `label_visible: true`.

═══════════════════════════════════════════════════════════════════════
WHEN NO LABEL IS VISIBLE (plated meal, restaurant plate, home cooking, produce, etc.):

1. Set `label_visible: false`.
2. List EVERY part of the meal in `items` as {"food": "<name>", "grams": <estimated grams>} — e.g. eggs, toast, the frying oil or butter, sauces, dressings, cheese. Never blend the plate into one food.
3. `food` must be the closest name from this FOOD LIST: """ + food_list + """
   Only if nothing on the list fits, use your own name and add "per_100g": {"calories", "protein", "carbs", "fats"}.
4. Estimate grams from what you see (a large egg ≈ 50g, a slice of sourdough ≈ 30g, a tablespoon of oil ≈ 14g). Count whole eggs and slices.
5. Set `food_name` to a short name for the whole meal, `energy_source: "derived"`, and leave `per_100g` and the top-level calories/protein/carbs/fats null — the app calculates them from the items.

═══════════════════════════════════════════════════════════════════════
QUALITY GATES — do this before responding:
• The per-100g values you return must be plausible: no macro > 100g/100g (impossible); calories/gram between 0.1 and 9.0.
• If the label is blurry or partially obscured such that you cannot read the per-100g or per-serving column confidently → set `confidence: "low"` and DO NOT INVENT VALUES. It is better to fail visibly than to guess plausibly.
• If confident you have read the values accurately → set `confidence: "high"`.
• Return the arithmetic in `reasoning` for auditability: "label per-100g: 143cal/12.2P/1.3C/9.9F; per-serving: 104g (2 eggs)".

═══════════════════════════════════════════════════════════════════════
Respond with ONLY valid JSON, no other text. Exact schema:
{
  "food_name": "Free Range Eggs",
  "serving_size": "104g (2 eggs)",
  "serving_size_g": 104,
  "units_per_serving": 2,
  "unit_name": "egg",
  "per_100g": {"calories": 143, "protein": 12.2, "carbs": 1.3, "fats": 9.9},
  "calories": 149, "protein": 12.7, "carbs": 1.4, "fats": 10.3,
  "fiber": 0, "sugar": 0.4, "sodium": 140,
  "energy_source": "label",
  "servings_per_package": 6,
  "package_size_g": 624,
  "label_visible": true,
  "items": null,
  "confidence": "high",
  "reasoning": "label per-100g col: 143cal/12.2P/1.3C/9.9F; per-serving 104g = 2 eggs (52g/egg)."
}

Plated meal (no label) example:
{"food_name": "Fried Eggs on Sourdough", "label_visible": false, "items": [{"food": "eggs", "grams": 232}, {"food": "sourdough bread", "grams": 90}, {"food": "olive oil", "grams": 7}], "per_100g": null, "calories": null, "protein": null, "carbs": null, "fats": null, "energy_source": "derived", "confidence": "high", "reasoning": "4 fried eggs, 3 slices sourdough, a little oil"}

For labels, the `calories/protein/carbs/fats` top-level fields describe ONE label serving as a sanity anchor. The app uses `per_100g` × resolved_portion_g / 100 as the source of truth for what gets logged. NEVER multiply anything yourself."""
        content = await call_claude_sonnet(
            system_message=vision_prompt,
            user_message=user_prompt,
            temperature=0.2,
            max_tokens=1000,
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

        qty = request.quantity if request.quantity > 0 else 1
        legacy_grams = False
        if request.portion_amount and request.portion_amount > 0:
            unit = (request.portion_unit or "grams").strip().lower()
            if unit == "count":
                unit = food_data.get("unit_name") or "unit"
            specs = parse_portions(f"{request.portion_amount:g} {unit}")
        elif (request.portion_text or "").strip():
            specs = parse_portions(request.portion_text)
        elif description:
            specs = parse_portions(description)
        elif request.portion_g and request.portion_g > 0:
            specs, legacy_grams = parse_portions(f"{request.portion_g:g}g"), True
        else:
            specs = []
        raw_items = food_data.get("items") if isinstance(food_data.get("items"), list) else []
        if raw_items and not food_data.get("label_visible"):
            return await _log_plated_meal(request, food_data, raw_items, specs, qty)

        # Low-confidence bail-out — only fail visibly when the model reports
        # low confidence AND its per-100g values are ALSO physically
        # implausible. If the model was cautious but the numbers themselves
        # pass Atwater/mass conservation, trust them (this stops the endpoint
        # 422'ing legible labels just because the AI hedged on confidence).
        if str(food_data.get("confidence", "high")).lower() == "low":
            _low_p100 = food_data.get("per_100g") if isinstance(food_data.get("per_100g"), dict) else None
            if not _low_p100:
                _low_p100 = derive_per_100g(food_data, grams_in_text(
                    food_data.get("serving_size", ""), food_data.get("food_name", "")))
            _low_ok, _low_reason = _is_physically_plausible_per_100g(_low_p100 or {})
            if not _low_ok:
                logger.warning(f"[nutrition-guard] low_confidence_scan+implausible reason={_low_reason} food_data={food_data}")
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "label_unreadable",
                        "message": "Couldn't read that label clearly. Try a closer, well-lit photo of the nutrition panel, or enter the food manually.",
                        "food_name_guess": food_data.get("food_name"),
                    },
                )
            logger.info(f"[nutrition-guard] low_confidence_but_plausible food='{food_data.get('food_name')}' — accepting")
        
        # ── Nutrition-accuracy guard: Fix 1 + 2 + 4 (internal-consistency retry) ──
        # Retry once if the AI's first reading is internally inconsistent
        # (Fix 1 Atwater) OR mass-conservation-violating (Fix 2). We do NOT
        # retry on reference-divergence-only warnings (Fix 4) because those
        # false-positive on legitimate composite dishes ("Chicken & Bacon
        # Macaroni" vs plain chicken breast reference has 15g carb delta and
        # trips this every time). A pointless retry costs ~4s of Claude
        # latency per scan — the user's #1 complaint is speed.
        try:
            portion_g_for_check = grams_in_text(food_data.get("serving_size", ""),
                                                        food_data.get("food_name", ""))
            _, first_warnings = sanitize_food_entry(dict(food_data), portion_g=portion_g_for_check)
            # Only truly-actionable warnings warrant a retry.
            _retry_worthy = [w for w in first_warnings
                             if not str(w).startswith("reference_divergence")]
            if _retry_worthy:
                import re as _re2
                complaint_lines = "\n".join(f"- {w}" for w in _retry_worthy)
                retry_raw = await call_claude_sonnet(
                    system_message=vision_prompt,
                    user_message=(
                        f"{user_prompt}\n\nIMPORTANT: your previous reading failed these checks:\n"
                        f"{complaint_lines}\n\nRe-read the image carefully. If a nutrition label is "
                        "visible, transcribe its printed per-100g values exactly. Then verify "
                        "calories ≈ P*4 + C*4 + F*9 and that macro mass does not exceed portion mass."
                    ),
                    temperature=0.0,
                    max_tokens=1000,
                    image_base64=request.image_base64
                )
                rc = (retry_raw or "").strip()
                rc = _re2.sub(r"```(?:json)?\n?", "", rc).strip("`").strip()
                m = _re2.search(r"\{[\s\S]+\}", rc)
                if m:
                    retry_data = json.loads(m.group(0))
                    retry_portion_g = grams_in_text(retry_data.get("serving_size", ""),
                                                             retry_data.get("food_name", ""))
                    _, retry_warnings = sanitize_food_entry(dict(retry_data),
                                                            portion_g=retry_portion_g)
                    if len(retry_warnings) < len(first_warnings):
                        food_data = retry_data
                        logger.info(f"Nutrition guard retry accepted: {len(first_warnings)} -> {len(retry_warnings)} warnings")
        except Exception as _ve:
            logger.warning(f"Food analysis consistency check skipped: {_ve}")

        food_name_raw = food_data.get("food_name", "Unknown Food")

        # The label's own reference points — the code converts the user's
        # amount with them; the model NEVER multiplies.
        def _num(v):
            try:
                return float(v or 0)
            except (TypeError, ValueError):
                return 0.0
        _label_serving_g = _num(food_data.get("serving_size_g")) or grams_in_text(
            food_data.get("serving_size", ""), food_name_raw)
        _label_units_per_serving = _num(food_data.get("units_per_serving")) or None
        _label_unit_name = food_data.get("unit_name") or None
        _pack_g = _num(food_data.get("package_size_g"))
        if _pack_g <= 0 and _num(food_data.get("servings_per_package")) > 0 and _label_serving_g > 0:
            _pack_g = _num(food_data.get("servings_per_package")) * _label_serving_g

        # Extract or derive per_100g
        _per_100g_model = food_data.get("per_100g") if isinstance(food_data.get("per_100g"), dict) else None
        _model_serving_g = grams_in_text(food_data.get("serving_size", ""),
                                                  food_data.get("food_name", ""))
        if _label_serving_g and _label_serving_g > 0:
            _model_serving_g = _label_serving_g  # explicit numeric wins over parsed string
        _per_100g = _per_100g_model
        _per_100g_source = "label" if _per_100g_model else None
        if not _per_100g:
            derived = derive_per_100g(food_data, _model_serving_g)
            if derived:
                _per_100g = derived
                _per_100g_source = "derived_from_serving"

        # Hallucination check on per_100g against reference table.
        #
        # DESIGN: A correctly-read label of a COMPOSITE dish (e.g. "Chicken &
        # Bacon Macaroni" 149cal/13P/14.9C/3.9F per 100g) will ALWAYS diverge
        # wildly from a single-ingredient reference — pasta dish vs plain
        # chicken breast has 14.9x more carbs → 1490% divergence and a false
        # hallucination flag. We therefore ONLY run the reference check when
        # the per-100g values are ALREADY physically implausible (impossible
        # macros, calorie/Atwater mismatch, macro mass > 100g/100g). Physically
        # valid label reads are TRUSTED without reference cross-check.
        hallucinated = False
        ref_tuple = None
        physically_ok, plaus_reason = _is_physically_plausible_per_100g(_per_100g) if _per_100g else (False, "no_per_100g")

        if _per_100g and not physically_ok:
            logger.warning(
                f"[nutrition-guard] implausible_read food='{food_name_raw}' reason={plaus_reason} "
                f"per_100g={_per_100g}"
            )
            hallucinated, ref_tuple, max_div = detect_hallucination(_per_100g, food_name_raw)
            if hallucinated and ref_tuple:
                logger.warning(
                    f"[nutrition-guard] hallucination_detected food='{food_name_raw}' "
                    f"max_divergence={max_div:.0%} model_per_100g={_per_100g} "
                    f"reference={{cal:{ref_tuple[0]},p:{ref_tuple[1]},c:{ref_tuple[2]},f:{ref_tuple[3]}}}"
                )
                try:
                    import re as _re3
                    ref_hint = (
                        f"USDA reference for {food_name_raw!r} (per-100g): "
                        f"{ref_tuple[0]}cal / {ref_tuple[1]}P / {ref_tuple[2]}C / {ref_tuple[3]}F. "
                        "Your previous per-100g values were more than 100% off this reference on at "
                        "least one macro — this is a misread, not a product variation. Re-read the "
                        "label carefully."
                    )
                    retry_h = await call_claude_sonnet(
                        system_message=vision_prompt,
                        user_message=f"{user_prompt}\n\n{ref_hint}",
                        temperature=0.0,
                        max_tokens=1000,
                        image_base64=request.image_base64
                    )
                    rc2 = (retry_h or "").strip()
                    rc2 = _re3.sub(r"```(?:json)?\n?", "", rc2).strip("`").strip()
                    m2 = _re3.search(r"\{[\s\S]+\}", rc2)
                    if m2:
                        rd = json.loads(m2.group(0))
                        rd_p100 = rd.get("per_100g") if isinstance(rd.get("per_100g"), dict) else None
                        if not rd_p100:
                            rd_p100 = derive_per_100g(rd, grams_in_text(
                                rd.get("serving_size", ""), rd.get("food_name", "")))
                        # Retry passes if it becomes physically plausible OR the
                        # divergence relaxes below hallucination threshold.
                        rd_ok, _ = _is_physically_plausible_per_100g(rd_p100 or {})
                        h2, _, div2 = detect_hallucination(rd_p100 or {}, food_name_raw)
                        if rd_p100 and (rd_ok or not h2):
                            food_data = rd
                            _per_100g = rd_p100
                            _per_100g_source = "retry_label" if rd.get("per_100g") else "retry_derived"
                            hallucinated = False
                            logger.info(f"[nutrition-guard] hallucination_retry_accepted food='{food_name_raw}' new_max_div={div2:.0%} plausible={rd_ok}")
                        else:
                            logger.error(f"[nutrition-guard] hallucination_persists food='{food_name_raw}' — falling back to reference")
                except Exception as _re:
                    logger.error(f"Hallucination retry failed: {_re}")

            # If still hallucinating after the retry, decide the safest exit:
            #   • single-ingredient whole food (apple, chicken breast, milk, …)
            #     → we can safely substitute the reference values
            #   • branded / composite / prepared product → fail visibly.
            if hallucinated and ref_tuple:
                if _is_safe_reference_fallback(food_name_raw):
                    _per_100g = {
                        "calories": ref_tuple[0], "protein": ref_tuple[1],
                        "carbs":    ref_tuple[2], "fats":    ref_tuple[3],
                    }
                    _per_100g_source = "reference_fallback"
                    logger.warning(
                        f"[nutrition-guard] hallucination_fallback_to_reference "
                        f"food='{food_name_raw}' per_100g={_per_100g}"
                    )
                else:
                    logger.warning(
                        f"[nutrition-guard] composite_reject food='{food_name_raw}' "
                        "hallucination detected but food is branded/composite — "
                        "not in safe-fallback allowlist. Failing visibly."
                    )
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": "label_unreadable",
                            "message": (
                                "Couldn't read that label accurately. Try a "
                                "closer, well-lit photo of the nutrition panel, "
                                "or enter it manually."
                            ),
                            "food_name_guess": food_name_raw,
                        },
                    )
        elif _per_100g:
            # Physically plausible read — log a soft note if the reference is
            # far off (useful for debugging drift) but DO NOT block or replace.
            try:
                _, _ref, _div = detect_hallucination(_per_100g, food_name_raw)
                if _ref and _div > 1.0:
                    logger.info(
                        f"[nutrition-guard] plausible_read_ignoring_reference food='{food_name_raw}' "
                        f"div={_div:.0%} per_100g={_per_100g} — trusting label over reference for composite/branded dish"
                    )
            except Exception:
                pass

        # A per-100g block that is still impossible (or all zeros) is never used
        # to scale: use the label's per-serving column instead, else nothing.
        if _per_100g and _per_100g_source != "reference_fallback" and (
                not _is_physically_plausible_per_100g(_per_100g)[0]
                or not any(_num(_per_100g.get(k)) > 0 for k in ("calories", "protein", "carbs", "fats"))):
            _derived = derive_per_100g(food_data, _model_serving_g)
            _usable = bool(_derived) and _is_physically_plausible_per_100g(_derived)[0]
            logger.warning(f"[nutrition-guard] unusable_per_100g food='{food_name_raw}' per_100g={_per_100g} "
                           f"→ {'per-serving column ' + str(_derived) if _usable else 'not used'}")
            _per_100g, _per_100g_source = (_derived, "derived_from_serving") if _usable else (None, None)

        spec = specs[0] if specs else None
        product_key = None if is_composite_name(food_name_raw) else resolve_food(food_name_raw)
        if spec:
            user_portion_g = portion_grams(
                spec, product_key, serving_g=_label_serving_g or None, unit_name=_label_unit_name,
                units_per_serving=_label_units_per_serving, pack_g=_pack_g or None, label=True)
            if user_portion_g is None:
                logger.warning(f"[portion-resolve] unresolved food='{food_name_raw}' spec={spec}")
                raise HTTPException(status_code=422, detail={
                    "error": "portion_unresolvable",
                    "message": (f"Couldn't work out \"{spec['text']}\" for {food_name_raw}. Try grams "
                                "(\"200g\"), servings (\"1 serving\", \"half\") or \"the whole pack\"."),
                    "food_name_guess": food_name_raw,
                })
            _portion_label = f"{_round_portion(user_portion_g)}g" if spec["unit"] == "g" else \
                f"{spec['text']} = {_round_portion(user_portion_g)}g"
        else:
            # Nothing typed → one label serving (or the whole single-serve pack).
            user_portion_g = _label_serving_g or _pack_g or None
            _portion_label = (f"1 serving = {_round_portion(user_portion_g)}g" if _label_serving_g else
                              f"whole pack = {_round_portion(user_portion_g)}g" if _pack_g else None)
        if not spec:
            _portion_source = "serving_default"
        elif legacy_grams:
            _portion_source = "legacy"
        else:
            _portion_source = {"g": "grams", "ml": "grams", "serving": "servings", "pack": "pack"}.get(spec["unit"]) or (
                "count_label" if portion_grams(spec, None, serving_g=_label_serving_g or None, unit_name=_label_unit_name,
                                               units_per_serving=_label_units_per_serving, label=True) is not None
                else "count_fallback" if spec["unit"] == "count" else spec["unit"])
        _portion_debug = {"spec": spec, "serving_size_g": _label_serving_g or None, "pack_g": _pack_g or None,
                          "units_per_serving": _label_units_per_serving, "unit_name": _label_unit_name}
        logger.info(f"[portion-resolve] source={_portion_source} → portion_g={user_portion_g} debug={_portion_debug}")

        _summary = None
        if user_portion_g and _per_100g:
            r = user_portion_g / 100.0
            _scaled = {
                "food_name": food_name_raw,
                "serving_size": f"{int(user_portion_g)}g" if qty == 1 else f"{qty}× {int(user_portion_g)}g",
                "calories": int(round(_per_100g["calories"] * r * qty)),
                "protein": round(_per_100g["protein"] * r * qty, 2),
                "carbs":   round(_per_100g["carbs"] * r * qty, 2),
                "fats":    round(_per_100g["fats"] * r * qty, 2),
                "energy_source": "label" if _per_100g_source in ("label", "retry_label") else "derived",
            }
            _portion_applied = user_portion_g * qty
            _summary = (f"{'Label' if _per_100g_source in ('label', 'retry_label', 'derived_from_serving') else 'Estimate'}: "
                        f"{round(_per_100g['calories'])} cal/100g · your portion: "
                        f"{(str(qty) + ' × ') if qty > 1 else ''}{_portion_label}")
        elif spec or food_data.get("calories") is None:
            # An amount was typed but there's no readable label to scale, or
            # nothing was recognised at all — fail visibly, never invent.
            raise HTTPException(status_code=422, detail={
                "error": "label_unreadable" if food_data.get("calories") is not None else "no_food_detected",
                "message": ("Couldn't read that label clearly. Try a closer, well-lit photo of the nutrition "
                            "panel, or enter the food manually." if food_data.get("calories") is not None else
                            "We couldn't recognise any food in that photo. Try a closer, well-lit shot of the "
                            "plate or the nutrition panel — or log it manually."),
                "food_name_guess": food_name_raw,
            })
        else:
            # No serving size on the label and nothing typed: the model's own
            # per-serving reading is the best we have.
            _scaled = {
                "food_name": food_name_raw,
                "serving_size": food_data.get("serving_size", "1 serving"),
                "calories": int(_num(food_data.get("calories"))) * qty,
                "protein": _num(food_data.get("protein")) * qty,
                "carbs":   _num(food_data.get("carbs")) * qty,
                "fats":    _num(food_data.get("fats")) * qty,
                "energy_source": str(food_data.get("energy_source") or "derived").lower(),
            }
            _portion_applied = None

        # Final sanitize — last-line safety net (never hurts; usually a no-op
        # after the deterministic path).
        sanitize_food_entry(_scaled, portion_g=_portion_applied or None)

        food_entry = FoodEntry(
            user_id=request.user_id,
            food_name=_scaled["food_name"],
            serving_size=_scaled["serving_size"],
            calories=int(_scaled["calories"]),
            protein=float(_scaled["protein"]),
            carbs=float(_scaled["carbs"]),
            fats=float(_scaled["fats"]),
            fiber=float(food_data.get("fiber", 0)) * qty,
            sugar=float(food_data.get("sugar", 0)) * qty,
            sodium=float(food_data.get("sodium", 0)) * qty,
            meal_type=request.meal_type,
            logged_date=request.logged_date or datetime.now().strftime("%Y-%m-%d"),
            image_base64=request.image_base64[:100] + "..."  # Store truncated for reference
        )

        if not request.preview:
            await db.food_logs.insert_one(food_entry.model_dump())
        # Attach preview metadata so the frontend can show the user exactly
        # what was read (label per-100g values, portion applied, source flag).
        # Not persisted; only visible in the response.
        result = food_entry.model_dump()
        result["label_per_100g"] = _per_100g
        result["portion_g_applied"] = _portion_applied
        result["per_100g_source"] = _per_100g_source or "none"
        result["hallucination_fallback"] = hallucinated  # true only when we fell back to reference
        # Fix 9 — expose the label's portion reference points AND how the
        # user's stated portion was resolved. Lets the UI show "4 eggs → 208g
        # (label: 52g/egg)" instead of a mystery number.
        result["label_serving_size_g"] = _label_serving_g or None
        result["label_units_per_serving"] = _label_units_per_serving
        result["label_unit_name"] = _label_unit_name
        result["label_package_g"] = _pack_g or None
        result["portion_source"] = _portion_source
        result["portion_debug"] = _portion_debug
        result["summary"] = _summary
        result["items"] = None
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Food analysis error: {e}")
        if "invalid" in str(e).lower() or "image" in str(e).lower():
            raise HTTPException(status_code=400, detail="Invalid image format. Please use a valid JPEG or PNG image.")
        raise HTTPException(status_code=500, detail=f"Failed to analyze food: {str(e)}")

async def usda_generic_per_100g(food: str):
    """Per-100g macros for a plain food from USDA's generic tables (Foundation /
    SR Legacy — not branded products), or None. Only a result whose name contains
    every word the user typed is used; otherwise nothing is guessed."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{USDA_API_BASE}/foods/search",
                params={"api_key": USDA_API_KEY, "query": food, "pageSize": 10,
                        "dataType": ["Foundation", "SR Legacy"]},
                timeout=8.0,
            )
        if response.status_code != 200:
            logger.warning(f"USDA fallback error {response.status_code} for '{food}'")
            return None
        foods = response.json().get("foods", [])
    except Exception as e:
        logger.warning(f"USDA fallback exception for '{food}': {e}")
        return None
    for f in foods:
        desc = f.get("description", "")
        if not food_matches(food, name=desc):
            continue
        n = {}
        for x in f.get("foodNutrients", []):
            name, unit = x.get("nutrientName", ""), str(x.get("unitName", "")).upper()
            if name.startswith("Energy") and unit != "KCAL":
                continue   # kJ entries
            n.setdefault("Energy" if name.startswith("Energy") else name, float(x.get("value") or 0))
        p, c, fat = n.get("Protein", 0), n.get("Carbohydrate, by difference", 0), n.get("Total lipid (fat)", 0)
        cal = n.get("Energy") or round(p * 4 + c * 4 + fat * 9)
        if cal <= 0 and p + c + fat <= 0:
            continue
        return {"calories": round(cal), "protein": round(p, 1), "carbs": round(c, 1),
                "fats": round(fat, 1), "usda_name": desc}
    return None


@api_router.post("/food/item")
async def snap_food_item(request: SnapItemRequest):
    """Edit one item of a snapped plate ('150g', '3 eggs') or add one by name
    ('30g cheddar', '1 tbsp olive oil'). Same food database and calculator as
    meal plans. A food that isn't in the database is looked up in USDA's generic
    tables (grams required); an unknown food is reported, never guessed."""
    item, error = snap_item_from_text(request.text, request.key, request.name, request.per_100g)
    if error and not request.key and not request.per_100g and "food database" in error:
        specs = parse_portions(request.text)
        spec = specs[0] if specs else None
        food = (spec["food"] if spec else request.text).strip()
        usda = await usda_generic_per_100g(food) if food else None
        if usda:
            if not spec or spec["unit"] not in ("g", "ml"):
                error = f"Found '{food}' — add the amount in grams, e.g. '50g {food}'."
            else:
                item = snap_item(food, spec["amount"], per_100g=usda)
                if item:
                    item["source"] = "usda"
                    item["usda_name"] = usda["usda_name"]
                    return item
    if error:
        raise HTTPException(status_code=422, detail={"error": "item_unresolvable", "message": error})
    return item


@api_router.post("/food/log", response_model=FoodEntry)
async def log_food(request: FoodLogRequest):
    """Manually log food entry"""
    # Premium gate — logging food is a paid action.
    access = await check_subscription_access(request.user_id)
    if not access.get("has_access"):
        raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Nutrition Tracking",
                                                     "message": "Nutrition tracking is a premium feature. Subscribe to unlock food search, logging, and photo analysis."})
    # Nutrition-accuracy guard — reconcile calories with macros (Fix 1) and
    # log warnings if the entry is implausible (Fix 2) or diverges from a
    # known reference (Fix 4). Manual entries can't be retried, so we
    # deterministically correct the calorie total in place.
    payload = request.model_dump()
    source = (payload.pop("source", None) or "").lower()
    portion_g = grams_in_text(payload.get("serving_size", ""), payload.get("food_name", ""))
    sanitize_food_entry(payload, portion_g=portion_g, reconcile=source in ("", "ai"))
    food_entry = FoodEntry(**payload)
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
async def search_foods(query: str, user_id: str, country: str = ""):
    """Search food database - combines local database with API results for best coverage.
    Requires an active subscription (`user_id` gates the paid nutrition feature)."""
    access = await check_subscription_access(user_id)
    if not access.get("has_access"):
        raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Nutrition Tracking",
                                                     "message": "Nutrition tracking is a premium feature. Subscribe to unlock food search, logging, and photo analysis."})
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
        {"name": "Turkey, Ground, cooked (100g)", "calories": 203, "protein": 27, "carbs": 0, "fats": 11.5},
        {"name": "Salmon, Atlantic (100g)", "calories": 206, "protein": 22, "carbs": 0, "fats": 12.4},
        {"name": "Salmon, Smoked (100g)", "calories": 117, "protein": 18, "carbs": 0, "fats": 4},
        {"name": "Tuna, Canned in Water (100g)", "calories": 116, "protein": 25.5, "carbs": 0, "fats": 0.8},
        {"name": "Tuna Steak, Grilled (100g)", "calories": 132, "protein": 29, "carbs": 0, "fats": 1},
        {"name": "Shrimp (100g)", "calories": 99, "protein": 24, "carbs": 0.2, "fats": 0.3},
        {"name": "Shrimp, Fried (6 pieces)", "calories": 210, "protein": 18, "carbs": 10, "fats": 10},
        {"name": "Tilapia, Baked (100g)", "calories": 128, "protein": 26, "carbs": 0, "fats": 2.7},
        {"name": "Cod, Baked (100g)", "calories": 105, "protein": 23, "carbs": 0, "fats": 0.9},
        {"name": "Lobster (100g)", "calories": 89, "protein": 19, "carbs": 0.5, "fats": 0.9},
        {"name": "Crab Meat (100g)", "calories": 97, "protein": 19, "carbs": 0, "fats": 1.5},
        {"name": "Beef Steak, Ribeye (100g)", "calories": 291, "protein": 24, "carbs": 0, "fats": 21},
        {"name": "Beef Steak, Sirloin (100g)", "calories": 212, "protein": 27, "carbs": 0, "fats": 10.6},
        {"name": "Beef Steak, Filet Mignon (100g)", "calories": 227, "protein": 26, "carbs": 0, "fats": 13},
        {"name": "Ground Beef, 95% Lean, cooked (100g)", "calories": 171, "protein": 26.5, "carbs": 0, "fats": 6.9},
        {"name": "Ground Beef, 90% Lean, cooked (100g)", "calories": 217, "protein": 26.6, "carbs": 0, "fats": 11.7},
        {"name": "Ground Beef, 80% Lean, cooked (100g)", "calories": 272, "protein": 25.8, "carbs": 0, "fats": 18.2},
        {"name": "Beef Mince, 5% Fat, cooked (100g)", "calories": 171, "protein": 26.5, "carbs": 0, "fats": 6.9},
        {"name": "Beef Mince, 10% Fat, cooked (100g)", "calories": 217, "protein": 26.6, "carbs": 0, "fats": 11.7},
        {"name": "Beef Mince, 20% Fat, cooked (100g)", "calories": 272, "protein": 25.8, "carbs": 0, "fats": 18.2},
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
    
    # A whole meal ("3 boiled eggs on 2 slices of rye") is calculated by
    # /food/ai-search from the food database; keyword matches for it are noise
    _meal = calculate_meal_text(query)
    # USDA's brand list is US products only: outside the US, brands come from
    # Open Food Facts / the web via /food/ai-search instead
    _country, _ = FoodLookup.country_from(query, country)
    usda_results = [] if _meal and len(_meal["items"]) > 1 else \
        await search_usda(query, max_results=30, branded=_country in ("US", "INTL"))
    if usda_results:
        logger.info(f"USDA returned {len(usda_results)} results")
        api_results = usda_results
    
    # STEP 3: Combine results - local first (specific items), then API results
    # Avoid duplicates by checking names
    combined_results = local_results.copy()
    # A typed meal or plain food worked out from the food database goes first —
    # the same numbers the AI search and the chat give
    if _meal:
        _db = database_meal_result(query, _meal)
        combined_results.insert(0, {**_db, "name": meal_summary(_meal)})
    local_names_lower = {food["name"].lower() for food in local_results}
    
    for api_food in api_results:
        if api_food["name"].lower() not in local_names_lower:
            combined_results.append(api_food)
    
    logger.info(f"Returning {len(combined_results)} combined results (local: {len(local_results)}, api: {len(api_results)})")
    # Nutrition-accuracy guard — reconcile each result's calories with its
    # macros (Fix 1) and log any physical-plausibility or reference
    # divergences (Fix 2/4). Deterministic — never blocks a result.
    for _r in combined_results:
        _tmp = {
            "food_name": _r.get("name", ""),
            "calories": float(_r.get("calories", 0)),
            "protein":  float(_r.get("protein", 0)),
            "carbs":    float(_r.get("carbs", 0)),
            "fats":     float(_r.get("fats", 0)),
        }
        _portion = grams_in_text(_r.get("name", ""), _r.get("name", ""))
        # Built-in and USDA values are trusted: food-specific energy factors and
        # fibre mean they rightly differ from 4/4/9 — warnings only, no rewrite
        sanitize_food_entry(_tmp, portion_g=_portion, reconcile=False)
    return combined_results[:50]

# Open Food Facts country sites (others use the ISO code)
_OFF_SITES = {"GB": "uk", "INTL": "world"}


async def _off_lookup(query: str, country: str = ""):
    """Packaged products from Open Food Facts (free, worldwide — Australian,
    UK and European brands that USDA doesn't have). Only an exact product match
    is used; restaurant chains go to the web. None when nothing matches."""
    if FoodLookup.is_chain(query):
        return None
    _, rest = FoodLookup.country_from(query, country)
    tokens = FoodLookup.food_tokens(rest)
    if not tokens:
        return None
    site = _OFF_SITES.get(country, (country or "world").lower())
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                f"https://{site}.openfoodfacts.org/cgi/search.pl",
                params={"search_terms": rest, "search_simple": 1, "action": "process", "json": 1,
                        "page_size": 20,
                        "fields": "code,product_name,brands,quantity,serving_size,serving_quantity,nutriments"},
                headers={"User-Agent": "InterFitAI/1.0 (nutrition tracking app)"},
            )
        if r.status_code != 200:
            return None
        products = r.json().get("products") or []
    except Exception as e:
        logger.warning(f"Open Food Facts search failed for '{query}': {e}")
        return None
    for product in products:
        if FoodLookup.off_match(product, tokens):
            res = FoodLookup.off_result(product)
            if res:
                return {**res, "is_ai_estimate": False, "verified": True, "confidence": "high"}
    return None


_food_lookup_index_ready = False


async def lookup_food(query: str, country: str = "", force_web: bool = False, whole: bool = False) -> dict:
    """One answer per food, the same every time, in the food log and the chat:
    1. the food database (USDA values) — everyday foods and typed meals
    2. the saved answer for this food in this country (any word order/spelling)
    3. Open Food Facts — packaged products
    4. a web search — brands and restaurants, for the user's country
    5. an AI estimate — only when nothing else finds it
    New answers are saved for everyone. Web/product answers are re-checked
    after a year; an AI estimate is retried against real sources after a week,
    and a verified answer is never replaced by an estimate."""
    global _food_lookup_index_ready
    query = (query or "").strip()
    calc = calculate_meal_text(query)
    if calc:
        return database_meal_result(query, calc)
    if not whole:
        if FoodLookup.is_chain(query):
            if re.search(r",|;|\+|&|\band\b|\bplus\b|\bwith\b|\bon\b|^\d", query):
                order = await _lookup_order(query, country, force_web)
                if order:
                    return order
        else:
            parts = split_foods(query)
            if len(parts) > 1:
                return await _lookup_items(query, parts, country, force_web)
    key, tokens, cc = FoodLookup.lookup_key(query, country)
    if not tokens:
        raise HTTPException(status_code=400, detail={"error": "empty_query", "message": "Type a food to search."})
    if not _food_lookup_index_ready:
        try:
            await db.food_lookups.create_index("key", unique=True)
            _food_lookup_index_ready = True
        except Exception as e:
            logger.warning(f"food_lookups index: {e}")
    saved = await db.food_lookups.find_one({"key": key})
    if saved and not force_web and FoodLookup.is_fresh(saved):
        return {**saved["result"], "saved": True}

    steps = [("web", _web_lookup)] if force_web else \
        [("open_food_facts", _off_lookup), ("web", _web_lookup), ("ai_estimate", _ai_estimate)]
    for kind, find in steps:
        if kind == "ai_estimate" and saved:
            break   # keep the saved answer rather than a new guess
        res = await find(query, cc)
        if res:
            res = {**res, "lookup": kind, "country": cc}
            await db.food_lookups.update_one(
                {"key": key},
                {"$set": {"key": key, "tokens": tokens, "country": cc, "query": query, "kind": kind,
                          "result": res, "updated_at": datetime.utcnow()}},
                upsert=True)
            return {**res, "saved": False}
    if saved:   # a re-check found nothing new: the saved answer stands
        return {**saved["result"], "saved": True, "web_not_found": force_web}
    return {
        "name": query[:1].upper() + query[1:], "calories": 0, "protein": 0, "carbs": 0, "fats": 0,
        "serving_size": "", "is_ai_estimate": True, "verified": False, "lookup": "none", "country": cc,
        "source": "Couldn't find this food — please add it manually", "source_url": "", "confidence": "low",
        "web_not_found": force_web,
    }


_ORDER_PROMPT = (
    "You split a food order into what was ordered. Respond with ONLY this JSON:\n"
    '{"items":[{"item":"<menu item, with the restaurant and size>","qty":1,"parts":[]}]}\n'
    "- Separate menu items (a burger and fries, a sub and a cookie) are separate items.\n"
    "- A standard menu item is one item with no parts, even if its name has 'and'/'with' "
    "(Whopper with Cheese, Steak & Cheese is a sub's name, Big Mac).\n"
    "- A build-your-own item (Subway sub, burrito, bowl, salad, wrap, poke, pizza with toppings) is ONE "
    "item; list every component the user named in \"parts\", each with the restaurant and the size, "
    "e.g. \"subway footlong rye bread\", \"subway footlong steak\", \"subway footlong cheese\", "
    "\"subway footlong spinach\", \"subway footlong smokey bbq sauce\".\n"
    "- Keep the user's words. Never add anything they didn't mention."
)


async def _parse_order(query: str):
    """A restaurant order → [{'item', 'qty', 'parts'}], or None if it can't be read."""
    try:
        raw = await call_claude_haiku(system_message=_ORDER_PROMPT, user_message=query, max_tokens=500)
        content = (raw or "").strip()
        m = re.search(r"\{[\s\S]+\}", content)
        items = json.loads(m.group(0) if m else content).get("items") or []
        out = []
        for it in items:
            name = str(it.get("item") or "").strip()
            if not name:
                continue
            qty = float(it.get("qty") or 1)
            parts = [str(x).strip() for x in (it.get("parts") or []) if str(x).strip()]
            out.append({"item": name, "qty": qty if 0 < qty <= 20 else 1, "parts": parts})
        return out or None
    except Exception as e:
        logger.warning(f"Order parse failed for '{query}': {e}")
        return None


def _combine(name: str, items: list, summary: str = None) -> dict:
    """Add up looked-up items (each with a 'qty'); the badge is the least trusted source."""
    trust = ["database", "open_food_facts", "web", "ai_estimate"]
    worst = max((i.get("lookup") or "ai_estimate" for i in items), key=lambda k: trust.index(k) if k in trust else 3)
    total = {k: round(sum(float(i.get(k) or 0) * i["qty"] for i in items), 0 if k == "calories" else 1)
             for k in ("calories", "protein", "carbs", "fats")}
    summary = summary or " + ".join(f"{i['qty']:g} × {i['name']}" if i["qty"] != 1 else i["name"] for i in items)
    return {
        "name": name[:1].upper() + name[1:], **total,
        "serving_size": summary, "serving_g": None, "serving_unit": "g",
        "items": [{k: i.get(k) for k in ("name", "qty", "calories", "protein", "carbs", "fats", "serving_size",
                                         "source", "source_url", "lookup")} for i in items],
        "is_ai_estimate": worst == "ai_estimate", "verified": worst in ("open_food_facts", "web"),
        "from_database": worst == "database", "lookup": worst,
        "source": ", ".join(dict.fromkeys(i.get("source") or "" for i in items if i.get("source"))),
        "source_url": next((i.get("source_url") for i in items if i.get("source_url")), ""),
        "confidence": "low" if worst == "ai_estimate" else "high",
        "saved": all(i.get("saved") for i in items),
    }


async def _lookup_order(query: str, country: str, force_web: bool):
    """A restaurant order, the way the chain's own nutrition calculator works:
    1. a quick AI read of the order: separate items ('whopper and large chips')
       vs one build-your-own item and its parts (a Subway sub: bread, steak,
       cheese, salads, sauce — at the sub's size)
    2. each item / part looked up and saved on its own
    3. added up.
    Saved parts make every later combination instant. Returns None for a single
    standard item (looked up whole by the caller)."""
    chain = FoodLookup.chain_in(query)
    order = await _parse_order(query)
    if order is None:   # can't read it: split on and / , / + (never 'with': "whopper with cheese")
        order = [{"item": x.strip(), "qty": 1, "parts": []}
                 for x in re.split(r"\s*(?:,|;|\+|&|\band\b|\bplus\b)\s*", query) if x.strip()]
    if len(order) == 1 and not order[0]["parts"] and order[0]["qty"] == 1:
        return None

    def with_chain(text):
        return text if not chain or FoodLookup.chain_in(text) else f"{chain} {text}"

    items = []
    for it in order:
        if it["parts"]:
            parts = []
            for part in it["parts"]:
                r = await lookup_food(with_chain(part), country, force_web, whole=True)
                if not r.get("calories"):
                    parts = None      # a part nobody knows: look the whole item up instead
                    break
                parts.append({**r, "qty": 1})
            if parts:
                combo = _combine(it["item"], parts, summary=", ".join(p["name"] for p in parts))
                items.append({**combo, "qty": it["qty"]})
                continue
        r = await lookup_food(with_chain(it["item"]), country, force_web, whole=True)
        if not r.get("calories"):
            return {**r, "name": query[:1].upper() + query[1:],
                    "source": f"Couldn't find '{it['item']}' — search it on its own or add it manually"}
        items.append({**r, "qty": it["qty"]})
    if len(items) == 1 and items[0]["qty"] == 1:
        return {**items[0], "name": query[:1].upper() + query[1:]}
    return _combine(query, items)


async def _lookup_items(query: str, parts: list, country: str, force_web: bool) -> dict:
    """A typed list that isn't a restaurant order ('2 boiled eggs and a homemade
    lasagne'): each item looked up on its own, then added up."""
    items = []
    for part in parts:
        calc = calculate_meal_text(part)
        if calc:
            items.append({**database_meal_result(part, calc), "qty": 1})
            continue
        r = await lookup_food(part, country, force_web, whole=True)
        if not r.get("calories"):
            return {**r, "name": query[:1].upper() + query[1:],
                    "source": f"Couldn't find '{part}' — search it on its own or add it manually"}
        items.append({**r, "qty": 1})
    return _combine(query, items)


async def saved_foods_in(message: str, country: str = "", limit: int = 3) -> list:
    """Saved foods named in a chat message (for the user's country), most
    specific first: 'is a large McDonald's thick shake ok?' → that shake."""
    words = set(FoodLookup.food_tokens(message))
    cc, _ = FoodLookup.country_from(message, country)
    if not words:
        return []
    found = await db.food_lookups.find({
        "country": cc, "tokens.0": {"$exists": True},
        "tokens": {"$not": {"$elemMatch": {"$nin": sorted(words)}}},
    }).to_list(50)
    found.sort(key=lambda d: len(d["tokens"]), reverse=True)
    picked = []
    for d in found:
        if not any(set(d["tokens"]) <= set(p["tokens"]) for p in picked):
            picked.append(d)
    return picked[:limit]


def database_meal_result(query: str, calc: dict) -> dict:
    """A typed meal worked out from the food database (USDA values), shaped
    like an AI search result. Same numbers as Snap and the chat coach."""
    summary = meal_summary(calc)
    if calc["assumed"]:
        summary += " — " + ", ".join(f"1 {f} assumed" for f in calc["assumed"])
    name = query.strip()
    return {
        "name":           name[:1].upper() + name[1:],
        "calories":       calc["calories"],
        "protein":        calc["protein"],
        "carbs":          calc["carbs"],
        "fats":           calc["fats"],
        "serving_size":   summary,
        "serving_g":      calc["grams"],
        "serving_unit":   "g",
        "items":          [{k: i[k] for k in ("name", "grams", "display", "calories", "protein", "carbs", "fats")}
                           for i in calc["items"]],
        "is_ai_estimate": False,
        "from_database":  True,
        "verified":       False,
        "lookup":         "database",
        "source":         "InterFitAI food database (USDA values)",
        "source_url":     "",
        "confidence":     "high",
    }


@api_router.get("/food/ai-search")
async def ai_food_search(query: str, user_id: str, country: str = ""):
    """Nutrition for any food — one answer per food, the same every time and in
    the chat (see lookup_food). `country` is the phone's region, e.g. 'AU'.
    Requires an active subscription (paid nutrition feature)."""
    access = await check_subscription_access(user_id)
    if not access.get("has_access"):
        raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Nutrition Tracking",
                                                     "message": "Nutrition tracking is a premium feature. Subscribe to unlock food search, logging, and photo analysis."})
    return await lookup_food(query, country)


async def _ai_estimate(query: str, country: str = ""):
    """The AI's own estimate, without the web. Only used when the food database,
    Open Food Facts and the web all find nothing. None when it fails."""
    import re as _re

    system_prompt = (
        "You are a precise nutrition database with deep knowledge of generic foods, "
        "packaged/branded products, and restaurant/chain menu items worldwide (US, UK, "
        "Australia, etc.). Given a food name, return your most accurate nutrition figures "
        "for ONE standard serving of that SPECIFIC item.\n"
        "- For a named brand or chain item, use that brand's known values "
        "(e.g. a McDonald's Big Mac, an In-N-Out Double-Double, a Red Rooster Quarter Pack).\n"
        "- For a generic food with no amount given, use a sensible standard serving and state it.\n"
        "- NEVER return all zeros for a real food. If unsure, give your best evidence-based "
        "estimate and set confidence to 'low'.\n"
        "Respond with ONLY this JSON, nothing else:\n"
        '{"food_name":"<exact full name>","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0,'
        '"fat_saturated_g":0,"fiber_g":0,"sodium_mg":0,"serving_size":"<e.g. 1 burger / 100g / 1 cup>",'
        '"source":"<brand / USDA / estimate>","confidence":"high|medium|low"}\n'
        "confidence: 'high' if confident of official/standard values, 'medium' if a close "
        "estimate, 'low' if a rough estimate."
    )

    def _parse(raw: str) -> dict:
        content = (raw or "").strip()
        if content.startswith("```"):
            content = _re.sub(r"```(?:json)?\n?", "", content).strip("`").strip()
        if content and not content.startswith("{"):
            m = _re.search(r"\{[\s\S]+\}", content)
            if m:
                content = m.group(0)
        return json.loads(content)

    def _all_zero(d: dict) -> bool:
        return (float(d.get("calories", 0)) == 0
                and float(d.get("protein_g", 0)) == 0
                and float(d.get("carbs_g", 0)) == 0
                and float(d.get("fat_g", 0)) == 0)

    data = None
    for attempt in range(2):
        try:
            raw = await call_claude_sonnet(
                system_message=system_prompt,
                user_message=f"Nutrition for: {query}" + (
                    f" (as sold in {FoodLookup.COUNTRY_NAMES[country]})" if country in FoodLookup.COUNTRY_NAMES else ""),
                temperature=0.2 if attempt == 0 else 0.0,
                max_tokens=500,
            )
            parsed = _parse(raw)
            data = parsed
            # An all-zero result for a real food means a bad parse/answer — retry once.
            if not _all_zero(parsed):
                break
        except Exception as e:
            logger.warning(f"AI food search attempt {attempt + 1} failed for '{query}': {e}")

    if not data or _all_zero(data):
        return None
    if data:
        # Nutrition-accuracy guard — reconcile calories with macros (Fix 1),
        # log any physical-plausibility or reference-table divergences (Fix 2/4).
        _tmp = {
            "food_name": data.get("food_name", query),
            "calories": float(data.get("calories", 0)),
            "protein_g": float(data.get("protein_g", 0)),
            "carbs_g":   float(data.get("carbs_g", 0)),
            "fat_g":     float(data.get("fat_g", 0)),
        }
        portion_g = grams_in_text(data.get("serving_size", ""),
                                           data.get("food_name", ""))
        sanitize_food_entry(_tmp, portion_g=portion_g)
        data["calories"] = _tmp["calories"]

    serving_size = str(data.get("serving_size") or "")
    serving_g = grams_in_text(serving_size, data.get("food_name", "")) or None
    return {
        "name":           data.get("food_name", query.title()),
        "calories":       round(float(data.get("calories", 0))),
        "protein":        round(float(data.get("protein_g", 0)), 1),
        "carbs":          round(float(data.get("carbs_g", 0)), 1),
        "fats":           round(float(data.get("fat_g", 0)), 1),
        "serving_size":   serving_size,
        "serving_g":      serving_g,
        "serving_unit":   "ml" if serving_g and re.search(r"\d\s*ml\b", serving_size, re.I) else "g",
        "is_ai_estimate": True,
        "verified":       False,
        "source":         data.get("source", "AI estimate"),
        "source_url":     "",
        "confidence":     data.get("confidence", "low"),
    }


@api_router.get("/food/web-search")
async def web_food_search(query: str, user_id: str, country: str = ""):
    """'Verify on the web' for an AI estimate: searches the web now and, when it
    finds real figures, saves them for everyone in place of the estimate.
    Requires an active subscription (paid nutrition feature)."""
    access = await check_subscription_access(user_id)
    if not access.get("has_access"):
        raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Nutrition Tracking",
                                                     "message": "Nutrition tracking is a premium feature. Subscribe to unlock food search, logging, and photo analysis."})
    return await lookup_food(query, country, force_web=True)


async def _web_lookup(query: str, country: str = ""):
    """Live, web-grounded nutrition: Tavily search -> Haiku extraction. Real,
    sourced macros for branded/restaurant items, for the user's country.
    None when the web has nothing reliable."""
    import re as _re
    from urllib.parse import urlparse

    if not TAVILY_API_KEY:
        return None
    where = FoodLookup.COUNTRY_NAMES.get(country, "")

    # 1. Tavily web search
    search_content, source_url = "", ""
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": f"{query} {'in ' + where + ' ' if where else ''}nutrition facts calories protein carbs fat per serving",
                    "search_depth": "basic",
                    "max_results": 5,
                    "include_answer": True,
                },
            )
        resp.raise_for_status()
        tav = resp.json()
        parts = []
        if tav.get("answer"):
            parts.append(f"Summary: {tav['answer']}")
        for r in tav.get("results", [])[:5]:
            parts.append(f"[{r.get('url', '')}] {r.get('content', '')}")
            if not source_url:
                source_url = r.get("url", "")
        search_content = "\n\n".join(parts)
    except Exception as e:
        logger.warning(f"Tavily search failed for '{query}': {e}")

    # 2. Haiku extraction (cheap, runs on existing Emergent key)
    data = None
    if search_content:
        system_prompt = (
            "You are a nutrition data extractor. Using ONLY the web search results "
            "provided, extract nutrition for ONE standard serving of the requested food. "
            "Prefer official brand/restaurant figures for the country named (if any). If results give a specific size/serving "
            "(e.g. 'large'), use that. Convert kilojoules to calories if needed (1 kcal = 4.184 kJ). "
            "Respond with ONLY this JSON:\n"
            '{"food_name":"<name>","calories":0,"protein_g":0,"carbs_g":0,"fat_g":0,'
            '"serving_size":"<e.g. 1 large / 100g>","found":true}\n'
            "Set found=false if the results do not contain real nutrition data for this food."
        )
        try:
            raw = await call_claude_haiku(
                system_message=system_prompt,
                user_message=f"Food: {query}" + (f" (in {where})" if where else "") +
                             f"\n\nWeb search results:\n{search_content}",
                temperature=0.0,
                max_tokens=400,
            )
            content = (raw or "").strip()
            if content.startswith("```"):
                content = _re.sub(r"```(?:json)?\n?", "", content).strip("`").strip()
            if content and not content.startswith("{"):
                m = _re.search(r"\{[\s\S]+\}", content)
                if m:
                    content = m.group(0)
            data = json.loads(content)
        except Exception as e:
            logger.warning(f"Haiku extraction failed for '{query}': {e}")

    # 3. Build response
    if data and data.get("found", True) and float(data.get("calories", 0)) > 0:
        # Nutrition-accuracy guard — reconcile calories with macros (Fix 1)
        # and log any physical-plausibility or reference divergences (Fix 2/4).
        _tmp = {
            "food_name": data.get("food_name", query),
            "calories": float(data.get("calories", 0)),
            "protein_g": float(data.get("protein_g", 0)),
            "carbs_g":   float(data.get("carbs_g", 0)),
            "fat_g":     float(data.get("fat_g", 0)),
            "fiber_g":   float(data.get("fiber_g", 0) or 0),
        }
        portion_g = grams_in_text(data.get("serving_size", ""),
                                           data.get("food_name", ""))
        sanitize_food_entry(_tmp, portion_g=portion_g)
        data["calories"] = _tmp["calories"]
        domain = urlparse(source_url).netloc.replace("www.", "") if source_url else "web"
        serving_size = str(data.get("serving_size") or "")
        serving_g = grams_in_text(serving_size, data.get("food_name", "")) or None
        return {
            "name":           data.get("food_name", query.title()),
            "calories":       round(float(data.get("calories", 0))),
            "protein":        round(float(data.get("protein_g", 0)), 1),
            "carbs":          round(float(data.get("carbs_g", 0)), 1),
            "fats":           round(float(data.get("fat_g", 0)), 1),
            "serving_size":   serving_size,
            "serving_g":      serving_g,
            "serving_unit":   "ml" if serving_g and re.search(r"\d\s*ml\b", serving_size, re.I) else "g",
            "is_ai_estimate": False,
            "verified":       True,
            "source":         domain,
            "source_url":     source_url,
            "confidence":     "high",
        }
    return None

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

CHAT_DAILY_LIMIT = 60          # messages per user per 24 hours
CHAT_MAX_MESSAGE_CHARS = 2000


async def _chat_user_context(user_id: str, profile: Optional[dict]) -> str:
    """What the coach knows about the user: stats, the app's own daily targets,
    and their current program (including injuries)."""
    if not profile:
        return ""
    lines = []
    for label, key, unit in (("Age", "age", ""), ("Gender", "gender", ""), ("Height", "height", " cm"),
                             ("Weight", "weight", " kg"), ("Activity level", "activity_level", "")):
        if profile.get(key):
            lines.append(f"{label}: {profile[key]}{unit}")
    if profile.get("goal"):
        lines.append(f"Nutrition goal: {str(profile['goal']).replace('_', ' ')}")
    if profile.get("unit_preference") == "lbs":
        lines.append("Prefers pounds (lbs) for weights")
    m = profile.get("calculated_macros") or {}
    if m.get("calories"):
        adj = safe_calorie_adjustment(m, profile.get("calorie_adjustment"))
        lines.append(f"App daily targets: {round(m['calories'] + adj)} kcal, {round(m.get('protein', 0))}g protein, "
                     f"{round(m.get('carbs', 0) + adj / 4)}g carbs, {round(m.get('fats', 0))}g fat")
    program = await db.workouts.find_one({"user_id": user_id}, sort=[("created_at", -1)])
    if program:
        lines.append(f"Current program: {program.get('name', '')} — {program.get('days_per_week', '?')} days/week, "
                     f"{program.get('session_duration_minutes', '?')} min sessions, level {program.get('fitness_level', '?')}")
        if program.get("injuries"):
            lines.append(f"Injuries / limitations: {', '.join(program['injuries'])}")
    lines.append(f"Today's date: {datetime.utcnow().strftime('%Y-%m-%d')}")
    return "\n".join(lines)


CHAT_SYSTEM_PROMPT = """You are InterFitAI, the user's AI fitness and nutrition coach inside the InterFitAI app. You help with training, exercise technique, nutrition, recovery, habits and motivation.

USER:
{context}

RULES
- Use the user's details above. When they ask about calories, protein or macros, use the APP DAILY TARGETS above — never invent different numbers. If they want to change them, tell them they can adjust calories in Profile → Daily targets.
- Respect their injuries/limitations: suggest safe alternatives and tell them to stop anything that causes pain.
- Evidence-based advice only. Food first. You may mention well-established basics (protein powder, creatine monohydrate, caffeine, vitamin D) with normal doses. Never recommend steroids, SARMs, prohormones, fat burners, diuretics, or any prescription drug, and never give dosing for them.
- Never suggest crash diets, eating under 1,200 kcal (women) or 1,500 kcal (men), purging, or extreme fasting.
- You are not a doctor. For chest pain, fainting, injuries that don't improve, pregnancy, medical conditions or medications, give general guidance only and recommend seeing a doctor or physio. If the user mentions disordered eating, self-harm or thoughts of hurting themselves, respond with care, don't give diet advice, and encourage them to contact a health professional or a local support line (e.g. Butterfly Foundation 1800 33 4673 in Australia, Lifeline 13 11 14).
- If the user seems under 18, keep advice general and safe and encourage involving a parent, coach or doctor.
- Stay on fitness, nutrition, health habits and using the app. Politely decline unrelated requests.

STYLE
- Friendly, direct, encouraging. Usually under 150 words unless they ask for detail or a full plan.
- Plain text. Short paragraphs; use simple "- " bullet lines for lists. No markdown headings, bold or tables."""


@api_router.post("/chat", response_model=ChatMessage)
async def chat_with_ai(request: ChatRequest):
    """Chat with InterFitAI for fitness and health questions"""
    # Paid AI feature: checked on the server, with a daily cap to control cost
    access = await check_subscription_access(request.user_id)
    if not access.get("has_access"):
        raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Ask InterFitAI",
                                                     "message": "Ask InterFitAI is a premium feature. Start your free trial to unlock it."})
    message = (request.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail={"error": "empty_message", "message": "Type a question first."})
    if len(message) > CHAT_MAX_MESSAGE_CHARS:
        raise HTTPException(status_code=400, detail={"error": "message_too_long",
                                                     "message": f"Please keep messages under {CHAT_MAX_MESSAGE_CHARS} characters."})
    sent_today = await db.chat_history.count_documents({
        "user_id": request.user_id, "role": "user",
        "created_at": {"$gte": datetime.utcnow() - timedelta(hours=24)},
    })
    if sent_today >= CHAT_DAILY_LIMIT:
        raise HTTPException(status_code=429, detail={"error": "daily_limit",
                                                     "message": "You've reached today's message limit. It resets within 24 hours."})

    # Get user context for personalized responses
    profile = await db.profiles.find_one({"id": request.user_id})

    # Recent conversation the user can still see (removed messages don't steer answers)
    history = await db.chat_history.find(
        {"user_id": request.user_id, "chat_visible": {"$ne": False}}
    ).sort("created_at", -1).limit(10).to_list(10)
    history.reverse()

    messages = [
        {
            "role": "system",
            "content": CHAT_SYSTEM_PROMPT.format(
                context=await _chat_user_context(request.user_id, profile) or "(no profile details yet)"),
        }
    ]

    # Add chat history
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # A meal with amounts in the question ("macros for 3 boiled eggs on 2 slices
    # of rye?") is worked out by the food database, so the coach gives the same
    # numbers as the food log instead of its own estimate
    digit = re.search(r"\d", message)
    meal = calculate_meal_text(re.split(r"[?!\n]", message[digit.start():])[0]) if digit else None
    if meal:
        lines = [f"- {i['display']} ({i['grams']}g): {i['calories']} kcal, {i['protein']}g protein, "
                 f"{i['carbs']}g carbs, {i['fats']}g fat" for i in meal["items"]]
        if meal["assumed"]:
            lines.append("- Assumed (no amount given): " + ", ".join(f"1 {f}" for f in meal["assumed"]))
        lines.append(f"- Total: {meal['calories']} kcal, {meal['protein']}g protein, "
                     f"{meal['carbs']}g carbs, {meal['fats']}g fat")
        messages[0]["content"] += (
            "\n\nFOOD DATABASE RESULT for the food in the user's message. The app's food log "
            "shows exactly these numbers — use them, do not estimate your own:\n" + "\n".join(lines))
    else:
        # Foods the food log has already looked up (brands, restaurants…). An
        # extra only: a lookup problem never stops the coach from answering
        try:
            saved = await saved_foods_in(message, request.country or "")
        except Exception as e:
            logger.warning(f"Saved food lookup for chat failed: {e}")
            saved = []
        if saved:
            lines = []
            for d in saved:
                r = d["result"]
                src = "verified on the web" if r.get("verified") else "estimate"
                lines.append(f"- {r.get('name')} ({r.get('serving_size') or 'per serving'}): {r.get('calories')} kcal, "
                             f"{r.get('protein')}g protein, {r.get('carbs')}g carbs, {r.get('fats')}g fat "
                             f"[{r.get('source') or src}]")
            messages[0]["content"] += (
                "\n\nFOOD LOG RESULTS for foods in the user's message. The app's food log shows exactly "
                "these numbers — use them, do not estimate your own:\n" + "\n".join(lines))

    # Add current message
    messages.append({"role": "user", "content": message})

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
            .with_model("anthropic", CLAUDE_HAIKU_MODEL)
            .with_params(max_tokens=1000 + HAIKU_THINKING_HEADROOM, timeout=90)
        )
        ai_response = await chat.send_message(UserMessage(text=message))
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=503, detail={"error": "chat_unavailable",
                                                     "message": "The coach couldn't answer just now. Please try again in a moment."})

    # Save user message
    user_msg = ChatMessage(user_id=request.user_id, role="user", content=message)
    await db.chat_history.insert_one(user_msg.model_dump())

    # Save AI response
    ai_msg = ChatMessage(user_id=request.user_id, role="assistant", content=ai_response)
    await db.chat_history.insert_one(ai_msg.model_dump())

    return ai_msg

@api_router.get("/chat/history/{user_id}")
async def get_chat_history(user_id: str, limit: int = 50):
    """Get chat history for a user"""
    history = await db.chat_history.find({"user_id": user_id, "chat_visible": {"$ne": False}}).sort("created_at", -1).limit(limit).to_list(limit)
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

@api_router.post("/chat/dismiss/{message_id}")
async def dismiss_chat_message(message_id: str):
    """Remove a message from the chat view only. Does NOT affect its saved status."""
    result = await db.chat_history.update_one({"id": message_id}, {"$set": {"chat_visible": False}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"message": "Message dismissed from chat"}

@api_router.delete("/chat/message/{message_id}")
async def delete_chat_message(message_id: str):
    """Permanently delete a chat message (used by the Saved tab delete)."""
    await db.chat_history.delete_one({"id": message_id})
    return {"message": "Message deleted"}

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
async def log_steps(user_id: str, steps: int, distance_km: float = 0, source: str = "device",
                    date: Optional[str] = None):
    """Log steps for the user's day. A phone/watch reports the day's total so
    far, so device entries replace a lower total instead of adding to it;
    manual entries add."""
    today = date or datetime.now().strftime("%Y-%m-%d")
    
    # Calculate calories burned (rough estimate: 0.04 calories per step)
    calories_burned = int(steps * 0.04)
    
    # Check if entry exists for today
    existing = await db.steps.find_one({"user_id": user_id, "date": today})
    
    if existing:
        # Update existing entry
        if source == "manual":
            new_steps = existing["steps"] + steps
            new_distance = existing["distance_km"] + distance_km
        else:
            new_steps = max(existing["steps"], steps)
            new_distance = max(existing["distance_km"], distance_km)
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

    return {"message": f"Unknown device type: {device_type}"}

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
    "monthly": {"name": "Monthly", "price": 14.99, "duration_months": 1, "trial_days": 7, "features": ["AI Workouts", "AI Meal Plans", "Food Tracking", "Ask InterFitAI", "Step Tracking", "Body Analyzer"]},
    "yearly": {"name": "Yearly", "price": 99.99, "duration_months": 12, "trial_days": 7, "features": ["AI Workouts", "AI Meal Plans", "Food Tracking", "Ask InterFitAI", "Step Tracking", "Body Analyzer", "Priority Support", "Exclusive Content"]}
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
    """Create Stripe checkout session with the plan's free trial (7 days)"""
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
                        'description': f'{plan["trial_days"]}-day FREE trial, then ${plan["price"]}/{"month" if plan["duration_months"] == 1 else str(plan["duration_months"]) + " months"}'
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
                'trial_period_days': plan["trial_days"],  # free trial (7 days)
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
    if not is_admin(request.admin_email):
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
    if not is_admin(admin_email):
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
    if not is_admin(admin_email):
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
    return {"is_admin": is_admin(email), "email": email}

# ==================== MOTIVATION & REMINDERS ====================

DAILY_MOTIVATIONS = [
    "The only bad workout is the one that didn't happen. Get moving! 💪",
    "Your body can stand almost anything. It's your mind you have to convince.",
    "Success is the sum of small efforts repeated day in and day out.",
    "The pain you feel today will be the strength you feel tomorrow.",
    "Don't wish for it, work for it.",
    "Your health is an investment, not an expense.",
    "Every rep counts. Every meal matters. Stay consistent.",
    "Wake up with determination. Go to bed with satisfaction.",
    "Fitness isn't about being better than someone else — it's about being better than you used to be.",
    "Push yourself, because no one else is going to do it for you.",
    "The hard days are what make you stronger.",
    "Believe in yourself and all that you are.",
    "Today's actions are tomorrow's results.",
    "Discipline is choosing what you want most over what you want now.",
    "You don't have to be extreme — just consistent.",
    "Small progress is still progress.",
    "Motivation gets you started. Habit keeps you going.",
    "A year from now, you'll wish you had started today.",
    "The body achieves what the mind believes.",
    "Strive for progress, not perfection.",
    "Sweat is just your effort made visible.",
    "You are one workout away from a better mood.",
    "Strong people are harder to break — in every way.",
    "Results happen over time, not overnight. Trust the process.",
    "Take care of your body. It's the only place you have to live.",
    "The best project you'll ever work on is you.",
    "Show up, even when you don't feel like it — especially then.",
    "Champions train. Everyone else complains.",
    "Energy flows where attention goes. Focus on your goals.",
    "Nothing truly worth having comes without the work.",
]

@api_router.get("/motivation")
async def get_daily_motivation():
    """Get the daily motivation quote — deterministic per calendar day,
    so every open of the app shows the same quote until midnight."""
    day_seed = int(datetime.utcnow().strftime("%Y%j"))
    return {"motivation": DAILY_MOTIVATIONS[day_seed % len(DAILY_MOTIVATIONS)]}

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

class WeightEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    weight_kg: float
    date: str                      # the user's day, YYYY-MM-DD
    note: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class WeightLogRequest(BaseModel):
    user_id: str
    weight_kg: float
    date: str
    note: Optional[str] = None


async def _sync_profile_weight(user_id: str):
    """The profile follows the 7-day average of logged weights (daily water
    swings don't move targets). Targets are recalculated, as when weight is
    edited in the profile, once the average moves by 0.5 kg or more."""
    recent = await db.weight_logs.find({"user_id": user_id}).sort("date", -1).to_list(7)
    if not recent:
        return
    latest = datetime.strptime(recent[0]["date"], "%Y-%m-%d")
    week = [r["weight_kg"] for r in recent
            if (latest - datetime.strptime(r["date"], "%Y-%m-%d")).days < 7]
    avg = round(sum(week) / len(week), 1)
    profile = await db.profiles.find_one({"id": user_id})
    if not profile or abs(float(profile.get("weight") or 0) - avg) < 0.5:
        return
    update = {"weight": avg, "updated_at": datetime.utcnow()}
    try:
        update["calculated_macros"] = calculate_macros(
            avg, profile["height"], profile["age"], profile["gender"],
            profile["activity_level"], profile["goal"], profile.get("mostly_muscle"))
        update["calorie_adjustment"] = safe_calorie_adjustment(
            update["calculated_macros"], profile.get("calorie_adjustment"))
    except Exception as e:   # incomplete profile — keep the weight, skip targets
        logger.warning(f"Weight sync: targets not recalculated for {user_id}: {e}")
    await db.profiles.update_one({"id": user_id}, {"$set": update})


@api_router.post("/weight/log")
async def log_weight(request: WeightLogRequest):
    """Log body weight for a day (one entry per day — logging again replaces
    it). The profile's weight follows the 7-day average."""
    if not 20 <= request.weight_kg <= 400:
        raise HTTPException(status_code=422, detail={"error": "weight_out_of_range",
                                                     "message": "Enter a weight between 20 and 400 kg."})
    try:
        datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=422, detail={"error": "bad_date", "message": "Date must be YYYY-MM-DD."})
    entry = WeightEntry(user_id=request.user_id, weight_kg=round(request.weight_kg, 2),
                        date=request.date, note=request.note)
    existing = await db.weight_logs.find_one({"user_id": request.user_id, "date": request.date})
    if existing:
        entry.id = existing["id"]
    await db.weight_logs.replace_one({"user_id": request.user_id, "date": request.date},
                                     entry.model_dump(), upsert=True)
    await _sync_profile_weight(request.user_id)
    return entry


@api_router.get("/weight/logs/{user_id}")
async def get_weight_logs(user_id: str, days: int = 365):
    """Weight entries, oldest first, for the last `days` days (by entry date)."""
    since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    docs = await db.weight_logs.find({"user_id": user_id, "date": {"$gte": since}}).sort("date", 1).to_list(None)
    for d in docs:
        d.pop("_id", None)
    return docs


@api_router.delete("/weight/log/{entry_id}")
async def delete_weight_log(entry_id: str, user_id: str):
    result = await db.weight_logs.delete_one({"id": entry_id, "user_id": user_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Weight entry not found")
    await _sync_profile_weight(user_id)
    return {"message": "Weight entry deleted"}


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
    before_weight_kg: Optional[float] = None
    after_weight_kg: Optional[float] = None

@api_router.post("/body/upload-progress")
async def upload_progress_photo(user_id: str, image_base64: str, label: str = "progress", notes: str = None, weight: float = None):
    """Upload a progress photo. Stores the full image for future comparison."""
    photo = ProgressPhoto(
        user_id=user_id,
        image_base64=image_base64,  # store full image — needed for history + analysis
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
    """AI-powered body transformation analysis comparing before/after photos.

    Enriches the prompt with the user's profile (weight, height, goal) so the AI
    can calibrate its feedback — a 4kg change means different things for a 60kg
    vs a 110kg person, and a cutter vs a bulker.
    """
    # Paid AI feature: checked here, not only in the app
    access = await check_subscription_access(request.user_id)
    if not access.get("has_access"):
        raise HTTPException(status_code=403, detail={"error": "premium_required", "feature": "Body Analysis",
                                                     "message": "AI body analysis is a premium feature. Start your free trial to unlock it."})

    # ── Pull user profile for context ────────────────────────────────
    profile = await db.profiles.find_one({"id": request.user_id})
    ctx_lines = [f"Time period between photos: {request.time_period}"]
    goal_framing = "overall body composition"
    if profile:
        weight = profile.get("weight")
        height = profile.get("height")
        age    = profile.get("age")
        gender = profile.get("gender", "unspecified")
        goal   = profile.get("goal", "maintenance")

        if weight: ctx_lines.append(f"Current weight: {weight} kg")
        if height: ctx_lines.append(f"Height: {height} cm")
        if age:    ctx_lines.append(f"Age: {age}")
        ctx_lines.append(f"Gender: {gender}")
        ctx_lines.append(f"Training goal: {goal.replace('_', ' ')}")
        m = profile.get("calculated_macros") or {}
        if m.get("calories"):
            cal = round(m["calories"] + safe_calorie_adjustment(m, profile.get("calorie_adjustment")))
            ctx_lines.append(f"App daily targets: {cal} kcal, {round(m.get('protein', 0))}g protein")

        goal_framing = {
            "weight_loss":     "visible fat loss while preserving muscle",
            "muscle_building": "visible muscle growth with controlled fat gain",
            "maintenance":     "body recomposition — simultaneous fat loss and muscle gain",
        }.get(goal, "overall body composition")

    # Optional explicit weight delta from the user
    if request.before_weight_kg and request.after_weight_kg:
        delta = request.after_weight_kg - request.before_weight_kg
        ctx_lines.append(
            f"Weight at Before: {request.before_weight_kg} kg | "
            f"Weight at After: {request.after_weight_kg} kg | "
            f"Delta: {'+' if delta >= 0 else ''}{delta:.1f} kg"
        )

    user_context = "\n".join(ctx_lines)

    body_system_prompt = None
    try:
        content = await call_claude_sonnet(
            system_message=(body_system_prompt := f"""You are a professional fitness coach and body composition expert analysing before/after progress photos.

USER CONTEXT:
{user_context}

PRIMARY GOAL FRAMING: Focus feedback on {goal_framing}.

SCORING RUBRIC (estimated_progress_score, 1-10):
  10 = near-complete physique transformation — dramatic change aligned with goal
  8  = clear, significant progress — obvious visible change
  6  = moderate progress — visible but modest change
  4  = minor changes — small shifts in composition or tone
  2  = very little visible change
  1  = no change or regression

Provide a body fat % ESTIMATE as a range (e.g. "18-21%") for each photo. Prefix with "Estimate: " — do not claim clinical precision. If the photos do not allow confident estimation (bad angle, clothing obscuring, poor lighting), say so honestly in overall_assessment and lower the confidence accordingly.

Be encouraging but HONEST. Do not inflate scores. If there is little change, say so and give specific actionable next steps.

The FIRST image is BEFORE and the SECOND image is AFTER. Compare like with like (same angle,
lighting, pump/flex); if the photos differ a lot in angle, lighting or clothing, say so and lower
analysis_confidence.

RECOMMENDATIONS: practical training, nutrition, sleep and consistency steps. If the user's app
daily targets are given above, keep nutrition advice in line with them (e.g. "keep hitting your
protein target") — never give a different calorie or protein number, never suggest crash diets,
fasting protocols, supplements beyond basics, or drugs.

SAFETY:
- Describe the body neutrally and respectfully. No comments on attractiveness; no shaming words.
- If the person appears to be under 18, do not analyse body fat or score — set
  estimated_progress_score to 0, analysis_confidence to "low", and kindly say the analysis is
  for adults.
- If the photos suggest the person may be underweight or unwell, do not praise further fat loss;
  gently encourage them to check in with a doctor or dietitian.
- If the images are not two photos of a person's body, say so in overall_assessment, set
  estimated_progress_score to 0 and analysis_confidence to "low".

Respond with valid JSON only — no markdown fences:
{{
    "overall_assessment": "2-3 sentence assessment calibrated to the user's goal and stats",
    "estimated_body_fat_before": "e.g. 18-21%",
    "estimated_body_fat_after":  "e.g. 14-17%",
    "visible_changes": ["Specific change 1", "Specific change 2", "Specific change 3"],
    "areas_improved": ["Specific muscle group or region 1", "Area 2"],
    "recommendations": ["Actionable recommendation 1", "Recommendation 2", "Recommendation 3"],
    "motivation_message": "Encouraging but honest message",
    "estimated_progress_score": 8,
    "analysis_confidence": "high | medium | low"
}}"""),
            user_message=f"Image 1 is BEFORE, image 2 is AFTER, taken {request.time_period} apart. Analyse them and return the full JSON response per the system prompt.",
            max_tokens=1200,
            temperature=0.3,   # consistent scores for the same photos
            image_base64=request.before_image_base64,
            image_base64_2=request.after_image_base64
        )

        # ── Clean markdown fences ────────────────────────────────────
        content = content.strip() if content else ""
        if content.startswith("```"):
            lines = content.split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.startswith("```json"):
                    in_json = True; continue
                elif line.startswith("```"):
                    in_json = False; continue
                if in_json or not line.startswith("```"):
                    json_lines.append(line)
            content = "\n".join(json_lines)
        content = content.strip()

        analysis_data = json.loads(content)

        analysis_record = {
            "id": str(uuid.uuid4()),
            "user_id": request.user_id,
            "time_period": request.time_period,
            "analysis": analysis_data,
            "created_at": datetime.utcnow(),
        }
        await db.body_analyses.insert_one(analysis_record)
        return {"analysis": analysis_data, "id": analysis_record["id"]}

    except json.JSONDecodeError as parse_err:
        logger.error(f"Body analysis JSON parse failed: {parse_err} | raw content: {content[:500]}")
        # One retry with a stricter instruction
        try:
            retry_content = await call_claude_sonnet(
                system_message=(body_system_prompt or "") + "\n\nYou MUST respond with valid JSON only — no markdown, no prose.",
                temperature=0.3,
                user_message=f"Image 1 is BEFORE, image 2 is AFTER. Re-analyse these photos and return ONLY the JSON object with fields: overall_assessment, estimated_body_fat_before, estimated_body_fat_after, visible_changes (array), areas_improved (array), recommendations (array), motivation_message, estimated_progress_score (1-10 integer), analysis_confidence (high|medium|low). Taken over {request.time_period}.",
                max_tokens=1000,
                image_base64=request.before_image_base64,
                image_base64_2=request.after_image_base64
            )
            retry_content = retry_content.strip()
            if retry_content.startswith("```"):
                retry_content = retry_content.split("```")[1]
                if retry_content.startswith("json"):
                    retry_content = retry_content[4:]
            retry_content = retry_content.strip()
            analysis_data = json.loads(retry_content)

            analysis_record = {
                "id": str(uuid.uuid4()),
                "user_id": request.user_id,
                "time_period": request.time_period,
                "analysis": analysis_data,
                "created_at": datetime.utcnow(),
            }
            await db.body_analyses.insert_one(analysis_record)
            return {"analysis": analysis_data, "id": analysis_record["id"]}
        except Exception as retry_err:
            logger.error(f"Body analysis retry failed: {retry_err}")
            raise HTTPException(
                status_code=502,
                detail="Analysis could not be completed — please try again with clearer photos."
            )
    except Exception as e:
        logger.error(f"Body analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze progress: {str(e)}")

@api_router.get("/body/history/{user_id}")
async def get_analysis_history(user_id: str):
    """Get body analysis history for a user"""
    analyses = await db.body_analyses.find({"user_id": user_id}).sort("created_at", -1).to_list(20)
    for item in analyses:
        if '_id' in item:
            item['_id'] = str(item['_id'])
    return analyses

@api_router.delete("/body/analysis/{analysis_id}")
async def delete_body_analysis(analysis_id: str):
    """Permanently delete a single body analysis record."""
    await db.body_analyses.delete_one({"id": analysis_id})
    return {"success": True}

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
    if is_admin(email):
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
    if not is_admin(admin_email):
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
    if not is_admin(admin_email):
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
    if not is_admin(admin_email):
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
    plan: str,  # monthly or yearly
    success_url: str,
    cancel_url: str
):
    """
    Create a Stripe Checkout session for website subscriptions — the same two
    plans and prices as the app (SUBSCRIPTION_PLANS):
    - Monthly: $14.99 with a 7-day free trial
    - Yearly: $99.99 with a 30-day bonus (applied after payment)
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    if plan not in ["monthly", "yearly"]:
        raise HTTPException(status_code=400, detail="Invalid plan. Choose 'monthly' or 'yearly'")
    
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
        if plan == "monthly":
            # Monthly with the same free trial as the app (SUBSCRIPTION_PLANS)
            checkout_params["line_items"] = [{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "InterFitAI Premium - Monthly",
                        "description": "Full access to all InterFitAI features",
                    },
                    "unit_amount": int(round(SUBSCRIPTION_PLANS["monthly"]["price"] * 100)),  # $14.99
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }]
            checkout_params["subscription_data"] = {
                "trial_period_days": SUBSCRIPTION_PLANS["monthly"]["trial_days"],
                "metadata": {"user_id": user_id, "plan": "monthly"},
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
                    "unit_amount": int(round(SUBSCRIPTION_PLANS["yearly"]["price"] * 100)),  # $99.99
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

def _stripe_plan_days(plan: str) -> int:
    """Days of access one website payment buys (renewals add the same)."""
    return {"yearly": 365, "quarterly": 90}.get(plan, 31)   # quarterly: older subscribers only


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
            plan = data.get("metadata", {}).get("plan", "monthly")
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
                    expires_at = datetime.utcnow() + timedelta(days=_stripe_plan_days(plan))
                
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
                    plan = profile.get("subscription_plan", "monthly")
                    expires_at = datetime.utcnow() + timedelta(days=_stripe_plan_days(plan))
                    
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
