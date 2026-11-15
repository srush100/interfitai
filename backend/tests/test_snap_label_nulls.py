"""
Snap on TestFlight (15 Nov): photos of packaged-food labels (Muscle Meals,
kangaroo snack sticks) failed with "float() argument must be a string or a real
number, not 'NoneType'". The label answer leaves fibre / sugar / sodium empty
(null), and the code turned empty into a number. Members also saw the raw
program error, and the failed photo counted towards the daily limit.
"""
import json

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

import server

IMAGE = "iVBORw0KGgo" + "A" * 200
MUSCLE_MEAL = {
    "food_name": "Muscle Meals Herbed Chicken & Potatoes", "serving_size": "350g", "serving_size_g": 350,
    "units_per_serving": None, "unit_name": None, "servings_per_package": 1, "package_size_g": 350,
    "label_visible": True, "items": None,
    "per_100g": {"calories": 139, "protein": 12.0, "carbs": 12.9, "fats": 5.4},
    "calories": 487, "protein": 42, "carbs": 45, "fats": 19,
    "fiber": None, "sugar": None, "sodium": None,          # ← what broke it
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
        if isinstance(answer, Exception):
            raise answer
        return json.dumps(answer)
    return call


def _req(**kw):
    return server.FoodImageAnalyzeRequest(user_id="u1", image_base64=IMAGE, meal_type="snack", preview=True, **kw)


async def test_label_with_empty_fibre_sugar_sodium(db, monkeypatch):
    monkeypatch.setattr(server, "call_claude_sonnet", _ai(MUSCLE_MEAL))
    res = await server.analyze_food_image(_req())
    assert 480 <= res["calories"] <= 495 and res["fiber"] == 0


async def test_label_with_servings_typed(db, monkeypatch):
    monkeypatch.setattr(server, "call_claude_sonnet", _ai({**MUSCLE_MEAL, "serving_size": "25g", "serving_size_g": 25,
                                                           "servings_per_package": 4, "package_size_g": 100}))
    res = await server.analyze_food_image(_req(additional_context="4 servings"))
    assert res["calories"] > 0


async def test_unexpected_error_is_plain_and_not_counted(db, monkeypatch):
    monkeypatch.setattr(server, "call_claude_sonnet", _ai(RuntimeError("boom")))
    monkeypatch.setattr(server, "call_claude_haiku", _ai(RuntimeError("boom")), raising=False)
    with pytest.raises(HTTPException) as e:
        await server.analyze_food_image(_req())
    detail = e.value.detail
    text = detail["message"] if isinstance(detail, dict) else str(detail)
    assert "boom" not in text and "float()" not in text
    assert await db.snap_usage.count_documents({}) == 0
