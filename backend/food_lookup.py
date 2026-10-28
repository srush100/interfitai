"""Saved food lookups: one answer per food, per country.

A food that isn't in the food database is looked up once (Open Food Facts or
the web, an AI estimate only as a last resort) and saved. Every later search
for the same food — in any word order or spelling — returns the saved answer,
so the food log and the chat coach always show the same numbers.

Matching rules
- Same words in any order, case, plural or spacing → same food:
  "Large McDonald's Thick Shake" = "mcdonalds thickshake large".
- Words that change the food stay in the key: size, flavour, brand, type.
- Country is part of the key (a large Big Mac in Australia isn't the US one).
  A country typed in the search wins; otherwise the phone's country is used.
"""
import re
from datetime import datetime, timedelta

REFRESH_AFTER = timedelta(days=365)       # chains change recipes: re-check yearly
ESTIMATE_RETRY_AFTER = timedelta(days=7)  # an AI estimate is replaced by a real source when one is found

# Typed country words → ISO country code
COUNTRY_WORDS = {
    "australia": "AU", "australian": "AU", "aussie": "AU", "aus": "AU", "au": "AU",
    "usa": "US", "us": "US", "america": "US", "american": "US", "united states": "US",
    "uk": "GB", "britain": "GB", "british": "GB", "england": "GB", "united kingdom": "GB",
    "nz": "NZ", "new zealand": "NZ", "canada": "CA", "canadian": "CA", "ireland": "IE", "irish": "IE",
    "singapore": "SG", "south africa": "ZA", "india": "IN", "indian": "IN",
}
COUNTRY_NAMES = {"AU": "Australia", "US": "the United States", "GB": "the United Kingdom", "NZ": "New Zealand",
                 "CA": "Canada", "IE": "Ireland", "SG": "Singapore", "ZA": "South Africa", "IN": "India"}

# Words that never change which food it is
_STOP = {"a", "an", "the", "of", "from", "at", "in", "with", "my", "some", "one", "1", "please", "and", "&"}
# Written as one word or two
_COMPOUNDS = {"thick shake": "thickshake", "milk shake": "milkshake", "ice cream": "icecream",
              "hash brown": "hashbrown", "cheese burger": "cheeseburger", "chicken burger": "chickenburger",
              "pop corn": "popcorn", "hot dog": "hotdog", "frozen yoghurt": "frozenyogurt",
              "frozen yogurt": "frozenyogurt", "big mac": "bigmac", "mc flurry": "mcflurry"}
_SPELLINGS = {"yoghurt": "yogurt", "doughnut": "donut", "flavour": "flavor", "colour": "color",
              "chips": "fries", "maccas": "mcdonalds", "macca": "mcdonalds", "hj": "hungry jacks"}  # "large chips" at an Australian McDonald's = large fries
SIZE_WORDS = {"small", "medium", "regular", "large", "kids", "junior", "mini", "jumbo", "king", "xl"}

# Restaurant chains: their menus are on the web, not in packaged-food databases
CHAINS = ("mcdonald", "maccas", "kfc", "subway", "hungry jack", "burger king", "domino", "red rooster",
          "nando", "guzman", "starbucks", "grill'd", "grilld", "oporto", "zambrero", "taco bell", "wendy",
          "chipotle", "pizza hut", "dunkin", "krispy kreme", "chick-fil-a", "five guys", "in-n-out", "boost juice",
          "gloria jean", "mad mex", "schnitz", "sushi hub", "costa", "pret", "greggs", "tim hortons",
          "big mac", "whopper", "mcflurry", "mcchicken", "mcmuffin", "zinger")


def _plain(text: str) -> str:
    t = (text or "").lower().replace("’", "'")
    t = re.sub(r"'s\b", "s", t)            # mcdonald's → mcdonalds
    t = re.sub(r"[^a-z0-9%.]+", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)
    return " ".join(t.split())


