# Meal plan verification — real generated plans

Generated 2026-10-20 23:12 UTC against https://nutrition-debug-1.preview.emergentagent.com/api. “Calculated from ingredients” = grams ÷ 100 × the database's per-100g values, rounded per ingredient exactly as the app shows them.


## Summary

| Plan | Meals match ingredients | Days within 5% | Allergy/diet safe | Swap (Day 1) | Swap: match / within 5% / safe |
|---|---|---|---|---|---|
| balanced | ✅ 3/3 days | ✅ 3/3 | ✅ | Protein-Packed Blueberry Oat Pancakes with Almond Butter → Scrambled Eggs with Whole Wheat Toast, Smoked Salmon, and Fresh Berries | ✅ / ✅ / ✅ |
| high_protein | ✅ 3/3 days | ✅ 3/3 | ✅ | Grilled Chicken & Sweet Potato Power Bowl → Spiced Chicken & Arborio Risotto with Roasted Vegetables | ✅ / ✅ / ✅ |
| vegetarian | ✅ 3/3 days | ✅ 3/3 | ✅ | Tempeh Stir-Fry with Brown Rice → Chickpea Curry with Basmati Rice | ✅ / ✅ / ✅ |
| vegan | ✅ 3/3 days | ✅ 3/3 | ✅ | Chocolate Peanut Butter Protein Smoothie → Peanut Butter Banana Protein Bites | ✅ / ✅ / ✅ |
| paleo | ✅ 3/3 days | ✅ 3/3 | ✅ | Sweet Potato Hash with Poached Eggs & Avocado → Spiced Duck Scramble with Roasted Root Vegetables | ✅ / ✅ / ✅ |
| keto | ✅ 3/3 days | ✅ 3/3 | ✅ | Salmon Bowl with Cauliflower Rice → Seared Tuna Steak with Avocado & Sesame Greens | ✅ / ✅ / ✅ |
| carnivore | ✅ 3/3 days | ✅ 3/3 | ✅ | Prime Rib with Bone Marrow Butter → Pan-Seared Duck Breast with Gouda & Egg Yolk | ✅ / ✅ / ✅ |
| balanced + allergies ['gluten', 'dairy'] | ✅ 3/3 days | ✅ 3/3 | ✅ | Tropical Mango Cashew Protein Snack → Banana Cashew Protein Energy Balls | ✅ / ✅ / ✅ |
| vegan + allergies ['nuts', 'soy'] | ✅ 3/3 days | ✅ 3/3 | ✅ | Protein-Packed Berry Quinoa Bowl → Lentil and Pumpkin Spice Porridge with Berries | ✅ / ✅ / ✅ |

---
## Your example: Greek Yogurt Parfait with Granola & Berries

| Ingredient | Database entry | Grams used | kcal | P | C | F |
|---|---|---|---|---|---|---|
| 200g Greek yogurt 0% | greek yogurt 0% | 200.0 | 118 | 20.0 | 8.0 | 0.8 |
| 50g granola | granola | 50.0 | 236 | 5.0 | 32.0 | 10.0 |
| 120g mixed berries | mixed berries | 120.0 | 52 | 1.2 | 12.0 | 0.4 |
| 30g sliced almonds | almonds | 30.0 | 174 | 6.3 | 6.6 | 15.0 |
| 15ml honey | honey | 21.3 | 65 | 0.1 | 17.5 | 0.0 |
| 1 medium banana 100g | banana | 100.0 | 89 | 1.1 | 23.0 | 0.3 |

Shown on screen after the fix: **734 kcal / 33.7P / 99.1C / 26.5F** (before: 476 / 34P / 45C / 17.5F). 15 ml honey is now 21.3 g (honey is denser than water) and the banana uses the stated 100 g, hence ~734 rather than 731.


---
## balanced
Plan **Elite Balanced Performance Plan** (`c3d05706-4f41-4573-ad1e-4dcccc40a6a1`), generated in 35s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Blueberry Oat Pancakes with Almond Butter | 80g Rolled oats → *rolled oats* (389/17/66/7) = 311 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>130g Banana → *banana* (89/1.1/23/0.3) = 116 kcal<br>18g Whey protein → *whey protein* (400/80/10/3.3) = 72 kcal<br>85g Blueberry → *blueberry* (57/0.7/14/0.3) = 48 kcal<br>9g Almond butter → *almond butter* (614/21/19/56) = 55 kcal<br>17g Honey → *honey* (304/0.3/82/0) = 52 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 749 kcal / 39.6P / 114.2C / 18.3F | 749 kcal / 39.6P / 114.2C / 18.3F | ✅ |
| **lunch** — Grilled Chicken Quinoa Bowl with Roasted Vegetables | 90g Chicken breast → *chicken breast* (165/31/0/3.6) = 148 kcal<br>225g Quinoa → *quinoa* (120/4.4/21/1.9) = 270 kcal<br>190g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 163 kcal<br>110g Broccoli → *broccoli* (34/2.8/7/0.4) = 37 kcal<br>105g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 33 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>23g Feta cheese → *feta cheese* (264/14/4/21) = 61 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal | 777 kcal / 48.7P / 103.2C / 19.2F | 777 kcal / 48.7P / 103.2C / 19.2F | ✅ |
| **dinner** — Seared Salmon with Garlic Herb Brown Rice and Asparagus | 100g Salmon → *salmon* (206/22/0/12.4) = 206 kcal<br>355g Brown rice → *brown rice* (123/2.7/25.6/1) = 437 kcal<br>180g Asparagus → *asparagus* (20/2.2/4/0.1) = 36 kcal<br>120g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 22 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal<br>10g Parsley → *parsley* (36/3/6.3/0.8) = 4 kcal<br>30g Lemon → *lemon* (29/1.1/9.3/0.3) = 9 kcal<br>12g Almonds → *almonds* (579/21/22/50) = 69 kcal | 867 kcal / 40.3P / 111.8C / 30.5F | 867 kcal / 40.3P / 111.8C / 30.5F | ✅ |
| **snack** — Greek Yogurt Parfait with Mixed Berries and Granola | 120g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 88 kcal<br>100g Mixed berries → *mixed berries* (43/1/10/0.3) = 43 kcal<br>30g Granola → *granola* (471/10/64/20) = 141 kcal<br>14g Honey → *honey* (304/0.3/82/0) = 43 kcal<br>4g Chia seeds → *chia seeds* (486/17/42/31) = 19 kcal | 334 kcal / 16.7P / 47.1C / 9.8F | 334 kcal / 16.7P / 47.1C / 9.8F | ✅ |

