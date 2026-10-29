"""
One answer per food, everywhere: the food database first, then a saved answer,
then Open Food Facts, the web, and an AI estimate only as a last resort. Saved
answers match any word order or spelling, but never a different size, flavour
or country — and the chat coach quotes the same numbers.
"""
import asyncio
from datetime import datetime, timedelta

import pytest

import server
import food_lookup as FL


# ── matching rules ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("a, b", [
    ("mcdonalds thick shake large australia", "Large McDonald's Thick Shake"),
    ("thickshake large mcdonalds", "mcdonalds   THICK  shake, large"),
    ("Big Macs", "big mac"),
    ("maccas large chips", "large fries mcdonalds"),
    ("Chobani Greek Yoghurt vanilla", "vanilla greek yogurt chobani"),
])
def test_same_food_same_key(a, b):
    assert FL.lookup_key(a, "AU")[0] == FL.lookup_key(b, "AU")[0]


@pytest.mark.parametrize("a, b", [
    ("mcdonalds thick shake large", "mcdonalds thick shake small"),          # size
    ("mcdonalds thick shake large", "mcdonalds strawberry thick shake large"),  # flavour
    ("diet coke", "coke"),                                                    # type
])
def test_different_food_different_key(a, b):
    assert FL.lookup_key(a, "AU")[0] != FL.lookup_key(b, "AU")[0]


def test_country_from_phone_or_typed():
    assert FL.lookup_key("big mac", "AU")[0] == FL.lookup_key("big mac australia", "")[0] == "AU|bigmac"
    assert FL.lookup_key("big mac", "US")[0] == "US|bigmac"
    assert FL.lookup_key("big mac usa", "AU")[0] == "US|bigmac"      # typed country wins
    assert FL.lookup_key("big mac", "")[0] == "INTL|bigmac"


# ── Open Food Facts matching ────────────────────────────────────────────────
def _product(name, brand="", quantity="", kcal=None, kj=None, per="100g", serving_g=None, p=0, c=0, f=0):
    n = {f"proteins_{per}": p, f"carbohydrates_{per}": c, f"fat_{per}": f}
    if kcal is not None:
        n[f"energy-kcal_{per}"] = kcal
    if kj is not None:
        n[f"energy-kj_{per}"] = kj
    return {"code": "123", "product_name": name, "brands": brand, "quantity": quantity,
            "serving_quantity": serving_g, "serving_size": f"{serving_g}g" if serving_g else None, "nutriments": n}


def test_off_needs_every_typed_word_including_size():
    tokens = FL.food_tokens("weet-bix")
    assert FL.off_match(_product("Weet-Bix", "Sanitarium"), tokens)
    assert not FL.off_match(_product("Banana Chips Honey Coated Crunchy"), FL.food_tokens("banana"))
    big = FL.food_tokens("chobani vanilla greek yogurt large")
    assert not FL.off_match(_product("Greek Yogurt Vanilla", "Chobani", "170g"), big)


def test_off_result_per_serving_and_kj():
    r = FL.off_result(_product("Weet-Bix", "Sanitarium", kcal=None, kj=1400, per="100g", p=12, c=67, f=1.4))
    assert r["calories"] == 335 and r["serving_size"] == "100g" and r["name"] == "Sanitarium Weet-Bix"
    r = FL.off_result(_product("Up&Go Chocolate", "Sanitarium", kcal=227, per="serving", serving_g=250, p=9))
    assert r["calories"] == 227 and r["serving_g"] == 250


# ── the lookup order and saved answers ─────────────────────────────────────
class Lookups:
    def __init__(self):
        self.docs = []

    async def create_index(self, *a, **k):
        return None

    async def find_one(self, q):
        conds = q.get("$or") or [q]
        return next((d for d in self.docs if any(all(d.get(k) == v for k, v in c.items()) for c in conds)), None)

    async def update_one(self, q, upd, upsert=False):
        d = await self.find_one(q)
        if d:
            d.update(upd["$set"])
        else:
            self.docs.append(dict(upd["$set"]))

    def find(self, q):
        words = set(q["tokens"]["$not"]["$elemMatch"]["$nin"])
        hits = [d for d in self.docs if d["country"] == q["country"] and d["tokens"] and set(d["tokens"]) <= words]

        class Cur:
            async def to_list(self, n):
                return hits[:n]
        return Cur()


