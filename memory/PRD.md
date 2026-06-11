# InterFitAI — Product Requirements Document

## Original Problem Statement
Build a comprehensive AI-powered fitness app (InterFitAI) with:
- User profile & macro calculation (Mifflin-St Jeor BMR/TDEE)
- AI workout generation (Elite Coaching Engine — Python rules-based, not LLM guessing)
- AI meal plan generation (template-based + AI with preferred foods)
- Food tracking with image recognition
- Ask InterFitAI chat
- Subscription payments (Stripe web + RevenueCat mobile)
- Step tracking & device connections
- Workout Streaks, Personal Records (PRs), Post-Workout Photos
- Monthly generation cap (3/month, admin bypass)
- kg/lbs unit preference (store kg, display in user's chosen unit)

## User Personas
- **Primary**: Fitness enthusiasts wanting personalized, AI-driven plans
- **Secondary**: Athletes tracking PRs and volume over time
- **Admin**: sebastianrush5@gmail.com — bypasses generation cap

## Architecture
- **Frontend**: Expo / React Native (file-based routing via expo-router)
- **Backend**: FastAPI (Python) — monolithic server.py (~9000 lines)
- **Database**: MongoDB (Motor async driver)
- **AI**: Claude Sonnet 4.5 (complex) + Claude Haiku 4.5 (fast/food) via Emergent LLM Key
- **Payments**: Stripe (web), RevenueCat (mobile — P2)

## Core Requirements (Static)
1. Store all weights in kg; display in user's `unit_preference` (kg/lbs)
2. Meal plan macros must match user's profile targets (post-processing enforces exact match)
3. `foods_to_avoid` must be respected in template and AI meal generation + alternate meals
4. Workout generation must follow Elite Coaching Engine rules (split selection, volume, RIR)
5. Monthly generation cap: 3 programs per user per month; admin emails bypass cap
6. After completing a workout, all inputs (weight, reps, checkboxes) reset to blank; "Last time" hints persist

## Key Endpoints
- `POST /api/profile` — create/update profile
- `POST /api/workouts/generate` — AI workout generation
- `POST /api/mealplans/generate` — meal plan generation (template or AI)
- `POST /api/mealplan/alternate` — alternate meal with foods_to_avoid filtering
- `POST /api/workout/{id}/session/complete` — complete session, detect PRs, blank-slate reset
- `GET /api/workout/stats/{user_id}` — streaks + weekly adherence
- `GET /api/workout/personal-records/{user_id}` — all-time PRs
- `GET /workouts/generation-quota/{user_id}` — monthly cap status
- `POST /api/workout/session/{session_id}/photo` — post-workout photo upload

## DB Schema Highlights
- `profiles`: { id, email, name, weight_kg, height_cm, unit_preference, calculated_macros, ... }
- `workouts`: { id, user_id, name, workout_days, performance: {day-ex-set: {weight, reps, completed}} }
- `workout_sessions`: { id, user_id, workout_id, completed_exercises, total_volume, photo_base64, date }
- `generation_events`: { user_id, email, created_at }
