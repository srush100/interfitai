"""InterFitAI meal-plan nutrition engine.

Pure, deterministic code — no AI calls, no database. The AI only ever chooses
foods and gram amounts; everything numeric shown to the user is calculated here
from food_database.INGREDIENT_MACROS:

  ingredient macros = grams / 100 × per-100g reference values
  meal macros       = sum of its listed ingredients
  day totals        = sum of its meals

so the numbers on screen always match the food that is listed.
"""
import logging
import math
import re

from food_database import INGREDIENT_MACROS

logger = logging.getLogger(__name__)

TOLERANCE = 0.05          # a day is "on target" when every macro is within 5%
MACRO_FLOOR_G = 2.0       # absolute slack (g) for tiny targets, e.g. carnivore carbs
MEAL_SHARES = {"breakfast": 0.25, "lunch": 0.30, "dinner": 0.35, "snack": 0.10}
MACRO_KEYS = ("calories", "protein", "carbs", "fats")


# ════════════════════════════════════════════════════════════════════════════
# 1. FOOD NAME → DATABASE ENTRY
# ════════════════════════════════════════════════════════════════════════════
_WORD_SYNONYMS = {
    "yoghurt": "yogurt", "chilli": "chili", "aubergine": "eggplant",
    "courgette": "zucchini", "coriander": "cilantro", "rocket": "arugula",
    "beetroot": "beets", "garbanzo": "chickpeas", "soya": "soy",
}
# Generic table keys that must never be a fuzzy-match target
# ("high protein pasta" must not become protein powder).
_RESOLVER_SKIP = {"protein"}


