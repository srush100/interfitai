"""Fallback meal templates (used only when AI generation fails).

Each ingredient stores GRAMS ONLY. Macros are always calculated in code from
food_database.INGREDIENT_MACROS, so template numbers can never drift from the
food that is listed.
"""

KETO_TEMPLATES = {
    "day1": {
        "breakfast": {
            "name": "Keto Egg & Bacon Plate",
            "ingredients": {
                "eggs": 150,
                "bacon": 60,
                "avocado": 100,
                "butter": 15,
            },
            "instructions": "Fry eggs in butter, crisp bacon, serve with fresh avocado slices",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Grilled Salmon with Greens",
            "ingredients": {
                "salmon": 200,
                "olive oil": 20,
                "spinach": 100,
                "cheese": 30,
            },
            "instructions": "Grill salmon, serve on bed of sautéed spinach with melted cheese",
            "prep_time": 20,
        },
        "dinner": {
            "name": "Ribeye Steak with Asparagus",
            "ingredients": {
                "ribeye steak": 250,
                "asparagus": 150,
                "butter": 20,
            },
            "instructions": "Pan-sear ribeye to preference, serve with butter-grilled asparagus",
            "prep_time": 25,
        },
        "snack": {
            "name": "Cheese & Nut Plate",
            "ingredients": {
                "cheddar cheese": 50,
                "macadamia nuts": 30,
            },
            "instructions": "Arrange cheese slices with macadamia nuts",
            "prep_time": 5,
        },
    },
    "day2": {
        "breakfast": {
            "name": "Keto Omelette",
            "ingredients": {
                "eggs": 200,
                "cheese": 40,
                "mushrooms": 50,
                "butter": 15,
            },
            "instructions": "Make fluffy omelette with cheese and sautéed mushrooms",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Chicken Thighs with Caesar Salad",
            "ingredients": {
                "chicken thighs": 200,
                "romaine lettuce": 100,
                "parmesan": 30,
                "olive oil": 20,
            },
            "instructions": "Grill chicken thighs, serve over romaine with parmesan and olive oil dressing",
            "prep_time": 25,
        },
        "dinner": {
            "name": "Bunless Burger with Cheese",
            "ingredients": {
                "ground beef 80% lean": 200,
                "cheese": 40,
                "avocado": 80,
                "lettuce wrap": 50,
            },
            "instructions": "Form patty, grill to preference, top with cheese and avocado in lettuce wrap",
            "prep_time": 20,
        },
        "snack": {
            "name": "Cream Cheese Celery",
            "ingredients": {
                "cream cheese": 60,
                "celery": 100,
                "pecans": 20,
            },
            "instructions": "Fill celery stalks with cream cheese, top with pecans",
            "prep_time": 5,
        },
    },
    "day3": {
        "breakfast": {
            "name": "Smoked Salmon & Eggs",
            "ingredients": {
                "smoked salmon": 100,
                "eggs": 150,
                "cream cheese": 40,
                "capers": 10,
            },
            "instructions": "Scramble eggs, serve with smoked salmon, cream cheese, and capers",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Tuna Salad Avocado Boats",
            "ingredients": {
                "tuna": 150,
                "avocado": 200,
                "mayonnaise": 30,
                "celery": 30,
            },
            "instructions": "Mix tuna with mayo and celery, serve in halved avocados",
            "prep_time": 10,
        },
        "dinner": {
            "name": "Pork Chops with Broccoli",
            "ingredients": {
                "pork chops": 200,
                "broccoli": 150,
                "butter": 25,
                "garlic": 5,
            },
            "instructions": "Pan-fry pork chops in butter with garlic, serve with steamed broccoli",
            "prep_time": 25,
        },
        "snack": {
            "name": "String Cheese & Almonds",
            "ingredients": {
                "mozzarella string cheese": 56,
                "almonds": 30,
            },
            "instructions": "Simple snack plate",
            "prep_time": 2,
        },
    },
}

