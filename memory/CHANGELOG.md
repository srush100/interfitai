
## 2026-04-13 — Workout Audit Round 3: 5 Fixes + Verification
- **Fix 1 (Pike Push-Up GIF)**: Corrected ID 0473→2921 (was mapping to "Hanging Pike" abs move, now correctly maps to pike push-up bodyweight vertical press)
- **Fix 2 (Australian Pull-Up cleanup)**: Removed from `vertical_pull` bodyweight list (wrong pattern), removed from `horizontal_pull` bodyweight list (kept only `Inverted Row`); GIF alias kept in CACHED_EXERCISE_GIFS with legacy comment
- **Fix 3 (Cable Glute Kickback rename)**: Renamed 5 occurrences of "Cable Kickback" → "Cable Glute Kickback" in glute pattern block; added `"cable glute kickback": "0860"` GIF alias
- **Fix 4 (Upper/Lower 6-day balance)**: Day 5 changed `upper_push_volume` → `upper_full` giving true 3U/3L split with 2× push, 2× pull frequency (not 3× push, 1× pull)
- **Assault bike**: Confirmed intact (NOT removed as incorrectly suggested in prior prompt)
- **Testing**: 16/16 pytest tests pass; all 4 verification scenarios confirmed working


- **Fix 1 (PPL 5-day)**: SPLIT_MAP PPL at 5 days now `push → pull → legs → upper_full → lower_full` (each muscle group 2x/week)
- **Fix 2 (Bro Split 3-day)**: Added `bro_chest_shoulders` archetype (chest + shoulders + OHP). bro_split[3] now uses it so shoulders get direct work
- **Fix 3 (Full Body 4-6 day)**: Added `full_body_heavy_b` (deadlift/OHP/pull-up focus) and `full_body_moderate_b` (squat/row/incline); no more repeating Day 1 on Day 4
- **Fix 4 (Calisthenics 4-6 day)**: Added `calisthenics_skill` (planche prep, L-sit, one-arm progressions) and `calisthenics_conditioning` archetypes; 4-day split no longer just alternates upper/lower
- **Fix 5 (Functional 4-6 day)**: Added `functional_power_endurance` archetype (box jumps, loaded carries, HIIT intervals); 3-pillar coverage
- **Fix 6 (Exercise Deduplication)**: Added `used_primary_options` set in `build_blueprint()` — each day's first-choice exercise is tracked and rotated to back of list on subsequent days
- **Fix 7 (Focus Area Strength)**: Boost now applies to up to 2 matching slots (was 1), includes `secondary_compound` slots, caps raised to 6/5 sets
- **Bonus Fix**: Added `model_validator` to `WorkoutGenerateRequest` so legacy field names (`split_type`, `style`, `experience_level`, `limitations`) are automatically mapped to internal names
- **Testing**: 26/26 engine logic tests pass; all 4 user-specified test cases verified correct


- **Live search with 400ms debounce**: Removed Search button; search triggers automatically as user types with ActivityIndicator spinner inside search bar
- **Custom serving size input**: Expanded card now shows gram/ml TextInput below stepper; macros recalculate proportionally using per-100g extraction from food name
- **AI fallback empty state**: When 0 results found, shows icon + message + "Search with AI" (calls new `/api/food/ai-search` Claude Haiku endpoint) + "Add Manually" shortcut to Manual tab; AI results show "AI Estimate" teal badge
- **Skeleton loading & suggestion chips**: 3 animated pulsing skeleton cards while searching; 4 suggestion chips before first search (Chicken breast, Oats, McDonald's Big Mac, Greek yogurt)
- **Backend**: Added `GET /api/food/ai-search?query=` endpoint (Claude Haiku, returns normalized JSON macros)
- **Fixed**: Pre-existing `manualSection` style missing in StyleSheet (was causing TypeScript error)
- **Fixed (this session)**: Backend IndentationError at line 2403 in server.py (`_pattern_to_secondary` block)
- **Added**: Time-estimation validation loop in EliteCoachingEngine (trims sessions exceeding target_minutes × 1.15)

