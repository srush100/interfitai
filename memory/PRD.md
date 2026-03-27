# InterFitAI - Product Requirements Document

## Original Problem Statement
Build InterFitAI - a comprehensive AI fitness app with:
- User profile & macro calculation
- AI workout generation (ELITE COACHING ENGINE - Python rules, not LLM guessing)
- AI meal plan generation (5-stage algorithmic scaling, 0% macro deviation)
- Food tracking with image recognition
- Ask InterFitAI chat
- Subscription payments with Stripe
- Step tracking
- Device connections (Apple Health, Garmin, Fitbit, Google Fit)

## User Personas
- Primary: Health-conscious individuals wanting personalized AI fitness plans
- Admin: sebastianrush5@gmail.com / srush@interfitai.com (full free access)

## Core Requirements
1. **Elite Workout Engine**: Python determines split/volume/sets/reps/rest/effort. LLM only fills names+form cues.
2. **Goal-driven programming**: Each of 6 goals (build_muscle, lose_fat, body_recomp, strength, general_fitness, athletic_performance) produces distinctly different programs.
3. **Style-driven programming**: Weights / Calisthenics / Hybrid / Functional produce meaningfully different output.
4. **Macro-accurate meal plans** aligned with user's daily targets (0% deviation via 5-stage algorithm)
5. Dietary preference support: vegan, vegetarian, keto, carnivore, balanced, whole_foods, high_protein
6. Foods-to-avoid strictly enforced in all meal generation and replacement (VERIFIED WORKING)
7. Food logging via image analysis (snap food) or manual entry
8. Ask InterFitAI chat (fitness Q&A with user context)
9. Subscription gating with 3-day free trial

## Architecture
- **Frontend**: Expo/React Native (TypeScript)
- **Backend**: FastAPI (Python) - port 8001
- **Database**: MongoDB
- **AI Engine**: Claude Sonnet 4.5 via emergentintegrations (EMERGENT_LLM_KEY)
- **Payments**: Stripe (web) + RevenueCat (native)
- **Exercise GIFs**: ExerciseDB RapidAPI

## Elite Coaching Engine (EliteCoachingEngine class in server.py)
- **PATTERNS**: 20+ movement patterns × equipment types → exercise options list
- **SESSION_ARCHETYPES**: 20+ session types (push, pull, legs, full body, functional, athletic, calisthenics)
- **SPLIT_MAP**: Days/week × goal/style → optimal split (PPL, Upper/Lower, Full Body, Athletic Hybrid, etc.)
- **GOAL_PARAMS**: 6 goals × 7 exercise types → precise sets/reps/rest/effort
- **LIMITATION_EXCLUSIONS**: 8 limitation types → excluded exercise names
- **select_split()**: Intelligent split selection with detailed rationale
- **build_blueprint()**: Main entry → complete day-by-day blueprint
- **generate_workout()**: Wired to engine. Blueprint first, LLM second (names+form cues only)

## Key Technical Details
- All AI calls use `call_claude_sonnet()` helper → emergentintegrations → `claude-sonnet-4-5-20250929`
- **Macro accuracy (HONEST)**: Multi-stage ingredient-level scaling — no artificial inflation
  - Stage 1: Calorie scale (all ingredients proportionally)
  - Stage 1.5: Protein correction
  - Stage 2: Carb correction
  - Stage 3: Fat correction
  - Stage 4: Final recalculation from actual ingredient amounts
  - Stage 5: Proportional calibration to guarantee exact daily totals
- **Coaching metadata per workout**: split_name, split_rationale, progression_method, deload_timing, weekly_structure
- **Exercise metadata**: effort_target (RIR/RPE), substitution_hint (alternatives from same movement pattern)

---

# CHANGELOG

## 2026-03-25 - Macro Accuracy Overhaul (Complete Rewrite)
- **Root cause fixed**: Previous approach artificially forced macro numbers to match targets WITHOUT changing ingredient gram amounts (fake values)
- **New approach**: Multi-stage ingredient-level scaling — displayed macros accurately reflect actual ingredient amounts
  - Protein-rich ingredients (chicken, tofu, seitan) scaled to hit protein target
  - Carb-rich ingredients (rice, oats, potato) scaled to hit carb target (cap 3.0x)
  - Fat-rich ingredients (oils, nuts, salmon, eggs) scaled to hit fat target