CARNIVORE_TEMPLATES = {
    "day1": {
        "breakfast": {
            "name": "Steak and Eggs",
            "ingredients": {
                "ribeye steak": 200,
                "eggs": 150,
                "butter": 20,
            },
            "instructions": "Pan-sear steak in butter, fry eggs to preference",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Ground Beef Patties",
            "ingredients": {
                "ground beef 80% lean": 300,
                "butter": 15,
                "salt": 2,
            },
            "instructions": "Form patties, cook in butter, season with salt",
            "prep_time": 15,
        },
        "dinner": {
            "name": "Roasted Chicken Thighs",
            "ingredients": {
                "chicken thighs": 350,
                "chicken fat": 20,
            },
            "instructions": "Roast chicken thighs with rendered fat until crispy",
            "prep_time": 40,
        },
        "snack": {
            "name": "Beef Jerky",
            "ingredients": {
                "beef jerky": 50,
                "pork rinds": 30,
            },
            "instructions": "Simple meat-based snack",
            "prep_time": 0,
        },
    },
    "day2": {
        "breakfast": {
            "name": "Bacon and Eggs Feast",
            "ingredients": {
                "bacon": 100,
                "eggs": 200,
                "butter": 10,
            },
            "instructions": "Crisp bacon, scramble eggs in bacon fat and butter",
            "prep_time": 20,
        },
        "lunch": {
            "name": "Lamb Chops",
            "ingredients": {
                "lamb chops": 300,
                "butter": 15,
            },
            "instructions": "Pan-sear lamb chops in butter to medium-rare",
            "prep_time": 20,
        },
        "dinner": {
            "name": "Prime Rib Roast",
            "ingredients": {
                "prime rib": 350,
                "beef tallow": 15,
            },
            "instructions": "Roast prime rib with beef tallow coating",
            "prep_time": 90,
        },
        "snack": {
            "name": "Sardines",
            "ingredients": {
                "sardines in oil": 100,
            },
            "instructions": "Eat straight from the can",
            "prep_time": 0,
        },
    },
    "day3": {
        "breakfast": {
            "name": "Sausage and Eggs",
            "ingredients": {
                "pork sausage": 150,
                "eggs": 150,
                "butter": 15,
            },
            "instructions": "Pan-fry sausages, cook eggs in remaining fat",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Bison Burgers",
            "ingredients": {
                "ground bison": 300,
                "beef tallow": 20,
            },
            "instructions": "Form patties, cook in beef tallow",
            "prep_time": 15,
        },
        "dinner": {
            "name": "Salmon Steaks",
            "ingredients": {
                "salmon steaks": 300,
                "butter": 25,
            },
            "instructions": "Pan-sear salmon steaks in butter",
            "prep_time": 20,
        },
        "snack": {
            "name": "Bone Broth",
            "ingredients": {
                "bone broth": 400,
                "butter": 15,
            },
            "instructions": "Heat bone broth, add butter for fat",
            "prep_time": 5,
        },
    },
}