def _stem(word: str) -> str:
    """Light plural stemmer — strawberries→strawberry, tomatoes→tomato, oats→oat."""
    w = word
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith("oes"):
        return w[:-2]
    if len(w) > 4 and w.endswith(("ches", "shes", "sses")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _tokens(text: str) -> list:
    t = (text or "").lower().replace("&", " and ")
    t = re.sub(r"(\d{2})\s*%\s*lean", lambda m: f" {m.group(1)}/{100 - int(m.group(1))} ", t)
    toks = re.findall(r"\d+/\d+|\d+(?:\.\d+)?%|[a-z]+", t)
    return [_WORD_SYNONYMS.get(x, x) for x in toks]


_KEY_STEMS = {k: frozenset(_stem(x) for x in _tokens(k)) for k in INGREDIENT_MACROS}

_BEEF_RATIO = {
    "96/4": "beef mince 95/5", "95/5": "beef mince 95/5", "93/7": "beef mince 95/5",
    "90/10": "beef mince 90/10", "88/12": "beef mince 90/10", "85/15": "beef mince 90/10",
    "80/20": "beef mince 80/20", "75/25": "beef mince 80/20", "70/30": "beef mince 80/20",
}


def resolve_food(name: str):
    """Map a free-text food name to an INGREDIENT_MACROS key, or None.

    Whole-word matching only: "eggplant" never matches "egg", "strawberries"
    keeps every letter, "baked beans" beats "green beans". The most specific
    entry wins ("chicken breast" over "chicken", "almond milk" over "milk")."""
    toks = _tokens(name)
    if not toks:
        return None
    tokset = set(toks)
    ratio = next((x for x in toks if x in _BEEF_RATIO), None)
    if ratio and tokset & {"beef", "mince", "ground", "burger", "patty"} and not tokset & {"turkey", "chicken", "lamb", "pork"}:
        return _BEEF_RATIO[ratio]
    flat = " ".join(toks)
    if flat in INGREDIENT_MACROS:
        return flat
    stems = {_stem(x) for x in toks}
    best, best_score = None, None
    for key, kst in _KEY_STEMS.items():
        if key in _RESOLVER_SKIP or not kst or not kst <= stems:
            continue
        score = (len(kst), len(key))
        if best_score is None or score > best_score:
            best, best_score = key, score
    return best


def macros_for(key: str, grams: float) -> dict:
    """Macros for `grams` of a database food (per-ingredient rounding: whole
    calories, 0.1g macros — the same rounding the screen shows)."""
    cal, pro, carb, fat = INGREDIENT_MACROS[key]
    f = grams / 100.0
    return {"calories": round(cal * f), "protein": round(pro * f, 1),
            "carbs": round(carb * f, 1), "fats": round(fat * f, 1)}


# ════════════════════════════════════════════════════════════════════════════
# 2. AMOUNT PARSING — everything becomes grams
# ════════════════════════════════════════════════════════════════════════════
# Grams per single item (medium size unless stated). Unknown count items are
# REJECTED instead of being guessed as 100g.
ITEM_WEIGHTS = {
    "egg": 58, "eggs": 58, "whole eggs": 58, "large eggs": 58, "egg white": 33, "egg whites": 33,
    "banana": 120, "bananas": 120, "apple": 180, "apples": 180, "orange": 130, "oranges": 130,
    "pear": 178, "peach": 150, "nectarine": 142, "plum": 66, "apricot": 35, "kiwi": 70, "fig": 50,
    "dates": 24, "strawberry": 12, "strawberries": 12, "lime": 67, "lemon": 58,
    "rice cake": 9, "rice cakes": 9, "tortilla": 45, "wrap": 60, "whole wheat wrap": 60,
    "corn tortilla": 26, "corn tortillas": 26, "pita bread": 60, "whole wheat pita": 60,
    "bagel": 105, "english muffin": 57, "naan": 90, "bread": 30, "whole wheat bread": 30,
    "toast": 30, "whole wheat toast": 30, "sourdough bread": 30, "rye bread": 30,
    "chicken breast": 175, "chicken thigh": 110, "chicken thighs": 110, "steak": 225,
    "pork sausage": 75, "bacon": 8, "turkey bacon": 15,
    "garlic": 4, "ginger": 5, "shallot": 20, "tomato": 120, "tomatoes": 120,
    "cherry tomatoes": 17, "avocado": 150, "onion": 110, "red onion": 110,
    "bell pepper": 120, "pepper": 120, "jalapeno": 14, "mushroom": 90, "mushrooms": 90,
    "carrot": 80, "carrots": 80, "zucchini": 196, "potato": 180, "potatoes": 180,
    "sweet potato": 130, "cucumber": 300, "almonds": 1.2, "almond": 1.2, "walnuts": 4,
    "brazil nuts": 5, "olives": 4, "falafel": 17,
}
# Foods bought and cooked as whole units: portions always end on whole units
# and are shown as e.g. "2 large eggs (116g)".
# key → (grams per unit, singular, plural); None names = "N slice(s) <label>".
UNIT_FOODS = {k: (58, "large egg", "large eggs") for k in ("egg", "eggs", "whole eggs", "large eggs")}
UNIT_FOODS.update({k: (30, None, None) for k in ("bread", "whole wheat bread", "sourdough bread", "rye bread",
                                                   "toast", "whole wheat toast")})
UNIT_FOODS.update({
    "tortilla": (45, "tortilla", "tortillas"), "corn tortilla": (26, "corn tortilla", "corn tortillas"),
    "corn tortillas": (26, "corn tortilla", "corn tortillas"), "wrap": (60, "wrap", "wraps"),
    "whole wheat wrap": (60, "whole wheat wrap", "whole wheat wraps"), "pita bread": (60, "pita bread", "pita breads"),
    "whole wheat pita": (60, "whole wheat pita", "whole wheat pitas"), "bagel": (105, "bagel", "bagels"),
    "english muffin": (57, "English muffin", "English muffins"), "naan": (90, "naan", "naans"),
    "rice cake": (9, "rice cake", "rice cakes"), "rice cakes": (9, "rice cake", "rice cakes"),
})


def unit_grams(key: str):
    """Grams per whole unit for foods portioned in units (eggs, slices…), else None."""
    u = UNIT_FOODS.get(key)
    return u[0] if u else None


_SIZE_FACTORS = {"small": 0.8, "medium": 1.0, "large": 1.25, "extra large": 1.4}
_EGG_SIZES = {"small": 42, "medium": 50, "large": 58, "extra large": 66, "jumbo": 70}
_SLICE_WEIGHTS = [({"bread", "toast", "sourdough", "rye", "ciabatta"}, 30), ({"bacon"}, 8),
                  ({"turkey", "ham"}, 28), ({"cheese", "cheddar", "mozzarella", "gouda", "brie", "halloumi"}, 20),
                  ({"tomato"}, 20), ({"avocado"}, 30), ({"pineapple"}, 80)]
# Grams per US cup, chosen by the food (1 cup of spinach is not 1 cup of honey).
_CUP_WEIGHTS = [
    ({"milk", "kefir", "broth", "juice", "water"}, 244), ({"yogurt", "skyr"}, 245),
    ({"cottage"}, 226), ({"ricotta"}, 246), ({"oil"}, 218), ({"honey"}, 339), ({"syrup", "agave"}, 315),
    ({"butter"}, 227), ({"cream"}, 238), ({"granola"}, 122), ({"muesli"}, 85), ({"oat"}, 81),
    ({"oatmeal", "porridge"}, 234), ({"rice"}, 158), ({"quinoa"}, 185), ({"couscous"}, 157),
    ({"pasta", "spaghetti", "orzo"}, 140), ({"noodle"}, 160), ({"flour"}, 125),
    ({"lentil"}, 198), ({"bean", "chickpea", "pea", "edamame"}, 165),
    ({"spinach", "arugula", "lettuce", "green", "kale", "romaine"}, 30),
    ({"broccoli"}, 91), ({"cauliflower"}, 107), ({"blueberry", "berry", "berries", "blackberry"}, 148),
    ({"strawberry"}, 152), ({"raspberry"}, 123), ({"grape"}, 151), ({"mango", "pineapple", "papaya"}, 165),
    ({"almond", "walnut", "cashew", "peanut", "nut", "pecan", "hazelnut", "pistachio", "seed"}, 140),
    ({"cheese", "cheddar", "mozzarella", "parmesan", "feta"}, 113), ({"salsa", "sauce", "marinara", "hummus"}, 250),
    ({"powder", "protein", "whey"}, 100), ({"sugar"}, 200),
]
_DENSITY = [({"honey"}, 1.42), ({"syrup", "agave", "molasses"}, 1.33), ({"oil", "tallow", "lard", "ghee"}, 0.92),
            ({"soy", "tamari", "aminos", "teriyaki", "hoisin"}, 1.15), ({"cream"}, 1.0), ({"butter"}, 0.91)]


def _lookup_by_tokens(key: str, table, default=None):
    st = {_stem(t) for t in _tokens(key)}
    for words, value in table:
        if st & {_stem(w) for w in words}:
            return value
    return default


def _item_weight(key: str, size: str = None):
    if key in ("egg", "eggs", "whole eggs", "large eggs"):
        return _EGG_SIZES.get(size or "large", 58)
    w = ITEM_WEIGHTS.get(key)
    if w is None:
        return None
    return w * _SIZE_FACTORS.get(size or "medium", 1.0)


_UNICODE_FRACTIONS = {"½": ".5", "¼": ".25", "¾": ".75", "⅓": ".333", "⅔": ".667", "⅛": ".125"}
_NUM = r"(\d+(?:\.\d+)?)"


def _normalise_amount_text(s: str) -> str:
    for u, d in _UNICODE_FRACTIONS.items():
        s = re.sub(rf"(\d)\s*{u}", lambda m, d=d: str(float(m.group(1)) + float(d)), s)
        s = s.replace(u, "0" + d)
    s = re.sub(r"\b(\d+)\s+([1-7])/([2348])\b",
               lambda m: str(int(m.group(1)) + int(m.group(2)) / int(m.group(3))), s)
    s = re.sub(r"(?<![\d/])\b([1-7])/([2348])\b(?![\d/])",
               lambda m: str(int(m.group(1)) / int(m.group(2))) if int(m.group(1)) < int(m.group(2)) else m.group(0), s)
    s = re.sub(r"^\s*(a|an|one)\s+", "1 ", s)
    return s


def _clean_label(s: str) -> str:
    s = re.sub(r"\(\s*\)", " ", s)
    s = re.sub(r"^\s*of\s+", "", s)
    s = re.sub(r"^[\s,.\-–:]+|[\s,.\-–:]+$", "", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def parse_ingredient(text: str):
    """Parse '200g greek yogurt', '15ml honey', '1 scoop whey protein',
    '2 rice cakes', '1 cup cooked rice', '1 medium banana (100g)' …

    Returns (label, grams, key) or None when the food or amount can't be
    determined. An explicit gram weight always wins over a count."""
    if not text or not str(text).strip():
        return None
    s = _normalise_amount_text(str(text).strip().lower())

    # 1. explicit weight anywhere in the string — "100g", "(100 g)", "100 grams", kg/oz/lb
    m = re.search(rf"{_NUM}\s*(kg|kilograms?|g|gr|grams?|oz|ounces?|lbs?|pounds?)\b", s)
    if m:
        unit = m.group(2)
        mult = 1000 if unit.startswith("k") else 28.35 if unit.startswith(("oz", "ounce")) else 453.6 if unit.startswith(("lb", "pound")) else 1
        grams = float(m.group(1)) * mult
        rest = s[:m.start()] + " " + s[m.end():]
        rest = re.sub(rf"^\s*{_NUM}\s*(x\s+)?(small|medium|large|extra large)?\s*(slices?\s+(of\s+)?)?", "", rest)
        label = _clean_label(rest)
        key = resolve_food(label)
        return (label, grams, key) if key else None

    # 2. volume — ml / l / cups / tbsp / tsp, converted per food
    m = re.match(rf"^\s*{_NUM}\s*(ml|millilit(?:re|er)s?|l|lit(?:re|er)s?|cups?|tbsps?|tablespoons?|tsps?|teaspoons?)\b\.?\s*(?:of\s+)?(.+)$", s)
    if m:
        amount, unit, label = float(m.group(1)), m.group(2), _clean_label(m.group(3))
        key = resolve_food(label)
        if not key:
            return None
        if unit.startswith(("ml", "milli")) or unit in ("l",) or unit.startswith("lit"):
            ml = amount * (1000 if (unit == "l" or unit.startswith("lit")) else 1)
            return label, ml * _lookup_by_tokens(key, _DENSITY, 1.0), key
        cup = _lookup_by_tokens(key, _CUP_WEIGHTS, 150)
        per = cup if unit.startswith("cup") else cup / 16 if unit.startswith(("tbsp", "tablespoon")) else cup / 48
        return label, amount * per, key

    # 3. scoops / slices / pinches
    m = re.match(rf"^\s*{_NUM}\s*(scoops?|slices?|pinch(?:es)?|dash(?:es)?)\s+(?:of\s+)?(.+)$", s)
    if m:
        amount, unit, label = float(m.group(1)), m.group(2), _clean_label(m.group(3))
        key = resolve_food(label)
        if not key:
            return None
        if unit.startswith("scoop"):
            return label, amount * 30, key
        if unit.startswith(("pinch", "dash")):
            return label, amount * 0.5, key
        per = _lookup_by_tokens(key, _SLICE_WEIGHTS)
        return (label, amount * per, key) if per else None

    # 4. seasoning "to taste"
    if re.search(r"\bto taste\b", s):
        label = _clean_label(re.sub(r"\bto taste\b", "", s))
        key = resolve_food(label)
        return (label, 0.5, key) if key else None

    # 5. counts — "3 large eggs", "2 rice cakes", "1 medium banana"
    m = re.match(rf"^\s*{_NUM}\s*(?:x\s+)?(small|medium|large|extra large|jumbo|whole(?!\s+(?:wheat|grain|milk|food))|pieces?|pcs?)?\s*(?:of\s+)?(.+)$", s)
    if m:
        amount, size, label = float(m.group(1)), m.group(2), _clean_label(m.group(3))
        if size in ("whole", "piece", "pieces", "pc", "pcs"):
            size = None
        key = resolve_food(label)
        if not key:
            return None
        per = _item_weight(key, size)
        if per is None:
            logger.warning(f"No per-item weight for '{text}' (food '{key}') — rejected, not guessed")
            return None
        return label, amount * per, key
    return None


def calculate_ingredient_macros(ingredient_str):
    """Macros for one ingredient string, e.g. '250g sweet potato' or '3 large eggs'.
    Returns {"calories","protein","carbs","fats"} or None if it can't be resolved."""
    parsed = parse_ingredient(ingredient_str)
    if not parsed:
        logger.warning(f"Could not resolve ingredient: '{ingredient_str}'")
        return None
    _label, grams, key = parsed
    return macros_for(key, grams)


def unit_text(label: str, grams: float, key: str = None):
    """'2 large eggs' / '3 slices sourdough bread' when `grams` is a whole number
    of a whole-unit food's units, else None."""
    unit = UNIT_FOODS.get(key)
    if unit:
        n = grams / unit[0]
        if n >= 1 and abs(n - round(n)) < 1e-6:
            n = int(round(n))
            if unit[1] is None:
                return f"{n} slice{'s' if n != 1 else ''} {label.lower()}"
            return f"{n} {unit[1] if n == 1 else unit[2]}"
    return None


def format_ingredient(label: str, grams: float, key: str = None) -> str:
    """'245g Sweet potato', or for whole-unit foods '2 large eggs (116g)' /
    '2 slices sourdough bread (60g)'. Both forms parse back to the same grams."""
    g = round(grams, 1)
    g_txt = str(int(g)) if float(g).is_integer() else f"{g}"
    units = unit_text(label, grams, key)
    return f"{units} ({g_txt}g)" if units else f"{g_txt}g {label}"


# ════════════════════════════════════════════════════════════════════════════
# 3. ALLERGENS, FOODS TO AVOID & DIET RULES
# ════════════════════════════════════════════════════════════════════════════
_DAIRY = ["milk", "cheese", "yogurt", "cream", "butter", "whey", "casein", "lactose", "ghee", "kefir",
          "skyr", "parmesan", "mozzarella", "ricotta", "halloumi", "paneer", "cheddar", "feta", "brie",
          "camembert", "gouda", "mascarpone", "quark", "burrata", "custard", "labneh", "gelato",
          "curd", "queso", "pecorino", "provolone", "emmental", "creme fraiche", "tzatziki", "raita",
          "alfredo", "bechamel", "buttermilk", "cheesecake", "milkshake"]
_GLUTEN = ["gluten", "wheat", "flour", "bread", "toast", "pasta", "spaghetti", "macaroni", "lasagna",
           "noodle", "ramen", "udon", "soba", "orzo", "couscous", "semolina", "bulgur", "farro", "freekeh",
           "barley", "rye", "spelt", "kamut", "durum", "seitan", "bagel", "naan", "pita", "ciabatta",
           "sourdough", "baguette", "bun", "croissant", "brioche", "muffin", "pancake", "waffle",
           "cracker", "crispbread", "crouton", "breadcrumb", "panko", "pretzel", "pastry", "pizza",
           "dumpling", "gnocchi", "tortilla", "wrap", "granola", "muesli", "cereal", "oat", "oatmeal",
           "porridge", "soy sauce", "teriyaki", "hoisin", "malt", "beer", "cake", "cookie", "biscuit"]
_EGGS = ["egg", "mayonnaise", "mayo", "aioli", "omelette", "omelet", "frittata", "meringue", "quiche",
         "custard", "brioche", "hollandaise", "shakshuka"]
_TREE_NUTS = ["almond", "cashew", "walnut", "pecan", "hazelnut", "pistachio", "macadamia", "brazil nut",
              "pine nut", "chestnut", "praline", "marzipan", "nutella", "nut butter", "nut milk", "pesto"]
_PEANUTS = ["peanut", "groundnut", "satay"]
_SOY = ["soy", "soybean", "tofu", "tempeh", "edamame", "miso", "tamari", "natto", "soy sauce", "teriyaki",
        "hoisin", "tvp", "textured vegetable protein", "bean curd"]
_SHELLFISH = ["shellfish", "prawn", "shrimp", "crab", "lobster", "oyster", "mussel", "scallop", "clam",
              "crayfish", "crawfish", "langoustine", "squid", "calamari", "octopus"]
_FISH = ["fish", "salmon", "tuna", "cod", "tilapia", "bass", "trout", "sardine", "mackerel", "anchovy",
         "halibut", "haddock", "snapper", "swordfish", "pollock", "herring", "mahi", "barramundi",
         "fish sauce", "worcestershire"]
_SESAME = ["sesame", "tahini", "hummus", "halva"]

ALLERGEN_SYNONYMS = {
    "gluten": _GLUTEN, "wheat": _GLUTEN,
    "dairy": _DAIRY, "lactose": _DAIRY,
    "eggs": _EGGS,
    "nuts": _TREE_NUTS + _PEANUTS, "tree nuts": _TREE_NUTS, "peanuts": _PEANUTS,
    "soy": _SOY,
    "shellfish": _SHELLFISH, "fish": _FISH, "sesame": _SESAME,
}

_PLANT_MILKS = ["almond milk", "oat milk", "soy milk", "coconut milk", "light coconut milk", "coconut milk light",
                "rice milk", "cashew milk", "hemp milk", "pea milk", "plant milk", "macadamia milk"]
# Phrases that contain a banned word but are NOT that food. Applied per word,
# so "soy milk" escapes the dairy word "milk" but is still caught by "soy".
BANNED_TERM_EXEMPTIONS = {
    "milk": _PLANT_MILKS + ["coconut water"],
    "butter": ["peanut butter", "almond butter", "cashew butter", "sunflower seed butter", "seed butter",
               "nut butter", "cocoa butter", "apple butter", "butter beans", "butter bean", "butternut",
               "butter lettuce"],
    "cream": ["coconut cream", "cream of tartar"],
    "cheese": ["vegan cheese", "dairy free cheese", "dairy-free cheese"],
    "yogurt": ["coconut yogurt", "soy yogurt", "almond yogurt", "oat yogurt"],
    "curd": ["bean curd"],
    "egg": ["eggplant"],
    "noodle": ["rice noodles", "zucchini noodles", "shirataki noodles"],
    "tortilla": ["corn tortilla", "corn tortillas"],
    "flour": ["almond flour", "coconut flour", "rice flour", "chickpea flour", "tapioca flour", "cassava flour"],
    "wrap": ["lettuce wrap", "lettuce wraps"],
    "rice": ["cauliflower rice", "rice vinegar"],
    "pasta": ["zucchini pasta"],
    "bean": ["green beans", "green bean"],
    "peas": ["snap peas", "snow peas"],
    "honey": ["honeydew"],
    "apple": ["apple cider vinegar"],
    "juice": ["lemon juice", "lime juice"],
    "sugar": ["sugar snap"],
    "steak": ["cauliflower steak", "tofu steak", "mushroom steak", "portobello steak"],
    "bacon": ["tempeh bacon", "coconut bacon"],
    "beef": ["beefsteak tomato"],
}

_MEAT = ["chicken", "beef", "pork", "lamb", "turkey", "bacon", "ham", "sausage", "steak", "mince", "veal",
         "venison", "duck", "bison", "jerky", "prosciutto", "salami", "pepperoni", "chorizo", "liver",
         "gelatin", "lard", "tallow", "bone broth", "chicken broth", "beef broth", "ribeye", "sirloin",
         "brisket", "prime rib", "meatball", "rabbit", "eye of round", "chicken fat", "duck fat"]
_KETO_BANNED = ["rice", "bread", "toast", "pasta", "spaghetti", "orzo", "noodle", "oat", "oatmeal", "porridge",
                "granola", "muesli", "cereal", "quinoa", "couscous", "bulgur", "barley", "farro", "millet",
                "buckwheat", "potato", "plantain", "corn", "tortilla", "wrap", "bagel", "naan", "pita",
                "muffin", "cracker", "popcorn", "banana", "apple", "mango", "pineapple", "grape", "orange",
                "pear", "peach", "nectarine", "plum", "kiwi", "cherries", "watermelon", "papaya", "fig",
                "pomegranate", "grapefruit", "dates", "raisin", "dried cranberries", "honey", "maple syrup",
                "agave", "sugar", "syrup", "jam", "juice", "ketchup", "bbq sauce", "teriyaki", "hoisin",
                "bean", "lentil", "chickpea", "hummus", "falafel", "peas", "milk", "parsnip"]
_PALEO_BANNED = ([g for g in _GLUTEN if g not in ("soy sauce",)]
                 + ["rice", "quinoa", "corn", "millet", "buckwheat", "popcorn", "rice cake",
                    "bean", "lentil", "chickpea", "peanut", "soy", "tofu", "tempeh", "edamame", "hummus",
                    "falafel", "miso", "split peas", "sugar", "ketchup", "bbq sauce"]
                 + [d for d in _DAIRY if d != "ghee"])
DIET_BANNED_TERMS = {
    "vegan": _MEAT + _FISH + _SHELLFISH + _EGGS + _DAIRY + ["honey", "gelatin"],
    "vegetarian": _MEAT + _FISH + _SHELLFISH,
    "paleo": _PALEO_BANNED,
    "keto": _KETO_BANNED,
}

# Carnivore is an allow-list: every ingredient must be an animal food.
_ANIMAL_TOKENS = {"chicken", "beef", "steak", "sirloin", "ribeye", "rump", "mince", "turkey", "pork", "bacon",
                  "ham", "sausage", "chorizo", "lamb", "veal", "venison", "bison", "duck", "liver", "jerky",
                  "rinds", "rib", "brisket", "round", "salmon", "tuna", "cod", "tilapia", "shrimp", "prawn",
                  "crab", "scallop", "lobster", "mussel", "sardine", "mackerel", "trout", "halibut", "bass",
                  "haddock", "snapper", "mahi", "fish", "egg", "yolk", "butter", "ghee", "tallow", "lard",
                  "fat", "cheese", "cheddar", "parmesan", "mozzarella", "brie", "gouda", "feta", "halloumi",
                  "cream", "broth", "salt", "chop", "thigh", "breast", "loin", "tenderloin"}
_PLANT_MARKERS = {"peanut", "almond", "cashew", "coconut", "nut", "seed", "sunflower", "cocoa", "apple", "bean",
                  "lettuce", "butternut", "vegan", "eggplant", "noodle", "vegetable", "plant", "pepper"}


def is_carnivore_food(key: str) -> bool:
    st = {_stem(t) for t in _tokens(key)}
    animal = {_stem(t) for t in _ANIMAL_TOKENS}
    plant = {_stem(t) for t in _PLANT_MARKERS}
    return bool(st & animal) and not (st & plant)


def _stem_word(w: str) -> str:
    return _stem(w.lower())


def _words_match(a: str, b: str) -> bool:
    sa, sb = _stem_word(a), _stem_word(b)
    if sa == sb:
        return True
    # suffix variants only (tomato/tomatoes, cream/creamy, toast/toasted) —
    # never different foods that share a prefix (pepper/pepperoni)
    if len(sa) < 4 or len(sb) < 4:
        return False
    short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return long_.startswith(short) and long_[len(short):] in ("s", "es", "y", "ed", "d", "e")


def _remove_phrase(text: str, phrase: str) -> str:
    words = re.findall(r"[a-z]+", phrase.lower())
    if not words:
        return text
    pattern = r"\b" + r"[\s-]+".join(rf"{re.escape(w)}[a-z]*" for w in words) + r"\b"
    return re.sub(pattern, " ", text)


def contains_banned_food(text: str, banned_term: str) -> bool:
    """Whole-word (stem-aware) match of a banned term inside text.
    'mushrooms' catches 'mushroom'; 'gluten-free' doesn't trigger 'gluten';
    'almond milk' doesn't trigger dairy 'milk' (but does trigger 'almond')."""
    t = (text or "").lower()
    bt = (banned_term or "").lower().strip()
    if not t or not bt:
        return False
    for variant in (bt, _stem_word(bt), bt + "s"):
        t = t.replace(f"{variant}-free", " ").replace(f"{variant} free", " ")
    phrase = re.findall(r"[a-z]+", bt)
    if not phrase:
        return False
    exemptions = set(BANNED_TERM_EXEMPTIONS.get(phrase[-1], []) + BANNED_TERM_EXEMPTIONS.get(_stem_word(phrase[-1]), [])
                     + BANNED_TERM_EXEMPTIONS.get(bt, []))
    for ex in exemptions:
        if len(re.findall(r"[a-z]+", ex)) > len(phrase):
            t = _remove_phrase(t, ex)
    tokens = re.findall(r"[a-z]+", t)
    n = len(phrase)
    for i in range(len(tokens) - n + 1):
        if all(_words_match(tokens[i + j], phrase[j]) for j in range(n)):
            return True
    return False


def expand_banned_terms(banned_list):
    """Expand banned terms with allergen synonyms (nuts → almond, cashew…)."""
    expanded = []
    for term in banned_list or []:
        t = str(term).lower().strip()
        if not t:
            continue
        if t not in expanded:
            expanded.append(t)
        syns = (ALLERGEN_SYNONYMS.get(t) or ALLERGEN_SYNONYMS.get(t + "s")
                or ALLERGEN_SYNONYMS.get(_stem_word(t)) or ALLERGEN_SYNONYMS.get(_stem_word(t) + "s"))
        for s in syns or []:
            if s not in expanded:
                expanded.append(s)
    return expanded


class FoodRules:
    """Everything a meal must respect: allergies, foods to avoid, eating style."""

    def __init__(self, allergies=None, avoid_terms=None, eating_style="balanced"):
        self.eating_style = (eating_style or "balanced").lower()
        self.allergies = [a for a in (allergies or []) if a and str(a).lower() != "none"]
        self.allergy_terms = expand_banned_terms(self.allergies)
        self.avoid_terms = expand_banned_terms([t for t in (avoid_terms or []) if t])
        self.diet_terms = list(dict.fromkeys(DIET_BANNED_TERMS.get(self.eating_style, [])))

    def violations(self, name: str, items: list, instructions: str = "") -> list:
        """Return human-readable reasons why a meal breaks the rules ([] = safe)."""
        foods_text = " | ".join(f"{it['label']} {it['key']}" for it in items)
        # cooking verbs that look like foods ("toast the seeds") are ignored in instructions
        steps = re.sub(r"\btoast(ed|ing)?\b", " ", (instructions or "").lower())
        all_text = f"{name or ''} | {foods_text} | {steps}"
        found = []
        for t in self.allergy_terms:
            if contains_banned_food(all_text, t):
                found.append(f"allergy:{t}")
        for t in self.avoid_terms:
            if contains_banned_food(all_text, t):
                found.append(f"avoid:{t}")
        for t in self.diet_terms:
            if contains_banned_food(foods_text, t):
                found.append(f"{self.eating_style}:{t}")
        if self.eating_style == "carnivore":
            for it in items:
                if not is_carnivore_food(it["key"]):
                    found.append(f"carnivore:{it['key']}")
        return found

    def food_allowed(self, key: str) -> bool:
        return not self.violations("", [{"label": key, "key": key}])


# ── Instructions ↔ ingredients: every food the steps mention must be listed ──
# Seasonings, aromatics and liquids with negligible calories may be mentioned freely.
_FREE_MENTIONS = {
    "salt", "sea salt", "black pepper", "cayenne pepper", "red pepper flakes", "chili flakes", "chili powder",
    "paprika", "smoked paprika", "cumin", "cinnamon", "turmeric", "curry powder", "garlic powder", "onion powder",
    "oregano", "italian seasoning", "dried herbs", "thyme", "rosemary", "basil", "cilantro", "parsley", "dill",
    "mint", "capers", "vanilla extract", "stevia", "vinegar", "red wine vinegar", "rice vinegar",
    "apple cider vinegar", "balsamic vinegar", "hot sauce", "lemon juice", "lime juice", "lemon", "lime",
    "vegetable broth", "chicken broth", "bone broth", "garlic", "ginger", "mustard", "dijon mustard",
    "soy sauce", "tamari", "coconut aminos", "fish sauce", "worcestershire sauce", "pickles",
}
# Words that are usually not a food on their own: "extra protein", "toast the oats", "wrap tightly".
_IGNORED_MENTIONS = {"protein", "toast", "wrap", "vegetables"}
# Generic words count as listed when any ingredient of that kind is.
_GENERIC_COVER = {
    "fish": {"fish", "salmon", "tilapia", "tuna", "cod", "trout", "halibut", "bass", "haddock", "snapper",
             "mahi", "mackerel", "sardine"},
    "berries": {"berry", "blueberry", "strawberry", "raspberry", "blackberry", "cherry"},
    "greens": {"green", "spinach", "kale", "arugula", "lettuce", "romaine", "chard", "collard"},
    "cheese": {"cheese", "cheddar", "mozzarella", "parmesan", "feta", "ricotta", "halloumi", "paneer", "brie",
               "gouda", "mascarpone"},
    "protein powder": {"whey", "protein", "casein"},
    "pasta": {"pasta", "spaghetti", "orzo", "noodle"},
    "noodles": {"noodle", "ramen", "udon", "soba", "spaghetti"},
    "beef": {"beef", "steak", "sirloin", "ribeye", "rump", "brisket", "flank", "mince"},
    "steak": {"steak", "sirloin", "ribeye", "rump", "flank", "beef", "venison", "bison", "lamb", "pork", "tuna"},
    "bread": {"bread", "toast", "sourdough", "ciabatta", "bagel", "pita", "naan", "muffin"},
    "tortilla": {"tortilla", "wrap"},
    "yogurt": {"yogurt", "skyr", "kefir"},
    "egg": {"egg"}, "eggs": {"egg"}, "whole eggs": {"egg"}, "large eggs": {"egg"},
    "seeds": {"seed"},
    "squash": {"squash", "zucchini", "pumpkin"},
    "onion": {"onion", "shallot", "scallion"}, "onions": {"onion", "shallot", "scallion"},
    "peppers": {"pepper", "capsicum", "jalapeno"}, "pepper": {"pepper", "capsicum", "jalapeno"},
    "oil": {"oil"}, "cream": {"cream"},
    "mayo": {"mayonnaise", "mayo"}, "mayonnaise": {"mayonnaise", "mayo"},
    "pita bread": {"pita"}, "pita": {"pita"},
    "jasmine rice": {"jasmine", "basmati", "white"}, "basmati rice": {"jasmine", "basmati", "white"},
    "white rice": {"jasmine", "basmati", "white"},
    "mixed vegetables": {"broccoli", "zucchini", "pepper", "carrot", "asparagus", "spinach", "kale", "onion",
                         "mushroom", "tomato", "cauliflower", "pea", "cabbage", "eggplant", "squash", "celery",
                         "cucumber", "beet", "leek", "bok", "radish", "fennel", "okra", "chard", "artichoke",
                         "broccolini", "sprout", "capsicum"},
}
# A missing cooking fat is added with a small default amount (grams).
_FAT_DEFAULTS = {"butter": 5, "ghee": 5, "olive oil": 5, "coconut oil": 5, "avocado oil": 5, "vegetable oil": 5,
                 "sesame oil": 3, "beef tallow": 5, "tallow": 5, "lard": 5, "duck fat": 5, "chicken fat": 5,
                 "heavy cream": 15, "sour cream": 15, "coconut cream": 15}
_GENERIC_FAT_PICKS = {"oil": ["olive oil", "avocado oil", "coconut oil", "vegetable oil"],
                      "cream": ["heavy cream", "coconut cream"]}


def _build_mention_index():
    idx = {}
    for k in list(INGREDIENT_MACROS) + ["oil", "cream"]:
        seq = tuple(_stem(t) for t in _tokens(k))
        if seq:
            idx.setdefault(seq[0], {}).setdefault(seq, k)
    return {first: sorted(seqs.items(), key=lambda kv: -len(kv[0])) for first, seqs in idx.items()}


_MENTION_INDEX = _build_mention_index()


def instruction_mentions(instructions: str) -> list:
    """Foods (database keys, plus generic 'oil'/'cream') the instructions mention,
    longest name first. Seasonings, negated ('no oil', 'oil-free') and
    alternative ('or butter') mentions are skipped."""
    raw = _tokens(instructions)
    st = [_stem(t) for t in raw]
    found, i = [], 0
    while i < len(st):
        for seq, key in _MENTION_INDEX.get(st[i], ()):
            n = len(seq)
            if tuple(st[i:i + n]) != seq:
                continue
            prev = raw[i - 1] if i else ""
            nxt = raw[i + n] if i + n < len(raw) else ""
            skipped = (prev in ("no", "without", "or", "skip") or nxt == "free" or key in _FREE_MENTIONS
                       or key in _IGNORED_MENTIONS or (n == 1 and raw[i] == "pepper"))  # "salt and pepper"
            if not skipped:
                found.append(key)
            i += n
            break
        else:
            i += 1
    return list(dict.fromkeys(found))


def _covers(mention: str, item_stems: set) -> bool:
    return {_stem(t) for t in _tokens(mention)} <= item_stems or bool(_GENERIC_COVER.get(mention, set()) & item_stems)


def _item_stems(it) -> set:
    return {_stem(t) for t in _tokens(f"{it['key']} {it.get('label', '')}")}


def unlisted_mentions(instructions: str, items: list) -> list:
    """Foods the instructions mention that no ingredient covers."""
    sets = [_item_stems(it) for it in items]
    return [m for m in instruction_mentions(instructions) if not any(_covers(m, s) for s in sets)]


def reconcile_instructions(draft, rules: FoodRules) -> list:
    """Make the ingredient list cover every food the instructions mention.
    A missing cooking fat (butter, oil, ghee, cream…) is added with a small
    default amount; any other missing food is returned as a problem so the
    meal gets regenerated. Listed foods the steps mention are marked 'keep'
    so portion tuning never removes them."""
    problems = []
    for key in unlisted_mentions(draft["instructions"], draft["items"]):
        picks = _GENERIC_FAT_PICKS.get(key, [key] if key in _FAT_DEFAULTS else [])
        fat = next((k for k in picks if rules.food_allowed(k)), None)
        if fat:
            draft["items"].append({"label": fat, "key": fat, "grams": float(_FAT_DEFAULTS[fat])})
            logger.info(f"'{draft['name']}': instructions mention {key} — added {_FAT_DEFAULTS[fat]}g {fat}")
        else:
            problems.append(f"instructions mention '{key}' but it is not in the ingredients")
    mentions = instruction_mentions(draft["instructions"])
    for it in draft["items"]:
        s = _item_stems(it)
        if any(_covers(m, s) for m in mentions):
            it["keep"] = True
    return problems


# ════════════════════════════════════════════════════════════════════════════
# 4. MEAL DRAFTS
# ════════════════════════════════════════════════════════════════════════════
def items_from_raw(raw_ingredients):
    """Turn AI/template ingredients into [{'label','key','grams'}].
    Accepts {"food": "...", "grams": N} objects or plain strings.
    Returns (items, unknown_labels)."""
    items, unknown = [], []
    for ing in raw_ingredients or []:
        label, grams, key = None, None, None
        if isinstance(ing, dict):
            label = str(ing.get("food") or ing.get("name") or "").strip()
            label = re.sub(r"\b\d+(?:\.\d+)?\s*(?:g|grams?|ml)\b", " ", label).strip(" ,-")
            gm = re.search(r"\d+(?:\.\d+)?", str(ing.get("grams", "")))
            grams = float(gm.group(0)) if gm else None
            key = resolve_food(label) if label else None
            if grams is None and label:
                parsed = parse_ingredient(f"{ing.get('amount', '')} {label}")
                if parsed:
                    label, grams, key = parsed
        else:
            parsed = parse_ingredient(str(ing))
            if parsed:
                label, grams, key = parsed
            else:
                label = str(ing)
        if not key or grams is None or grams <= 0:
            unknown.append((label or str(ing), grams))
            continue
        items.append({"label": label, "key": key, "grams": float(grams)})
    return items, unknown


def make_draft(name, meal_type, items, instructions="", prep_time=15):
    return {"name": name or f"{meal_type.capitalize()}", "meal_type": meal_type, "items": items,
            "instructions": instructions or "", "prep_time_minutes": int(prep_time or 15)}


def template_draft(meal_type: str, tpl: dict):
    items, unknown = items_from_raw([{"food": n, "grams": g} for n, g in tpl["ingredients"].items()])
    if unknown:
        raise ValueError(f"Template '{tpl['name']}' has unknown foods: {unknown}")
    return make_draft(tpl["name"], meal_type, items, tpl.get("instructions", ""), tpl.get("prep_time", 20))


def _item_vec(it):
    cal, p, c, f = INGREDIENT_MACROS[it["key"]]
    return (cal / 100.0, p / 100.0, c / 100.0, f / 100.0)


def draft_macros(draft) -> dict:
    tot = {k: 0.0 for k in MACRO_KEYS}
    for it in draft["items"]:
        m = macros_for(it["key"], it["grams"])
        for k in MACRO_KEYS:
            tot[k] += m[k]
    return tot


# ════════════════════════════════════════════════════════════════════════════
# 5. PORTION OPTIMISER — adjusts GRAMS only, never the displayed numbers
# ════════════════════════════════════════════════════════════════════════════
def _bounds(it, widen: bool):
    g0 = it["g0"]
    cal, p, c, f = INGREDIENT_MACROS[it["key"]]
    fat_dense = f >= 60
    cap = 45 if fat_dense else 90 if cal >= 450 else 60 if (p >= 60 and cal >= 300) else 400
    if widen:
        lo = 0.0 if fat_dense or g0 <= 15 else 0.3 * g0
        hi = max(3.0 * g0, 30.0)
    else:
        lo, hi = 0.5 * g0, 2.2 * g0
    if it.get("keep"):  # the instructions use it, so it must stay on the list
        lo = max(lo, min(g0, 3.0))
    hi = max(min(hi, max(cap, g0)), lo)
    return lo, hi


def _unit_bounds(bounds, u):
    """Bounds on whole units: at least one unit, never a fraction."""
    lo, hi = bounds
    lo_u = max(u, math.ceil(lo / u - 1e-9) * u)
    return lo_u, max(lo_u, math.floor(hi / u + 1e-9) * u)


def _tolerances(targets):
    return {k: max(TOLERANCE * targets[k], 0 if k == "calories" else MACRO_FLOOR_G) for k in MACRO_KEYS}


def _norm_devs(meals, targets):
    tot = {k: 0.0 for k in MACRO_KEYS}
    for m in meals:
        for k, v in draft_macros(m).items():
            tot[k] += v
    tol = _tolerances(targets)
    return {k: (tot[k] - targets[k]) / max(tol[k], 1e-6) for k in MACRO_KEYS}


def max_deviation(meals, targets) -> float:
    """Worst macro miss of the meals combined, in units of the 5% tolerance
    (≤ 1.0 means every macro is on target)."""
    return max(abs(v) for v in _norm_devs(meals, targets).values())


def optimise_portions(meals, targets, widen=False, shares=None, adjustable=None):
    """Scale ingredient grams (within realistic bounds) so the meals' combined
    macros approach `targets` (dict of calories/protein/carbs/fats). Mutates
    the drafts. Only meals whose index is in `adjustable` change (default: all);
    the others count towards the totals as they are. Returns True when every
    macro is within tolerance. Whole-unit foods (eggs, bread slices, wraps…)
    always end on whole units; the other foods are re-tuned around them."""
    adjustable = set(range(len(meals))) if adjustable is None else set(adjustable)
    items, fixed = [], []
    for mi, m in enumerate(meals):
        for it in m["items"]:
            it.setdefault("g0", it["grams"])
            # seasonings (<5g) and meals that must not change stay as written
            (items if (mi in adjustable and it["g0"] >= 5) else fixed).append((mi, it))
    if not items:
        return False
    T = {k: max(float(targets[k]), 1.0) for k in MACRO_KEYS}
    W = {"calories": 1.0, "protein": 1.5, "carbs": 1.0, "fats": 1.0}
    MU, NU = 0.0005, 0.02
    total_share = sum((shares or MEAL_SHARES).get(m["meal_type"], 0.2) for m in meals) or 1.0
    S = [T["calories"] * (shares or MEAL_SHARES).get(m["meal_type"], 0.2) / total_share for m in meals]
    vecs = [_item_vec(it) for _, it in items]
    units = [unit_grams(it["key"]) for _, it in items]
    bnds = [_unit_bounds(_bounds(it, widen), u) if u else _bounds(it, widen) for (_, it), u in zip(items, units)]

    def totals():
        tot = [0.0, 0.0, 0.0, 0.0]
        mc = [0.0] * len(meals)
        for (mi, it), v in zip(items, vecs):
            for k in range(4):
                tot[k] += v[k] * it["grams"]
            mc[mi] += v[0] * it["grams"]
        for mi, it in fixed:
            v = _item_vec(it)
            for k in range(4):
                tot[k] += v[k] * it["grams"]
            mc[mi] += v[0] * it["grams"]
        return tot, mc

    tk = [T[k] for k in MACRO_KEYS]
    wk = [W[k] for k in MACRO_KEYS]

    def descend(frozen=frozenset()):
        """Continuous coordinate descent on a bounded weighted least-squares objective."""
        for _sweep in range(150):
            tot, mc = totals()
            moved = 0.0
            for idx, ((mi, it), v, (lo, hi)) in enumerate(zip(items, vecs, bnds)):
                if idx in frozen:
                    continue
                moved += _descent_step(it, mi, v, lo, hi, tot, mc)
            if moved < 0.05:
                break

    def _descent_step(it, mi, v, lo, hi, tot, mc):
        s = max(it["g0"], 20.0)
        num = sum(wk[k] * v[k] * (tot[k] - tk[k]) / tk[k] ** 2 for k in range(4))
        num += MU * (it["grams"] - it["g0"]) / s ** 2
        num += NU * v[0] * (mc[mi] - S[mi]) / T["calories"] ** 2
        den = sum(wk[k] * v[k] ** 2 / tk[k] ** 2 for k in range(4)) + MU / s ** 2 + NU * v[0] ** 2 / T["calories"] ** 2
        if den <= 0:
            return 0.0
        new_g = min(max(it["grams"] - num / den, lo), hi)
        delta = new_g - it["grams"]
        if abs(delta) <= 1e-9:
            return 0.0
        for k in range(4):
            tot[k] += v[k] * delta
        mc[mi] += v[0] * delta
        it["grams"] = new_g
        return abs(delta)

    descend()
    # whole-unit foods snap to whole units, then the other foods are re-tuned around them
    unit_idx = frozenset(i for i, u in enumerate(units) if u)
    for i in unit_idx:
        (_, it), (lo, hi), u = items[i], bnds[i], units[i]
        it["grams"] = min(max(round(it["grams"] / u) * u, lo), hi)
    if unit_idx:
        descend(unit_idx)

    # round to kitchen-friendly amounts, then greedy integer refinement
    def step_of(i, g):
        return units[i] or (5 if g >= 25 else 1)
    for i, ((_, it), (lo, hi)) in enumerate(zip(items, bnds)):
        if units[i]:
            continue
        st = step_of(i, it["grams"])
        it["grams"] = min(max(round(it["grams"] / st) * st, 0 if lo == 0 else max(st, round(lo))), max(hi, st))

    def score(d):
        return sum(x * x for x in d.values()), max(abs(x) for x in d.values())

    devs = _norm_devs(meals, targets)
    cur = score(devs)
    for _ in range(400):
        if cur[1] <= 0.6:
            break
        best = None
        for i, ((_, it), (lo, hi)) in enumerate(zip(items, bnds)):
            st = step_of(i, it["grams"])
            for d in (-st, st):
                ng = it["grams"] + d
                if ng < lo - 1e-9 or ng > hi + 1e-9 or ng < 0:
                    continue
                old = it["grams"]
                it["grams"] = ng
                sc = score(_norm_devs(meals, targets))
                it["grams"] = old
                if sc[0] < cur[0] - 1e-9 and (best is None or sc[0] < best[0][0]):
                    best = (sc, it, ng)
        if not best:
            break
        cur, best[1]["grams"] = best[0], best[2]
    for mi, m in enumerate(meals):
        if mi in adjustable:
            m["items"] = [it for it in m["items"] if it["grams"] >= 1 or it["g0"] < 5]
    return cur[1] <= 1.0


_BOOSTERS = {
    "protein": ["chicken breast", "egg whites", "whey protein", "greek yogurt 0%", "tuna", "turkey breast",
                "pea protein powder", "seitan", "extra firm tofu", "shrimp", "cod", "sirloin steak"],
    "carbs": ["white rice", "banana", "rice cakes", "rolled oats", "sweet potato", "mixed berries", "quinoa",
              "potatoes", "apple", "mango", "pineapple", "butternut squash", "plantain", "dates"],
    "fats": ["olive oil", "avocado", "almonds", "peanut butter", "butter", "macadamia nuts", "pumpkin seeds"],
}


def _reset(meals):
    for m in meals:
        for it in m["items"]:
            it["grams"] = it.setdefault("g0", it["grams"])


def _add_booster(meals, targets, rules: FoodRules) -> bool:
    """Add a rule-compliant side for the macro that is furthest below target."""
    devs = _norm_devs(meals, targets)
    short = [k for k in ("protein", "carbs", "fats") if devs[k] < -1.0]
    if not short:
        return False
    macro = min(short, key=lambda k: devs[k])
    used = {it["key"] for m in meals for it in m["items"]}
    col = {"protein": 1, "carbs": 2, "fats": 3}[macro]
    for key in _BOOSTERS[macro]:
        if key in used or not rules.food_allowed(key):
            continue
        per_g = INGREDIENT_MACROS[key][col] / 100.0
        gap = -devs[macro] * _tolerances(targets)[macro]
        g0 = round(min(max(gap / per_g, 10), 30 if macro == "fats" else 250))
        # spread sides over the main meals: the one with the fewest boosters, then the biggest
        mains = [m for m in meals if m["meal_type"] != "snack"] or meals
        host = min(mains, key=lambda m: (sum(1 for it in m["items"] if it.get("booster")),
                                         -MEAL_SHARES.get(m["meal_type"], 0.2)))
        host["items"].append({"label": key, "key": key, "grams": g0, "g0": g0, "booster": True})
        logger.info(f"Booster added to {host['meal_type']}: {g0}g {key} (short on {macro})")
        return True
    return False


def balance_day(meals, targets, rules: FoodRules):
    """Hit the day's targets by adjusting grams within realistic bounds. If the
    chosen foods can't get there, add a rule-compliant side ('booster') to the
    main meal and retry; only as a last resort allow wider portion changes."""
    if optimise_portions(meals, targets):
        return True
    for _ in range(5):
        if not _add_booster(meals, targets, rules):
            break
        _reset(meals)
        if optimise_portions(meals, targets):
            return True
    _reset(meals)
    return optimise_portions(meals, targets, widen=True)


# ════════════════════════════════════════════════════════════════════════════
# 6. FINAL MEALS & DAYS — numbers come only from the listed ingredients
# ════════════════════════════════════════════════════════════════════════════
def finalize_meal(draft, meal_id) -> dict:
    ingredients, tot = [], {k: 0.0 for k in MACRO_KEYS}
    for it in draft["items"]:
        label = it["label"] if resolve_food(it["label"]) == it["key"] else it["key"]
        s = format_ingredient(label[:1].upper() + label[1:], it["grams"], it["key"])
        m = calculate_ingredient_macros(s)
        if m is None:  # cannot happen: label resolves to key by construction
            m = macros_for(it["key"], it["grams"])
        ingredients.append(s)
        for k in MACRO_KEYS:
            tot[k] += m[k]
    return {
        "id": meal_id, "name": draft["name"], "meal_type": draft["meal_type"],
        "ingredients": ingredients, "instructions": draft.get("instructions", ""),
        "calories": int(round(tot["calories"])), "protein": round(tot["protein"], 1),
        "carbs": round(tot["carbs"], 1), "fats": round(tot["fats"], 1),
        "prep_time_minutes": int(draft.get("prep_time_minutes") or 15),
    }


def day_totals(meals) -> dict:
    return {
        "total_calories": int(sum(int(m.get("calories") or 0) for m in meals)),
        "total_protein": round(sum(float(m.get("protein") or 0) for m in meals), 1),
        "total_carbs": round(sum(float(m.get("carbs") or 0) for m in meals), 1),
        "total_fats": round(sum(float(m.get("fats") or 0) for m in meals), 1),
    }


def is_on_target(totals: dict, targets: dict) -> bool:
    tol = _tolerances(targets)
    actual = {"calories": totals["total_calories"], "protein": totals["total_protein"],
              "carbs": totals["total_carbs"], "fats": totals["total_fats"]}
    return all(abs(actual[k] - targets[k]) <= tol[k] + 1e-9 for k in MACRO_KEYS)


def build_day(day_label, meals_final, targets) -> dict:
    tot = day_totals(meals_final)
    return {"day": day_label, "meals": meals_final, **tot, "on_target": is_on_target(tot, targets)}


def meal_targets(day_targets: dict, meal_type: str, meal_types: list) -> dict:
    total = sum(MEAL_SHARES.get(t, 0.2) for t in meal_types) or 1.0
    share = MEAL_SHARES.get(meal_type, 0.2) / total
    return {k: day_targets[k] * share for k in MACRO_KEYS}


# ════════════════════════════════════════════════════════════════════════════
# 7. FOOD LIST FOR THE AI + LAST-RESORT SAFE MEAL
# ════════════════════════════════════════════════════════════════════════════
_PROMPT_EXCLUDE = {"protein", "seeds", "fish", "vegetables", "mixed vegetables", "greens", "beef", "chicken",
                   "pepper", "peppers", "lean beef", "extra lean beef", "steak", "cheese", "yogurt", "milk",
                   "turkey", "noodles", "ramen", "wrap", "dry pasta", "uncooked rice", "tofu", "tofu firm",
                   "rice", "egg", "lettuce wrap"}
_PROMPT_PREFER = {"eggs", "chicken breast", "greek yogurt 0%", "extra firm tofu", "beef mince 95/5",
                  "beef mince 90/10", "beef mince 80/20", "sirloin steak", "white rice", "rolled oats",
                  "whey protein", "pea protein powder", "almonds", "mozzarella cheese", "cheddar cheese",
                  "parmesan cheese", "feta cheese", "salmon", "shrimp", "lamb chops", "pork chop",
                  "chickpeas", "black beans", "lentils", "sweet potato", "mixed berries", "spinach"}


def prompt_food_names(rules: FoodRules = None) -> list:
    """One canonical name per food (aliases removed), filtered by the rules,
    so the AI can only pick foods that are both in the database and safe."""
    groups = {}
    for key, vals in INGREDIENT_MACROS.items():
        if key in _PROMPT_EXCLUDE:
            continue
        groups.setdefault(vals, []).append(key)
    names = []
    for keys in groups.values():
        pick = sorted(keys, key=lambda k: (k not in _PROMPT_PREFER, -len(_tokens(k)), len(k)))[0]
        if rules is None or rules.food_allowed(pick):
            names.append(pick)
    return sorted(names)


_SAFE_PROTEINS = ["chicken breast", "salmon", "sirloin steak", "turkey breast", "eggs", "greek yogurt 0%",
                  "cod", "extra firm tofu", "tempeh", "seitan", "lentils", "pork tenderloin", "chickpeas"]
_SAFE_CARBS = ["white rice", "sweet potato", "quinoa", "potato", "banana", "mixed berries", "rolled oats"]
_SAFE_VEG = ["broccoli", "spinach", "zucchini", "green beans", "asparagus", "mixed greens", "bell pepper"]
_SAFE_FATS = ["olive oil", "avocado", "butter", "pumpkin seeds", "almonds"]


def build_safe_meal(meal_type: str, rules: FoodRules, exclude_names=()) -> dict:
    """Deterministic, rule-compliant replacement meal (last resort)."""
    def first(cands, skip=()):
        return next((k for k in cands if k not in skip and rules.food_allowed(k)), None)
    no_carb = rules.eating_style in ("keto", "carnivore")
    protein = first(_SAFE_PROTEINS) or first(["bacon", "beef mince 80/20", "lamb chops"])
    carb = None if no_carb else first(_SAFE_CARBS)
    veg = None if rules.eating_style == "carnivore" else first(_SAFE_VEG)
    fat = first(_SAFE_FATS)
    picks = [(protein, 150), (carb, 150), (veg, 100), (fat, 10)]
    items = [{"label": k, "key": k, "grams": g} for k, g in picks if k]
    parts = [k.title() for k, _ in picks[:3] if k]
    name = " with ".join([parts[0], " & ".join(parts[1:])]) if len(parts) > 1 else (parts[0] if parts else meal_type.title())
    return make_draft(name, meal_type, items, "Cook the protein, prepare the sides and serve together.", 20)


# ════════════════════════════════════════════════════════════════════════════
# 6. SNAP FOOD — the user's description → grams; plated meals → items
# ════════════════════════════════════════════════════════════════════════════
# Words that mark a branded / prepared product: per-food weights ("1 cup of
# rice") never apply to it, and single-food references never stand in for it.
COMPOSITE_INDICATORS = {
    "meal", "ready", "readymade", "ready-made", "microwave", "microwaveable",
    "frozen", "pack", "packet", "bar", "bars", "shake", "shakes", "drink",
    "smoothie", "sauce", "curry", "stir", "fry", "burrito", "wrap", "pizza",
    "burger", "sandwich", "roll", "pasta bake", "casserole", "soup", "stew",
    "salad", "bowl", "protein bar", "protein shake", "protein powder",
    "supplement", "muesli", "granola", "cereal", "yogurt drink",
    # Brand tokens common in AU / global packaged foods
    "youfoodz", "my muscle chef", "lite n easy", "weight watchers",
    "healthy choice", "mccain", "birds eye", "sunrice", "kelloggs",
    "nestle", "sanitarium", "vitasoy", "so good",
}


def is_composite_name(name: str) -> bool:
    low = (name or "").lower()
    return any(re.search(rf"\b{re.escape(kw)}\b", low) for kw in COMPOSITE_INDICATORS)


def resolve_food_loose(name: str):
    """resolve_food, or — for short names like 'sourdough' — the database food
    whose name contains every word typed (fewest extra words wins)."""
    key = resolve_food(name)
    if key:
        return key
    stems = {_stem(x) for x in _tokens(name)} - {"large", "medium", "small", "fresh", "plain"}
    if not stems:
        return None
    hits = [k for k, kst in _KEY_STEMS.items() if k not in _RESOLVER_SKIP and stems <= kst]
    return min(hits, key=lambda k: (len(_KEY_STEMS[k]) - len(stems), k not in _PROMPT_PREFER, len(k))) if hits else None


def grams_in_text(text: str, food_name: str = "") -> float:
    """Grams stated in a serving description ('104g (2 eggs)', '250ml',
    '2 large eggs', '1 cup' of `food_name`); 0 when it can't be worked out."""
    s = _normalise_amount_text(str(text or "").lower())
    m = re.search(rf"{_NUM}\s*(kg|g|grams?|ml|l)\b", s)
    if m:
        return float(m.group(1)) * (1000 if m.group(2) in ("kg", "l") else 1)
    parsed = parse_ingredient(s) or (parse_ingredient(f"{s} {food_name}") if s and food_name else None)
    return float(parsed[1]) if parsed else 0.0


_PACK_WORDS = ("pack", "packet", "bag", "tub", "bar", "container", "box", "tin", "can", "bottle", "punnet",
               "carton", "jar", "pouch", "tray", "sachet", "pot", "tube", "package", "meal")
_UNIT_WORDS = {
    **{w: ("g", 1) for w in ("g", "gm", "gms", "gr", "gram", "grams")},
    **{w: ("g", 1000) for w in ("kg", "kgs", "kilo", "kilos", "kilogram", "kilograms")},
    **{w: ("g", 28.35) for w in ("oz", "ounce", "ounces")},
    **{w: ("g", 453.6) for w in ("lb", "lbs", "pound", "pounds")},
    **{w: ("ml", 1) for w in ("ml", "millilitre", "millilitres", "milliliter", "milliliters")},
    **{w: ("ml", 1000) for w in ("l", "litre", "litres", "liter", "liters")},
    **{w: ("serving", 1) for w in ("serving", "servings", "serve", "serves", "portion", "portions", "srv")},
    **{w: ("pack", 1) for w in _PACK_WORDS + tuple(p + "s" for p in _PACK_WORDS) + ("boxes", "pouches")},
    **{w: ("cup", 1) for w in ("cup", "cups")},
    **{w: ("tbsp", 1) for w in ("tbsp", "tbsps", "tablespoon", "tablespoons")},
    **{w: ("tsp", 1) for w in ("tsp", "tsps", "teaspoon", "teaspoons")},
    **{w: ("slice", 1) for w in ("slice", "slices")},
    **{w: ("piece", 1) for w in ("piece", "pieces", "pc", "pcs")},
    **{w: ("handful", 1) for w in ("handful", "handfuls")},
    **{w: ("bowl", 1) for w in ("bowl", "bowls", "bowlful")},
    **{w: ("scoop", 1) for w in ("scoop", "scoops")},
}
_WORD_AMOUNTS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                 "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "dozen": 12,
                 "half": 0.5, "quarter": 0.25, "third": 1 / 3}
_FILLER_RE = re.compile(r"~|≈|\b(?:about|approx\.?|approximately|around|roughly|maybe|nearly|almost|just|"
                        r"i\s+ate|i\s+had|i've\s+had|ate|had|eaten)\b")
_WHOLE_PACK_RE = re.compile(rf"\b(?:the\s+)?(?:whole|entire|full|complete)\s+(?:the\s+)?(?:{'|'.join(_PACK_WORDS)}|thing)\b"
                            rf"|\ball\s+of\s+(?:it|the\s+(?:{'|'.join(_PACK_WORDS)}))\b|\bthe\s+lot\b")
_SIZE_WORDS = ("small", "medium", "large", "extra large", "jumbo")
_HANDFUL_WEIGHTS = [({"almond", "walnut", "cashew", "peanut", "nut", "pecan", "hazelnut", "pistachio", "macadamia"}, 30),
                    ({"seed"}, 20), ({"berry", "blueberry", "strawberry", "raspberry", "blackberry", "grape", "cherry"}, 75),
                    ({"spinach", "arugula", "rocket", "lettuce", "green", "kale", "romaine"}, 25),
                    ({"raisin", "sultana", "cranberry", "date", "apricot"}, 30),
                    ({"chip", "crisp", "popcorn", "pretzel", "cracker"}, 25), ({"granola", "muesli", "cereal", "oat"}, 30),
                    ({"chocolate"}, 30)]
_BOWL_WEIGHTS = [({"oatmeal", "porridge"}, 250), ({"rice", "quinoa", "couscous"}, 250), ({"pasta", "spaghetti", "noodle"}, 300),
                 ({"granola", "muesli", "cereal", "oat"}, 50), ({"soup", "stew", "curry", "chili", "broth", "ramen"}, 400),
                 ({"salad", "lettuce", "spinach", "green"}, 150), ({"yogurt", "skyr"}, 200), ({"berry", "fruit"}, 150),
                 ({"popcorn"}, 30)]
_SCOOP_WEIGHTS = [({"protein", "whey", "powder", "casein"}, 30), ({"ice", "gelato"}, 65)]


def _normalise_portion_text(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    s = _FILLER_RE.sub(" ", s)
    s = re.sub(r"\bthree\s+quarters?\b", "0.75", s)
    s = re.sub(r"\btwo\s+thirds?\b", "0.667", s)
    s = re.sub(r"\b(\d+(?:\.\d+)?|one|two|three|four|five)\s+and\s+a\s+half\b",
               lambda m: str(float(_WORD_AMOUNTS.get(m.group(1), m.group(1))) + 0.5), s)
    s = re.sub(r"\ba\s+(half|quarter|third)\b", r"\1", s)
    for u, d in _UNICODE_FRACTIONS.items():
        s = re.sub(rf"(\d)\s*{u}", lambda m, d=d: str(float(m.group(1)) + float(d)), s)
        s = s.replace(u, " 0" + d)
    s = re.sub(r"\b(\d+)\s+([1-7])/([2348])\b", lambda m: str(int(m.group(1)) + int(m.group(2)) / int(m.group(3))), s)
    s = re.sub(r"(?<![\d/])\b([1-7])/([2348])\b(?![\d/])",
               lambda m: str(int(m.group(1)) / int(m.group(2))) if int(m.group(1)) < int(m.group(2)) else m.group(0), s)
    return re.sub(r"\s+", " ", s).strip()


def _strip_articles(s: str) -> str:
    return re.sub(r"^(?:(?:of|a|an|the|my)\s+)+", "", s.strip()).strip(" .,!?")


def _parse_segment(seg: str):
    s = seg.strip(" .,!?")
    if not s:
        return None
    if _WHOLE_PACK_RE.search(s):
        return {"amount": 1.0, "unit": "pack", "food": "", "text": seg.strip()}
    # an explicit weight anywhere wins: "chicken 200g", "300 grams"
    m = re.search(r"(?<![-\d.])(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|gms|gr|grams?|oz|ounces?|lbs?|pounds?|ml|millilit(?:re|er)s?|l|lit(?:re|er)s?)\b", s)
    if m:
        if float(m.group(1)) <= 0:
            return None
        unit, mult = _UNIT_WORDS[m.group(2)]
        food = _strip_articles(re.sub(r"^\s*of\s+", "", (s[:m.start()] + " " + s[m.end():]).strip()))
        return {"amount": float(m.group(1)) * mult, "unit": unit, "food": food, "text": seg.strip()}
    m = re.match(rf"^(\d+(?:\.\d+)?|\.\d+|{'|'.join(_WORD_AMOUNTS)})\b\s*(.*)$", s)
    if not m:
        return None
    word = m.group(1)
    amount = float(_WORD_AMOUNTS.get(word, word) if word in _WORD_AMOUNTS else word)
    if amount <= 0:
        return None
    rest = _strip_articles(m.group(2))
    if word in ("a", "an") and not rest:
        return None
    if not rest:
        # "300" → grams; "half" / "one" → servings
        return {"amount": amount, "unit": "g" if word[0].isdigit() or word[0] == "." else "serving",
                "food": "", "text": seg.strip()}
    first, _, tail = rest.partition(" ")
    if first in _UNIT_WORDS:
        unit, mult = _UNIT_WORDS[first]
        return {"amount": amount * mult, "unit": unit, "food": _strip_articles(tail), "text": seg.strip()}
    if word in ("a", "an") and first not in ("egg", "eggs"):
        # "a little oil", "an extra egg"? — a correction for the AI, not an amount
        if resolve_food_loose(rest) is None:
            return None
    return {"amount": amount, "unit": "count", "food": rest, "text": seg.strip()}


def parse_portions(text: str) -> list:
    """Amounts the user typed, one per item: '4 eggs and 3 pieces of sourdough'
    → [{amount 4, unit count, food eggs}, {amount 3, unit piece, food sourdough}].
    Text without an amount ('no dressing', 'grilled not fried') gives [] — it is
    a correction for the AI, never a reason to fail."""
    s = _normalise_portion_text(text)
    if not s:
        return []
    out = []
    for seg in re.split(r"\s*(?:,|;|\+|&|\band\b|\bplus\b|\bwith\b|\balso\b)\s*", s):
        spec = _parse_segment(seg)
        if spec:
            out.append(spec)
    return out


# Words that describe a food rather than name it ("fried eggs", "fresh sourdough").
_DESCRIPTIVE = {"large", "medium", "small", "jumbo", "extra", "fresh", "plain", "fried", "boiled", "poached",
                "scrambled", "grilled", "toasted", "raw", "cooked", "baked", "roasted", "steamed", "sliced",
                "chopped", "diced", "whole", "organic", "free", "range", "homemade", "natural"}


def _food_stems(text: str) -> set:
    return {_stem(x) for x in _tokens(text)} - _DESCRIPTIVE


def resolve_food_typed(name: str):
    """For foods the USER typed: the database food only when it accounts for
    every word typed — 'unicorn steak' or 'chicken nuggets' are reported as
    not found instead of being guessed as steak / chicken."""
    key = resolve_food_loose(name)
    return key if key and _food_stems(name) <= _KEY_STEMS[key] else None


def food_matches(food_text: str, key: str = None, name: str = "") -> bool:
    """Does what the user typed ('eggs', 'sourdough') refer to this food?"""
    fs = _food_stems(food_text)
    if not fs:
        return False
    ks = _food_stems(f"{key or ''} {name or ''}")
    return bool(ks) and (fs <= ks or (key is not None and _KEY_STEMS.get(key, frozenset()) and _KEY_STEMS[key] <= fs))


def portion_grams(spec, key=None, *, serving_g=None, unit_name=None, units_per_serving=None, pack_g=None,
                  label=False):
    """Grams for one stated amount, or None when it can't be worked out.
    Label reference points win (serving size, the label's own unit, pack size);
    otherwise the food's own weights — never one weight for every food."""
    a, u, food = spec["amount"], spec["unit"], spec.get("food") or ""
    if u == "g":
        return a
    if u == "ml":
        return a if label or not key else a * _lookup_by_tokens(key, _DENSITY, 1.0)
    if u == "serving":
        return a * serving_g if serving_g else None
    noun = (food.split()[-1] if food else "") if u == "count" else u
    if unit_name and noun and serving_g and units_per_serving and \
            _stem(noun) == _stem(str(unit_name).lower().split()[-1]):
        return a * serving_g / units_per_serving          # the label's own unit ("egg")
    if u == "pack":
        return a * pack_g if pack_g else None
    if not key:
        return None
    if u in ("cup", "tbsp", "tsp"):
        cup = _lookup_by_tokens(key, _CUP_WEIGHTS)
        return a * cup / {"cup": 1, "tbsp": 16, "tsp": 48}[u] if cup else None
    if u == "slice":
        per = unit_grams(key) or _lookup_by_tokens(key, _SLICE_WEIGHTS)
    elif u == "handful":
        per = _lookup_by_tokens(key, _HANDFUL_WEIGHTS)
    elif u == "bowl":
        per = _lookup_by_tokens(key, _BOWL_WEIGHTS)
    elif u == "scoop":
        per = _lookup_by_tokens(key, _SCOOP_WEIGHTS)
    else:  # "4 eggs", "3 pieces of sourdough" — the food's own unit weight
        if u == "count" and not food_matches(food, key):
            return None
        size = next((w for w in _SIZE_WORDS if re.search(rf"\b{w}\b", food)), None)
        per = unit_grams(key) if key in UNIT_FOODS and not size else _item_weight(key, size)
    return a * per if per else None


def _round_g(g: float):
    g = round(float(g), 1)
    return int(g) if g.is_integer() else g


def snap_item(name: str, grams: float, key: str = None, per_100g: dict = None, whole_units: bool = False):
    """One item of a plated meal: database macros for its grams. Foods that
    aren't in the database keep the AI's per-100g estimate (flagged).
    Returns None when the food can't be found and has no estimate."""
    key = key or resolve_food_loose(name)
    if grams is None or grams <= 0:
        return None
    if key:
        u = unit_grams(key)
        if whole_units and u:
            grams = max(1, round(grams / u)) * u       # AI's eggs / slices → whole units
        m = macros_for(key, grams)
        source = "database"
    elif isinstance(per_100g, dict) and float(per_100g.get("calories") or 0) > 0:
        f = grams / 100.0
        m = {"calories": round(float(per_100g.get("calories") or 0) * f),
             "protein": round(float(per_100g.get("protein") or 0) * f, 1),
             "carbs": round(float(per_100g.get("carbs") or 0) * f, 1),
             "fats": round(float(per_100g.get("fats") or 0) * f, 1)}
        source = "estimate"
    else:
        return None
    label = (name or key).strip()
    label = label[:1].upper() + label[1:]
    return {"name": label, "key": key, "grams": _round_g(grams),
            "display": unit_text(label, grams, key) or label, "per_100g": None if key else per_100g,
            "source": source, **m}


def plate_totals(items) -> dict:
    return {"calories": int(sum(i["calories"] for i in items)),
            "protein": round(sum(i["protein"] for i in items), 1),
            "carbs": round(sum(i["carbs"] for i in items), 1),
            "fats": round(sum(i["fats"] for i in items), 1),
            "grams": _round_g(sum(float(i["grams"]) for i in items))}


def _resize(it, grams):
    return snap_item(it["name"], grams, it["key"], it.get("per_100g"))


def build_plate(raw_items, specs, qty: int = 1):
    """Plated meal: the AI's {food, grams} items + amounts the user typed →
    items with database macros. Typed amounts replace the AI's estimate for the
    matching item (or add the item); a typed amount with no food ('200g',
    'half', '1 cup') resizes the whole plate. Returns (items, problems)."""
    items = []
    for r in raw_items or []:
        try:
            g = float(r.get("grams") or 0)
        except (TypeError, ValueError):
            continue
        it = snap_item(str(r.get("food") or ""), g, per_100g=r.get("per_100g"), whole_units=True)
        if it:
            items.append(it)
        else:
            logger.warning(f"Snap item '{r.get('food')}' not in the food database and no estimate — skipped")
    problems = []
    plate_specs = [s for s in specs if not s["food"]]
    food_specs = [s for s in specs if s["food"]]
    if plate_specs and items:
        s, total = plate_specs[0], sum(float(i["grams"]) for i in items)
        if s["unit"] in ("g", "ml"):
            factor = s["amount"] / total
        elif s["unit"] in ("serving", "pack"):
            factor = s["amount"]
        else:  # "1 cup" / "1 bowl" of the dish — the plate's own weight per cup
            per = [(float(i["grams"]), portion_grams({**s, "amount": 1}, i["key"])) for i in items if i["key"]]
            per = [(g, w) for g, w in per if w]
            factor = (s["amount"] * sum(g * w for g, w in per) / sum(g for g, _ in per)) / total if per else None
            if factor is None:
                problems.append(f"Couldn't work out '{s['text']}' for this meal — try grams, e.g. '300g'.")
        if factor:
            items = [i for i in (_resize(i, float(i["grams"]) * factor) for i in items) if i]
    for s in food_specs:
        match = next((i for i in items if food_matches(s["food"], i["key"], i["name"])), None)
        key = match["key"] if match else resolve_food_typed(s["food"])
        if not match and not key:
            problems.append(f"Couldn't find '{s['food']}' in the food database.")
            continue
        g = portion_grams(s, key)
        if g is None:
            problems.append(f"Couldn't work out '{s['text']}' — try grams, e.g. '100g {s['food']}'.")
            continue
        if match:
            new = _resize(match, g)
            if new:
                items[items.index(match)] = new
            else:
                items.remove(match)
        else:
            new = snap_item(s["food"], g, key)
            if new:
                items.append(new)
    if qty and qty > 1:
        items = [_resize(i, float(i["grams"]) * qty) for i in items]
    return [i for i in items if i], problems


def snap_item_from_text(text: str, key: str = None, name: str = None, per_100g: dict = None):
    """Edit an item's amount ('150g', '3 eggs') or add a new item by name
    ('30g cheddar', '1 tbsp olive oil', 'banana'). Returns (item, error)."""
    specs = parse_portions(text)
    spec = specs[0] if specs else None
    if key or per_100g:  # editing an existing item
        if not spec:
            return None, "Type an amount, e.g. 150g."
        g = portion_grams(spec, key) if key else (spec["amount"] if spec["unit"] in ("g", "ml") else None)
        if g is None:
            return None, f"Couldn't work out '{text.strip()}' for {name or key} — try grams, e.g. 150g."
        return snap_item(name or key, g, key, per_100g), None
    if spec and not spec["food"]:
        return None, f"Add the food's name too, e.g. '{text.strip()} chicken breast'."
    food = spec["food"] if spec else _strip_articles(_normalise_portion_text(text))
    key = resolve_food_typed(food)
    if not key:
        return None, f"Couldn't find '{food or text.strip()}' in the food database."
    if spec:
        g = portion_grams(spec, key)
    else:
        g = unit_grams(key) or _item_weight(key)
        if not g:
            return None, f"Add an amount, e.g. '100g {food}'."
    if g is None:
        return None, f"Couldn't work out '{text.strip()}' — try grams, e.g. '100g {food}'."
    return snap_item(food, g, key), None