@pytest.fixture
def world(monkeypatch):
    """Fake database and lookup steps; records which steps ran."""
    calls = []

    class DB:
        food_lookups = Lookups()
    monkeypatch.setattr(server, "db", DB())
    monkeypatch.setattr(server, "_food_lookup_index_ready", False)
    found = {"open_food_facts": None, "web": None, "ai_estimate": None}

    def step(kind):
        async def run(query, country):
            calls.append((kind, query, country))
            r = found[kind]
            return dict(r) if r else None
        return run
    monkeypatch.setattr(server, "_off_lookup", step("open_food_facts"))
    monkeypatch.setattr(server, "_web_lookup", step("web"))
    monkeypatch.setattr(server, "_ai_estimate", step("ai_estimate"))
    return {"db": DB.food_lookups, "calls": calls, "found": found}


SHAKE = {"name": "McDonald's Chocolate Thick Shake, Large (AU)", "calories": 610, "protein": 15, "carbs": 98,
         "fats": 17, "serving_size": "1 large", "verified": True, "is_ai_estimate": False, "source": "mcdonalds.com.au"}


def run(coro):
    return asyncio.run(coro)


def test_database_first_no_lookup(world):
    r = run(server.lookup_food("3 boiled eggs on 2 slices rye", "AU"))
    assert r["lookup"] == "database" and r["calories"] == 387 and world["calls"] == []
    r = run(server.lookup_food("banana", "AU"))
    assert r["lookup"] == "database" and world["calls"] == []


def test_web_answer_saved_and_reused_for_any_wording(world):
    world["found"]["web"] = SHAKE
    a = run(server.lookup_food("mcdonalds thick shake large australia", "AU"))
    assert a["lookup"] == "web" and a["calories"] == 610 and not a["saved"]
    assert [c[0] for c in world["calls"]] == ["open_food_facts", "web"]
    b = run(server.lookup_food("Large McDonald's Thick Shake", "AU"))
    assert b["saved"] and b["calories"] == 610 and len(world["calls"]) == 2   # no new search
    run(server.lookup_food("mcdonalds thick shake small", "AU"))               # different size → new search
    run(server.lookup_food("large mcdonalds thick shake", "US"))                # different country → new search
    assert len(world["calls"]) >= 6 and world["calls"][-1][2] == "US"


def test_ai_estimate_only_last_and_replaced_by_web(world):
    world["found"]["ai_estimate"] = {**SHAKE, "verified": False, "is_ai_estimate": True, "calories": 550}
    r = run(server.lookup_food("homemade lasagne", "AU"))
    assert r["lookup"] == "ai_estimate" and [c[0] for c in world["calls"]] == ["open_food_facts", "web", "ai_estimate"]
    # same week: the saved estimate, no new guess
    assert run(server.lookup_food("lasagne homemade", "AU"))["calories"] == 550 and len(world["calls"]) == 3
    # "Verify on the web" finds real figures → they replace the estimate for everyone
    world["found"]["web"] = {**SHAKE, "calories": 430}
    v = run(server.lookup_food("homemade lasagne", "AU", force_web=True))
    assert v["lookup"] == "web" and v["calories"] == 430
    assert run(server.lookup_food("homemade lasagne", "AU"))["calories"] == 430


def test_estimate_retried_after_a_week_but_never_replaces_verified(world):
    world["found"]["ai_estimate"] = {**SHAKE, "verified": False, "calories": 550}
    run(server.lookup_food("homemade lasagne", "AU"))
    world["db"].docs[0]["updated_at"] = datetime.utcnow() - timedelta(days=8)
    n = len(world["calls"])
    r = run(server.lookup_food("homemade lasagne", "AU"))
    assert [c[0] for c in world["calls"][n:]] == ["open_food_facts", "web"]   # tried real sources again
    assert r["calories"] == 550 and r["saved"]                                 # nothing found: estimate kept, no new guess