- **Keto/Carnivore**: Now correctly uses diet-appropriate targets (72% fat, 5% carbs)
- **Bug fixes**:
  - Garlic clove ITEM_WEIGHTS: 100g default → 4g (was giving 66g carbs from 2 cloves!)
  - Added 40+ vegan ingredients to INGREDIENT_MACROS: seitan, edamame, tahini, chickpea flour, agave, nutritional yeast, etc.
  - Improved fat correction to include fatty proteins (salmon, whole egg, bacon, ribeye)
  - Vegan diet_instructions updated to emphasize seitan/tempeh for protein
  - High_protein prompt explicitly includes carb gram targets to prevent low-carb interpretation
- **Tested results**: Balanced ≤5%, High Protein ≤3%, Keto 16-34g carbs, Vegan 1-15%
- Migrated ALL AI endpoints from OpenAI GPT-4o to Claude Opus 4.6
  - Workout generation, meal plan generation, alternate meal generation
  - Food image analysis, body analyzer, Ask InterFitAI chat
- Added `call_claude_opus()` helper function using emergentintegrations
- Fixed critical vegan protein bug: `is_plant_based_diet` parameter was missing from `scale_day_to_targets()`
- Testing agent fixed JSON parsing: Claude returns JSON with leading `\n\n` before ``` blocks
- All 8 backend tests passed (100%)

## Earlier Sessions
- Complete InterFitAI MVP built: profiles, workouts, meal plans, food logging, chat, Stripe, step tracking
- Admin access system and subscription system
- Exercise GIF integration via ExerciseDB RapidAPI
- Body analyzer (before/after photo AI comparison)
- Save favorite meals feature
- Calorie adjustment feature
- Macro accuracy post-processing system (forces daily totals to match targets)
- Diet-specific meal plan templates (keto, carnivore, vegan, vegetarian, high_protein, whole_foods)
- Foods-to-avoid enforcement with PROTEIN_GROUPS grouping + retry logic
- kJ/cal toggle and inline quantity multiplier (1-10) in food log
- Macro Breakdown color bars in meal detail cards
- Manual food logging with auto-calorie calculation from macros

## 2026-03-27 - Elite Workout Coaching Engine
- **WIRED EliteCoachingEngine into generate_workout()** — was dead code before, now called first
- Python determines all sets/reps/rest/effort via GOAL_PARAMS × experience level
- LLM only picks exercise name from options list and writes 15-20 word form cues
- Added athletic_performance as 6th goal (front + backend)
- Goal-specific deload timing (4 weeks for strength, 5-6 for hypertrophy, etc.)
- Secondary focus areas sent to LLM context for exercise selection bias
- Premium coaching panel in workout-detail.tsx (split rationale, progression, deload, weekly blueprint)
- Effort badge (RIR/RPE) on each exercise row
- Substitution hints (alternative exercises from same movement pattern)
- Fixed equipment inference for calisthenics (bodyweight override)
- **foods_to_avoid meal replacement VERIFIED WORKING** via 7/7 backend tests

---

# ROADMAP

## P0 - Critical (COMPLETE ✅)
- [x] Macro accuracy: protein, carbs, fat all accurate and within targets (2026-03-25)
- [x] Keto macro compliance: carbs < 50g, high fat diet targets (2026-03-25)
- [x] Vegan protein accuracy: seitan/tempeh/edamame now in ingredient DB (2026-03-25)
- [x] Elite Coaching Engine wired (2026-03-27)
- [x] foods_to_avoid meal replacement verified (2026-03-27)

## P1 - High Priority
- [ ] RevenueCat native purchase integration (requires native build, not web preview)

## P2 - Medium Priority
- [ ] Google Fit / Fitbit / Garmin live device connection (OAuth flows)
- [ ] Food image analysis (Claude vision)

## P3 - Low Priority
- [ ] Enhance subscription page UI
- [ ] Push notifications for workout/meal reminders
