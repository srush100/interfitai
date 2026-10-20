"""
Review request regression tests:
 - Food search (local + USDA, no FatSecret, no 500s)
 - Food logging CRUD + daily summary totals
 - Photo scan (/api/food/analyze)
 - AI search (/api/food/ai-search)
 - Meal plan /generate macro-vs-ingredient recomputation (balanced + carnivore + allergy)
 - Meal plan /alternate swap keeps day within 5%, respects diet/allergy
"""

import os
import re
import base64
import time
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://nutrition-debug-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
USER_ID = "2663e0c4-d8b9-4feb-b42a-8b055631ea25"
TIMEOUT = 60

# Reuse backend internals for authoritative macro recomputation
import sys
sys.path.insert(0, "/app/backend")
from nutrition_engine import resolve_food, FoodRules  # type: ignore
from food_database import INGREDIENT_MACROS  # type: ignore


# --------- helpers ---------

def _parse_ingredient_line(s):
    """'220g Whole wheat bread' -> (grams=220.0, label='Whole wheat bread')"""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*g\s+(.+?)\s*$", s)
    if not m:
        return None
    return float(m.group(1)), m.group(2).strip()


def _recompute_meal(meal):
    """Return (kcal, p, c, f) summed from the meal's ingredient strings."""
    tot_k = tot_p = tot_c = tot_f = 0.0
    for ing in meal.get("ingredients", []):
        parsed = _parse_ingredient_line(ing)
        if not parsed:
            continue
        grams, label = parsed
        key = resolve_food(label)
        if not key or key not in INGREDIENT_MACROS:
            # Unknown ingredient -> macros can't be checked; this is a hard failure
            pytest.fail(f"Unresolved ingredient '{label}' (key={key}) in meal {meal.get('name')}")
        per100 = INGREDIENT_MACROS[key]  # (cal, p, c, f) tuple
        factor = grams / 100.0
        tot_k += round(per100[0] * factor)
        tot_p += round(per100[1] * factor, 1)
        tot_c += round(per100[2] * factor, 1)
        tot_f += round(per100[3] * factor, 1)
    return (int(round(tot_k)), round(tot_p, 1), round(tot_c, 1), round(tot_f, 1))


def _within_5pct(actual, target, floor=2.0):
    if target <= 0:
        return abs(actual - target) <= floor
    tol = max(target * 0.05, floor)
    return abs(actual - target) <= tol


# --------- fixtures ---------

@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ============ FOOD SEARCH ============

class TestFoodSearch:
    @pytest.mark.parametrize("q", ["chicken breast", "banana", "greek yogurt"])
    def test_food_search(self, api, q):
        r = api.get(f"{API}/food/search", params={"query": q, "user_id": USER_ID}, timeout=TIMEOUT)
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:300]}"
        data = r.json()
        results = data if isinstance(data, list) else (data.get("results") or data.get("foods") or [])
        assert len(results) > 0, f"no results for {q}"
        # No FatSecret references
        assert "fatsecret" not in r.text.lower(), "FatSecret reference should be removed"
        sources = {str(x.get("source", "")).lower() for x in results if isinstance(x, dict)}
        assert "fatsecret" not in sources
        print(f"  '{q}' -> {len(results)} results, sources={sources}")


# ============ FOOD LOG CRUD + DAILY SUMMARY ============

class TestFoodLog:
    log_ids = []

    def test_create_log_and_persist(self, api):
        from datetime import date
        payload = {
            "user_id": USER_ID,
            "food_name": "TEST_banana",
            "serving_size": "100g",
            "calories": 89,
            "protein": 1.1,
            "carbs": 23.0,
            "fats": 0.3,
            "meal_type": "snack",
            "logged_date": date.today().isoformat(),
        }
        r = api.post(f"{API}/food/log", json=payload, timeout=TIMEOUT)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:300]}"
        body = r.json()
        log_id = body.get("id") or body.get("log_id") or (body.get("log") or {}).get("id")
        assert log_id, f"missing id in response: {body}"
        TestFoodLog.log_ids.append(log_id)

        # Verify via GET /logs
        r2 = api.get(f"{API}/food/logs/{USER_ID}", timeout=TIMEOUT)
        assert r2.status_code == 200
        rj = r2.json()
        logs = rj if isinstance(rj, list) else rj.get("logs", [])
        assert any((l.get("id") == log_id) for l in logs), "created log not found in list"

    def test_daily_summary_totals(self, api):
        from datetime import date
        today = date.today().isoformat()
        r = api.get(f"{API}/food/daily-summary/{USER_ID}/{today}", timeout=TIMEOUT)
        assert r.status_code == 200, r.text[:300]
        s = r.json()
        totals = s.get("consumed") or s.get("totals") or s
        assert float(totals.get("calories", 0)) >= 89, f"calories too low: {totals}"
        assert float(totals.get("protein", 0)) >= 1.0

    def test_delete_log(self, api):
        if not TestFoodLog.log_ids:
            pytest.skip("no log to delete")
        lid = TestFoodLog.log_ids[0]
        r = api.delete(f"{API}/food/log/{lid}", timeout=TIMEOUT)
        assert r.status_code in (200, 204), f"{r.status_code} {r.text[:300]}"
        r2 = api.get(f"{API}/food/logs/{USER_ID}", timeout=TIMEOUT)
        rj = r2.json()
        logs = rj if isinstance(rj, list) else rj.get("logs", [])
        assert not any((l.get("id") == lid) for l in logs), "deleted log still present"


