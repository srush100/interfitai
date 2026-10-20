# Meal plan verification — real generated plans

Generated 2026-10-20 10:21 UTC against https://nutrition-debug-1.preview.emergentagent.com/api. “Calculated from ingredients” = grams ÷ 100 × the database's per-100g values, rounded per ingredient exactly as the app shows them.


## Summary

| Plan | Meals match ingredients | Days within 5% | Allergy/diet safe | Swap (Day 1) | Swap: match / within 5% / safe |
|---|---|---|---|---|---|
| balanced | ✅ 3/3 days | ✅ 3/3 | ✅ | Protein-Packed Blueberry Oat Pancakes with Almond Butter → Whole Wheat Toast with Scrambled Eggs and Berries | ✅ / ✅ / ✅ |
| high_protein | ✅ 3/3 days | ✅ 3/3 | ✅ | Grilled Chicken & Sweet Potato Power Bowl → Spiced Turkey & Quinoa Buddha Bowl | ✅ / ✅ / ✅ |
| vegetarian | ✅ 3/3 days | ✅ 3/3 | ✅ | Tempeh Stir-Fry with Brown Rice → Chickpea Curry with Basmati Rice | ✅ / ✅ / ✅ |
| vegan | ✅ 3/3 days | ✅ 3/3 | ✅ | Chocolate Peanut Protein Smoothie → Chickpea Flour Energy Bites with Dates | ✅ / ✅ / ✅ |
| paleo | ✅ 3/3 days | ✅ 3/3 | ✅ | Sweet Potato & Egg Skillet with Berries → Tropical Mango & Prawn Scramble with Sweet Potato Hash | ✅ / ✅ / ✅ |
| keto | ✅ 3/3 days | ✅ 3/3 | ✅ | Pan-Seared Salmon with Creamy Garlic Broccoli → Seared Tuna Steak with Creamy Avocado & Crispy Bacon | ✅ / ✅ / ✅ |
| carnivore | ✅ 3/3 days | ✅ 3/3 | ✅ | Prime Rib with Bone Marrow Butter → Pan-Seared Halibut with Gouda & Butter | ✅ / ✅ / ✅ |
| balanced + allergies ['gluten', 'dairy'] | ✅ 3/3 days | ✅ 3/3 | ✅ | Apple Slices with Almond Butter & Dark Chocolate → Pear & Almond Butter Energy Snack | ✅ / ✅ / ✅ |
| vegan + allergies ['nuts', 'soy'] | ✅ 3/3 days | ✅ 3/3 | ✅ | Protein-Packed Berry Quinoa Bowl → Spiced Lentil & Chickpea Flour Porridge with Mango | ✅ / ✅ / ✅ |

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
Plan **Elite Balanced Performance Plan** (`34060a95-eeeb-4372-9bf0-e1000e2070c5`), generated in 34s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Blueberry Oat Pancakes with Almond Butter | 85g Rolled oats → *rolled oats* (389/17/66/7) = 331 kcal<br>60g Eggs → *eggs* (155/13/1.1/11) = 93 kcal<br>125g Banana → *banana* (89/1.1/23/0.3) = 111 kcal<br>17g Whey protein → *whey protein* (400/80/10/3.3) = 68 kcal<br>105g Blueberry → *blueberry* (57/0.7/14/0.3) = 60 kcal<br>12g Almond butter → *almond butter* (614/21/19/56) = 74 kcal<br>16g Honey → *honey* (304/0.3/82/0) = 49 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 791 kcal / 40.5P / 119.0C / 20.6F | 791 kcal / 40.5P / 119.0C / 20.6F | ✅ |
| **lunch** — Teriyaki Salmon Bowl with Brown Rice and Roasted Vegetables | 70g Salmon → *salmon* (206/22/0/12.4) = 144 kcal<br>295g Brown rice → *brown rice* (123/2.7/25.6/1) = 363 kcal<br>125g Broccoli → *broccoli* (34/2.8/7/0.4) = 42 kcal<br>105g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 33 kcal<br>70g Edamame → *edamame* (121/11/8/5) = 85 kcal<br>30g Teriyaki sauce → *teriyaki sauce* (89/3.5/17/0) = 27 kcal<br>4g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 23 kcal<br>5g Olive oil → *olive oil* (884/0/0/100) = 44 kcal | 761 kcal / 37.5P / 102.2C / 23.0F | 761 kcal / 37.5P / 102.2C / 23.0F | ✅ |
| **dinner** — Lean Beef Bolognese with Whole Wheat Pasta and Garden Salad | 90g Beef mince 95/5 → *beef mince 95/5* (171/26.5/0/6.9) = 154 kcal<br>235g Whole wheat pasta → *whole wheat pasta* (149/6/30/1.1) = 350 kcal<br>155g Marinara sauce → *marinara sauce* (50/1.5/8/1.5) = 78 kcal<br>95g Canned tomatoes → *canned tomatoes* (32/1.6/7.3/0.3) = 30 kcal<br>115g Zucchini → *zucchini* (17/1.2/3.1/0.3) = 20 kcal<br>80g Carrot → *carrot* (41/0.9/10/0.2) = 33 kcal<br>75g Mixed greens → *mixed greens* (20/2/3.5/0.3) = 15 kcal<br>60g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 11 kcal<br>9g Olive oil → *olive oil* (884/0/0/100) = 80 kcal<br>11g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 47 kcal | 818 kcal / 50.1P / 106.7C / 24.4F | 818 kcal / 50.1P / 106.7C / 24.4F | ✅ |
| **snack** — Greek Yogurt Parfait with Granola and Mixed Berries | 115g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 84 kcal<br>35g Granola → *granola* (471/10/64/20) = 165 kcal<br>100g Mixed berries → *mixed berries* (43/1/10/0.3) = 43 kcal<br>13g Honey → *honey* (304/0.3/82/0) = 40 kcal | 332 kcal / 16.0P / 47.6C / 9.5F | 332 kcal / 16.0P / 47.6C / 9.5F | ✅ |

