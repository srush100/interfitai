# InterFitAI - Product Requirements Document

## Original Problem Statement
Build InterFitAI - a comprehensive AI fitness app with:
- User profile & macro calculation
- AI workout generation
- AI meal plan generation
- Food tracking with image recognition
- Ask InterFitAI chat
- Subscription payments with Stripe
- Step tracking
- Device connections (Apple Health, Garmin, Fitbit, Google Fit)

## User Personas
- Primary: Health-conscious individuals wanting personalized AI fitness plans
- Admin: sebastianrush5@gmail.com / srush@interfitai.com (full free access)

## Core Requirements
1. Macro-accurate meal plans aligned with user's daily targets
2. Dietary preference support: vegan, vegetarian, keto, carnivore, balanced, whole_foods, high_protein
3. Foods-to-avoid strictly enforced in all meal generation and replacement
4. AI workout generation with exercise GIFs
5. Food logging via image analysis (snap food) or manual entry
6. Ask InterFitAI chat (fitness Q&A with user context)
7. Subscription gating with 3-day free trial

## Architecture
- **Frontend**: Expo/React Native (TypeScript)
- **Backend**: FastAPI (Python) - port 8001
- **Database**: MongoDB
- **AI Engine**: Claude Opus 4.6 via emergentintegrations (EMERGENT_LLM_KEY)
- **Payments**: Stripe (web) + RevenueCat (native)
- **Exercise GIFs**: ExerciseDB RapidAPI

## Key Technical Details
- All AI calls use `call_claude_opus()` helper → emergentintegrations → `claude-opus-4-6`
- Meal templates (VEGAN_TEMPLATES, KETO_TEMPLATES etc.) use pre-calculated macros with mathematical scaling
- Vegan/vegetarian plans bypass artificial macro inflation (`is_plant_based_diet` flag)
- Low-carb plans (keto/carnivore) bypass artificial macro inflation (`is_low_carb_diet` flag)
- Alternate meal generation uses PROTEIN_GROUPS + retry loop + post-validation for foods_to_avoid

---

# CHANGELOG

## 2026-03-24 - Claude Opus 4.6 Migration
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

---

# ROADMAP

## P0 - Critical (must fix)
- [ ] Verify vegan template protein values are realistic (193g at 2273cal may be too high - uses seitan/pea protein powder)
- [ ] Keto meal plan accuracy validation (net carbs ≤ 25g/day)

## P1 - High Priority
- [ ] Alternate meal foods_to_avoid: tested and PASSING with Claude Opus 4.6
- [ ] RevenueCat native purchase integration (requires native build, not web preview)

## P2 - Medium Priority
- [ ] Google Fit / Fitbit / Garmin live device connection (OAuth flows)
- [ ] Food image analysis (Claude Opus 4.6 vision - previously broken with OpenAI)

## P3 - Low Priority
- [ ] Enhance subscription page UI
- [ ] Push notifications for workout/meal reminders
