"""Subway orders (17 Nov): 'footlong' means Subway even when the restaurant
isn't typed, and a sub with no bread named gets Subway's standard white bread
at the sub's size, so the total isn't 300-500 calories short."""
import server
import food_lookup as F


def test_footlong_means_subway():
    q = "chicken teriyaki footlong with sweet onion sauce, tomato, onion and lettuce"
    assert F.chain_in(q, "AU") == "subway" and F.is_chain(q)
    assert F.chain_in("foot long meatball", "AU") == "subway"


def test_bread_added_when_none_named():
    order = [{"item": "subway footlong chicken teriyaki", "qty": 1,
              "parts": ["subway footlong chicken teriyaki", "subway footlong lettuce"]}]
    assert server._add_sub_bread(order, "subway")[0]["parts"][0] == "subway footlong white bread"
    six = [{"item": "subway 6 inch ham", "qty": 1, "parts": ["subway 6 inch ham"]}]
    assert server._add_sub_bread(six, "subway")[0]["parts"][0] == "subway 6 inch white bread"


def test_named_bread_wrap_or_bowl_left_alone():
    for parts in (["subway footlong rye bread", "subway footlong steak"],
                  ["subway footlong multigrain", "subway footlong steak"]):
        order = [{"item": "subway footlong steak", "qty": 1, "parts": parts}]
        assert server._add_sub_bread(order, "subway")[0]["parts"] == parts
    bowl = [{"item": "subway rice bowl korean bbq steak", "qty": 1, "parts": ["subway korean bbq steak"]}]
    assert server._add_sub_bread(bowl, "subway")[0]["parts"] == ["subway korean bbq steak"]


def test_other_restaurants_and_plain_items_untouched():
    order = [{"item": "guzman burrito", "qty": 1, "parts": ["guzman chicken"]}]
    assert server._add_sub_bread(order, "guzman") == order
    plain = [{"item": "subway cookie", "qty": 1, "parts": []}]
    assert server._add_sub_bread(plain, "subway") == plain


def test_addon_without_with_or_and_is_its_own_item():
    import asyncio, json
    q = "zambreros big burrito chipotle sauce extra chicken"
    looked = []

    async def web(qq, c):
        looked.append(qq)
        return {"name": qq, "calories": 100, "protein": 5, "carbs": 10, "fats": 2, "serving_size": "1",
                "verified": True, "source": "zambrero.com.au", "source_url": "https://www.zambrero.com.au"}

    async def none(qq, c):
        return None

    async def haiku(*a, **k):          # the reader fails → the code's own split is used
        raise RuntimeError("unavailable")

    class Coll:
        async def find_one(s, *a, **k): return None
        async def create_index(s, *a, **k): pass
        async def update_one(s, *a, **k): pass

    class DB:
        food_lookups = Coll()

    old = (server._off_lookup, server._web_lookup, server.call_claude_haiku, server.db)
    server._off_lookup, server._web_lookup, server.call_claude_haiku, server.db = none, web, haiku, DB()
    try:
        r = asyncio.run(server.lookup_food(q, "AU"))
    finally:
        server._off_lookup, server._web_lookup, server.call_claude_haiku, server.db = old
    assert looked == ["zambreros big burrito chipotle sauce", "zambreros extra chicken"]
    assert r["calories"] == 200


def test_double_menu_items_stay_whole():
    for t in ("mcdonalds double cheeseburger", "hungry jacks double whopper", "kfc double down"):
        assert [i["item"] for i in server._split_addons([{"item": t, "qty": 1, "parts": []}])] == [t]
    assert [i["item"] for i in server._split_addons([{"item": "big mac with double patty", "qty": 1, "parts": []}])] \
        == ["big mac", "double patty"]
