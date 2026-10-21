"""Snap food: the description box, the portion parser, labelled products and
plated meals — all on nutrition_engine (the meal-plan calculator).

The vision model is mocked, so these run offline and deterministically."""
import json
import os
import sys
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
import server  # noqa: E402
from nutrition_engine import (build_plate, macros_for, parse_portions, plate_totals,  # noqa: E402
                              portion_grams, snap_item_from_text)
from server import app  # noqa: E402

_db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "test_database")]
IMAGE = "iVBORw0KGgo" + "A" * 200


def _mock(response):
    async def _call(system_message, user_message, temperature=0.7, max_tokens=2500, image_base64=None, image_base64_2=None):
        _call.max_tokens = max_tokens
        _call.user_message = user_message
        return json.dumps(response)
    return _call


@pytest.fixture
def paid_user():
    uid = f"TEST_snap_{uuid.uuid4().hex[:8]}"
    _db.profiles.insert_one({"id": uid, "email": f"{uid}@test.local", "name": "Snap Test", "subscription_status": "monthly",
                             "weight": 80, "height": 180, "age": 30, "gender": "male", "activity_level": "moderate",
                             "goal": "maintenance"})
    yield uid
    _db.profiles.delete_one({"id": uid})
    _db.food_logs.delete_many({"user_id": uid})


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


EGGS = {"food_name": "Free Range Eggs", "serving_size": "104g (2 eggs)", "serving_size_g": 104, "units_per_serving": 2,
        "unit_name": "egg", "servings_per_package": 6, "package_size_g": None, "label_visible": True, "items": None,
        "per_100g": {"calories": 143, "protein": 12.2, "carbs": 1.3, "fats": 9.9},
        "calories": 149, "protein": 12.7, "carbs": 1.4, "fats": 10.3, "confidence": "high", "energy_source": "label"}
YOGHURT = {"food_name": "Greek Yoghurt Natural", "serving_size": "170g", "serving_size_g": 170, "units_per_serving": None,
           "unit_name": None, "servings_per_package": None, "package_size_g": 500, "label_visible": True, "items": None,
           "per_100g": {"calories": 62, "protein": 9.5, "carbs": 3.4, "fats": 0.2},
           "calories": 105, "protein": 16.2, "carbs": 5.8, "fats": 0.3, "confidence": "high", "energy_source": "label"}
YOUFOODZ = {"food_name": "Youfoodz Chicken Teriyaki", "serving_size": "430g", "serving_size_g": 430, "units_per_serving": None,
            "unit_name": None, "servings_per_package": 1, "package_size_g": 430, "label_visible": True, "items": None,
            "per_100g": {"calories": 148, "protein": 10.4, "carbs": 20.1, "fats": 2.6},
            "calories": 637, "protein": 44.9, "carbs": 86.5, "fats": 11.2, "confidence": "high", "energy_source": "label"}
PLATE = {"food_name": "Fried Eggs on Sourdough", "label_visible": False, "per_100g": None,
         "calories": None, "protein": None, "carbs": None, "fats": None, "energy_source": "derived", "confidence": "high",
         "items": [{"food": "eggs", "grams": 110}, {"food": "sourdough bread", "grams": 60},
                   {"food": "olive oil", "grams": 7}, {"food": "tomato sauce", "grams": 20}]}


async def _scan(client, user, monkeypatch, data, text="", qty=1):
    mock = _mock(data)
    monkeypatch.setattr(server, "call_claude_sonnet", mock)
    r = await client.post("/api/food/analyze", json={"user_id": user, "image_base64": IMAGE, "meal_type": "breakfast",
                                                     "additional_context": text or None, "quantity": qty, "preview": True})
    return r, mock


# ── parser ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("", []), ("no dressing", []), ("grilled not fried", []), ("extra cheese", []),
    ("200g", [(200, "g", "")]), ("about 300g", [(300, "g", "")]), ("~250ml", [(250, "ml", "")]),
    ("approx 150 grams", [(150, "g", "")]),
    ("half", [(0.5, "serving", "")]), ("1/2 serving", [(0.5, "serving", "")]), ("½ serving", [(0.5, "serving", "")]),
    ("quarter of the tub", [(0.25, "pack", "")]), ("half the pack", [(0.5, "pack", "")]),
    ("the whole pack", [(1, "pack", "")]), ("the whole bag", [(1, "pack", "")]), ("whole tub", [(1, "pack", "")]),
    ("1 cup", [(1, "cup", "")]), ("4 eggs", [(4, "count", "eggs")]),
    ("4 eggs and 3 pieces of sourdough", [(4, "count", "eggs"), (3, "piece", "sourdough")]),
    ("half, no dressing", [(0.5, "serving", "")]), ("a handful of almonds", [(1, "handful", "almonds")]),
])
def test_parse_portions(text, expected):
    assert [(s["amount"], s["unit"], s["food"]) for s in parse_portions(text)] == expected


