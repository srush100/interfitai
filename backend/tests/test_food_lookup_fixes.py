"""
Food lookup fixes (snap food "+ Add item" and food log references):
- loose matches never turn a food into a different food (duck → duck fat, curry → curry powder)
- onion varieties, nori / seaweed, tzatziki and other common foods are found
- raw meat / raw rice weights use raw values
- a photographed "15g onion powder" is fresh onion
- "coconut milk" says it's canned; the carton drink is separate
- foods missing from the database fall back to USDA's generic tables (grams required)
"""
import asyncio

import pytest

from nutrition_engine import build_plate, resolve_food, resolve_food_typed, snap_item_from_text


@pytest.mark.parametrize("typed, wrong", [
    ("duck", "duck fat"), ("curry", "curry powder"), ("oysters", "oyster sauce"), ("cake", "rice cake"),
    ("chilli", "chili flakes"), ("wine", "red wine vinegar"), ("cider", "apple cider vinegar"),
    ("chips", "dark chocolate chips"), ("cream", "ice cream"), ("water", "coconut water"),
])
def test_loose_match_never_changes_the_food(typed, wrong):
    assert resolve_food_typed(typed) != wrong


@pytest.mark.parametrize("typed", ["sauce", "curry", "cake", "chili con carne"])
def test_vague_or_unknown_foods_are_not_guessed(typed):
    assert resolve_food_typed(typed) is None


@pytest.mark.parametrize("typed, key", [
    ("white onion", "white onion"), ("brown onion", "brown onion"), ("nori", "nori"),
    ("seaweed", "seaweed"), ("tzatziki", "tzatziki"), ("chilli", "fresh chili"),
    ("raw chicken breast", "raw chicken breast"), ("dry rice", "dry rice"),
    ("sweet chilli sauce", "sweet chili sauce"), ("flaxseed", "flaxseed meal"),
])
def test_common_foods_are_found(typed, key):
    assert resolve_food_typed(typed) == key


def test_recipe_names_resolve_as_before():
    # the template foods must not move to a different database food
    assert resolve_food("lettuce wrap") == "lettuce"
    assert resolve_food("salmon steaks") == "salmon"


def test_raw_chicken_uses_raw_values():
    item, err = snap_item_from_text("100g raw chicken breast")
    assert err is None and item["calories"] == 120
    cooked, _ = snap_item_from_text("100g chicken breast")
    assert cooked["calories"] == 165


def test_photographed_onion_powder_is_fresh_onion():
    items, _ = build_plate([{"food": "onion powder", "grams": 15}, {"food": "garlic powder", "grams": 2}], [])
    names = {i["name"].lower(): i for i in items}
    assert "onion" in names and names["onion"]["calories"] == 6
    assert "garlic powder" in names  # a real pinch of spice stays a spice


def test_coconut_milk_says_canned_and_drink_is_separate():
    canned, _ = snap_item_from_text("200ml coconut milk")
    drink, _ = snap_item_from_text("200ml coconut milk drink")
    assert "canned" in canned["name"].lower() and canned["calories"] == 460
    assert drink["calories"] == 40


def test_nori_sheets_count_as_units():
    item, err = snap_item_from_text("3 nori")
    assert err is None and item["grams"] == 7.5


# ── USDA fallback (simulated USDA response; no network) ────────────────────
FAKE_USDA = {"foods": [
    {"description": "Cheese, cheddar", "foodNutrients": []},
    {"description": "Seaweed, kelp, raw", "foodNutrients": [
        {"nutrientName": "Energy", "unitName": "kJ", "value": 180},
        {"nutrientName": "Energy", "unitName": "KCAL", "value": 43},
        {"nutrientName": "Protein", "unitName": "G", "value": 1.7},
        {"nutrientName": "Carbohydrate, by difference", "unitName": "G", "value": 9.6},
        {"nutrientName": "Total lipid (fat)", "unitName": "G", "value": 0.6}]},
]}


@pytest.fixture
def fake_usda(monkeypatch):
    import server

    class _Resp:
        status_code = 200

        def json(self):
            return FAKE_USDA

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def get(self, *a, **k):
            _Client.params = k.get("params")
            return _Resp()

    monkeypatch.setattr(server.httpx, "AsyncClient", _Client)
    return server, _Client


def _add(server, text):
    from fastapi import HTTPException
    try:
        return asyncio.run(server.snap_food_item(server.SnapItemRequest(text=text)))
    except HTTPException as e:
        return e.detail["message"]


def test_usda_fallback_logs_generic_food(fake_usda):
    server, client = fake_usda
    item = _add(server, "30g kelp")
    assert item["source"] == "usda" and item["calories"] == 13 and item["grams"] == 30
    assert client.params["dataType"] == ["Foundation", "SR Legacy"]   # never branded products


def test_usda_fallback_needs_grams(fake_usda):
    server, _ = fake_usda
    assert "grams" in _add(server, "kelp")


def test_usda_fallback_never_guesses(fake_usda):
    server, _ = fake_usda
    assert "Couldn't find" in _add(server, "100g unicorn steak")


def test_database_food_does_not_use_usda(fake_usda):
    server, _ = fake_usda
    assert _add(server, "150g chicken breast")["source"] == "database"
