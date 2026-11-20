"""
Snap on TestFlight (20 Nov): Zerella Fresh potatoes, label 208 kJ per 100 g
(= 50 cal). The AI turned 208 kJ into 83 cal (÷2.5, not ÷4.184), so 462 g
was logged as 383 cal instead of about 230. The printed energy and unit are
now converted in code, and calories that don't fit the label's macros are
worked out from the macros instead.
"""
import json

import pytest
from mongomock_motor import AsyncMongoMockClient

import server

IMAGE = "iVBORw0KGgo" + "A" * 200
ZERELLA = {
    "food_name": "Zerella Fresh Potatoes", "serving_size": "250g", "serving_size_g": 250,
    "units_per_serving": None, "unit_name": None, "servings_per_package": 6, "package_size_g": None,
    "label_visible": True, "items": None,
    "per_100g": {"calories": 83, "protein": 1.4, "carbs": 8.9, "fats": 0.1},     # ← the AI's wrong 83
    "calories": 208, "protein": 3.5, "carbs": 22.2, "fats": 0.2,
    "fiber": 3.5, "sugar": 2.7, "sodium": 25,
    "energy_100g_printed": {"value": 208, "unit": "kJ"}, "energy_serving_printed": {"value": 520, "unit": "kJ"},
    "confidence": "high", "energy_source": "label",
}


@pytest.fixture
def db(monkeypatch):
    d = AsyncMongoMockClient()["t"]
    monkeypatch.setattr(server, "db", d)

    async def paid(user_id):
        return {"has_access": True}
    monkeypatch.setattr(server, "check_subscription_access", paid)
    return d


def _ai(answer):
    async def call(*a, **k):
        return json.dumps(answer)
    return call


async def _snap(monkeypatch, answer, text="462 g"):
    monkeypatch.setattr(server, "call_claude_sonnet", _ai(answer))
    req = server.FoodImageAnalyzeRequest(user_id="u1", image_base64=IMAGE, meal_type="snack", preview=True,
                                         additional_context=text)
    return await server.analyze_food_image(req)


async def test_printed_kj_converted_in_code(db, monkeypatch):
    res = await _snap(monkeypatch, ZERELLA)
    assert 225 <= res["calories"] <= 235            # 462 g × 49.7 cal/100 g ≈ 230, not 383
    assert round(res["protein"], 1) == 6.5 and round(res["carbs"], 1) == 41.1


async def test_old_answer_without_printed_energy_uses_macros(db, monkeypatch):
    old = {k: v for k, v in ZERELLA.items() if not k.startswith("energy_")}
    res = await _snap(monkeypatch, old)
    assert res["calories"] < 260                    # from the macros, never the misread 83/100 g


def test_conversions():
    assert round(server._printed_kcal({"value": 208, "unit": "kJ"}), 1) == 49.7
    assert server._printed_kcal({"value": 50, "unit": "Cal"}) == 50
    assert server._printed_kcal({"value": 50, "unit": "?"}) == 0
    p, fd = server._label_energy_fix({"calories": 143, "protein": 12.2, "carbs": 1.3, "fats": 9.9},
                                     {"energy_100g_printed": {"value": 598, "unit": "kJ"}}, 104)
    assert round(p["calories"]) == 143             # a correct label stays correct