def test_portion_grams_uses_label_unit_only_when_it_matches():
    four_eggs = parse_portions("4 eggs")[0]
    assert portion_grams(four_eggs, "eggs", serving_g=104, unit_name="egg", units_per_serving=2, label=True) == 208
    assert portion_grams(four_eggs, "greek yogurt", serving_g=170, label=True) is None     # yoghurt isn't eggs
    assert portion_grams(parse_portions("1 cup")[0], "greek yogurt", label=True) == 245       # yoghurt's own cup
    assert portion_grams(parse_portions("1 cup")[0], None, serving_g=430, label=True) is None  # ready meal: no cup weight


# ── labelled products: unchanged accuracy, description never breaks a scan ──
@pytest.mark.asyncio
@pytest.mark.parametrize("text,grams", [("", 430), ("1 serving", 430), ("the whole pack", 430), ("no dressing", 430),
                                        ("half", 215), ("about 300g", 300), ("200g", 200)])
async def test_youfoodz_label(client, paid_user, monkeypatch, text, grams):
    r, mock = await _scan(client, paid_user, monkeypatch, YOUFOODZ, text)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["portion_g_applied"] == grams
    assert b["calories"] == round(148 * grams / 100)
    assert b["items"] is None and b["summary"].startswith("Label: 148 cal/100g · your portion:")
    assert mock.max_tokens == 1000


@pytest.mark.asyncio
async def test_youfoodz_blank_matches_label_serving(client, paid_user, monkeypatch):
    b = (await _scan(client, paid_user, monkeypatch, YOUFOODZ))[0].json()
    assert abs(b["calories"] - 637) <= 1 and b["summary"] == "Label: 148 cal/100g · your portion: 1 serving = 430g"


@pytest.mark.asyncio
@pytest.mark.parametrize("text,grams", [("4 eggs", 208), ("half", 52), ("1/2 serving", 52), ("200g", 200),
                                        ("the whole pack", 624), ("", 104)])
async def test_egg_carton(client, paid_user, monkeypatch, text, grams):
    r, _ = await _scan(client, paid_user, monkeypatch, EGGS, text)
    assert r.status_code == 200, r.text
    assert r.json()["portion_g_applied"] == grams


@pytest.mark.asyncio
@pytest.mark.parametrize("text,grams", [("quarter of the tub", 125), ("the whole pack", 500), ("1 cup", 245),
                                        ("½ serving", 85)])
async def test_yoghurt_tub(client, paid_user, monkeypatch, text, grams):
    r, _ = await _scan(client, paid_user, monkeypatch, YOGHURT, text)
    assert r.status_code == 200, r.text
    assert r.json()["portion_g_applied"] == grams


@pytest.mark.asyncio
async def test_clear_amount_that_cant_be_worked_out_fails(client, paid_user, monkeypatch):
    r, _ = await _scan(client, paid_user, monkeypatch, YOGHURT, "4 eggs")
    assert r.status_code == 422 and r.json()["detail"]["error"] == "portion_unresolvable"
    r, _ = await _scan(client, paid_user, monkeypatch, {**YOGHURT, "package_size_g": None}, "the whole pack")
    assert r.status_code == 422


# ── plated meals: each part from the database ─────────────────────────────
@pytest.mark.asyncio
async def test_eggs_on_sourdough_items(client, paid_user, monkeypatch):
    r, mock = await _scan(client, paid_user, monkeypatch, PLATE, "4 eggs and 3 pieces of sourdough")
    assert r.status_code == 200, r.text
    b = r.json()
    names = [(i["display"], i["grams"]) for i in b["items"]]
    assert ("4 large eggs", 232) in names and ("3 slices sourdough bread", 90) in names
    exp = [macros_for("eggs", 232), macros_for("sourdough bread", 90), macros_for("olive oil", 7), macros_for("tomato sauce", 20)]
    assert b["calories"] == sum(m["calories"] for m in exp)
    assert 600 <= b["calories"] <= 700 and b["protein"] >= 38
    assert "4 eggs and 3 pieces of sourdough" in mock.user_message


@pytest.mark.asyncio
@pytest.mark.parametrize("text,factor", [("", 1), ("half", 0.5), ("the whole pack", 1), ("no dressing", 1)])
async def test_plate_scaling(client, paid_user, monkeypatch, text, factor):
    b = (await _scan(client, paid_user, monkeypatch, PLATE, text))[0].json()
    base = plate_totals(build_plate(PLATE["items"], [])[0])
    assert abs(b["portion_g_applied"] - base["grams"] * factor) <= 1


def test_item_edit_and_add():
    it, err = snap_item_from_text("3 eggs", key="eggs", name="Eggs")
    assert err is None and it["grams"] == 174 and it["display"] == "3 large eggs"
    it, err = snap_item_from_text("1 tbsp olive oil")
    assert err is None and it["key"] == "olive oil"
    it, err = snap_item_from_text("30g dragonfruit-ish thing")
    assert it is None and "food database" in err


@pytest.mark.asyncio
async def test_food_item_endpoint(client):
    r = await client.post("/api/food/item", json={"text": "30g cheddar"})
    assert r.status_code == 200 and r.json()["grams"] == 30
    r = await client.post("/api/food/item", json={"text": "unicorn steak"})
    assert r.status_code == 422 and "food database" in r.json()["detail"]["message"]