PALEO_TEMPLATES = {
    "day1": {
        "breakfast": {
            "name": "Sweet Potato Hash with Eggs",
            "ingredients": {
                "sweet potato": 150,
                "eggs": 150,
                "coconut oil": 15,
                "bell peppers": 50,
            },
            "instructions": "Cube and fry sweet potato in coconut oil, add peppers, top with eggs",
            "prep_time": 20,
        },
        "lunch": {
            "name": "Grilled Chicken with Roasted Vegetables",
            "ingredients": {
                "chicken breast": 200,
                "zucchini": 100,
                "carrots": 80,
                "olive oil": 20,
            },
            "instructions": "Grill chicken, roast vegetables with olive oil",
            "prep_time": 30,
        },
        "dinner": {
            "name": "Grass-Fed Steak with Salad",
            "ingredients": {
                "sirloin steak": 220,
                "mixed greens": 100,
                "avocado": 100,
                "olive oil": 15,
            },
            "instructions": "Grill steak, serve with fresh salad and avocado",
            "prep_time": 25,
        },
        "snack": {
            "name": "Fruit and Nuts",
            "ingredients": {
                "apple": 150,
                "almonds": 30,
                "walnuts": 20,
            },
            "instructions": "Simple paleo snack plate",
            "prep_time": 2,
        },
    },
    "day2": {
        "breakfast": {
            "name": "Banana Egg Pancakes",
            "ingredients": {
                "banana": 150,
                "eggs": 150,
                "almond butter": 30,
                "coconut oil": 10,
            },
            "instructions": "Blend banana and eggs, cook as pancakes, top with almond butter",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Turkey Lettuce Wraps",
            "ingredients": {
                "ground turkey": 200,
                "lettuce": 80,
                "tomato": 80,
                "avocado": 80,
            },
            "instructions": "Cook seasoned turkey, serve in lettuce cups with toppings",
            "prep_time": 20,
        },
        "dinner": {
            "name": "Baked Salmon with Asparagus",
            "ingredients": {
                "salmon": 200,
                "asparagus": 150,
                "lemon": 30,
                "olive oil": 15,
            },
            "instructions": "Bake salmon with lemon, roast asparagus in olive oil",
            "prep_time": 25,
        },
        "snack": {
            "name": "Berries and Coconut",
            "ingredients": {
                "mixed berries": 150,
                "coconut flakes": 30,
            },
            "instructions": "Mix berries with unsweetened coconut flakes",
            "prep_time": 2,
        },
    },
    "day3": {
        "breakfast": {
            "name": "Veggie Omelette",
            "ingredients": {
                "eggs": 200,
                "spinach": 50,
                "tomato": 50,
                "coconut oil": 15,
                "avocado": 80,
            },
            "instructions": "Make omelette with veggies, serve with avocado",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Shrimp Stir Fry",
            "ingredients": {
                "shrimp": 200,
                "broccoli": 100,
                "bell pepper": 80,
                "coconut aminos": 15,
                "coconut oil": 15,
            },
            "instructions": "Stir fry shrimp and vegetables in coconut oil with coconut aminos",
            "prep_time": 20,
        },
        "dinner": {
            "name": "Pork Tenderloin with Sweet Potato",
            "ingredients": {
                "pork tenderloin": 200,
                "sweet potato": 200,
                "olive oil": 15,
                "rosemary": 2,
            },
            "instructions": "Roast pork with rosemary, bake sweet potato",
            "prep_time": 35,
        },
        "snack": {
            "name": "Guacamole with Veggies",
            "ingredients": {
                "avocado": 100,
                "cucumber": 100,
                "carrots": 50,
            },
            "instructions": "Mash avocado for guac, serve with veggie sticks",
            "prep_time": 5,
        },
    },
}

