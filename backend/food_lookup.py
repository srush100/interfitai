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
# Saved web answers from before version 2 may show a per-100g column as one
# serve: they are looked up again on the next search
LOOKUP_VERSION = 2

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
              "chips": "fries", "maccas": "mcdonalds", "macca": "mcdonalds", "hj": "hungry jacks",
              # common short forms on menus and packets
              "bbq": "barbecue", "barbeque": "barbecue", "choc": "chocolate", "choccy": "chocolate",
              "vanila": "vanilla", "straw": "strawberry"}  # "large chips" at an Australian McDonald's = large fries
SIZE_WORDS = {"small", "medium", "regular", "large", "kids", "junior", "mini", "jumbo", "king", "xl"}

# Restaurant chains: their menus are on the web, not in packaged-food databases
CHAINS = ("mcdonald", "maccas", "kfc", "subway", "hungry jack", "burger king", "domino", "red rooster",
          "nando", "guzman", "starbucks", "grill'd", "grilld", "oporto", "zambrero", "taco bell", "wendy",
          "chipotle", "pizza hut", "dunkin", "krispy kreme", "chick-fil-a", "five guys", "in-n-out", "boost juice",
          "gloria jean", "mad mex", "schnitz", "sushi hub", "costa", "pret", "greggs", "tim hortons",
          "big mac", "whopper", "mcflurry", "mcchicken", "mcmuffin", "zinger", "footlong", "foot long")


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


def _words(text: str) -> list:
    """Normalised words in the order typed ("Up&Go" → ['up', 'go'])."""
    t = (text or "").replace("&", " and ")
    return [w for w in (_stem(_SPELLINGS.get(x, x)) for x in _plain(t).split()) if w not in _STOP]


def squash(text: str) -> str:
    """The food's name with the spaces taken out, so a name written as one word
    or two is the same food: 'mint slice' = 'mintslice', 'Weet-Bix' = 'weetbix',
    'Tim Tams' = 'timtam', 'Up&Go' = 'up and go'."""
    return "".join(_words(text))


def alt_key(query: str, phone_country: str = "") -> str:
    """A second saved-answer key: the name without spaces (see squash)."""
    country, rest = country_from(query, phone_country)
    return f"{country}|{squash(rest)}"


def lookup_key(query: str, phone_country: str = "") -> tuple:
    """('AU|bigmac mcdonald', tokens, country) — the same for every spelling of the same food."""
    country, rest = country_from(query, phone_country)
    tokens = food_tokens(rest)
    return f"{country}|{' '.join(tokens)}", tokens, country


# Menu items that name their restaurant ("a big mac" is McDonald's)
_PRODUCT_CHAINS = {"big mac": "mcdonalds", "mcflurry": "mcdonalds", "mcchicken": "mcdonalds",
                   "mcmuffin": "mcdonalds", "zinger": "kfc", "footlong": "subway", "foot long": "subway"}


# "chipotle sauce", "with chipotle" is a flavour, not the Chipotle restaurant
_FLAVOUR_CHIPOTLE = re.compile(
    r"\b(?:(?:with|and|in|of|plus)\s+(?:a\s+|some\s+|extra\s+)?chipotle\b(?!\s+(?:mexican|restaurant|grill))"
    r"|chipotle\s+(?=(?:sauce|mayo|mayonnaise|aioli|dressing|pepper|peppers|seasoning|salsa|paste|powder|"
    r"marinade|ranch|glaze|dip|spice|flavou?r|chilli|chili|lime|bbq|barbecue|southwest)\b))")


def _no_flavour_chipotle(q: str) -> str:
    return _FLAVOUR_CHIPOTLE.sub(" ", q)


def chain_in(query: str, country: str = "") -> str:
    """The restaurant chain named in the text, as typed ('hungry jacks'), or the
    one a menu item belongs to ('big mac' → 'mcdonalds'; a Whopper is Hungry
    Jack's in Australia, Burger King elsewhere). '' if none."""
    q = _no_flavour_chipotle(_plain(query).replace("'", ""))
    for product, chain in _PRODUCT_CHAINS.items():
        if re.search(rf"\b{product}", q) and not any(c.replace("'", "") in q for c in CHAINS[:40]
                                                       if c not in _PRODUCT_CHAINS and c != "whopper"):
            return chain
    if re.search(r"\bwhopper", q) and "hungry jack" not in q and "burger king" not in q:
        return "hungry jacks" if (country or "").upper() == "AU" else "burger king"
    for c in CHAINS:
        c2 = c.replace("'", "")
        m = re.search(rf"\b{re.escape(c2)}\w*", q)
        if m and c2 not in ("big mac", "whopper", "mcflurry", "mcchicken", "mcmuffin", "zinger", "footlong", "foot long"):
            return m.group(0)
    return ""


def is_chain(query: str) -> bool:
    q = _no_flavour_chipotle(_plain(query).replace("'", ""))
    return any(c.replace("'", "") in q for c in CHAINS)


def is_fresh(saved: dict, now: datetime = None) -> bool:
    """A saved web / product answer is good for a year; an AI estimate for a week
    (then a real source is tried again)."""
    now = now or datetime.utcnow()
    if saved.get("kind") == "web" and (saved.get("v") or 1) < LOOKUP_VERSION:
        return False
    age = now - (saved.get("updated_at") or now)
    return age < (ESTIMATE_RETRY_AFTER if saved.get("kind") == "ai_estimate" else REFRESH_AFTER)


# ── Open Food Facts (packaged foods, worldwide) ───────────────────────────
MAX_EXTRA_WORDS = 3    # "Tim Tam Original Chocolate Biscuits" for "tim tam"