# ============ PHOTO SCAN ============

class TestPhotoScan:
    def _tiny_jpeg_b64(self):
        # Valid 300x300 solid-color JPEG via PIL
        from PIL import Image
        import io, base64
        img = Image.new("RGB", (300, 300), (200, 150, 100))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return base64.b64encode(buf.getvalue()).decode()

    def test_food_analyze_non_food_returns_422(self, api):
        """Iter51 fix: non-food/unreadable image must return 422 no_food_detected
        (or label_unreadable), never 500."""
        payload = {"user_id": USER_ID, "image_base64": self._tiny_jpeg_b64()}
        r = api.post(f"{API}/food/analyze", json=payload, timeout=120)
        assert r.status_code == 422, (
            f"expected 422 no_food_detected, got {r.status_code}: {r.text[:300]}"
        )
        body = r.json()
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict):
            assert detail.get("error") in ("no_food_detected", "label_unreadable"), (
                f"wrong detail.error: {detail}"
            )
        else:
            # Fallback: accept any 422 with error-ish detail string
            assert detail is not None, f"no detail on 422: {body}"

    def test_ai_search(self, api):
        r = api.get(f"{API}/food/ai-search", params={"query": "oatmeal with berries", "user_id": USER_ID}, timeout=120)
        assert r.status_code in (200, 404), f"{r.status_code} {r.text[:300]}"
        if r.status_code == 200:
            d = r.json()
            assert isinstance(d, (dict, list)), f"bad body: {d}"


# ============ MEAL PLAN GENERATE + MACROS ============

class TestMealPlanGenerate:
    plan_cache = {}

    def _generate(self, api, style, allergies=None):
        payload = {
            "user_id": USER_ID,
            "eating_style": style,
            "duration_days": 3,
            "meals_per_day": 4,
            "allergies": allergies or [],
            "goal": "muscle_building",
            "activity_level": "moderate",
        }
        r = api.post(f"{API}/mealplans/generate", json=payload, timeout=300)
        assert r.status_code == 200, f"{style}: {r.status_code} {r.text[:400]}"
        return r.json()

    def test_balanced_macros_and_targets(self, api):
        plan = self._generate(api, "balanced")
        TestMealPlanGenerate.plan_cache["balanced"] = plan
        self._verify_plan(plan, allergies=[])

    def test_carnivore_macros(self, api):
        plan = self._generate(api, "carnivore")
        TestMealPlanGenerate.plan_cache["carnivore"] = plan
        self._verify_plan(plan, allergies=[])

    def test_balanced_gluten_dairy_allergy(self, api):
        plan = self._generate(api, "balanced", allergies=["gluten", "dairy"])
        TestMealPlanGenerate.plan_cache["balanced_gd"] = plan
        self._verify_plan(plan, allergies=["gluten", "dairy"])

    def _verify_plan(self, plan, allergies):
        from nutrition_engine import FoodRules, items_from_raw  # type: ignore
        rules = FoodRules(allergies=allergies, eating_style=plan.get("eating_style") or "balanced")

        plan_doc = plan.get("meal_plan") or plan
        days = plan_doc.get("meal_days") or plan_doc.get("days") or []
        assert days, f"no days in plan: keys={list(plan_doc.keys())}"
        tgt_k = plan_doc.get("target_calories")
        tgt_p = plan_doc.get("target_protein")
        tgt_c = plan_doc.get("target_carbs")
        tgt_f = plan_doc.get("target_fats")
        assert tgt_k, f"missing targets in plan keys: {list(plan_doc.keys())}"

        # Dairy / gluten / nut / soy violation checks using backend's own
        # FoodRules — same engine that gates generation.
        for day in days:
            day_k = day_p = day_c = day_f = 0.0
            meals = day.get("meals", [])
            for m in meals:
                calc_k, calc_p, calc_c, calc_f = _recompute_meal(m)
                shown_k = int(round(float(m.get("calories", 0))))
                shown_p = round(float(m.get("protein", 0)), 1)
                shown_c = round(float(m.get("carbs", 0)), 1)
                shown_f = round(float(m.get("fats", 0)), 1)
                assert abs(calc_k - shown_k) <= 2, f"{m.get('name')}: calc {calc_k} vs shown {shown_k}"
                assert abs(calc_p - shown_p) <= 0.3, f"{m.get('name')}: P {calc_p} vs {shown_p}"
                assert abs(calc_c - shown_c) <= 0.3, f"{m.get('name')}: C {calc_c} vs {shown_c}"
                assert abs(calc_f - shown_f) <= 0.3, f"{m.get('name')}: F {calc_f} vs {shown_f}"
                day_k += shown_k; day_p += shown_p; day_c += shown_c; day_f += shown_f

                # Authoritative allergy/diet check via FoodRules
                items, _ = items_from_raw(m.get("ingredients", []))
                v = rules.violations(m.get("name", ""), items, m.get("instructions", ""))
                assert not v, f"rules violated for '{m.get('name')}' (allergies={allergies}): {v}"

            # Day totals within 5%
            assert _within_5pct(day_k, tgt_k), f"day kcal {day_k} vs target {tgt_k}"
            assert _within_5pct(day_p, tgt_p, floor=2.0), f"day P {day_p} vs {tgt_p}"
            assert _within_5pct(day_c, tgt_c, floor=2.0), f"day C {day_c} vs {tgt_c}"
            assert _within_5pct(day_f, tgt_f, floor=2.0), f"day F {day_f} vs {tgt_f}"


