"""
Food log accuracy fixes:
- the accuracy guard leaves alcohol and high-fibre foods alone, still fixes bad AI numbers
- search results (built-in list, USDA) are shown as they are, not "corrected"
- USDA branded results are scaled to the label serving they show
- AI / web results say what their serving is
- the log endpoint only corrects AI estimates (and entries from older apps)
"""
import asyncio

import pytest

import server
from server import sanitize_food_entry


def _guard(name, cal, p, c, f, fiber=0, **kw):
    e = {"food_name": name, "calories": cal, "protein": p, "carbs": c, "fats": f, "fiber": fiber}
    sanitize_food_entry(e, **kw)
    return e["calories"]


@pytest.mark.parametrize("name, cal, p, c, f", [
    ("Beer, Regular (12 oz)", 153, 1.6, 12.6, 0),
    ("Wine, Red (5 oz)", 125, 0.1, 3.8, 0),
    ("Vodka (30ml)", 64, 0, 0, 0.0001),
    ("Margarita", 274, 0.1, 36, 0.1),
])
def test_alcohol_calories_kept(name, cal, p, c, f):
    assert _guard(name, cal, p, c, f) == cal


def test_alcohol_free_and_vinegar_still_checked():
    assert _guard("Red wine vinegar (15ml)", 300, 0, 0.4, 0) != 300
    assert _guard("Ginger beer", 300, 0, 10, 0) != 300


def test_high_fibre_bar_kept():
    # Quest bar label: 190 cal, 20P / 21C (14 fibre) / 8F
    assert _guard("Quest Protein Bar", 190, 20, 21, 8, fiber=14) == 190


def test_bad_ai_numbers_still_fixed():
    assert _guard("Eggs (100g)", 596, 13, 1.1, 11) == 155


def test_reconcile_off_leaves_numbers():
    assert _guard("Quest Protein Bar", 190, 20, 21, 8, reconcile=False) == 190


# ── search ────────────────────────────────────────────────────────────────
@pytest.fixture
def paid(monkeypatch):
    async def ok(_uid):
        return {"has_access": True}
    monkeypatch.setattr(server, "check_subscription_access", ok)


def _fake_usda(monkeypatch, foods):
    async def fake(query, max_results=50):
        return [r for r in foods]
    monkeypatch.setattr(server, "search_usda", fake)


def test_search_shows_real_beer_and_broccoli(paid, monkeypatch):
    _fake_usda(monkeypatch, [])
    res = asyncio.run(server.search_foods(query="beer", user_id="u"))
    beer = next(r for r in res if r["name"].startswith("Beer, Regular"))
    assert beer["calories"] == 153
    res = asyncio.run(server.search_foods(query="broccoli", user_id="u"))
    assert next(r for r in res if r["name"].startswith("Broccoli, Steamed"))["calories"] == 55


class _Resp:
    status_code = 200

    def __init__(self, data):
        self._d = data

    def json(self):
        return self._d


def _usda_client(monkeypatch, foods):
    class Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def get(self, *a, **k):
            return _Resp({"foods": foods})
    monkeypatch.setattr(server.httpx, "AsyncClient", Client)


def _n(cal, p, c, f):
    return [{"nutrientName": "Energy", "unitName": "KCAL", "value": cal},
            {"nutrientName": "Protein", "value": p},
            {"nutrientName": "Carbohydrate, by difference", "value": c},
            {"nutrientName": "Total lipid (fat)", "value": f}]


def test_usda_branded_scaled_to_label_serving(monkeypatch):
    _usda_client(monkeypatch, [
        {"dataType": "Branded", "description": "GRANOLA", "brandName": "Acme", "servingSize": 45,
         "servingSizeUnit": "GRM", "foodNutrients": _n(450, 10, 60, 18)},
        {"dataType": "Branded", "description": "OAT DRINK", "brandName": "Oatly", "servingSize": 250,
         "servingSizeUnit": "MLT", "foodNutrients": _n(46, 1, 6.6, 1.5)},
        {"dataType": "SR Legacy", "description": "Broccoli, raw", "foodNutrients": _n(34, 2.8, 6.6, 0.4)},
    ])
    res = asyncio.run(server.search_usda("x"))
    granola, oat, broc = res
    assert granola["name"] == "Acme - GRANOLA (45g)" and granola["calories"] == 202 and granola["serving_g"] == 45
    assert oat["name"].endswith("(250ml)") and oat["calories"] == 115 and oat["serving_unit"] == "ml"
    assert broc["name"] == "Broccoli, raw (100g)" and broc["calories"] == 34


def test_ai_search_reports_its_serving(paid, monkeypatch):
    async def fake_claude(**kw):
        return ('{"food_name":"Big Mac","calories":563,"protein_g":26,"carbs_g":45,"fat_g":33,'
                '"serving_size":"1 burger (219g)","source":"McDonald\'s","confidence":"high"}')
    monkeypatch.setattr(server, "call_claude_sonnet", fake_claude)
    r = asyncio.run(server.ai_food_search(query="big mac", user_id="u"))
    assert r["serving_size"] == "1 burger (219g)" and r["serving_g"] == 219 and r["calories"] == 563


def test_ai_search_serving_without_weight(paid, monkeypatch):
    async def fake_claude(**kw):
        return ('{"food_name":"Big Mac","calories":563,"protein_g":26,"carbs_g":45,"fat_g":33,'
                '"serving_size":"1 burger","confidence":"high"}')
    monkeypatch.setattr(server, "call_claude_sonnet", fake_claude)
    r = asyncio.run(server.ai_food_search(query="big mac", user_id="u"))
    assert r["serving_size"] == "1 burger" and r["serving_g"] is None


# ── log endpoint ──────────────────────────────────────────────────────────
@pytest.fixture
def fake_db(monkeypatch, paid):
    saved = []

    class Coll:
        async def insert_one(self, doc):
            saved.append(doc)

    class DB:
        food_logs = Coll()
    monkeypatch.setattr(server, "db", DB())
    return saved


def _log(source, name="Quest Protein Bar", cal=190, p=20, c=21, f=8):
    req = server.FoodLogRequest(user_id="u", food_name=name, serving_size="1 serving", calories=cal,
                                protein=p, carbs=c, fats=f, meal_type="snack", logged_date="2026-10-21",
                                source=source)
    return asyncio.run(server.log_food(req))


def test_log_keeps_database_and_manual_values(fake_db):
    assert _log("database").calories == 190
    assert _log("manual").calories == 190
    assert _log("usda", "Beer, Regular (12 oz)", 153, 1.6, 12.6, 0).calories == 153


def test_log_still_checks_ai_and_old_apps(fake_db):
    assert _log("ai", "Eggs (100g)", 596, 13, 1.1, 11).calories == 155
    assert _log(None, "Eggs (100g)", 596, 13, 1.1, 11).calories == 155
    assert _log("ai", "Beer", 153, 1.6, 12.6, 0).calories == 153