VEGAN_TEMPLATES = {
    "day1": {
        "breakfast": {
            "name": "High Protein Tofu Scramble",
            "ingredients": {
                "extra firm tofu": 250,
                "edamame": 100,
                "spinach": 50,
                "nutritional yeast": 20,
                "olive oil": 10,
            },
            "instructions": "Crumble and sauté tofu with edamame and spinach, finish with nutritional yeast",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Seitan & Quinoa Power Bowl",
            "ingredients": {
                "seitan": 150,
                "quinoa": 150,
                "chickpeas": 100,
                "tahini": 20,
                "kale": 60,
            },
            "instructions": "Sear seitan, serve over quinoa with roasted chickpeas, kale, and tahini drizzle",
            "prep_time": 25,
        },
        "dinner": {
            "name": "Tempeh Lentil Curry",
            "ingredients": {
                "tempeh": 200,
                "red lentils": 100,
                "brown rice": 150,
                "coconut milk light": 80,
                "spinach": 50,
            },
            "instructions": "Cube tempeh, simmer with lentils and coconut milk, serve over rice with spinach",
            "prep_time": 35,
        },
        "snack": {
            "name": "Protein Edamame Bowl",
            "ingredients": {
                "edamame": 150,
                "pumpkin seeds": 25,
                "sea salt": 1,
            },
            "instructions": "Steam edamame, sprinkle with pumpkin seeds and sea salt",
            "prep_time": 5,
        },
    },
    "day2": {
        "breakfast": {
            "name": "Protein Oat Bowl",
            "ingredients": {
                "oats": 60,
                "pea protein powder": 30,
                "soy milk": 200,
                "peanut butter": 25,
                "chia seeds": 15,
            },
            "instructions": "Cook oats with soy milk, stir in protein powder and peanut butter, top with chia",
            "prep_time": 10,
        },
        "lunch": {
            "name": "Black Bean Tempeh Tacos",
            "ingredients": {
                "tempeh": 150,
                "black beans": 150,
                "corn tortillas": 60,
                "avocado": 75,
                "salsa": 60,
            },
            "instructions": "Crumble tempeh, warm with black beans, serve in tortillas with avocado and salsa",
            "prep_time": 20,
        },
        "dinner": {
            "name": "Seitan Stir Fry",
            "ingredients": {
                "seitan": 200,
                "brown rice": 150,
                "broccoli": 120,
                "bell pepper": 80,
                "soy sauce": 15,
                "sesame oil": 10,
            },
            "instructions": "Slice seitan, stir fry with vegetables and soy sauce, serve over rice",
            "prep_time": 25,
        },
        "snack": {
            "name": "Soy Yogurt with Seeds",
            "ingredients": {
                "soy yogurt": 200,
                "hemp seeds": 25,
                "almonds": 20,
            },
            "instructions": "Top soy yogurt with hemp seeds and almonds",
            "prep_time": 3,
        },
    },
    "day3": {
        "breakfast": {
            "name": "High Protein Smoothie Bowl",
            "ingredients": {
                "silken tofu": 200,
                "pea protein powder": 35,
                "banana": 100,
                "peanut butter": 30,
                "soy milk": 100,
            },
            "instructions": "Blend silken tofu with protein powder, banana, and soy milk until smooth, top with peanut butter",
            "prep_time": 10,
        },
        "lunch": {
            "name": "Lentil Falafel Plate",
            "ingredients": {
                "lentils": 150,
                "falafel": 120,
                "hummus": 80,
                "whole wheat pita": 60,
                "cucumber": 60,
            },
            "instructions": "Serve lentils with falafel, hummus, pita bread, and fresh cucumber",
            "prep_time": 20,
        },
        "dinner": {
            "name": "Tofu & Tempeh Vegetable Pasta",
            "ingredients": {
                "extra firm tofu": 150,
                "tempeh": 100,
                "whole wheat pasta": 120,
                "tomato sauce": 100,
                "nutritional yeast": 15,
                "olive oil": 10,
            },
            "instructions": "Cube tofu and tempeh, pan fry, toss with pasta and tomato sauce, finish with nutritional yeast",
            "prep_time": 30,
        },
        "snack": {
            "name": "Roasted Chickpea Snack",
            "ingredients": {
                "chickpeas": 150,
                "pumpkin seeds": 20,
                "olive oil": 5,
            },
            "instructions": "Roast chickpeas with olive oil until crispy, mix with pumpkin seeds",
            "prep_time": 25,
        },
    },
}

