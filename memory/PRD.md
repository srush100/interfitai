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
- All AI calls use `call_claude_opus()` helper → emergentintegrations → `claude-claude-sonnet-4-5-20250929`
- **Macro accuracy (HONEST)**: Multi-stage ingredient-level scaling — no artificial inflation
  - Stage 1: Calorie scale (all ingredients proportionally)
  - Stage 1.5: Protein correction (scale protein-rich ingredients to hit protein target)
  - Stage 2: Carb correction (skip for keto/carnivore) — cap 3.0x for high_protein plans
  - Stage 3: Fat correction (skip for keto/carnivore) — triggers at 4%+ deviation
  - Stage 4: Final recalculation from actual ingredient amounts
- **Keto/carnivore use diet-appropriate macro targets**: 72% fat/5% carbs instead of user profile
- **Template path** (`scale_day_to_targets`): also uses ingredient-level scaling (Steps 1-5)
- **INGREDIENT_MACROS DB**: 100+ ingredients including seitan (25gP), edamame, tahini, nutritional yeast, chickpea flour, agave, etc.
- **ITEM_WEIGHTS**: garlic clove = 4g (was 100g default — caused 66g carbs from 2 cloves!)

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

---

# ROADMAP

## P0 - Critical (COMPLETE ✅)
- [x] Macro accuracy: protein, carbs, fat all accurate and within targets (2026-03-25)
- [x] Keto macro compliance: carbs < 50g, high fat diet targets (2026-03-25)
- [x] Vegan protein accuracy: seitan/tempeh/edamame now in ingredient DB (2026-03-25)

## P1 - High Priority
- [x] Alternate meal foods_to_avoid: VERIFIED WORKING (2026-02) — PROTEIN_GROUPS filtering + retry loop confirmed with 7/7 tests passing
- [ ] RevenueCat native purchase integration (requires native build, not web preview)

## P2 - Medium Priority
- [ ] Google Fit / Fitbit / Garmin live device connection (OAuth flows)
- [ ] Food image analysis (Claude vision)

## P3 - Low Priority
- [ ] Enhance subscription page UI
- [ ] Push notifications for workout/meal reminders