def test_verified_answer_refreshed_yearly(world):
    world["found"]["web"] = SHAKE
    run(server.lookup_food("big mac", "AU"))
    world["db"].docs[0]["updated_at"] = datetime.utcnow() - timedelta(days=400)
    world["found"]["web"] = {**SHAKE, "calories": 563}
    assert run(server.lookup_food("big mac", "AU"))["calories"] == 563


def test_verify_without_web_result_keeps_saved(world):
    world["found"]["ai_estimate"] = {**SHAKE, "verified": False, "calories": 550}
    run(server.lookup_food("nanna's slice", "AU"))
    r = run(server.lookup_food("nanna's slice", "AU", force_web=True))
    assert r["calories"] == 550 and r["web_not_found"]


# ── US brand list hidden outside the US ────────────────────────────────────
def test_usda_brands_only_for_us(monkeypatch):
    seen = []

    async def ok(_):
        return {"has_access": True}

    async def usda(query, max_results=50, branded=True):
        seen.append(branded)
        return []
    monkeypatch.setattr(server, "check_subscription_access", ok)
    monkeypatch.setattr(server, "search_usda", usda)
    run(server.search_foods("cheerios", "u", country="AU"))
    run(server.search_foods("cheerios", "u", country="US"))
    run(server.search_foods("cheerios usa", "u", country="AU"))
    assert seen == [False, True, True]


def test_food_search_list_starts_with_database_result(monkeypatch):
    async def ok(_):
        return {"has_access": True}

    async def usda(*a, **k):
        return []
    monkeypatch.setattr(server, "check_subscription_access", ok)
    monkeypatch.setattr(server, "search_usda", usda)
    res = run(server.search_foods("3 boiled eggs on 2 slices rye", "u", country="AU"))
    assert res[0]["from_database"] and res[0]["calories"] == 387
    assert res[0]["name"] == "3 large eggs (150g) + 2 slices rye (60g)"


# ── the chat coach quotes saved foods ──────────────────────────────────────
def test_chat_uses_saved_food(world, monkeypatch):
    world["found"]["web"] = SHAKE
    run(server.lookup_food("large mcdonalds thick shake", "AU"))
    hits = run(server.saved_foods_in("Is a large McDonald's thickshake OK on a cut?", "AU"))
    assert [h["result"]["calories"] for h in hits] == [610]
    assert run(server.saved_foods_in("Is a large McDonald's thickshake OK on a cut?", "US")) == []
    assert run(server.saved_foods_in("what about a small thickshake from mcdonalds", "AU")) == []


# ── restaurant orders: each item looked up and saved on its own ───────────
def test_order_split_per_item_with_chain_carried(world, monkeypatch):
    menu = {"hungry jacks whopper": {"name": "Hungry Jack's Whopper", "calories": 600, "protein": 27, "carbs": 49,
                                     "fats": 33, "serving_size": "1 burger", "verified": True,
                                     "source": "hungryjacks.com.au"},
            "hungry jacks large chips": {"name": "Hungry Jack's Large Chips", "calories": 400, "protein": 5,
                                         "carbs": 52, "fats": 19, "serving_size": "1 large",
                                         "verified": True, "source": "hungryjacks.com.au"}}

    async def web(query, country):
        world["calls"].append(("web", query, country))
        return dict(menu[query.lower()]) if query.lower() in menu else None
    monkeypatch.setattr(server, "_web_lookup", web)
    r = run(server.lookup_food("hungry jacks whopper and large chips", "AU"))
    assert r["calories"] == 1000 and r["protein"] == 32 and r["lookup"] == "web" and r["verified"]
    assert [i["name"] for i in r["items"]] == ["Hungry Jack's Whopper", "Hungry Jack's Large Chips"]
    assert {c[1] for c in world["calls"] if c[0] == "web"} == set(menu)
    # each item is now saved: the chips alone come back instantly, same numbers
    n = len(world["calls"])
    assert run(server.lookup_food("large chips hungry jacks", "AU"))["calories"] == 400 and len(world["calls"]) == n
    # "with" stays inside a menu item's name
    run(server.lookup_food("hungry jacks whopper with cheese", "AU"))
    assert world["calls"][-1][1] == "hungry jacks whopper with cheese"