**Day total on screen:** calo 2702 vs 2759 (-2.1%) / prot 144.1 vs 144 (+0.1%) / carb 375.5 vs 372 (+0.9%) / fats 77.5 vs 77 (+0.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Scrambled Eggs with Sweet Potato Hash and Avocado Toast | 75g Eggs → *eggs* (155/13/1.1/11) = 116 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>110g Whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 272 kcal<br>30g Avocado → *avocado* (160/2/9/15) = 48 kcal<br>60g Spinach → *spinach* (23/2.9/3.6/0.4) = 14 kcal<br>115g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 36 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>1g Black pepper → *black pepper* (251/10.4/64/3.3) = 3 kcal | 886 kcal / 30.7P / 138.3C / 23.3F | 886 kcal / 30.7P / 138.3C / 23.3F | ✅ |
| **lunch** — Grilled Chicken Quinoa Power Bowl with Tahini Dressing | 115g Chicken breast → *chicken breast* (165/31/0/3.6) = 190 kcal<br>150g Quinoa → *quinoa* (120/4.4/21/1.9) = 180 kcal<br>140g Chickpeas → *chickpeas* (164/9/27/2.6) = 230 kcal<br>80g Kale → *kale* (49/4.3/9/0.9) = 39 kcal<br>145g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 22 kcal<br>125g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 22 kcal<br>10g Tahini → *tahini* (595/17/23/54) = 60 kcal<br>18g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal | 782 kcal / 62.1P / 90.2C / 20.9F | 782 kcal / 62.1P / 90.2C / 20.9F | ✅ |
| **dinner** — Herb-Crusted Sirloin Steak with Roasted Potatoes and Asparagus | 100g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 212 kcal<br>400g Potato → *potato* (77/2/17/0.1) = 308 kcal<br>400g Asparagus → *asparagus* (20/2.2/4/0.1) = 80 kcal<br>22g Garlic → *garlic* (149/6/33/0.5) = 33 kcal<br>2g Rosemary → *rosemary* (131/3.3/20.7/5.9) = 3 kcal<br>2g Thyme → *thyme* (101/5.6/24/1.7) = 2 kcal<br>9g Olive oil → *olive oil* (884/0/0/100) = 80 kcal<br>5g Butter → *butter* (717/0.9/0.1/81) = 36 kcal | 754 kcal / 45.3P / 92.2C / 24.6F | 754 kcal / 45.3P / 92.2C / 24.6F | ✅ |
| **snack** — Apple Slices with Peanut Butter and Dark Chocolate | 320g Apple → *apple* (52/0.3/14/0.2) = 166 kcal<br>14g Peanut butter → *peanut butter* (588/25/20/50) = 82 kcal<br>8g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 48 kcal | 296 kcal / 5.1P / 51.0C / 11.0F | 296 kcal / 5.1P / 51.0C / 11.0F | ✅ |

**Day total on screen:** calo 2718 vs 2759 (-1.5%) / prot 143.2 vs 144 (-0.6%) / carb 371.7 vs 372 (-0.1%) / fats 79.8 vs 77 (+3.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Tropical Mango Smoothie Bowl with Coconut and Chia | 220g Mango → *mango* (60/0.8/15/0.4) = 132 kcal<br>135g Banana → *banana* (89/1.1/23/0.3) = 120 kcal<br>145g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 106 kcal<br>18g Whey protein → *whey protein* (400/80/10/3.3) = 72 kcal<br>45g Rolled oats → *rolled oats* (389/17/66/7) = 175 kcal<br>10g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 66 kcal<br>10g Chia seeds → *chia seeds* (486/17/42/31) = 49 kcal<br>50g Strawberry → *strawberry* (32/0.7/8/0.3) = 16 kcal<br>100g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 17 kcal | 753 kcal / 43.2P / 113.3C / 18.6F | 753 kcal / 43.2P / 113.3C / 18.6F | ✅ |
| **lunch** — Turkey and Hummus Whole Wheat Wrap with Sweet Potato Wedges | 70g Turkey breast → *turkey breast* (135/30/0/1) = 94 kcal<br>105g Whole wheat wrap → *whole wheat wrap* (310/8/52/8) = 326 kcal<br>50g Hummus → *hummus* (166/8/14/10) = 83 kcal<br>50g Romaine lettuce → *romaine lettuce* (17/1.2/3.3/0.3) = 8 kcal<br>80g Tomato → *tomato* (18/0.9/3.9/0.2) = 14 kcal<br>60g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 9 kcal<br>370g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 318 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>2g Paprika → *paprika* (282/14/54/13) = 6 kcal | 911 kcal / 41.3P / 143.6C / 21.2F | 911 kcal / 41.3P / 143.6C / 21.2F | ✅ |
| **dinner** — Lemon Herb Halibut with Wild Rice and Sautéed Green Beans | 110g Halibut → *halibut* (111/22.5/0/1.6) = 122 kcal<br>275g Wild rice → *wild rice* (101/4/21.3/0.3) = 278 kcal<br>200g Green beans → *green beans* (31/1.8/7/0.1) = 62 kcal<br>40g Lemon → *lemon* (29/1.1/9.3/0.3) = 12 kcal<br>13g Garlic → *garlic* (149/6/33/0.5) = 19 kcal<br>10g Parsley → *parsley* (36/3/6.3/0.8) = 4 kcal<br>100g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 18 kcal<br>18g Olive oil → *olive oil* (884/0/0/100) = 159 kcal<br>8g Butter → *butter* (717/0.9/0.1/81) = 57 kcal | 731 kcal / 41.9P / 85.1C / 27.8F | 731 kcal / 41.9P / 85.1C / 27.8F | ✅ |
| **snack** — Cottage Cheese Bowl with Pineapple and Almonds | 130g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 109 kcal<br>130g Pineapple → *pineapple* (50/0.5/13/0.1) = 65 kcal<br>15g Almonds → *almonds* (579/21/22/50) = 87 kcal<br>13g Honey → *honey* (304/0.3/82/0) = 40 kcal | 301 kcal / 18.1P / 36.1C / 10.8F | 301 kcal / 18.1P / 36.1C / 10.8F | ✅ |

**Day total on screen:** calo 2696 vs 2759 (-2.3%) / prot 144.5 vs 144 (+0.3%) / carb 378.1 vs 372 (+1.6%) / fats 78.4 vs 77 (+1.8%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 breakfast: “Protein-Packed Blueberry Oat Pancakes with Almond Butter” → “Whole Wheat Toast with Scrambled Eggs and Berries” (2s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Whole Wheat Toast with Scrambled Eggs and Berries | 220g Whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 543 kcal<br>6g Butter → *butter* (717/0.9/0.1/81) = 43 kcal<br>90g Eggs → *eggs* (155/13/1.1/11) = 140 kcal<br>190g Mixed berries → *mixed berries* (43/1/10/0.3) = 82 kcal<br>8g Honey → *honey* (304/0.3/82/0) = 24 kcal | 832 kcal / 35.7P / 116.8C / 22.9F | 832 kcal / 35.7P / 116.8C / 22.9F | ✅ |
| **lunch** — Teriyaki Salmon Bowl with Brown Rice and Roasted Vegetables | 70g Salmon → *salmon* (206/22/0/12.4) = 144 kcal<br>295g Brown rice → *brown rice* (123/2.7/25.6/1) = 363 kcal<br>125g Broccoli → *broccoli* (34/2.8/7/0.4) = 42 kcal<br>105g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 33 kcal<br>70g Edamame → *edamame* (121/11/8/5) = 85 kcal<br>30g Teriyaki sauce → *teriyaki sauce* (89/3.5/17/0) = 27 kcal<br>4g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 23 kcal<br>5g Olive oil → *olive oil* (884/0/0/100) = 44 kcal | 761 kcal / 37.5P / 102.2C / 23.0F | 761 kcal / 37.5P / 102.2C / 23.0F | ✅ |
| **dinner** — Lean Beef Bolognese with Whole Wheat Pasta and Garden Salad | 90g Beef mince 95/5 → *beef mince 95/5* (171/26.5/0/6.9) = 154 kcal<br>235g Whole wheat pasta → *whole wheat pasta* (149/6/30/1.1) = 350 kcal<br>155g Marinara sauce → *marinara sauce* (50/1.5/8/1.5) = 78 kcal<br>95g Canned tomatoes → *canned tomatoes* (32/1.6/7.3/0.3) = 30 kcal<br>115g Zucchini → *zucchini* (17/1.2/3.1/0.3) = 20 kcal<br>80g Carrot → *carrot* (41/0.9/10/0.2) = 33 kcal<br>75g Mixed greens → *mixed greens* (20/2/3.5/0.3) = 15 kcal<br>60g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 11 kcal<br>9g Olive oil → *olive oil* (884/0/0/100) = 80 kcal<br>11g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 47 kcal | 818 kcal / 50.1P / 106.7C / 24.4F | 818 kcal / 50.1P / 106.7C / 24.4F | ✅ |
| **snack** — Greek Yogurt Parfait with Granola and Mixed Berries | 115g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 84 kcal<br>35g Granola → *granola* (471/10/64/20) = 165 kcal<br>100g Mixed berries → *mixed berries* (43/1/10/0.3) = 43 kcal<br>13g Honey → *honey* (304/0.3/82/0) = 40 kcal | 332 kcal / 16.0P / 47.6C / 9.5F | 332 kcal / 16.0P / 47.6C / 9.5F | ✅ |

**Day total on screen:** calo 2743 vs 2759 (-0.6%) / prot 139.3 vs 144 (-3.3%) / carb 373.3 vs 372 (+0.3%) / fats 79.8 vs 77 (+3.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## high_protein
Plan **Elite High-Protein Performance Plan** (`caafe9d5-08d9-42ed-aa73-5c001698c9a4`), generated in 32s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Blueberry Oat Bowl | 75g Rolled oats → *rolled oats* (389/17/66/7) = 292 kcal<br>18g Whey protein → *whey protein* (400/80/10/3.3) = 72 kcal<br>140g Blueberry → *blueberry* (57/0.7/14/0.3) = 80 kcal<br>105g Banana → *banana* (89/1.1/23/0.3) = 93 kcal<br>13g Almond butter → *almond butter* (614/21/19/56) = 80 kcal<br>175g Skim milk → *skim milk* (34/3.4/5/0.1) = 60 kcal<br>14g Honey → *honey* (304/0.3/82/0) = 43 kcal | 720 kcal / 38.1P / 117.9C / 14.0F | 720 kcal / 38.1P / 117.9C / 14.0F | ✅ |
| **lunch** — Grilled Chicken & Sweet Potato Power Bowl | 90g Chicken breast → *chicken breast* (165/31/0/3.6) = 148 kcal<br>335g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 288 kcal<br>120g Broccoli → *broccoli* (34/2.8/7/0.4) = 41 kcal<br>18g Olive oil → *olive oil* (884/0/0/100) = 159 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>10g Lime juice → *lime juice* (25/0.4/8/0.1) = 2 kcal | 718 kcal / 37.7P / 80.7C / 29.5F | 718 kcal / 37.7P / 80.7C / 29.5F | ✅ |
| **dinner** — Lean Beef Stir-Fry with Jasmine Rice | 120g Beef mince 95/5 → *beef mince 95/5* (171/26.5/0/6.9) = 205 kcal<br>370g White rice → *white rice* (130/2.7/28/0.3) = 481 kcal<br>120g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 37 kcal<br>95g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 40 kcal<br>90g Broccoli → *broccoli* (34/2.8/7/0.4) = 31 kcal<br>20g Soy sauce → *soy sauce* (53/8/5/0) = 11 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal<br>6g Ginger → *ginger* (80/1.8/18/0.8) = 5 kcal<br>16g Olive oil → *olive oil* (884/0/0/100) = 141 kcal | 963 kcal / 50.4P / 129.0C / 26.4F | 963 kcal / 50.4P / 129.0C / 26.4F | ✅ |
| **snack** — Greek Yogurt Berry Protein Parfait | 145g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 86 kcal<br>95g Strawberry → *strawberry* (32/0.7/8/0.3) = 30 kcal<br>75g Banana → *banana* (89/1.1/23/0.3) = 67 kcal<br>19g Honey → *honey* (304/0.3/82/0) = 58 kcal<br>12g Almonds → *almonds* (579/21/22/50) = 69 kcal | 310 kcal / 18.6P / 48.8C / 7.1F | 310 kcal / 18.6P / 48.8C / 7.1F | ✅ |

**Day total on screen:** calo 2711 vs 2759 (-1.7%) / prot 144.8 vs 144 (+0.6%) / carb 376.4 vs 372 (+1.2%) / fats 77 vs 77 (+0.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Egg White Veggie Scramble with Toast | 125g Egg white → *egg white* (52/11/0.7/0.2) = 65 kcal<br>35g Whole eggs → *whole eggs* (155/13/1.1/11) = 54 kcal<br>120g Whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 296 kcal<br>55g Spinach → *spinach* (23/2.9/3.6/0.4) = 13 kcal<br>80g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 14 kcal<br>55g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 12 kcal<br>55g Avocado → *avocado* (160/2/9/15) = 88 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>190g Orange → *orange* (47/0.9/12/0.1) = 89 kcal | 702 kcal / 37.1P / 85.2C / 25.1F | 702 kcal / 37.1P / 85.2C / 25.1F | ✅ |
| **lunch** — Seared Tuna Steak with Quinoa Medley | 90g Tuna steak → *tuna steak* (130/29/0/0.6) = 117 kcal<br>330g Quinoa → *quinoa* (120/4.4/21/1.9) = 396 kcal<br>130g Asparagus → *asparagus* (20/2.2/4/0.1) = 26 kcal<br>100g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 18 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>11g Olive oil → *olive oil* (884/0/0/100) = 97 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal<br>155g Mango → *mango* (60/0.8/15/0.4) = 93 kcal | 759 kcal / 46.1P / 104.7C / 18.7F | 759 kcal / 46.1P / 104.7C / 18.7F | ✅ |
| **dinner** — Turkey Meatballs with Basmati Rice & Roasted Vegetables | 100g Turkey mince → *turkey mince* (203/27/0/11.5) = 203 kcal<br>400g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 484 kcal<br>145g Zucchini noodles → *zucchini noodles* (17/1.2/3.1/0.3) = 25 kcal<br>135g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 42 kcal<br>125g Eggplant → *eggplant* (25/1/6/0.2) = 31 kcal<br>105g Marinara sauce → *marinara sauce* (50/1.5/8/1.5) = 52 kcal<br>8g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 34 kcal<br>9g Olive oil → *olive oil* (884/0/0/100) = 80 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal | 961 kcal / 50.3P / 131.9C / 27.0F | 961 kcal / 50.3P / 131.9C / 27.0F | ✅ |
| **snack** — Cottage Cheese Apple Crunch | 90g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 76 kcal<br>185g Apple → *apple* (52/0.3/14/0.2) = 96 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal<br>24g Honey → *honey* (304/0.3/82/0) = 73 kcal<br>7g Walnuts → *walnuts* (654/15/14/65) = 46 kcal | 296 kcal / 11.8P / 51.8C / 7.2F | 296 kcal / 11.8P / 51.8C / 7.2F | ✅ |

**Day total on screen:** calo 2718 vs 2759 (-1.5%) / prot 145.3 vs 144 (+0.9%) / carb 373.6 vs 372 (+0.4%) / fats 78 vs 77 (+1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein Banana Pancakes with Berries | 60g Rolled oats → *rolled oats* (389/17/66/7) = 233 kcal<br>80g Egg white → *egg white* (52/11/0.7/0.2) = 42 kcal<br>45g Whole eggs → *whole eggs* (155/13/1.1/11) = 70 kcal<br>140g Banana → *banana* (89/1.1/23/0.3) = 125 kcal<br>12g Whey protein → *whey protein* (400/80/10/3.3) = 48 kcal<br>120g Mixed berries → *mixed berries* (43/1/10/0.3) = 52 kcal<br>60g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 35 kcal<br>30g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 78 kcal<br>8g Coconut oil → *coconut oil* (862/0/0/100) = 69 kcal | 752 kcal / 43.2P / 108.6C / 18.8F | 752 kcal / 43.2P / 108.6C / 18.8F | ✅ |
| **lunch** — Grilled Salmon with Herb Rice & Green Beans | 80g Salmon → *salmon* (206/22/0/12.4) = 165 kcal<br>325g Brown rice → *brown rice* (123/2.7/25.6/1) = 400 kcal<br>160g Green beans → *green beans* (31/1.8/7/0.1) = 50 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>12g Olive oil → *olive oil* (884/0/0/100) = 106 kcal<br>3g Dill → *dill* (43/3.5/7/1.1) = 1 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal<br>130g Orange → *orange* (47/0.9/12/0.1) = 61 kcal | 795 kcal / 31.1P / 113.3C / 25.4F | 795 kcal / 31.1P / 113.3C / 25.4F | ✅ |
| **dinner** — Lean Sirloin Steak with Loaded Baked Potato | 100g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 212 kcal<br>400g Potato → *potato* (77/2/17/0.1) = 308 kcal<br>50g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 30 kcal<br>120g Broccoli → *broccoli* (34/2.8/7/0.4) = 41 kcal<br>100g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 43 kcal<br>16g Olive oil → *olive oil* (884/0/0/100) = 141 kcal<br>5g Garlic → *garlic* (149/6/33/0.5) = 7 kcal<br>105g Apple → *apple* (52/0.3/14/0.2) = 55 kcal | 837 kcal / 47.4P / 103.8C / 28.2F | 837 kcal / 47.4P / 103.8C / 28.2F | ✅ |
| **snack** — Tropical Protein Smoothie | 15g Whey protein → *whey protein* (400/80/10/3.3) = 60 kcal<br>100g Banana → *banana* (89/1.1/23/0.3) = 89 kcal<br>80g Mango → *mango* (60/0.8/15/0.4) = 48 kcal<br>60g Pineapple → *pineapple* (50/0.5/13/0.1) = 30 kcal<br>60g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 35 kcal<br>190g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 32 kcal<br>5g Chia seeds → *chia seeds* (486/17/42/31) = 24 kcal | 318 kcal / 22.0P / 51.5C / 5.1F | 318 kcal / 22.0P / 51.5C / 5.1F | ✅ |

**Day total on screen:** calo 2702 vs 2759 (-2.1%) / prot 143.7 vs 144 (-0.2%) / carb 377.2 vs 372 (+1.4%) / fats 77.5 vs 77 (+0.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 lunch: “Grilled Chicken & Sweet Potato Power Bowl” → “Spiced Turkey & Quinoa Buddha Bowl” (3s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Blueberry Oat Bowl | 75g Rolled oats → *rolled oats* (389/17/66/7) = 292 kcal<br>18g Whey protein → *whey protein* (400/80/10/3.3) = 72 kcal<br>140g Blueberry → *blueberry* (57/0.7/14/0.3) = 80 kcal<br>105g Banana → *banana* (89/1.1/23/0.3) = 93 kcal<br>13g Almond butter → *almond butter* (614/21/19/56) = 80 kcal<br>175g Skim milk → *skim milk* (34/3.4/5/0.1) = 60 kcal<br>14g Honey → *honey* (304/0.3/82/0) = 43 kcal | 720 kcal / 38.1P / 117.9C / 14.0F | 720 kcal / 38.1P / 117.9C / 14.0F | ✅ |
| **lunch** — Spiced Turkey & Quinoa Buddha Bowl | 90g Turkey breast → *turkey breast* (135/30/0/1) = 122 kcal<br>110g Quinoa → *quinoa* (120/4.4/21/1.9) = 132 kcal<br>225g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 194 kcal<br>55g Spinach → *spinach* (23/2.9/3.6/0.4) = 13 kcal<br>100g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 31 kcal<br>25g Olive oil → *olive oil* (884/0/0/100) = 221 kcal<br>2g Cumin → *cumin* (375/17.8/44/22) = 8 kcal<br>15g Lime juice → *lime juice* (25/0.4/8/0.1) = 4 kcal | 725 kcal / 38.5P / 78.2C / 29.1F | 725 kcal / 38.5P / 78.2C / 29.1F | ✅ |
| **dinner** — Lean Beef Stir-Fry with Jasmine Rice | 120g Beef mince 95/5 → *beef mince 95/5* (171/26.5/0/6.9) = 205 kcal<br>370g White rice → *white rice* (130/2.7/28/0.3) = 481 kcal<br>120g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 37 kcal<br>95g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 40 kcal<br>90g Broccoli → *broccoli* (34/2.8/7/0.4) = 31 kcal<br>20g Soy sauce → *soy sauce* (53/8/5/0) = 11 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal<br>6g Ginger → *ginger* (80/1.8/18/0.8) = 5 kcal<br>16g Olive oil → *olive oil* (884/0/0/100) = 141 kcal | 963 kcal / 50.4P / 129.0C / 26.4F | 963 kcal / 50.4P / 129.0C / 26.4F | ✅ |
| **snack** — Greek Yogurt Berry Protein Parfait | 145g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 86 kcal<br>95g Strawberry → *strawberry* (32/0.7/8/0.3) = 30 kcal<br>75g Banana → *banana* (89/1.1/23/0.3) = 67 kcal<br>19g Honey → *honey* (304/0.3/82/0) = 58 kcal<br>12g Almonds → *almonds* (579/21/22/50) = 69 kcal | 310 kcal / 18.6P / 48.8C / 7.1F | 310 kcal / 18.6P / 48.8C / 7.1F | ✅ |

**Day total on screen:** calo 2718 vs 2759 (-1.5%) / prot 145.6 vs 144 (+1.1%) / carb 373.9 vs 372 (+0.5%) / fats 76.6 vs 77 (-0.5%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## vegetarian
Plan **Elite Vegetarian Performance Plan** (`7f704d40-9b16-43c4-83b4-dcb53839f2e5`), generated in 36s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Oat Bowl | 90g Rolled oats → *rolled oats* (389/17/66/7) = 350 kcal<br>185g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 109 kcal<br>23g Whey protein → *whey protein* (400/80/10/3.3) = 92 kcal<br>100g Blueberry → *blueberry* (57/0.7/14/0.3) = 57 kcal<br>75g Banana → *banana* (89/1.1/23/0.3) = 67 kcal<br>9g Almond butter → *almond butter* (614/21/19/56) = 55 kcal<br>7g Chia seeds → *chia seeds* (486/17/42/31) = 34 kcal<br>12g Honey → *honey* (304/0.3/82/0) = 36 kcal | 800 kcal / 56.8P / 114.7C / 15.5F | 800 kcal / 56.8P / 114.7C / 15.5F | ✅ |
| **lunch** — Mediterranean Chickpea Quinoa Power Bowl | 225g Quinoa → *quinoa* (120/4.4/21/1.9) = 270 kcal<br>155g Chickpeas → *chickpeas* (164/9/27/2.6) = 254 kcal<br>35g Feta cheese → *feta cheese* (264/14/4/21) = 92 kcal<br>95g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 14 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>30g Red onion → *red onion* (40/1.1/9/0.1) = 12 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>19g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal<br>9g Parsley → *parsley* (36/3/6.3/0.8) = 3 kcal | 762 kcal / 31.9P / 107.0C / 24.2F | 762 kcal / 31.9P / 107.0C / 24.2F | ✅ |
| **dinner** — Tempeh Stir-Fry with Brown Rice | 100g Tempeh → *tempeh* (192/20/8/11) = 192 kcal<br>280g Brown rice → *brown rice* (123/2.7/25.6/1) = 344 kcal<br>110g Broccoli → *broccoli* (34/2.8/7/0.4) = 37 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>100g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 42 kcal<br>80g Carrot → *carrot* (41/0.9/10/0.2) = 33 kcal<br>18g Cashews → *cashews* (553/18/30/44) = 100 kcal<br>4g Sesame oil → *sesame oil* (884/0/0/100) = 35 kcal<br>20g Soy sauce → *soy sauce* (53/8/5/0) = 11 kcal<br>10g Ginger → *ginger* (80/1.8/18/0.8) = 8 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal | 853 kcal / 40.9P / 121.3C / 27.0F | 853 kcal / 40.9P / 121.3C / 27.0F | ✅ |
| **snack** — Apple Almond Protein Plate | 135g Apple → *apple* (52/0.3/14/0.2) = 70 kcal<br>105g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 88 kcal<br>16g Almonds → *almonds* (579/21/22/50) = 93 kcal<br>10g Honey → *honey* (304/0.3/82/0) = 30 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 286 kcal / 15.5P / 36.4C / 10.9F | 286 kcal / 15.5P / 36.4C / 10.9F | ✅ |

**Day total on screen:** calo 2701 vs 2759 (-2.1%) / prot 145.1 vs 144 (+0.8%) / carb 379.4 vs 372 (+2.0%) / fats 77.6 vs 77 (+0.8%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Veggie-Loaded Scramble with Toast | 120g Eggs → *eggs* (155/13/1.1/11) = 186 kcal<br>120g Whole wheat bread → *whole wheat bread* (247/10/41/3.4) = 296 kcal<br>80g Spinach → *spinach* (23/2.9/3.6/0.4) = 18 kcal<br>80g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 18 kcal<br>80g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 14 kcal<br>23g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 93 kcal<br>40g Avocado → *avocado* (160/2/9/15) = 64 kcal<br>95g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 69 kcal | 758 kcal / 49.2P / 66.7C / 33.4F | 758 kcal / 49.2P / 66.7C / 33.4F | ✅ |
| **lunch** — Lentil Sweet Potato Buddha Bowl | 230g Lentils → *lentils* (116/9/20/0.4) = 267 kcal<br>355g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 305 kcal<br>70g Kale → *kale* (49/4.3/9/0.9) = 34 kcal<br>100g Beets → *beets* (43/1.6/10/0.2) = 43 kcal<br>15g Goat cheese → *goat cheese* (364/21.6/0.1/29.8) = 55 kcal<br>7g Pumpkin seeds → *pumpkin seeds* (559/30/11/49) = 39 kcal<br>6g Tahini → *tahini* (595/17/23/54) = 36 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal | 782 kcal / 37.4P / 136.6C / 13.2F | 782 kcal / 37.4P / 136.6C / 13.2F | ✅ |
| **dinner** — Paneer Tikka with Basmati and Vegetables | 55g Paneer → *paneer* (296/19/6/22) = 163 kcal<br>275g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 333 kcal<br>70g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 41 kcal<br>135g Cauliflower → *cauliflower* (25/1.9/5/0.3) = 34 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>85g Red onion → *red onion* (40/1.1/9/0.1) = 34 kcal<br>90g Chickpeas → *chickpeas* (164/9/27/2.6) = 148 kcal<br>3g Curry powder → *curry powder* (325/14.3/56/14) = 10 kcal<br>10g Garlic → *garlic* (149/6/33/0.5) = 15 kcal<br>8g Ginger → *ginger* (80/1.8/18/0.8) = 6 kcal<br>10g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 2 kcal | 825 kcal / 41.2P / 128.4C / 17.4F | 825 kcal / 41.2P / 128.4C / 17.4F | ✅ |
| **snack** — Greek Yogurt Parfait | 120g Greek yogurt 2% → *greek yogurt 2%* (73/10/3.9/1.9) = 88 kcal<br>35g Granola → *granola* (471/10/64/20) = 165 kcal<br>80g Strawberry → *strawberry* (32/0.7/8/0.3) = 26 kcal<br>7g Walnuts → *walnuts* (654/15/14/65) = 46 kcal<br>14g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 36 kcal | 361 kcal / 17.2P / 43.9C / 14.1F | 361 kcal / 17.2P / 43.9C / 14.1F | ✅ |

**Day total on screen:** calo 2726 vs 2759 (-1.2%) / prot 145 vs 144 (+0.7%) / carb 375.6 vs 372 (+1.0%) / fats 78.1 vs 77 (+1.4%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein Pancakes with Berry Compote | 40g Rolled oats → *rolled oats* (389/17/66/7) = 156 kcal<br>60g Eggs → *eggs* (155/13/1.1/11) = 93 kcal<br>60g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 50 kcal<br>14g Whey protein → *whey protein* (400/80/10/3.3) = 56 kcal<br>95g Banana → *banana* (89/1.1/23/0.3) = 85 kcal<br>115g Mixed berries → *mixed berries* (43/1/10/0.3) = 49 kcal<br>70g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 41 kcal<br>8g Almond butter → *almond butter* (614/21/19/56) = 49 kcal<br>22g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 57 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 641 kcal / 43.3P / 84.8C / 16.8F | 641 kcal / 43.3P / 84.8C / 16.8F | ✅ |
| **lunch** — Tofu Burrito Bowl | 100g Extra firm tofu → *extra firm tofu* (144/17/3/8) = 144 kcal<br>240g Brown rice → *brown rice* (123/2.7/25.6/1) = 295 kcal<br>155g Black beans → *black beans* (132/9/24/0.5) = 205 kcal<br>80g Sweet corn → *sweet corn* (86/3.2/19/1.2) = 69 kcal<br>40g Avocado → *avocado* (160/2/9/15) = 64 kcal<br>75g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 14 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>55g Romaine lettuce → *romaine lettuce* (17/1.2/3.3/0.3) = 9 kcal<br>55g Salsa → *salsa* (36/2/8/0.2) = 20 kcal<br>15g Lime juice → *lime juice* (25/0.4/8/0.1) = 4 kcal<br>5g Olive oil → *olive oil* (884/0/0/100) = 44 kcal<br>3g Cumin → *cumin* (375/17.8/44/22) = 11 kcal | 904 kcal / 44.8P / 136.8C / 24.6F | 904 kcal / 44.8P / 136.8C / 24.6F | ✅ |
| **dinner** — Eggplant Parmesan with Whole Wheat Pasta | 200g Whole wheat pasta → *whole wheat pasta* (149/6/30/1.1) = 298 kcal<br>205g Eggplant → *eggplant* (25/1/6/0.2) = 51 kcal<br>25g Eggs → *eggs* (155/13/1.1/11) = 39 kcal<br>40g Mozzarella cheese → *mozzarella cheese* (280/28/3/17) = 112 kcal<br>15g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 65 kcal<br>160g Marinara sauce → *marinara sauce* (50/1.5/8/1.5) = 80 kcal<br>35g Chickpea flour → *chickpea flour* (387/22/58/6) = 135 kcal<br>80g Spinach → *spinach* (23/2.9/3.6/0.4) = 18 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal<br>9g Basil → *basil* (23/3.2/2.7/0.6) = 2 kcal | 884 kcal / 47.3P / 113.6C / 29.4F | 884 kcal / 47.3P / 113.6C / 29.4F | ✅ |
| **snack** — Hummus Veggie Plate | 50g Hummus → *hummus* (166/8/14/10) = 83 kcal<br>40g Whole wheat pita → *whole wheat pita* (266/9.8/55/2.6) = 106 kcal<br>75g Carrot → *carrot* (41/0.9/10/0.2) = 31 kcal<br>75g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 11 kcal<br>55g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 10 kcal<br>17g Olives → *olives* (115/0.8/6.3/10.7) = 20 kcal | 261 kcal / 9.7P / 42.4C / 8.2F | 261 kcal / 9.7P / 42.4C / 8.2F | ✅ |

**Day total on screen:** calo 2690 vs 2759 (-2.5%) / prot 145.1 vs 144 (+0.8%) / carb 377.6 vs 372 (+1.5%) / fats 79 vs 77 (+2.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 dinner: “Tempeh Stir-Fry with Brown Rice” → “Chickpea Curry with Basmati Rice” (3s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Oat Bowl | 90g Rolled oats → *rolled oats* (389/17/66/7) = 350 kcal<br>185g Greek yogurt 0% → *greek yogurt 0%* (59/10/4/0.4) = 109 kcal<br>23g Whey protein → *whey protein* (400/80/10/3.3) = 92 kcal<br>100g Blueberry → *blueberry* (57/0.7/14/0.3) = 57 kcal<br>75g Banana → *banana* (89/1.1/23/0.3) = 67 kcal<br>9g Almond butter → *almond butter* (614/21/19/56) = 55 kcal<br>7g Chia seeds → *chia seeds* (486/17/42/31) = 34 kcal<br>12g Honey → *honey* (304/0.3/82/0) = 36 kcal | 800 kcal / 56.8P / 114.7C / 15.5F | 800 kcal / 56.8P / 114.7C / 15.5F | ✅ |
| **lunch** — Mediterranean Chickpea Quinoa Power Bowl | 225g Quinoa → *quinoa* (120/4.4/21/1.9) = 270 kcal<br>155g Chickpeas → *chickpeas* (164/9/27/2.6) = 254 kcal<br>35g Feta cheese → *feta cheese* (264/14/4/21) = 92 kcal<br>95g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 14 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>30g Red onion → *red onion* (40/1.1/9/0.1) = 12 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>19g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal<br>9g Parsley → *parsley* (36/3/6.3/0.8) = 3 kcal | 762 kcal / 31.9P / 107.0C / 24.2F | 762 kcal / 31.9P / 107.0C / 24.2F | ✅ |
| **dinner** — Chickpea Curry with Basmati Rice | 270g Chickpeas → *chickpeas* (164/9/27/2.6) = 443 kcal<br>82g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 99 kcal<br>60g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 138 kcal<br>60g Onion → *onion* (40/1.1/9/0.1) = 24 kcal<br>13g Garlic → *garlic* (149/6/33/0.5) = 19 kcal<br>6g Ginger → *ginger* (80/1.8/18/0.8) = 5 kcal<br>4g Curry powder → *curry powder* (325/14.3/56/14) = 13 kcal<br>110g Canned tomatoes → *canned tomatoes* (32/1.6/7.3/0.3) = 35 kcal<br>110g Spinach → *spinach* (23/2.9/3.6/0.4) = 25 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>110g Vegetable broth → *vegetable broth* (6/0.2/1/0.2) = 7 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 861 kcal / 36.0P / 123.0C / 29.3F | 861 kcal / 36.0P / 123.0C / 29.3F | ✅ |
| **snack** — Apple Almond Protein Plate | 135g Apple → *apple* (52/0.3/14/0.2) = 70 kcal<br>105g Cottage cheese → *cottage cheese* (84/11/4/2.5) = 88 kcal<br>16g Almonds → *almonds* (579/21/22/50) = 93 kcal<br>10g Honey → *honey* (304/0.3/82/0) = 30 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 286 kcal / 15.5P / 36.4C / 10.9F | 286 kcal / 15.5P / 36.4C / 10.9F | ✅ |

**Day total on screen:** calo 2709 vs 2759 (-1.8%) / prot 140.2 vs 144 (-2.6%) / carb 381.1 vs 372 (+2.4%) / fats 79.9 vs 77 (+3.8%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## vegan
Plan **Elite Vegan Performance Plan** (`98e71f8b-e99d-443e-abd6-bb6e9a59708b`), generated in 44s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Oat Bowl | 65g Rolled oats → *rolled oats* (389/17/66/7) = 253 kcal<br>15g Pea protein powder → *pea protein powder* (380/72/8/5) = 57 kcal<br>12g Almond butter → *almond butter* (614/21/19/56) = 74 kcal<br>115g Banana → *banana* (89/1.1/23/0.3) = 102 kcal<br>80g Blueberry → *blueberry* (57/0.7/14/0.3) = 46 kcal<br>230g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 39 kcal<br>9g Chia seeds → *chia seeds* (486/17/42/31) = 44 kcal<br>17g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 44 kcal | 659 kcal / 29.2P / 102.4C / 17.8F | 659 kcal / 29.2P / 102.4C / 17.8F | ✅ |
| **lunch** — Mediterranean Tempeh Power Bowl | 100g Tempeh → *tempeh* (192/20/8/11) = 192 kcal<br>230g Quinoa → *quinoa* (120/4.4/21/1.9) = 276 kcal<br>100g Chickpeas → *chickpeas* (164/9/27/2.6) = 164 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>75g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 11 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>50g Spinach → *spinach* (23/2.9/3.6/0.4) = 12 kcal<br>13g Tahini → *tahini* (595/17/23/54) = 77 kcal<br>14g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal<br>5g Garlic → *garlic* (149/6/33/0.5) = 7 kcal | 819 kcal / 45.3P / 102.0C / 29.7F | 819 kcal / 45.3P / 102.0C / 29.7F | ✅ |
| **dinner** — Seitan Stir-Fry with Brown Rice | 110g Seitan → *seitan* (166/25/14/2) = 183 kcal<br>315g Brown rice → *brown rice* (123/2.7/25.6/1) = 387 kcal<br>100g Broccoli → *broccoli* (34/2.8/7/0.4) = 34 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>60g Shelled edamame → *shelled edamame* (121/11/8/5) = 73 kcal<br>75g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 32 kcal<br>13g Cashews → *cashews* (553/18/30/44) = 72 kcal<br>5g Sesame oil → *sesame oil* (884/0/0/100) = 44 kcal<br>19g Soy sauce → *soy sauce* (53/8/5/0) = 10 kcal<br>10g Ginger → *ginger* (80/1.8/18/0.8) = 8 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal | 892 kcal / 53.1P / 129.9C / 20.1F | 892 kcal / 53.1P / 129.9C / 20.1F | ✅ |
| **snack** — Chocolate Peanut Protein Smoothie | 15g Pea protein powder → *pea protein powder* (380/72/8/5) = 57 kcal<br>95g Banana → *banana* (89/1.1/23/0.3) = 85 kcal<br>8g Peanut butter → *peanut butter* (588/25/20/50) = 47 kcal<br>4g Cocoa powder → *cocoa powder* (228/20/28/14) = 9 kcal<br>215g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 37 kcal<br>19g Dates → *dates* (282/2.5/75/0.4) = 54 kcal<br>4g Flax seeds → *flax seeds* (534/18/29/42) = 21 kcal | 310 kcal / 17.1P / 44.1C / 9.9F | 310 kcal / 17.1P / 44.1C / 9.9F | ✅ |

**Day total on screen:** calo 2680 vs 2759 (-2.9%) / prot 144.7 vs 144 (+0.5%) / carb 378.4 vs 372 (+1.7%) / fats 77.5 vs 77 (+0.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Tofu Scramble Breakfast Burrito | 115g Extra firm tofu → *extra firm tofu* (144/17/3/8) = 166 kcal<br>40g Whole wheat wrap → *whole wheat wrap* (310/8/52/8) = 124 kcal<br>85g Black beans → *black beans* (132/9/24/0.5) = 112 kcal<br>30g Avocado → *avocado* (160/2/9/15) = 48 kcal<br>20g Spinach → *spinach* (23/2.9/3.6/0.4) = 5 kcal<br>60g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 11 kcal<br>50g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 16 kcal<br>9g Yeast flakes → *yeast flakes* (355/50/35/7) = 32 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal<br>2g Turmeric → *turmeric* (312/9.7/67/3.3) = 6 kcal<br>35g Salsa → *salsa* (36/2/8/0.2) = 13 kcal | 568 kcal / 37.9P / 60.5C / 22.4F | 568 kcal / 37.9P / 60.5C / 22.4F | ✅ |
| **lunch** — Lentil Bolognese with Whole Wheat Pasta | 285g Lentils → *lentils* (116/9/20/0.4) = 331 kcal<br>175g Whole wheat pasta → *whole wheat pasta* (149/6/30/1.1) = 261 kcal<br>140g Canned tomatoes → *canned tomatoes* (32/1.6/7.3/0.3) = 45 kcal<br>95g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 21 kcal<br>70g Carrot → *carrot* (41/0.9/10/0.2) = 29 kcal<br>95g Zucchini noodles → *zucchini noodles* (17/1.2/3.1/0.3) = 16 kcal<br>10g Walnuts → *walnuts* (654/15/14/65) = 65 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal<br>4g Basil → *basil* (23/3.2/2.7/0.6) = 1 kcal<br>12g Yeast flakes → *yeast flakes* (355/50/35/7) = 43 kcal | 877 kcal / 51.1P / 141.0C / 17.4F | 877 kcal / 51.1P / 141.0C / 17.4F | ✅ |
| **dinner** — BBQ Tempeh with Sweet Potato and Greens | 110g Tempeh → *tempeh* (192/20/8/11) = 211 kcal<br>245g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 211 kcal<br>140g Black beans → *black beans* (132/9/24/0.5) = 185 kcal<br>55g Kale → *kale* (49/4.3/9/0.9) = 27 kcal<br>40g Corn tortilla → *corn tortilla* (218/5.7/44.6/2.9) = 87 kcal<br>40g Bbq sauce → *bbq sauce* (172/0.8/41/0.6) = 69 kcal<br>10g Tahini → *tahini* (595/17/23/54) = 60 kcal<br>5g Olive oil → *olive oil* (884/0/0/100) = 44 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal<br>2g Smoked paprika → *smoked paprika* (282/14/54/13) = 6 kcal | 912 kcal / 46.0P / 136.6C / 25.6F | 912 kcal / 46.0P / 136.6C / 25.6F | ✅ |
| **snack** — Apple Almond Energy Bites | 65g Apple → *apple* (52/0.3/14/0.2) = 34 kcal<br>12g Almond butter → *almond butter* (614/21/19/56) = 74 kcal<br>25g Rolled oats → *rolled oats* (389/17/66/7) = 97 kcal<br>8g Hemp seed → *hemp seed* (553/32/9/49) = 44 kcal<br>14g Raisins → *raisins* (299/3.1/79/0.5) = 42 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 296 kcal / 10.0P / 41.3C / 12.6F | 296 kcal / 10.0P / 41.3C / 12.6F | ✅ |

**Day total on screen:** calo 2653 vs 2759 (-3.8%) / prot 145 vs 144 (+0.7%) / carb 379.4 vs 372 (+2.0%) / fats 78 vs 77 (+1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Tropical Protein Pancakes | 105g Chickpea flour → *chickpea flour* (387/22/58/6) = 406 kcal<br>30g Pea protein powder → *pea protein powder* (380/72/8/5) = 114 kcal<br>105g Banana → *banana* (89/1.1/23/0.3) = 93 kcal<br>80g Mango → *mango* (60/0.8/15/0.4) = 48 kcal<br>70g Coconut yogurt → *coconut yogurt* (100/0.7/6/9) = 70 kcal<br>11g Almond butter → *almond butter* (614/21/19/56) = 68 kcal<br>145g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 25 kcal<br>1g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 7 kcal<br>21g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 55 kcal | 886 kcal / 50.3P / 122.1C / 23.1F | 886 kcal / 50.3P / 122.1C / 23.1F | ✅ |
| **lunch** — Asian Edamame Buddha Bowl | 175g Shelled edamame → *shelled edamame* (121/11/8/5) = 212 kcal<br>45g Extra firm tofu → *extra firm tofu* (144/17/3/8) = 65 kcal<br>210g Brown rice → *brown rice* (123/2.7/25.6/1) = 258 kcal<br>95g Bok choy → *bok choy* (13/1.5/2/0.2) = 12 kcal<br>80g Carrot → *carrot* (41/0.9/10/0.2) = 33 kcal<br>60g Red cabbage → *cabbage* (25/1.3/6/0.1) = 15 kcal<br>30g Avocado → *avocado* (160/2/9/15) = 48 kcal<br>8g Peanut butter → *peanut butter* (588/25/20/50) = 47 kcal<br>15g Soy sauce → *soy sauce* (53/8/5/0) = 8 kcal<br>15g Lime juice → *lime juice* (25/0.4/8/0.1) = 4 kcal<br>8g Ginger → *ginger* (80/1.8/18/0.8) = 6 kcal | 708 kcal / 39.5P / 90.4C / 23.6F | 708 kcal / 39.5P / 90.4C / 23.6F | ✅ |
| **dinner** — Spiced Lentil and Vegetable Curry with Basmati Rice | 190g Lentils → *lentils* (116/9/20/0.4) = 220 kcal<br>200g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 242 kcal<br>60g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 138 kcal<br>105g Onion → *onion* (40/1.1/9/0.1) = 42 kcal<br>15g Garlic → *garlic* (149/6/33/0.5) = 22 kcal<br>12g Ginger → *ginger* (80/1.8/18/0.8) = 10 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>75g Spinach → *spinach* (23/2.9/3.6/0.4) = 17 kcal<br>2g Curry powder → *curry powder* (325/14.3/56/14) = 6 kcal<br>3g Turmeric → *turmeric* (312/9.7/67/3.3) = 9 kcal<br>195g Vegetable broth → *vegetable broth* (6/0.2/1/0.2) = 12 kcal<br>15g Lime juice → *lime juice* (25/0.4/8/0.1) = 4 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 761 kcal / 32.3P / 124.8C / 17.7F | 761 kcal / 32.3P / 124.8C / 17.7F | ✅ |
| **snack** — Trail Mix Protein Bar | 22g Pea protein powder → *pea protein powder* (380/72/8/5) = 84 kcal<br>7g Almonds → *almonds* (579/21/22/50) = 41 kcal<br>1g Walnuts → *walnuts* (654/15/14/65) = 7 kcal<br>40g Dates → *dates* (282/2.5/75/0.4) = 113 kcal<br>10g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 60 kcal<br>5g Pumpkin seeds → *pumpkin seeds* (559/30/11/49) = 28 kcal<br>2g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 13 kcal | 346 kcal / 20.8P / 38.8C / 13.5F | 346 kcal / 20.8P / 38.8C / 13.5F | ✅ |

**Day total on screen:** calo 2701 vs 2759 (-2.1%) / prot 142.9 vs 144 (-0.8%) / carb 376.1 vs 372 (+1.1%) / fats 77.9 vs 77 (+1.2%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 snack: “Chocolate Peanut Protein Smoothie” → “Chickpea Flour Energy Bites with Dates” (3s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Oat Bowl | 65g Rolled oats → *rolled oats* (389/17/66/7) = 253 kcal<br>15g Pea protein powder → *pea protein powder* (380/72/8/5) = 57 kcal<br>12g Almond butter → *almond butter* (614/21/19/56) = 74 kcal<br>115g Banana → *banana* (89/1.1/23/0.3) = 102 kcal<br>80g Blueberry → *blueberry* (57/0.7/14/0.3) = 46 kcal<br>230g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 39 kcal<br>9g Chia seeds → *chia seeds* (486/17/42/31) = 44 kcal<br>17g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 44 kcal | 659 kcal / 29.2P / 102.4C / 17.8F | 659 kcal / 29.2P / 102.4C / 17.8F | ✅ |
| **lunch** — Mediterranean Tempeh Power Bowl | 100g Tempeh → *tempeh* (192/20/8/11) = 192 kcal<br>230g Quinoa → *quinoa* (120/4.4/21/1.9) = 276 kcal<br>100g Chickpeas → *chickpeas* (164/9/27/2.6) = 164 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>75g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 11 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>50g Spinach → *spinach* (23/2.9/3.6/0.4) = 12 kcal<br>13g Tahini → *tahini* (595/17/23/54) = 77 kcal<br>14g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal<br>5g Garlic → *garlic* (149/6/33/0.5) = 7 kcal | 819 kcal / 45.3P / 102.0C / 29.7F | 819 kcal / 45.3P / 102.0C / 29.7F | ✅ |
| **dinner** — Seitan Stir-Fry with Brown Rice | 110g Seitan → *seitan* (166/25/14/2) = 183 kcal<br>315g Brown rice → *brown rice* (123/2.7/25.6/1) = 387 kcal<br>100g Broccoli → *broccoli* (34/2.8/7/0.4) = 34 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>60g Shelled edamame → *shelled edamame* (121/11/8/5) = 73 kcal<br>75g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 32 kcal<br>13g Cashews → *cashews* (553/18/30/44) = 72 kcal<br>5g Sesame oil → *sesame oil* (884/0/0/100) = 44 kcal<br>19g Soy sauce → *soy sauce* (53/8/5/0) = 10 kcal<br>10g Ginger → *ginger* (80/1.8/18/0.8) = 8 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal | 892 kcal / 53.1P / 129.9C / 20.1F | 892 kcal / 53.1P / 129.9C / 20.1F | ✅ |
| **snack** — Chickpea Flour Energy Bites with Dates | 50g Chickpea flour → *chickpea flour* (387/22/58/6) = 194 kcal<br>18g Dates → *dates* (282/2.5/75/0.4) = 51 kcal<br>10g Almond butter → *almond butter* (614/21/19/56) = 61 kcal<br>2g Coconut oil → *coconut oil* (862/0/0/100) = 17 kcal<br>2g Vanilla extract → *vanilla extract* (288/0.1/12.7/0.1) = 6 kcal<br>1g Cinnamon → *cinnamon* (247/4/81/1.2) = 2 kcal | 331 kcal / 13.5P / 45.5C / 10.7F | 331 kcal / 13.5P / 45.5C / 10.7F | ✅ |

**Day total on screen:** calo 2701 vs 2759 (-2.1%) / prot 141.1 vs 144 (-2.0%) / carb 379.8 vs 372 (+2.1%) / fats 78.3 vs 77 (+1.7%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## paleo
Plan **Elite Paleo Performance Plan** (`3c1b55a5-cca1-43c7-bb7e-c2c67aa99a4e`), generated in 59s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Sweet Potato & Egg Skillet with Berries | 400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>87g Eggs → *eggs* (155/13/1.1/11) = 135 kcal<br>264g Blueberry → *blueberry* (57/0.7/14/0.3) = 150 kcal<br>6g Ghee → *ghee* (876/0/0/97) = 53 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal<br>1g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 687 kcal / 19.6P / 119.6C / 16.6F | 687 kcal / 19.6P / 119.6C / 16.6F | ✅ |
| **lunch** — Grilled Chicken & Roasted Butternut Squash Bowl | 190g Chicken breast → *chicken breast* (165/31/0/3.6) = 314 kcal<br>400g Butternut squash → *butternut squash* (45/1/11.7/0.1) = 180 kcal<br>150g Kale → *kale* (49/4.3/9/0.9) = 74 kcal<br>23g Almonds → *almonds* (579/21/22/50) = 133 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>30g Balsamic vinegar → *balsamic vinegar* (88/0.5/17/0) = 26 kcal<br>11g Garlic → *garlic* (149/6/33/0.5) = 16 kcal | 796 kcal / 74.9P / 74.1C / 26.2F | 796 kcal / 74.9P / 74.1C / 26.2F | ✅ |
| **dinner** — Pan-Seared Salmon with Roasted Sweet Potato & Asparagus | 140g Salmon → *salmon* (206/22/0/12.4) = 288 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>400g Asparagus → *asparagus* (20/2.2/4/0.1) = 80 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>24g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 5 kcal<br>3g Garlic powder → *garlic powder* (331/16.6/73/0.7) = 10 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal<br>1g Black pepper → *black pepper* (251/10.4/64/3.3) = 3 kcal | 801 kcal / 46.7P / 100.5C / 26.2F | 801 kcal / 46.7P / 100.5C / 26.2F | ✅ |
| **snack** — Apple Slices with Almond Butter & Berries | 395g Apple → *apple* (52/0.3/14/0.2) = 205 kcal<br>14g Almond butter → *almond butter* (614/21/19/56) = 86 kcal<br>130g Blueberry → *blueberry* (57/0.7/14/0.3) = 74 kcal<br>1g Cinnamon → *cinnamon* (247/4/81/1.2) = 2 kcal | 367 kcal / 5.0P / 77.0C / 9.0F | 367 kcal / 5.0P / 77.0C / 9.0F | ✅ |

**Day total on screen:** calo 2651 vs 2759 (-3.9%) / prot 146.2 vs 144 (+1.5%) / carb 371.2 vs 372 (-0.2%) / fats 78 vs 77 (+1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Paleo Banana Pancakes with Mixed Berries | 125g Eggs → *eggs* (155/13/1.1/11) = 194 kcal<br>265g Banana → *banana* (89/1.1/23/0.3) = 236 kcal<br>20g Almond flour → *almond flour* (571/21/20/50) = 114 kcal<br>170g Mixed berries → *mixed berries* (43/1/10/0.3) = 73 kcal<br>13g Almond butter → *almond butter* (614/21/19/56) = 80 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal<br>3g Vanilla extract → *vanilla extract* (288/0.1/12.7/0.1) = 9 kcal | 711 kcal / 27.8P / 87.8C / 32.4F | 711 kcal / 27.8P / 87.8C / 32.4F | ✅ |
| **lunch** — Beef Sirloin Stir-Fry with Rainbow Vegetables | 105g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 223 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>110g Broccoli → *broccoli* (34/2.8/7/0.4) = 37 kcal<br>110g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 34 kcal<br>85g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 36 kcal<br>21g Coconut aminos → *coconut aminos* (74/2/18/0) = 16 kcal<br>9g Ginger → *ginger* (80/1.8/18/0.8) = 7 kcal<br>7g Garlic → *garlic* (149/6/33/0.5) = 10 kcal | 707 kcal / 42.4P / 108.5C / 12.5F | 707 kcal / 42.4P / 108.5C / 12.5F | ✅ |
| **dinner** — Herb-Crusted Chicken Thighs with Roasted Root Vegetables | 145g Chicken thigh → *chicken thigh* (209/26/0/10.9) = 303 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>165g Carrot → *carrot* (41/0.9/10/0.2) = 68 kcal<br>130g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 56 kcal<br>1g Olive oil → *olive oil* (884/0/0/100) = 9 kcal<br>2g Rosemary → *rosemary* (131/3.3/20.7/5.9) = 3 kcal<br>2g Thyme → *thyme* (101/5.6/24/1.7) = 2 kcal<br>11g Garlic → *garlic* (149/6/33/0.5) = 16 kcal<br>65g Chicken breast → *chicken breast* (165/31/0/3.6) = 107 kcal | 908 kcal / 71.1P / 112.7C / 20.4F | 908 kcal / 71.1P / 112.7C / 20.4F | ✅ |
| **snack** — Tropical Energy Bites | 70g Dates → *dates* (282/2.5/75/0.4) = 197 kcal<br>7g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 46 kcal<br>10g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 72 kcal<br>85g Mango → *mango* (60/0.8/15/0.4) = 51 kcal<br>5g Lime juice → *lime juice* (25/0.4/8/0.1) = 1 kcal | 367 kcal / 3.8P / 68.8C / 12.7F | 367 kcal / 3.8P / 68.8C / 12.7F | ✅ |

**Day total on screen:** calo 2693 vs 2759 (-2.4%) / prot 145.1 vs 144 (+0.8%) / carb 377.8 vs 372 (+1.6%) / fats 78 vs 77 (+1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Chorizo & Sweet Potato Breakfast Skillet | 35g Chorizo → *chorizo* (455/24/1.9/38) = 159 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>46g Eggs → *eggs* (155/13/1.1/11) = 71 kcal<br>115g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 36 kcal<br>60g Spinach → *spinach* (23/2.9/3.6/0.4) = 14 kcal<br>30g Avocado → *avocado* (160/2/9/15) = 48 kcal<br>2g Onion powder → *onion powder* (341/10.4/79/1) = 7 kcal<br>1g Smoked paprika → *smoked paprika* (282/14/54/13) = 3 kcal | 682 kcal / 24.5P / 95.1C / 23.9F | 682 kcal / 24.5P / 95.1C / 23.9F | ✅ |
| **lunch** — Blackened Mahi Mahi with Mango Salsa & Sweet Potato Wedges | 270g Mahi mahi → *mahi mahi* (109/23.7/0/0.9) = 294 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>210g Mango → *mango* (60/0.8/15/0.4) = 126 kcal<br>45g Red onion → *red onion* (40/1.1/9/0.1) = 18 kcal<br>9g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 2 kcal<br>14g Lime juice → *lime juice* (25/0.4/8/0.1) = 4 kcal<br>8g Coconut oil → *coconut oil* (862/0/0/100) = 69 kcal<br>3g Chili powder → *chili powder* (282/13.5/50/14.3) = 8 kcal<br>50g Mixed greens → *mixed greens* (20/2/3.5/0.3) = 10 kcal | 875 kcal / 74.3P / 120.2C / 12.1F | 875 kcal / 74.3P / 120.2C / 12.1F | ✅ |
| **dinner** — Grass-Fed Beef Mince Power Bowl with Cauliflower Rice | 100g Beef mince 90/10 → *beef mince 90/10* (217/26.6/0/11.7) = 217 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>215g Cauliflower rice → *cauliflower rice* (25/1.9/5/0.3) = 54 kcal<br>115g Zucchini noodles → *zucchini noodles* (17/1.2/3.1/0.3) = 20 kcal<br>120g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 22 kcal<br>35g Avocado → *avocado* (160/2/9/15) = 56 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>2g Cumin → *cumin* (375/17.8/44/22) = 8 kcal<br>17g Garlic → *garlic* (149/6/33/0.5) = 25 kcal | 817 kcal / 41.7P / 108.7C / 26.9F | 817 kcal / 41.7P / 108.7C / 26.9F | ✅ |
| **snack** — Berry Coconut Parfait | 75g Coconut yogurt → *coconut yogurt* (100/0.7/6/9) = 75 kcal<br>115g Strawberry → *strawberry* (32/0.7/8/0.3) = 37 kcal<br>60g Raspberries → *raspberries* (52/1.2/12/0.7) = 31 kcal<br>10g Pecans → *pecans* (691/9/14/72) = 69 kcal<br>33g Honey → *honey* (304/0.3/82/0) = 100 kcal<br>5g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 33 kcal | 345 kcal / 3.3P / 50.6C / 17.9F | 345 kcal / 3.3P / 50.6C / 17.9F | ✅ |

**Day total on screen:** calo 2719 vs 2759 (-1.4%) / prot 143.8 vs 144 (-0.1%) / carb 374.6 vs 372 (+0.7%) / fats 80.8 vs 77 (+4.9%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 breakfast: “Sweet Potato & Egg Skillet with Berries” → “Tropical Mango & Prawn Scramble with Sweet Potato Hash” (9s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Tropical Mango & Prawn Scramble with Sweet Potato Hash | 35g Eggs → *eggs* (155/13/1.1/11) = 54 kcal<br>36g Prawn → *prawn* (99/24/0/0.3) = 36 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>280g Mango → *mango* (60/0.8/15/0.4) = 168 kcal<br>11g Coconut oil → *coconut oil* (862/0/0/100) = 95 kcal<br>14g Lime juice → *lime juice* (25/0.4/8/0.1) = 4 kcal<br>7g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 2 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 703 kcal / 21.9P / 123.8C / 16.4F | 703 kcal / 21.9P / 123.8C / 16.4F | ✅ |
| **lunch** — Grilled Chicken & Roasted Butternut Squash Bowl | 190g Chicken breast → *chicken breast* (165/31/0/3.6) = 314 kcal<br>400g Butternut squash → *butternut squash* (45/1/11.7/0.1) = 180 kcal<br>150g Kale → *kale* (49/4.3/9/0.9) = 74 kcal<br>23g Almonds → *almonds* (579/21/22/50) = 133 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>30g Balsamic vinegar → *balsamic vinegar* (88/0.5/17/0) = 26 kcal<br>11g Garlic → *garlic* (149/6/33/0.5) = 16 kcal | 796 kcal / 74.9P / 74.1C / 26.2F | 796 kcal / 74.9P / 74.1C / 26.2F | ✅ |
| **dinner** — Pan-Seared Salmon with Roasted Sweet Potato & Asparagus | 140g Salmon → *salmon* (206/22/0/12.4) = 288 kcal<br>400g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 344 kcal<br>400g Asparagus → *asparagus* (20/2.2/4/0.1) = 80 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>24g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 5 kcal<br>3g Garlic powder → *garlic powder* (331/16.6/73/0.7) = 10 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal<br>1g Black pepper → *black pepper* (251/10.4/64/3.3) = 3 kcal | 801 kcal / 46.7P / 100.5C / 26.2F | 801 kcal / 46.7P / 100.5C / 26.2F | ✅ |
| **snack** — Apple Slices with Almond Butter & Berries | 395g Apple → *apple* (52/0.3/14/0.2) = 205 kcal<br>14g Almond butter → *almond butter* (614/21/19/56) = 86 kcal<br>130g Blueberry → *blueberry* (57/0.7/14/0.3) = 74 kcal<br>1g Cinnamon → *cinnamon* (247/4/81/1.2) = 2 kcal | 367 kcal / 5.0P / 77.0C / 9.0F | 367 kcal / 5.0P / 77.0C / 9.0F | ✅ |

**Day total on screen:** calo 2667 vs 2759 (-3.3%) / prot 148.5 vs 144 (+3.1%) / carb 375.4 vs 372 (+0.9%) / fats 77.8 vs 77 (+1.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## keto
Plan **Elite Keto Performance Plan** (`26e51020-627a-4c8d-bebd-b45cb8d6aa05`), generated in 31s. Targets: 2759 kcal / 162.0P / 30.0C / 221.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Loaded Scrambled Eggs with Bacon & Avocado | 115g Eggs → *eggs* (155/13/1.1/11) = 178 kcal<br>30g Bacon → *bacon* (417/13/1.4/40) = 125 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>10g Butter → *butter* (717/0.9/0.1/81) = 72 kcal<br>15g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 60 kcal<br>40g Spinach → *spinach* (23/2.9/3.6/0.4) = 9 kcal | 524 kcal / 24.9P / 7.8C / 45.4F | 524 kcal / 24.9P / 7.8C / 45.4F | ✅ |
| **lunch** — Pan-Seared Salmon with Creamy Garlic Broccoli | 395g Salmon → *salmon* (206/22/0/12.4) = 814 kcal<br>75g Broccoli → *broccoli* (34/2.8/7/0.4) = 26 kcal<br>30g Heavy cream → *heavy cream* (340/2.8/2.7/36) = 102 kcal<br>18g Butter → *butter* (717/0.9/0.1/81) = 129 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>4g Garlic → *garlic* (149/6/33/0.5) = 6 kcal<br>15g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 65 kcal | 1213 kcal / 95.9P / 7.9C / 87.0F | 1213 kcal / 95.9P / 7.9C / 87.0F | ✅ |
| **dinner** — Ribeye Steak with Buttered Asparagus & Blue Cheese | 110g Ribeye steak → *ribeye steak* (291/24/0/21) = 320 kcal<br>150g Asparagus → *asparagus* (20/2.2/4/0.1) = 30 kcal<br>25g Butter → *butter* (717/0.9/0.1/81) = 179 kcal<br>20g Brie → *brie* (334/20.8/0.5/27.7) = 67 kcal<br>12g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 86 kcal<br>5g Olive oil → *olive oil* (884/0/0/100) = 44 kcal | 726 kcal / 35.1P / 7.8C / 63.1F | 726 kcal / 35.1P / 7.8C / 63.1F | ✅ |
| **snack** — Macadamia Nut Fat Bombs | 15g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 108 kcal<br>25g Cream cheese → *cream cheese* (342/6/4/34) = 86 kcal<br>8g Coconut oil → *coconut oil* (862/0/0/100) = 69 kcal<br>8g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 48 kcal | 311 kcal / 3.3P / 6.5C / 31.3F | 311 kcal / 3.3P / 6.5C / 31.3F | ✅ |

**Day total on screen:** calo 2774 vs 2759 (+0.5%) / prot 159.2 vs 162 (-1.7%) / carb 30 vs 30 (+0.0%) / fats 226.8 vs 221 (+2.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Keto Breakfast Bowl with Sausage & Fried Eggs | 65g Pork sausage → *pork sausage* (325/18.5/1.4/27) = 211 kcal<br>120g Eggs → *eggs* (155/13/1.1/11) = 186 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>16g Butter → *butter* (717/0.9/0.1/81) = 115 kcal<br>30g Gouda → *gouda* (356/25/2.2/27.4) = 107 kcal<br>30g Arugula → *arugula* (25/2.6/3.7/0.7) = 8 kcal | 707 kcal / 37.0P / 8.5C / 59.7F | 707 kcal / 37.0P / 8.5C / 59.7F | ✅ |
| **lunch** — Chicken Thigh Alfredo with Zucchini Noodles | 180g Chicken thigh → *chicken thigh* (209/26/0/10.9) = 376 kcal<br>155g Zucchini noodles → *zucchini noodles* (17/1.2/3.1/0.3) = 26 kcal<br>40g Heavy cream → *heavy cream* (340/2.8/2.7/36) = 136 kcal<br>30g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 129 kcal<br>15g Butter → *butter* (717/0.9/0.1/81) = 108 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>5g Garlic → *garlic* (149/6/33/0.5) = 7 kcal | 853 kcal / 61.6P / 8.8C / 63.4F | 853 kcal / 61.6P / 8.8C / 63.4F | ✅ |
| **dinner** — Beef Brisket with Cauliflower Mash & Herb Butter | 120g Beef brisket → *beef brisket* (291/28/0/19) = 349 kcal<br>175g Cauliflower rice → *cauliflower rice* (25/1.9/5/0.3) = 44 kcal<br>30g Butter → *butter* (717/0.9/0.1/81) = 215 kcal<br>35g Heavy cream → *heavy cream* (340/2.8/2.7/36) = 119 kcal<br>30g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 121 kcal<br>8g Beef tallow → *beef tallow* (902/0/0/100) = 72 kcal<br>3g Rosemary → *rosemary* (131/3.3/20.7/5.9) = 4 kcal | 924 kcal / 45.8P / 10.7C / 78.3F | 924 kcal / 45.8P / 10.7C / 78.3F | ✅ |
| **snack** — Prosciutto-Wrapped Brie with Pecans | 45g Ham → *ham* (145/21/1/6) = 65 kcal<br>35g Brie → *brie* (334/20.8/0.5/27.7) = 117 kcal<br>12g Pecans → *pecans* (691/9/14/72) = 83 kcal<br>4g Olive oil → *olive oil* (884/0/0/100) = 35 kcal | 300 kcal / 17.9P / 2.4C / 25.0F | 300 kcal / 17.9P / 2.4C / 25.0F | ✅ |

**Day total on screen:** calo 2784 vs 2759 (+0.9%) / prot 162.3 vs 162 (+0.2%) / carb 30.4 vs 30 (+1.3%) / fats 226.4 vs 221 (+2.4%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Smoked Salmon & Cream Cheese Plate | 155g Smoked salmon → *smoked salmon* (117/18.3/0/4.3) = 181 kcal<br>65g Cream cheese → *cream cheese* (342/6/4/34) = 222 kcal<br>115g Eggs → *eggs* (155/13/1.1/11) = 178 kcal<br>45g Avocado → *avocado* (160/2/9/15) = 72 kcal<br>16g Butter → *butter* (717/0.9/0.1/81) = 115 kcal<br>45g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 7 kcal<br>9g Capers → *capers* (23/2.4/4.9/0.9) = 2 kcal | 777 kcal / 48.7P / 9.9C / 61.3F | 777 kcal / 48.7P / 9.9C / 61.3F | ✅ |
| **lunch** — Ground Lamb Skillet with Feta & Greens | 155g Ground lamb → *ground lamb* (283/23/0/21) = 439 kcal<br>40g Feta cheese → *feta cheese* (264/14/4/21) = 106 kcal<br>75g Spinach → *spinach* (23/2.9/3.6/0.4) = 17 kcal<br>14g Olive oil → *olive oil* (884/0/0/100) = 124 kcal<br>16g Butter → *butter* (717/0.9/0.1/81) = 115 kcal<br>30g Olives → *olives* (115/0.8/6.3/10.7) = 34 kcal<br>8g Pine nuts → *pine nuts* (673/13.7/13/68.4) = 54 kcal | 889 kcal / 44.8P / 7.2C / 77.0F | 889 kcal / 44.8P / 7.2C / 77.0F | ✅ |
| **dinner** — Duck Breast with Roasted Brussels & Bacon | 225g Duck breast → *duck breast* (201/23.5/0/11.2) = 452 kcal<br>55g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 24 kcal<br>25g Bacon → *bacon* (417/13/1.4/40) = 104 kcal<br>9g Duck fat → *duck fat* (882/0/0/99.8) = 79 kcal<br>13g Butter → *butter* (717/0.9/0.1/81) = 93 kcal<br>30g Goat cheese → *goat cheese* (364/21.6/0.1/29.8) = 109 kcal<br>5g Pecans → *pecans* (691/9/14/72) = 35 kcal | 896 kcal / 65.1P / 6.0C / 67.4F | 896 kcal / 65.1P / 6.0C / 67.4F | ✅ |
| **snack** — Almond Butter Berry Bowl | 10g Almond butter → *almond butter* (614/21/19/56) = 61 kcal<br>12g Coconut cream → *coconut cream* (330/3.6/6.7/34.7) = 40 kcal<br>23g Blackberries → *blackberries* (43/1.4/9.6/0.5) = 10 kcal<br>9g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 65 kcal<br>3g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 20 kcal | 196 kcal / 3.7P / 6.9C / 18.6F | 196 kcal / 3.7P / 6.9C / 18.6F | ✅ |

**Day total on screen:** calo 2758 vs 2759 (-0.0%) / prot 162.3 vs 162 (+0.2%) / carb 30 vs 30 (+0.0%) / fats 224.3 vs 221 (+1.5%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 lunch: “Pan-Seared Salmon with Creamy Garlic Broccoli” → “Seared Tuna Steak with Creamy Avocado & Crispy Bacon” (9s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Loaded Scrambled Eggs with Bacon & Avocado | 115g Eggs → *eggs* (155/13/1.1/11) = 178 kcal<br>30g Bacon → *bacon* (417/13/1.4/40) = 125 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>10g Butter → *butter* (717/0.9/0.1/81) = 72 kcal<br>15g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 60 kcal<br>40g Spinach → *spinach* (23/2.9/3.6/0.4) = 9 kcal | 524 kcal / 24.9P / 7.8C / 45.4F | 524 kcal / 24.9P / 7.8C / 45.4F | ✅ |
| **lunch** — Seared Tuna Steak with Creamy Avocado & Crispy Bacon | 260g Tuna steak → *tuna steak* (130/29/0/0.6) = 338 kcal<br>45g Avocado → *avocado* (160/2/9/15) = 72 kcal<br>165g Bacon → *bacon* (417/13/1.4/40) = 688 kcal<br>18g Heavy cream → *heavy cream* (340/2.8/2.7/36) = 61 kcal<br>6g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 1 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal<br>1g Black pepper → *black pepper* (251/10.4/64/3.3) = 3 kcal<br>24g Arugula → *arugula* (25/2.6/3.7/0.7) = 6 kcal | 1169 kcal / 98.9P / 8.7C / 81.1F | 1169 kcal / 98.9P / 8.7C / 81.1F | ✅ |
| **dinner** — Ribeye Steak with Buttered Asparagus & Blue Cheese | 110g Ribeye steak → *ribeye steak* (291/24/0/21) = 320 kcal<br>150g Asparagus → *asparagus* (20/2.2/4/0.1) = 30 kcal<br>25g Butter → *butter* (717/0.9/0.1/81) = 179 kcal<br>20g Brie → *brie* (334/20.8/0.5/27.7) = 67 kcal<br>12g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 86 kcal<br>5g Olive oil → *olive oil* (884/0/0/100) = 44 kcal | 726 kcal / 35.1P / 7.8C / 63.1F | 726 kcal / 35.1P / 7.8C / 63.1F | ✅ |
| **snack** — Macadamia Nut Fat Bombs | 15g Macadamia nuts → *macadamia nuts* (718/8/14/76) = 108 kcal<br>25g Cream cheese → *cream cheese* (342/6/4/34) = 86 kcal<br>8g Coconut oil → *coconut oil* (862/0/0/100) = 69 kcal<br>8g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 48 kcal | 311 kcal / 3.3P / 6.5C / 31.3F | 311 kcal / 3.3P / 6.5C / 31.3F | ✅ |

**Day total on screen:** calo 2730 vs 2759 (-1.1%) / prot 162.2 vs 162 (+0.1%) / carb 30.8 vs 30 (+2.7%) / fats 220.9 vs 221 (-0.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## carnivore
Plan **Elite Carnivore Performance Plan** (`fffb1d75-dfab-43b1-9496-d8c5729b6183`), generated in 23s. Targets: 2759 kcal / 201.0P / 5.0C / 215.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Ribeye & Eggs with Butter | 90g Ribeye steak → *ribeye steak* (291/24/0/21) = 262 kcal<br>255g Eggs → *eggs* (155/13/1.1/11) = 395 kcal<br>10g Butter → *butter* (717/0.9/0.1/81) = 72 kcal | 729 kcal / 54.8P / 2.8C / 55.0F | 729 kcal / 54.8P / 2.8C / 55.0F | ✅ |
| **lunch** — Grilled Salmon with Cheddar | 290g Salmon → *salmon* (206/22/0/12.4) = 597 kcal<br>95g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 383 kcal<br>12g Butter → *butter* (717/0.9/0.1/81) = 86 kcal | 1066 kcal / 87.7P / 1.2C / 77.0F | 1066 kcal / 87.7P / 1.2C / 77.0F | ✅ |
| **dinner** — Prime Rib with Bone Marrow Butter | 140g Prime rib → *prime rib* (340/22/0/28) = 476 kcal<br>18g Butter → *butter* (717/0.9/0.1/81) = 129 kcal<br>325g Bone broth → *bone broth* (17/3.8/0/0.2) = 55 kcal | 660 kcal / 43.3P / 0.0C / 54.5F | 660 kcal / 43.3P / 0.0C / 54.5F | ✅ |
| **snack** — Bacon & Brie Plate | 50g Bacon → *bacon* (417/13/1.4/40) = 208 kcal<br>35g Brie → *brie* (334/20.8/0.5/27.7) = 117 kcal | 325 kcal / 13.8P / 0.9C / 29.7F | 325 kcal / 13.8P / 0.9C / 29.7F | ✅ |

**Day total on screen:** calo 2780 vs 2759 (+0.8%) / prot 199.6 vs 201 (-0.7%) / carb 4.9 vs 5 (-2.0%) / fats 216.2 vs 215 (+0.6%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Chorizo Scramble with Ghee | 80g Chorizo → *chorizo* (455/24/1.9/38) = 364 kcal<br>110g Eggs → *eggs* (155/13/1.1/11) = 170 kcal<br>14g Ghee → *ghee* (876/0/0/97) = 123 kcal | 657 kcal / 33.5P / 2.7C / 56.1F | 657 kcal / 33.5P / 2.7C / 56.1F | ✅ |
| **lunch** — Lamb Chops with Goat Cheese | 220g Lamb chops → *lamb chops* (258/25/0/17) = 568 kcal<br>40g Goat cheese → *goat cheese* (364/21.6/0.1/29.8) = 146 kcal<br>16g Butter → *butter* (717/0.9/0.1/81) = 115 kcal | 829 kcal / 63.7P / 0.0C / 62.3F | 829 kcal / 63.7P / 0.0C / 62.3F | ✅ |
| **dinner** — Beef Brisket with Tallow | 270g Beef brisket → *beef brisket* (291/28/0/19) = 786 kcal<br>15g Beef tallow → *beef tallow* (902/0/0/100) = 135 kcal<br>30g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 121 kcal | 1042 kcal / 83.1P / 0.4C / 76.2F | 1042 kcal / 83.1P / 0.4C / 76.2F | ✅ |
| **snack** — Smoked Salmon & Cream Cheese Roll-Ups | 95g Smoked salmon → *smoked salmon* (117/18.3/0/4.3) = 111 kcal<br>45g Cream cheese → *cream cheese* (342/6/4/34) = 154 kcal | 265 kcal / 20.1P / 1.8C / 19.4F | 265 kcal / 20.1P / 1.8C / 19.4F | ✅ |

**Day total on screen:** calo 2793 vs 2759 (+1.2%) / prot 200.4 vs 201 (-0.3%) / carb 4.9 vs 5 (-2.0%) / fats 214 vs 215 (-0.5%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Duck Breast & Egg Yolk Bowl | 215g Duck breast → *duck breast* (201/23.5/0/11.2) = 432 kcal<br>40g Egg yolk → *egg yolk* (322/15.9/3.6/26.5) = 129 kcal<br>21g Duck fat → *duck fat* (882/0/0/99.8) = 185 kcal | 746 kcal / 56.9P / 1.4C / 55.7F | 746 kcal / 56.9P / 1.4C / 55.7F | ✅ |
| **lunch** — Mackerel with Parmesan Crust | 220g Mackerel → *mackerel* (262/23.9/0/17.8) = 576 kcal<br>25g Parmesan cheese → *parmesan cheese* (431/38/4/29) = 108 kcal<br>18g Butter → *butter* (717/0.9/0.1/81) = 129 kcal | 813 kcal / 62.3P / 1.0C / 61.0F | 813 kcal / 62.3P / 1.0C / 61.0F | ✅ |
| **dinner** — Sirloin Steak with Pork Belly | 230g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 488 kcal<br>85g Pork belly → *pork belly* (518/9.3/0/53) = 440 kcal<br>19g Ghee → *ghee* (876/0/0/97) = 166 kcal | 1094 kcal / 70.0P / 0.0C / 87.8F | 1094 kcal / 70.0P / 0.0C / 87.8F | ✅ |
| **snack** — Beef Jerky & Aged Gouda | 25g Beef jerky → *beef jerky* (410/33.2/11/25.6) = 102 kcal<br>15g Gouda → *gouda* (356/25/2.2/27.4) = 53 kcal | 155 kcal / 12.1P / 3.1C / 10.5F | 155 kcal / 12.1P / 3.1C / 10.5F | ✅ |

**Day total on screen:** calo 2808 vs 2759 (+1.8%) / prot 201.3 vs 201 (+0.1%) / carb 5.5 vs 5 (+10.0%) / fats 215 vs 215 (+0.0%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 dinner: “Prime Rib with Bone Marrow Butter” → “Pan-Seared Halibut with Gouda & Butter” (2s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Ribeye & Eggs with Butter | 90g Ribeye steak → *ribeye steak* (291/24/0/21) = 262 kcal<br>255g Eggs → *eggs* (155/13/1.1/11) = 395 kcal<br>10g Butter → *butter* (717/0.9/0.1/81) = 72 kcal | 729 kcal / 54.8P / 2.8C / 55.0F | 729 kcal / 54.8P / 2.8C / 55.0F | ✅ |
| **lunch** — Grilled Salmon with Cheddar | 290g Salmon → *salmon* (206/22/0/12.4) = 597 kcal<br>95g Cheddar cheese → *cheddar cheese* (403/25/1.3/33) = 383 kcal<br>12g Butter → *butter* (717/0.9/0.1/81) = 86 kcal | 1066 kcal / 87.7P / 1.2C / 77.0F | 1066 kcal / 87.7P / 1.2C / 77.0F | ✅ |
| **dinner** — Pan-Seared Halibut with Gouda & Butter | 150g Halibut → *halibut* (111/22.5/0/1.6) = 166 kcal<br>42g Gouda → *gouda* (356/25/2.2/27.4) = 150 kcal<br>45g Butter → *butter* (717/0.9/0.1/81) = 323 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 639 kcal / 44.7P / 0.9C / 50.4F | 639 kcal / 44.7P / 0.9C / 50.4F | ✅ |
| **snack** — Bacon & Brie Plate | 50g Bacon → *bacon* (417/13/1.4/40) = 208 kcal<br>35g Brie → *brie* (334/20.8/0.5/27.7) = 117 kcal | 325 kcal / 13.8P / 0.9C / 29.7F | 325 kcal / 13.8P / 0.9C / 29.7F | ✅ |

**Day total on screen:** calo 2759 vs 2759 (+0.0%) / prot 201 vs 201 (+0.0%) / carb 5.8 vs 5 (+16.0%) / fats 212.1 vs 215 (-1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## balanced + allergies ['gluten', 'dairy']
Plan **Elite Balanced Performance Plan** (`3c8324b0-3494-40c4-918c-094a1c3c9480`), generated in 45s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Tropical Protein Smoothie Bowl with Almond Crunch | 225g Banana → *banana* (89/1.1/23/0.3) = 200 kcal<br>135g Mango → *mango* (60/0.8/15/0.4) = 81 kcal<br>40g Pea protein powder → *pea protein powder* (380/72/8/5) = 152 kcal<br>10g Almond butter → *almond butter* (614/21/19/56) = 61 kcal<br>75g Coconut yogurt → *coconut yogurt* (100/0.7/6/9) = 75 kcal<br>8g Chia seeds → *chia seeds* (486/17/42/31) = 39 kcal<br>10g Almonds → *almonds* (579/21/22/50) = 58 kcal<br>5g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 33 kcal<br>22g Honey → *honey* (304/0.3/82/0) = 67 kcal | 766 kcal / 38.9P / 106.4C / 26.3F | 766 kcal / 38.9P / 106.4C / 26.3F | ✅ |
| **lunch** — Grilled Chicken & Quinoa Power Bowl | 135g Chicken breast → *chicken breast* (165/31/0/3.6) = 223 kcal<br>150g Quinoa → *quinoa* (120/4.4/21/1.9) = 180 kcal<br>280g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 241 kcal<br>30g Avocado → *avocado* (160/2/9/15) = 48 kcal<br>80g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 14 kcal<br>50g Spinach → *spinach* (23/2.9/3.6/0.4) = 12 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal | 786 kcal / 56.3P / 98.8C / 18.9F | 786 kcal / 56.3P / 98.8C / 18.9F | ✅ |
| **dinner** — Pan-Seared Salmon with Herb Rice & Roasted Vegetables | 90g Salmon → *salmon* (206/22/0/12.4) = 185 kcal<br>400g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 484 kcal<br>150g Broccoli → *broccoli* (34/2.8/7/0.4) = 51 kcal<br>110g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 34 kcal<br>130g Asparagus → *asparagus* (20/2.2/4/0.1) = 26 kcal<br>9g Olive oil → *olive oil* (884/0/0/100) = 80 kcal<br>11g Garlic → *garlic* (149/6/33/0.5) = 16 kcal<br>9g Parsley → *parsley* (36/3/6.3/0.8) = 3 kcal<br>30g Lemon → *lemon* (29/1.1/9.3/0.3) = 9 kcal | 888 kcal / 43.3P / 130.1C / 23.1F | 888 kcal / 43.3P / 130.1C / 23.1F | ✅ |
| **snack** — Apple Slices with Almond Butter & Dark Chocolate | 240g Apple → *apple* (52/0.3/14/0.2) = 125 kcal<br>12g Almond butter → *almond butter* (614/21/19/56) = 74 kcal<br>8g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 48 kcal | 247 kcal / 3.8P / 39.3C / 10.6F | 247 kcal / 3.8P / 39.3C / 10.6F | ✅ |

**Day total on screen:** calo 2687 vs 2759 (-2.6%) / prot 142.3 vs 144 (-1.2%) / carb 374.6 vs 372 (+0.7%) / fats 78.9 vs 77 (+2.5%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Sweet Potato Hash with Eggs & Avocado | 375g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 322 kcal<br>120g Eggs → *eggs* (155/13/1.1/11) = 186 kcal<br>40g Turkey bacon → *turkey bacon* (233/17/1/17) = 93 kcal<br>40g Avocado → *avocado* (160/2/9/15) = 64 kcal<br>85g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 26 kcal<br>2g Onion powder → *onion powder* (341/10.4/79/1) = 7 kcal<br>40g Spinach → *spinach* (23/2.9/3.6/0.4) = 9 kcal | 707 kcal / 31.4P / 88.4C / 26.9F | 707 kcal / 31.4P / 88.4C / 26.9F | ✅ |
| **lunch** — Lean Beef Stir-Fry with Wild Rice | 95g Sirloin steak → *sirloin steak* (212/27/0/10.6) = 201 kcal<br>300g Wild rice → *wild rice* (101/4/21.3/0.3) = 303 kcal<br>120g Bok choy → *bok choy* (13/1.5/2/0.2) = 16 kcal<br>110g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 46 kcal<br>90g Carrot → *carrot* (41/0.9/10/0.2) = 37 kcal<br>75g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 16 kcal<br>21g Coconut aminos → *coconut aminos* (74/2/18/0) = 16 kcal<br>1g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 6 kcal<br>9g Ginger → *ginger* (80/1.8/18/0.8) = 7 kcal | 648 kcal / 46.4P / 91.8C / 12.4F | 648 kcal / 46.4P / 91.8C / 12.4F | ✅ |
| **dinner** — Herb-Crusted Chicken Thighs with Roasted Root Vegetables | 160g Chicken thigh → *chicken thigh* (209/26/0/10.9) = 334 kcal<br>355g Brown rice → *brown rice* (123/2.7/25.6/1) = 437 kcal<br>205g Butternut squash → *butternut squash* (45/1/11.7/0.1) = 92 kcal<br>140g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 60 kcal<br>110g Beets → *beets* (43/1.6/10/0.2) = 47 kcal<br>3g Olive oil → *olive oil* (884/0/0/100) = 27 kcal<br>3g Rosemary → *rosemary* (131/3.3/20.7/5.9) = 4 kcal<br>2g Thyme → *thyme* (101/5.6/24/1.7) = 2 kcal<br>11g Garlic → *garlic* (149/6/33/0.5) = 16 kcal | 1019 kcal / 60.7P / 143.2C / 25.0F | 1019 kcal / 60.7P / 143.2C / 25.0F | ✅ |
| **snack** — Banana & Almond Butter Energy Bites | 175g Banana → *banana* (89/1.1/23/0.3) = 156 kcal<br>10g Almond butter → *almond butter* (614/21/19/56) = 61 kcal<br>13g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 78 kcal<br>7g Chia seeds → *chia seeds* (486/17/42/31) = 34 kcal | 329 kcal / 6.2P / 50.6C / 13.8F | 329 kcal / 6.2P / 50.6C / 13.8F | ✅ |

**Day total on screen:** calo 2703 vs 2759 (-2.0%) / prot 144.7 vs 144 (+0.5%) / carb 374 vs 372 (+0.5%) / fats 78.1 vs 77 (+1.4%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Quinoa & Berry Bowl with Almond Butter Drizzle | 180g Quinoa → *quinoa* (120/4.4/21/1.9) = 216 kcal<br>225g Almond milk → *almond milk* (17/0.6/1.4/1.1) = 38 kcal<br>160g Mixed berries → *mixed berries* (43/1/10/0.3) = 69 kcal<br>15g Almond butter → *almond butter* (614/21/19/56) = 92 kcal<br>17g Honey → *honey* (304/0.3/82/0) = 52 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal<br>15g Almonds → *almonds* (579/21/22/50) = 87 kcal | 559 kcal / 17.2P / 78.6C / 22.3F | 559 kcal / 17.2P / 78.6C / 22.3F | ✅ |
| **lunch** — Mediterranean Tuna & White Bean Salad | 160g Tuna steak → *tuna steak* (130/29/0/0.6) = 208 kcal<br>185g White beans → *white beans* (139/9.7/25.1/0.4) = 257 kcal<br>145g Quinoa → *quinoa* (120/4.4/21/1.9) = 174 kcal<br>100g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 18 kcal<br>100g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 15 kcal<br>55g Arugula → *arugula* (25/2.6/3.7/0.7) = 14 kcal<br>25g Olives → *olives* (115/0.8/6.3/10.7) = 29 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>20g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal<br>5g Garlic → *garlic* (149/6/33/0.5) = 7 kcal | 797 kcal / 74.3P / 91.0C / 15.9F | 797 kcal / 74.3P / 91.0C / 15.9F | ✅ |
| **dinner** — Grass-Fed Beef & Sweet Potato Skillet | 95g Beef mince 90/10 → *beef mince 90/10* (217/26.6/0/11.7) = 206 kcal<br>340g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 292 kcal<br>215g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 260 kcal<br>70g Kale → *kale* (49/4.3/9/0.9) = 34 kcal<br>60g Red onion → *red onion* (40/1.1/9/0.1) = 24 kcal<br>105g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 33 kcal<br>115g Canned tomatoes → *canned tomatoes* (32/1.6/7.3/0.3) = 37 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>3g Cumin → *cumin* (375/17.8/44/22) = 11 kcal<br>2g Smoked paprika → *smoked paprika* (282/14/54/13) = 6 kcal | 974 kcal / 45.6P / 151.0C / 22.6F | 974 kcal / 45.6P / 151.0C / 22.6F | ✅ |
| **snack** — Trail Mix Energy Bites | 60g Dates → *dates* (282/2.5/75/0.4) = 169 kcal<br>13g Cashews → *cashews* (553/18/30/44) = 72 kcal<br>8g Pumpkin seeds → *pumpkin seeds* (559/30/11/49) = 45 kcal<br>11g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 66 kcal<br>5g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 33 kcal | 385 kcal / 7.4P / 55.7C / 17.6F | 385 kcal / 7.4P / 55.7C / 17.6F | ✅ |

**Day total on screen:** calo 2715 vs 2759 (-1.6%) / prot 144.5 vs 144 (+0.3%) / carb 376.3 vs 372 (+1.2%) / fats 78.4 vs 77 (+1.8%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 snack: “Apple Slices with Almond Butter & Dark Chocolate” → “Pear & Almond Butter Energy Snack” (2s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Tropical Protein Smoothie Bowl with Almond Crunch | 225g Banana → *banana* (89/1.1/23/0.3) = 200 kcal<br>135g Mango → *mango* (60/0.8/15/0.4) = 81 kcal<br>40g Pea protein powder → *pea protein powder* (380/72/8/5) = 152 kcal<br>10g Almond butter → *almond butter* (614/21/19/56) = 61 kcal<br>75g Coconut yogurt → *coconut yogurt* (100/0.7/6/9) = 75 kcal<br>8g Chia seeds → *chia seeds* (486/17/42/31) = 39 kcal<br>10g Almonds → *almonds* (579/21/22/50) = 58 kcal<br>5g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 33 kcal<br>22g Honey → *honey* (304/0.3/82/0) = 67 kcal | 766 kcal / 38.9P / 106.4C / 26.3F | 766 kcal / 38.9P / 106.4C / 26.3F | ✅ |
| **lunch** — Grilled Chicken & Quinoa Power Bowl | 135g Chicken breast → *chicken breast* (165/31/0/3.6) = 223 kcal<br>150g Quinoa → *quinoa* (120/4.4/21/1.9) = 180 kcal<br>280g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 241 kcal<br>30g Avocado → *avocado* (160/2/9/15) = 48 kcal<br>80g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 14 kcal<br>50g Spinach → *spinach* (23/2.9/3.6/0.4) = 12 kcal<br>6g Olive oil → *olive oil* (884/0/0/100) = 53 kcal<br>15g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>8g Garlic → *garlic* (149/6/33/0.5) = 12 kcal | 786 kcal / 56.3P / 98.8C / 18.9F | 786 kcal / 56.3P / 98.8C / 18.9F | ✅ |
| **dinner** — Pan-Seared Salmon with Herb Rice & Roasted Vegetables | 90g Salmon → *salmon* (206/22/0/12.4) = 185 kcal<br>400g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 484 kcal<br>150g Broccoli → *broccoli* (34/2.8/7/0.4) = 51 kcal<br>110g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 34 kcal<br>130g Asparagus → *asparagus* (20/2.2/4/0.1) = 26 kcal<br>9g Olive oil → *olive oil* (884/0/0/100) = 80 kcal<br>11g Garlic → *garlic* (149/6/33/0.5) = 16 kcal<br>9g Parsley → *parsley* (36/3/6.3/0.8) = 3 kcal<br>30g Lemon → *lemon* (29/1.1/9.3/0.3) = 9 kcal | 888 kcal / 43.3P / 130.1C / 23.1F | 888 kcal / 43.3P / 130.1C / 23.1F | ✅ |
| **snack** — Pear & Almond Butter Energy Snack | 240g Pear → *pear* (57/0.4/15/0.1) = 137 kcal<br>11g Almond butter → *almond butter* (614/21/19/56) = 68 kcal<br>8g Dark chocolate chips → *dark chocolate chips* (598/7.8/43/42) = 48 kcal | 253 kcal / 3.9P / 41.5C / 9.8F | 253 kcal / 3.9P / 41.5C / 9.8F | ✅ |

**Day total on screen:** calo 2693 vs 2759 (-2.4%) / prot 142.4 vs 144 (-1.1%) / carb 376.8 vs 372 (+1.3%) / fats 78.1 vs 77 (+1.4%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


---
## vegan + allergies ['nuts', 'soy']
Plan **Elite Vegan High-Performance 3-Day Plan** (`76424ea7-ddec-496e-a51e-4de33df0e075`), generated in 44s. Targets: 2759 kcal / 144.0P / 372.0C / 77.0F


#### Day 1

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Protein-Packed Berry Quinoa Bowl | 225g Quinoa → *quinoa* (120/4.4/21/1.9) = 270 kcal<br>25g Pea protein powder → *pea protein powder* (380/72/8/5) = 95 kcal<br>115g Blueberry → *blueberry* (57/0.7/14/0.3) = 66 kcal<br>95g Strawberry → *strawberry* (32/0.7/8/0.3) = 30 kcal<br>15g Chia seeds → *chia seeds* (486/17/42/31) = 73 kcal<br>21g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 55 kcal<br>145g Plant milk → *plant milk* (35/1.5/4/1.8) = 51 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal | 645 kcal / 34.2P / 100.7C / 13.3F | 645 kcal / 34.2P / 100.7C / 13.3F | ✅ |
| **lunch** — Mediterranean Lentil Power Bowl | 215g Lentils → *lentils* (116/9/20/0.4) = 249 kcal<br>135g Quinoa → *quinoa* (120/4.4/21/1.9) = 162 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>75g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 11 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>40g Arugula → *arugula* (25/2.6/3.7/0.7) = 10 kcal<br>19g Tahini → *tahini* (595/17/23/54) = 113 kcal<br>14g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>14g Olive oil → *olive oil* (884/0/0/100) = 124 kcal<br>4g Garlic → *garlic* (149/6/33/0.5) = 6 kcal | 720 kcal / 31.9P / 90.8C / 28.6F | 720 kcal / 31.9P / 90.8C / 28.6F | ✅ |
| **dinner** — Seitan Stir-Fry with Brown Rice | 120g Seitan → *seitan* (166/25/14/2) = 199 kcal<br>325g Brown rice → *brown rice* (123/2.7/25.6/1) = 400 kcal<br>115g Broccoli → *broccoli* (34/2.8/7/0.4) = 39 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>100g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 42 kcal<br>70g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 15 kcal<br>25g Coconut aminos → *coconut aminos* (74/2/18/0) = 18 kcal<br>10g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 57 kcal<br>13g Coconut oil → *coconut oil* (862/0/0/100) = 112 kcal<br>8g Ginger → *ginger* (80/1.8/18/0.8) = 6 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal | 936 kcal / 51.0P / 135.7C / 25.0F | 936 kcal / 51.0P / 135.7C / 25.0F | ✅ |
| **snack** — Tropical Protein Smoothie | 30g Pea protein powder → *pea protein powder* (380/72/8/5) = 114 kcal<br>95g Banana → *banana* (89/1.1/23/0.3) = 85 kcal<br>90g Mango → *mango* (60/0.8/15/0.4) = 54 kcal<br>30g Spinach → *spinach* (23/2.9/3.6/0.4) = 7 kcal<br>175g Plant milk → *plant milk* (35/1.5/4/1.8) = 61 kcal<br>8g Chia seeds → *chia seeds* (486/17/42/31) = 39 kcal<br>3g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 20 kcal | 380 kcal / 28.4P / 49.9C / 9.8F | 380 kcal / 28.4P / 49.9C / 9.8F | ✅ |

**Day total on screen:** calo 2681 vs 2759 (-2.8%) / prot 145.5 vs 144 (+1.0%) / carb 377.1 vs 372 (+1.4%) / fats 76.7 vs 77 (-0.4%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 2

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Loaded Sweet Potato Protein Hash | 230g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 198 kcal<br>130g Black beans → *black beans* (132/9/24/0.5) = 172 kcal<br>24g Pea protein powder → *pea protein powder* (380/72/8/5) = 91 kcal<br>50g Kale → *kale* (49/4.3/9/0.9) = 24 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>45g Salsa → *salsa* (36/2/8/0.2) = 16 kcal<br>8g Olive oil → *olive oil* (884/0/0/100) = 71 kcal<br>2g Cumin → *cumin* (375/17.8/44/22) = 8 kcal<br>2g Smoked paprika → *smoked paprika* (282/14/54/13) = 6 kcal | 691 kcal / 38.2P / 98.5C / 19.1F | 691 kcal / 38.2P / 98.5C / 19.1F | ✅ |
| **lunch** — Chickpea Buddha Bowl with Tahini Drizzle | 135g Chickpeas → *chickpeas* (164/9/27/2.6) = 221 kcal<br>75g Farro → *farro* (170/7/34/1.5) = 128 kcal<br>35g Roasted chickpeas → *chickpeas* (164/9/27/2.6) = 57 kcal<br>85g Brussels sprouts → *brussels sprouts* (43/3.4/9/0.3) = 37 kcal<br>120g Sweet potato → *sweet potato* (86/1.6/20/0.1) = 103 kcal<br>40g Kale → *kale* (49/4.3/9/0.9) = 20 kcal<br>17g Tahini → *tahini* (595/17/23/54) = 101 kcal<br>19g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 4 kcal<br>10g Olive oil → *olive oil* (884/0/0/100) = 88 kcal<br>2g Garlic powder → *garlic powder* (331/16.6/73/0.7) = 7 kcal | 766 kcal / 30.3P / 113.3C / 25.5F | 766 kcal / 30.3P / 113.3C / 25.5F | ✅ |
| **dinner** — Hearty Lentil Bolognese with Whole Wheat Pasta | 130g Whole wheat pasta → *whole wheat pasta* (149/6/30/1.1) = 194 kcal<br>235g Lentils → *lentils* (116/9/20/0.4) = 273 kcal<br>140g Canned tomatoes → *canned tomatoes* (32/1.6/7.3/0.3) = 45 kcal<br>35g Tomato paste → *tomato paste* (82/4.3/18.9/0.5) = 29 kcal<br>85g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 19 kcal<br>75g Carrot → *carrot* (41/0.9/10/0.2) = 31 kcal<br>60g Celery → *celery* (16/0.7/3/0.2) = 10 kcal<br>70g Spinach → *spinach* (23/2.9/3.6/0.4) = 16 kcal<br>19g Olive oil → *olive oil* (884/0/0/100) = 168 kcal<br>9g Garlic → *garlic* (149/6/33/0.5) = 13 kcal<br>3g Dried herbs → *dried herbs* (265/9/69/4.3) = 8 kcal | 806 kcal / 39.2P / 122.5C / 22.9F | 806 kcal / 39.2P / 122.5C / 22.9F | ✅ |
| **snack** — Pea Protein & Berry Oat Bar | 30g Rolled oats → *rolled oats* (389/17/66/7) = 117 kcal<br>45g Pea protein powder → *pea protein powder* (380/72/8/5) = 171 kcal<br>65g Blueberry → *blueberry* (57/0.7/14/0.3) = 37 kcal<br>17g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 44 kcal<br>6g Coconut oil → *coconut oil* (862/0/0/100) = 52 kcal | 421 kcal / 38.0P / 43.9C / 10.5F | 421 kcal / 38.0P / 43.9C / 10.5F | ✅ |

**Day total on screen:** calo 2684 vs 2759 (-2.7%) / prot 145.7 vs 144 (+1.2%) / carb 378.2 vs 372 (+1.7%) / fats 78 vs 77 (+1.3%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


#### Day 3

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — High-Protein Oat Pancakes with Berry Compote | 75g Rolled oats → *rolled oats* (389/17/66/7) = 292 kcal<br>40g Pea protein powder → *pea protein powder* (380/72/8/5) = 152 kcal<br>65g Banana → *banana* (89/1.1/23/0.3) = 58 kcal<br>135g Plant milk → *plant milk* (35/1.5/4/1.8) = 47 kcal<br>100g Mixed berries → *mixed berries* (43/1/10/0.3) = 43 kcal<br>21g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 55 kcal<br>10g Flax seeds → *flax seeds* (534/18/29/42) = 53 kcal<br>4g Coconut oil → *coconut oil* (862/0/0/100) = 34 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal<br>3g Vanilla extract → *vanilla extract* (288/0.1/12.7/0.1) = 9 kcal | 748 kcal / 47.2P / 102.1C / 18.3F | 748 kcal / 47.2P / 102.1C / 18.3F | ✅ |
| **lunch** — Protein-Loaded Black Bean Burrito Bowl | 180g Black beans → *black beans* (132/9/24/0.5) = 238 kcal<br>150g Brown rice → *brown rice* (123/2.7/25.6/1) = 184 kcal<br>70g Pinto beans → *pinto beans* (143/9/26.2/0.7) = 100 kcal<br>65g Sweet corn → *sweet corn* (86/3.2/19/1.2) = 56 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>50g Avocado → *avocado* (160/2/9/15) = 80 kcal<br>55g Salsa → *salsa* (36/2/8/0.2) = 20 kcal<br>14g Lime juice → *lime juice* (25/0.4/8/0.1) = 4 kcal<br>10g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 2 kcal<br>2g Cumin → *cumin* (375/17.8/44/22) = 8 kcal<br>2g Chili powder → *chili powder* (282/13.5/50/14.3) = 6 kcal | 723 kcal / 32.6P / 129.3C / 12.3F | 723 kcal / 32.6P / 129.3C / 12.3F | ✅ |
| **dinner** — Lentil & Vegetable Curry with Basmati Rice | 145g Lentils → *lentils* (116/9/20/0.4) = 168 kcal<br>155g Basmati rice → *basmati rice* (121/3.5/25.2/0.4) = 188 kcal<br>100g Coconut milk → *coconut milk* (230/2.3/5.5/23.8) = 230 kcal<br>5g Onion powder → *onion powder* (341/10.4/79/1) = 17 kcal<br>6g Curry powder → *curry powder* (325/14.3/56/14) = 20 kcal<br>3g Turmeric → *turmeric* (312/9.7/67/3.3) = 9 kcal<br>4g Garlic powder → *garlic powder* (331/16.6/73/0.7) = 13 kcal<br>14g Ginger → *ginger* (80/1.8/18/0.8) = 11 kcal<br>70g Spinach → *spinach* (23/2.9/3.6/0.4) = 16 kcal<br>100g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 31 kcal<br>70g Carrot → *carrot* (41/0.9/10/0.2) = 29 kcal<br>290g Vegetable broth → *vegetable broth* (6/0.2/1/0.2) = 17 kcal<br>10g Olive oil → *olive oil* (884/0/0/100) = 88 kcal<br>2g Sea salt → *sea salt* (0/0/0/0) = 0 kcal<br>10g Cilantro → *cilantro* (23/2.1/3.7/0.5) = 2 kcal | 839 kcal / 27.8P / 107.2C / 37.5F | 839 kcal / 27.8P / 107.2C / 37.5F | ✅ |
| **snack** — Energy-Boosting Green Protein Smoothie | 40g Pea protein powder → *pea protein powder* (380/72/8/5) = 152 kcal<br>65g Banana → *banana* (89/1.1/23/0.3) = 58 kcal<br>80g Pineapple → *pineapple* (50/0.5/13/0.1) = 40 kcal<br>40g Spinach → *spinach* (23/2.9/3.6/0.4) = 9 kcal<br>170g Plant milk → *plant milk* (35/1.5/4/1.8) = 60 kcal<br>8g Hemp seed → *hemp seed* (553/32/9/49) = 44 kcal<br>50g Coconut water → *coconut water* (19/0.7/3.7/0.2) = 10 kcal<br>9g Lime juice → *lime juice* (25/0.4/8/0.1) = 2 kcal | 375 kcal / 36.5P / 40.1C / 9.6F | 375 kcal / 36.5P / 40.1C / 9.6F | ✅ |

**Day total on screen:** calo 2685 vs 2759 (-2.7%) / prot 144.1 vs 144 (+0.1%) / carb 378.7 vs 372 (+1.8%) / fats 77.7 vs 77 (+0.9%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target


### Swap test — Day 1 breakfast: “Protein-Packed Berry Quinoa Bowl” → “Spiced Lentil & Chickpea Flour Porridge with Mango” (6s)


#### Day 1 (after swap)

| Meal | Ingredients (grams → database entry, per 100g kcal/P/C/F) | Calculated from ingredients | On screen | Match |
|---|---|---|---|---|
| **breakfast** — Spiced Lentil & Chickpea Flour Porridge with Mango | 120g Lentils → *lentils* (116/9/20/0.4) = 139 kcal<br>75g Chickpea flour → *chickpea flour* (387/22/58/6) = 290 kcal<br>85g Mango → *mango* (60/0.8/15/0.4) = 51 kcal<br>250g Plant milk → *plant milk* (35/1.5/4/1.8) = 88 kcal<br>2g Cinnamon → *cinnamon* (247/4/81/1.2) = 5 kcal<br>4g Ginger → *ginger* (80/1.8/18/0.8) = 3 kcal<br>11g Maple syrup → *maple syrup* (260/0.1/67/0.1) = 29 kcal<br>7g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 46 kcal<br>1g Sea salt → *sea salt* (0/0/0/0) = 0 kcal | 651 kcal / 32.5P / 101.7C / 14.3F | 651 kcal / 32.5P / 101.7C / 14.3F | ✅ |
| **lunch** — Mediterranean Lentil Power Bowl | 215g Lentils → *lentils* (116/9/20/0.4) = 249 kcal<br>135g Quinoa → *quinoa* (120/4.4/21/1.9) = 162 kcal<br>95g Cherry tomatoes → *cherry tomatoes* (18/0.9/3.9/0.2) = 17 kcal<br>75g Cucumber → *cucumber* (15/0.7/3.6/0.1) = 11 kcal<br>80g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 25 kcal<br>40g Arugula → *arugula* (25/2.6/3.7/0.7) = 10 kcal<br>19g Tahini → *tahini* (595/17/23/54) = 113 kcal<br>14g Lemon juice → *lemon juice* (22/0.4/7/0.2) = 3 kcal<br>14g Olive oil → *olive oil* (884/0/0/100) = 124 kcal<br>4g Garlic → *garlic* (149/6/33/0.5) = 6 kcal | 720 kcal / 31.9P / 90.8C / 28.6F | 720 kcal / 31.9P / 90.8C / 28.6F | ✅ |
| **dinner** — Seitan Stir-Fry with Brown Rice | 120g Seitan → *seitan* (166/25/14/2) = 199 kcal<br>325g Brown rice → *brown rice* (123/2.7/25.6/1) = 400 kcal<br>115g Broccoli → *broccoli* (34/2.8/7/0.4) = 39 kcal<br>125g Red bell pepper → *red bell pepper* (31/1/6/0.3) = 39 kcal<br>100g Snap peas → *snap peas* (42/2.8/7.6/0.2) = 42 kcal<br>70g Mushroom → *mushroom* (22/3.1/3.3/0.3) = 15 kcal<br>25g Coconut aminos → *coconut aminos* (74/2/18/0) = 18 kcal<br>10g Sesame seeds → *sesame seeds* (573/17.7/23.5/49.7) = 57 kcal<br>13g Coconut oil → *coconut oil* (862/0/0/100) = 112 kcal<br>8g Ginger → *ginger* (80/1.8/18/0.8) = 6 kcal<br>6g Garlic → *garlic* (149/6/33/0.5) = 9 kcal | 936 kcal / 51.0P / 135.7C / 25.0F | 936 kcal / 51.0P / 135.7C / 25.0F | ✅ |
| **snack** — Tropical Protein Smoothie | 30g Pea protein powder → *pea protein powder* (380/72/8/5) = 114 kcal<br>95g Banana → *banana* (89/1.1/23/0.3) = 85 kcal<br>90g Mango → *mango* (60/0.8/15/0.4) = 54 kcal<br>30g Spinach → *spinach* (23/2.9/3.6/0.4) = 7 kcal<br>175g Plant milk → *plant milk* (35/1.5/4/1.8) = 61 kcal<br>8g Chia seeds → *chia seeds* (486/17/42/31) = 39 kcal<br>3g Coconut flakes → *coconut flakes* (660/6.9/23.7/64.5) = 20 kcal | 380 kcal / 28.4P / 49.9C / 9.8F | 380 kcal / 28.4P / 49.9C / 9.8F | ✅ |

**Day total on screen:** calo 2687 vs 2759 (-2.6%) / prot 143.8 vs 144 (-0.1%) / carb 378.1 vs 372 (+1.6%) / fats 77.7 vs 77 (+0.9%) → ✅ within 5%; day total = sum of meals: ✅; app badge: On target

