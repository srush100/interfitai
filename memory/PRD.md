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
- **Backend**: FastAPI (Python) — monolithic server.py (~9200 lines)
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
- `PATCH /api/workout/{id}/week-override` — set manual week (1-4) for progression block

## DB Schema Highlights
- `profiles`: { id, email, name, weight_kg, height_cm, unit_preference, calculated_macros, ... }
|- `workouts`: { id, user_id, name, workout_days, performance: {day-ex-set: {weight, reps, completed}}, weekly_structure, weekly_progression, current_week_override }
- `workout_sessions`: { id, user_id, workout_id, completed_exercises, total_volume, photo_base64, date }
- `exercise_library`: { exercisedb_id, name, target, secondary_muscles, body_part, equipment, gif_url, gif_id, instructions } — 1394 exercises

## Implemented Features (Changelog)
- User auth (email + password, JWT)
- Profile creation with macro calculation
- AI workout generation with Elite Coaching Engine (split selection, volume, RIR, deload)
- Workout detail view: exercises, sets/reps, weight tracking, GIFs
- Session completion with blank-slate reset (all inputs cleared)
- Personal Record (PR) detection with confetti celebration
- Workout streaks and weekly adherence stats
- Meal plan generation (template-based + AI)
- Food tracking with AI image recognition
- Ask InterFitAI chat (Claude Sonnet)
- Subscription flow (Stripe web payments)
- kg/lbs unit preference toggle
- Monthly generation quota enforcement (3/month, admin bypass)
- Post-workout photo upload
- Workout rename
- **[Jun 2026] Conditional Split Picker**: Hidden in questionnaire for hybrid/functional/calisthenics training styles and athletic_performance goal
- **[Jun 2026] Preferred Start Day**: Questionnaire includes start day selector (default Monday)
- **[Jun 2026] 7-Day Weekly Structure with Explicit Rest Days**: Backend distributes rest days optimally (no 3+ consecutive training days for beginners), displayed in Weekly Blueprint with `moon-outline` icon, muted styling, and coaching note
- **[Jun 2026] 4-Week Progressive Progression Banner**: Auto-computed week (days 0-6=Wk1...capped at 4), tappable to manually override, shows coaching instruction per week, Week 4 shows completion prompt
- **[Jun 2026] Local Exercise Library Migration**: Imported 1394 exercises from ExerciseDB into local MongoDB `exercise_library` collection. Rewrote `GET /api/exercises/search` to query local DB (no rate limits, proper muscle group filtering). Frontend Replace Modal auto-selects primary muscle chip on open, shows "Recommended Swaps" section, and "Load More" pagination button.
- **[Jun 2026] GIF Proxy Fix**: Fixed HTTPException swallowing bug in `/api/exercises/gif/{id}` — invalid IDs now return 404/400 instead of 500.
- **[Jun 2026] Exercise Naming & Multi-Muscle Categorization**: Added EXERCISE_NAME_OVERRIDES (90+ entries) — ExerciseDB raw names → gym-standard display names at response time only (e.g. "Barbell Full Squat" → "Barbell Back Squat", "Barbell Lying Triceps Extension" → "Skull Crushers", "Sled 45° Leg Press" → "Leg Press"). Added EXERCISE_TARGET_OVERRIDES (60+ entries) — compound exercises now surface under all relevant muscle chips (back squat → legs + glutes, deadlift → glutes + legs + back, bench press → chest + triceps, rows → back + biceps, OHP → shoulders + triceps). Updated search query to use `$or` combining primary target, secondary_muscles array, and override names. Added reverse text lookup so "back squat" finds "Barbell Back Squat". Added `secondary_muscles` index.

- **[Jun 2026] Exercise Preferences Wired into Generation**: `exercise_preferences` free-text field was dead code — now flows from `WorkoutGenerateRequest` → `build_blueprint()` return dict → Claude prompt as advisory guidance: "When an option matches a liked exercise, prefer it. When an option matches a disliked exercise, choose a different option from the list. Never pick an exercise outside the provided Options." Verified: "hate burpees" → zero burpees in 15-exercise 3-day plan; "love RDLs, hate burpees" → RDL appeared in hip_hinge slot, zero burpees across 21 exercises. (backend/server.py only)

## Backlog (Prioritized)
### P0 — Critical
- (none)

### P1 — High
- Test `generate_alternate_meal` endpoint with foods_to_avoid filtering (deferred by user)

### P2 — Medium
- Enable Live In-App Purchases (RevenueCat — native build only, not testable in web preview)
- Build Profile/Stats screen with all-time PRs

### P3 — Low
- Exercise GIFs in circuit workouts
- Enhance subscription page UI
- Google Fit / Fitbit / Garmin device connection logic
- `generation_events`: { user_id, email, created_at }