def test_order_mixes_database_and_restaurant(world):
    world["found"]["web"] = {**SHAKE, "name": "Big Mac", "calories": 560, "protein": 26, "carbs": 45, "fats": 30}
    r = run(server.lookup_food("2 boiled eggs and a big mac", "AU"))
    assert r["calories"] == 560 + 155 and r["lookup"] == "web"
    assert [i["lookup"] for i in r["items"]] == ["database", "web"]


# ── build-your-own items (Subway): added up from saved parts ───────────────
SUB = "subway footlong on rye bread, steak and cheese with spinach, tomato and onion with smokey bbq sauce"
PARTS = {"subway footlong rye bread": 420, "subway footlong steak": 220, "subway footlong cheese": 110,
         "subway footlong spinach": 10, "subway footlong tomato": 15, "subway footlong onion": 15,
         "subway footlong smokey bbq sauce": 120}


def _parser(order):
    async def parse(query):
        return order
    return parse


def test_subway_sub_built_from_parts(world, monkeypatch):
    monkeypatch.setattr(server, "_parse_order", _parser([{"item": "Subway Footlong Steak & Cheese on rye",
                                                         "qty": 1, "parts": list(PARTS)}]))

    async def web(query, country):
        world["calls"].append(("web", query, country))
        cal = PARTS.get(query.lower())
        return {"name": query.title(), "calories": cal, "protein": 1, "carbs": 1, "fats": 1, "verified": True,
                "source": "subway.com/en-AU"} if cal else None
    monkeypatch.setattr(server, "_web_lookup", web)
    r = run(server.lookup_food(SUB, "AU"))
    assert r["calories"] == sum(PARTS.values()) and r["lookup"] == "web"
    assert len([c for c in world["calls"] if c[0] == "web"]) == len(PARTS)
    # every part is saved: a different sub with the same parts needs no new search
    monkeypatch.setattr(server, "_parse_order", _parser([{"item": "Subway Footlong Steak", "qty": 1,
                                                         "parts": ["subway footlong rye bread",
                                                                   "subway footlong steak"]}]))
    n = len(world["calls"])
    assert run(server.lookup_food("subway footlong steak on rye", "AU"))["calories"] == 640
    assert len(world["calls"]) == n


def test_missing_part_falls_back_to_whole_item(world, monkeypatch):
    monkeypatch.setattr(server, "_parse_order", _parser([{"item": "Subway Footlong Mystery Sub", "qty": 1,
                                                         "parts": ["subway footlong mystery bread"]}]))
    world["found"]["ai_estimate"] = {"name": "Footlong", "calories": 800, "protein": 40, "carbs": 90, "fats": 25}
    r = run(server.lookup_food("subway footlong mystery sub with mystery bread", "AU"))
    assert r["calories"] == 800 and r["lookup"] == "ai_estimate"


def test_two_menu_items_from_parser(world, monkeypatch):
    monkeypatch.setattr(server, "_parse_order", _parser([{"item": "Hungry Jack's Whopper", "qty": 1, "parts": []},
                                                        {"item": "Hungry Jack's Large Chips", "qty": 2, "parts": []}]))
    world["found"]["web"] = {**SHAKE, "calories": 500}
    r = run(server.lookup_food("hungry jacks whopper and 2 large chips", "AU"))
    assert r["calories"] == 1500


