"""Every food the instructions mention must be in the ingredient list."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from meal_templates import TEMPLATES_BY_STYLE  # noqa: E402
from nutrition_engine import (FoodRules, instruction_mentions, items_from_raw, make_draft,  # noqa: E402
                              optimise_portions, reconcile_instructions, template_draft, unlisted_mentions)


def _draft(instr, foods, meal_type="breakfast"):
    return make_draft("Test meal", meal_type, items_from_raw([{"food": f, "grams": g} for f, g in foods])[0], instr)


def test_unlisted_butter_is_added_with_small_default():
    d = _draft("Heat butter in a skillet and cook the pancakes.", [("banana", 125), ("almond flour", 12), ("eggs", 116)])
    assert reconcile_instructions(d, FoodRules([], [], "balanced")) == []
    butter = [it for it in d["items"] if it["key"] == "butter"]
    assert butter and butter[0]["grams"] == 5 and butter[0]["keep"]


def test_generic_oil_and_cream_get_an_allowed_fat():
    d = _draft("Drizzle with oil. Stir in cream.", [("chicken breast", 150)], "dinner")
    assert reconcile_instructions(d, FoodRules([], [], "balanced")) == []
    assert {"olive oil", "heavy cream"} <= {it["key"] for it in d["items"]}
    v = _draft("Stir in cream.", [("lentils", 150)], "dinner")
    assert reconcile_instructions(v, FoodRules([], [], "vegan")) == []
    assert "coconut cream" in {it["key"] for it in v["items"]}


def test_banned_fat_or_other_food_means_regenerate():
    d = _draft("Heat butter in a pan.", [("banana", 100)])
    assert reconcile_instructions(d, FoodRules([], [], "vegan"))          # butter not allowed → problem
    assert reconcile_instructions(_draft("Top with cheese.", [("eggs", 116)]), FoodRules([], [], "balanced"))
    assert reconcile_instructions(_draft("Fry in olive oil.", [("salmon", 150)], "dinner"), FoodRules([], [], "carnivore"))


def test_seasonings_negations_and_listed_foods_are_fine():
    items = items_from_raw([{"food": "chicken breast", "grams": 150}, {"food": "red bell pepper", "grams": 80},
                            {"food": "olive oil", "grams": 5}])[0]
    assert unlisted_mentions("Season with salt and pepper, sauté peppers in olive oil, add chicken.", items) == []
    assert instruction_mentions("Use a non-stick pan. Blend until creamy. Oil-free, no butter.") == []
    assert instruction_mentions("Toast the oats; wrap tightly; add extra protein.") == ["oats"]


def test_mentioned_foods_are_never_tuned_away():
    d = _draft("Cook in butter, serve with banana.", [("banana", 120), ("eggs", 116), ("butter", 5)])
    reconcile_instructions(d, FoodRules([], [], "balanced"))
    optimise_portions([d], {"calories": 200, "protein": 15, "carbs": 25, "fats": 2}, widen=True,
                      shares={"breakfast": 1.0})
    assert "butter" in {it["key"] for it in d["items"]}


def test_all_templates_list_every_food_they_mention():
    bad = []
    for style, days in TEMPLATES_BY_STYLE.items():
        for day in days.values():
            for mt, tpl in day.items():
                d = template_draft(mt, tpl)
                if unlisted_mentions(d["instructions"], d["items"]):
                    bad.append((style, tpl["name"], unlisted_mentions(d["instructions"], d["items"])))
    assert bad == []
