"""Unit tests for the meal-plan nutrition engine (no AI, no network).

Covers every bug reported for meal-plan accuracy: unit parsing, name matching,
allergen coverage, template data and portion tuning."""
import sys

import pytest

sys.path.insert(0, "/app/backend")
from food_database import INGREDIENT_MACROS  # noqa: E402
from meal_templates import TEMPLATES_BY_STYLE  # noqa: E402
from nutrition_engine import (  # noqa: E402
    FoodRules, MACRO_KEYS, balance_day, build_day, calculate_ingredient_macros, finalize_meal,
    parse_ingredient, resolve_food, template_draft,
)

PARFAIT = ["200g Greek yogurt 0%", "50g granola", "120g mixed berries", "30g sliced almonds",
           "15ml honey", "1 medium banana 100g"]


def _sum(ings):
    tot = {k: 0.0 for k in MACRO_KEYS}
    for ing in ings:
        m = calculate_ingredient_macros(ing)
        assert m is not None, ing
        for k in MACRO_KEYS:
            tot[k] += m[k]
    return tot


# ── 2. Every ingredient in grams ────────────────────────────────────────────
@pytest.mark.parametrize("text,key,grams", [
    ("1 scoop whey protein", "whey protein", 30),
    ("2 rice cakes", "rice cakes", 18),
    ("1 cup spinach", "spinach", 30),
    ("1 cup cooked rice", "rice", 158),
    ("1 cup milk", "milk", 244),
    ("15ml honey", "honey", 21.3),
    ("1 medium banana 100g", "banana", 100),
    ("2 large eggs", "eggs", 116),
    ("2 tbsp olive oil", "olive oil", 27.25),
])
def test_units_become_real_grams(text, key, grams):
    label, g, k = parse_ingredient(text)
    assert k == key
    assert g == pytest.approx(grams, abs=0.1)


def test_unknown_count_item_is_rejected_not_100g():
    assert parse_ingredient("2 mystery bars") is None


# ── 5. Name matching ───────────────────────────────────────────────────────
@pytest.mark.parametrize("name,key", [
    ("eggplant", "eggplant"), ("strawberries", "strawberries"), ("fresh strawberries", "strawberries"),
    ("baked beans", "baked beans"), ("coconut milk", "coconut milk"), ("almond milk", "almond milk"),
    ("sliced almonds", "almonds"), ("greek yogurt 0%", "greek yogurt 0%"), ("oats", "oats"),
    ("cooked oats", "cooked oats"), ("extra lean beef mince (95/5)", "beef mince 95/5"),
    ("ground beef 80% lean", "beef mince 80/20"), ("red bell pepper", "red bell pepper"),
])
def test_resolve_food(name, key):
    assert resolve_food(name) == key


def test_oats_are_stored_dry():
    assert INGREDIENT_MACROS["oats"] == (389, 17, 66, 7)
    assert calculate_ingredient_macros("60g oats")["calories"] == 233


def test_user_parfait_example():
    tot = _sum(PARFAIT)
    assert tot["calories"] == pytest.approx(731, abs=10)
    assert tot["carbs"] == pytest.approx(99, abs=2)
    assert tot["fats"] == pytest.approx(26.5, abs=1)


# ── 1. Allergies ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("allergy,food", [
    ("gluten", f) for f in ["seitan", "soy sauce", "egg noodles", "bulgur", "orzo", "granola", "bagel", "naan", "rolled oats"]
] + [
    ("dairy", f) for f in ["parmesan cheese", "mozzarella", "ricotta", "halloumi", "paneer", "ghee", "kefir", "skyr"]
] + [
    ("lactose", f) for f in ["parmesan", "ricotta", "ghee", "kefir", "skyr"]
])
def test_allergen_synonyms_catch_common_foods(allergy, food):
    rules = FoodRules([allergy], [], "balanced")
    assert rules.violations("Meal", [{"label": food, "key": resolve_food(food) or food}]), (allergy, food)


@pytest.mark.parametrize("allergy,food", [
    ("dairy", "almond milk"), ("dairy", "peanut butter"), ("dairy", "coconut yogurt"),
    ("eggs", "eggplant"), ("gluten", "rice noodles"), ("gluten", "corn tortilla"),
])
def test_allergen_exemptions(allergy, food):
    assert FoodRules([allergy], [], "balanced").violations("Meal", [{"label": food, "key": resolve_food(food)}]) == []


def test_vegan_bell_pepper_is_not_pepperoni():
    assert FoodRules([], [], "vegan").violations("Stir fry", [{"label": "bell pepper", "key": "bell pepper"}]) == []


# ── 5. Templates: grams only, every food resolves ──────────────────────────
def test_templates_store_grams_only_and_resolve():
    for style, days in TEMPLATES_BY_STYLE.items():
        for day in days.values():
            for mt, tpl in day.items():
                for food, grams in tpl["ingredients"].items():
                    assert isinstance(grams, (int, float)), (style, food)
                    assert resolve_food(food), (style, food)


# ── 3. Honest numbers + within 5% ──────────────────────────────────────────
@pytest.mark.parametrize("style,targets", [
    ("balanced", {"calories": 2759, "protein": 144, "carbs": 372, "fats": 77}),
    ("vegan", {"calories": 2200, "protein": 150, "carbs": 250, "fats": 70}),
    ("keto", {"calories": 2759, "protein": 162, "carbs": 30, "fats": 221}),
    ("carnivore", {"calories": 2759, "protein": 201, "carbs": 5, "fats": 215}),
])
def test_template_days_honest_and_on_target(style, targets):
    rules = FoodRules([], [], style)
    for di in range(1, 4):
        drafts = [template_draft(mt, TEMPLATES_BY_STYLE[style][f"day{di}"][mt])
                  for mt in ("breakfast", "lunch", "dinner", "snack")]
        balance_day(drafts, targets, rules)
        meals = [finalize_meal(d, f"m{i}") for i, d in enumerate(drafts)]
        day = build_day(f"Day {di}", meals, targets)
        for m in meals:  # displayed numbers == sum of listed ingredients
            tot = _sum(m["ingredients"])
            assert m["calories"] == round(tot["calories"])
            for k in ("protein", "carbs", "fats"):
                assert m[k] == pytest.approx(tot[k], abs=0.05)
        assert day["on_target"], (style, di, day["total_calories"], day["total_protein"], day["total_carbs"], day["total_fats"])
