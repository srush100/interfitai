"""Backend tests for whole-unit (eggs/bread/etc.) + raw/dry display changes.

Covers:
 - POST /api/mealplans/generate for balanced + paleo for sdk57tester
 - every egg ingredient rendered as 'N large egg(s) (N*58g)'
 - bread/toast/wraps/bagels/english muffin/pita/naan/rice cakes in whole units
 - meal macros == sum of calculate_ingredient_macros per ingredient
 - each day on_target (within 5% of targets)
 - POST /api/mealplan/alternate (swap_preference=similar) keeps whole units & on_target
"""
import os
import re
import sys
import time

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
sys.path.insert(0, "/app/backend")
from nutrition_engine import UNIT_FOODS, calculate_ingredient_macros, resolve_food  # noqa: E402

BASE = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ["EXPO_BACKEND_URL"]).rstrip("/") + "/api"
USER_ID = "2663e0c4-d8b9-4feb-b42a-8b055631ea25"
MONGO = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

EGG_RE = re.compile(r"^(\d+)\s+(large eggs?|large egg)\s+\((\d+)g\)$", re.I)
UNIT_RE = re.compile(r"^(\d+)\s+(?:slices?\s+)?(.+?)\s+\((\d+(?:\.\d+)?)g\)$", re.I)
GRAM_RE = re.compile(r"^(\d+(?:\.\d+)?)g\s+(.+)$")


def _clear_quota():
    MONGO.meal_generation_events.delete_many({"user_id": USER_ID})


def _generate(style: str):
    _clear_quota()
    r = requests.post(f"{BASE}/mealplans/generate",
                      json={"user_id": USER_ID, "food_preferences": style,
                            "allergies": [], "supplements": []},
                      timeout=300)
    assert r.status_code == 200, f"generate {style} -> {r.status_code}: {r.text[:400]}"
    plan_id = r.json()["id"]
    g = requests.get(f"{BASE}/mealplan/{plan_id}", timeout=60)
    assert g.status_code == 200
    return g.json()


def _check_whole_units(ing: str) -> bool:
    """If ingredient resolves to a UNIT_FOODS entry, it MUST be in whole-unit form."""
    gm = GRAM_RE.match(ing)
    um = UNIT_RE.match(ing)
    if gm:
        label = gm.group(2)
        key = resolve_food(label)
        if key in UNIT_FOODS:
            return False, f"'{ing}' uses grams for whole-unit food (key={key})"
        return True, None
    if um:
        n = int(um.group(1))
        label = um.group(2)
        shown_g = float(um.group(3))
        key = resolve_food(label)
        if key not in UNIT_FOODS:
            return True, None  # non-unit items with grams in parens is unusual but allowed
        per = UNIT_FOODS[key][0]
        if abs(shown_g - n * per) > 0.5:
            return False, f"'{ing}' grams ({shown_g}) != {n}*{per}"
        return True, None
    return True, None


def _check_eggs(ing: str):
    """If the ingredient refers to eggs, it must be the 'N large egg(s) (N*58g)' form."""
    if "egg" not in ing.lower():
        return True, None
    if re.search(r"\begg white", ing, re.I):
        return True, None  # egg whites allowed as grams
    if GRAM_RE.match(ing):
        key = resolve_food(GRAM_RE.match(ing).group(2))
        if key in ("egg", "eggs", "whole eggs", "large eggs"):
            return False, f"'{ing}' uses grams for eggs"
    m = EGG_RE.match(ing)
    if m:
        n = int(m.group(1))
        g = int(m.group(3))
        if g != n * 58:
            return False, f"'{ing}' egg grams != n*58"
    return True, None


def _macro_sum(ingredients):
    tot = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fats": 0.0}
    for ing in ingredients:
        m = calculate_ingredient_macros(ing)
        assert m is not None, f"could not parse ingredient '{ing}'"
        for k in tot:
            tot[k] += m[k]
    return tot


