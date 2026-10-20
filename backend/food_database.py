"""Per-100g nutrition reference table used by the meal-plan engine and the
food-log reference cross-check. Format: food name -> (calories, protein, carbs, fat).

Convention: meat, fish and grains are COOKED weights, EXCEPT oats, which are
stored DRY (uncooked) — oats are weighed dry in recipes.
"""
# Ingredient database for accurate macro calculation (per 100g)
# Format: (calories, protein, carbs, fat)
INGREDIENT_MACROS = {
    # Proteins - Poultry
    # (all values USDA per-100g COOKED unless noted — the file convention)
    "chicken breast": (165, 31, 0, 3.6),   # SR Legacy #05064 breast, meat only, cooked, roasted
    "chicken": (165, 31, 0, 3.6),           # default = chicken breast (as above)
    "chicken thigh": (209, 26, 0, 10.9),   # SR Legacy #05098 thigh, meat only, cooked, roasted
    "chicken thighs": (209, 26, 0, 10.9),
    "turkey breast": (135, 30, 0, 1),      # SR Legacy #05192 breast, meat only, cooked, roasted
    "turkey": (170, 29, 0, 5),             # SR Legacy #05171 all classes, meat only, cooked, roasted
    "ground turkey": (203, 27, 0, 11.5),   # SR Legacy #05306 ground, cooked, pan-browned
    # Proteins - Beef  (all cooked / broiled / pan-browned; USDA "lean+fat, trimmed to 1/8"" versions)
    "sirloin steak": (212, 27, 0, 10.6),   # SR Legacy #23621 top sirloin, lean+fat 1/8", broiled
    "sirloin": (212, 27, 0, 10.6),
    "ribeye steak": (291, 24, 0, 21),      # SR Legacy #23111 rib eye small end, lean+fat 1/8", broiled
    "ribeye": (291, 24, 0, 21),
    "rump steak": (194, 28, 0, 8.3),       # SR Legacy #23086 bottom round steak, lean+fat 1/8", roasted
    "rump": (194, 28, 0, 8.3),
    "steak": (212, 27, 0, 10.6),           # default = sirloin (as above)
    # Ground beef family — one product should not appear twice with different macros,
    # so the generic aliases ("ground beef", "beef mince") default to 80/20 (retail standard).
    "ground beef": (272, 25.8, 0, 18.2),   # SR Legacy #23566 80/20, pan-browned, cooked
    "extra lean beef mince": (171, 26.5, 0, 6.9),  # SR Legacy #23576 95/5, pan-browned, cooked
    "premium beef mince": (171, 26.5, 0, 6.9),
    "premium ground beef": (171, 26.5, 0, 6.9),
    "5 star beef mince": (171, 26.5, 0, 6.9),
    "five star beef mince": (171, 26.5, 0, 6.9),
    "extra lean ground beef": (171, 26.5, 0, 6.9),
    "lean beef mince": (217, 26.6, 0, 11.7),  # SR Legacy #23572 90/10, pan-browned, cooked
    "lean ground beef": (217, 26.6, 0, 11.7),
    "fatty beef mince": (272, 25.8, 0, 18.2),  # SR Legacy #23566 80/20, pan-browned, cooked
    "regular beef mince": (272, 25.8, 0, 18.2),
    "fatty ground beef": (272, 25.8, 0, 18.2),
    "regular ground beef": (272, 25.8, 0, 18.2),
    "beef mince": (272, 25.8, 0, 18.2),     # default = 80/20 (retail standard)
    "beef": (212, 27, 0, 10.6),             # default = sirloin
    "extra lean beef": (175, 26, 0, 7),
    "lean beef": (175, 26, 0, 7),
    # Proteins - Fish/Seafood  (all COOKED)
    "salmon": (206, 22, 0, 12.4),          # SR Legacy #15236 Atlantic, farmed, cooked, dry heat
    "tilapia": (128, 26, 0, 2.7),          # SR Legacy #15261 tilapia, cooked, dry heat
    "tuna": (116, 25.5, 0, 0.8),           # SR Legacy #15122 light, canned in water, drained
    "shrimp": (99, 24, 0.2, 0.3),          # SR Legacy #15271 mixed species, cooked, moist heat
    "cod": (105, 23, 0, 0.9),              # SR Legacy #15016 Atlantic cod, cooked, dry heat
    "fish": (100, 20, 0, 2),  # generic fish
    # Proteins - Eggs/Dairy
    "egg": (155, 13, 1.1, 11),  # per 100g (about 2 eggs)
    "eggs": (155, 13, 1.1, 11),
    "whole eggs": (155, 13, 1.1, 11),
    "large eggs": (155, 13, 1.1, 11),
    "egg white": (52, 11, 0.7, 0.2),
    "egg whites": (52, 11, 0.7, 0.2),
    "greek yogurt": (59, 10, 4, 0.4),    # SR Legacy #01256 Greek plain, nonfat
    "yogurt": (59, 10, 4, 0.4),          # aliased to Greek nonfat (fitness-app convention)
    "cottage cheese": (84, 11, 4, 2.5),  # SR Legacy #01169 lowfat 2% milkfat
    # Proteins - Other
    "tofu": (144, 17, 3, 8),
    "tofu firm": (144, 17, 3, 8),
    "firm tofu": (144, 17, 3, 8),
    "tempeh": (192, 20, 8, 11),
    "seitan": (166, 25, 14, 2),          # wheat gluten — 25g P per 100g
    "edamame": (121, 11, 8, 5),           # shelled edamame — 11g P per 100g
    "shelled edamame": (121, 11, 8, 5),
    "nutritional yeast": (355, 50, 35, 7), # 50g P per 100g!
    "yeast flakes": (355, 50, 35, 7),      # alias for nutritional yeast
    # hemp seeds → declared with the rest of the seeds/nuts section below
    "tahini": (595, 17, 23, 54),           # sesame paste — high fat
    "pork": (242, 27, 0, 14),
    "pork chop": (231, 27, 0, 13),
    "bacon": (417, 13, 1.4, 40),
    "ham": (145, 21, 1, 6),
    # Carbs - Grains  (cooked unless the food is generally weighed dry in recipes)
    "rice": (130, 2.7, 28, 0.3),          # SR Legacy #20045 white long-grain, cooked
    "white rice": (130, 2.7, 28, 0.3),
    "brown rice": (123, 2.7, 25.6, 1),    # SR Legacy #20037 long-grain, cooked (was 112/2.6/24/0.9)
    "oats": (389, 17, 66, 7),             # SR Legacy #20038 raw oats — recipe convention (dry weight)
    "oatmeal": (68, 2.4, 12, 1.4),        # SR Legacy #08123 cooked with water
    "quinoa": (120, 4.4, 21, 1.9),        # SR Legacy #20137 cooked
    "pasta": (158, 5.8, 30.9, 0.9),       # SR Legacy #20421 enriched, cooked (was 131/5/25/1.1 — 20% cal understated)
    "whole wheat pasta": (149, 6, 30, 1.1), # SR Legacy #20124 whole-wheat, cooked
    "bread": (265, 9, 49, 3.2),
    "whole wheat bread": (247, 10, 41, 3.4),
    "wrap": (310, 8, 52, 8),
    "whole wheat wrap": (310, 8, 52, 8),
    "tortilla": (312, 8, 52, 8),
    "couscous": (112, 3.8, 23, 0.2),      # SR Legacy #20028 cooked (was 176/6/36/0.3 — was actually a dry-ish value)
    "cooked couscous": (112, 3.8, 23, 0.2),
    "bulgur": (83, 3, 19, 0.2),           # SR Legacy #20014 cooked
    "farro": (170, 7, 34, 1.5),           # no direct USDA row; industry-standard cooked farro
    "barley": (123, 2.3, 28, 0.4),        # SR Legacy #20005 pearled, cooked
    "noodles": (138, 5, 25, 2),           # SR Legacy #20110 egg noodles, cooked
    "ramen": (138, 5, 25, 2),
    "rice noodles": (109, 0.9, 25, 0.2),
    "soba noodles": (99, 5, 21, 0.1),
    "udon noodles": (118, 3, 24, 0.3),
    # Carbs - Starchy Vegetables
    "sweet potato": (86, 1.6, 20, 0.1),
    "potato": (77, 2, 17, 0.1),
    "potatoes": (77, 2, 17, 0.1),
    "corn": (86, 3.2, 19, 1.2),
    # Carbs - Fruits
    "banana": (89, 1.1, 23, 0.3),
    "bananas": (89, 1.1, 23, 0.3),
    "apple": (52, 0.3, 14, 0.2),
    "apples": (52, 0.3, 14, 0.2),
    "berries": (43, 1, 10, 0.3),
    "mixed berries": (43, 1, 10, 0.3),
    "orange": (47, 0.9, 12, 0.1),
    "oranges": (47, 0.9, 12, 0.1),
    "grapes": (67, 0.6, 17, 0.4),
    "mango": (60, 0.8, 15, 0.4),
    "pineapple": (50, 0.5, 13, 0.1),
    # Vegetables - Leafy Greens
    "spinach": (23, 2.9, 3.6, 0.4),
    "kale": (49, 4.3, 9, 0.9),
    "lettuce": (15, 1.4, 2.9, 0.2),
    "greens": (20, 2, 3.5, 0.3),  # generic greens
    "mixed greens": (20, 2, 3.5, 0.3),
    "salad greens": (20, 2, 3.5, 0.3),
    "romaine": (17, 1.2, 3.3, 0.3),
    "arugula": (25, 2.6, 3.7, 0.7),
    # Vegetables - Cruciferous
    "broccoli": (34, 2.8, 7, 0.4),
    "cauliflower": (25, 1.9, 5, 0.3),
    "cabbage": (25, 1.3, 6, 0.1),
    "brussels sprouts": (43, 3.4, 9, 0.3),
    # Vegetables - Other
    "asparagus": (20, 2.2, 4, 0.1),
    "zucchini": (17, 1.2, 3.1, 0.3),
    "bell pepper": (31, 1, 6, 0.3),
    "pepper": (31, 1, 6, 0.3),
    "peppers": (31, 1, 6, 0.3),
    "tomato": (18, 0.9, 3.9, 0.2),
    "tomatoes": (18, 0.9, 3.9, 0.2),
    "cherry tomatoes": (18, 0.9, 3.9, 0.2),
    "cucumber": (15, 0.7, 3.6, 0.1),
    "carrots": (41, 0.9, 10, 0.2),
    "carrot": (41, 0.9, 10, 0.2),
    "onion": (40, 1.1, 9, 0.1),
    "onions": (40, 1.1, 9, 0.1),
    "mushroom": (22, 3.1, 3.3, 0.3),
    "mushrooms": (22, 3.1, 3.3, 0.3),
    "avocado": (160, 2, 9, 15),
    "celery": (16, 0.7, 3, 0.2),
    "green beans": (31, 1.8, 7, 0.1),
    "peas": (81, 5.4, 14, 0.4),
    "mixed vegetables": (50, 2.5, 10, 0.3),
    "vegetables": (50, 2.5, 10, 0.3),
    "sweet peppers": (31, 1, 6, 0.3),
    "eggplant": (25, 1, 6, 0.2),
    "squash": (16, 0.6, 3.4, 0.2),
    "beets": (43, 1.6, 10, 0.2),
    "radish": (16, 0.7, 3.4, 0.1),
    "leek": (61, 1.5, 14, 0.3),
    "bok choy": (13, 1.5, 2, 0.2),
    # Fats/Oils
    "olive oil": (884, 0, 0, 100),
    "coconut oil": (862, 0, 0, 100),
    "vegetable oil": (884, 0, 0, 100),
    "butter": (717, 0.9, 0.1, 81),
    "ghee": (876, 0, 0, 97),
    "avocado oil": (884, 0, 0, 100),
    # Nuts and Seeds
    "almond": (579, 21, 22, 50),
    "almonds": (579, 21, 22, 50),
    "peanut butter": (588, 25, 20, 50),
    "almond butter": (614, 21, 19, 56),
    "walnut": (654, 15, 14, 65),
    "walnuts": (654, 15, 14, 65),
    "cashews": (553, 18, 30, 44),
    "peanuts": (567, 26, 16, 49),
    "seeds": (534, 18, 23, 45),  # average seeds
    "chia seeds": (486, 17, 42, 31),
    "flax seeds": (534, 18, 29, 42),
    "sunflower seeds": (584, 21, 20, 51),
    "pumpkin seeds": (559, 30, 11, 49),
    "hemp seeds": (553, 32, 9, 49),        # SR Legacy #12012 shelled hemp seeds — 32g P per 100g
    "hemp seed": (553, 32, 9, 49),
    "macadamia": (718, 8, 14, 76),
    "pecans": (691, 9, 14, 72),
    "pistachios": (560, 20, 28, 45),
    "hazelnuts": (628, 15, 17, 61),
    # Dairy
    "milk": (42, 3.4, 5, 1),
    "whole milk": (61, 3.2, 4.8, 3.3),
    "almond milk": (17, 0.6, 1.4, 1.1),
    "cheese": (403, 25, 1.3, 33),
    "cheddar": (403, 25, 1.3, 33),
    "mozzarella": (280, 28, 3, 17),
    "parmesan": (431, 38, 4, 29),
    "feta": (264, 14, 4, 21),
    "cream cheese": (342, 6, 4, 34),
    # Protein Supplements
    "whey protein": (400, 80, 10, 3.3),
    "protein powder": (400, 80, 10, 3.3),
    "protein": (400, 80, 10, 3.3),
    # Condiments/Spreads
    "hummus": (166, 8, 14, 10),
    "salsa": (36, 2, 8, 0.2),
    "mayo": (680, 1, 0, 75),
    "mayonnaise": (680, 1, 0, 75),
    "mustard": (66, 4, 5, 4),
    "honey": (304, 0.3, 82, 0),
    "maple syrup": (260, 0.1, 67, 0.1),
    # Legumes
    "black beans": (132, 9, 24, 0.5),
    "chickpeas": (164, 9, 27, 2.6),
    "lentils": (116, 9, 20, 0.4),
    "kidney beans": (127, 9, 23, 0.5),
    # Lamb
    "lamb": (258, 25, 0, 17),
    "lamb chop": (258, 25, 0, 17),
    "lamb chops": (258, 25, 0, 17),
    "lamb loin": (258, 25, 0, 17),
    "lamb leg": (225, 28, 0, 12),
    "ground lamb": (283, 23, 0, 21),
    "minced lamb": (283, 23, 0, 21),
    # More seafood
    "prawn": (99, 24, 0, 0.3),
    "prawns": (99, 24, 0, 0.3),
    "scallops": (111, 21, 5, 1),
    "crab": (97, 19, 0.5, 1.5),
    # Breakfast / snack staples
    "granola": (471, 10, 64, 20),
    "rice cake": (387, 8, 82, 3),
    "rice cakes": (387, 8, 82, 3),
    "blueberry": (57, 0.7, 14, 0.3),
    "blueberries": (57, 0.7, 14, 0.3),
    "strawberry": (32, 0.7, 8, 0.3),
    "strawberries": (32, 0.7, 8, 0.3),
    "raspberries": (52, 1.2, 12, 0.7),
    # Condiments
    "soy sauce": (53, 8, 5, 0),
    "tamari": (53, 8, 5, 0),
    "teriyaki sauce": (89, 3.5, 17, 0),
    "tomato sauce": (29, 1.5, 6, 0.3),
    "garlic": (149, 6, 33, 0.5),
    "ginger": (80, 1.8, 18, 0.8),
    # Vegan / specialty ingredients (frequently missing)
    "chickpea flour": (387, 22, 58, 6),
    "besan": (387, 22, 58, 6),         # Indian name for chickpea flour
    "dark chocolate": (598, 7.8, 43, 42),
    "dark chocolate chips": (598, 7.8, 43, 42),
    "cacao": (228, 20, 28, 14),
    "cocoa powder": (228, 20, 28, 14),
    "agave nectar": (310, 0.1, 76, 0),
    "agave syrup": (310, 0.1, 76, 0),
    "balsamic vinegar": (88, 0.5, 17, 0),
    "apple cider vinegar": (22, 0, 0.9, 0),
    "lemon juice": (22, 0.4, 7, 0.2),
    "lime juice": (25, 0.4, 8, 0.1),
    # nutritional yeast, yeast flakes → declared earlier (Proteins - Other section)
    "miso paste": (199, 12, 26, 6),
    "miso": (199, 12, 26, 6),
    "coconut aminos": (74, 2, 18, 0),
    "plant milk": (35, 1.5, 4, 1.8),   # generic plant milk
    "soy milk": (54, 3.3, 4.5, 2.2),
    "oat milk": (47, 1.5, 8, 0.9),
    "coconut yogurt": (100, 0.7, 6, 9),
    "soy yogurt": (67, 3.9, 6.6, 2.4),
    "vegan protein": (380, 72, 8, 5),  # generic vegan protein powder
    "pea protein": (380, 72, 8, 5),
    "brown sugar": (380, 0, 98, 0),
    # maple syrup → declared earlier (sweeteners section)
    # tahini → declared earlier (Proteins - Other section)
    "almond flour": (571, 21, 20, 50),
    "flaxseed meal": (534, 18, 29, 42),
    # chia seeds → declared earlier (seeds/nuts section)
    "spirulina": (290, 57, 24, 8),
    "maca powder": (325, 11, 66, 4),
    "matcha powder": (306, 26, 52, 5),
}