VEGETARIAN_TEMPLATES = {
    "day1": {
        "breakfast": {
            "name": "Greek Yogurt Parfait",
            "ingredients": {
                "greek yogurt": 250,
                "granola": 40,
                "berries": 100,
                "honey": 15,
            },
            "instructions": "Layer yogurt with granola, berries, and honey drizzle",
            "prep_time": 5,
        },
        "lunch": {
            "name": "Caprese Panini",
            "ingredients": {
                "mozzarella": 100,
                "ciabatta bread": 80,
                "tomato": 100,
                "pesto": 20,
                "olive oil": 10,
            },
            "instructions": "Layer mozzarella and tomato with pesto on bread, grill until melted",
            "prep_time": 15,
        },
        "dinner": {
            "name": "Vegetable Stir Fry with Tofu",
            "ingredients": {
                "tofu": 200,
                "brown rice": 200,
                "broccoli": 100,
                "bell pepper": 80,
                "soy sauce": 15,
                "sesame oil": 10,
            },
            "instructions": "Crisp tofu, stir fry with vegetables, serve over rice",
            "prep_time": 25,
        },
        "snack": {
            "name": "Cottage Cheese & Fruit",
            "ingredients": {
                "cottage cheese": 150,
                "peach": 150,
            },
            "instructions": "Top cottage cheese with sliced peach",
            "prep_time": 3,
        },
    },
    "day2": {
        "breakfast": {
            "name": "Veggie Omelette",
            "ingredients": {
                "eggs": 150,
                "cheese": 30,
                "spinach": 50,
                "mushrooms": 50,
                "butter": 10,
            },
            "instructions": "Make fluffy omelette with veggies and cheese",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Quinoa Salad Bowl",
            "ingredients": {
                "quinoa": 200,
                "feta cheese": 50,
                "cucumber": 100,
                "tomato": 100,
                "olive oil": 15,
            },
            "instructions": "Toss cooked quinoa with vegetables and feta",
            "prep_time": 25,
        },
        "dinner": {
            "name": "Eggplant Parmesan",
            "ingredients": {
                "eggplant": 200,
                "mozzarella": 80,
                "parmesan": 30,
                "marinara sauce": 100,
                "olive oil": 15,
            },
            "instructions": "Bread and bake eggplant, top with sauce and cheese",
            "prep_time": 40,
        },
        "snack": {
            "name": "Cheese and Crackers",
            "ingredients": {
                "cheddar cheese": 40,
                "whole grain crackers": 30,
            },
            "instructions": "Simple snack plate",
            "prep_time": 2,
        },
    },
    "day3": {
        "breakfast": {
            "name": "Avocado Toast with Eggs",
            "ingredients": {
                "whole wheat bread": 60,
                "avocado": 100,
                "eggs": 100,
                "olive oil": 5,
            },
            "instructions": "Toast bread, top with mashed avocado and poached eggs",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Lentil Soup with Bread",
            "ingredients": {
                "lentils": 150,
                "carrots": 50,
                "celery": 30,
                "crusty bread": 60,
                "olive oil": 15,
            },
            "instructions": "Simmer lentils with vegetables, serve with bread",
            "prep_time": 35,
        },
        "dinner": {
            "name": "Mushroom Risotto",
            "ingredients": {
                "arborio rice": 150,
                "mushrooms": 150,
                "parmesan": 40,
                "butter": 20,
                "vegetable broth": 200,
            },
            "instructions": "Cook risotto with mushrooms, finish with butter and parmesan",
            "prep_time": 30,
        },
        "snack": {
            "name": "Hummus and Pita",
            "ingredients": {
                "hummus": 80,
                "pita bread": 40,
            },
            "instructions": "Serve hummus with warm pita triangles",
            "prep_time": 3,
        },
    },
}