def _assert_plan_valid(plan):
    for day in plan["meal_days"]:
        for meal in day["meals"]:
            for ing in meal["ingredients"]:
                ok, msg = _check_eggs(ing)
                assert ok, msg
                ok, msg = _check_whole_units(ing)
                assert ok, msg
            calc = _macro_sum(meal["ingredients"])
            assert calc["calories"] == meal["calories"], (
                f"{meal['name']}: meal calories {meal['calories']} != sum {calc['calories']}")
            for k in ("protein", "carbs", "fats"):
                assert abs(calc[k] - meal[k]) <= 0.11, (
                    f"{meal['name']}: {k} sum {calc[k]} != meal {meal[k]}")
        # within 5% of targets (2g floor on macros)
        targets = {"calories": plan["target_calories"], "protein": plan["target_protein"],
                   "carbs": plan["target_carbs"], "fats": plan["target_fats"]}
        for k, tv in targets.items():
            key = "total_" + ("calories" if k == "calories" else k)
            actual = day[key]
            tol = max(0.05 * tv, 0 if k == "calories" else 2.0)
            assert abs(actual - tv) <= tol + 1e-9, (
                f"{day['day']} {k} {actual} not within 5% of {tv}")
        assert day["on_target"] is True, f"{day['day']} on_target=False"


@pytest.fixture(scope="module")
def balanced_plan():
    return _generate("balanced")


@pytest.fixture(scope="module")
def paleo_plan():
    return _generate("paleo")


class TestWholeUnitAndRawDry:
    def test_balanced_plan_whole_units_and_accuracy(self, balanced_plan):
        _assert_plan_valid(balanced_plan)

    def test_paleo_plan_whole_units_and_accuracy(self, paleo_plan):
        _assert_plan_valid(paleo_plan)

    def test_balanced_has_at_least_one_whole_unit_food(self, balanced_plan):
        """Sanity: given eggs/bread etc are preferred, at least one unit-food
        should appear in the plan with correct N-unit format."""
        hits = []
        for day in balanced_plan["meal_days"]:
            for meal in day["meals"]:
                for ing in meal["ingredients"]:
                    um = UNIT_RE.match(ing)
                    if um and resolve_food(um.group(2)) in UNIT_FOODS:
                        hits.append(ing)
        assert hits, "expected at least one whole-unit food in balanced plan"

    def test_swap_breakfast_similar_stays_valid(self, balanced_plan):
        plan_id = balanced_plan["id"]
        # locate first breakfast
        day0 = balanced_plan["meal_days"][0]
        idx = next((i for i, m in enumerate(day0["meals"]) if m["meal_type"] == "breakfast"), 0)
        r = requests.post(f"{BASE}/mealplan/alternate",
                          json={"user_id": USER_ID, "meal_plan_id": plan_id,
                                "day_index": 0, "meal_index": idx,
                                "swap_preference": "similar"},
                          timeout=180)
        assert r.status_code == 200, f"alternate -> {r.status_code}: {r.text[:400]}"
        time.sleep(1)
        plan2 = requests.get(f"{BASE}/mealplan/{plan_id}", timeout=60).json()
        new_meal = plan2["meal_days"][0]["meals"][idx]
        for ing in new_meal["ingredients"]:
            ok, msg = _check_eggs(ing);           assert ok, msg
            ok, msg = _check_whole_units(ing);    assert ok, msg
        calc = _macro_sum(new_meal["ingredients"])
        assert calc["calories"] == new_meal["calories"]
        # day stays on target
        day = plan2["meal_days"][0]
        targets = {"calories": plan2["target_calories"], "protein": plan2["target_protein"],
                   "carbs": plan2["target_carbs"], "fats": plan2["target_fats"]}
        for k, tv in targets.items():
            key = "total_" + ("calories" if k == "calories" else k)
            tol = max(0.05 * tv, 0 if k == "calories" else 2.0)
            assert abs(day[key] - tv) <= tol + 1e-9, f"after swap {k} {day[key]} not within 5% of {tv}"
        assert day["on_target"] is True


class TestReferencePlan:
    """Reference plan 19ee0e84 is new-style — must obey whole-unit rules too."""

    REF_PLAN_ID = "19ee0e84-c48d-48ab-b661-5c0e06b0d0d1"

    def test_reference_plan_structure(self):
        r = requests.get(f"{BASE}/mealplan/{self.REF_PLAN_ID}", timeout=60)
        if r.status_code == 404:
            pytest.skip("reference plan not present in this fork")
        assert r.status_code == 200
        plan = r.json()
        _assert_plan_valid(plan)
        # Spot-check Day 1 breakfast has eggs rendered as whole units
        d0 = plan["meal_days"][0]
        all_ings = [i for m in d0["meals"] for i in m["ingredients"]]
        egg_lines = [i for i in all_ings if re.search(r"\begg", i, re.I) and "white" not in i.lower()]
        for ing in egg_lines:
            assert EGG_RE.match(ing), f"egg ingredient not whole-unit form: '{ing}'"