def country_from(text: str, fallback: str = "") -> tuple:
    """(country code, text without the country word). A typed country wins over
    the phone's; unknown → 'INTL'."""
    t = f" {_plain(text)} "
    found = None
    for word in sorted(COUNTRY_WORDS, key=len, reverse=True):
        if f" {word} " in t:
            found = found or COUNTRY_WORDS[word]
            t = t.replace(f" {word} ", " ")
    code = found or (fallback or "").strip().upper()[:2] or "INTL"
    return code, " ".join(t.split())


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("es") and word[-3] in "sxz":
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def food_tokens(text: str) -> list:
    """Sorted, de-duplicated words that identify a food."""
    words = [_stem(_SPELLINGS.get(w, w)) for w in _plain(text).split()]
    t = f" {' '.join(words)} "
    for two, one in _COMPOUNDS.items():          # after plurals: "big macs" → "bigmac"
        t = t.replace(f" {two} ", f" {one} ")
    return sorted({w for w in t.split() if w not in _STOP})


def lookup_key(query: str, phone_country: str = "") -> tuple:
    """('AU|bigmac mcdonald', tokens, country) — the same for every spelling of the same food."""
    country, rest = country_from(query, phone_country)
    tokens = food_tokens(rest)
    return f"{country}|{' '.join(tokens)}", tokens, country


def chain_in(query: str) -> str:
    """The restaurant chain named in the text, as typed ('hungry jacks'), or ''."""
    q = _plain(query).replace("'", "")
    for c in CHAINS:
        c2 = c.replace("'", "")
        m = re.search(rf"\b{re.escape(c2)}\w*", q)
        if m and c2 not in ("big mac", "whopper", "mcflurry", "mcchicken", "mcmuffin", "zinger"):
            return m.group(0)
    return ""


def is_chain(query: str) -> bool:
    q = _plain(query)
    return any(c.replace("'", "") in q.replace("'", "") for c in CHAINS)


def is_fresh(saved: dict, now: datetime = None) -> bool:
    """A saved web / product answer is good for a year; an AI estimate for a week
    (then a real source is tried again)."""
    now = now or datetime.utcnow()
    age = now - (saved.get("updated_at") or now)
    return age < (ESTIMATE_RETRY_AFTER if saved.get("kind") == "ai_estimate" else REFRESH_AFTER)


# ── Open Food Facts (packaged foods, worldwide) ───────────────────────────
def off_match(product: dict, query_tokens: list) -> bool:
    """A product matches only if it contains every word the user typed (size
    words included) and doesn't add more than two of its own words — so
    'banana' never matches 'banana chips' plus extras, and 'large' is never
    answered with the small one."""
    name = product.get("product_name") or ""
    text = f"{name} {product.get('brands') or ''} {product.get('quantity') or ''}"
    have = set(food_tokens(text))
    if not query_tokens or not set(query_tokens) <= have:
        return False
    extra = set(food_tokens(name)) - set(query_tokens)
    return len(extra) <= 2


def off_result(product: dict) -> dict:
    """Open Food Facts product → nutrition for one serving (or 100g)."""
    n = product.get("nutriments") or {}

    def kcal(suffix):
        v = n.get(f"energy-kcal_{suffix}")
        if v in (None, ""):
            kj = n.get(f"energy-kj_{suffix}", n.get(f"energy_{suffix}"))
            v = float(kj) / 4.184 if kj not in (None, "") else None
        return float(v) if v not in (None, "") else None

    try:
        serving_g = float(product.get("serving_quantity") or 0)
    except (TypeError, ValueError):
        serving_g = 0
    per = "serving" if serving_g > 0 and kcal("serving") else "100g"
    cal = kcal(per)
    if not cal:
        return None
    g = serving_g if per == "serving" else 100.0
    brand = (product.get("brands") or "").split(",")[0].strip()
    name = (product.get("product_name") or "").strip()
    full = f"{brand} {name}".strip() if brand and brand.lower() not in name.lower() else name
    return {
        "name": full or "Product",
        "calories": round(cal),
        "protein": round(float(n.get(f"proteins_{per}") or 0), 1),
        "carbs": round(float(n.get(f"carbohydrates_{per}") or 0), 1),
        "fats": round(float(n.get(f"fat_{per}") or 0), 1),
        "serving_size": (product.get("serving_size") or f"{g:g}g") if per == "serving" else "100g",
        "serving_g": g,
        "serving_unit": "g",
        "source": "Open Food Facts",
        "source_url": f"https://world.openfoodfacts.org/product/{product.get('code')}" if product.get("code") else "",
    }