# ============ MEAL PLAN ALTERNATE (SWAP) ============

class TestMealPlanAlternate:
    def test_swap_similar_stays_on_target(self, api):
        plan = TestMealPlanGenerate.plan_cache.get("balanced")
        if not plan:
            pytest.skip("balanced plan not generated")
        plan_doc = plan.get("meal_plan") or plan
        plan_id = plan_doc.get("id") or plan_doc.get("plan_id")
        assert plan_id, f"no plan id: keys={list(plan_doc.keys())}"
        body = {
            "user_id": USER_ID,
            "meal_plan_id": plan_id,
            "day_index": 0,
            "meal_index": 3,
            "swap_preference": "similar",
        }
        r = api.post(f"{API}/mealplan/alternate", json=body, timeout=120)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        d = r.json()
        new_meal = d.get("alternate_meal") or d.get("meal") or d.get("new_meal")
        day_totals = d.get("day_totals") or d.get("day_total") or {}
        assert new_meal, f"no new_meal: {d}"
        # Macro match from ingredients
        calc = _recompute_meal(new_meal)
        shown = (int(round(float(new_meal.get("calories", 0)))),
                 round(float(new_meal.get("protein", 0)), 1),
                 round(float(new_meal.get("carbs", 0)), 1),
                 round(float(new_meal.get("fats", 0)), 1))
        assert abs(calc[0] - shown[0]) <= 2, f"swap meal kcal mismatch: calc={calc[0]} shown={shown[0]}"
        assert abs(calc[1] - shown[1]) <= 0.3
        # Day totals within 5% of plan targets
        tgt_k = plan_doc.get("target_calories")
        tgt_p = plan_doc.get("target_protein")
        tgt_c = plan_doc.get("target_carbs")
        tgt_f = plan_doc.get("target_fats")
        dk = float(day_totals.get("total_calories", day_totals.get("calories", 0)))
        dp = float(day_totals.get("total_protein", day_totals.get("protein", 0)))
        dc = float(day_totals.get("total_carbs", day_totals.get("carbs", 0)))
        df = float(day_totals.get("total_fats", day_totals.get("fats", 0)))
        assert _within_5pct(dk, tgt_k), f"day kcal {dk} vs {tgt_k}"
        assert _within_5pct(dp, tgt_p, floor=2.0), f"day P {dp} vs {tgt_p}"
        assert _within_5pct(dc, tgt_c, floor=2.0), f"day C {dc} vs {tgt_c}"
        assert _within_5pct(df, tgt_f, floor=2.0), f"day F {df} vs {tgt_f}"
        assert day_totals.get("on_target") in (True, None), f"on_target should be True: {day_totals}"
