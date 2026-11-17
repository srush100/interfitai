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