def off_score(product: dict, query: str):
    """How well a product matches what was typed: the number of extra words in
    its name (fewer = better), or None for no match. The product must contain
    every word typed (size words included, so 'large' is never answered with
    the small one) — as separate words or run together ('mintslice' = 'Mint
    Slice') — and add at most 3 words of its own ('banana' never matches
    'Banana Chips Honey Coated Crunchy')."""
    name = product.get("product_name") or ""
    brand = product.get("brands") or ""
    q_tokens = food_tokens(query)
    if not q_tokens:
        return None
    have = set(food_tokens(f"{name} {brand} {product.get('quantity') or ''}"))
    if set(q_tokens) <= have:
        extra = len(set(food_tokens(name)) - set(q_tokens))
        return extra if extra <= MAX_EXTRA_WORDS else None
    # the same words run together or split differently
    q = squash(query)
    name_w, all_w = _words(name), _words(name) + _words(brand)
    for i in range(len(all_w)):
        for j in range(i + 1, len(all_w) + 1):
            if "".join(all_w[i:j]) == q:
                extra = len(set(name_w) - set(all_w[i:j]))
                return extra if extra <= MAX_EXTRA_WORDS else None
    return None


def off_match(product: dict, query_tokens) -> bool:
    query = query_tokens if isinstance(query_tokens, str) else " ".join(query_tokens)
    return off_score(product, query) is not None


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


# ── Keyword search results (USDA list) ─────────────────────────────────────
_AMOUNT_WORDS = {"g", "gram", "kg", "ml", "l", "oz", "lb", "cup", "tbsp", "tsp", "tablespoon", "teaspoon",
                 "slice", "piece", "serve", "serving", "portion", "x", "half", "bowl", "plate", "handful"}


def _food_words(query: str, country: str = "") -> tuple:
    """(food words typed, chain words typed) — country and filler words removed."""
    _, rest = country_from(query, country)
    chain = chain_in(rest, country)
    chain_words = set(food_tokens(chain)) if chain else set()
    words = [w for w in food_tokens(rest) if w not in chain_words and w not in SIZE_WORDS
             and w not in _AMOUNT_WORDS and not re.fullmatch(r"[\d.%]+[a-z]{0,2}", w)]
    return words, chain_words


def relevant_results(results: list, query: str, country: str = "") -> list:
    """Keyword results that are about the food typed, best match first.

    - A result must share most of the words typed: 'big chicken burrito with
      chipotle sauce' never lists 'Fast foods, chicken tenders' or 'Cheese
      sauce mix, dry' just because one word is the same.
    - When a restaurant is named, other restaurants' and generic items are
      dropped unless they have every word typed — the restaurant's own item is
      found by the exact-match lookup instead.
    - If the filter would leave almost nothing for an everyday food, the list
      is kept (re-ordered) so a food written differently in the database isn't lost."""
    words, chain_words = _food_words(query, country)
    if not words or not results:
        return results
    need = len(words) if len(words) <= 2 else max(2, -(-len(words) * 6 // 10))   # 60%, rounded up

    def score(r):
        have = set(food_tokens(r.get("name", "")))
        names_chain = bool(chain_words) and bool(chain_words & have)
        return sum(1 for w in words if w in have), names_chain

    scored = [(score(r), i, r) for i, r in enumerate(results)]
    scored.sort(key=lambda t: (-t[0][0], t[1]))
    if chain_words:
        return [r for (n, named), _, r in scored if n == len(words) or (named and n >= max(1, len(words) - 1))]
    kept = [r for (n, _), _, r in scored if n >= need]
    return kept if len(kept) >= 3 else [r for _, _, r in scored]


# File hosts that say nothing about where the figures come from
_FILE_HOSTS = ("cloudfront.net", "amazonaws.com", "googleusercontent.com", "ctfassets.net", "azureedge.net",
               "akamaized.net", "blob.core.windows.net", "storage.googleapis.com", "squarespace-cdn.com",
               "shopify.com", "wp-content", "prismic.io", "contentful.com")


_CHAIN_NAMES = {"mcdonald": "McDonald's", "maccas": "McDonald's", "kfc": "KFC", "subway": "Subway",
                "hungry jack": "Hungry Jack's", "burger king": "Burger King", "domino": "Domino's",
                "red rooster": "Red Rooster", "nando": "Nando's", "guzman": "Guzman y Gomez",
                "starbucks": "Starbucks", "grill": "Grill'd", "oporto": "Oporto", "zambrero": "Zambrero",
                "taco bell": "Taco Bell", "wendy": "Wendy's", "chipotle": "Chipotle", "pizza hut": "Pizza Hut",
                "boost juice": "Boost Juice", "mad mex": "Mad Mex", "schnitz": "Schnitz", "greggs": "Greggs",
                "five guys": "Five Guys", "krispy kreme": "Krispy Kreme", "tim hortons": "Tim Hortons"}


def source_label(url: str, query: str = "", country: str = "") -> str:
    """A readable source name: the website ('mcdonalds.com.au'), or the
    restaurant's name for a document on a file host ('Zambrero nutrition
    document' instead of 'dph95f73vdxmz.cloudfront.net')."""
    from urllib.parse import urlparse
    if not url:
        return "web"
    host = urlparse(url).netloc.lower().replace("www.", "")
    if not any(h in url.lower() for h in _FILE_HOSTS):
        return host or "web"
    chain = chain_in(query, country)
    name = next((v for k, v in _CHAIN_NAMES.items() if chain.startswith(k)), "") if chain else ""
    name = name or " ".join(w.capitalize() for w in chain.split())
    return f"{name} nutrition document" if name else "Nutrition document"
