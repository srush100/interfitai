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
    async def fake(query, max_results=50, **kw):
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
    r = asyncio.run(server._ai_estimate("big mac"))      # the last-resort step of the lookup
    assert r["serving_size"] == "1 burger (219g)" and r["serving_g"] == 219 and r["calories"] == 563


def test_ai_search_serving_without_weight(paid, monkeypatch):
    async def fake_claude(**kw):
        return ('{"food_name":"Big Mac","calories":563,"protein_g":26,"carbs_g":45,"fat_g":33,'
                '"serving_size":"1 burger","confidence":"high"}')
    monkeypatch.setattr(server, "call_claude_sonnet", fake_claude)
    r = asyncio.run(server._ai_estimate("big mac"))
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


# ── typed amounts on a snapped plate: "220 gram chicken" is never 220 breasts ──
import nutrition_engine as _ne


@pytest.mark.parametrize("text", ["220 gram cooked chicken breast", "220 grams chicken breast",
                                  "220g chicken breast", "220 chicken breast"])
def test_snap_typed_chicken_is_220_grams(text):
    specs = _ne.parse_portions(f"200g cooked basmati rice, {text}, half an avocado")
    items, problems = _ne.build_plate([{"food": "basmati rice", "grams": 180},
                                       {"food": "chicken breast", "grams": 150},
                                       {"food": "avocado", "grams": 60}], specs)
    chicken = next(i for i in items if "hicken" in i["name"])
    assert chicken["grams"] == 220 and chicken["calories"] < 400 and not problems


def test_small_counts_still_counted():
    assert _ne.portion_grams({"amount": 2, "unit": "count", "food": "chicken breast"}, "chicken breast") == 350
    assert _ne.portion_grams({"amount": 25, "unit": "count", "food": "almonds"}, "almonds") < 100


def test_huge_plate_is_flagged():
    items, problems = _ne.build_plate([{"food": "chicken breast", "grams": 4000}], [])
    assert problems and "3 kg" in problems[0]


# ── one calculation everywhere: food search, AI search and the chat coach ──
def _paid(monkeypatch):
    async def ok(_):
        return {"has_access": True}
    monkeypatch.setattr(server, "check_subscription_access", ok)


@pytest.mark.parametrize("text, kcal, assumed", [
    ("3 boiled eggs on 2 pieces of rye", 387, []),
    ("3 boiled eggs on 2 pieces of rye bread", 387, []),
    ("3 boiled eggs + 2 slices rye bread", 387, []),
    ("3 eggs on rye", 310, ["rye"]),                 # rye isn't dropped: 1 slice, and said so
    ("3 eggs on rye for breakfast", 310, ["rye"]),
])
def test_typed_meal_from_food_database(text, kcal, assumed):
    calc = _ne.calculate_meal_text(text)
    assert calc["calories"] == kcal and calc["assumed"] == assumed


@pytest.mark.parametrize("text", ["big mac", "beans on toast", "2 eggs and some spinach", "how much protein?"])
def test_typed_meal_unclear_goes_to_ai(text):
    assert _ne.calculate_meal_text(text) is None


def test_ai_search_uses_database_and_is_the_same_every_time(monkeypatch):
    _paid(monkeypatch)
    async def no_ai(**kw):
        raise AssertionError("AI must not be asked")
    monkeypatch.setattr(server, "call_claude_sonnet", no_ai)
    a = asyncio.run(server.ai_food_search("3 boiled eggs on 2 pieces of rye", "u"))
    b = asyncio.run(server.ai_food_search("3 boiled eggs on 2 pieces of rye", "u"))
    assert a == b and a["from_database"] and a["calories"] == 387
    assert "3 large eggs (150g)" in a["serving_size"] and "2 slices" in a["serving_size"]


def test_food_search_meal_skips_usda_keyword_noise(monkeypatch):
    _paid(monkeypatch)
    async def usda(*a, **k):
        raise AssertionError("no USDA keyword search for a whole meal")
    monkeypatch.setattr(server, "search_usda", usda)
    res = asyncio.run(server.search_foods("3 boiled eggs on 2 pieces of rye", "u"))
    assert not any("dried" in r["name"].lower() for r in res)


class _KjResp:
    status_code = 200
    def __init__(self, foods): self._f = foods
    def json(self): return {"foods": self._f}


class _KjClient:
    def __init__(self, foods): self._f = foods
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    async def get(self, *a, **k): return _KjResp(self._f)


def test_usda_search_shows_kcal_not_kilojoules(monkeypatch):
    broccoli = {"description": "Broccoli, cooked, boiled, drained, with salt", "dataType": "SR Legacy", "fdcId": 1,
                "foodNutrients": [{"nutrientName": "Energy", "unitName": "KCAL", "value": 35},
                                  {"nutrientName": "Protein", "unitName": "G", "value": 2.4},
                                  {"nutrientName": "Energy", "unitName": "kJ", "value": 146}]}
    yolk_kj_only = {"description": "Egg, yolk, dried", "dataType": "SR Legacy", "fdcId": 2,
                    "foodNutrients": [{"nutrientName": "Energy", "unitName": "kJ", "value": 2800}]}
    monkeypatch.setattr(server.httpx, "AsyncClient", lambda *a, **k: _KjClient([broccoli, yolk_kj_only]))
    res = asyncio.run(server.search_usda("broccoli"))
    assert res[0]["calories"] == 35 and res[0]["protein"] == 2.4
    assert res[1]["calories"] == 669


def test_chat_coach_gets_food_database_numbers(monkeypatch):
    _paid(monkeypatch)
    seen = {}

    class Coll:
        async def count_documents(self, q): return 0
        async def find_one(self, q): return None
        async def insert_one(self, d): return None
        def find(self, q): return self
        def sort(self, *a): return self
        def limit(self, n): return self
        async def to_list(self, n): return []

    class FakeDB:
        def __getattr__(self, name): return Coll()

    class FakeChat:
        def __init__(self, **kw): seen["system"] = kw["initial_messages"][0]["content"]
        def with_model(self, *a): return self
        def with_params(self, **k): return self
        async def send_message(self, m): return "ok"

    monkeypatch.setattr(server, "db", FakeDB())
    monkeypatch.setattr(server, "LlmChat", FakeChat)
    async def ctx(*a): return ""
    monkeypatch.setattr(server, "_chat_user_context", ctx)
    asyncio.run(server.chat_with_ai(server.ChatRequest(
        user_id="u", message="What are the macros for 3 boiled eggs on 2 pieces of rye bread?")))
    assert "FOOD DATABASE RESULT" in seen["system"] and "Total: 387 kcal" in seen["system"]