# ── Snap fair-use cap ───────────────────────────────────────────────────────
def test_snap_daily_cap(monkeypatch):
    used = []

    class Usage:
        async def count_documents(self, q):
            return len([u for u in used if u["user_id"] == q["user_id"] and u["created_at"] >= q["created_at"]["$gte"]])

        async def insert_one(self, d):
            used.append(d)

    class DB:
        snap_usage = Usage()

    async def ok(_):
        return {"has_access": True}
    monkeypatch.setattr(server, "db", DB())
    monkeypatch.setattr(server, "check_subscription_access", ok)
    for _ in range(server.SNAP_DAILY_LIMIT):
        used.append({"user_id": "u", "created_at": datetime.utcnow() - timedelta(hours=2)})
    req = server.FoodImageAnalyzeRequest(user_id="u", image_base64="x" * 200)
    with pytest.raises(server.HTTPException) as e:
        run(server.analyze_food_image(req))
    assert e.value.status_code == 429 and e.value.detail["error"] == "daily_limit"
    # yesterday's photos don't count
    for u in used:
        u["created_at"] -= timedelta(hours=23)
    monkeypatch.setattr(server, "call_claude_sonnet", None)   # past the cap check, the AI step runs
    try:
        run(server.analyze_food_image(req))
    except server.HTTPException as err:
        assert err.detail != {"error": "daily_limit"} and getattr(err, "status_code", 0) != 429
    except Exception:
        pass
    assert len(used) == server.SNAP_DAILY_LIMIT + 1


# ── add-ons ("with extra chicken") are their own item, never dropped ───────
@pytest.mark.parametrize("text, items", [
    ("oporto pulled chicken bowl with extra chicken", ["oporto pulled chicken bowl", "extra chicken"]),
    ("Oporto Pulled Chicken Bowl with extra chicken and extra cheese",
     ["Oporto Pulled Chicken Bowl", "extra chicken", "extra cheese"]),
    ("mcdonalds big mac add bacon", ["mcdonalds big mac", "extra bacon"]),
    ("hungry jacks whopper with cheese", ["hungry jacks whopper with cheese"]),   # menu item, not an add-on
])
def test_addons_split(text, items):
    assert [i["item"] for i in server._split_addons([{"item": text, "qty": 1, "parts": []}])] == items


def test_bowl_with_extra_chicken_adds_the_extra(world, monkeypatch):
    monkeypatch.setattr(server, "_parse_order", _parser(None))   # AI read unavailable: the rules still work
    menu = {"oporto pulled chicken bowl": 620, "oporto extra chicken": 150}

    async def web(query, country):
        world["calls"].append(("web", query, country))
        cal = menu.get(query.lower())
        return {"name": query.title(), "calories": cal, "protein": 10, "carbs": 10, "fats": 5,
                "verified": True, "source": "oporto.com.au"} if cal else None
    monkeypatch.setattr(server, "_web_lookup", web)
    r = run(server.lookup_food("oporto pulled chicken bowl with extra chicken", "AU"))
    assert r["calories"] == 770 and [i["calories"] for i in r["items"]] == [620, 150]


@pytest.mark.parametrize("text, items", [
    ("big mac but with bacon", ["big mac", "extra bacon"]),
    ("add bacon to my big mac", ["big mac", "extra bacon"]),
    ("big mac with added bacon", ["big mac", "extra bacon"]),
    ("mcdonalds extra large fries", ["mcdonalds extra large fries"]),            # a size, not an add-on
    ("kfc zinger burger with a side of chips", ["kfc zinger burger", "chips"]),
    ("maccas cheeseburger with extra pickles and extra cheese",
     ["maccas cheeseburger", "extra pickles", "extra cheese"]),                # each add-on once
    ("big mac no pickles", ["big mac no pickles"]),
])
def test_addon_phrasings(text, items):
    import re
    order = [{"item": x.strip(), "qty": 1, "parts": []}
             for x in re.split(r"\s*(?:,|;|\+|&|\band\b|\bplus\b)\s*", server._normalise_order(text)) if x.strip()]
    assert [i["item"] for i in server._split_addons(order)] == items


def test_menu_items_name_their_restaurant():
    assert FL.chain_in("big mac with bacon", "AU") == "mcdonalds"
    assert FL.chain_in("whopper", "AU") == "hungry jacks" and FL.chain_in("whopper", "US") == "burger king"
    assert FL.chain_in("hungry jacks whopper", "US") == "hungry jacks"