# ── Additional foods (USDA FoodData Central SR Legacy / FNDDS per 100g unless
# noted). Added so every template ingredient and the foods the AI is allowed to
# use resolve to a real entry instead of a wrong fuzzy match.
INGREDIENT_MACROS.update({
    # Proteins — meat
    "pork tenderloin": (143, 26, 0, 3.5),
    "pork loin": (196, 27.3, 0, 8.9),
    "pork sausage": (325, 18.5, 1.4, 27),
    "pork belly": (518, 9.3, 0, 53),
    "pork rinds": (544, 61, 0, 31),
    "prime rib": (340, 22, 0, 28),
    "flank steak": (192, 27.7, 0, 8.2),
    "eye of round": (169, 29, 0, 4.9),
    "beef brisket": (291, 28, 0, 19),
    "beef jerky": (410, 33.2, 11, 25.6),
    "beef liver": (175, 27, 5.1, 4.7),
    "chicken liver": (167, 24.5, 0.9, 6.5),
    "ground bison": (179, 25.5, 0, 8.6),
    "bison": (179, 25.5, 0, 8.6),
    "venison": (158, 30.2, 0, 3.2),
    "veal": (196, 31.9, 0, 6.6),
    "duck breast": (201, 23.5, 0, 11.2),
    "ground chicken": (189, 23.3, 0, 10.2),
    "chicken mince": (189, 23.3, 0, 10.2),
    "turkey mince": (203, 27, 0, 11.5),
    "turkey bacon": (233, 17, 1, 17),          # typical retail (15g slice = 35 cal)
    "chorizo": (455, 24, 1.9, 38),
    "beef mince 95/5": (171, 26.5, 0, 6.9),
    "beef mince 90/10": (217, 26.6, 0, 11.7),
    "beef mince 80/20": (272, 25.8, 0, 18.2),
    "ground beef 95/5": (171, 26.5, 0, 6.9),
    "ground beef 90/10": (217, 26.6, 0, 11.7),
    "ground beef 80/20": (272, 25.8, 0, 18.2),
    # Proteins — fish & seafood (cooked)
    "smoked salmon": (117, 18.3, 0, 4.3),
    "tuna steak": (130, 29, 0, 0.6),
    "sardines": (208, 24.6, 0, 11.5),
    "sardines in oil": (208, 24.6, 0, 11.5),
    "mackerel": (262, 23.9, 0, 17.8),
    "trout": (190, 26.6, 0, 8.5),
    "halibut": (111, 22.5, 0, 1.6),
    "sea bass": (124, 23.6, 0, 2.6),
    "haddock": (90, 20, 0, 0.6),
    "snapper": (128, 26.3, 0, 1.7),
    "mahi mahi": (109, 23.7, 0, 0.9),
    "white fish": (105, 23, 0, 0.9),
    "lobster": (89, 19, 0, 0.9),
    "mussels": (172, 23.8, 7.4, 4.5),
    # Eggs
    "egg yolk": (322, 15.9, 3.6, 26.5),
    # Dairy
    "cheddar cheese": (403, 25, 1.3, 33),
    "feta cheese": (264, 14, 4, 21),
    "parmesan cheese": (431, 38, 4, 29),
    "mozzarella cheese": (280, 28, 3, 17),
    "ricotta": (174, 11.3, 3, 13),
    "halloumi": (321, 22, 2.2, 25),
    "paneer": (296, 19, 6, 22),
    "kefir": (41, 3.8, 4.5, 0.9),
    "skyr": (63, 11, 4, 0.2),
    "greek yogurt 0%": (59, 10, 4, 0.4),
    "greek yogurt 2%": (73, 10, 3.9, 1.9),
    "full fat greek yogurt": (97, 9, 4, 5),
    "skim milk": (34, 3.4, 5, 0.1),
    "heavy cream": (340, 2.8, 2.7, 36),
    "sour cream": (198, 2.4, 4.6, 19.4),
    "mascarpone": (429, 4.6, 4.6, 44),
    "brie": (334, 20.8, 0.5, 27.7),
    "goat cheese": (364, 21.6, 0.1, 29.8),
    "gouda": (356, 25, 2.2, 27.4),
    "string cheese": (280, 28, 3, 17),
    "vegan cheese": (286, 1.5, 24, 21),        # coconut-oil based (typical retail)
    # Plant proteins & legumes (cooked)
    "silken tofu": (55, 4.8, 2.9, 2.7),
    "extra firm tofu": (144, 17, 3, 8),
    "baked beans": (94, 4.8, 21, 0.4),          # USDA #16005 canned, plain/vegetarian
    "pinto beans": (143, 9, 26.2, 0.7),
    "white beans": (139, 9.7, 25.1, 0.4),
    "cannellini beans": (139, 9.7, 25.1, 0.4),
    "butter beans": (115, 7.8, 20.9, 0.4),
    "lima beans": (115, 7.8, 20.9, 0.4),
    "split peas": (118, 8.3, 21, 0.4),
    "soybeans": (172, 18.2, 8.4, 9),
    "red lentils": (116, 9, 20, 0.4),
    "falafel": (333, 13.3, 31.8, 17.8),
    # Grains & starches (cooked unless stated; oats are DRY)
    "rolled oats": (389, 17, 66, 7),
    "cooked oats": (68, 2.4, 12, 1.4),
    "porridge": (68, 2.4, 12, 1.4),
    "basmati rice": (121, 3.5, 25.2, 0.4),
    "jasmine rice": (130, 2.7, 28, 0.3),
    "arborio rice": (130, 2.4, 28.6, 0.3),
    "wild rice": (101, 4, 21.3, 0.3),
    "uncooked rice": (365, 7.1, 80, 0.7),
    "dry pasta": (371, 13, 75, 1.5),
    "orzo": (158, 5.8, 30.9, 0.9),
    "spaghetti": (158, 5.8, 30.9, 0.9),
    "egg noodles": (138, 4.5, 25, 2.1),
    "buckwheat": (92, 3.4, 19.9, 0.6),
    "millet": (119, 3.5, 23.7, 1),
    "popcorn": (387, 13, 78, 4.5),
    "toast": (265, 9, 49, 3.2),
    "whole wheat toast": (247, 10, 41, 3.4),
    "sourdough bread": (270, 10.7, 51.9, 2.4),
    "rye bread": (259, 8.5, 48.3, 3.3),
    "ciabatta": (271, 9, 50, 3.6),
    "bagel": (250, 10.1, 48.9, 1.5),
    "naan": (291, 9.6, 50.4, 5.6),
    "english muffin": (235, 8.9, 46, 1.8),
    "pita bread": (275, 9.1, 55.7, 1.2),
    "whole wheat pita": (266, 9.8, 55, 2.6),
    "corn tortilla": (218, 5.7, 44.6, 2.9),
    "corn tortillas": (218, 5.7, 44.6, 2.9),
    "crackers": (430, 10, 69, 14),
    "whole grain crackers": (430, 10, 69, 14),
    "muesli": (363, 10, 66, 6),
    "plantain": (116, 0.8, 31, 0.2),
    "butternut squash": (45, 1, 11.7, 0.1),
    "parsnip": (75, 1.2, 18, 0.3),
    "pumpkin": (26, 1, 6.5, 0.1),
    # Fruit
    "pear": (57, 0.4, 15, 0.1),
    "peach": (39, 0.9, 9.5, 0.3),
    "kiwi": (61, 1.1, 14.7, 0.5),
    "watermelon": (30, 0.6, 7.6, 0.2),
    "cherries": (63, 1.1, 16, 0.2),
    "blackberries": (43, 1.4, 9.6, 0.5),
    "apricot": (48, 1.4, 11, 0.4),
    "grapefruit": (42, 0.8, 10.7, 0.1),
    "papaya": (43, 0.5, 10.8, 0.3),
    "plum": (46, 0.7, 11.4, 0.3),
    "nectarine": (44, 1.1, 10.6, 0.3),
    "pomegranate": (83, 1.7, 18.7, 1.2),
    "fig": (74, 0.8, 19.2, 0.3),
    "dates": (282, 2.5, 75, 0.4),
    "raisins": (299, 3.1, 79, 0.5),
    "dried cranberries": (308, 0.1, 82, 1.1),
    "lemon": (29, 1.1, 9.3, 0.3),
    "lime": (30, 0.7, 10.5, 0.2),
    "coconut": (354, 3.3, 15.2, 33.5),
    "coconut flakes": (660, 6.9, 23.7, 64.5),   # unsweetened, dried
    "orange juice": (45, 0.7, 10.4, 0.2),
    "coconut water": (19, 0.7, 3.7, 0.2),
    # Vegetables
    "romaine lettuce": (17, 1.2, 3.3, 0.3),
    "green onion": (32, 1.8, 7.3, 0.2),
    "spring onion": (32, 1.8, 7.3, 0.2),
    "scallions": (32, 1.8, 7.3, 0.2),
    "red onion": (40, 1.1, 9, 0.1),
    "shallot": (72, 2.5, 16.8, 0.1),
    "snap peas": (42, 2.8, 7.6, 0.2),
    "snow peas": (42, 2.8, 7.6, 0.2),
    "broccolini": (35, 3, 5.5, 0.4),
    "artichoke": (47, 3.3, 10.5, 0.2),
    "bean sprouts": (30, 3, 5.9, 0.2),
    "jalapeno": (29, 0.9, 6.5, 0.4),
    "capsicum": (31, 1, 6, 0.3),
    "red bell pepper": (31, 1, 6, 0.3),
    "olives": (115, 0.8, 6.3, 10.7),
    "pickles": (11, 0.3, 2.3, 0.2),
    "sauerkraut": (19, 0.9, 4.3, 0.1),
    "kimchi": (15, 1.1, 2.4, 0.5),
    "spaghetti squash": (27, 0.7, 6.5, 0.3),
    "cauliflower rice": (25, 1.9, 5, 0.3),
    "zucchini noodles": (17, 1.2, 3.1, 0.3),
    "swiss chard": (19, 1.8, 3.7, 0.2),
    "collard greens": (32, 3, 5.4, 0.6),
    "fennel": (31, 1.2, 7.3, 0.2),
    "okra": (33, 1.9, 7.5, 0.2),
    "tomato paste": (82, 4.3, 18.9, 0.5),
    "canned tomatoes": (32, 1.6, 7.3, 0.3),
    "sweet corn": (86, 3.2, 19, 1.2),
    # Herbs, spices & seasonings (tiny amounts)
    "salt": (0, 0, 0, 0),
    "sea salt": (0, 0, 0, 0),
    "black pepper": (251, 10.4, 64, 3.3),
    "cayenne pepper": (318, 12, 57, 17),
    "red pepper flakes": (318, 12, 57, 17),
    "chili flakes": (318, 12, 57, 17),
    "chili powder": (282, 13.5, 50, 14.3),
    "paprika": (282, 14, 54, 13),
    "smoked paprika": (282, 14, 54, 13),
    "cumin": (375, 17.8, 44, 22),
    "cinnamon": (247, 4, 81, 1.2),
    "turmeric": (312, 9.7, 67, 3.3),
    "curry powder": (325, 14.3, 56, 14),
    "garlic powder": (331, 16.6, 73, 0.7),
    "onion powder": (341, 10.4, 79, 1),
    "oregano": (265, 9, 69, 4.3),
    "italian seasoning": (265, 9, 69, 4.3),
    "dried herbs": (265, 9, 69, 4.3),
    "thyme": (101, 5.6, 24, 1.7),
    "rosemary": (131, 3.3, 20.7, 5.9),
    "basil": (23, 3.2, 2.7, 0.6),
    "cilantro": (23, 2.1, 3.7, 0.5),
    "parsley": (36, 3, 6.3, 0.8),
    "dill": (43, 3.5, 7, 1.1),
    "mint": (70, 3.8, 15, 0.9),
    "capers": (23, 2.4, 4.9, 0.9),
    "vanilla extract": (288, 0.1, 12.7, 0.1),
    "stevia": (0, 0, 0, 0),
    # Sauces & condiments
    "marinara sauce": (50, 1.5, 8, 1.5),
    "marinara": (50, 1.5, 8, 1.5),
    "pesto": (418, 4.9, 6.2, 42),
    "vinegar": (18, 0, 0, 0),
    "red wine vinegar": (19, 0, 0.3, 0),
    "rice vinegar": (18, 0, 0, 0),
    "hot sauce": (12, 0.5, 1.8, 0.4),
    "sriracha": (93, 1.9, 19, 0.9),
    "worcestershire sauce": (78, 0, 19.5, 0),
    "fish sauce": (35, 5, 3.6, 0),
    "dijon mustard": (66, 4, 5, 4),
    "ketchup": (101, 1, 27, 0.1),
    "bbq sauce": (172, 0.8, 41, 0.6),
    "hoisin sauce": (220, 3.3, 44, 3.4),
    "oyster sauce": (51, 1.4, 11, 0.3),
    "sugar": (387, 0, 100, 0),
    "jam": (278, 0.4, 69, 0.1),
    "vegetable broth": (6, 0.2, 1, 0.2),
    "chicken broth": (6, 0.6, 0.4, 0.2),
    "bone broth": (17, 3.8, 0, 0.2),
    # Fats, oils, nuts & seeds
    "sesame oil": (884, 0, 0, 100),
    "beef tallow": (902, 0, 0, 100),
    "tallow": (902, 0, 0, 100),
    "lard": (902, 0, 0, 100),
    "chicken fat": (900, 0, 0, 99.8),
    "duck fat": (882, 0, 0, 99.8),
    "coconut cream": (330, 3.6, 6.7, 34.7),
    "coconut milk": (230, 2.3, 5.5, 23.8),     # USDA #12118 canned, full fat
    "light coconut milk": (74, 0.6, 2.8, 7),
    "coconut milk light": (74, 0.6, 2.8, 7),
    "macadamia nuts": (718, 8, 14, 76),
    "sesame seeds": (573, 17.7, 23.5, 49.7),
    "pine nuts": (673, 13.7, 13, 68.4),
    "brazil nuts": (659, 14.3, 11.7, 67.1),
    "mixed nuts": (594, 17.3, 25.4, 51.5),
    "cashew butter": (587, 17.6, 27.6, 49.4),
    "sunflower seed butter": (617, 17.3, 23.3, 55.2),
    "rice milk": (47, 0.3, 9.2, 1),
    "whey isolate": (370, 90, 1, 1),
    "pea protein powder": (380, 72, 8, 5),
    "egg white protein": (380, 80, 6, 0.5),
})