HIGH_PROTEIN_TEMPLATES = {
    "day1": {
        "breakfast": {
            "name": "Protein Oatmeal",
            "ingredients": {
                "oats": 50,
                "whey protein": 30,
                "milk": 200,
                "banana": 80,
            },
            "instructions": "Cook oats with milk, stir in protein powder, top with banana",
            "prep_time": 10,
        },
        "lunch": {
            "name": "Double Chicken Breast",
            "ingredients": {
                "chicken breast": 250,
                "brown rice": 150,
                "broccoli": 100,
                "olive oil": 10,
            },
            "instructions": "Grill extra-large chicken breast, serve with rice and broccoli",
            "prep_time": 25,
        },
        "dinner": {
            "name": "Lean Steak with Potato",
            "ingredients": {
                "sirloin steak": 250,
                "white potato": 200,
                "asparagus": 100,
                "olive oil": 10,
            },
            "instructions": "Grill lean steak, bake potato, roast asparagus",
            "prep_time": 30,
        },
        "snack": {
            "name": "Protein Shake",
            "ingredients": {
                "whey protein": 40,
                "milk": 300,
                "banana": 100,
            },
            "instructions": "Blend protein with milk and banana",
            "prep_time": 5,
        },
    },
    "day2": {
        "breakfast": {
            "name": "Egg White Scramble",
            "ingredients": {
                "egg whites": 200,
                "whole eggs": 100,
                "turkey bacon": 50,
                "whole wheat toast": 40,
            },
            "instructions": "Scramble egg whites with whole eggs, serve with turkey bacon and toast",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Tuna Steak Salad",
            "ingredients": {
                "tuna steak": 200,
                "mixed greens": 100,
                "quinoa": 100,
                "olive oil": 15,
            },
            "instructions": "Sear tuna steak, serve over greens and quinoa",
            "prep_time": 20,
        },
        "dinner": {
            "name": "Turkey Meatballs with Pasta",
            "ingredients": {
                "ground turkey": 250,
                "whole wheat pasta": 150,
                "marinara": 100,
                "parmesan": 20,
            },
            "instructions": "Form and bake turkey meatballs, serve over pasta with sauce",
            "prep_time": 35,
        },
        "snack": {
            "name": "Greek Yogurt Protein Bowl",
            "ingredients": {
                "greek yogurt": 250,
                "whey protein": 15,
                "almonds": 20,
            },
            "instructions": "Mix protein into yogurt, top with almonds",
            "prep_time": 5,
        },
    },
    "day3": {
        "breakfast": {
            "name": "Cottage Cheese Pancakes",
            "ingredients": {
                "cottage cheese": 200,
                "eggs": 100,
                "oats": 30,
                "berries": 80,
            },
            "instructions": "Blend cottage cheese with eggs and oats, cook as pancakes, top with berries",
            "prep_time": 20,
        },
        "lunch": {
            "name": "Salmon Power Bowl",
            "ingredients": {
                "salmon": 200,
                "brown rice": 150,
                "edamame": 80,
                "cucumber": 60,
            },
            "instructions": "Bake salmon, serve over rice with edamame and cucumber",
            "prep_time": 25,
        },
        "dinner": {
            "name": "Chicken & Egg Fried Rice",
            "ingredients": {
                "chicken breast": 180,
                "eggs": 100,
                "brown rice": 200,
                "vegetables": 100,
                "soy sauce": 10,
            },
            "instructions": "Stir fry chicken and eggs with rice and vegetables",
            "prep_time": 25,
        },
        "snack": {
            "name": "Protein Cottage Cheese",
            "ingredients": {
                "cottage cheese": 200,
                "pineapple": 100,
            },
            "instructions": "Top cottage cheese with pineapple chunks",
            "prep_time": 3,
        },
    },
}

