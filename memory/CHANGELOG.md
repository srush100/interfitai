
## 2026-04-09 — Food Search Enhancement
- **Live search with 400ms debounce**: Removed Search button; search triggers automatically as user types with ActivityIndicator spinner inside search bar
- **Custom serving size input**: Expanded card now shows gram/ml TextInput below stepper; macros recalculate proportionally using per-100g extraction from food name
- **AI fallback empty state**: When 0 results found, shows icon + message + "Search with AI" (calls new `/api/food/ai-search` Claude Haiku endpoint) + "Add Manually" shortcut to Manual tab; AI results show "AI Estimate" teal badge
- **Skeleton loading & suggestion chips**: 3 animated pulsing skeleton cards while searching; 4 suggestion chips before first search (Chicken breast, Oats, McDonald's Big Mac, Greek yogurt)
- **Backend**: Added `GET /api/food/ai-search?query=` endpoint (Claude Haiku, returns normalized JSON macros)
- **Fixed**: Pre-existing `manualSection` style missing in StyleSheet (was causing TypeScript error)
- **Fixed (this session)**: Backend IndentationError at line 2403 in server.py (`_pattern_to_secondary` block)
- **Added**: Time-estimation validation loop in EliteCoachingEngine (trims sessions exceeding target_minutes × 1.15)