**Day total on screen:** calo 2727 vs 2759 (-1.2%) / prot 145.3 vs 144 (+0.9%) / carb 376.3 vs 372 (+1.2%) / fats 77.8 vs 77 (+1.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Scrambled Eggs with Avocado Toast and Turkey Bacon | 116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>180g whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 445 kcal<br>45g Avocado → *avocado* (160/2/9/15) = 72 kcal<br>30g Turkey bacon → *turkey bacon* (233/17/1/17) = 70 kcal<br>85g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 15 kcal<br>50g Spinach → *spinach* (23/2.9/3.6/0.4) = 12 kcal<br>1g Black pepper → *black pepper* (251/10.4/64/3.3) = 3 kcal | 797 kcal / 41.4P / 85.1C / 31.2F | 797 kcal / 41.4P / 85.1C / 31.2F | ✅ |
| **lunch** — Lean Beef Stir-Fry with Basmati Rice and Mixed Vegetables | 80g Beef mince 95/5 → *beef mince 95/5* (171/26.5/0/6.9) = 137 kcal<br>400g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 484 kcal<br>140g Broccoli → *broccoli* (34/2.8/7/0.4) = 48 kcal<br>115g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 36 kcal<br>120g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 50 kcal<br>95g Carrot → *carrot* (41/0.9/10/0.2) = 39 kcal<br>21g Soy sauce → *soy sauce* (53/8/5/0) = 11 kcal<br>10g Ginger → *ginger* (80/1.8/18/0.8) = 8 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal<br>3g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 17 kcal | 843 kcal / 47.4P / 142.7C / 10.0F | 843 kcal / 47.4P / 142.7C / 10.0F | ✅ |
| **dinner** — Herb-Crusted Sirloin Steak with Sweet Potato Mash and Green Beans | 130g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 276 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>245g Green beans → *green beans* (31/1.8/7/0.1) = 76 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal<br>2g Butter → *butter* (717/0.9/0.1/81) = 14 kcal<br>12g Garlic → *garlic* (149/6/33/0.5) = 18 kcal<br>3g Rosemary → *rosemary* (131/3.3/20.7/5.9) = 4 kcal<br>2g Thyme → *thyme* (101/5.6/24/1.7) = 2 kcal<br>12g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 52 kcal | 821 kcal / 51.4P / 102.8C / 23.8F | 821 kcal / 51.4P / 102.8C / 23.8F | ✅ |
| **snack** — Apple Slices with Peanut Butter and Dark Chocolate | 230g Apple → *apple* (52/0.3/14/0.2) = 120 kcal<br>14g Peanut butter → *peanut butter* (588/25/20/50) = 82 kcal<br>14g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 84 kcal | 286 kcal / 5.3P / 41.0C / 13.4F | 286 kcal / 5.3P / 41.0C / 13.4F | ✅ |

**Day total on screen:** calo 2747 vs 2759 (-0.4%) / prot 145.5 vs 144 (+1.0%) / carb 371.6 vs 372 (-0.1%) / fats 78.4 vs 77 (+1.8%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Banana Protein Smoothie Bowl with Granola and Berries | 400g Banana → *banana* (89/1.1/23/0.3) = 356 kcal<br>18g Whey protein → *whey protein* (400/80/10/3.3) = 72 kcal<br>75g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 55 kcal<br>20g Rolled oats → *rolled oats* (389/17/66/7) = 78 kcal<br>120g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 20 kcal<br>90g Strawberry → *strawberry* (32/0.7/8/0.3) = 29 kcal<br>25g Granola → *granola* (471/10/64/20) = 118 kcal<br>8g Almond butter → *almond butter* (614/21/19/56) = 49 kcal<br>5g Chia seeds → *chia seeds* (486/17/42/31) = 24 kcal | 801 kcal / 36.1P / 138.4C / 17.3F | 801 kcal / 36.1P / 138.4C / 17.3F | ✅ |
| **lunch** — Mediterranean Chicken Wrap with Hummus and Roasted Vegetables | 85g Chicken breast → *chicken breast* (165/31/0/3.6) = 140 kcal<br>180g whole wheat wraps → *whole wheat wrap* (310/8/52/8) = 558 kcal<br>30g Hummus → *hummus* (166/8/14/10) = 50 kcal<br>75g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 11 kcal<br>70g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 13 kcal<br>40g Red onion → *red onion* (40/1.1/9/0.1) = 16 kcal<br>45g Romaine lettuce → *romaine lettuce* (17/1.2/3.3/0.3) = 8 kcal<br>18g Feta cheese → *feta cheese* (264/14/4/21) = 48 kcal<br>5g Olive oil → *olive oil* (884/0/0/100) = 44 kcal<br>16g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal | 892 kcal / 47.7P / 110.1C / 29.6F | 892 kcal / 47.7P / 110.1C / 29.6F | ✅ |
| **dinner** — Garlic Butter Shrimp with Wild Rice Pilaf and Roasted Brussels Sprouts | 120g Shrimp → *shrimp* (99/24/0.2/0.3) = 119 kcal<br>275g Wild rice → *wild rice* (101/4/21.3/0.3) = 278 kcal<br>100g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 43 kcal<br>9g Butter → *butter* (717/0.9/0.1/81) = 65 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>14g Garlic → *garlic* (149/6/33/0.5) = 21 kcal<br>40g Lemon → *lemon* (29/1.1/9.3/0.3) = 12 kcal<br>13g Parsley → *parsley* (36/3/6.3/0.8) = 5 kcal<br>10g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 43 kcal<br>10g Almonds → *almonds* (579/21/22/50) = 58 kcal | 697 kcal / 50.8P / 79.5C / 23.0F | 697 kcal / 50.8P / 79.5C / 23.0F | ✅ |
| **snack** — Cottage Cheese with Pineapple and Walnuts | 90g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 76 kcal<br>180g Pineapple → *pineapple* (50/0.5/13/0.1) = 90 kcal<br>8g Walnut → *walnut* (654/15/14/65) = 52 kcal<br>22g Honey → *honey* (304/0.3/82/0) = 67 kcal<br>1g Cinnamon → *cinnamon* (247/4/81/1.2) = 2 kcal | 287 kcal / 12.1P / 46.9C / 7.6F | 287 kcal / 12.1P / 46.9C / 7.6F | ✅ |

**Day total on screen:** calo 2677 vs 2759 (-3.0%) / prot 146.7 vs 144 (+1.9%) / carb 374.9 vs 372 (+0.8%) / fats 77.5 vs 77 (+0.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 breakfast: “Protein-Packed Blueberry Oat Pancakes with Almond Butter” → “Scrambled Eggs with Whole Wheat Toast, Smoked Salmon, and Fresh Berries” (3s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Scrambled Eggs with Whole Wheat Toast, Smoked Salmon, and Fresh Berries | 58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>180g whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 445 kcal<br>2g Butter → *butter* (717/0.9/0.1/81) = 14 kcal<br>55g Smoked salmon → *smoked salmon* (117/18.3/0/4.3) = 64 kcal<br>315g Mixed berries → *mixed berries* (43/1/10/0.3) = 135 kcal<br>12g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal | 751 kcal / 38.7P / 106.7C / 17.4F | 751 kcal / 38.7P / 106.7C / 17.4F | ✅ |
| **lunch** — Grilled Chicken Quinoa Bowl with Roasted Vegetables | 90g Chicken breast → *chicken breast* (165/31/0/3.6) = 148 kcal<br>225g Quinoa → *quinoa* (120/4.4/21/1.9) = 270 kcal<br>190g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 163 kcal<br>110g Broccoli → *broccoli* (34/2.8/7/0.4) = 37 kcal<br>105g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 33 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>23g Feta cheese → *feta cheese* (264/14/4/21) = 61 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal | 777 kcal / 48.7P / 103.2C / 19.2F | 777 kcal / 48.7P / 103.2C / 19.2F | ✅ |
| **dinner** — Seared Salmon with Garlic Herb Brown Rice and Asparagus | 100g Salmon → *salmon* (206/22/0/12.4) = 206 kcal<br>355g Brown rice → *brown rice* (123/2.7/25.6/1) = 437 kcal<br>180g Asparagus → *asparagus* (20/2.2/4/0.1) = 36 kcal<br>120g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 22 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal<br>10g Parsley → *parsley* (36/3/6.3/0.8) = 4 kcal<br>30g Lemon → *lemon* (29/1.1/9.3/0.3) = 9 kcal<br>12g Almonds → *almonds* (579/21/22/50) = 69 kcal | 867 kcal / 40.3P / 111.8C / 30.5F | 867 kcal / 40.3P / 111.8C / 30.5F | ✅ |
| **snack** — Greek Yogurt Parfait with Mixed Berries and Granola | 120g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 88 kcal<br>100g Mixed berries → *mixed berries* (43/1/10/0.3) = 43 kcal<br>30g Granola → *granola* (471/10/64/20) = 141 kcal<br>14g Honey → *honey* (304/0.3/82/0) = 43 kcal<br>4g Chia seeds → *chia seeds* (486/17/42/31) = 19 kcal | 334 kcal / 16.7P / 47.1C / 9.8F | 334 kcal / 16.7P / 47.1C / 9.8F | ✅ |

**Day total on screen:** calo 2729 vs 2759 (-1.1%) / prot 144.4 vs 144 (+0.3%) / carb 368.8 vs 372 (-0.9%) / fats 76.9 vs 77 (-0.1%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## high_protein
Plan **Elite High-Protein Performance Plan** (`6b242343-07dd-4121-9284-8a16af267d9e`), generated in 31s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Blueberry Oat Bowl | 75g Rolled oats → *rolled oats* (389/17/66/7) = 292 kcal<br>15g Whey protein → *whey protein* (400/80/10/3.3) = 60 kcal<br>85g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 50 kcal<br>120g Blueberry → *blueberry* (57/0.7/14/0.3) = 68 kcal<br>100g Banana → *banana* (89/1.1/23/0.3) = 89 kcal<br>15g Almond butter → *almond butter* (614/21/19/56) = 92 kcal<br>16g Honey → *honey* (304/0.3/82/0) = 49 kcal | 700 kcal / 38.3P / 110.2C / 15.1F | 700 kcal / 38.3P / 110.2C / 15.1F | ✅ |
| **lunch** — Grilled Chicken & Sweet Potato Power Bowl | 90g Chicken breast → *chicken breast* (165/31/0/3.6) = 148 kcal<br>365g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 314 kcal<br>120g Broccoli → *broccoli* (34/2.8/7/0.4) = 41 kcal<br>21g Olive oil → *olive oil* (884/0/0/100) = 186 kcal<br>55g Avocado → *avocado* (160/2/9/15) = 88 kcal<br>10g Lime juice → *lime juice* (25/0.4/8/0.1) = 2 kcal | 779 kcal / 38.2P / 87.2C / 33.3F | 779 kcal / 38.2P / 87.2C / 33.3F | ✅ |
| **dinner** — Lean Beef Stir-Fry with Jasmine Rice | 100g Beef mince 95/5 → *beef mince 95/5* (171/26.5/0/6.9) = 171 kcal<br>395g White rice → *white rice* (130/2.7/28/0.3) = 514 kcal<br>120g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 37 kcal<br>100g Broccoli → *broccoli* (34/2.8/7/0.4) = 34 kcal<br>95g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 40 kcal<br>19g Soy sauce → *soy sauce* (53/8/5/0) = 10 kcal<br>16g Sesame oil → *sesame oil* (884/0/0/100) = 141 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal | 959 kcal / 45.9P / 135.5C / 25.1F | 959 kcal / 45.9P / 135.5C / 25.1F | ✅ |
| **snack** — Tropical Protein Smoothie | 15g Whey protein → *whey protein* (400/80/10/3.3) = 60 kcal<br>100g Banana → *banana* (89/1.1/23/0.3) = 89 kcal<br>80g Mango → *mango* (60/0.8/15/0.4) = 48 kcal<br>70g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 41 kcal<br>200g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 34 kcal | 272 kcal / 21.9P / 42.1C / 3.6F | 272 kcal / 21.9P / 42.1C / 3.6F | ✅ |

**Day total on screen:** calo 2710 vs 2759 (-1.8%) / prot 144.3 vs 144 (+0.2%) / carb 375 vs 372 (+0.8%) / fats 77.1 vs 77 (+0.1%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Egg White & Turkey Power Scramble | 120g Egg white → *egg white* (52/11/0.7/0.2) = 62 kcal<br>40g Turkey breast → *turkey breast* (135/30/0/1) = 54 kcal<br>180g whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 445 kcal<br>60g Spinach → *spinach* (23/2.9/3.6/0.4) = 14 kcal<br>85g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 15 kcal<br>60g Avocado → *avocado* (160/2/9/15) = 96 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal | 739 kcal / 46.9P / 85.5C / 22.1F | 739 kcal / 46.9P / 85.5C / 22.1F | ✅ |
| **lunch** — Seared Tuna Steak with Quinoa Medley | 55g Tuna steak → *tuna steak* (130/29/0/0.6) = 72 kcal<br>400g Quinoa → *quinoa* (120/4.4/21/1.9) = 480 kcal<br>165g Asparagus → *asparagus* (20/2.2/4/0.1) = 33 kcal<br>110g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 20 kcal<br>85g Mixed greens → *mixed greens* (20/2/3.5/0.3) = 17 kcal<br>14g Olive oil → *olive oil* (884/0/0/100) = 124 kcal<br>16g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal | 750 kcal / 40.0P / 99.0C / 22.6F | 750 kcal / 40.0P / 99.0C / 22.6F | ✅ |
| **dinner** — Herb-Crusted Chicken with Roasted Potatoes | 66g Chicken breast → *chicken breast* (165/31/0/3.6) = 109 kcal<br>400g Potato → *potato* (77/2/17/0.1) = 308 kcal<br>240g Green beans → *green beans* (31/1.8/7/0.1) = 74 kcal<br>17g Olive oil → *olive oil* (884/0/0/100) = 150 kcal<br>14g Garlic → *garlic* (149/6/33/0.5) = 21 kcal<br>2g Rosemary → *rosemary* (131/3.3/20.7/5.9) = 3 kcal<br>2g Thyme → *thyme* (101/5.6/24/1.7) = 2 kcal<br>160g White rice → *white rice* (130/2.7/28/0.3) = 208 kcal | 875 kcal / 38.1P / 135.1C / 20.7F | 875 kcal / 38.1P / 135.1C / 20.7F | ✅ |
| **snack** — Berry Cottage Cheese Bowl | 145g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 122 kcal<br>120g Strawberry → *strawberry* (32/0.7/8/0.3) = 38 kcal<br>70g Raspberries → *raspberries* (52/1.2/12/0.7) = 36 kcal<br>30g Honey → *honey* (304/0.3/82/0) = 91 kcal<br>13g Almonds → *almonds* (579/21/22/50) = 75 kcal | 362 kcal / 20.3P / 51.3C / 11.0F | 362 kcal / 20.3P / 51.3C / 11.0F | ✅ |

**Day total on screen:** calo 2726 vs 2759 (-1.2%) / prot 145.3 vs 144 (+0.9%) / carb 370.9 vs 372 (-0.3%) / fats 76.4 vs 77 (-0.8%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Banana Protein Pancake Stack | 65g Rolled oats → *rolled oats* (389/17/66/7) = 253 kcal<br>15g Whey protein → *whey protein* (400/80/10/3.3) = 60 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>135g Banana → *banana* (89/1.1/23/0.3) = 120 kcal<br>80g Blueberry → *blueberry* (57/0.7/14/0.3) = 46 kcal<br>75g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 44 kcal<br>25g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 65 kcal | 678 kcal / 40.2P / 107.1C / 12.3F | 678 kcal / 40.2P / 107.1C / 12.3F | ✅ |
| **lunch** — Turkey & Brown Rice Buddha Bowl | 90g Turkey breast → *turkey breast* (135/30/0/1) = 122 kcal<br>250g Brown rice → *brown rice* (123/2.7/25.6/1) = 308 kcal<br>65g Kale → *kale* (49/4.3/9/0.9) = 32 kcal<br>155g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 133 kcal<br>70g Chickpeas → *chickpeas* (164/9/27/2.6) = 115 kcal<br>19g Tahini → *tahini* (595/17/23/54) = 113 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal | 826 kcal / 48.7P / 125.3C / 16.3F | 826 kcal / 48.7P / 125.3C / 16.3F | ✅ |
| **dinner** — Grilled Salmon with Basmati & Vegetables | 110g Salmon → *salmon* (206/22/0/12.4) = 227 kcal<br>310g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 375 kcal<br>140g Zucchini → *zucchini* (17/1.2/3.1/0.3) = 24 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>115g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 49 kcal<br>20g Olive oil → *olive oil* (884/0/0/100) = 177 kcal<br>30g Lemon → *lemon* (29/1.1/9.3/0.3) = 9 kcal<br>3g Dill → *dill* (43/3.5/7/1.1) = 1 kcal | 901 kcal / 42.2P / 103.2C / 36.0F | 901 kcal / 42.2P / 103.2C / 36.0F | ✅ |
| **snack** — Apple Almond Protein Bites | 140g Apple → *apple* (52/0.3/14/0.2) = 73 kcal<br>85g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 50 kcal<br>21g Almond butter → *almond butter* (614/21/19/56) = 129 kcal<br>15g Honey → *honey* (304/0.3/82/0) = 46 kcal<br>1g Cinnamon → *cinnamon* (247/4/81/1.2) = 2 kcal | 300 kcal / 13.3P / 40.1C / 12.4F | 300 kcal / 13.3P / 40.1C / 12.4F | ✅ |

**Day total on screen:** calo 2705 vs 2759 (-2.0%) / prot 144.4 vs 144 (+0.3%) / carb 375.7 vs 372 (+1.0%) / fats 77 vs 77 (+0.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 lunch: “Grilled Chicken & Sweet Potato Power Bowl” → “Spiced Chicken & Arborio Risotto with Roasted Vegetables” (4s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Blueberry Oat Bowl | 75g Rolled oats → *rolled oats* (389/17/66/7) = 292 kcal<br>15g Whey protein → *whey protein* (400/80/10/3.3) = 60 kcal<br>85g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 50 kcal<br>120g Blueberry → *blueberry* (57/0.7/14/0.3) = 68 kcal<br>100g Banana → *banana* (89/1.1/23/0.3) = 89 kcal<br>15g Almond butter → *almond butter* (614/21/19/56) = 92 kcal<br>16g Honey → *honey* (304/0.3/82/0) = 49 kcal | 700 kcal / 38.3P / 110.2C / 15.1F | 700 kcal / 38.3P / 110.2C / 15.1F | ✅ |
| **lunch** — Spiced Chicken & Arborio Risotto with Roasted Vegetables | 100g Chicken breast → *chicken breast* (165/31/0/3.6) = 165 kcal<br>255g Arborio rice → *arborio rice* (130/2.4/28.6/0.3) = 332 kcal<br>150g Chicken broth → *chicken broth* (6/0.6/0.4/0.2) = 9 kcal<br>60g Asparagus → *asparagus* (20/2.2/4/0.1) = 12 kcal<br>50g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 16 kcal<br>12g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 52 kcal<br>24g Olive oil → *olive oil* (884/0/0/100) = 212 kcal<br>4g Garlic → *garlic* (149/6/33/0.5) = 6 kcal<br>2g Cumin → *cumin* (375/17.8/44/22) = 8 kcal<br>1g Black pepper → *black pepper* (251/10.4/64/3.3) = 3 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 815 kcal / 45.1P / 82.2C / 32.8F | 815 kcal / 45.1P / 82.2C / 32.8F | ✅ |
| **dinner** — Lean Beef Stir-Fry with Jasmine Rice | 100g Beef mince 95/5 → *beef mince 95/5* (171/26.5/0/6.9) = 171 kcal<br>395g White rice → *white rice* (130/2.7/28/0.3) = 514 kcal<br>120g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 37 kcal<br>100g Broccoli → *broccoli* (34/2.8/7/0.4) = 34 kcal<br>95g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 40 kcal<br>19g Soy sauce → *soy sauce* (53/8/5/0) = 10 kcal<br>16g Sesame oil → *sesame oil* (884/0/0/100) = 141 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal | 959 kcal / 45.9P / 135.5C / 25.1F | 959 kcal / 45.9P / 135.5C / 25.1F | ✅ |
| **snack** — Tropical Protein Smoothie | 15g Whey protein → *whey protein* (400/80/10/3.3) = 60 kcal<br>100g Banana → *banana* (89/1.1/23/0.3) = 89 kcal<br>80g Mango → *mango* (60/0.8/15/0.4) = 48 kcal<br>70g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 41 kcal<br>200g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 34 kcal | 272 kcal / 21.9P / 42.1C / 3.6F | 272 kcal / 21.9P / 42.1C / 3.6F | ✅ |

**Day total on screen:** calo 2746 vs 2759 (-0.5%) / prot 151.2 vs 144 (+5.0%) / carb 370 vs 372 (-0.5%) / fats 76.6 vs 77 (-0.5%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## vegetarian
Plan **Elite Vegetarian Performance Plan** (`ce91f0f2-f127-41b0-8435-f82ba933d5b8`), generated in 35s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Oat Bowl | 85g Rolled oats → *rolled oats* (389/17/66/7) = 331 kcal<br>190g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 112 kcal<br>23g Whey protein → *whey protein* (400/80/10/3.3) = 92 kcal<br>100g Blueberry → *blueberry* (57/0.7/14/0.3) = 57 kcal<br>110g Banana → *banana* (89/1.1/23/0.3) = 98 kcal<br>9g Almond butter → *almond butter* (614/21/19/56) = 55 kcal<br>7g Chia seeds → *chia seeds* (486/17/42/31) = 34 kcal<br>10g Honey → *honey* (304/0.3/82/0) = 30 kcal | 809 kcal / 56.8P / 118.1C / 15.4F | 809 kcal / 56.8P / 118.1C / 15.4F | ✅ |
| **lunch** — Mediterranean Chickpea Quinoa Bowl | 250g Quinoa → *quinoa* (120/4.4/21/1.9) = 300 kcal<br>135g Chickpeas → *chickpeas* (164/9/27/2.6) = 221 kcal<br>35g Feta cheese → *feta cheese* (264/14/4/21) = 92 kcal<br>95g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 14 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>40g Red onion → *red onion* (40/1.1/9/0.1) = 16 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>14g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>9g Parsley → *parsley* (36/3/6.3/0.8) = 3 kcal | 762 kcal / 31.3P / 107.5C / 24.2F | 762 kcal / 31.3P / 107.5C / 24.2F | ✅ |
| **dinner** — Tempeh Stir-Fry with Brown Rice | 100g Tempeh → *tempeh* (192/20/8/11) = 192 kcal<br>255g Brown rice → *brown rice* (123/2.7/25.6/1) = 314 kcal<br>110g Broccoli → *broccoli* (34/2.8/7/0.4) = 37 kcal<br>120g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 37 kcal<br>95g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 40 kcal<br>75g Carrot → *carrot* (41/0.9/10/0.2) = 31 kcal<br>15g Cashews → *cashews* (553/18/30/44) = 83 kcal<br>4g Sesame oil → *sesame oil* (884/0/0/100) = 35 kcal<br>20g Soy sauce → *soy sauce* (53/8/5/0) = 11 kcal<br>10g Ginger → *ginger* (80/1.8/18/0.8) = 8 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal | 798 kcal / 39.5P / 112.5C / 25.4F | 798 kcal / 39.5P / 112.5C / 25.4F | ✅ |
| **snack** — Greek Yogurt Protein Parfait | 115g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 84 kcal<br>30g Granola → *granola* (471/10/64/20) = 141 kcal<br>90g Strawberry → *strawberry* (32/0.7/8/0.3) = 29 kcal<br>9g Almonds → *almonds* (579/21/22/50) = 52 kcal<br>7g Honey → *honey* (304/0.3/82/0) = 21 kcal | 327 kcal / 17.0P / 38.6C / 13.0F | 327 kcal / 17.0P / 38.6C / 13.0F | ✅ |

**Day total on screen:** calo 2696 vs 2759 (-2.3%) / prot 144.6 vs 144 (+0.4%) / carb 376.7 vs 372 (+1.3%) / fats 78 vs 77 (+1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Veggie-Loaded Scrambled Eggs with Toast | 116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>150g whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 370 kcal<br>75g Spinach → *spinach* (23/2.9/3.6/0.4) = 17 kcal<br>75g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 16 kcal<br>80g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 14 kcal<br>19g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 77 kcal<br>40g Avocado → *avocado* (160/2/9/15) = 64 kcal | 738 kcal / 40.9P / 74.9C / 30.9F | 738 kcal / 40.9P / 74.9C / 30.9F | ✅ |
| **lunch** — Lentil Sweet Potato Buddha Bowl | 220g Lentils → *lentils* (116/9/20/0.4) = 255 kcal<br>375g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 322 kcal<br>70g Kale → *kale* (49/4.3/9/0.9) = 34 kcal<br>120g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 101 kcal<br>105g Beets → *beets* (43/1.6/10/0.2) = 45 kcal<br>13g Pumpkin seeds → *pumpkin seeds* (559/30/11/49) = 73 kcal<br>13g Tahini → *tahini* (595/17/23/54) = 77 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal | 910 kcal / 49.9P / 146.1C / 18.5F | 910 kcal / 49.9P / 146.1C / 18.5F | ✅ |
| **dinner** — Tofu Paneer Tikka with Basmati Rice | 66g Extra firm tofu → *extra firm tofu* (144/17/3/8) = 95 kcal<br>40g Paneer → *paneer* (296/19/6/22) = 118 kcal<br>355g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 430 kcal<br>80g Full fat greek yogurt → *full fat greek yogurt* (97/9/4/5) = 78 kcal<br>130g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 40 kcal<br>110g Red onion → *red onion* (40/1.1/9/0.1) = 44 kcal<br>5g Curry powder → *curry powder* (325/14.3/56/14) = 16 kcal<br>11g Garlic → *garlic* (149/6/33/0.5) = 16 kcal<br>9g Ginger → *ginger* (80/1.8/18/0.8) = 7 kcal<br>10g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 2 kcal | 846 kcal / 42.7P / 123.2C / 21.0F | 846 kcal / 42.7P / 123.2C / 21.0F | ✅ |
| **snack** — Apple Almond Energy Bites | 170g Apple → *apple* (52/0.3/14/0.2) = 88 kcal<br>9g Almond butter → *almond butter* (614/21/19/56) = 55 kcal<br>85g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 71 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 219 kcal / 11.8P / 30.5C / 7.4F | 219 kcal / 11.8P / 30.5C / 7.4F | ✅ |

**Day total on screen:** calo 2713 vs 2759 (-1.7%) / prot 145.3 vs 144 (+0.9%) / carb 374.7 vs 372 (+0.7%) / fats 77.8 vs 77 (+1.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein Pancakes with Berry Compote | 58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>60g Rolled oats → *rolled oats* (389/17/66/7) = 233 kcal<br>85g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 71 kcal<br>12g Whey protein → *whey protein* (400/80/10/3.3) = 48 kcal<br>95g Banana → *banana* (89/1.1/23/0.3) = 85 kcal<br>115g Mixed berries → *mixed berries* (43/1/10/0.3) = 49 kcal<br>30g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 78 kcal<br>5g Coconut oil → *coconut oil* (862/0/0/100) = 43 kcal | 697 kcal / 38.7P / 98.2C / 18.7F | 697 kcal / 38.7P / 98.2C / 18.7F | ✅ |
| **lunch** — Black Bean Burrito Bowl | 140g Black beans → *black beans* (132/9/24/0.5) = 185 kcal<br>240g Brown rice → *brown rice* (123/2.7/25.6/1) = 295 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>55g Avocado → *avocado* (160/2/9/15) = 88 kcal<br>80g Sweet corn → *sweet corn* (86/3.2/19/1.2) = 69 kcal<br>75g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 14 kcal<br>30g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 121 kcal<br>55g Salsa → *salsa* (36/2/8/0.2) = 20 kcal<br>9g Lime juice → *lime juice* (25/0.4/8/0.1) = 2 kcal<br>9g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 2 kcal | 886 kcal / 39.8P / 124.5C / 28.9F | 886 kcal / 39.8P / 124.5C / 28.9F | ✅ |
| **dinner** — Seitan Mushroom Stroganoff with Farro | 90g Seitan → *seitan* (166/25/14/2) = 149 kcal<br>210g Farro → *farro* (170/7/34/1.5) = 357 kcal<br>125g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 28 kcal<br>95g Full fat greek yogurt → *full fat greek yogurt* (97/9/4/5) = 92 kcal<br>105g Onion → *onion* (40/1.1/9/0.1) = 42 kcal<br>10g Garlic → *garlic* (149/6/33/0.5) = 15 kcal<br>100g Vegetable broth → *vegetable broth* (6/0.2/1/0.2) = 6 kcal<br>14g Dijon mustard → *dijon mustard* (66/4/5/4) = 9 kcal<br>15g Olive oil → *olive oil* (884/0/0/100) = 133 kcal<br>14g Parsley → *parsley* (36/3/6.3/0.8) = 5 kcal<br>2g Black pepper → *black pepper* (251/10.4/64/3.3) = 5 kcal | 841 kcal / 52.8P / 108.6C / 26.4F | 841 kcal / 52.8P / 108.6C / 26.4F | ✅ |
| **snack** — Tropical Protein Smoothie | 85g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 50 kcal<br>115g Mango → *mango* (60/0.8/15/0.4) = 69 kcal<br>80g Pineapple → *pineapple* (50/0.5/13/0.1) = 40 kcal<br>60g Banana → *banana* (89/1.1/23/0.3) = 53 kcal<br>8g Hemp seed → *hemp seed* (553/32/9/49) = 44 kcal<br>100g Coconut water → *coconut water* (19/0.7/3.7/0.2) = 19 kcal | 275 kcal / 13.8P / 49.2C / 5.2F | 275 kcal / 13.8P / 49.2C / 5.2F | ✅ |

**Day total on screen:** calo 2699 vs 2759 (-2.2%) / prot 145.1 vs 144 (+0.8%) / carb 380.5 vs 372 (+2.3%) / fats 79.2 vs 77 (+2.9%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 dinner: “Tempeh Stir-Fry with Brown Rice” → “Chickpea Curry with Basmati Rice” (3s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Oat Bowl | 85g Rolled oats → *rolled oats* (389/17/66/7) = 331 kcal<br>190g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 112 kcal<br>23g Whey protein → *whey protein* (400/80/10/3.3) = 92 kcal<br>100g Blueberry → *blueberry* (57/0.7/14/0.3) = 57 kcal<br>110g Banana → *banana* (89/1.1/23/0.3) = 98 kcal<br>9g Almond butter → *almond butter* (614/21/19/56) = 55 kcal<br>7g Chia seeds → *chia seeds* (486/17/42/31) = 34 kcal<br>10g Honey → *honey* (304/0.3/82/0) = 30 kcal | 809 kcal / 56.8P / 118.1C / 15.4F | 809 kcal / 56.8P / 118.1C / 15.4F | ✅ |
| **lunch** — Mediterranean Chickpea Quinoa Bowl | 250g Quinoa → *quinoa* (120/4.4/21/1.9) = 300 kcal<br>135g Chickpeas → *chickpeas* (164/9/27/2.6) = 221 kcal<br>35g Feta cheese → *feta cheese* (264/14/4/21) = 92 kcal<br>95g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 14 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>40g Red onion → *red onion* (40/1.1/9/0.1) = 16 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>14g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>9g Parsley → *parsley* (36/3/6.3/0.8) = 3 kcal | 762 kcal / 31.3P / 107.5C / 24.2F | 762 kcal / 31.3P / 107.5C / 24.2F | ✅ |
| **dinner** — Chickpea Curry with Basmati Rice | 330g Chickpeas → *chickpeas* (164/9/27/2.6) = 541 kcal<br>45g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 54 kcal<br>50g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 115 kcal<br>45g Onion → *onion* (40/1.1/9/0.1) = 18 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal<br>5g Ginger → *ginger* (80/1.8/18/0.8) = 4 kcal<br>80g Spinach → *spinach* (23/2.9/3.6/0.4) = 18 kcal<br>18g Tomato paste → *tomato paste* (82/4.3/18.9/0.5) = 15 kcal<br>3g Olive oil → *olive oil* (884/0/0/100) = 27 kcal<br>95g Vegetable broth → *vegetable broth* (6/0.2/1/0.2) = 6 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 811 kcal / 36.8P / 118.3C / 24.3F | 811 kcal / 36.8P / 118.3C / 24.3F | ✅ |
| **snack** — Greek Yogurt Protein Parfait | 115g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 84 kcal<br>30g Granola → *granola* (471/10/64/20) = 141 kcal<br>90g Strawberry → *strawberry* (32/0.7/8/0.3) = 29 kcal<br>9g Almonds → *almonds* (579/21/22/50) = 52 kcal<br>7g Honey → *honey* (304/0.3/82/0) = 21 kcal | 327 kcal / 17.0P / 38.6C / 13.0F | 327 kcal / 17.0P / 38.6C / 13.0F | ✅ |

**Day total on screen:** calo 2709 vs 2759 (-1.8%) / prot 141.9 vs 144 (-1.5%) / carb 382.5 vs 372 (+2.8%) / fats 76.9 vs 77 (-0.1%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## vegan
Plan **Elite Vegan Performance Plan** (`d57b115f-b895-46ce-bb16-f63ef5027328`), generated in 39s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Oat Bowl | 75g Rolled oats → *rolled oats* (389/17/66/7) = 292 kcal<br>23g Pea protein powder → *pea protein powder* (380/72/8/5) = 87 kcal<br>12g Almond butter → *almond butter* (614/21/19/56) = 74 kcal<br>110g Banana → *banana* (89/1.1/23/0.3) = 98 kcal<br>80g Blueberry → *blueberry* (57/0.7/14/0.3) = 46 kcal<br>235g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 40 kcal<br>9g Chia seeds → *chia seeds* (486/17/42/31) = 44 kcal<br>16g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 42 kcal | 723 kcal / 36.6P / 107.9C / 19.0F | 723 kcal / 36.6P / 107.9C / 19.0F | ✅ |
| **lunch** — Tempeh Buddha Bowl with Tahini Dressing | 90g Tempeh → *tempeh* (192/20/8/11) = 173 kcal<br>215g Quinoa → *quinoa* (120/4.4/21/1.9) = 258 kcal<br>165g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 142 kcal<br>50g Kale → *kale* (49/4.3/9/0.9) = 24 kcal<br>75g Chickpeas → *chickpeas* (164/9/27/2.6) = 123 kcal<br>13g Tahini → *tahini* (595/17/23/54) = 77 kcal<br>14g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal<br>4g Garlic → *garlic* (149/6/33/0.5) = 6 kcal | 841 kcal / 41.5P / 115.3C / 27.7F | 841 kcal / 41.5P / 115.3C / 27.7F | ✅ |
| **dinner** — Seitan Stir-Fry with Brown Rice | 100g Seitan → *seitan* (166/25/14/2) = 166 kcal<br>275g Brown rice → *brown rice* (123/2.7/25.6/1) = 338 kcal<br>105g Broccoli → *broccoli* (34/2.8/7/0.4) = 36 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>75g Shelled edamame → *shelled edamame* (121/11/8/5) = 91 kcal<br>16g Cashews → *cashews* (553/18/30/44) = 88 kcal<br>5g Sesame oil → *sesame oil* (884/0/0/100) = 44 kcal<br>20g Soy sauce → *soy sauce* (53/8/5/0) = 11 kcal<br>10g Ginger → *ginger* (80/1.8/18/0.8) = 8 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal | 831 kcal / 49.8P / 115.2C / 21.5F | 831 kcal / 49.8P / 115.2C / 21.5F | ✅ |
| **snack** — Chocolate Peanut Butter Protein Smoothie | 15g Pea protein powder → *pea protein powder* (380/72/8/5) = 57 kcal<br>8g Peanut butter → *peanut butter* (588/25/20/50) = 47 kcal<br>80g Banana → *banana* (89/1.1/23/0.3) = 71 kcal<br>4g Cocoa powder → *cocoa powder* (228/20/28/14) = 9 kcal<br>215g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 37 kcal<br>18g Dates → *dates* (282/2.5/75/0.4) = 51 kcal<br>4g Flax seeds → *flax seeds* (534/18/29/42) = 21 kcal | 293 kcal / 16.9P / 40.0C / 9.8F | 293 kcal / 16.9P / 40.0C / 9.8F | ✅ |

**Day total on screen:** calo 2688 vs 2759 (-2.6%) / prot 144.8 vs 144 (+0.6%) / carb 378.4 vs 372 (+1.7%) / fats 78 vs 77 (+1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Tofu Scramble Power Plate | 190g Extra firm tofu → *extra firm tofu* (144/17/3/8) = 274 kcal<br>60g whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 148 kcal<br>35g Avocado → *avocado* (160/2/9/15) = 56 kcal<br>50g Spinach → *spinach* (23/2.9/3.6/0.4) = 12 kcal<br>90g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 16 kcal<br>9g Nutritional yeast → *nutritional yeast* (355/50/35/7) = 32 kcal<br>2g Olive oil → *olive oil* (884/0/0/100) = 18 kcal<br>2g Turmeric → *turmeric* (312/9.7/67/3.3) = 6 kcal<br>80g Black beans → *black beans* (132/9/24/0.5) = 106 kcal | 668 kcal / 53.1P / 62.3C / 25.9F | 668 kcal / 53.1P / 62.3C / 25.9F | ✅ |
| **lunch** — Lentil & Sweet Potato Curry | 205g Lentils → *lentils* (116/9/20/0.4) = 238 kcal<br>165g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 142 kcal<br>195g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 236 kcal<br>35g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 80 kcal<br>50g Spinach → *spinach* (23/2.9/3.6/0.4) = 12 kcal<br>70g Chickpeas → *chickpeas* (164/9/27/2.6) = 115 kcal<br>60g Onion → *onion* (40/1.1/9/0.1) = 24 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal<br>6g Ginger → *ginger* (80/1.8/18/0.8) = 5 kcal | 864 kcal / 37.6P / 154.8C / 12.2F | 864 kcal / 37.6P / 154.8C / 12.2F | ✅ |
| **dinner** — BBQ Tempeh with Quinoa & Roasted Vegetables | 95g Tempeh → *tempeh* (192/20/8/11) = 182 kcal<br>230g Quinoa → *quinoa* (120/4.4/21/1.9) = 276 kcal<br>110g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 47 kcal<br>135g Butternut squash → *butternut squash* (45/1/11.7/0.1) = 61 kcal<br>105g Black beans → *black beans* (132/9/24/0.5) = 139 kcal<br>40g Bbq sauce → *bbq sauce* (172/0.8/41/0.6) = 69 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal<br>9g Pumpkin seeds → *pumpkin seeds* (559/30/11/49) = 50 kcal | 859 kcal / 46.7P / 124.2C / 24.3F | 859 kcal / 46.7P / 124.2C / 24.3F | ✅ |
| **snack** — Apple Almond Energy Bites | 90g Apple → *apple* (52/0.3/14/0.2) = 47 kcal<br>12g Almond butter → *almond butter* (614/21/19/56) = 74 kcal<br>12g Almonds → *almonds* (579/21/22/50) = 69 kcal<br>23g Dates → *dates* (282/2.5/75/0.4) = 65 kcal<br>4g Hemp seed → *hemp seed* (553/32/9/49) = 22 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 282 kcal / 7.3P / 36.7C / 15.0F | 282 kcal / 7.3P / 36.7C / 15.0F | ✅ |

**Day total on screen:** calo 2673 vs 2759 (-3.1%) / prot 144.7 vs 144 (+0.5%) / carb 378 vs 372 (+1.6%) / fats 77.4 vs 77 (+0.5%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein Pancakes with Mixed Berries | 30g Pea protein powder → *pea protein powder* (380/72/8/5) = 114 kcal<br>30g Oat flour → *oats* (389/17/66/7) = 117 kcal<br>130g Banana → *banana* (89/1.1/23/0.3) = 116 kcal<br>75g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 13 kcal<br>125g Mixed berries → *mixed berries* (43/1/10/0.3) = 54 kcal<br>10g Almond butter → *almond butter* (614/21/19/56) = 61 kcal<br>40g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 104 kcal<br>5g Flax seeds → *flax seeds* (534/18/29/42) = 27 kcal<br>4g Coconut oil → *coconut oil* (862/0/0/100) = 34 kcal | 640 kcal / 32.7P / 95.8C / 16.9F | 640 kcal / 32.7P / 95.8C / 16.9F | ✅ |
| **lunch** — Mediterranean Chickpea & Farro Bowl | 100g Chickpeas → *chickpeas* (164/9/27/2.6) = 164 kcal<br>170g Farro → *farro* (170/7/34/1.5) = 289 kcal<br>50g Extra firm tofu → *extra firm tofu* (144/17/3/8) = 72 kcal<br>105g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 16 kcal<br>105g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 19 kcal<br>45g Red onion → *red onion* (40/1.1/9/0.1) = 18 kcal<br>30g Hummus → *hummus* (166/8/14/10) = 50 kcal<br>8g Tahini → *tahini* (595/17/23/54) = 48 kcal<br>19g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>5g Parsley → *parsley* (36/3/6.3/0.8) = 2 kcal | 735 kcal / 35.6P / 105.8C / 22.7F | 735 kcal / 35.6P / 105.8C / 22.7F | ✅ |
| **dinner** — Asian-Style Edamame & Tofu Noodle Bowl | 100g Extra firm tofu → *extra firm tofu* (144/17/3/8) = 144 kcal<br>400g Soba noodles → *soba noodles* (99/5/21/0.1) = 396 kcal<br>75g Shelled edamame → *shelled edamame* (121/11/8/5) = 91 kcal<br>105g Bok choy → *bok choy* (13/1.5/2/0.2) = 14 kcal<br>80g Carrot → *carrot* (41/0.9/10/0.2) = 33 kcal<br>105g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 33 kcal<br>10g Peanut butter → *peanut butter* (588/25/20/50) = 59 kcal<br>45g Soy sauce → *soy sauce* (53/8/5/0) = 24 kcal<br>6g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 34 kcal<br>12g Ginger → *ginger* (80/1.8/18/0.8) = 10 kcal<br>12g Garlic → *garlic* (149/6/33/0.5) = 18 kcal<br>4g Sesame oil → *sesame oil* (884/0/0/100) = 35 kcal | 891 kcal / 56.7P / 121.2C / 25.1F | 891 kcal / 56.7P / 121.2C / 25.1F | ✅ |
| **snack** — Trail Mix & Protein Boost | 19g Pea protein powder → *pea protein powder* (380/72/8/5) = 72 kcal<br>10g Walnuts → *walnuts* (654/15/14/65) = 65 kcal<br>30g Dried cranberries → *dried cranberries* (308/0.1/82/1.1) = 92 kcal<br>8g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 48 kcal<br>8g Pumpkin seeds → *pumpkin seeds* (559/30/11/49) = 45 kcal<br>95g Banana → *banana* (89/1.1/23/0.3) = 85 kcal<br>55g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 9 kcal | 416 kcal / 19.5P / 54.4C / 15.9F | 416 kcal / 19.5P / 54.4C / 15.9F | ✅ |

**Day total on screen:** calo 2682 vs 2759 (-2.8%) / prot 144.5 vs 144 (+0.3%) / carb 377.2 vs 372 (+1.4%) / fats 80.6 vs 77 (+4.7%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 snack: “Chocolate Peanut Butter Protein Smoothie” → “Peanut Butter Banana Protein Bites” (2s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Oat Bowl | 75g Rolled oats → *rolled oats* (389/17/66/7) = 292 kcal<br>23g Pea protein powder → *pea protein powder* (380/72/8/5) = 87 kcal<br>12g Almond butter → *almond butter* (614/21/19/56) = 74 kcal<br>110g Banana → *banana* (89/1.1/23/0.3) = 98 kcal<br>80g Blueberry → *blueberry* (57/0.7/14/0.3) = 46 kcal<br>235g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 40 kcal<br>9g Chia seeds → *chia seeds* (486/17/42/31) = 44 kcal<br>16g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 42 kcal | 723 kcal / 36.6P / 107.9C / 19.0F | 723 kcal / 36.6P / 107.9C / 19.0F | ✅ |
| **lunch** — Tempeh Buddha Bowl with Tahini Dressing | 90g Tempeh → *tempeh* (192/20/8/11) = 173 kcal<br>215g Quinoa → *quinoa* (120/4.4/21/1.9) = 258 kcal<br>165g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 142 kcal<br>50g Kale → *kale* (49/4.3/9/0.9) = 24 kcal<br>75g Chickpeas → *chickpeas* (164/9/27/2.6) = 123 kcal<br>13g Tahini → *tahini* (595/17/23/54) = 77 kcal<br>14g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal<br>4g Garlic → *garlic* (149/6/33/0.5) = 6 kcal | 841 kcal / 41.5P / 115.3C / 27.7F | 841 kcal / 41.5P / 115.3C / 27.7F | ✅ |
| **dinner** — Seitan Stir-Fry with Brown Rice | 100g Seitan → *seitan* (166/25/14/2) = 166 kcal<br>275g Brown rice → *brown rice* (123/2.7/25.6/1) = 338 kcal<br>105g Broccoli → *broccoli* (34/2.8/7/0.4) = 36 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>75g Shelled edamame → *shelled edamame* (121/11/8/5) = 91 kcal<br>16g Cashews → *cashews* (553/18/30/44) = 88 kcal<br>5g Sesame oil → *sesame oil* (884/0/0/100) = 44 kcal<br>20g Soy sauce → *soy sauce* (53/8/5/0) = 11 kcal<br>10g Ginger → *ginger* (80/1.8/18/0.8) = 8 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal | 831 kcal / 49.8P / 115.2C / 21.5F | 831 kcal / 49.8P / 115.2C / 21.5F | ✅ |
| **snack** — Peanut Butter Banana Protein Bites | 16g Peanut butter → *peanut butter* (588/25/20/50) = 94 kcal<br>90g Banana → *banana* (89/1.1/23/0.3) = 80 kcal<br>20g Rolled oats → *rolled oats* (389/17/66/7) = 78 kcal<br>11g Pea protein powder → *pea protein powder* (380/72/8/5) = 42 kcal | 294 kcal / 16.3P / 38.0C / 10.3F | 294 kcal / 16.3P / 38.0C / 10.3F | ✅ |

**Day total on screen:** calo 2689 vs 2759 (-2.5%) / prot 144.2 vs 144 (+0.1%) / carb 376.4 vs 372 (+1.2%) / fats 78.5 vs 77 (+1.9%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## paleo
Plan **Elite Paleo Performance Plan** (`fd5ecf8c-cfd7-4b4b-a1ac-fe0014a1dbfb`), generated in 37s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Sweet Potato Hash with Poached Eggs & Avocado | 400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>30g Avocado → *avocado* (160/2/9/15) = 48 kcal<br>50g Chicken sausage → *chicken* (165/31/0/3.6) = 82 kcal<br>85g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 26 kcal<br>50g Onion → *onion* (40/1.1/9/0.1) = 20 kcal<br>2g Paprika → *paprika* (282/14/54/13) = 6 kcal | 706 kcal / 39.3P / 94.7C / 20.2F | 706 kcal / 39.3P / 94.7C / 20.2F | ✅ |
| **lunch** — Grilled Chicken & Roasted Butternut Squash Bowl | 150g Chicken breast → *chicken breast* (165/31/0/3.6) = 248 kcal<br>400g Butternut squash → *butternut squash* (45/1/11.7/0.1) = 180 kcal<br>85g Kale → *kale* (49/4.3/9/0.9) = 42 kcal<br>200g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 172 kcal<br>13g Almonds → *almonds* (579/21/22/50) = 75 kcal<br>3g Olive oil → *olive oil* (884/0/0/100) = 27 kcal<br>17g Balsamic vinegar → *balsamic vinegar* (88/0.5/17/0) = 15 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal | 768 kcal / 60.6P / 102.2C / 16.3F | 768 kcal / 60.6P / 102.2C / 16.3F | ✅ |
| **dinner** — Pan-Seared Salmon with Herb Sweet Potato Mash | 115g Salmon → *salmon* (206/22/0/12.4) = 237 kcal<br>500g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 430 kcal<br>175g Asparagus → *asparagus* (20/2.2/4/0.1) = 35 kcal<br>7g Ghee → *ghee* (876/0/0/97) = 61 kcal<br>30g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 69 kcal<br>30g Lemon → *lemon* (29/1.1/9.3/0.3) = 9 kcal<br>3g Dill → *dill* (43/3.5/7/1.1) = 1 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal | 855 kcal / 38.8P / 114.6C / 29.0F | 855 kcal / 38.8P / 114.6C / 29.0F | ✅ |
| **snack** — Tropical Energy Smoothie | 125g Banana → *banana* (89/1.1/23/0.3) = 111 kcal<br>100g Mango → *mango* (60/0.8/15/0.4) = 60 kcal<br>30g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 69 kcal<br>4g Almond butter → *almond butter* (614/21/19/56) = 25 kcal<br>21g Dates → *dates* (282/2.5/75/0.4) = 59 kcal<br>5g Chia seeds → *chia seeds* (486/17/42/31) = 24 kcal<br>30g Spinach → *spinach* (23/2.9/3.6/0.4) = 7 kcal | 355 kcal / 6.0P / 65.2C / 11.9F | 355 kcal / 6.0P / 65.2C / 11.9F | ✅ |

**Day total on screen:** calo 2684 vs 2759 (-2.7%) / prot 144.7 vs 144 (+0.5%) / carb 376.7 vs 372 (+1.3%) / fats 77.4 vs 77 (+0.5%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Beef & Veggie Breakfast Skillet with Plantain | 85g Beef mince 90/10 → *beef mince 90/10* (217/26.6/0/11.7) = 184 kcal<br>290g Plantain → *plantain* (116/0.8/31/0.2) = 336 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>110g Bell pepper → *bell pepper* (31/1/6/0.3) = 34 kcal<br>70g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 15 kcal<br>55g Spinach → *spinach* (23/2.9/3.6/0.4) = 13 kcal<br>5g Coconut oil → *coconut oil* (862/0/0/100) = 43 kcal<br>2g Cumin → *cumin* (375/17.8/44/22) = 8 kcal<br>5g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 1 kcal | 724 kcal / 37.8P / 102.5C / 23.0F | 724 kcal / 37.8P / 102.5C / 23.0F | ✅ |
| **lunch** — Sirloin Steak with Sweet Potato Wedges & Chimichurri | 115g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 244 kcal<br>450g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 387 kcal<br>130g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 56 kcal<br>9g Olive oil → *olive oil* (884/0/0/100) = 80 kcal<br>15g Parsley → *parsley* (36/3/6.3/0.8) = 5 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal<br>12g Red wine vinegar → *red wine vinegar* (19/0/0.3/0) = 2 kcal<br>1g Red pepper flakes → *red pepper flakes* (318/12/57/17) = 3 kcal | 790 kcal / 43.6P / 106.2C / 22.4F | 790 kcal / 43.6P / 106.2C / 22.4F | ✅ |
| **dinner** — Herb-Crusted Halibut with Cauliflower Mash | 180g Halibut → *halibut* (111/22.5/0/1.6) = 200 kcal<br>320g Cauliflower rice → *cauliflower rice* (25/1.9/5/0.3) = 80 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>180g Green beans → *green beans* (31/1.8/7/0.1) = 56 kcal<br>15g Ghee → *ghee* (876/0/0/97) = 131 kcal<br>10g Almond flour → *almond flour* (571/21/20/50) = 57 kcal<br>35g Lemon → *lemon* (29/1.1/9.3/0.3) = 10 kcal<br>2g Thyme → *thyme* (101/5.6/24/1.7) = 2 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal | 890 kcal / 59.2P / 116.7C / 24.1F | 890 kcal / 59.2P / 116.7C / 24.1F | ✅ |
| **snack** — Apple Slices with Almond Butter & Berries | 170g Apple → *apple* (52/0.3/14/0.2) = 88 kcal<br>14g Almond butter → *almond butter* (614/21/19/56) = 86 kcal<br>90g Blueberry → *blueberry* (57/0.7/14/0.3) = 51 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal<br>14g Honey → *honey* (304/0.3/82/0) = 43 kcal | 273 kcal / 4.1P / 52.2C / 8.4F | 273 kcal / 4.1P / 52.2C / 8.4F | ✅ |

**Day total on screen:** calo 2677 vs 2759 (-3.0%) / prot 144.7 vs 144 (+0.5%) / carb 377.6 vs 372 (+1.5%) / fats 77.9 vs 77 (+1.2%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Turkey & Sweet Potato Breakfast Bowl | 55g Turkey mince → *turkey mince* (203/27/0/11.5) = 112 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>70g Kale → *kale* (49/4.3/9/0.9) = 34 kcal<br>30g Avocado → *avocado* (160/2/9/15) = 48 kcal<br>4g Coconut oil → *coconut oil* (862/0/0/100) = 34 kcal<br>2g Smoked paprika → *smoked paprika* (282/14/54/13) = 6 kcal<br>2g Garlic powder → *garlic powder* (331/16.6/73/0.7) = 7 kcal | 675 kcal / 33.0P / 92.2C / 22.5F | 675 kcal / 33.0P / 92.2C / 22.5F | ✅ |
| **lunch** — Grilled Tuna Steak with Rainbow Vegetable Medley | 155g Tuna steak → *tuna steak* (130/29/0/0.6) = 202 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>140g Zucchini → *zucchini* (17/1.2/3.1/0.3) = 24 kcal<br>125g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 22 kcal<br>150g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 46 kcal<br>7g Olive oil → *olive oil* (884/0/0/100) = 62 kcal<br>22g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 5 kcal<br>5g Basil → *basil* (23/3.2/2.7/0.6) = 1 kcal<br>9g Capers → *capers* (23/2.4/4.9/0.9) = 2 kcal | 708 kcal / 56.2P / 100.2C / 9.4F | 708 kcal / 56.2P / 100.2C / 9.4F | ✅ |
| **dinner** — Bison Meatballs with Sweet Potato Noodles | 110g Ground bison → *ground bison* (179/25.5/0/8.6) = 197 kcal<br>450g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 387 kcal<br>170g Marinara sauce → *marinara sauce* (50/1.5/8/1.5) = 85 kcal<br>245g Zucchini noodles → *zucchini noodles* (17/1.2/3.1/0.3) = 42 kcal<br>10g Almond flour → *almond flour* (571/21/20/50) = 57 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>21g Garlic → *garlic* (149/6/33/0.5) = 31 kcal<br>4g Basil → *basil* (23/3.2/2.7/0.6) = 1 kcal | 943 kcal / 51.7P / 120.8C / 30.7F | 943 kcal / 51.7P / 120.8C / 30.7F | ✅ |
| **snack** — Mixed Berry & Coconut Parfait | 75g Coconut yogurt → *coconut yogurt* (100/0.7/6/9) = 75 kcal<br>230g Mixed berries → *mixed berries* (43/1/10/0.3) = 99 kcal<br>8g Pecans → *pecans* (691/9/14/72) = 55 kcal<br>5g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 33 kcal<br>33g Honey → *honey* (304/0.3/82/0) = 100 kcal<br>1g Cinnamon → *cinnamon* (247/4/81/1.2) = 2 kcal | 364 kcal / 3.9P / 57.7C / 16.5F | 364 kcal / 3.9P / 57.7C / 16.5F | ✅ |

**Day total on screen:** calo 2690 vs 2759 (-2.5%) / prot 144.8 vs 144 (+0.6%) / carb 370.9 vs 372 (-0.3%) / fats 79.1 vs 77 (+2.7%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 breakfast: “Sweet Potato Hash with Poached Eggs & Avocado” → “Spiced Duck Scramble with Roasted Root Vegetables” (4s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Spiced Duck Scramble with Roasted Root Vegetables | 100g Duck breast → *duck breast* (201/23.5/0/11.2) = 201 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>115g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 36 kcal<br>2g Ghee → *ghee* (876/0/0/97) = 18 kcal<br>2g Cumin → *cumin* (375/17.8/44/22) = 8 kcal<br>1g Black pepper → *black pepper* (251/10.4/64/3.3) = 3 kcal<br>1g Sea salt → *sea salt* (0/0/0/0) = 0 kcal<br>11g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 3 kcal | 703 kcal / 39.2P / 89.4C / 20.7F | 703 kcal / 39.2P / 89.4C / 20.7F | ✅ |
| **lunch** — Grilled Chicken & Roasted Butternut Squash Bowl | 150g Chicken breast → *chicken breast* (165/31/0/3.6) = 248 kcal<br>400g Butternut squash → *butternut squash* (45/1/11.7/0.1) = 180 kcal<br>85g Kale → *kale* (49/4.3/9/0.9) = 42 kcal<br>200g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 172 kcal<br>13g Almonds → *almonds* (579/21/22/50) = 75 kcal<br>3g Olive oil → *olive oil* (884/0/0/100) = 27 kcal<br>17g Balsamic vinegar → *balsamic vinegar* (88/0.5/17/0) = 15 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal | 768 kcal / 60.6P / 102.2C / 16.3F | 768 kcal / 60.6P / 102.2C / 16.3F | ✅ |
| **dinner** — Pan-Seared Salmon with Herb Sweet Potato Mash | 115g Salmon → *salmon* (206/22/0/12.4) = 237 kcal<br>500g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 430 kcal<br>175g Asparagus → *asparagus* (20/2.2/4/0.1) = 35 kcal<br>7g Ghee → *ghee* (876/0/0/97) = 61 kcal<br>30g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 69 kcal<br>30g Lemon → *lemon* (29/1.1/9.3/0.3) = 9 kcal<br>3g Dill → *dill* (43/3.5/7/1.1) = 1 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal | 855 kcal / 38.8P / 114.6C / 29.0F | 855 kcal / 38.8P / 114.6C / 29.0F | ✅ |
| **snack** — Tropical Energy Smoothie | 125g Banana → *banana* (89/1.1/23/0.3) = 111 kcal<br>100g Mango → *mango* (60/0.8/15/0.4) = 60 kcal<br>30g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 69 kcal<br>4g Almond butter → *almond butter* (614/21/19/56) = 25 kcal<br>21g Dates → *dates* (282/2.5/75/0.4) = 59 kcal<br>5g Chia seeds → *chia seeds* (486/17/42/31) = 24 kcal<br>30g Spinach → *spinach* (23/2.9/3.6/0.4) = 7 kcal | 355 kcal / 6.0P / 65.2C / 11.9F | 355 kcal / 6.0P / 65.2C / 11.9F | ✅ |

**Day total on screen:** calo 2681 vs 2759 (-2.8%) / prot 144.6 vs 144 (+0.4%) / carb 371.4 vs 372 (-0.2%) / fats 77.9 vs 77 (+1.2%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## keto
Plan **Elite Keto Performance Plan** (`84f75d75-73e9-491f-b677-74603db2c5cd`), generated in 29s. Targets: 2759 kcal / 162.0P / 30.0C / 221.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Ribeye & Eggs with Avocado | 120g Ribeye steak → *ribeye steak* (291/24/0/21) = 349 kcal<br>116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>9g Butter → *butter* (717/0.9/0.1/81) = 65 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>45g Spinach → *spinach* (23/2.9/3.6/0.4) = 10 kcal | 684 kcal / 46.3P / 7.4C / 53.0F | 684 kcal / 46.3P / 7.4C / 53.0F | ✅ |
| **lunch** — Salmon Bowl with Cauliflower Rice | 240g Salmon → *salmon* (206/22/0/12.4) = 494 kcal<br>110g Cauliflower rice → *cauliflower rice* (25/1.9/5/0.3) = 28 kcal<br>14g Olive oil → *olive oil* (884/0/0/100) = 124 kcal<br>40g Avocado → *avocado* (160/2/9/15) = 64 kcal<br>13g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 93 kcal<br>40g Arugula → *arugula* (25/2.6/3.7/0.7) = 10 kcal | 813 kcal / 57.7P / 12.4C / 60.3F | 813 kcal / 57.7P / 12.4C / 60.3F | ✅ |
| **dinner** — Prime Rib with Garlic Butter Broccoli | 160g Prime rib → *prime rib* (340/22/0/28) = 544 kcal<br>100g Broccoli → *broccoli* (34/2.8/7/0.4) = 34 kcal<br>20g Butter → *butter* (717/0.9/0.1/81) = 143 kcal<br>2g Garlic → *garlic* (149/6/33/0.5) = 3 kcal<br>30g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 121 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal | 916 kcal / 45.8P / 8.1C / 79.3F | 916 kcal / 45.8P / 8.1C / 79.3F | ✅ |
| **snack** — Bacon & Cheese Plate | 30g Bacon → *bacon* (417/13/1.4/40) = 125 kcal<br>40g Brie → *brie* (334/20.8/0.5/27.7) = 134 kcal<br>11g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 79 kcal | 338 kcal / 13.1P / 2.1C / 31.5F | 338 kcal / 13.1P / 2.1C / 31.5F | ✅ |

**Day total on screen:** calo 2751 vs 2759 (-0.3%) / prot 162.9 vs 162 (+0.6%) / carb 30 vs 30 (+0.0%) / fats 224.1 vs 221 (+1.4%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Keto Omelette with Chorizo & Goat Cheese | 174g large eggs → *large eggs* (155/13/1.1/11) = 270 kcal<br>45g Chorizo → *chorizo* (455/24/1.9/38) = 205 kcal<br>30g Goat cheese → *goat cheese* (364/21.6/0.1/29.8) = 109 kcal<br>15g Butter → *butter* (717/0.9/0.1/81) = 108 kcal<br>45g Bell pepper → *bell pepper* (31/1/6/0.3) = 14 kcal | 706 kcal / 40.5P / 5.5C / 57.4F | 706 kcal / 40.5P / 5.5C / 57.4F | ✅ |
| **lunch** — Chicken Thigh Caesar with Parmesan Crisps | 140g Chicken thigh → *chicken thigh* (209/26/0/10.9) = 293 kcal<br>120g Romaine lettuce → *romaine lettuce* (17/1.2/3.3/0.3) = 20 kcal<br>35g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 151 kcal<br>22g Mayo → *mayo* (680/1/0/75) = 150 kcal<br>14g Olive oil → *olive oil* (884/0/0/100) = 124 kcal<br>25g Bacon → *bacon* (417/13/1.4/40) = 104 kcal | 842 kcal / 54.5P / 5.7C / 66.3F | 842 kcal / 54.5P / 5.7C / 66.3F | ✅ |
| **dinner** — Beef Brisket with Creamy Mushroom Sauce | 135g Beef brisket → *beef brisket* (291/28/0/19) = 393 kcal<br>150g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 33 kcal<br>65g Heavy cream → *heavy cream* (340/2.8/2.7/36) = 221 kcal<br>22g Butter → *butter* (717/0.9/0.1/81) = 158 kcal<br>205g Asparagus → *asparagus* (20/2.2/4/0.1) = 41 kcal<br>10g Olive oil → *olive oil* (884/0/0/100) = 88 kcal | 934 kcal / 49.0P / 14.9C / 77.5F | 934 kcal / 49.0P / 14.9C / 77.5F | ✅ |
| **snack** — Smoked Salmon & Cream Cheese Roll-Ups | 80g Smoked salmon → *smoked salmon* (117/18.3/0/4.3) = 94 kcal<br>45g Cream cheese → *cream cheese* (342/6/4/34) = 154 kcal<br>45g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 7 kcal<br>3g Dill → *dill* (43/3.5/7/1.1) = 1 kcal | 256 kcal / 17.7P / 3.6C / 18.7F | 256 kcal / 17.7P / 3.6C / 18.7F | ✅ |

**Day total on screen:** calo 2738 vs 2759 (-0.8%) / prot 161.7 vs 162 (-0.2%) / carb 29.7 vs 30 (-1.0%) / fats 219.9 vs 221 (-0.5%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Pork Belly & Fried Eggs with Sautéed Kale | 45g Pork belly → *pork belly* (518/9.3/0/53) = 233 kcal<br>116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>45g Kale → *kale* (49/4.3/9/0.9) = 22 kcal<br>15g Butter → *butter* (717/0.9/0.1/81) = 108 kcal<br>9g Ghee → *ghee* (876/0/0/97) = 79 kcal | 622 kcal / 21.3P / 5.3C / 58.0F | 622 kcal / 21.3P / 5.3C / 58.0F | ✅ |
| **lunch** — Lamb Chops with Feta & Olive Salad | 195g Lamb chops → *lamb chops* (258/25/0/17) = 503 kcal<br>40g Feta cheese → *feta cheese* (264/14/4/21) = 106 kcal<br>30g Olives → *olives* (115/0.8/6.3/10.7) = 34 kcal<br>70g Mixed greens → *mixed greens* (20/2/3.5/0.3) = 14 kcal<br>15g Olive oil → *olive oil* (884/0/0/100) = 133 kcal<br>35g Avocado → *avocado* (160/2/9/15) = 56 kcal | 846 kcal / 56.7P / 9.0C / 65.1F | 846 kcal / 56.7P / 9.0C / 65.1F | ✅ |
| **dinner** — Duck Breast with Brussels Sprouts & Bacon | 270g Duck breast → *duck breast* (201/23.5/0/11.2) = 543 kcal<br>75g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 32 kcal<br>30g Bacon → *bacon* (417/13/1.4/40) = 125 kcal<br>18g Butter → *butter* (717/0.9/0.1/81) = 129 kcal<br>30g Heavy cream → *heavy cream* (340/2.8/2.7/36) = 102 kcal<br>23g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 99 kcal | 1030 kcal / 79.6P / 8.9C / 74.5F | 1030 kcal / 79.6P / 8.9C / 74.5F | ✅ |
| **snack** — Pecans with Mascarpone | 18g Pecans → *pecans* (691/9/14/72) = 124 kcal<br>25g Mascarpone → *mascarpone* (429/4.6/4.6/44) = 107 kcal<br>22g Raspberries → *raspberries* (52/1.2/12/0.7) = 11 kcal | 242 kcal / 3.0P / 6.2C / 24.2F | 242 kcal / 3.0P / 6.2C / 24.2F | ✅ |

**Day total on screen:** calo 2740 vs 2759 (-0.7%) / prot 160.6 vs 162 (-0.9%) / carb 29.4 vs 30 (-2.0%) / fats 221.8 vs 221 (+0.4%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 lunch: “Salmon Bowl with Cauliflower Rice” → “Seared Tuna Steak with Avocado & Sesame Greens” (9s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Ribeye & Eggs with Avocado | 120g Ribeye steak → *ribeye steak* (291/24/0/21) = 349 kcal<br>116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>9g Butter → *butter* (717/0.9/0.1/81) = 65 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>45g Spinach → *spinach* (23/2.9/3.6/0.4) = 10 kcal | 684 kcal / 46.3P / 7.4C / 53.0F | 684 kcal / 46.3P / 7.4C / 53.0F | ✅ |
| **lunch** — Seared Tuna Steak with Avocado & Sesame Greens | 175g Tuna steak → *tuna steak* (130/29/0/0.6) = 228 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>60g Mixed greens → *mixed greens* (20/2/3.5/0.3) = 12 kcal<br>18g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 103 kcal<br>39.6g Olive oil → *olive oil* (884/0/0/100) = 350 kcal<br>8g Lime juice → *lime juice* (25/0.4/8/0.1) = 2 kcal<br>6g Soy sauce → *soy sauce* (53/8/5/0) = 3 kcal<br>4g Ginger → *ginger* (80/1.8/18/0.8) = 3 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 781 kcal / 56.8P / 12.4C / 57.3F | 781 kcal / 56.8P / 12.4C / 57.3F | ✅ |
| **dinner** — Prime Rib with Garlic Butter Broccoli | 160g Prime rib → *prime rib* (340/22/0/28) = 544 kcal<br>100g Broccoli → *broccoli* (34/2.8/7/0.4) = 34 kcal<br>20g Butter → *butter* (717/0.9/0.1/81) = 143 kcal<br>2g Garlic → *garlic* (149/6/33/0.5) = 3 kcal<br>30g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 121 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal | 916 kcal / 45.8P / 8.1C / 79.3F | 916 kcal / 45.8P / 8.1C / 79.3F | ✅ |
| **snack** — Bacon & Cheese Plate | 30g Bacon → *bacon* (417/13/1.4/40) = 125 kcal<br>40g Brie → *brie* (334/20.8/0.5/27.7) = 134 kcal<br>11g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 79 kcal | 338 kcal / 13.1P / 2.1C / 31.5F | 338 kcal / 13.1P / 2.1C / 31.5F | ✅ |

**Day total on screen:** calo 2719 vs 2759 (-1.4%) / prot 162 vs 162 (+0.0%) / carb 30 vs 30 (+0.0%) / fats 221.1 vs 221 (+0.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## carnivore
Plan **Elite Carnivore Performance Plan** (`3c5e2144-505b-455f-a813-7007640ce28a`), generated in 21s. Targets: 2759 kcal / 201.0P / 5.0C / 215.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Ribeye & Eggs with Butter | 90g Ribeye steak → *ribeye steak* (291/24/0/21) = 262 kcal<br>348g large eggs → *large eggs* (155/13/1.1/11) = 539 kcal<br>12g Butter → *butter* (717/0.9/0.1/81) = 86 kcal | 887 kcal / 66.9P / 3.8C / 66.9F | 887 kcal / 66.9P / 3.8C / 66.9F | ✅ |
| **lunch** — Grilled Salmon with Cheddar | 275g Salmon → *salmon* (206/22/0/12.4) = 566 kcal<br>40g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 161 kcal<br>12g Butter → *butter* (717/0.9/0.1/81) = 86 kcal | 813 kcal / 70.6P / 0.5C / 57.0F | 813 kcal / 70.6P / 0.5C / 57.0F | ✅ |
| **dinner** — Prime Rib with Bone Marrow Butter | 190g Prime rib → *prime rib* (340/22/0/28) = 646 kcal<br>18g Butter → *butter* (717/0.9/0.1/81) = 129 kcal<br>235g Bone broth → *bone broth* (17/3.8/0/0.2) = 40 kcal | 815 kcal / 50.9P / 0.0C / 68.3F | 815 kcal / 50.9P / 0.0C / 68.3F | ✅ |
| **snack** — Bacon & Brie Plate | 30g Bacon → *bacon* (417/13/1.4/40) = 125 kcal<br>40g Brie → *brie* (334/20.8/0.5/27.7) = 134 kcal | 259 kcal / 12.2P / 0.6C / 23.1F | 259 kcal / 12.2P / 0.6C / 23.1F | ✅ |

**Day total on screen:** calo 2774 vs 2759 (+0.5%) / prot 200.6 vs 201 (-0.2%) / carb 4.9 vs 5 (-2.0%) / fats 215.3 vs 215 (+0.1%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Chorizo Scramble with Ghee | 75g Chorizo → *chorizo* (455/24/1.9/38) = 341 kcal<br>116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>14g Ghee → *ghee* (876/0/0/97) = 123 kcal | 644 kcal / 33.1P / 2.7C / 54.9F | 644 kcal / 33.1P / 2.7C / 54.9F | ✅ |
| **lunch** — Beef Brisket with Gouda | 205g Beef brisket → *beef brisket* (291/28/0/19) = 597 kcal<br>40g Gouda → *gouda* (356/25/2.2/27.4) = 142 kcal<br>17g Beef tallow → *beef tallow* (902/0/0/100) = 153 kcal | 892 kcal / 67.4P / 0.9C / 66.9F | 892 kcal / 67.4P / 0.9C / 66.9F | ✅ |
| **dinner** — Lamb Chops with Duck Fat | 295g Lamb chops → *lamb chops* (258/25/0/17) = 761 kcal<br>25g Duck fat → *duck fat* (882/0/0/99.8) = 220 kcal<br>155g Bone broth → *bone broth* (17/3.8/0/0.2) = 26 kcal | 1007 kcal / 79.7P / 0.0C / 75.4F | 1007 kcal / 79.7P / 0.0C / 75.4F | ✅ |
| **snack** — Smoked Salmon & Cream Cheese Roll-Ups | 95g Smoked salmon → *smoked salmon* (117/18.3/0/4.3) = 111 kcal<br>35g Cream cheese → *cream cheese* (342/6/4/34) = 120 kcal | 231 kcal / 19.5P / 1.4C / 16.0F | 231 kcal / 19.5P / 1.4C / 16.0F | ✅ |

**Day total on screen:** calo 2774 vs 2759 (+0.5%) / prot 199.7 vs 201 (-0.6%) / carb 5 vs 5 (+0.0%) / fats 213.2 vs 215 (-0.8%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Pork Sausage & Egg Yolk Power Bowl | 70g Pork sausage → *pork sausage* (325/18.5/1.4/27) = 227 kcal<br>30g Egg yolk → *egg yolk* (322/15.9/3.6/26.5) = 97 kcal<br>30g Butter → *butter* (717/0.9/0.1/81) = 215 kcal | 539 kcal / 18.0P / 2.1C / 51.1F | 539 kcal / 18.0P / 2.1C / 51.1F | ✅ |
| **lunch** — Mackerel with Parmesan Crust | 280g Mackerel → *mackerel* (262/23.9/0/17.8) = 734 kcal<br>15g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 65 kcal<br>22g Butter → *butter* (717/0.9/0.1/81) = 158 kcal | 957 kcal / 72.8P / 0.6C / 71.9F | 957 kcal / 72.8P / 0.6C / 71.9F | ✅ |
| **dinner** — Sirloin Steak with Pork Belly | 335g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 710 kcal<br>45g Pork belly → *pork belly* (518/9.3/0/53) = 233 kcal<br>15g Ghee → *ghee* (876/0/0/97) = 131 kcal | 1074 kcal / 94.7P / 0.0C / 73.9F | 1074 kcal / 94.7P / 0.0C / 73.9F | ✅ |
| **snack** — Beef Jerky & Aged Cheddar | 16g Beef jerky → *beef jerky* (410/33.2/11/25.6) = 66 kcal<br>35g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 141 kcal | 207 kcal / 14.1P / 2.3C / 15.6F | 207 kcal / 14.1P / 2.3C / 15.6F | ✅ |

**Day total on screen:** calo 2777 vs 2759 (+0.7%) / prot 199.6 vs 201 (-0.7%) / carb 5 vs 5 (+0.0%) / fats 212.5 vs 215 (-1.2%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 dinner: “Prime Rib with Bone Marrow Butter” → “Pan-Seared Duck Breast with Gouda & Egg Yolk” (3s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Ribeye & Eggs with Butter | 90g Ribeye steak → *ribeye steak* (291/24/0/21) = 262 kcal<br>348g large eggs → *large eggs* (155/13/1.1/11) = 539 kcal<br>12g Butter → *butter* (717/0.9/0.1/81) = 86 kcal | 887 kcal / 66.9P / 3.8C / 66.9F | 887 kcal / 66.9P / 3.8C / 66.9F | ✅ |
| **lunch** — Grilled Salmon with Cheddar | 275g Salmon → *salmon* (206/22/0/12.4) = 566 kcal<br>40g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 161 kcal<br>12g Butter → *butter* (717/0.9/0.1/81) = 86 kcal | 813 kcal / 70.6P / 0.5C / 57.0F | 813 kcal / 70.6P / 0.5C / 57.0F | ✅ |
| **dinner** — Pan-Seared Duck Breast with Gouda & Egg Yolk | 155g Duck breast → *duck breast* (201/23.5/0/11.2) = 312 kcal<br>42g Gouda → *gouda* (356/25/2.2/27.4) = 150 kcal<br>31g Egg yolk → *egg yolk* (322/15.9/3.6/26.5) = 100 kcal<br>35g Butter → *butter* (717/0.9/0.1/81) = 251 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 813 kcal / 52.1P / 2.0C / 65.4F | 813 kcal / 52.1P / 2.0C / 65.4F | ✅ |
| **snack** — Bacon & Brie Plate | 30g Bacon → *bacon* (417/13/1.4/40) = 125 kcal<br>40g Brie → *brie* (334/20.8/0.5/27.7) = 134 kcal | 259 kcal / 12.2P / 0.6C / 23.1F | 259 kcal / 12.2P / 0.6C / 23.1F | ✅ |

**Day total on screen:** calo 2772 vs 2759 (+0.5%) / prot 201.8 vs 201 (+0.4%) / carb 6.9 vs 5 (+38.0%) / fats 212.4 vs 215 (-1.2%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## balanced + allergies ['gluten', 'dairy']
Plan **Elite Balanced Performance Plan** (`19ee0e84-c48d-48ab-b661-5c0e06b0d0d1`), generated in 31s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Sweet Potato Power Bowl with Eggs & Avocado | 400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>55g Avocado → *avocado* (160/2/9/15) = 88 kcal<br>40g Spinach → *spinach* (23/2.9/3.6/0.4) = 9 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal | 656 kcal / 23.8P / 87.7C / 25.6F | 656 kcal / 23.8P / 87.7C / 25.6F | ✅ |
| **lunch** — Grilled Chicken & Wild Rice Buddha Bowl | 105g Chicken breast → *chicken breast* (165/31/0/3.6) = 173 kcal<br>400g Wild rice → *wild rice* (101/4/21.3/0.3) = 404 kcal<br>175g Broccoli → *broccoli* (34/2.8/7/0.4) = 60 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>14g Tahini → *tahini* (595/17/23/54) = 83 kcal<br>17g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal | 741 kcal / 56.9P / 105.5C / 13.5F | 741 kcal / 56.9P / 105.5C / 13.5F | ✅ |
| **dinner** — Herb-Crusted Salmon with Basmati Rice & Asparagus | 100g Salmon → *salmon* (206/22/0/12.4) = 206 kcal<br>400g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 484 kcal<br>285g Asparagus → *asparagus* (20/2.2/4/0.1) = 57 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>17.6g Garlic → *garlic* (149/6/33/0.5) = 26 kcal<br>11g Parsley → *parsley* (36/3/6.3/0.8) = 4 kcal | 848 kcal / 43.7P / 118.7C / 22.5F | 848 kcal / 43.7P / 118.7C / 22.5F | ✅ |
| **snack** — Tropical Mango Cashew Protein Snack | 330g Mango → *mango* (60/0.8/15/0.4) = 198 kcal<br>25g Cashews → *cashews* (553/18/30/44) = 138 kcal<br>19g Pea protein powder → *pea protein powder* (380/72/8/5) = 72 kcal<br>5g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 33 kcal | 441 kcal / 21.1P / 59.7C / 16.4F | 441 kcal / 21.1P / 59.7C / 16.4F | ✅ |

**Day total on screen:** calo 2686 vs 2759 (-2.6%) / prot 145.5 vs 144 (+1.0%) / carb 371.6 vs 372 (-0.1%) / fats 78 vs 77 (+1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Sirloin Steak & Hash Brown Breakfast | 80g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 170 kcal<br>400g Potato → *potato* (77/2/17/0.1) = 308 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>85g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 26 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal | 665 kcal / 37.9P / 73.7C / 23.6F | 665 kcal / 37.9P / 73.7C / 23.6F | ✅ |
| **lunch** — Turkey & Quinoa Power Salad | 90g Turkey breast → *turkey breast* (135/30/0/1) = 122 kcal<br>270g Quinoa → *quinoa* (120/4.4/21/1.9) = 324 kcal<br>130g Chickpeas → *chickpeas* (164/9/27/2.6) = 213 kcal<br>100g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 15 kcal<br>60g Arugula → *arugula* (25/2.6/3.7/0.7) = 15 kcal<br>12g Olive oil → *olive oil* (884/0/0/100) = 106 kcal<br>17g Balsamic vinegar → *balsamic vinegar* (88/0.5/17/0) = 15 kcal | 810 kcal / 53.0P / 100.5C / 21.9F | 810 kcal / 53.0P / 100.5C / 21.9F | ✅ |
| **dinner** — Lean Beef Stir-Fry with Brown Rice | 110g Beef mince 95/5 → *beef mince 95/5* (171/26.5/0/6.9) = 188 kcal<br>400g Brown rice → *brown rice* (123/2.7/25.6/1) = 492 kcal<br>150g Bok choy → *bok choy* (13/1.5/2/0.2) = 20 kcal<br>135g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 57 kcal<br>90g Carrot → *carrot* (41/0.9/10/0.2) = 37 kcal<br>25g Coconut aminos → *coconut aminos* (74/2/18/0) = 18 kcal<br>8g Sesame oil → *sesame oil* (884/0/0/100) = 71 kcal<br>11g Ginger → *ginger* (80/1.8/18/0.8) = 9 kcal | 892 kcal / 47.5P / 131.2C / 20.5F | 892 kcal / 47.5P / 131.2C / 20.5F | ✅ |
| **snack** — Apple Almond Energy Bites | 175g Apple → *apple* (52/0.3/14/0.2) = 91 kcal<br>20g Almond butter → *almond butter* (614/21/19/56) = 123 kcal<br>50g Dates → *dates* (282/2.5/75/0.4) = 141 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 360 kcal / 6.0P / 67.4C / 11.8F | 360 kcal / 6.0P / 67.4C / 11.8F | ✅ |

**Day total on screen:** calo 2727 vs 2759 (-1.2%) / prot 144.4 vs 144 (+0.3%) / carb 372.8 vs 372 (+0.2%) / fats 77.8 vs 77 (+1.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Mediterranean Chicken Sausage Scramble | 70g Chicken mince → *chicken mince* (189/23.3/0/10.2) = 132 kcal<br>58g large egg → *large eggs* (155/13/1.1/11) = 90 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>110g Zucchini → *zucchini* (17/1.2/3.1/0.3) = 19 kcal<br>65g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 12 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal | 650 kcal / 32.1P / 86.5C / 20.3F | 650 kcal / 32.1P / 86.5C / 20.3F | ✅ |
| **lunch** — Tuna Poke Bowl with White Rice | 135g Tuna steak → *tuna steak* (130/29/0/0.6) = 176 kcal<br>400g White rice → *white rice* (130/2.7/28/0.3) = 520 kcal<br>55g Avocado → *avocado* (160/2/9/15) = 88 kcal<br>90g Edamame → *edamame* (121/11/8/5) = 109 kcal<br>90g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 14 kcal<br>5g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 29 kcal<br>23g Coconut aminos → *coconut aminos* (74/2/18/0) = 17 kcal | 953 kcal / 63.0P / 132.7C / 17.3F | 953 kcal / 63.0P / 132.7C / 17.3F | ✅ |
| **dinner** — Herb-Roasted Chicken Thigh with Sweet Potato Mash | 110g Chicken thigh → *chicken thigh* (209/26/0/10.9) = 230 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>285g Green beans → *green beans* (31/1.8/7/0.1) = 88 kcal<br>9g Olive oil → *olive oil* (884/0/0/100) = 80 kcal<br>3g Rosemary → *rosemary* (131/3.3/20.7/5.9) = 4 kcal<br>15g Garlic → *garlic* (149/6/33/0.5) = 22 kcal | 768 kcal / 41.1P / 105.5C / 22.0F | 768 kcal / 41.1P / 105.5C / 22.0F | ✅ |
| **snack** — Berry Cashew Protein Bowl | 210g Blueberry → *blueberry* (57/0.7/14/0.3) = 120 kcal<br>100g Strawberry → *strawberry* (32/0.7/8/0.3) = 32 kcal<br>24g Cashews → *cashews* (553/18/30/44) = 133 kcal<br>8g Hemp seed → *hemp seed* (553/32/9/49) = 44 kcal<br>5g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 33 kcal | 362 kcal / 9.4P / 46.5C / 18.6F | 362 kcal / 9.4P / 46.5C / 18.6F | ✅ |

**Day total on screen:** calo 2733 vs 2759 (-0.9%) / prot 145.6 vs 144 (+1.1%) / carb 371.2 vs 372 (-0.2%) / fats 78.2 vs 77 (+1.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 snack: “Tropical Mango Cashew Protein Snack” → “Banana Cashew Protein Energy Balls” (3s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Sweet Potato Power Bowl with Eggs & Avocado | 400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>116g large eggs → *large eggs* (155/13/1.1/11) = 180 kcal<br>55g Avocado → *avocado* (160/2/9/15) = 88 kcal<br>40g Spinach → *spinach* (23/2.9/3.6/0.4) = 9 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal | 656 kcal / 23.8P / 87.7C / 25.6F | 656 kcal / 23.8P / 87.7C / 25.6F | ✅ |
| **lunch** — Grilled Chicken & Wild Rice Buddha Bowl | 105g Chicken breast → *chicken breast* (165/31/0/3.6) = 173 kcal<br>400g Wild rice → *wild rice* (101/4/21.3/0.3) = 404 kcal<br>175g Broccoli → *broccoli* (34/2.8/7/0.4) = 60 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>14g Tahini → *tahini* (595/17/23/54) = 83 kcal<br>17g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal | 741 kcal / 56.9P / 105.5C / 13.5F | 741 kcal / 56.9P / 105.5C / 13.5F | ✅ |
| **dinner** — Herb-Crusted Salmon with Basmati Rice & Asparagus | 100g Salmon → *salmon* (206/22/0/12.4) = 206 kcal<br>400g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 484 kcal<br>285g Asparagus → *asparagus* (20/2.2/4/0.1) = 57 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>17.6g Garlic → *garlic* (149/6/33/0.5) = 26 kcal<br>11g Parsley → *parsley* (36/3/6.3/0.8) = 4 kcal | 848 kcal / 43.7P / 118.7C / 22.5F | 848 kcal / 43.7P / 118.7C / 22.5F | ✅ |
| **snack** — Banana Cashew Protein Energy Balls | 210g Banana → *banana* (89/1.1/23/0.3) = 187 kcal<br>12g Cashew butter → *cashew butter* (587/17.6/27.6/49.4) = 70 kcal<br>20g Pea protein powder → *pea protein powder* (380/72/8/5) = 76 kcal<br>19g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 114 kcal<br>1g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 7 kcal | 454 kcal / 20.4P / 61.6C / 16.1F | 454 kcal / 20.4P / 61.6C / 16.1F | ✅ |

**Day total on screen:** calo 2699 vs 2759 (-2.2%) / prot 144.8 vs 144 (+0.6%) / carb 373.5 vs 372 (+0.4%) / fats 77.7 vs 77 (+0.9%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## vegan + allergies ['nuts', 'soy']
Plan **Elite Vegan High-Performance 3-Day Plan** (`e3a1e0e3-5c6f-44ff-8313-d1f49fb86fc1`), generated in 36s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Quinoa Bowl | 220g Quinoa → *quinoa* (120/4.4/21/1.9) = 264 kcal<br>30g Pea protein powder → *pea protein powder* (380/72/8/5) = 114 kcal<br>115g Blueberry → *blueberry* (57/0.7/14/0.3) = 66 kcal<br>75g Strawberry → *strawberry* (32/0.7/8/0.3) = 24 kcal<br>15g Chia seeds → *chia seeds* (486/17/42/31) = 73 kcal<br>21g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 55 kcal<br>140g Plant milk → *plant milk* (35/1.5/4/1.8) = 49 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 650 kcal / 37.3P / 98.3C / 13.3F | 650 kcal / 37.3P / 98.3C / 13.3F | ✅ |
| **lunch** — Seitan Power Bowl with Roasted Vegetables | 90g Seitan → *seitan* (166/25/14/2) = 149 kcal<br>270g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 232 kcal<br>100g Chickpeas → *chickpeas* (164/9/27/2.6) = 164 kcal<br>55g Kale → *kale* (49/4.3/9/0.9) = 27 kcal<br>21g Tahini → *tahini* (595/17/23/54) = 125 kcal<br>12g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>15g Olive oil → *olive oil* (884/0/0/100) = 133 kcal<br>4g Garlic → *garlic* (149/6/33/0.5) = 6 kcal<br>2g Smoked paprika → *smoked paprika* (282/14/54/13) = 6 kcal | 845 kcal / 42.3P / 106.6C / 31.8F | 845 kcal / 42.3P / 106.6C / 31.8F | ✅ |
| **dinner** — Lentil Bolognese with Whole Wheat Pasta | 190g Whole wheat pasta → *whole wheat pasta* (149/6/30/1.1) = 283 kcal<br>175g Lentils → *lentils* (116/9/20/0.4) = 203 kcal<br>190g Marinara sauce → *marinara sauce* (50/1.5/8/1.5) = 95 kcal<br>110g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 24 kcal<br>110g Zucchini → *zucchini* (17/1.2/3.1/0.3) = 19 kcal<br>85g Spinach → *spinach* (23/2.9/3.6/0.4) = 20 kcal<br>9g Yeast flakes → *yeast flakes* (355/50/35/7) = 32 kcal<br>17g Olive oil → *olive oil* (884/0/0/100) = 150 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal<br>4g Basil → *basil* (23/3.2/2.7/0.6) = 1 kcal | 837 kcal / 42.2P / 122.8C / 24.1F | 837 kcal / 42.2P / 122.8C / 24.1F | ✅ |
| **snack** — Chocolate Protein Smoothie | 23g Pea protein powder → *pea protein powder* (380/72/8/5) = 87 kcal<br>95g Banana → *banana* (89/1.1/23/0.3) = 85 kcal<br>5g Cocoa powder → *cocoa powder* (228/20/28/14) = 11 kcal<br>205g Plant milk → *plant milk* (35/1.5/4/1.8) = 72 kcal<br>21g Dates → *dates* (282/2.5/75/0.4) = 59 kcal<br>6g Flax seeds → *flax seeds* (534/18/29/42) = 32 kcal | 346 kcal / 23.3P / 50.7C / 8.5F | 346 kcal / 23.3P / 50.7C / 8.5F | ✅ |

**Day total on screen:** calo 2678 vs 2759 (-2.9%) / prot 145.1 vs 144 (+0.8%) / carb 378.4 vs 372 (+1.7%) / fats 77.7 vs 77 (+0.9%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Loaded Chickpea Scramble with Avocado Toast | 70g Chickpea flour → *chickpea flour* (387/22/58/6) = 271 kcal<br>90g whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 222 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>75g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 14 kcal<br>55g Spinach → *spinach* (23/2.9/3.6/0.4) = 13 kcal<br>7g Yeast flakes → *yeast flakes* (355/50/35/7) = 25 kcal<br>2g Turmeric → *turmeric* (312/9.7/67/3.3) = 6 kcal<br>5g Olive oil → *olive oil* (884/0/0/100) = 44 kcal<br>1g Black pepper → *black pepper* (251/10.4/64/3.3) = 3 kcal | 678 kcal / 31.5P / 91.3C / 20.8F | 678 kcal / 31.5P / 91.3C / 20.8F | ✅ |
| **lunch** — Mediterranean Seitan Wrap with Hummus | 120g whole wheat wraps → *whole wheat wrap* (310/8/52/8) = 372 kcal<br>135g Seitan → *seitan* (166/25/14/2) = 224 kcal<br>50g Hummus → *hummus* (166/8/14/10) = 83 kcal<br>90g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 14 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>55g Romaine lettuce → *romaine lettuce* (17/1.2/3.3/0.3) = 9 kcal<br>25g Olives → *olives* (115/0.8/6.3/10.7) = 29 kcal<br>12g Tahini → *tahini* (595/17/23/54) = 71 kcal<br>9g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 2 kcal | 829 kcal / 51.7P / 103.1C / 27.0F | 829 kcal / 51.7P / 103.1C / 27.0F | ✅ |
| **dinner** — Black Bean and Sweet Potato Buddha Bowl | 180g Black beans → *black beans* (132/9/24/0.5) = 238 kcal<br>150g Brown rice → *brown rice* (123/2.7/25.6/1) = 184 kcal<br>160g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 138 kcal<br>115g Broccoli → *broccoli* (34/2.8/7/0.4) = 39 kcal<br>75g Red cabbage → *cabbage* (25/1.3/6/0.1) = 19 kcal<br>16g Tahini → *tahini* (595/17/23/54) = 95 kcal<br>15g Hemp seed → *hemp seed* (553/32/9/49) = 83 kcal<br>14g Lime juice → *lime juice* (25/0.4/8/0.1) = 4 kcal<br>2g Cumin → *cumin* (375/17.8/44/22) = 8 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal | 843 kcal / 35.1P / 133.1C / 23.5F | 843 kcal / 35.1P / 133.1C / 23.5F | ✅ |
| **snack** — Apple Cinnamon Protein Bites | 30g Pea protein powder → *pea protein powder* (380/72/8/5) = 114 kcal<br>25g Rolled oats → *rolled oats* (389/17/66/7) = 97 kcal<br>75g Apple → *apple* (52/0.3/14/0.2) = 39 kcal<br>20g Dates → *dates* (282/2.5/75/0.4) = 56 kcal<br>5g Flax seeds → *flax seeds* (534/18/29/42) = 27 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal<br>30g Plant milk → *plant milk* (35/1.5/4/1.8) = 10 kcal | 348 kcal / 27.9P / 48.7C / 6.2F | 348 kcal / 27.9P / 48.7C / 6.2F | ✅ |

**Day total on screen:** calo 2698 vs 2759 (-2.2%) / prot 146.2 vs 144 (+1.5%) / carb 376.2 vs 372 (+1.1%) / fats 77.5 vs 77 (+0.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — High-Protein Banana Pancakes with Berry Compote | 100g Chickpea flour → *chickpea flour* (387/22/58/6) = 387 kcal<br>21g Pea protein powder → *pea protein powder* (380/72/8/5) = 80 kcal<br>115g Banana → *banana* (89/1.1/23/0.3) = 102 kcal<br>110g Plant milk → *plant milk* (35/1.5/4/1.8) = 38 kcal<br>110g Mixed berries → *mixed berries* (43/1/10/0.3) = 47 kcal<br>24g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 62 kcal<br>9g Flax seeds → *flax seeds* (534/18/29/42) = 48 kcal<br>5g Coconut oil → *coconut oil* (862/0/0/100) = 43 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 812 kcal / 42.9P / 121.8C / 18.5F | 812 kcal / 42.9P / 121.8C / 18.5F | ✅ |
| **lunch** — Spicy Seitan Stir-Fry with Quinoa | 90g Seitan → *seitan* (166/25/14/2) = 149 kcal<br>180g Quinoa → *quinoa* (120/4.4/21/1.9) = 216 kcal<br>110g Bok choy → *bok choy* (13/1.5/2/0.2) = 14 kcal<br>105g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 33 kcal<br>100g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 42 kcal<br>13g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 74 kcal<br>25g Coconut aminos → *coconut aminos* (74/2/18/0) = 18 kcal<br>16g Sriracha → *sriracha* (93/1.9/19/0.9) = 15 kcal<br>8g Ginger → *ginger* (80/1.8/18/0.8) = 6 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal<br>7g Coconut oil → *coconut oil* (862/0/0/100) = 60 kcal | 636 kcal / 39.6P / 80.5C / 19.6F | 636 kcal / 39.6P / 80.5C / 19.6F | ✅ |
| **dinner** — White Bean and Vegetable Curry with Brown Rice | 145g White beans → *white beans* (139/9.7/25.1/0.4) = 202 kcal<br>210g Brown rice → *brown rice* (123/2.7/25.6/1) = 258 kcal<br>125g Cauliflower rice → *cauliflower rice* (25/1.9/5/0.3) = 31 kcal<br>85g Spinach → *spinach* (23/2.9/3.6/0.4) = 20 kcal<br>125g Canned tomatoes → *canned tomatoes* (32/1.6/7.3/0.3) = 40 kcal<br>65g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 150 kcal<br>75g Chickpeas → *chickpeas* (164/9/27/2.6) = 123 kcal<br>4g Curry powder → *curry powder* (325/14.3/56/14) = 13 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal<br>6g Ginger → *ginger* (80/1.8/18/0.8) = 5 kcal<br>9g Coconut oil → *coconut oil* (862/0/0/100) = 78 kcal<br>5g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 1 kcal | 931 kcal / 36.2P / 138.2C / 30.9F | 931 kcal / 36.2P / 138.2C / 30.9F | ✅ |
| **snack** — Tropical Green Protein Smoothie | 25g Pea protein powder → *pea protein powder* (380/72/8/5) = 95 kcal<br>105g Mango → *mango* (60/0.8/15/0.4) = 63 kcal<br>45g Spinach → *spinach* (23/2.9/3.6/0.4) = 10 kcal<br>180g Plant milk → *plant milk* (35/1.5/4/1.8) = 63 kcal<br>11g Chia seeds → *chia seeds* (486/17/42/31) = 53 kcal<br>100g Coconut water → *coconut water* (19/0.7/3.7/0.2) = 19 kcal<br>9g Lime juice → *lime juice* (25/0.4/8/0.1) = 2 kcal | 305 kcal / 25.4P / 35.6C / 8.6F | 305 kcal / 25.4P / 35.6C / 8.6F | ✅ |

**Day total on screen:** calo 2684 vs 2759 (-2.7%) / prot 144.1 vs 144 (+0.1%) / carb 376.1 vs 372 (+1.1%) / fats 77.6 vs 77 (+0.8%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 breakfast: “Protein-Packed Berry Quinoa Bowl” → “Lentil and Pumpkin Spice Porridge with Berries” (5s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Lentil and Pumpkin Spice Porridge with Berries | 70g Rolled oats → *rolled oats* (389/17/66/7) = 272 kcal<br>60g Lentils → *lentils* (116/9/20/0.4) = 70 kcal<br>370g Plant milk → *plant milk* (35/1.5/4/1.8) = 130 kcal<br>60g Pumpkin → *pumpkin* (26/1/6.5/0.1) = 16 kcal<br>3g Cinnamon → *cinnamon* (247/4/81/1.2) = 7 kcal<br>15g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 39 kcal<br>85g Mixed berries → *mixed berries* (43/1/10/0.3) = 37 kcal<br>18g Pea protein powder → *pea protein powder* (380/72/8/5) = 68 kcal | 639 kcal / 37.4P / 99.2C / 13.1F | 639 kcal / 37.4P / 99.2C / 13.1F | ✅ |
| **lunch** — Seitan Power Bowl with Roasted Vegetables | 90g Seitan → *seitan* (166/25/14/2) = 149 kcal<br>270g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 232 kcal<br>100g Chickpeas → *chickpeas* (164/9/27/2.6) = 164 kcal<br>55g Kale → *kale* (49/4.3/9/0.9) = 27 kcal<br>21g Tahini → *tahini* (595/17/23/54) = 125 kcal<br>12g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>15g Olive oil → *olive oil* (884/0/0/100) = 133 kcal<br>4g Garlic → *garlic* (149/6/33/0.5) = 6 kcal<br>2g Smoked paprika → *smoked paprika* (282/14/54/13) = 6 kcal | 845 kcal / 42.3P / 106.6C / 31.8F | 845 kcal / 42.3P / 106.6C / 31.8F | ✅ |
| **dinner** — Lentil Bolognese with Whole Wheat Pasta | 190g Whole wheat pasta → *whole wheat pasta* (149/6/30/1.1) = 283 kcal<br>175g Lentils → *lentils* (116/9/20/0.4) = 203 kcal<br>190g Marinara sauce → *marinara sauce* (50/1.5/8/1.5) = 95 kcal<br>110g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 24 kcal<br>110g Zucchini → *zucchini* (17/1.2/3.1/0.3) = 19 kcal<br>85g Spinach → *spinach* (23/2.9/3.6/0.4) = 20 kcal<br>9g Yeast flakes → *yeast flakes* (355/50/35/7) = 32 kcal<br>17g Olive oil → *olive oil* (884/0/0/100) = 150 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal<br>4g Basil → *basil* (23/3.2/2.7/0.6) = 1 kcal | 837 kcal / 42.2P / 122.8C / 24.1F | 837 kcal / 42.2P / 122.8C / 24.1F | ✅ |
| **snack** — Chocolate Protein Smoothie | 23g Pea protein powder → *pea protein powder* (380/72/8/5) = 87 kcal<br>95g Banana → *banana* (89/1.1/23/0.3) = 85 kcal<br>5g Cocoa powder → *cocoa powder* (228/20/28/14) = 11 kcal<br>205g Plant milk → *plant milk* (35/1.5/4/1.8) = 72 kcal<br>21g Dates → *dates* (282/2.5/75/0.4) = 59 kcal<br>6g Flax seeds → *flax seeds* (534/18/29/42) = 32 kcal | 346 kcal / 23.3P / 50.7C / 8.5F | 346 kcal / 23.3P / 50.7C / 8.5F | ✅ |

**Day total on screen:** calo 2667 vs 2759 (-3.3%) / prot 145.2 vs 144 (+0.8%) / carb 379.3 vs 372 (+2.0%) / fats 77.5 vs 77 (+0.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target