BALANCED_TEMPLATES = {
    "day1": {
        "breakfast": {
            "name": "Oatmeal Power Bowl",
            "ingredients": {
                "oats (dry)": 50,
                "milk": 200,
                "banana": 100,
                "almonds": 25,
            },
            "instructions": "Cook oats with milk, top with sliced banana and almonds",
            "prep_time": 10,
        },
        "lunch": {
            "name": "Grilled Chicken & Rice Bowl",
            "ingredients": {
                "chicken breast": 180,
                "brown rice (cooked)": 200,
                "broccoli": 100,
                "olive oil": 14,
            },
            "instructions": "Grill seasoned chicken breast, serve over brown rice with steamed broccoli drizzled with olive oil",
            "prep_time": 25,
        },
        "dinner": {
            "name": "Baked Salmon & Sweet Potato",
            "ingredients": {
                "salmon": 180,
                "sweet potato": 200,
                "asparagus": 100,
                "olive oil": 14,
            },
            "instructions": "Bake salmon fillet, roast sweet potato and asparagus with olive oil at 400°F for 25 minutes",
            "prep_time": 30,
        },
        "snack": {
            "name": "Protein Yogurt Bowl",
            "ingredients": {
                "greek yogurt": 200,
                "berries": 100,
                "whey protein": 30,
            },
            "instructions": "Mix protein powder into Greek yogurt, top with fresh berries",
            "prep_time": 5,
        },
    },
    "day2": {
        "breakfast": {
            "name": "Scrambled Eggs with Toast",
            "ingredients": {
                "egg": 150,
                "whole wheat bread": 60,
                "butter": 10,
                "orange": 150,
            },
            "instructions": "Scramble eggs in butter, serve with toasted bread and fresh orange segments",
            "prep_time": 15,
        },
        "lunch": {
            "name": "Turkey Rice Bowl",
            "ingredients": {
                "ground turkey": 200,
                "white rice (cooked)": 200,
                "spinach": 100,
                "olive oil": 14,
            },
            "instructions": "Cook seasoned ground turkey, serve over rice with sautéed spinach",
            "prep_time": 20,
        },
        "dinner": {
            "name": "Grilled Tilapia with Quinoa",
            "ingredients": {
                "tilapia": 200,
                "quinoa (cooked)": 200,
                "zucchini": 150,
                "olive oil": 14,
            },
            "instructions": "Grill tilapia, serve with fluffy quinoa and roasted zucchini",
            "prep_time": 25,
        },
        "snack": {
            "name": "Cottage Cheese & Fruit",
            "ingredients": {
                "cottage cheese": 200,
                "apple": 150,
                "walnuts": 20,
            },
            "instructions": "Top cottage cheese with diced apple and crushed walnuts",
            "prep_time": 5,
        },
    },
    "day3": {
        "breakfast": {
            "name": "Protein Smoothie Bowl",
            "ingredients": {
                "whey protein": 30,
                "banana": 150,
                "milk": 200,
                "peanut butter": 30,
            },
            "instructions": "Blend protein powder, banana, milk into thick smoothie, top with peanut butter drizzle",
            "prep_time": 10,
        },
        "lunch": {
            "name": "Beef & Potato Bowl",
            "ingredients": {
                "ground beef 90% lean": 180,
                "white potato": 250,
                "bell pepper": 100,
                "olive oil": 14,
            },
            "instructions": "Brown ground beef with spices, serve over roasted potato cubes with sautéed peppers",
            "prep_time": 25,
        },
        "dinner": {
            "name": "Shrimp Stir Fry",
            "ingredients": {
                "shrimp": 200,
                "brown rice (cooked)": 200,
                "mixed vegetables": 150,
                "olive oil": 20,
            },
            "instructions": "Stir fry shrimp with vegetables in olive oil, serve over brown rice",
            "prep_time": 20,
        },
        "snack": {
            "name": "Greek Yogurt Parfait",
            "ingredients": {
                "greek yogurt": 200,
                "berries": 100,
                "almonds": 25,
            },
            "instructions": "Layer Greek yogurt with berries and crushed almonds",
            "prep_time": 5,
        },
    },
}

TEMPLATES_BY_STYLE = {
    "keto": KETO_TEMPLATES,
    "carnivore": CARNIVORE_TEMPLATES,
    "paleo": PALEO_TEMPLATES,
    "vegan": VEGAN_TEMPLATES,
    "vegetarian": VEGETARIAN_TEMPLATES,
    "high_protein": HIGH_PROTEIN_TEMPLATES,
    "balanced": BALANCED_TEMPLATES,
}