# ── "3 weet-bix": the food is looked up once and scaled to the number typed ──
WEETBIX = {"name": "Sanitarium Weet-Bix", "calories": 105, "protein": 3.6, "carbs": 20.1, "fats": 0.4,
           "serving_size": "2 biscuits (30 g)", "serving_g": 30.0, "verified": True, "is_ai_estimate": False,
           "source": "Open Food Facts"}


def test_counted_product_scaled_from_label_serving(world):
    world["found"]["open_food_facts"] = WEETBIX
    r = run(server.lookup_food("3 weet-bix", "AU"))
    assert r["calories"] == 158 and r["protein"] == 5.4 and r["serving_g"] == 45
    assert r["serving_size"] == "3 biscuits (45g) — label serving 2 biscuits (30 g)"
    assert world["calls"][0][:2] == ("open_food_facts", "weet-bix")       # the count isn't searched
    n = len(world["calls"])
    assert run(server.lookup_food("2 Weet-Bix", "AU"))["calories"] == 105  # same saved answer, any amount
    assert run(server.lookup_food("4 x weetbix", "AU"))["calories"] in (210,)  # "weetbix" spelt as one word
    assert len(world["calls"]) == n            # "weetbix" = "Weet-Bix": no new search


def test_grams_are_not_a_count(world):
    world["found"]["web"] = {**WEETBIX, "name": "Chobani", "serving_size": "100g"}
    run(server.lookup_food("200g chobani greek yogurt", "AU"))
    assert all(c[1] != "g chobani greek yogurt" for c in world["calls"])


def test_count_without_piece_info_looks_up_as_typed(world):
    world["found"]["web"] = {**WEETBIX, "serving_size": "100g", "serving_g": 100}
    r = run(server.lookup_food("3 mystery cookies", "AU"))
    assert any(c[1] == "3 mystery cookies" for c in world["calls"]) and r["calories"] == 105


# ── any product name: one word or two, long names, plurals, short forms ────
PRODUCTS = [("Tim Tam Original Chocolate Biscuits", "Arnott's"), ("Weet-Bix Wholegrain Breakfast Cereal", "Sanitarium"),
            ("Up&Go Liquid Breakfast Chocolate", "Sanitarium"), ("Shapes Barbecue", "Arnott's"),
            ("Mint Slice", "Arnott's"), ("Nutri-Grain", "Kellogg's"), ("Tiny Teddy Choc", "Arnott's"),
            ("Le Snak Cheese", "Kraft"), ("Banana Chips Honey Coated Crunchy", "")]


@pytest.mark.parametrize("typed, product", [
    ("timtams", "Tim Tam Original Chocolate Biscuits"), ("weetbix", "Weet-Bix Wholegrain Breakfast Cereal"),
    ("up and go", "Up&Go Liquid Breakfast Chocolate"), ("up&go", "Up&Go Liquid Breakfast Chocolate"),
    ("shapes bbq", "Shapes Barbecue"), ("mintslice", "Mint Slice"), ("nutri grain", "Nutri-Grain"),
    ("tiny teddies chocolate", "Tiny Teddy Choc"), ("lesnak", "Le Snak Cheese"),
])
def test_any_name_variation_matches(typed, product):
    scored = [(FL.off_score({"product_name": n, "brands": b}, typed), n) for n, b in PRODUCTS]
    best = min((s, n) for s, n in scored if s is not None)
    assert best[1] == product


def test_generic_word_still_needs_a_close_name():
    assert FL.off_score({"product_name": "Banana Chips Honey Coated Crunchy"}, "banana") is None


def test_saved_answer_found_for_one_word_or_two(world):
    world["found"]["open_food_facts"] = {**WEETBIX, "name": "Arnott's Mint Slice", "serving_size": "1 biscuit (12 g)"}
    run(server.lookup_food("mint slice", "AU"))
    n = len(world["calls"])
    r = run(server.lookup_food("2 mintslice", "AU"))
    assert len(world["calls"]) == n and r["serving_size"].startswith("2 biscuits")
