"""
Food search on TestFlight (12 Nov): 'big chicken burrito with chipotle sauce
zambreros' listed chicken tenders, cheese sauce mix and another brand's
burrito, and the web answer showed the per-100g column as one burrito
(232 cal) with a file-host name as the source.
"""
from datetime import datetime

import server
import food_lookup as FL

Q = "big chicken burrito with chipotle sauce zambreros"
USDA = [
    {"name": "Fast foods, chicken tenders (100g)"},
    {"name": "Sauce, cheese sauce mix, dry (100g)"},
    {"name": "EVOL. - SRIRACHA CHICKEN BIG BURRITO, SRIRACHA CHICKEN (298g)"},
    {"name": "SUBWAY, sweet onion chicken teriyaki sub on white bread with lettuce, tomato and sweet onion sauce (100g)"},
]


# ── keyword results ────────────────────────────────────────────────────────
def test_restaurant_search_drops_unrelated_results():
    assert FL.relevant_results(USDA, Q, "AU") == []


def test_restaurant_search_keeps_its_own_item():
    own = {"name": "Zambrero Big Chicken Burrito, chipotle sauce"}
    assert FL.relevant_results(USDA + [own], Q, "AU") == [own]


def test_everyday_food_best_match_first():
    res = [{"name": "Fast foods, chicken tenders"}, {"name": "Chicken, broilers or fryers, breast, meat only, cooked"},
           {"name": "Chicken breast tenders, breaded"}, {"name": "Chicken breast, roasted"}]
    out = FL.relevant_results(res, "chicken breast", "AU")
    assert out[0]["name"].startswith("Chicken, broilers") and {"name": "Fast foods, chicken tenders"} not in out


def test_everyday_food_never_left_empty():
    res = [{"name": "Beef, ground, 85% lean, cooked"}, {"name": "Beef, ground, 95% lean, raw"}]
    assert FL.relevant_results(res, "beef mince", "AU") == res      # written differently: kept


def test_single_word_untouched():
    res = [{"name": "Broccoli, raw"}, {"name": "Broccoli, cooked, boiled"}]
    assert FL.relevant_results(res, "broccoli", "AU") == res


# ── 'chipotle' the flavour vs the restaurant ───────────────────────────────
def test_chipotle_sauce_is_not_the_restaurant():
    assert FL.chain_in(Q, "AU") == "zambreros"
    assert not FL.is_chain("chicken burrito with chipotle sauce")
    assert not FL.is_chain("chipotle mayo")
    assert FL.is_chain("chipotle burrito bowl")


# ── web answer: per serve, not per 100 g ───────────────────────────────────
def _col(c, p, cb, f):
    return {"calories": c, "protein_g": p, "carbs_g": cb, "fat_g": f}


def test_per_serve_used():
    d = server._web_serving({"food_name": "Zambrero Big Chicken Burrito", "serving_size": "1 burrito", "serving_g": 410,
                             "per_serve": _col(951, 48, 63, 57), "per_100g": _col(232, 11.7, 15.3, 13.8)})
    assert d["calories"] == 951 and d["serving_size"] == "1 burrito (410g)"


def test_per_100g_copied_into_per_serve_is_scaled():
    d = server._web_serving({"serving_size": "1 burrito", "serving_g": 410,
                             "per_serve": _col(232, 11.7, 15.3, 13.8), "per_100g": _col(232, 11.7, 15.3, 13.8)})
    assert round(d["calories"]) == 951 and round(d["protein_g"]) == 48


def test_only_per_100g_with_weight_is_scaled():
    d = server._web_serving({"serving_size": "1 burrito (410g)", "per_serve": None,
                             "per_100g": _col(232, 11.7, 15.3, 13.8)})
    assert round(d["calories"]) == 951


def test_only_per_100g_without_weight_says_100g():
    d = server._web_serving({"serving_size": "1 burrito", "per_100g": _col(232, 11.7, 15.3, 13.8)})
    assert d["calories"] == 232 and d["serving_size"] == "100g"


def test_old_flat_answer_still_works():
    d = server._web_serving({"calories": 540, "protein_g": 25, "carbs_g": 45, "fat_g": 28, "serving_size": "1 burger"})
    assert d["calories"] == 540


def test_source_must_be_a_search_result():
    urls = ["https://a.com/x", "https://dph95f73vdxmz.cloudfront.net/zambrero.pdf"]
    d = server._web_serving({"per_serve": _col(900, 40, 60, 50), "source_url": urls[1]}, urls)
    assert d["source_url"] == urls[1]
    d = server._web_serving({"per_serve": _col(900, 40, 60, 50), "source_url": "https://made-up.com"}, urls)
    assert d["source_url"] == ""


def test_source_label():
    assert FL.source_label("https://dph95f73vdxmz.cloudfront.net/z.pdf", Q, "AU") == "Zambrero nutrition document"
    assert FL.source_label("https://www.mcdonalds.com.au/menu/big-mac", "big mac", "AU") == "mcdonalds.com.au"
    assert FL.source_label("https://x.cloudfront.net/a.pdf", "weetbix", "AU") == "Nutrition document"


# ── answers saved before the fix are looked up again ───────────────────────
def test_old_web_answers_rechecked():
    now = datetime.utcnow()
    assert not FL.is_fresh({"kind": "web", "updated_at": now})
    assert FL.is_fresh({"kind": "web", "updated_at": now, "v": FL.LOOKUP_VERSION})
    assert FL.is_fresh({"kind": "open_food_facts", "updated_at": now})
